"""The Trustpilot authorized-export parser (spec Phase 3c): it maps the export's
columns to review rows, reads the rating from the star-image URL and the date
from an English `Month D, YYYY`, drops every personal and layout column, and
refuses anything outside the declared shape (done-when 2, 3; §8)."""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import pytest

from ingest.parsed import PageShapeError
from ingest.sources import sample_source
from ingest.trustpilot import COLUMNS, parse

SRC = sample_source("trustpilot")
URL = "https://ca.trustpilot.com/review/exemple-fictif.com?languages=all"
STAMP = "2026-09-04T12:00:00"
STARS = "https://cdn.trustpilot.net/brand-assets/4.1.0/stars/stars-{}.svg"

# The columns a review's content comes from; every other column is filled with
# a marker no parsed value may carry, so a leak shows up as the marker.
_LEAK = "LEAKMARKERXYZ"


def _row(**over: str) -> dict[str, str]:
    row = {c: _LEAK for c in COLUMNS}
    row.update(
        web_scraper_order="r1",
        web_scraper_start_url=URL,
        headline="Un titre",
        reviewbody="Un corps de texte.",
        data3="September 3, 2026",
        rating=STARS.format(5),
    )
    row.update(over)
    return row


def _csv(*rows: dict[str, str], columns: tuple[str, ...] = COLUMNS) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return ("﻿" + buf.getvalue()).encode("utf-8")  # a BOM, as the export has


def _parse(*rows: dict[str, str]):
    return parse(_csv(*rows), URL, STAMP, SRC).reviews


def test_maps_rating_date_title_body_and_only_those():
    (review,) = _parse(
        _row(
            headline="Rapide", reviewbody="Remboursement clair.", rating=STARS.format(4)
        )
    )
    assert review["rating"] == Decimal("4")
    assert review["review_date"] == "2026-09-03"
    assert review["title"] == "Rapide"
    assert review["body"] == "Remboursement clair."
    assert review["source"] == "trustpilot"
    assert review["source_url"] == URL and review["captured_at"] == STAMP
    # Exactly the eight raw-review fields: no reviewer name, avatar or country.
    assert set(review) == {
        "source",
        "external_id",
        "source_url",
        "captured_at",
        "review_date",
        "rating",
        "title",
        "body",
    }


def test_dropped_columns_reach_no_field():
    """done-when 3: name, avatar, country and the layout cells are read from
    nowhere — a marker planted in every non-content column appears in no value."""
    (review,) = _parse(_row())  # every non-content column is the marker
    assert _LEAK not in "".join(str(v) for v in review.values())


def test_a_rating_only_review_keeps_its_title_with_an_empty_body():
    (review,) = _parse(
        _row(headline="Sans texte", reviewbody="", rating=STARS.format(3))
    )
    assert review["rating"] == Decimal("3") and review["title"] == "Sans texte"
    assert review["body"] == ""


@pytest.mark.parametrize(
    "value",
    [
        STARS.format(7),  # a number outside 1..5
        STARS.format(0),
        "https://cdn.trustpilot.net/brand-assets/4.1.0/stars/stars-4.png",  # not svg
        "https://example.com/stars-5.svg",  # not the trustpilot host/path
        "5",
        "",
    ],
)
def test_a_rating_that_is_not_a_known_star_url_refuses(value):
    with pytest.raises(PageShapeError, match="rating"):
        _parse(_row(rating=value))


@pytest.mark.parametrize(
    "value",
    [
        "3 hours ago",  # the relative time, not the date column
        "2026-09-03",  # ISO, not the export's spelling
        "Septembre 3, 2026",  # a French month name: locale-independent, refused
        "Foo 3, 2026",  # not a month
        "February 30, 2026",  # not a real day
        "September 3",  # no year
        "",
    ],
)
def test_a_date_that_is_not_month_day_year_refuses(value):
    with pytest.raises(PageShapeError, match="data3"):
        _parse(_row(data3=value))


def test_a_header_that_is_not_the_export_refuses():
    short = COLUMNS[:-1]  # drop the rating column
    with pytest.raises(PageShapeError, match="columns"):
        parse(_csv(_row(), columns=short), URL, STAMP, SRC)


def test_identical_content_is_one_fingerprint():
    """The review's identity is its content, so the same review twice is one
    external_id — the basis of re-import idempotency (done-when 6)."""
    a, b = _parse(
        _row(
            web_scraper_order="x", headline="T", reviewbody="B", rating=STARS.format(5)
        ),
        _row(
            web_scraper_order="y", headline="T", reviewbody="B", rating=STARS.format(5)
        ),
    )
    assert a["external_id"] == b["external_id"]
    # A different body is a different review.
    (c,) = _parse(_row(headline="T", reviewbody="Autre", rating=STARS.format(5)))
    assert c["external_id"] != a["external_id"]
