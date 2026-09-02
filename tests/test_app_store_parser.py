"""The strict parser (spec Phase 2, invariants 1, 2 and 7; done-when 2 and 6).
Every negative case is built in memory by mutating the frozen sample — no
malformed page is committed. A refusal is a `FeedShapeError` that names the
page, the item and the field; nothing is guessed or defaulted."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ingest.app_store import SOURCE, FeedShapeError, parse_page
from tests import pins

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
PAGE_URL = pins.APP_STORE_SAMPLE_FIRST_ROW["source_url"]
CAPTURED = pins.APP_STORE_SAMPLE_CAPTURED_AT
RAW_COLUMNS = (
    "source",
    "external_id",
    "source_url",
    "captured_at",
    "review_date",
    "rating",
    "title",
    "body",
)
REQUIRED = ("id", "title", "content", "im:rating", "updated")


def _page(n: int = 1) -> dict:
    return json.loads((SAMPLE / f"page-{n}.json").read_text(encoding="utf-8"))


def _parse(doc: dict) -> list[dict]:
    return parse_page(json.dumps(doc), PAGE_URL, CAPTURED)


def _mutated(mutate) -> dict:
    doc = copy.deepcopy(_page(1))
    mutate(doc["feed"]["entry"][1])  # the second item: proves the page is the unit
    return doc


def test_well_formed_item_maps_to_the_eight_raw_columns():
    rows = _parse(_page(1))
    assert len(rows) == pins.APP_STORE_SAMPLE_ITEMS_ON_PAGES[0]
    for row in rows:
        assert tuple(row) == RAW_COLUMNS
        assert row["source"] == SOURCE == "app-store"
        assert isinstance(row["rating"], int) and 1 <= row["rating"] <= 5
        assert len(row["review_date"]) == 10
    first = {k: rows[0][k] for k in pins.APP_STORE_SAMPLE_FIRST_ROW}
    assert first == pins.APP_STORE_SAMPLE_FIRST_ROW


def test_absent_entry_is_the_end_of_the_feed():
    assert "entry" not in _page(3)["feed"]
    assert _parse(_page(3)) == []


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_required_field_refuses_the_page(field):
    def drop(item):
        del item[field]

    with pytest.raises(FeedShapeError, match=f"'{field}' is missing"):
        _parse(_mutated(drop))

    def drop_label(item):
        del item[field]["label"]

    with pytest.raises(FeedShapeError, match=f"'{field}' has no 'label'"):
        _parse(_mutated(drop_label))


@pytest.mark.parametrize(
    "field, bad",
    [
        ("im:rating", 4),  # an integer where the feed's digit string is declared
        ("title", ["x"]),
        ("content", None),
        ("id", 900000002),
        ("updated", 20260118),
    ],
)
def test_mistyped_field_refuses_the_page(field, bad):
    def retype(item):
        item[field]["label"] = bad

    with pytest.raises(FeedShapeError, match=f"'{field}' is .*not a string"):
        _parse(_mutated(retype))


@pytest.mark.parametrize("label", ["0", "6", "4.5", "", "-1", "five", " 4"])
def test_rating_outside_1_to_5_is_refused(label):
    def set_rating(item):
        item["im:rating"]["label"] = label

    with pytest.raises(FeedShapeError, match="'im:rating'"):
        _parse(_mutated(set_rating))


@pytest.mark.parametrize(
    "label",
    [
        "2025-13-40T00:00:00Z",
        "yesterday",
        "",
        "2026-01-18",  # a date alone: the declared shape is a timestamp with offset
        "2026-01-18T09:15:00",  # no offset
        "18/01/2026 09:15",
    ],
)
def test_malformed_timestamp_is_refused(label):
    def set_updated(item):
        item["updated"]["label"] = label

    with pytest.raises(FeedShapeError, match="'updated'"):
        _parse(_mutated(set_updated))


def test_review_date_is_the_items_own_date_without_timezone_arithmetic():
    """A timestamp late in the day at -07:00 stays on the date the feed printed
    (no conversion to UTC, which would move it to the next day)."""

    def late(item):
        item["updated"]["label"] = "2026-02-28T23:30:00-07:00"

    rows = _parse(_mutated(late))
    assert rows[1]["review_date"] == "2026-02-28"


def test_refusal_names_page_item_and_field():
    def drop(item):
        del item["im:rating"]

    with pytest.raises(FeedShapeError) as exc:
        _parse(_mutated(drop))
    message = str(exc.value)
    assert PAGE_URL in message
    assert "item '900000002'" in message
    assert "'im:rating'" in message


def test_non_json_and_missing_feed_are_refused():
    with pytest.raises(FeedShapeError, match="is not JSON"):
        parse_page(b"<html>blocked</html>", PAGE_URL, CAPTURED)
    with pytest.raises(FeedShapeError, match="'feed' is missing"):
        parse_page(json.dumps({"rss": {}}), PAGE_URL, CAPTURED)
    with pytest.raises(FeedShapeError, match="'entry' is dict, not a list"):
        doc = _page(1)
        doc["feed"]["entry"] = doc["feed"]["entry"][0]
        _parse(doc)


def test_author_fields_are_never_read():
    """Removing every author block changes nothing; no output column carries a
    name. The raw shape has no column for one (CLAUDE.md -> Neutrality)."""
    with_authors = _parse(_page(1))
    doc = copy.deepcopy(_page(1))
    for item in doc["feed"]["entry"]:
        del item["author"]
        del item["im:version"]
        del item["im:voteSum"]
        del item["link"]
    assert _parse(doc) == with_authors
    for row in with_authors:
        assert "author" not in row and "name" not in row


def test_sample_is_obviously_fake_and_nameless():
    """The frozen sample is hand-written: placeholder author labels, bodies
    marked as fictional, a rights line saying so, an app id of 0."""
    for n in (1, 2):
        doc = _page(n)
        assert "hand-written fixture" in doc["feed"]["rights"]["label"]
        for item in doc["feed"]["entry"]:
            assert item["author"]["name"]["label"] == "reviewer-placeholder"
            assert item["content"]["label"].startswith("EXEMPLE FICTIF.")
    assert "id=0/" in PAGE_URL
    ids = [row["external_id"] for row in _parse(_page(2))]
    assert pins.APP_STORE_SAMPLE_DUPLICATE_ID in ids
