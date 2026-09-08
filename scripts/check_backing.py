#!/usr/bin/env python3
"""The evidence-contract guard — `make check-backing` (CI runs it too). Not a
pytest file. Stdlib only.

BACKING.md (PROJECT_BRIEF.md §8) has one table, one row per study claim:

  | Study claim (beat, chart/sentence) | Mart table | SQL file | Upstream source | Tag |

Rules checked, one line per check:
  1. Header — the table's five columns start with exactly those five words.
  2. Tags — every row's Tag is one of Measured, Documented, Modeled, Pending.
  3. Sources — a Measured or Documented row names a source of the declared
     shape, each `;`-separated part being exactly one of: a URL `https?://…`
     (no whitespace); a markdown link whose destination is such a URL; a
     backticked dataset name of two or more lowercase segments joined by
     `-`, `_`, `.` or `/` (`open-damir-2026-01`). Nothing trails a part, so
     `TBD`, `?`, `—`, `` `TBD` ``, a `javascript:` link or prose is not a source.
  4. SQL files — a non-Pending row's SQL file exists and lives under `sql/`.
     "No file yet" is written as a blank cell or `—` (nothing else). A Pending
     row may point at a file not built yet (the tag says so: the brief writes
     BACKING before code; a row flips Pending → Measured/Modeled in the phase
     that lands its mart).
  5. Orphans — every `sql/marts/*.sql` is named by at least one row (work that
     maps to no claim is out of scope, §8).
  6. Row ids — every claim cell starts with `B<beat>.<n> ` (`B2.3 …`), the id
     SPEC.md panels cite.
  7. Citations — SPEC.md and BACKING.md reconcile both ways: every `B<beat>.<n>`
     token in SPEC.md (outside code fences) is a BACKING row, and every BACKING
     row is cited by at least one SPEC.md panel or prose sentence. An absent
     SPEC.md (Phase 0a, before the study structure is written) is OK.

An empty table with no marts is OK — Phase 0a. Exit 1 on any FAIL.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import ROOT, read_text_or_error

COLUMNS = ("Study claim", "Mart table", "SQL file", "Upstream source", "Tag")
TAGS = frozenset({"Measured", "Documented", "Modeled", "Pending"})
NEEDS_SOURCE = frozenset({"Measured", "Documented"})
NO_FILE = frozenset({"", "—"})  # the one declared spelling of "no SQL file yet"
_SEP = re.compile(r":?-+:?")  # one separator cell: ---, :---, ---:, :---:
_ROW_ID = re.compile(r"^(B\d+\.\d+) ")  # `B<beat>.<n> ` opens every claim cell
_CITE = re.compile(r"\bB\d+\.\d+\b")  # a `B<beat>.<n>` token SPEC.md cites
_FENCE = re.compile(
    r"```.*?```", re.S
)  # a fenced block: an example B-id is not a citation
# One source part, whole-cell anchored: a URL, a markdown link TO a URL, or a
# backticked dataset name (two or more lowercase segments — `tbd` is not one).
_URL = r"https?://\S+"
_LINK_URL = r"https?://[^\s()<>]+"  # inside `[…](…)` the `)` closes the link
_DATASET = r"[a-z0-9]+(?:[-._/][a-z0-9]+)+"
_SOURCE_PART = re.compile(rf"^(?:{_URL}|\[[^\]]+\]\({_LINK_URL}\)|`{_DATASET}`)$")


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
            sep = lines[i + 1] if i + 1 < len(lines) else ""
            sep_cells = [c.strip() for c in sep.strip().strip("|").split("|")]
            if len(sep_cells) != len(COLUMNS) or not all(
                _SEP.fullmatch(c) for c in sep_cells
            ):
                return [], [f"line {i + 2}: header is not followed by a separator row"]
            rows: list[Row] = []
            for j in range(i + 2, len(lines)):
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


def check_row_ids(rows: list[Row]) -> list[str]:
    return [
        f"line {r.line}: claim does not start with a row id `B<beat>.<n> `: "
        f"{r.claim[:30]!r}"
        for r in rows
        if not _ROW_ID.match(r.claim)
    ]


def source_ok(cell: str) -> bool:
    """Every `;`-separated part matches one declared shape; an empty cell or a
    placeholder of any spelling does not."""
    parts = [part.strip() for part in cell.split(";")]
    return bool(cell.strip()) and all(_SOURCE_PART.match(part) for part in parts)


def check_sources(rows: list[Row]) -> list[str]:
    return [
        f"line {r.line}: {r.tag} row has no source of the declared shape "
        "(URL, markdown link, or `dataset`)"
        for r in rows
        if r.tag in NEEDS_SOURCE and not source_ok(r.source)
    ]


def check_sql_files(rows: list[Row], root: Path) -> list[str]:
    """Every given path RESOLVES under `sql/` (no `..`, no symlink out); a
    non-Pending row's file exists. A Pending row may name a file not built yet."""
    sql_root = (root / "sql").resolve()
    errors: list[str] = []
    for r in rows:
        path = _bare(r.sql_file)
        if path in NO_FILE:
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


def row_id(claim: str) -> str | None:
    m = _ROW_ID.match(claim)
    return m.group(1) if m else None


def check_citations(rows: list[Row], root: Path) -> list[str]:
    """SPEC.md ↔ BACKING.md, both ways. An absent SPEC.md (Phase 0a) is OK; a
    B-id inside a code fence is an example, not a citation."""
    spec = root / "SPEC.md"
    if not spec.is_file():
        return []
    text, err = read_text_or_error(spec, root)
    if text is None:
        return [err]
    cited = set(_CITE.findall(_FENCE.sub("", text)))
    defined = {rid for r in rows if (rid := row_id(r.claim))}
    return [
        f"SPEC.md cites {b}, which is not a BACKING row"
        for b in sorted(cited - defined)
    ] + [
        f"BACKING row {b} is cited by no SPEC.md panel or sentence"
        for b in sorted(defined - cited)
    ]


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
    text, err = read_text_or_error(backing, root)
    if text is None:
        print(f"FAIL header: {err}")
        return 1
    rows, header_errors = parse_table(text)
    checks = [
        ("header", header_errors),
        ("tags", check_tags(rows)),
        ("sources", check_sources(rows)),
        ("SQL files", check_sql_files(rows, root)),
        ("orphans", check_orphans(rows, root)),
        ("row ids", check_row_ids(rows)),
        ("citations", check_citations(rows, root)),
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
