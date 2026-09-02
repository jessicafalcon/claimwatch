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

Captures are read back by `read_captures`: `page-<n>.json` is the body as
served, `page-<n>.meta.json` beside it carries the provenance stamped at fetch
(`source_url`, `captured_at`, `status`) — a rebuild reads no clock."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from ingest.politeness import ALLOWED_HOSTS

SOURCE = "app-store"  # the platform slug, as in fixtures/anchors/
RATING_MIN, RATING_MAX = 1, 5
_DIGITS = re.compile(r"^[0-9]+$")
_PAGE = re.compile(r"^page-([0-9]+)\.json$")
META_FIELDS = ("source_url", "captured_at", "status")
_STAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")


class FeedShapeError(ValueError):
    """The page is not the declared shape; nothing from it is loaded."""


def _refuse(page_url: str, item_id: str | None, field: str, why: str) -> FeedShapeError:
    where = f"item {item_id!r}" if item_id is not None else "page"
    return FeedShapeError(f"{page_url}: {where}: field {field!r} {why}")


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


def parse_item(item: object, page_url: str, captured_at: str) -> dict[str, object]:
    """One feed item -> one raw-shape row, or a refusal."""
    item_id = _label(item, "id", page_url, None)
    if not _DIGITS.match(item_id):
        raise _refuse(page_url, item_id, "id", "is not a digit string")
    return {
        "source": SOURCE,
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
    body: bytes | str, page_url: str, captured_at: str
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
    return [parse_item(item, page_url, captured_at) for item in entries]


def read_meta(path: Path) -> dict[str, object]:
    """`page-<n>.meta.json`, strictly (fix amendment A4): exactly the three
    provenance fields, each in the shape the fetcher writes — `captured_at` a
    real `YYYY-MM-DDTHH:MM:SS` instant (it is staging's dedup sort key),
    `source_url` an https address on an allowed host, `status` the integer 200.
    Anything else refuses the capture with the file and field named."""
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FeedShapeError(f"{path}: meta is missing or not JSON") from exc
    if not isinstance(meta, dict) or set(meta) != set(META_FIELDS):
        raise FeedShapeError(f"{path}: meta must have exactly {META_FIELDS}")
    stamp = meta["captured_at"]
    if not isinstance(stamp, str) or not _STAMP.match(stamp):
        raise FeedShapeError(f"{path}: field 'captured_at' is not YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise FeedShapeError(
            f"{path}: field 'captured_at' is not a real instant"
        ) from exc
    url = meta["source_url"]
    parts = urlsplit(url) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise FeedShapeError(
            f"{path}: field 'source_url' is not an https address on {ALLOWED_HOSTS}"
        )
    status = meta["status"]
    if type(status) is not int or status != 200:
        raise FeedShapeError(f"{path}: field 'status' is not 200")
    return meta


def capture_pages(capture_dir: Path) -> list[Path]:
    """The `page-<n>.json` files of one capture, in page order."""
    pages = []
    for p in capture_dir.iterdir():
        m = _PAGE.match(p.name)
        if m:
            pages.append((int(m.group(1)), p))
    return [p for _, p in sorted(pages)]


def has_pages(root: Path) -> bool:
    """Whether anything under `root` is a page a rebuild would load — the same
    rule `read_captures` applies, so a refused page (`page-<n>.refused.json`)
    counts for neither."""
    return root.is_dir() and any(_PAGE.match(p.name) for p in root.rglob("page-*.json"))


def read_captures(root: Path) -> list[tuple[str, list[dict[str, object]]]]:
    """Every capture under `root` -> [(capture_id, rows)], captures in name
    order, pages in page order, items in feed order. A capture is any directory
    holding `page-<n>.json` files; `root` itself may be one (the fixture). A
    missing root is zero captures, not an error (a fresh clone)."""
    if not root.is_dir():
        return []
    dirs = sorted({p.parent for p in root.rglob("page-*.json") if _PAGE.match(p.name)})
    out: list[tuple[str, list[dict[str, object]]]] = []
    for d in dirs:
        rows: list[dict[str, object]] = []
        for page in capture_pages(d):
            try:
                meta = read_meta(
                    page.with_name(page.name[: -len(".json")] + ".meta.json")
                )
                rows.extend(
                    parse_page(
                        page.read_bytes(),
                        str(meta["source_url"]),
                        str(meta["captured_at"]),
                    )
                )
            except FeedShapeError as exc:
                # Which file to fix: the capture directory, then the page's own line.
                raise FeedShapeError(f"capture {d}: {exc}") from exc
        out.append((d.name, rows))
    return out
