"""Shared by scripts/review_gate.py, check_docs.py and check_backing.py (not a
pytest file). One spec-path validator, one section parser, one subprocess
runner, one Makefile-target reader. Stdlib only."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A target is DECLARED by a rule line `name:` at column 0 (not `.PHONY`).
_TARGET_LINE = re.compile(r"^([a-z][a-z0-9-]*):(?!=)", re.M)  # `x := v` is not a target


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


def section(text: str, heading: str) -> str:
    """Body of the first `## <heading>…` section (heading matched as a prefix, so
    `Evidence (REQUIRED)` is found by `Evidence`); '' if absent."""
    m = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run `cmd`, capture stdout+stderr merged, never raise: a non-zero exit is
    returned, a missing executable is (127, one line) — never a traceback."""
    try:
        res = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    return res.returncode, res.stdout + res.stderr


def make_targets(root: Path = ROOT) -> set[str]:
    """Targets the Makefile declares (rule lines), read as text — never `make -n`."""
    makefile = root / "Makefile"
    if not makefile.is_file():
        return set()
    return set(_TARGET_LINE.findall(makefile.read_text(encoding="utf-8")))


def tail(text: str, n: int = 20) -> str:
    return "\n".join(text.splitlines()[-n:])
