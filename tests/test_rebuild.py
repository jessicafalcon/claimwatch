"""rebuild runs end to end on zero rows and on the synthetic fixture, and staging
keeps the latest capture (spec Phase 1, done-when 2 and 3). Offline, temp file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pins  # noqa: E402

from pipeline.build import build_derived, create_raw, rebuild  # noqa: E402
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
