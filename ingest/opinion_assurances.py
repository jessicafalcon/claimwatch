"""An insurer's review-profile page on Opinion Assurances -> review rows and one
snapshot row (spec Phase 3a, pinned decision 4, amendment A1). The page marks
its data inline with schema.org microdata (`itemscope` / `itemprop`), which
this parser walks with the stdlib HTML parser; everything else on the page is
layout and is never read.

The declared shape, from the structure dump of 2026-09-02 (DECISIONS -> Phase
3a, Gotchas). One page holds:

  [itemscope itemtype=".../review"]            one scope per review, in page order
    [itemscope itemprop=reviewRating]            <meta itemprop=worstRating content=1>
                                                 <meta itemprop=bestRating content=5>
                                                 the site's own scale for a review;
                                                 any other declared scale refuses,
                                                 so a value the site does not admit
                                                 is never admitted here (A6)
                                                 <meta itemprop=ratingValue content=N>
                                                 N a half-step 1..5, a digit or a
                                                 digit and `.5` (A6) -> rating
    [itemscope itemprop=author]                  NEVER READ (a Person: a pseudonym
                                                 and a member link)
    div.oa_description, its own text             "Avis publié le dd/mm/yyyy suite à une
                                                 expérience le dd/mm/yyyy": the first
                                                 date -> review_date (YYYY-MM-DD),
                                                 the second is the experience date
    h4.oa_text                                   the review text -> body (title = "");
                                                 a child of the review scope, read
                                                 wherever it sits in the scope outside
                                                 the author markup, exactly one (A5:
                                                 the live page has it FOLLOW the
                                                 description; the first sample nested
                                                 it inside, and the guard keyed on that)
  [itemscope itemtype=".../AggregateRating"]   exactly one per page:
                                                 <meta itemprop=worstRating content=0>
                                                 <meta itemprop=bestRating content=5>
                                                 the site's scale for the aggregate;
                                                 another declared scale refuses (A8)
    <meta itemprop=ratingValue content=x.y>      0..5 -> snapshot rating
    <meta itemprop=ratingCount content=N>        -> snapshot review_count

A review missing its rating, its sentence or its body, carrying two ratings or
two bodies, a rating outside the half-steps 1..5, a date that does not parse,
or a page with two aggregates refuses the WHOLE page naming page, review (its
position on the page) and field. A page with an aggregate and no review scope
is the end of the list (an empty page); a page with neither is not a profile
page and is refused.

`external_id`: the page marks no stable review identifier (the only per-review
link is the reviewer's member page, an author field), so the id is a content
hash — sha256 over the publication date, the experience date, the rating and
the body. Deterministic and author-free; the cost, recorded in BACKLOG: an
edited review is a new review, not a new version of one. The one-star share,
response rate and response delay the page displays are layout text, not data,
and are not read; those figures stay Documented from the anchors."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser

from ingest.parsed import (
    MEASURES,
    REVIEW_RATINGS,
    Parsed,
    count_in_range,
    rating_from_page,
    refuse,
    review_rating,
)
from ingest.sources import ROOT, Source, profile_pages

EXTENSION = "html"
SAMPLE_PLATFORM = "opinion-assurances"
SAMPLE_HOST = "www.opinion-assurances.fr"
SAMPLE_DIR = ROOT / "fixtures" / "opinion-assurances"
# The frozen sample's three page addresses, as its meta files carry them: a
# fake, nameless profile (A4 (c)).
SAMPLE_PAGES = profile_pages(f"https://{SAMPLE_HOST}/assureur-exemple-fictif.html", 3)
_SENTENCE = re.compile(
    r"\A\S+ publié le (\d{2}/\d{2}/\d{4}) "
    r"suite à une expérience le (\d{2}/\d{2}/\d{4})\Z"
)
# Matched whole, like every shape (exit pass, code-reviewer #3).
_REVIEW_TYPE = re.compile(r"\Ahttps?://schema\.org/review\Z", re.I)
_AGGREGATE_TYPE = re.compile(r"\Ahttps?://schema\.org/aggregaterating\Z", re.I)
_PERSON_TYPE = re.compile(r"\Ahttps?://schema\.org/person\Z", re.I)
# The scale a review scope declares (`worstRating`, `bestRating`): the bounds
# of `parsed.REVIEW_RATINGS`, which admits exactly the site's scale. A bound
# is a number, compared as one — `5` and `5.0` declare the same scale — read
# through a bounded digit shape so no page text reaches `Decimal()` unchecked
# (round 4, code-reviewer #10).
REVIEW_SCALE = (min(REVIEW_RATINGS), max(REVIEW_RATINGS))
# The scale the aggregate scope declares: the snapshot rating column's range
# (`parsed.MEASURES["rating"]`, 0..5), the one guard for both scopes (A8 (c)).
AGGREGATE_SCALE = (MEASURES["rating"].lo, MEASURES["rating"].hi)
_BOUND = re.compile(r"[0-9]{1,3}(\.[0-9]{1,3})?")


def _declared_scale(
    worst: str | None, best: str | None
) -> tuple[Decimal, Decimal] | None:
    """The scale a review scope declares, as numbers; None when a bound is
    missing or is not a number in the shape."""
    if worst is None or best is None:
        return None
    if not (_BOUND.fullmatch(worst) and _BOUND.fullmatch(best)):
        return None
    return (Decimal(worst), Decimal(best))


_VOID = frozenset({"meta", "br", "img", "input", "hr", "link", "source", "wbr"})
_SEP = "\x1f"


def _classes(attrs: dict[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


class _Review:
    def __init__(self) -> None:
        self.rating: str | None = None
        self.ratings_seen = 0  # more than one ratingValue is outside the shape
        self.worst: str | None = None  # the scale the review declares (A6)
        self.best: str | None = None
        # A bound declared twice is outside the shape, as a second ratingValue
        # is — counted, never resolved last-wins (round 5, code-reviewer #3).
        self.bounds_seen: dict[str, int] = {"worstRating": 0, "bestRating": 0}
        self.sentence: list[str] = []
        self.body: list[str] = []
        self.bodies_seen = 0  # more than one oa_text is outside the shape (A5)
        self.author_depth: int | None = None  # skipped while set


class _Walker(HTMLParser):
    """Walks the page once, keeping the open-element stack, and fills one
    `_Review` per review scope and the aggregate's two values."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str | None]]] = []
        # For each tag, the stack positions of its open elements, innermost
        # last: closing an element is a pop, never a rescan of the stack, so a
        # page with thousands of unclosed elements and stray closers costs
        # time linear in its size (round 1, security-reviewer #1).
        self.open: dict[str, list[int]] = {}
        self.reviews: list[_Review] = []
        self.review_depth: int | None = None
        self.rating_depth: int | None = None
        self.desc_depth: int | None = None
        self.body_depth: int | None = None
        self.aggregate_depth: int | None = None
        self.aggregates: list[dict[str, str | None]] = []
        self.aggregate_duplicates: list[str] = []
        self.nested_reviews = 0  # a review scope inside a review scope
        self.nested_aggregates = 0  # an aggregate inside a review or the aggregate

    @property
    def current(self) -> _Review | None:
        return self.reviews[-1] if self.review_depth is not None else None

    def handle_starttag(
        self, tag: str, attrs_list: list[tuple[str, str | None]]
    ) -> None:
        attrs = dict(attrs_list)
        depth = len(self.stack) + 1
        scope = "itemscope" in attrs
        itemtype = attrs.get("itemtype") or ""
        itemprop = attrs.get("itemprop") or ""
        if tag == "meta":  # a value carried as data, in whichever scope is open
            if self.aggregate_depth is not None and itemprop in (
                "ratingValue",
                "ratingCount",
                "worstRating",
                "bestRating",
            ):
                if itemprop in self.aggregates[-1]:
                    self.aggregate_duplicates.append(itemprop)  # outside the shape
                self.aggregates[-1][itemprop] = attrs.get("content")
            elif (
                self.current is not None
                and self.current.author_depth is None
                and self.rating_depth is not None
            ):
                if itemprop == "ratingValue":
                    self.current.ratings_seen += 1
                    self.current.rating = attrs.get("content")
                elif itemprop == "worstRating":
                    self.current.bounds_seen[itemprop] += 1
                    self.current.worst = attrs.get("content")
                elif itemprop == "bestRating":
                    self.current.bounds_seen[itemprop] += 1
                    self.current.best = attrs.get("content")
        if tag in _VOID:
            return
        self.open.setdefault(tag, []).append(len(self.stack))
        self.stack.append((tag, attrs))
        if scope and _REVIEW_TYPE.fullmatch(itemtype):
            if self.review_depth is not None:
                self.nested_reviews += 1  # outside the shape: refused, never dropped
                return
            self.review_depth = depth
            self.reviews.append(_Review())
            return
        if scope and _AGGREGATE_TYPE.fullmatch(itemtype):
            # The profile's aggregate stands on its own: one inside a review
            # would be that review's numbers, one inside the aggregate would
            # merge its values into it. Both are outside the shape and refuse,
            # never dropped or merged (round 2, code-reviewer #8,
            # functionality-tester F1; the class of round 1's finding 7).
            if self.aggregate_depth is not None or self.review_depth is not None:
                self.nested_aggregates += 1
                return
            self.aggregate_depth = depth
            self.aggregates.append({})
            return
        review = self.current
        if review is None:
            return
        # Author markup is skipped wherever it sits and however it is marked:
        # an `author` property with or without a scope, or any `Person` — the
        # kind of the guard is "this element is about a person", not "this
        # element is the author scope" (round 1, functionality-tester F3).
        if review.author_depth is None and (
            itemprop == "author" or _PERSON_TYPE.fullmatch(itemtype)
        ):
            review.author_depth = depth
        elif scope and itemprop == "reviewRating" and self.rating_depth is None:
            self.rating_depth = depth
        elif "oa_description" in _classes(attrs) and self.desc_depth is None:
            self.desc_depth = depth
        elif "oa_text" in _classes(attrs) and review.author_depth is None:
            # The review's text, wherever it sits in the scope: the live page
            # has it follow the description, not sit inside it (A5). Every
            # `oa_text` in the scope is counted, one nested in another
            # included — "exactly one body" is a count of elements, not of
            # openings (round 4, code-reviewer #7, functionality-tester #2).
            review.bodies_seen += 1
            if self.body_depth is None:
                self.body_depth = depth

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        positions = self.open.get(tag)
        if not positions:
            return  # a stray closer with nothing open: ignored
        idx = positions.pop()
        for inner, _ in self.stack[idx + 1 :]:  # closed implicitly with their parent
            self.open[inner].pop()
        del self.stack[idx:]
        depth = len(self.stack)
        review = self.current
        if (
            review is not None
            and review.author_depth is not None
            and review.author_depth > depth
        ):
            review.author_depth = None
        for name in ("rating_depth", "desc_depth", "body_depth", "aggregate_depth"):
            value = getattr(self, name)
            if value is not None and value > depth:
                setattr(self, name, None)
        if self.review_depth is not None and self.review_depth > depth:
            self.review_depth = None

    def handle_data(self, data: str) -> None:
        review = self.current
        if review is None or review.author_depth is not None:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self.body_depth is not None:
            review.body.append(text)
        elif self.desc_depth is not None and len(self.stack) == self.desc_depth:
            review.sentence.append(text)  # the description's OWN text, not a child's


def _iso(day: str, page_url: str, item: str, field: str) -> str:
    """dd/mm/yyyy -> YYYY-MM-DD, a real day, else a refusal."""
    d, m, y = day.split("/")
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError as exc:
        raise refuse(page_url, item, field, f"is not a real day: {day!r}") from exc


def _review_row(
    k: int, review: _Review, page_url: str, captured_at: str, source: Source
) -> dict[str, object]:
    item = f"review {k}"
    if review.rating is None:
        raise refuse(page_url, item, "ratingValue", "is missing")
    if review.ratings_seen > 1:
        raise refuse(
            page_url,
            item,
            "ratingValue",
            f"appears {review.ratings_seen} times, not once",
        )
    for bound, seen in review.bounds_seen.items():
        if seen > 1:
            raise refuse(page_url, item, bound, f"appears {seen} times, not once")
    if _declared_scale(review.worst, review.best) != REVIEW_SCALE:
        # The site declares each review's scale; ours admits exactly it. A
        # page declaring another (a 0, a 10) refuses here, so a value the
        # site does not admit is never admitted by widening our set (A6).
        raise refuse(
            page_url,
            item,
            "worstRating/bestRating",
            f"declares the scale {review.worst!r}..{review.best!r}, "
            f"not {REVIEW_SCALE[0]}..{REVIEW_SCALE[1]}",
        )
    rating = review_rating(review.rating)
    if rating is None:
        raise refuse(
            page_url,
            item,
            "ratingValue",
            f"is not a half-step 1..5: {review.rating!r}",
        )
    if len(review.sentence) != 1:
        raise refuse(
            page_url,
            item,
            "oa_description",
            f"holds {len(review.sentence)} texts, not one sentence",
        )
    m = _SENTENCE.fullmatch(review.sentence[0])
    if not m:
        raise refuse(page_url, item, "oa_description", "is not the declared sentence")
    published = _iso(m.group(1), page_url, item, "published")
    experienced = _iso(m.group(2), page_url, item, "experience")
    if review.bodies_seen > 1:
        raise refuse(
            page_url, item, "oa_text", f"appears {review.bodies_seen} times, not once"
        )
    body = " ".join(review.body)
    if not body:
        raise refuse(page_url, item, "oa_text", "is missing or empty")
    payload = _SEP.join((published, experienced, review.rating, body))
    return {
        "source": source.platform,
        "external_id": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "source_url": page_url,
        "captured_at": captured_at,
        "review_date": published,
        "rating": rating,
        "title": "",
        "body": body,
    }


def _snapshot_row(
    aggregate: dict[str, str | None], page_url: str, captured_at: str, source: Source
) -> dict[str, object]:
    declared = _declared_scale(
        aggregate.get("worstRating"), aggregate.get("bestRating")
    )
    if declared != AGGREGATE_SCALE:
        # The site declares the aggregate's scale as it declares each review's;
        # the snapshot rating column admits 0..5 and nothing else, so an
        # aggregate declared on another scale refuses instead of landing as a
        # 0-5 rating tagged Measured (A8 (c)).
        raise refuse(
            page_url,
            None,
            "worstRating/bestRating",
            f"declares the aggregate's scale {aggregate.get('worstRating')!r}.."
            f"{aggregate.get('bestRating')!r}, not "
            f"{AGGREGATE_SCALE[0]}..{AGGREGATE_SCALE[1]}",
        )
    value = aggregate.get("ratingValue")
    rating = rating_from_page(value) if value is not None else None
    if rating is None:
        raise refuse(
            page_url, None, "ratingValue", f"is not a number in 0..5: {value!r}"
        )
    count = count_in_range(aggregate.get("ratingCount"))
    if count is None:
        raise refuse(
            page_url,
            None,
            "ratingCount",
            "is not a non-negative integer the count column holds: "
            f"{aggregate.get('ratingCount')!r}",
        )
    return {
        "source": source.platform,
        "profile": source.profile,
        "segment": source.segment,
        "channel": source.channel,
        "origin": "fetch",
        "rating": rating,
        "review_count": count,
        "one_star_share": None,
        "response_rate": None,
        "response_delay_days": None,
        "source_url": page_url,
        "captured_at": captured_at,
    }


def parse(body: bytes | str, page_url: str, captured_at: str, source: Source) -> Parsed:
    """One profile page -> its review rows and one snapshot row; an empty page
    (an aggregate, no review) is the end of the list; a page with neither is
    refused."""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    w = _Walker()
    w.feed(text)
    w.close()
    # Structure first: a scope inside a scope names the cause; the counts
    # and duplicates it would produce are its symptoms.
    if w.nested_reviews:
        raise refuse(
            page_url,
            None,
            "review",
            f"{w.nested_reviews} review scope(s) nested in a review",
        )
    if w.nested_aggregates:
        raise refuse(
            page_url,
            None,
            "aggregateRating",
            f"{w.nested_aggregates} aggregate scope(s) nested in a review or in "
            "the aggregate",
        )
    if len(w.aggregates) > 1:
        raise refuse(
            page_url,
            None,
            "aggregateRating",
            f"appears {len(w.aggregates)} times, not once",
        )
    if not w.aggregates:
        raise refuse(
            page_url, None, "aggregateRating", "is missing: not a profile page"
        )
    if w.aggregate_duplicates:
        raise refuse(
            page_url, None, w.aggregate_duplicates[0], "appears twice in the aggregate"
        )
    if not w.reviews:
        return Parsed()  # the end of the list
    reviews = [
        _review_row(k, r, page_url, captured_at, source)
        for k, r in enumerate(w.reviews, 1)
    ]
    return Parsed(
        reviews=reviews,
        snapshots=[_snapshot_row(w.aggregates[0], page_url, captured_at, source)],
    )
