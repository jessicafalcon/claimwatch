"""Pins for scripts/check_docs.py (spec Phase 0a, invariants 4 and 5; done-when
3): each check reports on a planted violation in a tmp tree, and the real repo
is green today. Offline, no services."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_docs

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
    tooling = {p.relative_to(ROOT).parts[1] for p in check_docs.tooling_files(ROOT)}
    assert tooling == {"agents", "skills"}
    by_class = {
        c: sum(
            p.relative_to(ROOT).parts[1] == c for p in check_docs.tooling_files(ROOT)
        )
        for c in tooling
    }
    assert by_class == {"agents": 6, "skills": 8}, by_class
    assert len(check_docs.command_files(ROOT)) == 8  # every skill runs today
    assert check_docs.check_make_targets(files, ROOT) == []


def test_tooling_prose_is_checked(tmp_path: Path):
    """`.claude/**/*.md` is a document class: links are checked everywhere
    under it, make targets in skills/; banned words never (an agent names
    them to flag them)."""
    agent = tmp_path / ".claude" / "agents" / "a.md"
    skill = tmp_path / ".claude" / "skills" / "s" / "SKILL.md"
    for f in (agent, skill):
        f.parent.mkdir(parents=True)
        f.write_text("Run `make nope`; see [x](../../missing.md). Flag 'robust'.\n")
    (tmp_path / "Makefile").write_text("test:\n\tx\n")
    assert check_docs.tooling_files(tmp_path) == [agent, skill]
    assert check_docs.command_files(tmp_path) == [skill]
    assert check_docs.check_links([agent, skill], tmp_path) == [
        ".claude/agents/a.md: broken link: ../../missing.md",
        ".claude/skills/s/SKILL.md: broken link: ../../missing.md",
    ]
    assert check_docs.check_make_targets([skill], tmp_path) == [
        ".claude/skills/s/SKILL.md: names `make nope` — not in the Makefile",
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


def test_check_neutrality_reports_a_token_never_a_url_and_never_the_name(
    tmp_path: Path,
):
    """A listed token as a word is reported by file:line and digest prefix; the
    same token inside a URL is not; the report never carries the token."""
    digest = hashlib.sha256(b"zzbrand").hexdigest()
    hashes = tmp_path / "scripts" / "neutrality_hashes.txt"
    hashes.parent.mkdir()
    hashes.write_text(f"# a comment\n\n{digest}\nnot-a-digest\n")
    digests, errors = check_docs.neutrality_hashes(hashes)
    assert digests == {digest}
    assert errors == ["neutrality_hashes.txt:4: not a sha256 hex digest"]
    readme = tmp_path / "README.md"
    readme.write_text(
        "ZZBrand held the refund.\n"
        "See https://zzbrand.example/zzbrand/page only.\n"
        "See https://zzbrand.example/page and zzbrand-mobile.\n"
        "A rebranding is not a hit.\n"
    )
    out = check_docs.check_neutrality([readme], digests, tmp_path)
    assert out == [
        f"README.md:1: names the study's target (sha256 {digest[:8]}…)",
        f"README.md:3: names the study's target (sha256 {digest[:8]}…)",
    ]  # line 2 carries the token only inside a URL: stripped, not a hit
    assert "zzbrand" not in "\n".join(out)
    accented = tmp_path / "notes.md"
    accented.write_text("ZZBRÄND held it; zzbránd too.\n")
    assert check_docs.check_neutrality([accented], digests, tmp_path) == [
        f"notes.md:1: names the study's target (sha256 {digest[:8]}…)"
    ]
    assert check_docs.plain_tokens("Générali, café https://x.y/z") == {
        "generali",
        "cafe",
    }
    assert check_docs.check_neutrality([readme], set(), tmp_path) == []
    _, missing = check_docs.neutrality_hashes(tmp_path / "gone.txt")
    assert missing == ["gone.txt: hash file is missing"]


def test_neutrality_files_are_the_tracked_code_and_prose_minus_the_declarations():
    paths = [
        "README.md",
        "pipeline/build.py",
        "Makefile",
        ".github/workflows/ci.yml",
        "sql/marts/x.sql",
        "ingest/sources.py",
        "fixtures/anchors/a.csv",
        "data/snapshots/m.csv",
        "scripts/neutrality_hashes.txt",
        "study/index.png",
    ]
    kept = check_docs.neutrality_files(ROOT, paths)
    assert [p.relative_to(ROOT).as_posix() for p in kept] == [
        "README.md",
        "pipeline/build.py",
        "Makefile",
        ".github/workflows/ci.yml",
        "sql/marts/x.sql",
    ]
    assert "CLAUDE.md" in check_docs.tracked_paths(ROOT)


def test_record_titles_are_read_outside_fences_with_open_state():
    """The two title readers the tag check cites against: a BACKLOG row's bold
    title with its open/struck state; every DECISIONS bold span and heading,
    a fenced one excluded."""
    assert check_docs.backlog_titles(
        "| Item | Source | Trigger |\n|---|---|---|\n"
        "| **Open row** — detail | r | t |\n| ~~**Closed row** — d~~ DONE | r | t |\n"
    ) == {"Open row": True, "Closed row": False}
    assert check_docs.decisions_titles(
        "## Gotchas\n- **An entry (2026-09-03).** Why.\n```\n**fenced**\n```\n"
    ) == {"Gotchas", "An entry (2026-09-03)."}


def test_check_comment_tags_reports_each_shape_and_missing_record(tmp_path: Path):
    """Check 7: a tag word is one of four shapes, each pointing at a record entry
    that exists; a struck BACKLOG row, an unknown DECISIONS entry, a missing
    spec and any other shape are each one error naming the line."""
    (tmp_path / "BACKLOG.md").write_text(
        "| Item | Source | Trigger |\n|---|---|---|\n"
        "| **Open row about a scan** — detail | r1 | t |\n"
        "| ~~**Closed row** — detail~~ DONE | r1 | t |\n"
    )
    (tmp_path / "DECISIONS.md").write_text(
        "## Gotchas\n\n- **The gate is a goal (2026-09-03).** Because.\n"
        "```\n**Not an entry** inside a fence\n```\n"
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "phase-1-schema.md").write_text("# s\n")
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "page.py").write_text("# " + "TODO: sample, never read\n")
    code = tmp_path / "pipeline.py"
    lines = [
        "# " + "TODO(BACKLOG): Open row about a scan",  # ok
        "x = 1  # " + "TODO(BACKLOG): Open row",  # ok — a prefix, trailing comment
        "# " + "TODO(BACKLOG): Closed row",
        "# " + "TODO(BACKLOG): Nothing like it",
        "# " + "TODO: no record",
        "# " + "HACK(DECISIONS): The gate is a goal",  # ok
        "# " + "HACK(DECISIONS): Not an entry",
        "# " + "REF: https://example.org/spec §2",  # ok
        "# " + "REF: brief §6.2",  # ok
        "# " + "REF: RFC 9309",  # ok
        "# " + "REF: see the brief",
        "# " + "INVARIANT(phase-1-schema 3): raw is append-only",  # ok
        "# " + "INVARIANT(phase-9-study 1): not yet",
        "# " + "INVARIANT 3: no parens",
    ]
    code.write_text("\n".join(lines) + "\n")
    sql = tmp_path / "mart.sql"
    sql.write_text("-- " + "HACK: no record\nselect 1\n")
    paths = ["pipeline.py", "mart.sql", "fixtures/page.py", "notes.md"]
    files = check_docs.comment_files(tmp_path, paths)
    assert files == [code, sql]
    assert check_docs.check_comment_tags(files, tmp_path) == [
        "pipeline.py:3: TODO cites a closed BACKLOG row: 'Closed row'",
        "pipeline.py:4: TODO cites no single open BACKLOG row: 'Nothing like it'",
        "pipeline.py:5: malformed TODO comment "
        "(shape: TODO(BACKLOG): <open row title>)",
        "pipeline.py:7: HACK cites no single DECISIONS entry: 'Not an entry'",
        "pipeline.py:11: malformed REF comment (shape: REF: <URL | brief §n | RFC n>)",
        "pipeline.py:13: INVARIANT names no spec: specs/phase-9-study.md",
        "pipeline.py:14: malformed INVARIANT comment "
        "(shape: INVARIANT(<spec slug> <n>): <why>)",
        "mart.sql:1: malformed HACK comment (shape: HACK(DECISIONS): <entry title>)",
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
