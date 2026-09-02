#!/usr/bin/env python3
"""The evidence-contract guard — `make check-backing` (CI runs it too). Not a
pytest file. Stdlib only.

BACKING.md (PROJECT_BRIEF.md §8) has one table, one row per study claim:

  | Study claim (beat, chart/sentence) | Mart table | SQL file | Upstream source | Tag |

Rules checked, one line per check:
  1. Header — the table's five columns start with exactly those five words.
  2. Tags — every row's Tag is one of Measured, Documented, Modeled, Pending.
  3. Sources — a Measured or Documented row names an upstream source.
  4. SQL files — a non-Pending row's SQL file exists and lives under `sql/`.
     A Pending row may point at a file not built yet (the tag says so: the
     brief writes BACKING before code; a row flips Pending → Measured/Modeled
     in the phase that lands its mart).
  5. Orphans — every `sql/marts/*.sql` is named by at least one row (work that
     maps to no claim is out of scope, §8).

An empty table with no marts is OK — Phase 0a. Exit 1 on any FAIL.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import ROOT  # noqa: E402

COLUMNS = ("Study claim", "Mart table", "SQL file", "Upstream source", "Tag")
TAGS = frozenset({"Measured", "Documented", "Modeled", "Pending"})
NEEDS_SOURCE = frozenset({"Measured", "Documented"})
EMPTY = {"", "—", "-", "n/a"}


@dataclass(frozen=True)
class Row:
    claim: str
    mart: str
    sql_file: str
    source: str
    tag: str
    line: int


def parse_table(text: str) -> tuple[list[Row], list[str]]:
    """The first table whose header matches COLUMNS; its rows. A missing or
    mis-shaped header is an error (the shape IS the contract)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == len(COLUMNS) and all(
            c.startswith(col) for c, col in zip(cells, COLUMNS, strict=True)
        ):
            rows: list[Row] = []
            for j in range(i + 2, len(lines)):  # skip the separator row
                raw = lines[j]
                if not raw.startswith("|"):
                    break
                cells = [c.strip() for c in raw.strip().strip("|").split("|")]
                if len(cells) != len(COLUMNS):
                    return [], [f"line {j + 1}: row has {len(cells)} cells, want 5"]
                rows.append(Row(*cells, line=j + 1))
            return rows, []
    return [], ["no table with the §8 five-column header (Study claim … Tag)"]


def _bare(cell: str) -> str:
    return cell.strip("`").strip()


def check_tags(rows: list[Row]) -> list[str]:
    return [
        f"line {r.line}: tag {r.tag!r} not in {sorted(TAGS)}"
        for r in rows
        if r.tag not in TAGS
    ]


def check_sources(rows: list[Row]) -> list[str]:
    return [
        f"line {r.line}: {r.tag} row has no upstream source"
        for r in rows
        if r.tag in NEEDS_SOURCE and _bare(r.source) in EMPTY
    ]


def check_sql_files(rows: list[Row], root: Path) -> list[str]:
    """Every given path RESOLVES under `sql/` (no `..`, no symlink out); a
    non-Pending row's file exists. A Pending row may name a file not built yet."""
    sql_root = (root / "sql").resolve()
    errors: list[str] = []
    for r in rows:
        path = _bare(r.sql_file)
        if path in EMPTY:
            if r.tag != "Pending":
                errors.append(f"line {r.line}: {r.tag} row names no SQL file")
            continue
        target = (root / path).resolve()
        if sql_root not in target.parents:
            errors.append(
                f"line {r.line}: SQL path does not resolve under sql/: {path}"
            )
        elif r.tag != "Pending" and not target.is_file():
            errors.append(f"line {r.line}: SQL file not found under sql/: {path}")
    return errors


def check_orphans(rows: list[Row], root: Path) -> list[str]:
    named = {_bare(r.sql_file) for r in rows}
    marts = sorted(p for p in root.glob("sql/marts/*.sql") if p.is_file())
    return [
        f"{p.relative_to(root)}: no BACKING row names it"
        for p in marts
        if str(p.relative_to(root)) not in named
    ]


def main(root: Path = ROOT) -> int:
    backing = root / "BACKING.md"
    if not backing.is_file():
        print("FAIL header: BACKING.md does not exist")
        return 1
    rows, header_errors = parse_table(backing.read_text(encoding="utf-8"))
    checks = [
        ("header", header_errors),
        ("tags", check_tags(rows)),
        ("sources", check_sources(rows)),
        ("SQL files", check_sql_files(rows, root)),
        ("orphans", check_orphans(rows, root)),
    ]
    failed = 0
    for name, errors in checks:
        if errors:
            failed += 1
            print(f"FAIL {name}:")
            for e in errors:
                print(f"  {e}")
        else:
            print(f"ok   {name}")
    n_marts = len(list(root.glob("sql/marts/*.sql")))
    if failed:
        print(f"check-backing FAILED: {failed} check(s)")
        return 1
    print(f"check-backing OK: {len(rows)} rows, {n_marts} marts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
