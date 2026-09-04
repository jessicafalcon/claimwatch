"""`make label-sample N=<n>` — draw N reviews for a human to label.

The sheet a person labels needs the review text; the answer key they produce
must not carry it (the wall). So this writes the text sheet to
`data/label_sample.csv`, which the gitignored `data/*` rule keeps out of git,
while the tracked answer key under `classify/eval/` stays `review_id, theme`
with no text. The person reads the sheet, decides each review's themes from the
closed set, and appends `(review_id, theme)` rows to the answer key offline
(hours, not a session; docs/PLAN.md §5).

The draw is deterministic: reviews are ordered by `sha256(review_id)` and the
first N taken, so re-running writes a byte-identical sheet (no clock, no random)
and a larger N is a superset of a smaller one. N is capped at the corpus size.
A warehouse with no `stg_reviews` (no rebuild yet) writes a header-only sheet
and says so — never a fabricated row."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from classify.labels import review_id
from pipeline.warehouse import ROOT, connect, database_for

SHEET = ROOT / "data" / "label_sample.csv"
SHEET_COLUMNS: tuple[str, ...] = ("review_id", "source_url", "text")


def _sample_key(rid: str) -> str:
    """The stable draw order: the hex digest of the review id. Ordering by it
    and taking a prefix makes the sample deterministic and nested in N."""
    return hashlib.sha256(rid.encode("utf-8")).hexdigest()


def _staged_reviews(db: Path) -> list[tuple[str, str, str]] | None:
    """`(review_id, source_url, text)` for every staged review, or None if the
    warehouse has no `stg_reviews` yet (no file, or no such table). `text` is
    the review's title and body, the context a labeler reads."""
    if not db.is_file():
        return None
    conn = connect("duckdb", database=db)
    try:
        exists = conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name = 'stg_reviews'"
        ).fetchone()[0]
        if not exists:
            return None
        rows = conn.execute(
            "select source, external_id, source_url, title, body from stg_reviews"
        ).fetchall()
    finally:
        conn.close()
    out: list[tuple[str, str, str]] = []
    for source, external_id, source_url, title, body in rows:
        text = "\n".join(part for part in (title, body) if part).strip()
        out.append((review_id(source, external_id), source_url, text))
    return out


def _write_sheet(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SHEET_COLUMNS)
        writer.writerows(rows)


def label_sample(
    n: int, *, sheet: str | Path = SHEET, db: str | Path | None = None
) -> int:
    """Write the labeling sheet and return how many reviews it holds. `n` is a
    positive integer (the CLI validates it); the sheet gets the first
    `min(n, corpus)` reviews in `sha256(review_id)` order. `db` defaults to the
    real corpus (`ROWS=captured`); a test passes its own. With no `stg_reviews`,
    the sheet is header-only and this returns 0."""
    sheet = Path(sheet)
    db = database_for("captured") if db is None else Path(db)
    reviews = _staged_reviews(db)
    if reviews is None:
        _write_sheet(sheet, [])
        return 0
    chosen = sorted(reviews, key=lambda r: _sample_key(r[0]))[:n]
    _write_sheet(sheet, chosen)
    return len(chosen)
