"""Copy the marts Metabase reads into a gitignored SQLite file, so the Metabase
demonstration (9g) reads them through Metabase's built-in SQLite driver — no
DuckDB community driver (DECISIONS → Phase 9g).

Offline, stdlib `sqlite3`, no network, no credentials. Deterministic: a fixed
mart set, every table's rows in a fixed order, and DuckDB decimals written as
their exact string (`rating` decimal(2,1) -> '5.0', never a float that could
drift to 4.999...), so a re-export writes the same content every time.

No review text or per-review brand address can travel: `review_drill` carries the
non-text allowlist only, and this module refuses by name any exported mart column
in `FORBIDDEN_COLUMNS` (a second guard beside the view's own projection). The
sole text a reader sees, the theme paraphrases, is separate curated content
(`study/paraphrases.yaml`, B2.1), never a review body."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import duckdb
import yaml

from pipeline import warehouse

# The marts Metabase reads, each with the deterministic order its rows export in.
# review_drill is the drill; the theme shares give it context. All are built in
# the post-classify path (pipeline/build.py).
EXPORTED_MARTS: tuple[tuple[str, str], ...] = (
    ("review_drill", "review_id, theme"),
    ("theme_share_by_month", "month, segment, label"),
    ("theme_share_by_segment", "segment, label"),
)

# No exported mart column may carry review text or a per-review brand address —
# refused by name, so a future mart that added one cannot leak through the export.
FORBIDDEN_COLUMNS = frozenset({"body", "title", "source_url"})

DEFAULT_SQLITE = warehouse.ROOT / "data" / "metabase.sqlite"
PARAPHRASES_YAML = Path(__file__).resolve().parent.parent / "paraphrases.yaml"


class ExportError(Exception):
    """A one-line refusal on the export path — a mart missing, or a column that
    must never travel to the reader-facing engine."""


def _cell(value: object) -> object:
    """Bind a DuckDB value into SQLite: a Decimal as its exact string (fixed
    form, no float drift), everything else unchanged. sqlite3 cannot bind a
    Decimal, and str(Decimal) is exact and deterministic."""
    return str(value) if isinstance(value, Decimal) else value


def _columns(duck_conn, table: str) -> list[str]:
    """The mart's column names, from the engine's own catalog (a limit-0 read). A
    missing mart (an export before `make rebuild`, or a DB with no classify step)
    is refused in one line naming it, not a raw duckdb traceback at the boundary."""
    try:
        cur = duck_conn.execute(f"select * from {table} limit 0")
    except duckdb.Error as error:
        raise ExportError(
            f"mart {table!r} not found — run `make rebuild` (then the classify "
            f"step) before exporting"
        ) from error
    return [d[0] for d in cur.description]


def _export_table(duck_conn, sqlite_conn, table: str, order_by: str) -> int:
    """Copy one mart into SQLite: refuse a forbidden column by name, create the
    table with those columns, insert the rows in `order_by`. Returns the row
    count."""
    columns = _columns(duck_conn, table)
    leaked = sorted(set(columns) & FORBIDDEN_COLUMNS)
    if leaked:
        raise ExportError(
            f"refusing to export {table}: column(s) {leaked} must never reach "
            f"the reader-facing engine (review text / brand address)"
        )
    cols_sql = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join("?" for _ in columns)
    sqlite_conn.execute(f'drop table if exists "{table}"')
    sqlite_conn.execute(f'create table "{table}" ({cols_sql})')
    rows = duck_conn.execute(
        f"select {cols_sql} from {table} order by {order_by}"
    ).fetchall()
    sqlite_conn.executemany(
        f'insert into "{table}" ({cols_sql}) values ({placeholders})',
        [[_cell(v) for v in row] for row in rows],
    )
    return len(rows)


def _export_paraphrases(sqlite_conn, yaml_path: Path = PARAPHRASES_YAML) -> int:
    """Write B2.1's five theme paraphrases (study/paraphrases.yaml) as a
    `paraphrases` table: theme (the closed label), theme_title, paraphrase,
    source. Keyed order for determinism. This is the only text a drilled theme
    shows; it is curated study content, never a review body."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    sqlite_conn.execute('drop table if exists "paraphrases"')
    sqlite_conn.execute(
        'create table "paraphrases" (theme, theme_title, paraphrase, source)'
    )
    rows = [
        (
            theme,
            entry["title"],
            " ".join(entry["paraphrase"].split()),
            entry["source"],
        )
        for theme, entry in sorted(data.items())
    ]
    sqlite_conn.executemany(
        'insert into "paraphrases" (theme, theme_title, paraphrase, source) '
        "values (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def build_sqlite(
    duck_db: str | Path | None = None,
    sqlite_path: str | Path = DEFAULT_SQLITE,
) -> Path:
    """Build the gitignored SQLite file Metabase reads, from the DuckDB warehouse.
    A fresh file each run (the existing one is removed first), the marts and the
    paraphrases written in a fixed order — so the content is the same every time.
    Returns the SQLite path. Reads the corpus DuckDB by default; a caller (the
    test) passes its own."""
    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_path.unlink(missing_ok=True)
    duck_conn = warehouse.connect("duckdb", database=duck_db)
    sqlite_conn = sqlite3.connect(sqlite_path)
    try:
        for table, order_by in EXPORTED_MARTS:
            _export_table(duck_conn, sqlite_conn, table, order_by)
        _export_paraphrases(sqlite_conn)
        sqlite_conn.commit()
    finally:
        sqlite_conn.close()
        duck_conn.close()
    return sqlite_path
