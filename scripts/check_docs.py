#!/usr/bin/env python3
"""The one docs guard. Standalone, no pytest, no services — `make check-docs`
(CI runs it too). Not a pytest file, so a docs-only edit does not re-trigger
the suite.

Eight checks. Four document classes:
  LIVING  — CLAUDE.md, README.md, SPEC.md, BACKING.md: describe what exists.
  RECORDS — DECISIONS.md, BACKLOG.md, LESSONS.md: history; may name targets
            not built.
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
  7. comment tags — a tagged comment in tracked code (`.py`, `.sql`, `.yaml`,
     `.yml`, Makefile) is a pointer at a record, and the record entry exists:
     `TODO(BACKLOG): <open row title>`, `HACK(DECISIONS): <entry title>`,
     `REF: <URL | brief §n | RFC n>`, `INVARIANT(<spec stem> <n>): …` where
     the stem is the spec's file name, `specs/<stem>.md`. A tag OPENS a
     comment: `# TODO(...)`, `-- HACK(...)`; a tag word later in a comment
     is prose and is not read. Python comments are the tokenizer's COMMENT
     tokens (a tag inside a string literal or docstring is not a comment);
     the other files are read by line, the text after the first `#` or `--`.
     A tag in any other shape is a FAIL naming the shape. FIXME and XXX never
     pass ruff (TD001, FIX001, FIX003), so they are not read here. The four
     are the closed set (code-craft → Comments).
  8. lessons — every row of LESSONS.md's table has six cells, a Class from the
     closed set LESSON_CLASSES (the same set the file's fence spells) and a
     Status shaped `open`, `promoted → <mechanism>` or `expired <date>`.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import io
import re
import sys
import tokenize
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import (
    LIVING_DOCS,
    MAKE_TICK,
    RECORD_DOCS,
    ROOT,
    diff_paths,
    make_targets,
    read_text_or_error,
    readable,
    run,
    shown,
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

# Check 7 — tagged comments. A comment opener (`#` or `--`), a tag word, the rest.
COMMENT_SUFFIXES = (".py", ".sql", ".yaml", ".yml")
COMMENT_NAMES = ("Makefile",)
COMMENT_EXCLUDED = ("fixtures/", "data/")
_TAG_OPENS = re.compile(r"^\s*(TODO|HACK|REF|INVARIANT)\b(.*)$")
_LINE_COMMENT = {".sql": "--", ".yaml": "#", ".yml": "#", "": "#"}
_TAG_SHAPES = {
    "TODO": re.compile(r"^\(BACKLOG\): (\S.*?)\s*$"),
    "HACK": re.compile(r"^\(DECISIONS\): (\S.*?)\s*$"),
    "REF": re.compile(r"^: (?:https?://\S+|brief §\d+(?:\.\d+)*|RFC \d+)(?:\s|$)"),
    "INVARIANT": re.compile(r"^\((phase-[a-z0-9-]+) \d+\): \S"),
}
_TAG_HELP = {
    "TODO": "TODO(BACKLOG): <open row title>",
    "HACK": "HACK(DECISIONS): <entry title>",
    "REF": "REF: <URL | brief §n | RFC n>",
    "INVARIANT": "INVARIANT(<spec stem> <n>): <why>",
}
# Check 8 — the lessons record: a closed class set and a status shape.
LESSON_CLASSES = (
    "unpinned",
    "unshaped-input",
    "traceback-at-boundary",
    "suppression",
    "site-fix",
    "caller-sourced",
    "partial-write",
    "name-drift",
    "empty-default",
)
LESSON_CELLS = 6
_LESSON_STATUS = re.compile(r"^(?:open|promoted → \S.*|expired \d{4}-\d{2}-\d{2})$")
_BACKLOG_TITLE = re.compile(r"^\|\s*(~~)?\s*\*\*(.+?)\*\*", re.M)
_BOLD = re.compile(r"\*\*(.+?)\*\*")


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
    for f, text in readable(files, root, errors):
        for m in _LINK.finditer(text):
            target, _, anchor = m.group(1).partition("#")
            # `#local` (no file part) is an anchor in THIS file.
            dest = f.resolve() if not target else (f.parent / target).resolve()
            target_shown = target or f.name
            if root.resolve() not in dest.parents and dest != root.resolve():
                errors.append(f"{f.relative_to(root)}: link escapes the repo: {target}")
                continue
            if not dest.exists():
                errors.append(f"{f.relative_to(root)}: broken link: {target}")
                continue
            if not anchor or not dest.is_file():
                continue
            dest_text, err = read_text_or_error(dest, root)
            if dest_text is None:
                errors.append(err)
            elif anchor not in anchors(dest_text):
                errors.append(
                    f"{f.relative_to(root)}: missing anchor #{anchor} in {target_shown}"
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
    declared, err = make_targets(root)
    if err:
        return [err]  # nothing to check names against
    errors: list[str] = []
    for f, text in readable(files, root, errors):
        for name in sorted(named_targets(text)):
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
    for f, text in readable(files, root, errors):
        for word in banned_hits(text):
            errors.append(f"{f.relative_to(root)}: banned word: {word}")
    return errors


def glossary_section(text: str) -> str | None:
    """Body of the glossary section; None if the doc has no glossary."""
    m = _GLOSSARY.search(text)
    return m.group(1) if m else None


def check_glossary(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for f, text in readable(files, root, errors):
        body = glossary_section(text)
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
    code, out = run(["git", "ls-files", "-z"], root)
    return sorted(diff_paths(out)) if code == 0 else []


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


def neutrality_hashes(root: Path) -> tuple[set[str], list[str]]:
    """The listed digests and the lines that are not one (a name, a typo)."""
    path = root / NEUTRALITY_HASHES
    if not path.is_file():
        return set(), [f"{shown(path, root)}: hash file is missing"]
    text, err = read_text_or_error(path, root)
    if text is None:
        return set(), [err]
    digests: set[str] = set()
    errors: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if _SHA256.match(line):
            digests.add(line)
        else:
            errors.append(f"{shown(path, root)}:{n}: not a sha256 hex digest")
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
    code, out = run(["git", "log", f"-{COMMIT_MESSAGES}", "--format=%B"], root)
    return out if code == 0 else ""


def check_neutrality(files: list[Path], digests: set[str], root: Path) -> list[str]:
    errors: list[str] = []
    for f, text in readable(files, root, errors):
        for n, prefix in named_tokens(text, digests):
            rel = f.relative_to(root)
            errors.append(f"{rel}:{n}: names the study's target (sha256 {prefix}…)")
    for n, prefix in named_tokens(commit_messages(root), digests):
        errors.append(
            f"git log (last {COMMIT_MESSAGES} commits), line {n}: names the "
            f"study's target (sha256 {prefix}…)"
        )
    return errors


def check_backlog_count(root: Path) -> list[str]:
    claude, backlog = root / "CLAUDE.md", root / "BACKLOG.md"
    missing = [shown(p, root) for p in (claude, backlog) if not p.is_file()]
    if missing:
        return [f"{name}: record file is missing" for name in missing]
    claude_text, err1 = read_text_or_error(claude, root)
    backlog_text, err2 = read_text_or_error(backlog, root)
    if claude_text is None or backlog_text is None:
        return [e for e in (err1, err2) if e]
    m = _BACKLOG_COUNT.search(claude_text)
    if not m:
        return ["CLAUDE.md: no 'Open BACKLOG rows: **N**' sentence"]
    stated, actual = int(m.group(1)), open_backlog_rows(backlog_text)
    if stated != actual:
        return [f"CLAUDE.md says {stated} open BACKLOG rows; BACKLOG.md has {actual}"]
    return []


def backlog_titles(text: str) -> dict[str, bool]:
    """Row title → open? (a struck first cell is closed)."""
    return {m.group(2): m.group(1) is None for m in _BACKLOG_TITLE.finditer(text)}


def decisions_titles(text: str) -> set[str]:
    """Every bold span and heading outside fenced blocks: the entry titles."""
    body = _FENCE.sub("", text)
    return set(_BOLD.findall(body)) | set(_HEADING.findall(body))


def comment_files(root: Path, paths: list[str]) -> list[Path]:
    """Tracked code the tag check reads: the comment-bearing suffixes and the
    Makefile, minus fixtures/ and data/ (sample pages are not our comments)."""
    return [
        root / p
        for p in paths
        if (p.endswith(COMMENT_SUFFIXES) or Path(p).name in COMMENT_NAMES)
        and not p.startswith(COMMENT_EXCLUDED)
    ]


def _titled(prefix: str, titles: set[str] | dict[str, bool]) -> list[str]:
    """The titles the comment text is a prefix of (a citation is the title's
    start, not a paraphrase)."""
    return [t for t in titles if t.startswith(prefix)]


@dataclasses.dataclass(frozen=True)
class _Records:
    """What a tag may point at, read once per run."""

    backlog_rows: dict[str, bool]
    decisions_titles: set[str]
    specs: Path

    @classmethod
    def read(cls, root: Path) -> tuple[_Records | None, list[str]]:
        """(the records, []) or (None, the error lines of the ones that did not
        read): a record that did not read is never an empty record, which
        would report every tag citing it (LESSONS: empty-default)."""
        backlog, err1 = read_text_or_error(root / "BACKLOG.md", root)
        decisions, err2 = read_text_or_error(root / "DECISIONS.md", root)
        if backlog is None or decisions is None:
            return None, [e for e in (err1, err2) if e]
        return cls(
            backlog_titles(backlog), decisions_titles(decisions), root / "specs"
        ), []


def _cited_error(tag: str, cited: str, records: _Records) -> str | None:
    """The record side of a well-formed tag: the entry it names exists (and,
    for a BACKLOG row, is open)."""
    if tag == "TODO":
        hits = _titled(cited, records.backlog_rows)
        if len(hits) != 1:
            return f"TODO cites no single open BACKLOG row: {cited!r}"
        if not records.backlog_rows[hits[0]]:
            return f"TODO cites a closed BACKLOG row: {cited!r}"
    if tag == "HACK" and len(_titled(cited, records.decisions_titles)) != 1:
        return f"HACK cites no single DECISIONS entry: {cited!r}"
    if tag == "INVARIANT" and not (records.specs / f"{cited}.md").is_file():
        return f"INVARIANT names no spec: specs/{cited}.md"
    return None


def _tag_error(tag: str, rest: str, records: _Records) -> str | None:
    m = _TAG_SHAPES[tag].match(rest)
    if m is None:
        return f"malformed {tag} comment (shape: {_TAG_HELP[tag]})"
    return _cited_error(tag, m.group(1), records) if m.groups() else None


def comments(path: Path, text: str) -> list[tuple[int, str]]:
    """(line, comment body) for every comment in the file: Python's from the
    tokenizer (a string literal is not a comment); the other kinds by line,
    the text after the first opener — a quoted value that begins with a tag
    word is read as a comment, the documented ceiling of a line-based read.
    Raises one of _TOKENIZE_ERRORS."""
    if path.suffix == ".py":
        return [
            (tok.start[0], tok.string[1:])
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type == tokenize.COMMENT
        ]
    opener = _LINE_COMMENT[path.suffix]
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        _, found, body = line.partition(opener)
        if found:
            out.append((n, body))
    return out


# The closed set the tokenizer raises: TokenError (an unterminated statement)
# and SyntaxError's IndentationError/TabError (inconsistent indentation).
_TOKENIZE_ERRORS = (tokenize.TokenError, SyntaxError)


def check_comment_tags(files: list[Path], root: Path) -> list[str]:
    records, errors = _Records.read(root)
    if records is None:
        return errors  # the tags cannot be checked against a record that did not read
    for f, text in readable(files, root, errors):
        try:
            found = comments(f, text)
        except _TOKENIZE_ERRORS as exc:
            errors.append(f"{f.relative_to(root)}: does not tokenize: {exc.args[0]}")
            continue
        for n, body in found:
            m = _TAG_OPENS.match(body)
            if m is None:
                continue
            err = _tag_error(m.group(1), m.group(2), records)
            if err:
                errors.append(f"{f.relative_to(root)}:{n}: {err}")
    return errors


def table_cells(row: str) -> list[str]:
    """A markdown row's cells: split on `|` outside backticks and not escaped
    (`\\|`), so a cited pattern or command in a cell keeps its pipe."""
    cells: list[str] = []
    cell: list[str] = []
    in_code = False
    chars = iter(row.strip().strip("|"))
    for ch in chars:
        if ch == "\\":
            cell.append(next(chars, ""))
        elif ch == "`":
            in_code = not in_code
            cell.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(ch)
    cells.append("".join(cell).strip())
    return cells


def table_rows(text: str) -> list[list[str]]:
    """Cells of every table row after the header and separator (skipped by
    position, as open_backlog_rows does)."""
    rows = [line for line in text.splitlines() if line.startswith("|")]
    return [table_cells(r) for r in rows[2:]]


def check_lessons(root: Path) -> list[str]:
    path = root / "LESSONS.md"
    name = shown(path, root)
    if not path.is_file():
        return [f"{name}: record file is missing"]
    text, err = read_text_or_error(path, root)
    if text is None:
        return [err]
    errors: list[str] = []
    for n, cells in enumerate(table_rows(text), 1):
        if len(cells) != LESSON_CELLS:
            errors.append(f"{name} row {n}: {len(cells)} cells, not {LESSON_CELLS}")
            continue
        if cells[0].strip("`") not in LESSON_CLASSES:
            errors.append(f"{name} row {n}: class not in the closed set: {cells[0]}")
        if not _LESSON_STATUS.match(cells[5]):
            errors.append(f"{name} row {n}: status shape: {cells[5]!r}")
    return errors


def _naming_errors(root: Path) -> list[str]:
    digests, errors = neutrality_hashes(root)
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
        ("BACKLOG count", check_backlog_count(root)),
        ("naming the target", _naming_errors(root)),
        (
            "comment tags",
            check_comment_tags(comment_files(root, tracked_paths(root)), root),
        ),
        ("lessons", check_lessons(root)),
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
