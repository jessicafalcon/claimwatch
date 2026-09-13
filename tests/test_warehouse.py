"""The warehouse seam (spec Phase 1, done-when 1). DuckDB now; Snowflake defers
to Phase 10b and imports nothing. Offline, in-memory."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pipeline.build import CLASSIFY_TARGETS
from pipeline.warehouse import LOCAL, TARGETS, WIRED, connect

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


def test_local_is_the_duckdb_target():
    """`LOCAL` is the laptop engine every caller outside the seam names instead
    of spelling it (Phase 10a); it is the first of the two targets and opens."""
    assert LOCAL == TARGETS[0] == "duckdb"
    conn = connect(LOCAL, database=":memory:")
    try:
        assert conn.execute("select 1").fetchone()[0] == 1
    finally:
        conn.close()


def test_wired_is_exactly_the_targets_connect_opens():
    """`WIRED` is the CLI's TARGET set: every member opens, and every declared
    target outside it is the seam's NotImplementedError — so the set and the
    seam cannot disagree (10b appends `snowflake` to both at once)."""
    assert WIRED == (LOCAL,) and set(WIRED) <= set(TARGETS)
    assert set(CLASSIFY_TARGETS) <= set(
        WIRED
    )  # the classify step's set never outruns the seam
    for target in WIRED:
        connect(target, database=":memory:").close()
    for target in set(TARGETS) - set(WIRED):
        with pytest.raises(NotImplementedError):
            connect(target)


def test_unknown_target_is_a_value_error():
    with pytest.raises(ValueError):
        connect("postgres")
