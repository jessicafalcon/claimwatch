"""Pins for scripts/check_docs.py (spec Phase 0a, invariants 4 and 5; done-when
3): each check reports on a planted violation in a tmp tree, and the real repo
is green today. Offline, no services."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_docs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_check_links_reports_a_broken_link_and_anchor(tmp_path: Path):
    (tmp_path / "b.md").write_text(
        "# B\n\n## Real `heading` here\n\n### 2.1 Deterministic first — always\n"
        "```\n# not a heading, a comment in a fence\n```\n"
    )
    (tmp_path / "a.md").write_text(
        "# A\n[ok](b.md) [ok2](b.md#real-heading-here) [broken](missing.md) "
        "[anchor](b.md#nope) [web](https://example.com) [self](#a) [same](#local)\n"
        "[punct](b.md#21-deterministic-first--always) "
        "[punct-wrong](b.md#21-deterministic-first-always) "
        "[fenced](b.md#not-a-heading-a-comment-in-a-fence)\n"
    )
    errors = check_docs.check_links([tmp_path / "a.md"], tmp_path)
    assert errors == [
        "a.md: broken link: missing.md",
        "a.md: missing anchor #nope in b.md",
        "a.md: missing anchor #local in a.md",
        "a.md: missing anchor #21-deterministic-first-always in b.md",
        "a.md: missing anchor #not-a-heading-a-comment-in-a-fence in b.md",
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
    files = check_docs.living_files(ROOT) + check_docs.command_files(ROOT)
    # six agents, three commands, four skills
    assert len(check_docs.tooling_files(ROOT)) == 13
    assert len(check_docs.command_files(ROOT)) == 3
    assert check_docs.check_make_targets(files, ROOT) == []


def test_tooling_prose_is_checked(tmp_path: Path):
    """`.claude/**/*.md` is a document class: links are checked everywhere
    under it, make targets in commands/; banned words never (an agent names
    them to flag them)."""
    agent = tmp_path / ".claude" / "agents" / "a.md"
    command = tmp_path / ".claude" / "commands" / "c.md"
    for f in (agent, command):
        f.parent.mkdir(parents=True)
        f.write_text("Run `make nope`; see [x](../../missing.md). Flag 'robust'.\n")
    (tmp_path / "Makefile").write_text("test:\n\tx\n")
    assert check_docs.tooling_files(tmp_path) == [agent, command]
    assert check_docs.command_files(tmp_path) == [command]
    assert check_docs.check_links([agent, command], tmp_path) == [
        ".claude/agents/a.md: broken link: ../../missing.md",
        ".claude/commands/c.md: broken link: ../../missing.md",
    ]
    assert check_docs.check_make_targets([command], tmp_path) == [
        ".claude/commands/c.md: names `make nope` — not in the Makefile"
    ]
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "index.html").write_text("<p>a robust page</p>\n")
    assert check_docs.study_files(tmp_path) == [tmp_path / "study" / "index.html"]
    assert check_docs.check_banned_words(
        check_docs.study_files(tmp_path), tmp_path
    ) == ["study/index.html: banned word: robust"]


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


def test_check_glossary_reports_a_numbered_heading_and_unrecognised_shape(
    tmp_path: Path,
):
    """The brief numbers its headings (`## 11. Glossary (…)`); a glossary written
    as a table counts zero bullets and must not pass as empty."""
    eleven = "".join(f"- **term{i}** — one sentence.\n" for i in range(11))
    (tmp_path / "num.md").write_text(f"## 11. Glossary (keep to ~10 terms)\n\n{eleven}")
    (tmp_path / "table.md").write_text(
        "## Glossary\n\n| term | meaning |\n|---|---|\n| claim | a request |\n"
    )
    assert check_docs.check_glossary([tmp_path / "num.md"], tmp_path) == [
        "num.md: glossary has 11 terms (max 10)"
    ]
    assert check_docs.check_glossary([tmp_path / "table.md"], tmp_path) == [
        "table.md: glossary has no `- **term**` bullets"
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
    # the header is skipped by position, not by the word "Item"
    renamed = backlog.read_text().replace("| Item |", "| Finding |")
    assert check_docs.open_backlog_rows(renamed) == 2
    # a missing record file is an error, never a vacuous green
    backlog.unlink()
    assert check_docs.check_backlog_count(claude, backlog) == [
        "BACKLOG.md: record file is missing"
    ]
    assert check_docs.check_backlog_count(tmp_path / "nope.md", backlog) == [
        "nope.md: record file is missing",
        "BACKLOG.md: record file is missing",
    ]


def test_backlog_count_matches_today():
    assert check_docs.check_backlog_count(ROOT / "CLAUDE.md", ROOT / "BACKLOG.md") == []


def test_check_docs_is_green_today(capsys):
    assert check_docs.main(ROOT) == 0
    assert capsys.readouterr().out.rstrip().endswith("check-docs OK")


def test_banned_list_matches_the_claude_md_fence():
    """CLAUDE.md states the list inside a fence; the code's tuple must be the
    same set, or the two drift apart silently."""
    text = (ROOT / "CLAUDE.md").read_text()
    fence = re.search(r"```\n(.*?)```", text[text.index("Banned words") :], re.S)
    assert fence is not None
    assert set(fence.group(1).split()) == set(check_docs.BANNED)
