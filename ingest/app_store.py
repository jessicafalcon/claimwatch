"""Strict parser from the App Store feed's shape to the eight `raw_reviews`
columns (spec Phase 2, pinned decision 2; CLAUDE.md -> Before DONE #8).

A page we did not write can change under us, so this file declares exactly
which fields it expects and what type each must be, and refuses the WHOLE page
— naming the page, the item and the field — the moment one is missing or
malformed. It never guesses a rating, defaults a date, or drops a review
quietly: a silently skipped review would move a count with no trace. Widening
the accepted shape is a deliberate, tested change here, never a `.get(...,
default)`.

The declared shape:
  {"feed": {"entry": [item, ...]}}     `entry` absent -> an empty page (the end
                                       of the feed); anything but a list -> refused
  item["id"]["label"]          digit string        -> external_id
  item["title"]["label"]       string              -> title
  item["content"]["label"]     string              -> body
  item["im:rating"]["label"]   digit string, 1..5  -> rating (int)
  item["updated"]["label"]     ISO 8601 with offset-> review_date (its YYYY-MM-DD)
`author`, `im:version`, `im:voteSum`, `link` are never read: the raw shape has
no column for a reviewer's name, and none enters the warehouse.

Captures are read back by `ingest/captures.py` through `parse()` (Phase 3a):
`page-<n>.json` is the body as served, `page-<n>.meta.json` beside it carries
the provenance stamped at fetch — a rebuild reads no clock."""

from __future__ import annotations

import json
import re
from datetime import datetime

from ingest.parsed import PageShapeError, Parsed, refuse
from ingest.sources import ROOT, Source

SOURCE = "app-store"  # the platform slug, as in fixtures/anchors/
EXTENSION = "json"
SAMPLE_PLATFORM = SOURCE
SAMPLE_HOST = "itunes.apple.com"
SAMPLE_DIR = ROOT / "fixtures" / "app-store"
RATING_MIN, RATING_MAX = 1, 5
_DIGITS = re.compile(r"^[0-9]+$")

FeedShapeError = PageShapeError  # the Phase 2 name; one refusal class for every parser
_refuse = refuse


def _label(item: object, field: str, page_url: str, item_id: str | None) -> str:
    """`item[field]["label"]` as a string, or a refusal naming the field."""
    if not isinstance(item, dict) or field not in item:
        raise _refuse(page_url, item_id, field, "is missing")
    holder = item[field]
    if not isinstance(holder, dict) or "label" not in holder:
        raise _refuse(page_url, item_id, field, "has no 'label'")
    label = holder["label"]
    if not isinstance(label, str):
        raise _refuse(
            page_url, item_id, field, f"is {type(label).__name__}, not a string"
        )
    return label


def _rating(label: str, page_url: str, item_id: str) -> int:
    if not _DIGITS.match(label):
        raise _refuse(
            page_url, item_id, "im:rating", f"is not a digit string: {label!r}"
        )
    value = int(label)
    if not RATING_MIN <= value <= RATING_MAX:
        raise _refuse(page_url, item_id, "im:rating", f"is outside 1..5: {value}")
    return value


def _review_date(label: str, page_url: str, item_id: str) -> str:
    """The item's own date: the YYYY-MM-DD the feed states, no timezone
    arithmetic. The whole label must parse as an ISO 8601 timestamp with an
    offset, and its date part must be the one printed."""
    try:
        parsed = datetime.fromisoformat(label)
    except ValueError as exc:
        raise _refuse(
            page_url, item_id, "updated", f"is not ISO 8601: {label!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise _refuse(page_url, item_id, "updated", f"has no offset: {label!r}")
    date = label[:10]
    if parsed.date().isoformat() != date:
        raise _refuse(page_url, item_id, "updated", f"date part unreadable: {label!r}")
    return date


def parse_item(
    item: object, page_url: str, captured_at: str, platform: str = SOURCE
) -> dict[str, object]:
    """One feed item -> one raw-shape row, or a refusal."""
    item_id = _label(item, "id", page_url, None)
    if not _DIGITS.match(item_id):
        raise _refuse(page_url, item_id, "id", "is not a digit string")
    return {
        "source": platform,
        "external_id": item_id,
        "source_url": page_url,
        "captured_at": captured_at,
        "review_date": _review_date(
            _label(item, "updated", page_url, item_id), page_url, item_id
        ),
        "rating": _rating(
            _label(item, "im:rating", page_url, item_id), page_url, item_id
        ),
        "title": _label(item, "title", page_url, item_id),
        "body": _label(item, "content", page_url, item_id),
    }


def parse_page(
    body: bytes | str, page_url: str, captured_at: str, platform: str = SOURCE
) -> list[dict[str, object]]:
    """A feed page -> raw-shape rows. Refuses the whole page on the first item
    that is not the declared shape; an absent `entry` is the end of the feed."""
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise _refuse(page_url, None, "<body>", "is not JSON") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("feed"), dict):
        raise _refuse(page_url, None, "feed", "is missing or not an object")
    feed = doc["feed"]
    if "entry" not in feed:
        return []
    entries = feed["entry"]
    if not isinstance(entries, list):
        raise _refuse(
            page_url, None, "entry", f"is {type(entries).__name__}, not a list"
        )
    return [parse_item(item, page_url, captured_at, platform) for item in entries]


def parse(body: bytes | str, page_url: str, captured_at: str, source: Source) -> Parsed:
    """The uniform parser entry point (Phase 3a): a feed page -> review rows."""
    return Parsed(reviews=parse_page(body, page_url, captured_at, source.platform))
