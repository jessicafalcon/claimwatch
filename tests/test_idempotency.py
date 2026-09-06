"""Run twice, row counts unchanged; an edited review appends a new raw row (spec
Phase 1, done-when 2 and 3). Offline, temp file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pins

from pipeline.build import rebuild


def test_second_rebuild_adds_no_rows(tmp_path):
    first = rebuild("duckdb", "synthetic", root=tmp_path, run_id="run-1")
    second = rebuild("duckdb", "synthetic", root=tmp_path, run_id="run-2")
    assert first == second  # a different run_id inserts nothing


def test_edited_review_appends_new_row(synthetic_conn):
    source, external_id = pins.EDITED_REVIEW
    raw = synthetic_conn.execute(
        "select count(*) from raw_reviews where source = ? and external_id = ?",
        [source, external_id],
    ).fetchone()[0]
    stg = synthetic_conn.execute(
        "select count(*) from stg_reviews where source = ? and external_id = ?",
        [source, external_id],
    ).fetchone()[0]
    assert raw == pins.EDITED_REVIEW_RAW_ROWS  # both captures kept in raw
    assert stg == 1  # staging keeps one
