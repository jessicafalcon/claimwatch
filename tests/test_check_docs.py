"""Pins for scripts/check_docs.py (spec Phase 0a, invariants 4 and 5; done-when
3): each check reports on a planted violation in a tmp tree, and the real repo
is green today. Offline, no services."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_docs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_check_links_reports_a_broken_link_and_anchor(tmp_path: Path):
    (tmp_path / "b.md").write_text("# B\n\n## Real `heading` here\n")
    (tmp_path / "a.md").write_text(
        "# A\n[ok](b.md) [ok2](b.md#real-heading-here) [broken](missing.md) "
        "[anchor](b.md#nope) [web](https://example.com) [self](#a) [same](#local)\n"
    )
    errors = check_docs.check_links([tmp_path / "a.md"], tmp_path)
    assert errors == [
        "a.md: broken link: missing.md",
        "a.md: missing anchor #nope in b.md",
        "a.md: missing anchor #local in a.md",
    ]


def test_check_make_targets_reports_an_unknown_target(tmp_path: Path):
    (tmp_path / "Makefile").write_text(".PHONY: test\ntest:\n\tpytest\n")
    (tmp_path / "d.md").write_text(
        "Run `make test` then `make nope`. Make sure it works.\n"
        "```\nmake test\nmake other\n```\n"
    )
    errors = check_docs.check_make_targets([tmp_path / "d.md"], tmp_path)
    assert errors == [
        "d.md: names `make nope` — not in the Makefile",
        "d.md: names `make other` — not in the Makefile",
    ]


def test_partial_rename_is_a_failure(tmp_path: Path):
    (tmp_path / "Makefile").write_text("check-docs:\n\tx\n")
    (tmp_path / "d.md").write_text(
        "`make check-doc` and `make check-docs-all` and `make check-docs`\n"
    )
    errors = check_docs.check_make_targets([tmp_path / "d.md"], tmp_path)
    assert (
        len(errors) == 2 and "check-doc`" in errors[0] and "check-docs-all" in errors[1]
    )


def test_every_named_make_target_exists_today():
    assert check_docs.check_make_targets(check_docs.living_files(ROOT), ROOT) == []


def test_check_banned_words_reports_each_hit():
    text = (
        "A Robust plan. Seamless too.\n```\nleverage inside a fence is fine\n```\n"
        "orchestrations is a different word.\n"
    )
    assert check_docs.banned_hits(text) == ["robust", "seamless"]
    assert check_docs.banned_hits("nothing here") == []


def test_check_glossary_reports_an_eleventh_term(tmp_path: Path):
    ten = "".join(f"- **term{i}** — one sentence.\n" for i in range(10))
    (tmp_path / "ok.md").write_text(f"## Glossary\n\n{ten}\n## Next\n")
    (tmp_path / "over.md").write_text(f"## Glossary\n\n{ten}- **term10** — one more.\n")
    (tmp_path / "none.md").write_text("## Something\n- **bold** bullet\n")
    assert (
        check_docs.check_glossary([tmp_path / "ok.md", tmp_path / "none.md"], tmp_path)
        == []
    )
    assert check_docs.check_glossary([tmp_path / "over.md"], tmp_path) == [
        "over.md: glossary has 11 terms (max 10)"
    ]


def test_check_backlog_count_reports_a_mismatch(tmp_path: Path):
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "| Item | Source | Trigger |\n|---|---|---|\n"
        "| **A** open | s | t |\n| ~~**B** done~~ DONE | s | t |\n"
        "| **C** open | s | t |\n"
    )
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("Open BACKLOG rows: **3**\n")
    assert check_docs.check_backlog_count(claude, backlog) == [
        "CLAUDE.md says 3 open BACKLOG rows; BACKLOG.md has 2"
    ]
    claude.write_text("Open BACKLOG rows: **2**\n")
    assert check_docs.check_backlog_count(claude, backlog) == []
    claude.write_text("no sentence\n")
    assert check_docs.check_backlog_count(claude, backlog) == [
        "CLAUDE.md: no 'Open BACKLOG rows: **N**' sentence"
    ]


def test_backlog_count_matches_today():
    assert check_docs.check_backlog_count(ROOT / "CLAUDE.md", ROOT / "BACKLOG.md") == []


def test_check_docs_is_green_today(capsys):
    assert check_docs.main(ROOT) == 0
    assert capsys.readouterr().out.rstrip().endswith("check-docs OK")
