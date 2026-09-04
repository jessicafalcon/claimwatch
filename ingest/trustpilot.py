"""The Trustpilot review profile, read from an authorized export (spec Phase 3c).

Trustpilot disallows our crawler (its robots.txt ends `User-agent: *` ->
`Disallow: /`) and its terms forbid automated collection, so Phase 3b (A1)
declared it not fetchable and read one aggregate rating point by hand. The
developer now holds written authorization (recorded in `ingest/sources.py`'s
`terms` and in DECISIONS), and the reviews arrive as one authorized export in
the webscraper.io column shape, saved as a capture's `page-1.csv` — NOT a live
`ingest/fetch.py` capture (DECISIONS -> Gotchas). `fetchable` stays False: our
crawler never runs against Trustpilot.

This parser turns that one page into review rows for `raw_reviews`. It keeps
only the review's own content — the rating (the last number of the star-image
URL), the date, the headline and the body — and drops the reviewer's name,
avatar, country and the layout columns, so no personal data reaches any table
(spec Phase 3c, done-when 3; PROJECT_BRIEF §2.5). The column set, the star-URL
spelling and the date shape are a declaration: a file whose header is not the
export's, a rating that is not a Trustpilot star URL, or a date that is not
`Month D, YYYY` raises `PageShapeError`, and the whole page loads nothing (§8).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from ingest.parsed import Parsed, refuse, review_rating
from ingest.sources import Source

ROOT = Path(__file__).resolve().parent.parent

EXTENSION = "csv"
SAMPLE_PLATFORM = "trustpilot"
SAMPLE_HOST = "ca.trustpilot.com"
SAMPLE_DIR = ROOT / "fixtures" / "trustpilot"
# A fictional company, no brand (D1): the frozen sample proves the parser path
# without committing a real profile's reviews.
SAMPLE_PAGES = ("https://ca.trustpilot.com/review/exemple-fictif.com?languages=all",)

# The export's columns, exactly, in webscraper.io's order. A header that is not
# this refuses: the shape is a declaration, not a guess.
COLUMNS = (
    "web_scraper_order",
    "web_scraper_start_url",
    "pagination",
    "headline",
    "name",
    "reviewbody",
    "data",
    "data2",
    "data3",
    "name2",
    "data4",
    "data5",
    "data6",
    "addresscountry",
    "data7",
    "image",
    "rating",
)
# The columns whose content becomes a review row; every other column (the
# reviewer's name, avatar, country and the layout cells) is read from nowhere,
# so personal data never reaches a table (done-when 3).
_TITLE, _BODY, _DATE_COL, _RATING_COL = "headline", "reviewbody", "data3", "rating"

# The rating is the last number of the star image's URL — the closed set of
# spellings Trustpilot serves is `stars-1` .. `stars-5`; `review_rating` then
# admits it only as a member of `parsed.REVIEW_RATINGS` (whole stars are
# members). An unknown URL, or a number outside 1..5, refuses.
_STARS = re.compile(
    r"\Ahttps://cdn\.trustpilot\.net/brand-assets/[0-9.]+/stars/stars-([0-9]+)\.svg\Z"
)

# The review date as the export writes it: an English month name, a day and a
# year ("September 3, 2026"). Parsed with an explicit month table, never
# `strptime('%B')`, so the reading does not depend on the process locale (spec
# Phase 3c, stack risk (b)); no clock reaches the data path.
_DATE = re.compile(r"\A([A-Z][a-z]+) ([0-9]{1,2}), ([0-9]{4})\Z")
_MONTHS = {
    name: n
    for n, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}

_SEP = "\x1f"  # the external-id payload separator (unit separator; not in text)


def _rating(value: str, page_url: str, item: str) -> Decimal:
    """The review's rating from the star-image URL, or a refusal naming the
    field: the URL must be a Trustpilot star URL and its number a half-step
    1..5 (`parsed.REVIEW_RATINGS`)."""
    m = _STARS.fullmatch(value)
    if m is None:
        raise refuse(
            page_url, item, _RATING_COL, f"is not a Trustpilot star URL: {value!r}"
        )
    rating = review_rating(m.group(1))
    if rating is None:
        raise refuse(
            page_url, item, _RATING_COL, f"is not a half-step 1..5: stars-{m.group(1)}"
        )
    return rating


def _review_date(value: str, page_url: str, item: str) -> str:
    """The review date as `YYYY-MM-DD`, or a refusal: the export writes
    `Month D, YYYY` with an English month; anything else is outside the shape."""
    m = _DATE.fullmatch(value)
    if m is None:
        raise refuse(page_url, item, _DATE_COL, f"is not 'Month D, YYYY': {value!r}")
    month = _MONTHS.get(m.group(1))
    if month is None:
        raise refuse(page_url, item, _DATE_COL, f"names no month: {m.group(1)!r}")
    try:
        return date(int(m.group(3)), month, int(m.group(2))).isoformat()
    except ValueError as exc:
        raise refuse(
            page_url, item, _DATE_COL, f"is not a real day: {value!r}"
        ) from exc


def parse(body: bytes | str, page_url: str, captured_at: str, source: Source) -> Parsed:
    """One authorized-export page -> its review rows (no snapshot: the rating
    stays hand-read, spec Phase 3c central constraint). A header that is not
    the export's, or any cell outside its declared shape, refuses the page."""
    text = (
        body.decode("utf-8-sig", errors="replace")
        if isinstance(body, (bytes, bytearray))
        else body
    )
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise refuse(page_url, None, "columns", f"are not the export's {COLUMNS}")
    reviews: list[dict[str, object]] = []
    for k, row in enumerate(reader, 1):
        item = str(k)
        if None in row or None in row.values():
            raise refuse(page_url, item, "row", "has the wrong number of cells")
        rating = _rating(row[_RATING_COL], page_url, item)
        review_date = _review_date(row[_DATE_COL], page_url, item)
        title = row[_TITLE]
        body_text = row[_BODY]  # may be empty: a rating-only review keeps its title
        # The review's identity is its own content (like opinion_assurances):
        # this export carries no stable public review id, so a re-import of the
        # same review is one fingerprint and inserts nothing.
        payload = _SEP.join((review_date, title, body_text, format(rating, "f")))
        reviews.append(
            {
                "source": source.platform,
                "external_id": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "source_url": page_url,
                "captured_at": captured_at,
                "review_date": review_date,
                "rating": rating,
                "title": title,
                "body": body_text,
            }
        )
    return Parsed(reviews=reviews)
