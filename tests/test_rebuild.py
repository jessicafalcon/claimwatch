"""rebuild runs end to end on zero rows and on the synthetic fixture, and staging
keeps the latest capture (spec Phase 1, done-when 2 and 3). Offline, temp file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pins  # noqa: E402

from pipeline.build import rebuild  # noqa: E402


def test_zero_row_rebuild(tmp_path):
    counts = rebuild("duckdb", "empty", database=tmp_path / "empty.duckdb")
    assert counts == {"raw_reviews": 0, "stg_reviews": 0}


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
