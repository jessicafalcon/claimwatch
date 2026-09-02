"""The warehouse seam (spec Phase 1, done-when 1). DuckDB now; Snowflake defers
to Phase 10 and imports nothing. Offline, in-memory."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pipeline.warehouse import connect

WAREHOUSE = Path(__file__).resolve().parent.parent / "pipeline" / "warehouse.py"


def test_connect_selects_duckdb():
    conn = connect("duckdb", database=":memory:")
    try:
        assert conn.execute("select 1").fetchone()[0] == 1
    finally:
        conn.close()


def test_snowflake_target_defers_to_phase_10():
    with pytest.raises(NotImplementedError, match="Phase 10"):
        connect("snowflake")
    # The invariant: the seam imports no snowflake driver in Phase 1.
    src = WAREHOUSE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+snowflake\b", src, re.M)


def test_unknown_target_is_a_value_error():
    with pytest.raises(ValueError):
        connect("postgres")
