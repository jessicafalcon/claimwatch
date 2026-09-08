"""Session-wide guards: the make user-variables (SPEC, BASE, TARGET, ROWS,
SOURCE, and CONFIRM, a name the Makefile no longer reads) and MAKEFLAGS are
scrubbed so the Makefile-invoking tests
(tests/test_makefile.py) see a clean environment; UV_OFFLINE=1 is set so a test
that spawns `uv run` (the gate, `make test`) can never resolve or download; and
every socket connection in the process raises (Phase 2, invariant 6), so a test
that reaches for the network fails instead of quietly passing on a good day —
"offline" is enforced, not hoped. Every test here needs no service, no network
and no API key; the warehouse tests run DuckDB against a temp file only and the
fetcher tests use `httpx.MockTransport`, which opens no socket."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from pipeline.warehouse import database_for


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


@pytest.fixture(autouse=True)
def _isolate_fetched_snapshots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """The weekly cron appends real rows to the tracked
    `data/snapshots/fetched_snapshots.csv`, so a unit test that rebuilds
    `ROWS=captured` without naming its own fetched file must not couple to that
    growing file (Phase 4). Point the default at a per-test path with no file,
    so the default is zero rows; a test that exercises the fetched path passes
    `fetched_file=` explicitly, and the guard on the committed file reads its
    real path directly."""
    monkeypatch.setattr(
        "pipeline.build.FETCHED_SNAPSHOTS", tmp_path / "no-fetched-snapshots.csv"
    )
    yield


def build_study_db(root: Path, rows: str = "synthetic") -> Path:
    """A fully built study warehouse in `root`, returned as its db path: `rebuild`
    plus the CLI's classify step, which fills the theme-share marts (B2.2, B2.5)
    and classifier_quality (B2.4) that `rebuild` alone does not build. The model
    decider and the decision cache are neutralised, so the classification is
    rules-only, deterministic, and writes nothing under data/ — the same result
    `make rebuild` produces with no key (source: pipeline/cli.py::_do_rebuild)."""
    from pipeline import cli
    from pipeline.build import rebuild

    rebuild("duckdb", rows, root=root)
    db = database_for(rows, root)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cli, "make_model_decider", lambda: None)  # never call the model
        mp.setattr(cli, "read_decisions", lambda *a, **k: {})  # ignore any dev cache
        mp.setattr(cli, "write_decisions", lambda *a, **k: None)  # no data/ write
        cli._classify_and_print(db, rows)
    return db


@pytest.fixture
def synthetic_conn(tmp_path):
    """A DuckDB connection to a freshly built synthetic warehouse in a temp file.
    Rebuild closes its own connection, so this reopens the file for querying."""
    from pipeline.build import rebuild
    from pipeline.warehouse import connect

    db = database_for("synthetic", tmp_path)
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="test")
    conn = connect("duckdb", database=db)
    try:
        yield conn
    finally:
        conn.close()
