#!/usr/bin/env python3
"""The one docs guard. Standalone, no pytest, no services — `make check-docs`
(CI runs it too). Not a pytest file, so a docs-only edit does not re-trigger
the suite.

Six checks. Four document classes:
  LIVING  — CLAUDE.md, README.md, SPEC.md, BACKING.md: describe what exists.
  RECORDS — DECISIONS.md, BACKLOG.md: history; may name targets not built.
  PLANS   — PROJECT_BRIEF.md, docs/*.md, specs/*.md: describe what will exist.
  TOOLING — .claude/**/*.md: links checked like any class; `make` targets
            checked in skills/ (run today) but not agents/
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
  6. naming the target — no tracked prose, code or comment, and no recent
     commit message, carries a token whose sha256 is listed in
     scripts/neutrality_hashes.txt (the names never enter the repo). URLs are
     stripped first; ingest/sources.py, fixtures/ and data/ are excluded —
     insurers appear there only as sourced data points. The commit window is
     the last COMMIT_MESSAGES the checkout holds: a shallow CI clone sees
     fewer; the local run and the weekly checkout see all of them.
"""

from __future__ import annotations

import functools
import hashlib
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import (
    LIVING_DOCS,
    MAKE_TICK,
    RECORD_DOCS,
    ROOT,
    make_targets,
)

PLAN_GLOBS = ("PROJECT_BRIEF.md", "docs/*.md", "specs/*.md")
TOOLING_GLOB = ".claude/**/*.md"
COMMAND_GLOBS = (".claude/skills/*/SKILL.md",)
STUDY_GLOBS = ("study/**/*.md", "study/**/*.html")
NEUTRALITY_HASHES = "scripts/neutrality_hashes.txt"
NEUTRALITY_SUFFIXES = (".py", ".sql", ".yaml", ".yml", ".md", ".toml", ".txt", ".html")
NEUTRALITY_EXCLUDED = ("ingest/sources.py", "fixtures/", "data/", NEUTRALITY_HASHES)
COMMIT_MESSAGES = 50  # the recent history a check-docs run reads

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
_URL = re.compile(r"https?://\S+")
_TOKEN = re.compile(r"[a-z0-9]+")


def plain_tokens(line: str) -> set[str]:
    """The line's words as the hash file spells them: URLs removed, then
    case-folded and de-accented (NFKD, combining marks dropped), so an
    accented spelling of a listed token still matches its digest."""
    folded = unicodedata.normalize("NFKD", _URL.sub(" ", line).casefold())
    ascii_only = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return set(_TOKEN.findall(ascii_only))


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
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
    """Skills: the tooling prose that runs today (commands moved there)."""
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
            if (
                anchor
                and dest.is_file()
                and anchor not in anchors(dest.read_text(encoding="utf-8"))
            ):
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


def tracked_paths(root: Path) -> list[str]:
    """Every path git tracks under root, "" entries dropped; [] outside git."""
    res = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True
    )
    if res.returncode != 0:
        return []
    return [p for p in res.stdout.split("\0") if p]


def neutrality_files(root: Path, paths: list[str]) -> list[Path]:
    """The tracked paths the naming check reads: code, prose and workflow
    files, minus the declared exclusions."""
    keep: list[Path] = []
    for p in paths:
        if p.startswith(NEUTRALITY_EXCLUDED):
            continue
        if (
            p.endswith(NEUTRALITY_SUFFIXES)
            or p == "Makefile"
            or p.startswith(".github/")
        ):
            keep.append(root / p)
    return keep


def neutrality_hashes(path: Path) -> tuple[set[str], list[str]]:
    """The listed digests and the lines that are not one (a name, a typo)."""
    if not path.is_file():
        return set(), [f"{path.name}: hash file is missing"]
    digests: set[str] = set()
    errors: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if _SHA256.match(line):
            digests.add(line)
        else:
            errors.append(f"{path.name}:{n}: not a sha256 hex digest")
    return digests, errors


@functools.cache
def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def named_tokens(text: str, digests: set[str]) -> list[tuple[int, str]]:
    """(line number, digest prefix) for every line carrying a listed token,
    URLs stripped first. The token itself is never returned."""
    hits: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        for d in sorted(_digest(w) for w in plain_tokens(line)):
            if d in digests:
                hits.append((n, d[:8]))
    return hits


def commit_messages(root: Path) -> str:
    res = subprocess.run(
        ["git", "log", f"-{COMMIT_MESSAGES}", "--format=%B"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return res.stdout if res.returncode == 0 else ""


def check_neutrality(files: list[Path], digests: set[str], root: Path) -> list[str]:
    errors: list[str] = []
    for f in files:
        for n, prefix in named_tokens(f.read_text(encoding="utf-8"), digests):
            rel = f.relative_to(root)
            errors.append(f"{rel}:{n}: names the study's target (sha256 {prefix}…)")
    for n, prefix in named_tokens(commit_messages(root), digests):
        errors.append(
            f"git log (last {COMMIT_MESSAGES} commits), line {n}: names the "
            f"study's target (sha256 {prefix}…)"
        )
    return errors


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


def _naming_errors(root: Path) -> list[str]:
    digests, errors = neutrality_hashes(root / NEUTRALITY_HASHES)
    files = neutrality_files(root, tracked_paths(root))
    return errors + check_neutrality(files, digests, root)


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
        ("naming the target", _naming_errors(root)),
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
