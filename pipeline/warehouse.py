"""The one seam that knows DuckDB from Snowflake (PROJECT_BRIEF.md §4.4,
docs/PLAN.md §4.1). Every other module runs the SAME SQL through `connect()` and
`run_sql_file()`; nothing else imports a database driver, which is what keeps the
SQL portable.

DuckDB — a database that lives in a single file on a laptop — is the permanent
path (`make rebuild` needs no accounts). Snowflake is the cloud engine used once
as a demonstration in Phase 10; its connector is not a Phase 1 dependency, so the
Snowflake branch here raises a clear Phase-10 error and imports nothing. There is
no `snowflake` import anywhere in this file — the invariant a test pins."""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("duckdb", "snowflake")
# The working warehouse lives under data/ (gitignored; `.gitignore` covers
# `*.duckdb`). Callers pass `database=":memory:"` or a temp path in tests.
DEFAULT_DB = ROOT / "data" / "friction_ledger.duckdb"


def database_for(fixture: str) -> Path:
    """One file per rebuild input (spec Phase 2, fix amendment A2): the real
    corpus (`cache`) is `friction_ledger.duckdb`; every other input builds
    `friction_ledger.<input>.duckdb` beside it, so a fixture's rows can never
    land in the real database and the counts a rebuild prints are its own."""
    if fixture == "cache":
        return DEFAULT_DB
    return DEFAULT_DB.with_name(f"{DEFAULT_DB.stem}.{fixture}{DEFAULT_DB.suffix}")


def connect(target: str = "duckdb", *, database: str | Path | None = None):
    """Open a connection for `target`. DuckDB now; Snowflake defers to Phase 10.

    `database` defaults to the working file under data/; `":memory:"` is an
    ephemeral database (tests). The parent directory of a file database is
    created if missing."""
    if target == "duckdb":
        db = DEFAULT_DB if database is None else database
        if isinstance(db, Path) or (isinstance(db, str) and db != ":memory:"):
            Path(db).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(db))
    if target == "snowflake":
        raise NotImplementedError(
            "TARGET=snowflake is the Phase 10 demonstration; it is not wired in "
            "Phase 1 (the DuckDB path is the permanent one)."
        )
    raise ValueError(f"unknown TARGET {target!r}; expected one of {TARGETS}")


def run_sql_file(conn, path: str | Path) -> None:
    """Execute one .sql file on `conn`. The file is the unit of work; its header
    comment names the grain, the provenance columns and the BACKING rows it
    feeds (CLAUDE.md -> Conventions)."""
    conn.execute(Path(path).read_text(encoding="utf-8"))
