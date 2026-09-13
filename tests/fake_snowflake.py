"""A recording fake of `snowflake.connector` for the offline seam tests
(Phase 10b). It opens no socket, records every statement the seam runs, and
answers the catalog reads with UPPER-cased names so the case-fold is exercised.

The trust boundary this fake stands on (Phase 10b done-when 6, recorded in
DECISIONS → Gotchas): it models the connector at the points the seam relies on —
`paramstyle` set to `qmark` before connect, `execute_string` for a
multi-statement file, upper-cased catalog answers, and an `Error` class both
branches fold. The real driver is never in CI; the five stack-risk unknowns are
verified against the official docs in the first hour, and the run's counts and
schema name are recorded Documented-by-hand. Never imported by the pipeline —
`tests/test_ingest_layout.py::test_no_module_outside_the_seam_imports_a_database_driver`
excludes `tests/`."""

from __future__ import annotations

import re
import sys
import types

# Every statement the seam runs, in order: (op, text, params). Reset by install().
CALLS: list[tuple[str, str | None, object]] = []

# What the fake answers the catalog and read queries with. UPPER-cased on
# purpose (Snowflake folds unquoted identifiers to upper), so the seam's fold is
# exercised. Reset and overridden by install().
_DEFAULTS: dict[str, object] = {
    "schema": "FRICTION_LEDGER_SYNTHETIC",
    "tables": (),  # upper-cased table names in the default schema
    "columns": {},  # {UPPER_TABLE: [(pos, UPPER_COL, TYPE, NULLABLE), ...]}
    "reviews": (),  # rows for the classify step's read of stg_reviews
    "counts": {},  # {table_name_lower: n} for "select count(*) from <table>"
    "mart_columns": {},  # {mart_lower: [col, ...]} for the export's column read
    "mart_rows": {},  # {mart_lower: [row, ...]} for the export's data read
    "connect_error": None,  # a message to raise from connect(), or None
    "execute_error": None,  # a message every execute / execute_string raises, or None
}
_STATE: dict[str, object] = dict(_DEFAULTS)

# Tables the run has created, tracked from the DDL text so a full rebuild can
# run through the fake: `create table` makes one exist (so `_require_raw_tables`
# and `table_counts` see it), `drop schema` clears them (the scratch drop). This
# is the only state the fake keeps beyond its recording; columns stay empty, so
# `check_raw_declaration` compares two empty lists and passes (its real
# column-drift check is a DuckDB test).
_CREATED: set[str] = set()

# The connector's own module-level knobs the seam touches.
paramstyle = "pyformat"


class Error(Exception):
    """Stands in for `snowflake.connector.Error` — the class both branches fold
    into `warehouse.DriverError`."""


def _norm(sql: str) -> str:
    return " ".join(sql.lower().split())


_CREATE = re.compile(
    r"create (?:or replace |temporary )*table (?:if not exists )?\"?([a-z_][a-z0-9_]*)"
)
_DROP = re.compile(r"drop table (?:if exists )?\"?([a-z_][a-z0-9_]*)")


def _track(sql: str) -> None:
    """Update `_CREATED` from a statement's DDL, so the fake reports a table as
    existing once its create has run and gone after a drop."""
    q = _norm(sql)
    for name in _CREATE.findall(q):
        _CREATED.add(name.upper())
    for name in _DROP.findall(q):
        _CREATED.discard(name.upper())
    if "drop schema" in q:
        _CREATED.clear()


def _answer(sql: str) -> tuple[list[tuple], list[tuple] | None]:
    """Canned (rows, description) for the queries the seam and the classify step
    run; every other statement records and returns nothing."""
    q = _norm(sql)
    if q == "select current_schema()":
        return [(_STATE["schema"],)], [("current_schema()",)]
    if "information_schema.tables" in q:
        names = set(_STATE["tables"]) | _CREATED
        return [(t,) for t in sorted(names)], [("table_name",)]
    if "information_schema.columns" in q:
        rows = [
            (pos, table, name, kind, nullable)
            for table, cols in _STATE["columns"].items()
            for pos, name, kind, nullable in cols
        ]
        desc = [
            ("ordinal_position",),
            ("table_name",),
            ("column_name",),
            ("data_type",),
            ("is_nullable",),
        ]
        return rows, desc
    if "from stg_reviews" in q and "count(" not in q:
        return list(_STATE["reviews"]), [
            ("source",),
            ("external_id",),
            ("title",),
            ("body",),
        ]
    if q.startswith("select count(*) from "):
        table = q[len("select count(*) from ") :].strip().strip('"')
        return [(_STATE["counts"].get(table, 0),)], [("count",)]
    match = re.search(r"\bfrom\s+([a-z_]+)", q)
    table = match.group(1) if match else None
    if table and q.endswith("limit 0"):  # the export's column read (description)
        cols = _STATE["mart_columns"].get(table, [])
        return [], [(c,) for c in cols]
    if table and "order by" in q:  # the export's data read
        return list(_STATE["mart_rows"].get(table, [])), None
    return [], None


class _Cursor:
    def __init__(self) -> None:
        self.description: list[tuple] | None = None
        self._result: list[tuple] = []

    def execute(self, sql: str, params: object = None):
        CALLS.append(("execute", sql, params))
        if _STATE["execute_error"] is not None:
            raise Error(_STATE["execute_error"])
        _track(sql)
        self._result, self.description = _answer(sql)
        return self

    def executemany(self, sql: str, rows: object) -> None:
        CALLS.append(("executemany", sql, list(rows)))
        if _STATE["execute_error"] is not None:
            raise Error(_STATE["execute_error"])

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self) -> None:
        CALLS.append(("cursor.close", None, None))


class _Connection:
    def cursor(self) -> _Cursor:
        return _Cursor()

    def execute_string(self, text: str) -> None:
        CALLS.append(("execute_string", text, None))
        if _STATE["execute_error"] is not None:
            raise Error(_STATE["execute_error"])
        _track(text)

    def close(self) -> None:
        CALLS.append(("conn.close", None, None))


def connect(**kwargs):
    """Record the connect and hand back a fake connection, or raise the fake's
    own `Error` when the test asked for a driver refusal. Opens no socket."""
    CALLS.append(("connect", None, kwargs))
    if _STATE["connect_error"] is not None:
        raise Error(_STATE["connect_error"])
    return _Connection()


def set_credentials(monkeypatch) -> None:
    """Set every SNOWFLAKE_* credential to a dummy value (the names read from the
    seam's own tuple, after conftest's `_scrub_env` cleared them), so a test can
    drive a full connect. No real value, no socket."""
    from pipeline import warehouse

    for name in warehouse.SNOWFLAKE_ENV:
        monkeypatch.setenv(name, f"dummy-{name.lower()}")


def install(monkeypatch, *, credentials: bool = True, **config) -> types.ModuleType:
    """Wire this fake in as `snowflake.connector` for one test, reset its
    recording, apply `config` (schema, tables, columns, reviews, counts,
    connect_error), and (unless `credentials=False`) set the SNOWFLAKE_*
    environment. Returns this module so the test can read `CALLS`."""
    global paramstyle
    CALLS.clear()
    _CREATED.clear()
    _STATE.clear()
    _STATE.update(_DEFAULTS)
    _STATE.update(config)
    paramstyle = "pyformat"
    module = sys.modules[__name__]
    package = types.ModuleType("snowflake")
    package.connector = module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "snowflake", package)
    monkeypatch.setitem(sys.modules, "snowflake.connector", module)
    if credentials:
        set_credentials(monkeypatch)
    return module
