#!/usr/bin/env python3
"""The one docs guard. Standalone, no pytest, no services — `make check-docs`
(CI runs it too). Not a pytest file, so a docs-only edit does not re-trigger
the suite.

Five checks. Three document classes:
  LIVING  — CLAUDE.md, README.md, SPEC.md, BACKING.md: describe what exists.
  RECORDS — DECISIONS.md, BACKLOG.md: history; may name targets not built.
  PLANS   — PROJECT_BRIEF.md, docs/*.md, specs/*.md: describe what will exist.

  1. Links/anchors — every relative markdown link in ANY class points at a real
     file inside the repo, and a `#anchor` resolves to a heading there.
  2. Make targets — every `make <target>` a LIVING doc names exists in the
     Makefile as an exact token (a partial rename FAILS).
  3. Banned words — none of BANNED appears as a whole word in a LIVING doc or
     under study/, outside fenced code blocks (the one place the list itself
     may be written down). PROJECT_BRIEF.md §2.3 + the reference's style rule.
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
from review_common import ROOT, make_targets  # noqa: E402

LIVING = ("CLAUDE.md", "README.md", "SPEC.md", "BACKING.md")
RECORDS = ("DECISIONS.md", "BACKLOG.md")
PLAN_GLOBS = ("PROJECT_BRIEF.md", "docs/*.md", "specs/*.md")
STUDY_GLOB = "study/**/*.md"

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

_LINK = re.compile(r"\[[^\]]*\]\((?!https?://)(?!mailto:)(?!#)([^)\s]+)\)")
_MAKE_TICK = re.compile(r"`make ([a-z][a-z0-9-]*)[^`]*`")
_MAKE_FENCE_LINE = re.compile(r"^\s*make ([a-z][a-z0-9-]*)", re.M)
_FENCE = re.compile(r"```.*?```", re.S)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.M)
_BACKLOG_COUNT = re.compile(r"Open BACKLOG rows: \*\*(\d+)\*\*")
_TERM = re.compile(r"^- \*\*", re.M)


def living_files(root: Path) -> list[Path]:
    return [root / n for n in LIVING if (root / n).is_file()]


def record_files(root: Path) -> list[Path]:
    return [root / n for n in RECORDS if (root / n).is_file()]


def plan_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for g in PLAN_GLOBS:
        out.extend(sorted(p for p in root.glob(g) if p.is_file()))
    return out


def study_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob(STUDY_GLOB) if p.is_file())


def slug(heading: str) -> str:
    """GitHub-style anchor: strip backticks/punctuation, lowercase, spaces → `-`."""
    h = heading.replace("`", "")
    h = re.sub(r"[^\w\s-]", "", h).strip().lower()
    return re.sub(r"\s+", "-", h)


def anchors(text: str) -> set[str]:
    return {slug(h) for h in _HEADING.findall(text)}


def check_links(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in _LINK.finditer(text):
            target, _, anchor = m.group(1).partition("#")
            dest = (f.parent / target).resolve()
            if root.resolve() not in dest.parents and dest != root.resolve():
                errors.append(f"{f.relative_to(root)}: link escapes the repo: {target}")
                continue
            if not dest.exists():
                errors.append(f"{f.relative_to(root)}: broken link: {target}")
                continue
            if anchor and dest.is_file():
                if anchor not in anchors(dest.read_text(encoding="utf-8")):
                    errors.append(
                        f"{f.relative_to(root)}: missing anchor #{anchor} in {target}"
                    )
    return errors


def named_targets(text: str) -> set[str]:
    """Targets a doc NAMES: inside backticks, or on a fenced-block command line.
    Prose "make sure" is not a target."""
    names = set(_MAKE_TICK.findall(text))
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


def glossary_terms(text: str) -> int | None:
    """Number of `- **term**` bullets under `## Glossary`; None if no glossary."""
    m = re.search(r"^## Glossary.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    return len(_TERM.findall(m.group(1)))


def check_glossary(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        n = glossary_terms(f.read_text(encoding="utf-8"))
        if n is not None and n > GLOSSARY_MAX:
            errors.append(
                f"{f.relative_to(root)}: glossary has {n} terms (max {GLOSSARY_MAX})"
            )
    return errors


def open_backlog_rows(text: str) -> int:
    """Table rows whose first cell is not struck through (`~~`). Header and
    separator rows are skipped."""
    n = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Item", "") or set(cells[0]) <= {"-", ":"}:
            continue
        if not cells[0].startswith("~~"):
            n += 1
    return n


def check_backlog_count(claude: Path, backlog: Path) -> list[str]:
    if not claude.is_file() or not backlog.is_file():
        return []
    m = _BACKLOG_COUNT.search(claude.read_text(encoding="utf-8"))
    if not m:
        return ["CLAUDE.md: no 'Open BACKLOG rows: **N**' sentence"]
    stated, actual = int(m.group(1)), open_backlog_rows(backlog.read_text("utf-8"))
    if stated != actual:
        return [f"CLAUDE.md says {stated} open BACKLOG rows; BACKLOG.md has {actual}"]
    return []


def main(root: Path = ROOT) -> int:
    living = living_files(root)
    checks = [
        ("links", check_links(living + record_files(root) + plan_files(root), root)),
        ("make targets", check_make_targets(living, root)),
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
