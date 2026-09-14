"""The one seam that knows DuckDB from Snowflake (PROJECT_BRIEF.md §4.4,
docs/PLAN.md §4.1). Every other module runs the SAME SQL through `connect()` and
`run_sql_file()`, reads the catalog through `tables()`/`columns()`/
`table_exists()`, and catches one error name (`DriverError`); nothing else
imports a database driver, spells an engine name, queries `information_schema`
or reads a `SNOWFLAKE_*` credential — which is what keeps the SQL portable and
the engine's differences in one file.

DuckDB — a database that lives in a single file on a laptop — is the permanent
path (`make rebuild` needs no accounts, no network, no extra installed).
Snowflake is the cloud engine used once as a demonstration (Phase 10b, brief
§9): its connector is an optional extra (`uv sync --extra snowflake`), imported
lazily inside the Snowflake branch alone, so the DuckDB path never loads it and
a missing extra is one refusal line. Both branches return the SAME connection
shape (`execute`/`executemany`/`executescript`/`close`), so `pipeline/build.py`,
`study/` and the CLI are engine-blind."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("duckdb", "snowflake")
# The laptop engine, by name, for every caller outside this file: a module
# that opens a connection imports LOCAL and never spells the engine (Phase
# 10a; pinned by tests/test_ingest_layout.py), so threading a target
# through a caller is a parameter change with no literal left to miss.
LOCAL = TARGETS[0]
# The cloud engine, by name (the demonstration target, Phase 10b): the CLI
# names it to refuse a corpus input on it, never spelling the literal.
CLOUD = TARGETS[1]
# The targets `connect` can open: the CLI resolves a `TARGET` it will hand to
# the seam against this set, so a target the seam does not open is one refusal
# line naming the set, never a traceback. Both are wired since Phase 10b.
WIRED = TARGETS
# The working DuckDB warehouse lives under data/ (gitignored; `.gitignore`
# covers `*.duckdb`). Callers pass `database=":memory:"` or a temp path in tests.
DEFAULT_DB = ROOT / "data" / "friction_ledger.duckdb"
# The corpus inputs — the real scraped reviews and the frozen samples, real
# people's words (brief §2.5) — that a trial account (a third party's disk)
# may never hold: `location_for` refuses them on the cloud target by name, so
# the trial cannot hold a real review by construction (Phase 10b, invariant 2).
CLOUD_FORBIDDEN_INPUTS = ("captured", "samples")
# The six Snowflake credentials, read from the environment inside the Snowflake
# branch only (the closed set a layout test keeps here; `.env.example` carries
# placeholders). SNOWFLAKE_PASSWORD holds a password or a programmatic access
# token — a string either way, so no credential is ever a path the code opens
# (secure-by-construction; Phase 10b pinned decision 5). SNOWFLAKE_ROLE is
# optional; the rest are required when the Snowflake branch runs.
SNOWFLAKE_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_ROLE",
)
_SNOWFLAKE_REQUIRED = SNOWFLAKE_ENV[:-1]  # every name but the optional role
# The shape a schema name interpolated as a SQL identifier must match: only the
# characters `location_for`/`scratch` build from the closed INPUTS set and a
# pid. A value off this shape refuses at the seam rather than being quoted into
# DDL (round 1 security #4 / code-reviewer #10, defense-in-depth: the identifier
# cannot be parameterised, so its shape is enforced where it is spelled).
_SCHEMA_NAME = re.compile(r"\A[a-z0-9_]+\Z")


class DriverError(Exception):
    """The one error type both engine branches fold their driver's failure into,
    so every caller catches one name whatever the engine (round 5,
    security-reviewer #4; Phase 10b done-when 1). Its message is what the seam
    chooses at the raise: a SQL error carries the engine's own words (safe — no
    credential); a connect or credential refusal names the class and the
    variables involved, never a value and never the driver's message verbatim
    (which can carry the account or host)."""


@contextmanager
def _no_pandas_probe() -> Iterator[None]:
    """Suppress DuckDB's per-value `import pandas` probe for the duration of a bulk
    insert. Binding a Python value, DuckDB checks whether it is a pandas type by
    importing pandas; pandas is not installed here (a hard project rule — no pandas
    on a pipeline path) and Python does not cache a failed import, so the check
    re-scans `sys.path` on every value — ~4,000 rows × 10 columns per rebuild turns
    a sub-second write into ~5 s, and every rebuild (and every test that rebuilds)
    pays it. A sentinel `None` in `sys.modules` makes `import pandas` fail
    immediately with no path scan; it is set only around the insert and restored
    after, and the repo never uses DuckDB's dataframe API, so nothing else is
    affected. This is DuckDB's own quirk, so its home is the DuckDB branch of the
    seam (Phase 10b; it lived in `pipeline/build.py` through Phase 8b).
    DECISIONS → Phase 8b Gotchas."""
    sentinel = object()
    previous = sys.modules.get("pandas", sentinel)
    sys.modules["pandas"] = None  # type: ignore[assignment]
    try:
        yield
    finally:
        if previous is sentinel:
            del sys.modules["pandas"]
        else:
            sys.modules["pandas"] = previous  # type: ignore[assignment]


class _DuckConnection:
    """The DuckDB branch's wrapper: DuckDB's own connection already carries the
    seam's read shape (`execute` returns the connection, which has
    `fetchone`/`fetchall`/`description`), so this is a thin adapter that folds
    `duckdb.Error` into `DriverError`, guards the bulk insert with the
    no-pandas probe, and runs a multi-statement file in one `execute`."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: list | None = None):
        try:
            return (
                self._conn.execute(sql)
                if params is None
                else self._conn.execute(sql, params)
            )
        except duckdb.Error as exc:
            raise DriverError(str(exc)) from exc

    def executemany(self, sql: str, rows: list[list]) -> None:
        with _no_pandas_probe():
            try:
                self._conn.executemany(sql, rows)
            except duckdb.Error as exc:
                raise DriverError(str(exc)) from exc

    def executescript(self, text: str) -> None:
        try:
            self._conn.execute(text)  # DuckDB runs every ;-separated statement
        except duckdb.Error as exc:
            raise DriverError(str(exc)) from exc

    def close(self) -> None:
        self._conn.close()


class _SnowflakeConnection:
    """The Snowflake branch's wrapper: one `qmark` cursor of the connector, so
    the placeholders in `pipeline/build.py` are `?` on both engines and the SQL
    is not rewritten per engine. `executescript` runs a multi-statement file
    through `execute_string` (the connector's multi-statement entry — every
    `sql/` file holds two to eight statements). Every driver failure is folded
    into `DriverError` carrying the engine's SQL words (safe), never a value."""

    def __init__(self, conn, cursor) -> None:
        self._conn = conn
        self._cursor = cursor

    def execute(self, sql: str, params: list | None = None):
        try:
            if params is not None:
                self._cursor.execute(sql, params)
            else:
                self._cursor.execute(sql)
        except _connector_error() as exc:
            raise DriverError(str(exc)) from exc
        return self._cursor

    def executemany(self, sql: str, rows: list[list]) -> None:
        try:
            self._cursor.executemany(sql, rows)
        except _connector_error() as exc:
            raise DriverError(str(exc)) from exc

    def executescript(self, text: str) -> None:
        try:
            self._conn.execute_string(text)
        except _connector_error() as exc:
            raise DriverError(str(exc)) from exc

    def close(self) -> None:
        self._cursor.close()
        self._conn.close()


def _connector():
    """The Snowflake connector module, imported lazily so the DuckDB path never
    loads it. A missing extra is one refusal line naming the sync command, never
    an ImportError traceback (Phase 10b done-when 1)."""
    try:
        import snowflake.connector as connector
    except ImportError as exc:
        raise DriverError(
            "TARGET=snowflake needs the connector, which is an optional extra: "
            "install it with `uv sync --extra snowflake` (the DuckDB path needs "
            "no extra)"
        ) from exc
    return connector


def _connector_error() -> type[BaseException]:
    """The connector's own error class, for folding into `DriverError`. Read
    through the lazy import, so it is reached only on the Snowflake branch."""
    return _connector().Error


def _snowflake_credentials() -> dict[str, str]:
    """The six connector parameters, read from the environment by name inside
    this branch only. A missing required one is one refusal line naming the
    missing names (never a value); `SNOWFLAKE_ROLE` is optional."""
    values = {name: os.environ.get(name, "") for name in SNOWFLAKE_ENV}
    missing = [name for name in _SNOWFLAKE_REQUIRED if not values[name]]
    if missing:
        raise DriverError(
            "TARGET=snowflake: missing required credential(s) "
            f"{', '.join(missing)} — export them (or `.env`) before the cloud run; "
            "no value is read from a file"
        )
    return values


def _safe_schema(name: str) -> str:
    """A schema name about to be interpolated as a SQL identifier, checked
    against its shape first: it comes from the closed INPUTS set or a pid, so a
    value off `_SCHEMA_NAME` is a bug (or a future caller passing an unvalidated
    string), refused here rather than quoted into DDL."""
    if not _SCHEMA_NAME.fullmatch(name):
        raise DriverError(f"refusing a schema name that is not [a-z0-9_]+: {name!r}")
    return name


def _connect_snowflake(schema: str | None):
    """Open a `qmark` cursor of the connector against `SNOWFLAKE_DATABASE`, on
    the given schema (created if missing). `schema=None` connects to the
    database default (for `scratch` to drop a schema it can no longer connect
    into). Credentials are validated (and refused by name) BEFORE the connector's
    module-level `paramstyle` is touched, so a credential refusal leaves no side
    effect. `autocommit=False` makes the explicit `begin`/`commit`/`rollback`
    that `pipeline/build.py` issues the transaction unit (stack risk 2), not the
    connector's default. A connect failure names the class and the variables,
    never the driver's message (it can carry the account or host)."""
    connector = _connector()
    creds = _snowflake_credentials()  # validate before the paramstyle side effect
    connector.paramstyle = "qmark"  # the module-level setting the connector documents
    kwargs = {
        "account": creds["SNOWFLAKE_ACCOUNT"],
        "user": creds["SNOWFLAKE_USER"],
        "password": creds["SNOWFLAKE_PASSWORD"],
        "warehouse": creds["SNOWFLAKE_WAREHOUSE"],
        "database": creds["SNOWFLAKE_DATABASE"],
        "autocommit": False,
    }
    if creds["SNOWFLAKE_ROLE"]:
        kwargs["role"] = creds["SNOWFLAKE_ROLE"]
    try:
        conn = connector.connect(**kwargs)
        cursor = conn.cursor()
        if schema is not None:
            safe = _safe_schema(schema)
            cursor.execute(f'create schema if not exists "{safe}"')
            cursor.execute(f'use schema "{safe}"')
    except connector.Error as exc:
        raise DriverError(
            "TARGET=snowflake: the connector refused (snowflake.connector.Error) "
            "with SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, "
            "SNOWFLAKE_WAREHOUSE and SNOWFLAKE_DATABASE set — check the "
            "credentials, the warehouse and the login policy (no value shown)"
        ) from exc
    return _SnowflakeConnection(conn, cursor)


def database_for(rows: str, root: str | Path | None = None) -> Path:
    """One DuckDB file per rebuild input (spec Phase 2, fix amendment A2; named
    by `ROWS` since Phase 3a): the real corpus (`captured`) is
    `friction_ledger.duckdb`; every other input builds
    `friction_ledger.<input>.duckdb` beside it, so a sample's rows can never
    land in the real database and the counts a rebuild prints are its own.
    `root` is the directory the files live in (data/ by default; a temp dir in
    tests). The laptop callers that never take a target — `study/export.py`,
    `pipeline/label_sample.py`, `classify-eval`, the tests — keep calling this;
    `location_for` generalises it across engines for the target-taking paths."""
    base = DEFAULT_DB if root is None else Path(root) / DEFAULT_DB.name
    if rows == "captured":
        return base
    return base.with_name(f"{base.stem}.{rows}{base.suffix}")


def location_for(target: str, rows: str, root: str | Path | None = None) -> str | Path:
    """The location one (input, target) pair builds into: the DuckDB file per
    input on the laptop (`database_for`, unchanged), or the Snowflake schema
    `friction_ledger_<input>` per input in `SNOWFLAKE_DATABASE`. A corpus input
    (`captured`, `samples`) on the cloud target raises naming both, so the
    trial cannot hold a real review by construction (invariant 2). `rows` is a
    member of the CLI's closed `INPUTS` set before it arrives here, so it is a
    validated name, never raw user input, when it becomes a schema name."""
    if target == LOCAL:
        return database_for(rows, root)
    if target == CLOUD:
        if rows in CLOUD_FORBIDDEN_INPUTS:
            raise ValueError(
                f"refusing ROWS={rows} on TARGET={CLOUD}: the corpus inputs "
                f"{CLOUD_FORBIDDEN_INPUTS} are real people's words and never leave "
                "the laptop (brief §2.5); the cloud demonstration takes fixture "
                "inputs (synthetic, none) only"
            )
        return f"friction_ledger_{rows}"
    raise ValueError(f"unknown TARGET {target!r}; expected one of {TARGETS}")


def connect(target: str = LOCAL, *, database: str | Path | None = None):
    """Open a connection for `target`, returning the seam's one shape
    (`execute`/`executemany`/`executescript`/`close`). DuckDB: `database`
    defaults to the working file under data/; `":memory:"` is ephemeral (tests);
    the parent directory of a file database is created if missing. Snowflake:
    `database` is the schema to use (created if missing), or None for the
    database default; the connector is imported lazily and its error folded into
    `DriverError`."""
    if target == LOCAL:
        db = DEFAULT_DB if database is None else database
        if isinstance(db, Path) or (isinstance(db, str) and db != ":memory:"):
            Path(db).parent.mkdir(parents=True, exist_ok=True)
        return _DuckConnection(duckdb.connect(str(db)))
    if target == CLOUD:
        schema = None if database is None else str(database)
        return _connect_snowflake(schema)
    raise ValueError(f"unknown TARGET {target!r}; expected one of {TARGETS}")


@contextmanager
def scratch(target: str, rows: str) -> Iterator[str | Path]:
    """A throwaway location that exists for the block and not after, whatever
    happens inside it, and is never an input's own location (Phase 10b
    invariant 7). DuckDB: a temp directory removed on exit, so the location is a
    file under it. Snowflake: a uniquely named schema (`scratch_<input>_<pid>`,
    never `friction_ledger_<input>`), created on first connect and dropped on
    exit even after a failure — the drop connects to the database default,
    since a connection into the schema would recreate it. A corpus input on the
    cloud target is refused here too, so the trial cannot hold a real review
    through the scratch path either, not only through `location_for` (invariant
    2 by construction — round 1 code-reviewer #1 / security #1; the corpus-guard
    class, applied at every location source)."""
    if target == CLOUD and rows in CLOUD_FORBIDDEN_INPUTS:
        raise ValueError(
            f"refusing a scratch for ROWS={rows} on TARGET={CLOUD}: the corpus "
            f"inputs {CLOUD_FORBIDDEN_INPUTS} never reach the cloud (brief §2.5)"
        )
    if target == LOCAL:
        with tempfile.TemporaryDirectory() as tmp:
            yield database_for(rows, tmp)
        return
    if target == CLOUD:
        name = f"scratch_{rows}_{os.getpid()}"
        try:
            yield name
        finally:
            # best-effort drop; a cleanup DriverError never masks an in-block
            # error (round 1 code-reviewer #4). A schema left by a failed drop
            # is the developer's console cleanup (Out of scope).
            with suppress(DriverError):
                admin = connect(CLOUD, database=None)
                try:
                    admin.execute(f'drop schema if exists "{_safe_schema(name)}"')
                finally:
                    admin.close()
        return
    raise ValueError(f"unknown TARGET {target!r}; expected one of {TARGETS}")


def run_sql_file(conn, path: str | Path) -> None:
    """Execute one .sql file's statements on `conn`, whichever engine it wraps.
    The file is the unit of work; its header comment names the grain, the
    provenance columns and the BACKING rows it feeds (CLAUDE.md → Conventions)."""
    conn.executescript(Path(path).read_text(encoding="utf-8"))


def _default_schema(conn) -> str:
    """The schema an unqualified table name resolves to on `conn`, read from the
    engine itself (`main` on DuckDB, the session schema on Snowflake) in the
    engine's own spelling — so the catalog reads below filter on the engine's
    own answer and a same-named table in another schema never matches. Internal
    since Phase 10b: callers read the catalog through `tables`/`columns`/
    `table_exists`, which fold the answers, not this raw schema name."""
    return conn.execute("select current_schema()").fetchone()[0]


def tables(conn) -> list[str]:
    """Every table name in the engine's default schema, lower-cased and sorted —
    so `STG_REVIEWS` from Snowflake and `stg_reviews` from DuckDB are one name
    and an equality holds the same way on both (invariant 3). The one catalog
    read `table_counts` and `table_exists` share; `information_schema` is spelled
    in this file alone (the class of BACKLOG row 33, fixed as a layout test)."""
    rows = conn.execute(
        "select table_name from information_schema.tables where table_schema = ?",
        [_default_schema(conn)],
    ).fetchall()
    return sorted(str(name).lower() for (name,) in rows)


def table_exists(conn, table: str) -> bool:
    """Whether `table` (compared case-folded) is in the engine's default schema."""
    return table.lower() in set(tables(conn))


def columns(conn, table: str) -> list[tuple[str, str, str]]:
    """(name, type, is_nullable) per column of `table` in position order, from
    the engine's default schema. The column NAME is lower-cased (so a name
    equality holds the same on both engines); the type and nullability are the
    engine's own words, compared only within one engine (`check_raw_declaration`
    builds the scratch table on the same engine as the corpus table). The
    position is the catalog's `ordinal_position`, read and sorted on here, never
    the order the engine happens to return rows in (round 5,
    functionality-tester #1)."""
    want = table.lower()
    rows = [
        (int(pos), str(name).lower(), kind, nullable)
        for pos, tname, name, kind, nullable in conn.execute(
            "select ordinal_position, table_name, column_name, data_type, "
            "is_nullable from information_schema.columns where table_schema = ?",
            [_default_schema(conn)],
        ).fetchall()
        if str(tname).lower() == want
    ]
    return [(name, kind, nullable) for _, name, kind, nullable in sorted(rows)]
