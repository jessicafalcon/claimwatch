"""An insurer's review-profile page on Opinion Assurances -> review rows and one
snapshot row (spec Phase 3a, pinned decision 4, amendment A1). The page marks
its data inline with schema.org microdata (`itemscope` / `itemprop`), which
this parser walks with the stdlib HTML parser; everything else on the page is
layout and is never read.

The declared shape, from the structure dump of 2026-09-02 (DECISIONS -> Phase
3a, Gotchas). One page holds:

  [itemscope itemtype=".../review"]            one scope per review, in page order
    [itemscope itemprop=reviewRating]            <meta itemprop=ratingValue content=N>
                                                 N a digit 1..5   -> rating
    [itemscope itemprop=author]                  NEVER READ (a Person: a pseudonym
                                                 and a member link)
    div.oa_description, its own text             "Avis publié le dd/mm/yyyy suite à une
                                                 expérience le dd/mm/yyyy": the first
                                                 date -> review_date (YYYY-MM-DD),
                                                 the second is the experience date
      h4.oa_text                                 the review text -> body (title = "")
  [itemscope itemtype=".../AggregateRating"]   exactly one per page:
    <meta itemprop=ratingValue content=x.y>      0..5 -> snapshot rating
    <meta itemprop=ratingCount content=N>        -> snapshot review_count

A review missing its rating, its sentence or its body, a rating outside 1..5,
a date that does not parse, or a page with two aggregates refuses the WHOLE
page naming page, review (its position on the page) and field. A page with an
aggregate and no review scope is the end of the list (an empty page); a page
with neither is not a profile page and is refused.

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
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from html.parser import HTMLParser

from ingest.parsed import Parsed, refuse
from ingest.sources import ROOT, Source

EXTENSION = "html"
SAMPLE_PLATFORM = "opinion-assurances"
SAMPLE_HOST = "www.opinion-assurances.fr"
SAMPLE_DIR = ROOT / "fixtures" / "opinion-assurances"
_SENTENCE = re.compile(
    r"^\S+ publié le (\d{2}/\d{2}/\d{4}) suite à une expérience le (\d{2}/\d{2}/\d{4})$"
)
_REVIEW_TYPE = re.compile(r"^https?://schema\.org/review$", re.I)
_AGGREGATE_TYPE = re.compile(r"^https?://schema\.org/aggregaterating$", re.I)
_PERSON_TYPE = re.compile(r"^https?://schema\.org/person$", re.I)
_VOID = frozenset({"meta", "br", "img", "input", "hr", "link", "source", "wbr"})
_SEP = "\x1f"
_PLACES = Decimal("0.001")


def _classes(attrs: dict[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


class _Review:
    def __init__(self) -> None:
        self.rating: str | None = None
        self.ratings_seen = 0  # more than one ratingValue is outside the shape
        self.sentence: list[str] = []
        self.body: list[str] = []
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
            ):
                self.aggregates[-1][itemprop] = attrs.get("content")
            elif (
                self.current is not None
                and self.current.author_depth is None
                and self.rating_depth is not None
                and itemprop == "ratingValue"
            ):
                self.current.rating = attrs.get("content")
        if tag in _VOID:
            return
        self.open.setdefault(tag, []).append(len(self.stack))
        self.stack.append((tag, attrs))
        if scope and _REVIEW_TYPE.match(itemtype):
            if self.review_depth is not None:
                self.nested_reviews += 1  # outside the shape: refused, never dropped
                return
            self.review_depth = depth
            self.reviews.append(_Review())
            return
        if scope and _AGGREGATE_TYPE.match(itemtype) and self.aggregate_depth is None:
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
            itemprop == "author" or _PERSON_TYPE.match(itemtype)
        ):
            review.author_depth = depth
        elif scope and itemprop == "reviewRating" and self.rating_depth is None:
            self.rating_depth = depth
        elif "oa_description" in _classes(attrs) and self.desc_depth is None:
            self.desc_depth = depth
        elif "oa_text" in _classes(attrs) and self.desc_depth is not None:
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
    if not re.fullmatch(r"[1-5]", review.rating):
        raise refuse(
            page_url, item, "ratingValue", f"is not a digit 1..5: {review.rating!r}"
        )
    if len(review.sentence) != 1:
        raise refuse(
            page_url,
            item,
            "oa_description",
            f"holds {len(review.sentence)} texts, not one sentence",
        )
    m = _SENTENCE.match(review.sentence[0])
    if not m:
        raise refuse(page_url, item, "oa_description", "is not the declared sentence")
    published = _iso(m.group(1), page_url, item, "published")
    experienced = _iso(m.group(2), page_url, item, "experience")
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
        "rating": int(review.rating),
        "title": "",
        "body": body,
    }


def _snapshot_row(
    aggregate: dict[str, str | None], page_url: str, captured_at: str, source: Source
) -> dict[str, object]:
    value = aggregate.get("ratingValue")
    if value is None or not re.fullmatch(r"[0-9]+(\.[0-9]+)?", value):
        raise refuse(page_url, None, "ratingValue", f"is not a number: {value!r}")
    try:
        rating = Decimal(value).quantize(_PLACES, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise refuse(
            page_url, None, "ratingValue", f"is not a number: {value!r}"
        ) from exc
    if not Decimal(0) <= rating <= Decimal(5):
        raise refuse(page_url, None, "ratingValue", f"is outside 0..5: {value!r}")
    count = aggregate.get("ratingCount")
    if count is None or not re.fullmatch(r"[0-9]+", count):
        raise refuse(
            page_url, None, "ratingCount", f"is not a non-negative integer: {count!r}"
        )
    return {
        "source": source.platform,
        "profile": source.profile,
        "segment": source.segment,
        "channel": source.channel,
        "origin": "fetch",
        "rating": rating,
        "review_count": int(count),
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
