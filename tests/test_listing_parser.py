"""The listing parser (spec Phase 3a, invariant 6; done-when 5 and 6): one
JSON-LD `aggregateRating` per page, strictly, and nothing else read. Every
negative case is built in memory by mutating the frozen sample."""

from __future__ import annotations

import copy
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from ingest.listing import SAMPLE_DIR, parse
from ingest.parsed import PageShapeError
from ingest.sources import sample_source
from tests import pins

SRC = sample_source("listing")
PAGE_URL = pins.LISTING_SAMPLE_ROW["source_url"]
CAPTURED = pins.LISTING_SAMPLE_CAPTURED_AT
_BLOCK = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)


def _html() -> str:
    return (SAMPLE_DIR / "page-1.html").read_text(encoding="utf-8")


def _block() -> dict:
    return json.loads(_BLOCK.search(_html()).group(2))


def _with_block(doc: object) -> str:
    return _BLOCK.sub(lambda m: m.group(1) + json.dumps(doc) + m.group(3), _html())


def test_sample_maps_to_one_snapshot_row_matching_pins():
    parsed = parse(_html(), PAGE_URL, CAPTURED, SRC)
    assert parsed.reviews == [] and len(parsed.snapshots) == 1
    row = parsed.snapshots[0]
    assert row["rating"] == Decimal(pins.LISTING_SAMPLE_ROW["rating"])
    assert row["one_star_share"] is None and row["response_rate"] is None
    assert row["response_delay_days"] is None
    shown = {k: (str(v) if k == "rating" else v) for k, v in row.items()}
    for k, v in pins.LISTING_SAMPLE_ROW.items():
        assert shown[k] == v, k
    assert (
        SAMPLE_DIR == Path(__file__).resolve().parent.parent / "fixtures" / "listings"
    )


def test_only_the_aggregate_rating_is_read():
    """Dropping the name, author, url, description and every review leaves the
    row identical; the row carries no name and no author."""
    doc = _block()
    stripped = {"aggregateRating": doc["aggregateRating"]}
    html = _with_block(stripped).replace('<div class="review">', "<div>")
    assert parse(html, PAGE_URL, CAPTURED, SRC) == parse(
        _html(), PAGE_URL, CAPTURED, SRC
    )
    row = parse(_html(), PAGE_URL, CAPTURED, SRC).snapshots[0]
    assert not {"author", "name", "url"} & set(row)


def test_no_aggregate_rating_refuses_the_page():
    doc = _block()
    del doc["aggregateRating"]
    with pytest.raises(PageShapeError, match="'aggregateRating' is missing"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)
    with pytest.raises(PageShapeError, match="'aggregateRating' is missing"):
        parse("<html><body>no block</body></html>", PAGE_URL, CAPTURED, SRC)
    with pytest.raises(PageShapeError, match="'aggregateRating' is missing"):
        parse(_with_block("not an object"), PAGE_URL, CAPTURED, SRC)


def test_two_aggregate_ratings_refuse_the_page():
    doc = _block()
    html = _with_block([doc, copy.deepcopy(doc)])
    with pytest.raises(PageShapeError, match="appears 2 times"):
        parse(html, PAGE_URL, CAPTURED, SRC)
    twice = _html().replace("</head>", _BLOCK.search(_html()).group(0) + "</head>")
    with pytest.raises(PageShapeError, match="appears 2 times"):
        parse(twice, PAGE_URL, CAPTURED, SRC)


@pytest.mark.parametrize(
    "value",
    [
        "5.1",
        "-0.5",
        "abc",
        "",
        True,
        None,
        [4],
        {"x": 1},
        "4,5",
        float("nan"),
        float("inf"),
        -float("inf"),
        "NaN",
        "Infinity",
    ],
)
def test_rating_outside_the_shape_is_refused(value):
    """A rating is a finite number; `json.loads` accepts `NaN` and `Infinity`
    as numbers, and either is outside the shape and refuses in one line rather
    than raising at the range check (round 3, security-reviewer #2)."""
    doc = _block()
    doc["aggregateRating"]["ratingValue"] = value
    with pytest.raises(PageShapeError, match="'ratingValue'"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)


@pytest.mark.parametrize(
    "value",
    ["-1", "12.5", "", True, None, "many", 3.5, -5, 2**31, "2147483648", 10**11],
)
def test_count_outside_the_shape_is_refused(value):
    """The shape is the column's: a non-negative integer up to 2^31 - 1, as a
    JSON number or a digit string alike — a negative number, or one the
    column cannot hold, refuses at the parse, never as a driver exception at
    the load (round 2, code-reviewer #2 #3, security-reviewer #1 #2)."""
    doc = _block()
    doc["aggregateRating"]["ratingCount"] = value
    with pytest.raises(PageShapeError, match="'ratingCount'"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)


def test_the_count_bound_is_the_columns_and_its_edge_loads():
    """MAX_COUNT is the `integer` column's ceiling; a count exactly there, as a
    number or a string, is inside the shape."""
    from ingest.parsed import MAX_COUNT

    assert MAX_COUNT == 2**31 - 1
    for value in (MAX_COUNT, str(MAX_COUNT), 0, "0"):
        doc = _block()
        doc["aggregateRating"]["ratingCount"] = value
        row = parse(_with_block(doc), PAGE_URL, CAPTURED, SRC).snapshots[0]
        assert row["review_count"] == int(value)


def test_count_may_be_review_count_and_values_may_be_numbers():
    """The App Store form (`reviewCount`) and numeric JSON values are inside the
    declared shape; a missing count of either name refuses."""
    doc = _block()
    agg = doc["aggregateRating"]
    del agg["ratingCount"]
    agg["reviewCount"] = 13000
    agg["ratingValue"] = 4.9
    row = parse(_with_block(doc), PAGE_URL, CAPTURED, SRC).snapshots[0]
    assert row["review_count"] == 13000 and row["rating"] == Decimal("4.900")
    del agg["reviewCount"]
    with pytest.raises(PageShapeError, match="'ratingCount' is missing"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)


def test_rating_is_rounded_half_even_to_three_places():
    doc = _block()
    cases = [
        ("4.766666889190674", "4.767"),
        ("4.1235", "4.124"),
        ("4.1225", "4.122"),
        (5, "5.000"),
    ]
    for value, kept in cases:
        doc["aggregateRating"]["ratingValue"] = value
        row = parse(_with_block(doc), PAGE_URL, CAPTURED, SRC).snapshots[0]
        assert row["rating"] == Decimal(kept), value


def test_a_graph_block_is_searched_one_level_down():
    doc = {"@context": "https://schema.org", "@graph": [{"@type": "x"}, _block()]}
    row = parse(_with_block(doc), PAGE_URL, CAPTURED, SRC).snapshots[0]
    assert row["review_count"] == 1234


def test_refusal_names_page_and_field():
    doc = _block()
    doc["aggregateRating"]["ratingValue"] = "six"
    with pytest.raises(PageShapeError) as exc:
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)
    assert PAGE_URL in str(exc.value) and "'ratingValue'" in str(exc.value)
    assert "\n" not in str(exc.value)


def test_sample_is_obviously_fake_and_nameless():
    html = _html()
    assert "hand-written fixture" in html and "FICTIONAL" in html
    doc = _block()
    assert doc["author"]["name"] == "developer-placeholder"
    assert "fictive" in doc["name"] and "example.fictional.app" in PAGE_URL
    assert "reviewer-placeholder" in html


def test_an_absurdly_long_digit_string_refuses_not_tracebacks():
    """Round 1, security-reviewer #2: a 5,000-digit count or rating is outside
    the shape and refuses through PageShapeError; it never reaches int()."""
    doc = _block()
    doc["aggregateRating"]["ratingCount"] = "9" * 5000
    with pytest.raises(PageShapeError, match="'ratingCount'"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)
    doc = _block()
    doc["aggregateRating"]["ratingValue"] = "4." + "9" * 5000
    with pytest.raises(PageShapeError, match="'ratingValue'"):
        parse(_with_block(doc), PAGE_URL, CAPTURED, SRC)
