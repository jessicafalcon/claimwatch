"""Pins for scripts/check_backing.py (spec Phase 0a, invariant 3; done-when 4):
each rule bites on a planted violation in a tmp tree; the empty table passes;
the real repo is green today. Offline, no services."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_backing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

HEADER = (
    "# BACKING\n\nprose before\n\n"
    "| Study claim (beat, chart/sentence) | Mart table | SQL file "
    "| Upstream source | Tag |\n"
    "|---|---|---|---|---|\n"
)


def _root(tmp_path: Path, rows: str = "", marts: tuple[str, ...] = ()) -> Path:
    (tmp_path / "BACKING.md").write_text(HEADER + rows)
    for m in marts:
        (tmp_path / "sql" / "marts").mkdir(parents=True, exist_ok=True)
        (tmp_path / "sql" / "marts" / m).write_text("select 1\n")
    return tmp_path


def _rows(root: Path) -> list[check_backing.Row]:
    rows, errors = check_backing.parse_table((root / "BACKING.md").read_text())
    assert errors == []
    return rows


def test_empty_table_is_ok(tmp_path: Path, capsys):
    assert check_backing.main(_root(tmp_path)) == 0
    assert (
        capsys.readouterr().out.rstrip().endswith("check-backing OK: 0 rows, 0 marts")
    )


def test_missing_header_fails(tmp_path: Path):
    (tmp_path / "BACKING.md").write_text("# no table\n")
    assert check_backing.main(tmp_path) == 1


def test_tag_outside_the_four_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1 rating trend | m | `sql/marts/m.sql` | https://x | Verified |\n",
        ("m.sql",),
    )
    assert check_backing.check_tags(_rows(root)) == [
        "line 7: tag 'Verified' not in " + str(sorted(check_backing.TAGS))
    ]


def test_measured_without_source_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1 a | m | `sql/marts/m.sql` | — | Measured |\n"
        "| B2 b | m | `sql/marts/m.sql` |  | Documented |\n"
        "| B3 c | m | `sql/marts/m.sql` | — | Modeled |\n",
        ("m.sql",),
    )
    assert check_backing.check_sources(_rows(root)) == [
        "line 7: Measured row has no upstream source",
        "line 8: Documented row has no upstream source",
    ]


def test_missing_sql_file_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1 a | m | `sql/marts/missing.sql` | https://x | Measured |\n"
        "| B2 b | m | `scripts/x.sql` | https://x | Measured |\n"
        "| B3 c | m | — | https://x | Modeled |\n",
    )
    (root / "scripts").mkdir()
    (root / "scripts" / "x.sql").write_text("select 1\n")
    assert check_backing.check_sql_files(_rows(root), root) == [
        "line 7: SQL file not found under sql/: sql/marts/missing.sql",
        "line 8: SQL path does not resolve under sql/: scripts/x.sql",
        "line 9: Modeled row names no SQL file",
    ]


def test_sql_path_traversal_is_refused(tmp_path: Path):
    """`sql/../x` starts with `sql/` as a string but leaves sql/ once resolved;
    refused for every tag, Pending included (the path is checked, not the file)."""
    root = _root(
        tmp_path,
        "| B1 a | m | `sql/../pyproject.toml` | https://x | Measured |\n"
        "| B2 b | m | `sql/../later.sql` | — | Pending |\n",
    )
    (root / "pyproject.toml").write_text("[project]\n")
    assert check_backing.check_sql_files(_rows(root), root) == [
        "line 7: SQL path does not resolve under sql/: sql/../pyproject.toml",
        "line 8: SQL path does not resolve under sql/: sql/../later.sql",
    ]


def test_pending_row_is_ok_without_source(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B2 theme share | theme_share | `sql/marts/theme_share.sql` "
        "| — | Pending |\n",
    )
    rows = _rows(root)
    assert check_backing.check_tags(rows) == []
    assert check_backing.check_sources(rows) == []
    assert (
        check_backing.check_sql_files(rows, root) == []
    )  # not built yet: the tag says so
    assert check_backing.main(root) == 0


def test_orphan_mart_sql_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1 a | m | `sql/marts/m.sql` | https://x | Measured |\n",
        ("m.sql", "orphan.sql"),
    )
    assert check_backing.check_orphans(_rows(root), root) == [
        "sql/marts/orphan.sql: no BACKING row names it"
    ]
    assert check_backing.main(root) == 1


def test_check_backing_is_green_today(capsys):
    assert check_backing.main(ROOT) == 0
    assert "check-backing OK" in capsys.readouterr().out
