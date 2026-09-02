"""Session-wide guard: the make user-variables (SPEC, BASE, TARGET, FIXTURE,
CONFIRM) and MAKEFLAGS are scrubbed so the Makefile-invoking tests
(tests/test_makefile.py) see a clean environment, and UV_OFFLINE=1 is set so a
test that spawns `uv run` (the gate, `make test`) can never resolve or download —
"offline" is enforced, not hoped. Every test here needs no service, no network
and no API key; the warehouse tests run DuckDB against a temp file only."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in ("SPEC", "BASE", "TARGET", "FIXTURE", "CONFIRM", "MAKEFLAGS", "MFLAGS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("UV_OFFLINE", "1")
    yield


@pytest.fixture
def synthetic_conn(tmp_path):
    """A DuckDB connection to a freshly built synthetic warehouse in a temp file.
    Rebuild closes its own connection, so this reopens the file for querying."""
    from pipeline.build import rebuild
    from pipeline.warehouse import connect

    db = tmp_path / "warehouse.duckdb"
    rebuild("duckdb", "synthetic", database=db, run_id="test")
    conn = connect("duckdb", database=db)
    try:
        yield conn
    finally:
        conn.close()
