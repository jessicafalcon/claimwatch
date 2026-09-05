#!/usr/bin/env python3
"""The one docs guard. Standalone, no pytest, no services — `make check-docs`
(CI runs it too). Not a pytest file, so a docs-only edit does not re-trigger
the suite.

Five checks. Four document classes:
  LIVING  — CLAUDE.md, README.md, SPEC.md, BACKING.md: describe what exists.
  RECORDS — DECISIONS.md, BACKLOG.md: history; may name targets not built.
  PLANS   — PROJECT_BRIEF.md, docs/*.md, specs/*.md: describe what will exist.
  TOOLING — .claude/**/*.md: links checked like any class; `make` targets
            checked in commands/ and skills/ (run today) but not agents/
            (they describe the whole project's lifecycle, future targets
            included); banned words never (an agent names one to flag it).

  1. Links/anchors — every relative markdown link in ANY class points at a real
     file inside the repo, and a `#anchor` resolves to a heading there.
  2. Make targets — every `make <target>` a LIVING doc or a command names
     exists in the Makefile as an exact token (a partial rename FAILS).
  3. Banned words — none of BANNED appears as a whole word in a LIVING doc or
     under study/ (`*.md` and the `*.html` export), outside fenced code blocks
     (the one place the list itself may be written down). PROJECT_BRIEF.md
     §2.3 + the reference's style rule.
  4. Glossary — the `## Glossary` section of any LIVING doc has ≤ 10 terms
     (top-level `- **term**` bullets). Absent → OK.
  5. BACKLOG count — CLAUDE.md's "Open BACKLOG rows: **N**" equals the
     un-struck rows of BACKLOG.md's table.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import (  # noqa: E402
    LIVING_DOCS,
    MAKE_TICK,
    RECORD_DOCS,
    ROOT,
    make_targets,
)

PLAN_GLOBS = ("PROJECT_BRIEF.md", "docs/*.md", "specs/*.md")
TOOLING_GLOB = ".claude/**/*.md"
COMMAND_GLOBS = (".claude/commands/*.md", ".claude/skills/*/SKILL.md")
STUDY_GLOBS = ("study/**/*.md", "study/**/*.html")

BANNED = (
    "orchestration",
    "leverage",
    "robust",
    "scalable",
    "cutting-edge",
    "llm-powered",
    "state-of-the-art",
    "seamless",
    "comprehensive",
    "production-ready",
    "powerful",
)
GLOSSARY_MAX = 10

_LINK = re.compile(r"\[[^\]]*\]\((?!https?://)(?!mailto:)([^)\s]+)\)")
_MAKE_FENCE_LINE = re.compile(r"^\s*make ([a-z][a-z0-9-]*)", re.M)
_FENCE = re.compile(r"```.*?```", re.S)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.M)
_BACKLOG_COUNT = re.compile(r"Open BACKLOG rows: \*\*(\d+)\*\*")
_TERM = re.compile(r"^- \*\*", re.M)
# `## Glossary`, `## 11. Glossary (…)`, `### Glossary` — the brief numbers its headings.
_GLOSSARY = re.compile(r"^##+ (?:\d+\.\s*)?Glossary.*?$(.*?)(?=^## |\Z)", re.M | re.S)


def living_files(root: Path) -> list[Path]:
    return [root / n for n in LIVING_DOCS if (root / n).is_file()]


def record_files(root: Path) -> list[Path]:
    return [root / n for n in RECORD_DOCS if (root / n).is_file()]


def plan_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for g in PLAN_GLOBS:
        out.extend(sorted(p for p in root.glob(g) if p.is_file()))
    return out


def tooling_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob(TOOLING_GLOB) if p.is_file())


def command_files(root: Path) -> list[Path]:
    """Commands and skills: the tooling prose that runs today."""
    return sorted(p for g in COMMAND_GLOBS for p in root.glob(g) if p.is_file())


def study_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for g in STUDY_GLOBS:
        out.extend(sorted(p for p in root.glob(g) if p.is_file()))
    return out


def slug(heading: str) -> str:
    """GitHub's anchor rule: drop backticks and punctuation (hyphens stay),
    lowercase, then ONE hyphen per space — `# A — B` → `a--b`, as on GitHub."""
    h = heading.replace("`", "")
    h = re.sub(r"[^\w\s-]", "", h).strip().lower()
    return h.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Headings outside fenced blocks (a `# comment` in a fence is not one)."""
    return {slug(h) for h in _HEADING.findall(_FENCE.sub("", text))}


def check_links(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in _LINK.finditer(text):
            target, _, anchor = m.group(1).partition("#")
            # `#local` (no file part) is an anchor in THIS file.
            dest = f.resolve() if not target else (f.parent / target).resolve()
            shown = target or f.name
            if root.resolve() not in dest.parents and dest != root.resolve():
                errors.append(f"{f.relative_to(root)}: link escapes the repo: {target}")
                continue
            if not dest.exists():
                errors.append(f"{f.relative_to(root)}: broken link: {target}")
                continue
            if anchor and dest.is_file():
                if anchor not in anchors(dest.read_text(encoding="utf-8")):
                    errors.append(
                        f"{f.relative_to(root)}: missing anchor #{anchor} in {shown}"
                    )
    return errors


def named_targets(text: str) -> set[str]:
    """Targets a doc NAMES: inside backticks, or on a fenced-block command line.
    Prose "make sure" is not a target."""
    names = set(MAKE_TICK.findall(text))
    for block in _FENCE.findall(text):
        names.update(_MAKE_FENCE_LINE.findall(block))
    return names


def check_make_targets(files: list[Path], root: Path) -> list[str]:
    declared = make_targets(root)
    errors: list[str] = []
    for f in files:
        for name in sorted(named_targets(f.read_text(encoding="utf-8"))):
            if name not in declared:
                errors.append(
                    f"{f.relative_to(root)}: names `make {name}` — not in the Makefile"
                )
    return errors


def banned_hits(text: str) -> list[str]:
    """Whole-word, case-insensitive hits outside fenced code blocks."""
    prose = _FENCE.sub("", text)
    hits: list[str] = []
    for word in BANNED:
        if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", prose, re.I):
            hits.append(word)
    return hits


def check_banned_words(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        for word in banned_hits(f.read_text(encoding="utf-8")):
            errors.append(f"{f.relative_to(root)}: banned word: {word}")
    return errors


def glossary_section(text: str) -> str | None:
    """Body of the glossary section; None if the doc has no glossary."""
    m = _GLOSSARY.search(text)
    return m.group(1) if m else None


def check_glossary(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        body = glossary_section(f.read_text(encoding="utf-8"))
        if body is None:
            continue
        n = len(_TERM.findall(body))
        if n == 0 and body.strip():
            errors.append(
                f"{f.relative_to(root)}: glossary has no `- **term**` bullets"
            )
        elif n > GLOSSARY_MAX:
            errors.append(
                f"{f.relative_to(root)}: glossary has {n} terms (max {GLOSSARY_MAX})"
            )
    return errors


def open_backlog_rows(text: str) -> int:
    """Table rows whose first cell is not struck through (`~~`). The header and
    separator rows are skipped by POSITION (the first two `|` lines of the
    table), not by what the header says."""
    n = 0
    seen = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        seen += 1
        if seen <= 2:
            continue
        first = line.strip().strip("|").split("|")[0].strip()
        if not first.startswith("~~"):
            n += 1
    return n


def check_backlog_count(claude: Path, backlog: Path) -> list[str]:
    missing = [p.name for p in (claude, backlog) if not p.is_file()]
    if missing:
        return [f"{name}: record file is missing" for name in missing]
    m = _BACKLOG_COUNT.search(claude.read_text(encoding="utf-8"))
    if not m:
        return ["CLAUDE.md: no 'Open BACKLOG rows: **N**' sentence"]
    stated, actual = int(m.group(1)), open_backlog_rows(backlog.read_text("utf-8"))
    if stated != actual:
        return [f"CLAUDE.md says {stated} open BACKLOG rows; BACKLOG.md has {actual}"]
    return []


def main(root: Path = ROOT) -> int:
    living = living_files(root)
    tooling = tooling_files(root)
    every = living + record_files(root) + plan_files(root) + tooling
    checks = [
        ("links", check_links(every, root)),
        ("make targets", check_make_targets(living + command_files(root), root)),
        ("banned words", check_banned_words(living + study_files(root), root)),
        ("glossary", check_glossary(living, root)),
        ("BACKLOG count", check_backlog_count(root / "CLAUDE.md", root / "BACKLOG.md")),
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
    if failed:
        print(f"check-docs FAILED: {failed} check(s)")
        return 1
    print("check-docs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
