"""rebuild runs end to end on zero rows and on the synthetic fixture, and staging
keeps the latest capture (spec Phase 1, done-when 2 and 3). Offline, temp file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decimal import Decimal  # noqa: E402

import pins  # noqa: E402
import pytest  # noqa: E402

from ingest.parsed import PageShapeError  # noqa: E402
from pipeline.build import (  # noqa: E402
    build_derived,
    content_hash,
    create_raw,
    load_reviews,
    rebuild,
)
from pipeline.warehouse import connect  # noqa: E402

_INSERT_RAW = (
    "insert into raw_reviews (source, external_id, source_url, captured_at, "
    "run_id, review_date, rating, title, body, content_hash) "
    "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def test_zero_row_rebuild(tmp_path):
    """`none`: every table exists and every count is zero — the anchors seed
    every other input, not this one."""
    counts = rebuild("duckdb", "none", database=tmp_path / "none.duckdb")
    assert set(counts) >= {"raw_reviews", "stg_reviews", "raw_platform_snapshots"}
    assert all(n == 0 for n in counts.values()), counts


def test_synthetic_stage_counts_match_pins(tmp_path):
    counts = rebuild(
        "duckdb", "synthetic", database=tmp_path / "syn.duckdb", run_id="test"
    )
    assert counts["raw_reviews"] == pins.RAW_REVIEWS_ROWS
    assert counts["stg_reviews"] == pins.STG_REVIEWS_ROWS


def test_staging_keeps_latest_capture(synthetic_conn):
    source, external_id = pins.EDITED_REVIEW
    rows = synthetic_conn.execute(
        "select captured_at, rating from stg_reviews "
        "where source = ? and external_id = ?",
        [source, external_id],
    ).fetchall()
    assert len(rows) == 1
    captured_at, rating = rows[0]
    assert captured_at == pins.EDITED_REVIEW_LATEST_CAPTURED_AT
    assert rating == pins.EDITED_REVIEW_LATEST_RATING


def test_fixture_spans_the_rating_range(synthetic_conn):
    """The synthetic bodies cover every outcome from one-star to five-star; the
    ratings span the whole pinned scale (uses tests/pins.py::RATING_RANGE)."""
    lo, hi = synthetic_conn.execute(
        "select min(rating), max(rating) from raw_reviews"
    ).fetchone()
    assert (lo, hi) == pins.RATING_RANGE


def test_staging_tiebreak_is_deterministic_on_equal_captured_at():
    """Invariant 3's tiebreak: two captures of one key sharing a captured_at
    deduplicate to the higher content_hash, whatever the insertion order — so
    the survivor is a function of the data, not of the physical row order. Drop
    `content_hash desc` from the dedup and one insertion order changes."""
    lo = ("00aa", 3, "lower-hash")
    hi = ("ff99", 4, "higher-hash")
    for order in ([lo, hi], [hi, lo]):
        conn = connect("duckdb", database=":memory:")
        try:
            create_raw(conn)
            for content_hash, rating, body in order:
                conn.execute(
                    _INSERT_RAW,
                    [
                        "oa",
                        "DUP",
                        "https://x/",
                        "2026-05-01T00:00:00",
                        "t",
                        "2026-05-01",
                        rating,
                        "t",
                        body,
                        content_hash,
                    ],
                )
            build_derived(conn)
            row = conn.execute(
                "select content_hash, body from stg_reviews "
                "where source = 'oa' and external_id = 'DUP'"
            ).fetchone()
            assert row == ("ff99", "higher-hash"), order
        finally:
            conn.close()


def _review(rating) -> dict:
    return {
        "source": "oa",
        "external_id": "R1",
        "source_url": "https://x/",
        "captured_at": "2026-05-01T00:00:00",
        "review_date": "2026-05-01",
        "rating": rating,
        "title": "t",
        "body": "b",
    }


@pytest.mark.parametrize("rating", ["4.25", "4.0", "0.5", "6", "", "x", True, None])
def test_loader_refuses_a_rating_outside_the_half_steps(rating):
    """A6: the loader checks the closed set (`parsed.REVIEW_RATINGS`) on every
    row it is handed, whatever handed it; a refusal names the field and the
    value and nothing is inserted."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        with pytest.raises(PageShapeError, match="field 'rating' is not a half-step"):
            load_reviews(conn, [_review(rating)], run_id="t")
        assert conn.execute("select count(*) from raw_reviews").fetchone() == (0,)
    finally:
        conn.close()


@pytest.mark.parametrize("rating", ["4.5", Decimal("4.5"), 4, "4", Decimal("4.0")])
def test_loader_stores_a_half_step_as_the_column_spells_it(rating):
    """A6: a member of the set, however spelled by its source, lands as one
    decimal(2, 1) value."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        load_reviews(conn, [_review(rating)], run_id="t")
        (stored,) = conn.execute("select rating from raw_reviews").fetchone()
        assert stored == Decimal(str(rating))
    finally:
        conn.close()


def test_content_hash_spells_a_rating_one_way():
    """A6: `1`, `"1"` and `Decimal("1.0")` are one figure and one fingerprint,
    so the synthetic corpus's hashes (strings) and a parser's Decimals agree
    and a re-run inserts nothing."""
    hashes = {content_hash(_review(r)) for r in (1, "1", Decimal("1"), Decimal("1.0"))}
    assert len(hashes) == 1
    assert content_hash(_review("1.5")) == content_hash(_review(Decimal("1.5")))
    assert content_hash(_review("1.5")) != content_hash(_review("1"))
