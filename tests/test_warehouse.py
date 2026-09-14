"""The warehouse seam (spec Phase 1, Phase 10b done-when 1). Both engines are
wired since 10b: DuckDB runs for real (in-memory / temp file), Snowflake through
the recording fake (`tests/fake_snowflake.py`) — no socket, no real driver. The
Snowflake branch's detail (the qmark cursor, execute_string, the error fold, the
catalog fold, the credentials, scratch) is pinned in `test_snowflake_seam.py`."""

from __future__ import annotations

import pytest

from pipeline.warehouse import CLOUD, LOCAL, TARGETS, WIRED, connect
from tests import fake_snowflake


def test_connect_selects_duckdb():
    conn = connect("duckdb", database=":memory:")
    try:
        assert conn.execute("select 1").fetchone()[0] == 1
    finally:
        conn.close()


def test_local_is_the_duckdb_target():
    """`LOCAL` is the laptop engine every caller outside the seam names instead
    of spelling it (Phase 10a); it is the first of the two targets and opens."""
    assert LOCAL == TARGETS[0] == "duckdb"
    conn = connect(LOCAL, database=":memory:")
    try:
        assert conn.execute("select 1").fetchone()[0] == 1
    finally:
        conn.close()


def test_wired_is_exactly_the_targets_connect_opens(monkeypatch):
    """`WIRED` is the CLI's TARGET set and, since Phase 10b, exactly `TARGETS`:
    every member opens — DuckDB for real, Snowflake through the fake — so the set
    and the seam cannot disagree (there is no declared-but-unwired target left)."""
    assert WIRED == TARGETS and TARGETS[1] == CLOUD
    connect(LOCAL, database=":memory:").close()
    fake_snowflake.install(monkeypatch)
    connect(CLOUD, database="friction_ledger_synthetic").close()
    # the fake recorded a connect and set qmark before it
    assert ("connect", None, fake_snowflake.CALLS[0][2]) in fake_snowflake.CALLS
    assert fake_snowflake.paramstyle == "qmark"


def test_unknown_target_is_a_value_error():
    with pytest.raises(ValueError):
        connect("postgres")
