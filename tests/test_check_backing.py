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


def test_missing_separator_is_a_header_error(tmp_path: Path):
    """A header followed directly by a data row (no `|---|` line) is an error,
    not a silently swallowed first row."""
    (tmp_path / "BACKING.md").write_text(
        HEADER.replace("|---|---|---|---|---|\n", "")
        + "| B1.1 a | m | `sql/marts/m.sql` | https://x | Measured |\n"
    )
    rows, errors = check_backing.parse_table((tmp_path / "BACKING.md").read_text())
    assert rows == [] and errors == [
        "line 6: header is not followed by a separator row"
    ]


def test_missized_row_is_a_header_error(tmp_path: Path, capsys):
    root = _root(
        tmp_path, "| B1.1 a | m | `sql/marts/m.sql` | https://x | Measured | extra |\n"
    )
    rows, errors = check_backing.parse_table((root / "BACKING.md").read_text())
    assert rows == [] and errors == ["line 7: row has 6 cells, want 5"]
    assert check_backing.main(root) == 1
    assert "row has 6 cells, want 5" in capsys.readouterr().out


def test_tag_outside_the_four_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1.1 rating trend | m | `sql/marts/m.sql` | https://x | Verified |\n",
        ("m.sql",),
    )
    assert check_backing.check_tags(_rows(root)) == [
        "line 7: tag 'Verified' not in " + str(sorted(check_backing.TAGS))
    ]


def test_measured_without_source_fails(tmp_path: Path):
    """A source is a declared shape, not 'anything but a known placeholder':
    `TBD` and `?` fail exactly like `—` and empty; Modeled needs none."""
    root = _root(
        tmp_path,
        "| B1.1 a | m | `sql/marts/m.sql` | — | Measured |\n"
        "| B2.1 b | m | `sql/marts/m.sql` |  | Documented |\n"
        "| B3.1 c | m | `sql/marts/m.sql` | TBD | Measured |\n"
        "| B4.1 d | m | `sql/marts/m.sql` | ? | Documented |\n"
        "| B5.1 e | m | `sql/marts/m.sql` | see the brief | Measured |\n"
        "| B6.1 f | m | `sql/marts/m.sql` | — | Modeled |\n"
        # closed at both ends: a placeholder in backticks, a link to a non-URL,
        # a blank name, a valid part with trailing prose, an empty `;` part
        "| B7.1 g | m | `sql/marts/m.sql` | `TBD` | Measured |\n"
        "| B8.1 h | m | `sql/marts/m.sql` | [src](javascript:alert(1)) | Documented |\n"
        "| B9.1 i | m | `sql/marts/m.sql` | [a](../../etc/passwd) | Measured |\n"
        "| B10.1 j | m | `sql/marts/m.sql` | ` ` | Documented |\n"
        "| B11.1 k | m | `sql/marts/m.sql` | https://a.example see notes | Measured |\n"
        "| B12.1 l | m | `sql/marts/m.sql` | `ds-1` and prose | Documented |\n"
        "| B13.1 m | m | `sql/marts/m.sql` | https://a.example; | Measured |\n",
        ("m.sql",),
    )
    msg = "row has no source of the declared shape (URL, markdown link, or `dataset`)"
    assert check_backing.check_sources(_rows(root)) == [
        f"line 7: Measured {msg}",
        f"line 8: Documented {msg}",
        f"line 9: Measured {msg}",
        f"line 10: Documented {msg}",
        f"line 11: Measured {msg}",
        f"line 13: Measured {msg}",
        f"line 14: Documented {msg}",
        f"line 15: Measured {msg}",
        f"line 16: Documented {msg}",
        f"line 17: Measured {msg}",
        f"line 18: Documented {msg}",
        f"line 19: Measured {msg}",
    ]


def test_source_shapes_accepted(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1.1 a | m | `sql/marts/m.sql` | https://example.org/p?x=1 | Measured |\n"
        "| B2.1 b | m | `sql/marts/m.sql` | [profile](https://example.org/p) "
        "| Documented |\n"
        "| B3.1 c | m | `sql/marts/m.sql` | `open-damir-2026-01` | Measured |\n"
        "| B4.1 d | m | `sql/marts/m.sql` | https://a.example; https://b.example "
        "| Measured |\n"
        "| B5.1 e | m | `sql/marts/m.sql` | `fixtures/anchors/x.csv` | Documented |\n"
        "| B6.1 f | m | `sql/marts/m.sql` | https://x.example/a_(b) | Measured |\n",
        ("m.sql",),
    )
    assert check_backing.check_sources(_rows(root)) == []


def test_missing_sql_file_fails(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B1.1 a | m | `sql/marts/missing.sql` | https://x | Measured |\n"
        "| B2.1 b | m | `scripts/x.sql` | https://x | Measured |\n"
        "| B3.1 c | m | — | https://x | Modeled |\n",
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
        "| B1.1 a | m | `sql/../pyproject.toml` | https://x | Measured |\n"
        "| B2.1 b | m | `sql/../later.sql` | — | Pending |\n",
    )
    (root / "pyproject.toml").write_text("[project]\n")
    assert check_backing.check_sql_files(_rows(root), root) == [
        "line 7: SQL path does not resolve under sql/: sql/../pyproject.toml",
        "line 8: SQL path does not resolve under sql/: sql/../later.sql",
    ]


def test_pending_row_is_ok_without_source(tmp_path: Path):
    root = _root(
        tmp_path,
        "| B2.1 theme share | theme_share | `sql/marts/theme_share.sql` "
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
        "| B1.1 a | m | `sql/marts/m.sql` | https://x | Measured |\n",
        ("m.sql", "orphan.sql"),
    )
    assert check_backing.check_orphans(_rows(root), root) == [
        "sql/marts/orphan.sql: no BACKING row names it"
    ]
    assert check_backing.main(root) == 1


def test_claim_without_row_id_fails(tmp_path: Path):
    """The id SPEC.md cites is checked, not assumed: `B2.3 ` opens the cell."""
    root = _root(
        tmp_path,
        "| B2.3 theme share | m | `sql/marts/m.sql` | https://x | Measured |\n"
        "| theme share | m | `sql/marts/m.sql` | https://x | Measured |\n"
        "| B2 theme share | m | `sql/marts/m.sql` | https://x | Measured |\n"
        "| B2.3theme | m | `sql/marts/m.sql` | https://x | Measured |\n",
        ("m.sql",),
    )
    assert check_backing.check_row_ids(_rows(root)) == [
        "line 8: claim does not start with a row id `B<beat>.<n> `: 'theme share'",
        "line 9: claim does not start with a row id `B<beat>.<n> `: 'B2 theme share'",
        "line 10: claim does not start with a row id `B<beat>.<n> `: 'B2.3theme'",
    ]
    assert check_backing.main(root) == 1


def test_spec_citations(tmp_path: Path):
    """SPEC.md ↔ BACKING.md reconcile both ways; an absent SPEC.md is OK; a B-id
    inside a code fence is an example, not a citation."""
    rows_text = (
        "| B1.1 rating trend | m | `sql/marts/m.sql` | — | Pending |\n"
        "| B2.2 theme share | m | `sql/marts/m.sql` | — | Pending |\n"
    )
    root = _root(tmp_path, rows_text, ("m.sql",))
    rows = _rows(root)

    # no SPEC.md yet (Phase 0a): the check is vacuously OK
    assert check_backing.check_citations(rows, root) == []

    # a dangling citation and an uncited row, each reported once
    (root / "SPEC.md").write_text(
        "# SPEC\n\nBeat 1 cites B1.1 here.\n\nBeat 2 cites B9.9 (no such row).\n"
        "\n```\nan example B7.7 inside a fence is not a citation\n```\n"
    )
    assert check_backing.check_citations(rows, root) == [
        "SPEC.md cites B9.9, which is not a BACKING row",
        "BACKING row B2.2 is cited by no SPEC.md panel or sentence",
    ]
    assert check_backing.main(root) == 1

    # matched sets in both directions pass
    (root / "SPEC.md").write_text("# SPEC\n\nB1.1 and B2.2 are both cited.\n")
    assert check_backing.check_citations(rows, root) == []
    assert check_backing.main(root) == 0


def test_check_backing_is_green_today(capsys):
    assert check_backing.main(ROOT) == 0
    assert "check-backing OK" in capsys.readouterr().out
