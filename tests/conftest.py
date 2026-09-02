"""Session-wide guards: the make user-variables (SPEC, BASE, TARGET, ROWS,
CONFIRM, SOURCE) and MAKEFLAGS are scrubbed so the Makefile-invoking tests
(tests/test_makefile.py) see a clean environment; UV_OFFLINE=1 is set so a test
that spawns `uv run` (the gate, `make test`) can never resolve or download; and
every socket connection in the process raises (Phase 2, invariant 6), so a test
that reaches for the network fails instead of quietly passing on a good day —
"offline" is enforced, not hoped. Every test here needs no service, no network
and no API key; the warehouse tests run DuckDB against a temp file only and the
fetcher tests use `httpx.MockTransport`, which opens no socket."""

import socket
from collections.abc import Iterator

import pytest


def _blocked(*_args, **_kwargs):
    raise RuntimeError("network blocked: the test suite opens no socket")


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in (
        "SPEC",
        "BASE",
        "TARGET",
        "ROWS",
        "CONFIRM",
        "SOURCE",
        "MAKEFLAGS",
        "MFLAGS",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("UV_OFFLINE", "1")
    yield


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
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
