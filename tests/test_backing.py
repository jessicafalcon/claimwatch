"""The evidence contract's rating rows (spec Phase 4, done-when 6). The weekly
cron gives the fetched points a tracked home but does not make the series ours
to call Measured: B1.2-B1.4 keep their Documented tag, and their source cell
names the tracked fetched file where those Measured points now live."""

from __future__ import annotations

from pipeline.warehouse import ROOT

BACKING = ROOT / "BACKING.md"
RATING_ROWS = ("B1.2", "B1.3", "B1.4")
FETCHED = "data/snapshots/fetched_snapshots.csv"


def _row(row_id: str) -> list[str]:
    for line in BACKING.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"| {row_id} "):
            return [c.strip() for c in stripped.strip("|").split("|")]
    raise AssertionError(f"{row_id} not found in BACKING.md")


def test_rating_rows_stay_documented():
    for row_id in RATING_ROWS:
        cells = _row(row_id)
        assert cells[-1] == "Documented", (row_id, cells[-1])


def test_rating_rows_name_the_tracked_fetched_file():
    for row_id in RATING_ROWS:
        source_cell = _row(row_id)[3]
        assert FETCHED in source_cell, (row_id, source_cell)
