"""A store or platform listing page -> one snapshot row (spec Phase 3a, pinned
decisions 3 and 4). Such pages carry a block written for search engines,
`<script type="application/ld+json">` in the schema.org vocabulary, that
states the average rating and the count as plain data. This parser reads that
block and nothing else: the declared shape is exactly one object carrying
`aggregateRating`, whose `ratingValue` is a number between 0 and 5 (as a digit
string or a number) and whose count is `ratingCount` or `reviewCount` (a
non-negative integer, as a digit string or a number). A page with no such
object, with two, or with a value outside the shape refuses the whole page
naming the field. The block's `name`, `author`, `url` and any `review` items
are never read.

The page's value is kept to three decimals (`decimal(4,3)`, rounded
half-even) — every platform's displayed value fits exactly and a mart can
average it."""

from __future__ import annotations

import math
from decimal import Decimal
from html.parser import HTMLParser

from ingest.parsed import (
    PageShapeError,
    Parsed,
    count_in_range,
    decode_json,
    rating_from_page,
    refuse,
)
from ingest.sources import ROOT, Source

EXTENSION = "html"
SAMPLE_PLATFORM = "google-play"  # the frozen sample is written in that store's shape
SAMPLE_HOST = "play.google.com"
SAMPLE_DIR = ROOT / "fixtures" / "listings"
# A rating, as a JSON number or a digit string, and a count alike must fit
# their columns: `parsed.rating_from_page` (a bounded digit run — at most two
# digits before the point and thirty-two after, a store prints fifteen — so
# nothing long reaches Decimal(); round 1, security-reviewer #2) and
# `parsed.count_in_range`, both derived from the one declaration of the
# columns (A4 (a)).


class _Blocks(HTMLParser):
    """Collects the text of every `<script type="application/ld+json">`."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._in = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            types = [v for k, v in attrs if k == "type"]
            self._in = (
                bool(types)
                and types[0] is not None
                and (types[0].strip().lower() == "application/ld+json")
            )
            if self._in:
                self.blocks.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in = False

    def handle_data(self, data: str) -> None:
        if self._in:
            self.blocks[-1] += data


def _objects(doc: object) -> list[dict[str, object]]:
    """The schema.org objects one JSON-LD block declares: the block itself, the
    items of a list, or the items of a `@graph`."""
    if isinstance(doc, dict):
        graph = doc.get("@graph")
        return [doc] + (
            [g for g in graph if isinstance(g, dict)] if isinstance(graph, list) else []
        )
    if isinstance(doc, list):
        return [d for d in doc if isinstance(d, dict)]
    return []


def _rating(value: object, page_url: str) -> Decimal:
    # The shape is a finite number: a bounded digit string, or a JSON number
    # that is not a bool and not NaN or an infinity — `json.loads` accepts
    # those spellings, and a non-finite Decimal would raise at the range
    # comparison, a traceback past the parser (round 3, security-reviewer #2).
    if isinstance(value, bool) or not (
        isinstance(value, str)
        or (isinstance(value, int | float) and math.isfinite(value))
    ):
        raise refuse(page_url, None, "ratingValue", f"is not a number: {value!r}")
    rating = rating_from_page(str(value))
    if rating is None:
        raise refuse(
            page_url, None, "ratingValue", f"is not a number in 0..5: {value!r}"
        )
    return rating


def _count(aggregate: dict[str, object], page_url: str) -> int:
    present = [k for k in ("ratingCount", "reviewCount") if k in aggregate]
    if not present:
        raise refuse(
            page_url, None, "ratingCount", "is missing (and so is reviewCount)"
        )
    if len(present) > 1:
        # Two foreign values for one figure are never resolved by preference;
        # like a second ratingValue, they are the page outside its shape
        # (round 3, code-reviewer #6).
        raise refuse(
            page_url, None, "ratingCount", "and reviewCount both appear: one count"
        )
    field_name = present[0]
    value = aggregate[field_name]
    count = count_in_range(value)
    if count is None:
        raise refuse(
            page_url,
            None,
            field_name,
            f"is not a non-negative integer the count column holds: {value!r}",
        )
    return count


def parse(body: bytes | str, page_url: str, captured_at: str, source: Source) -> Parsed:
    """One listing page -> one snapshot row, or a refusal."""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    collector = _Blocks()
    collector.feed(text)
    carrying: list[dict[str, object]] = []
    for block in collector.blocks:
        try:
            doc = decode_json(block, page_url, "<script>")
        except PageShapeError:
            continue  # a block the decoder cannot read declares nothing
        carrying.extend(o for o in _objects(doc) if "aggregateRating" in o)
    if not carrying:
        raise refuse(
            page_url,
            None,
            "aggregateRating",
            "is missing: no JSON-LD object carries it",
        )
    if len(carrying) > 1:
        raise refuse(
            page_url,
            None,
            "aggregateRating",
            f"appears {len(carrying)} times, not once",
        )
    aggregate = carrying[0]["aggregateRating"]
    if not isinstance(aggregate, dict) or "ratingValue" not in aggregate:
        raise refuse(
            page_url, None, "aggregateRating", "is not an object with ratingValue"
        )
    row: dict[str, object] = {
        "source": source.platform,
        "profile": source.profile,
        "segment": source.segment,
        "channel": source.channel,
        "origin": "fetch",
        "rating": _rating(aggregate["ratingValue"], page_url),
        "review_count": _count(aggregate, page_url),
        "one_star_share": None,
        "response_rate": None,
        "response_delay_days": None,
        "source_url": page_url,
        "captured_at": captured_at,
    }
    return Parsed(snapshots=[row])
