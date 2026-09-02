"""raw -> staging -> marts, run the same way twice (PROJECT_BRIEF.md §4.3,
docs/PLAN.md §4 decision 2). The stages:

  create_raw   -> run every sql/raw/*.sql (`create table if not exists`)
  load_reviews -> read the fixture in Python (stdlib csv, no pandas), insert each
                  row only if (source, external_id, content_hash) is unseen
  build_derived-> run sql/staging/*.sql then sql/marts/*.sql (`create or replace`)

Idempotency: raw is append-only keyed on the natural key + a content fingerprint,
so a re-run of an unchanged review inserts nothing and an edited review (new
fingerprint) appends a new row; staging keeps the latest capture. `run_id` is
stamped here in Python (never in SQL — no clock on the data path) and is in no
natural key and no mart, so a changing `run_id` never duplicates a row or moves a
number; in FIXTURE mode it is the fixture name, making the synthetic run
byte-stable, not merely count-stable."""

from __future__ import annotations

import csv
import hashlib
import tempfile
from pathlib import Path

from pipeline.warehouse import ROOT, connect

FIXTURES = ("empty", "synthetic")  # the closed set of rebuild inputs
_SEP = "\x1f"  # unit separator — cannot appear in the CSV content fields
# The content fields whose hash is the fingerprint (provenance is excluded, so a
# re-capture of the same review at a new time is NOT a new row).
_CONTENT = ("rating", "review_date", "title", "body")


def content_hash(row: dict[str, str]) -> str:
    """sha256 of the content fields, in a fixed order, so it is stable across runs
    and machines."""
    payload = _SEP.join(str(row[c]) for c in _CONTENT)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sql_files(stage: str) -> list[Path]:
    """The sql/<stage>/*.sql files in name order (deterministic). A missing or
    empty stage directory yields no files (marts is empty in Phase 1)."""
    return sorted((ROOT / "sql" / stage).glob("*.sql"))


def create_raw(conn) -> None:
    for path in _sql_files("raw"):
        conn.execute(path.read_text(encoding="utf-8"))


def build_derived(conn) -> None:
    for stage in ("staging", "marts"):
        for path in _sql_files(stage):
            conn.execute(path.read_text(encoding="utf-8"))


def read_fixture(name: str) -> list[dict[str, str]]:
    with (ROOT / "fixtures" / name / "reviews.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_reviews(conn, rows: list[dict[str, str]], run_id: str) -> None:
    """Append each review not already present under its natural key + content
    hash. ANSI `insert ... select ... where not exists (...)`, parameterized — no
    reader function in SQL, so the load stays portable."""
    for r in rows:
        h = content_hash(r)
        conn.execute(
            "insert into raw_reviews "
            "(source, external_id, source_url, captured_at, run_id, "
            " review_date, rating, title, body, content_hash) "
            "select ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
            "where not exists (select 1 from raw_reviews "
            "where source = ? and external_id = ? and content_hash = ?)",
            [
                r["source"],
                r["external_id"],
                r["source_url"],
                r["captured_at"],
                run_id,
                r["review_date"],
                int(r["rating"]),
                r["title"],
                r["body"],
                h,
                r["source"],
                r["external_id"],
                h,
            ],
        )


def table_counts(conn) -> dict[str, int]:
    """Row count per table in the default schema — the reproducibility signal
    `idempotency-check` diffs."""
    names = [
        row[0]
        for row in conn.execute(
            "select table_name from information_schema.tables "
            "where table_schema = 'main' order by table_name"
        ).fetchall()
    ]
    return {n: conn.execute(f"select count(*) from {n}").fetchone()[0] for n in names}


def rebuild(
    target: str = "duckdb",
    fixture: str = "empty",
    *,
    database: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, int]:
    """Build the warehouse from raw and return the per-table row counts. `empty`
    runs the pipeline end to end with zero rows; `synthetic` loads the fixture."""
    conn = connect(target, database=database)
    try:
        create_raw(conn)
        if fixture == "synthetic":
            load_reviews(conn, read_fixture("synthetic"), run_id or "synthetic")
        build_derived(conn)
        return table_counts(conn)
    finally:
        conn.close()


def idempotency_check(
    target: str = "duckdb", fixture: str = "synthetic"
) -> tuple[bool, dict[str, int], dict[str, int]]:
    """Rebuild twice into one fresh database (different `run_id` each time, to
    prove `run_id` is not in the natural key) and compare per-table counts. Uses a
    throwaway file so it depends on no prior state and touches no working db."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idempotency.duckdb"
        first = rebuild(target, fixture, database=db, run_id="run-1")
        second = rebuild(target, fixture, database=db, run_id="run-2")
    return first == second, first, second


def reset(target: str = "duckdb", *, database: str | Path | None = None) -> list[Path]:
    """Delete the DuckDB file (and its write-ahead log). The CLI gates this on
    CONFIRM=yes from the command line; this function does the deletion once
    confirmed. Returns the files removed."""
    if target != "duckdb":
        raise ValueError(f"reset only handles the DuckDB file, not {target!r}")
    from pipeline.warehouse import DEFAULT_DB

    db = Path(DEFAULT_DB if database is None else database)
    removed: list[Path] = []
    for p in (db, db.with_name(db.name + ".wal")):
        if p.exists():
            p.unlink()
            removed.append(p)
    return removed
