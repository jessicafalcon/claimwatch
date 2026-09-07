"""Shared by scripts/review_gate.py, check_pins.py, check_docs.py and
check_backing.py (not a pytest file). One spec-path validator, one base-rev
validator, one diff-path reader, one section parser, one subprocess runner,
one file reader, one Makefile-target reader. Stdlib only.

The read boundary: every file a script reads and every subprocess it runs
goes through `read_text_or_error` / `readable` and `run` here, so a file that
is not UTF-8 text, a path that cannot be read or output that does not decode
is one line naming the input, never a traceback — the class, not the site
(LESSONS: traceback-at-boundary, site-fix). A grep test pins that no other
module under scripts/ reads or spawns on its own."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A git rev used as an argv token: a safe charset and never a leading `-`.
_BASE = re.compile(r"^[\w./-]+$")

# A target is DECLARED by a rule line `name:` at column 0 (not `.PHONY`).
# `x:= v` and `x::= v` are assignments, not targets; `x::` (a double-colon rule) is one.
_TARGET_LINE = re.compile(r"^([a-z][a-z0-9-]*):(?!:?=)", re.M)
# A `make` target NAMED in backticks — the one regex check_docs and the gate share.
MAKE_TICK = re.compile(r"`make ([a-z][a-z0-9-]*)[^`]*`")
# Document classes (check_docs.py explains them); the gate's record files build on them.
LIVING_DOCS = ("CLAUDE.md", "README.md", "SPEC.md", "BACKING.md")
RECORD_DOCS = ("DECISIONS.md", "BACKLOG.md", "LESSONS.md")


class Refused(Exception):
    """A one-line refusal: printed as-is, exit 2, never a traceback."""


def die(exc: Refused) -> None:
    print(str(exc), file=sys.stderr)
    sys.exit(2)


def resolve_spec(arg: str, root: Path = ROOT) -> Path:
    """`--spec` must name an existing FILE under `<root>/specs/`; nothing else is
    derived from it. Empty, absolute, `../x`, a directory, or anything outside
    specs/ is refused."""
    if not arg or not arg.strip():
        raise Refused("refusing: SPEC is empty (usage: SPEC=specs/<file>.md)")
    if Path(arg).is_absolute():
        raise Refused(f"refusing: SPEC must be a path under specs/, got {arg!r}")
    specs = (root / "specs").resolve()
    target = (root / arg).resolve()
    if specs not in target.parents:
        raise Refused(f"refusing: SPEC must be a path under specs/, got {arg!r}")
    if not target.is_file():
        raise Refused(f"refusing: SPEC is not an existing file: {arg!r}")
    return target


def resolve_base(arg: str) -> str:
    """`--base` is a git rev used as an argv token: a safe charset and never a
    leading `-` (git would read it as an option). Refused, never a traceback."""
    if not arg or not _BASE.match(arg) or arg.startswith("-"):
        raise Refused(f"refusing: BASE must be a plain git rev, got {arg!r}")
    return arg


def diff_paths(out: str) -> set[str]:
    """Paths from `git diff -z --name-only`: NUL-separated, read whole — a
    space, a quote or a non-ASCII letter never splits or hides a path."""
    return {p for p in out.split("\0") if p}


def section(text: str, heading: str) -> str:
    """Body of the first `## <heading>…` section (heading matched as a prefix, so
    `Evidence (REQUIRED)` is found by `Evidence`); '' if absent."""
    m = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run `cmd`, capture stdout+stderr merged, never raise: a non-zero exit is
    returned, a missing executable is (127, one line), output that is not
    UTF-8 text is (1, one line) — never a traceback."""
    try:
        res = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except UnicodeDecodeError:
        return 1, f"output of {cmd[0]} is not UTF-8 text"
    return res.returncode, res.stdout + res.stderr


def _shown(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def read_text_or_error(path: Path, root: Path = ROOT) -> tuple[str | None, str | None]:
    """(text, None) or (None, one error line naming the path): a file that is
    not UTF-8 text or cannot be read is reported, never raised."""
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, f"{_shown(path, root)}: not UTF-8 text"
    except OSError as exc:
        return None, f"{_shown(path, root)}: cannot be read: {exc.strerror}"


def readable(
    files: list[Path], root: Path, errors: list[str]
) -> Iterator[tuple[Path, str]]:
    """Yield (file, text) for every file that reads; an unreadable one adds
    its error line to `errors` and is skipped, so a per-file check goes on."""
    for f in files:
        text, err = read_text_or_error(f, root)
        if text is None:
            errors.append(err or f"{_shown(f, root)}: cannot be read")
            continue
        yield f, text


def make_targets(root: Path = ROOT) -> set[str]:
    """Targets the Makefile declares (rule lines), read as text — never `make -n`;
    an unreadable Makefile declares nothing (the caller's check then fails by name)."""
    text, _ = read_text_or_error(root / "Makefile", root)
    return set(_TARGET_LINE.findall(text)) if text is not None else set()


def tail(text: str, n: int = 20) -> str:
    return "\n".join(text.splitlines()[-n:])
