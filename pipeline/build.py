"""raw -> staging -> marts, run the same way twice (PROJECT_BRIEF.md §4.3,
docs/PLAN.md §4 decision 2). The stages:

  create_raw   -> run every sql/raw/*.sql (`create table if not exists`)
  load_reviews -> insert each row only if (source, external_id, content_hash)
                  is unseen; the rows come from the fixture (stdlib csv, no
                  pandas) or from the scraper's captures (ingest.app_store's
                  strict parser) — the SAME guard for both (Phase 2)
  build_derived-> run sql/staging/*.sql then sql/marts/*.sql (`create or replace`)

Idempotency: raw is append-only keyed on the natural key + a content fingerprint,
so a re-run of an unchanged review inserts nothing and an edited review (new
fingerprint) appends a new row; staging keeps the latest capture. `run_id` is
stamped here in Python (never in SQL — no clock on the data path) and is in no
natural key and no mart, so a changing `run_id` never duplicates a row or moves a
number; for a fixture input it is the input name and for captures the capture
id, making every rebuild from the same input byte-stable, not merely
count-stable. A rebuild reads captures from disk and never imports the fetcher:
no network on the data path."""

from __future__ import annotations

import csv
import hashlib
import tempfile
from pathlib import Path

from ingest.app_store import read_captures
from pipeline import warehouse
from pipeline.warehouse import ROOT, connect

# The closed set of rebuild inputs, named by what they are (`ROWS=`, spec
# Phase 3a, pinned decision 5): the scraper's captures under data/ (the real
# run, the default), nothing, the synthetic fixture, or the frozen samples
# read as captures (the offline proof of every parser path).
INPUTS = ("captured", "none", "synthetic", "samples")
DEFAULT_CACHE = ROOT / "data" / "cache" / "app-store"  # gitignored (data/*)
SAMPLE_CAPTURE = ROOT / "fixtures" / "app-store"
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
        warehouse.run_sql_file(conn, path)


def build_derived(conn) -> None:
    for stage in ("staging", "marts"):
        for path in _sql_files(stage):
            warehouse.run_sql_file(conn, path)


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


def capture_root(rows: str, cache_dir: str | Path | None = None) -> Path | None:
    """Where a capture-fed rebuild reads from: `captured` -> data/cache/app-store
    (or `cache_dir`), `samples` -> the frozen sample (or `cache_dir`); the
    other inputs read no capture."""
    if rows == "captured":
        return Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE
    if rows == "samples":
        return Path(cache_dir) if cache_dir is not None else SAMPLE_CAPTURE
    return None


def rebuild(
    target: str = "duckdb",
    rows: str = "none",
    *,
    database: str | Path | None = None,
    run_id: str | None = None,
    cache_dir: str | Path | None = None,
) -> dict[str, int]:
    """Build the warehouse from raw and return the per-table row counts.
    `captured` loads every capture under data/cache (zero captures -> zero
    rows); `none` runs the pipeline end to end with zero rows; `synthetic`
    loads the fixture; `samples` loads the frozen samples through the real
    parsers. Capture-fed rows go through the same `load_reviews` guard as the
    fixture. With no `database`, each input builds its own file
    (`warehouse.database_for`)."""
    if database is None:
        database = warehouse.database_for(rows)
    conn = connect(target, database=database)
    try:
        create_raw(conn)
        if rows == "synthetic":
            load_reviews(conn, read_fixture("synthetic"), run_id or "synthetic")
        root = capture_root(rows, cache_dir)
        if root is not None:
            for capture_id, parsed in read_captures(root):
                stamp = run_id or ("app-store" if rows == "samples" else capture_id)
                load_reviews(conn, parsed, f"app-store:{stamp}")
        build_derived(conn)
        return table_counts(conn)
    finally:
        conn.close()


def idempotency_check(
    target: str = "duckdb",
    rows: str = "synthetic",
    *,
    cache_dir: str | Path | None = None,
) -> tuple[bool, dict[str, int], dict[str, int]]:
    """Rebuild twice into one fresh database (different `run_id` each time, to
    prove `run_id` is not in the natural key) and compare per-table counts. Uses a
    throwaway file so it depends on no prior state and touches no working db."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idempotency.duckdb"
        first = rebuild(target, rows, database=db, run_id="run-1", cache_dir=cache_dir)
        second = rebuild(target, rows, database=db, run_id="run-2", cache_dir=cache_dir)
    return first == second, first, second


def reset(target: str = "duckdb", *, database: str | Path | None = None) -> list[Path]:
    """Delete the DuckDB files (and their write-ahead logs): with no `database`,
    every input's file — the real corpus and each fixture's own. The CLI gates
    this on CONFIRM=yes from the command line; this function does the deletion
    once confirmed. Returns the files removed."""
    if target != "duckdb":
        raise ValueError(f"reset only handles the DuckDB file, not {target!r}")
    dbs = (
        [warehouse.database_for(r) for r in INPUTS]
        if database is None
        else [Path(database)]
    )
    removed: list[Path] = []
    for db in dbs:
        for p in (db, db.with_name(db.name + ".wal")):
            if p.exists():
                p.unlink()
                removed.append(p)
    return removed
