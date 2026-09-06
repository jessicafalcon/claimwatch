#!/usr/bin/env python3
# .claude/hooks/challenge-gate.py — tracked; wired in the gitignored
# .claude/settings.local.json (CLAUDE.md → Project tooling); pinned by
# tests/test_challenge_gate.py. A reminder, never a gate: the only decision it
# ever emits is `ask`.
#
#   PostToolUse (matcher: Write|Edit|MultiEdit|NotebookEdit) — after an edit to
#   a file directly under specs/ named phase-*.md whose status line does not say
#   DELIVERED and which carries no CURRENT stamp (`Challenged: YYYY-MM-DD, round
#   <k>, spec <8 hex> — <verdict>`, unbolded, at line start, the hex being the
#   spec hash of its Invariants and Done-when sections), exit 2 with one line:
#   naming /challenge when there is no stamp, naming the two hashes when the
#   stamp predates those sections. PostToolUse cannot block: the line reaches
#   the model, the edit stands. It fires on every such edit — there is no "once".
#
#   CLI: `python3 .claude/hooks/challenge-gate.py --spec-hash specs/phase-N-x.md`
#   prints the spec hash the main session writes into the stamp. The path is
#   foreign input: it must resolve to a phase spec under ./specs, else exit 2.
#
#   PreToolUse (matcher: ExitPlanMode) — answers `ask` on EVERY plan
#   presentation, with the plan's own claim in the reason: stamped, not
#   stamped, or not readable. The plan text is the model's own, so the hook
#   shows the claim rather than trusting it; the developer decides. The
#   payload shape is undocumented — a missing or non-string `plan` still asks.
#
# Fails OPEN — exit 0, no output — on: a malformed or oversized event, an event
# it does not handle, no CLAUDE_PROJECT_DIR, a path that does not resolve to a
# phase spec directly under <project>/specs (symlinks resolved), a spec it
# cannot read or decode. It is a reminder, not a security control. Reads are
# capped: the event at MAX_EVENT_BYTES (the harness is the producer; a bigger
# event is not one we recognise) and the spec at MAX_SPEC_BYTES (the hashed
# sections can sit anywhere in it).
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Literal, NoReturn

MAX_EVENT_BYTES = 4 * 1024 * 1024
MAX_SPEC_BYTES = 1024 * 1024
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SPEC_NAME = re.compile(r"^phase-[0-9]+[a-z]?-[a-z0-9-]+\.md$")
STATUS = re.compile(r"^\*\*Status: (?P<rest>[^\n]*)$", re.M)
STAMP = re.compile(
    r"^Challenged: (?P<date>\d{4}-\d{2}-\d{2}), round \d+, "
    r"spec (?P<hash>[0-9a-f]{8}) — ",
    re.M,
)
# The sections a challenge judges: a change to either is a new plan.
HASHED_SECTIONS = ("## Invariants", "## Done-when")
_SECTION = re.compile(r"^## .*$", re.M)


def _section(text: str, title: str) -> str:
    """The section from its `## <title>` heading line up to the next `## `
    heading, trailing whitespace stripped per line; "" when absent."""
    starts = [m for m in _SECTION.finditer(text) if m.group(0).startswith(title)]
    if not starts:
        return ""
    start = starts[0].start()
    nxt = _SECTION.search(text, starts[0].end())
    body = text[start : nxt.start() if nxt else len(text)]
    return "\n".join(line.rstrip() for line in body.splitlines())


def spec_hash(text: str) -> str:
    """Eight hex of sha256 over the Invariants and Done-when sections."""
    joined = "\n\x00\n".join(_section(text, t) for t in HASHED_SECTIONS)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def _stamp_hash(text: str) -> str | None:
    """The stamp's hash when a full stamp with a real calendar date sits at
    line start; None otherwise."""
    m = STAMP.search(text)
    if m is None:
        return None
    try:
        dt.date.fromisoformat(m.group("date"))
    except ValueError:
        return None
    return m.group("hash")


def stamp_state(text: str) -> Literal["none", "stale", "current"]:
    stamped = _stamp_hash(text)
    if stamped is None:
        return "none"
    return "current" if stamped == spec_hash(text) else "stale"


def _delivered(text: str) -> bool:
    m = STATUS.search(text)
    return m is not None and "DELIVERED" in m.group("rest")


def _spec_text(path: Path) -> str | None:
    """The whole spec, or None when unreadable, not UTF-8, or over the cap."""
    try:
        with path.open("rb") as fh:
            raw = fh.read(MAX_SPEC_BYTES + 1)
        if len(raw) > MAX_SPEC_BYTES:
            return None
        return raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def _spec_reminder(path: Path, root: Path) -> NoReturn:
    text = _spec_text(path)
    if text is None or _delivered(text):
        sys.exit(0)
    state = stamp_state(text)
    if state == "current":
        sys.exit(0)
    rel = path.relative_to(root)
    if state == "none":
        line = (
            f"[challenge-gate] {rel} is not yet challenged — run `/challenge {rel}` "
            "before asking for approval."
        )
    else:
        line = (
            f"[challenge-gate] {rel}: the Challenged stamp (spec "
            f"{_stamp_hash(text)}) predates its Invariants or Done-when (spec "
            f"{spec_hash(text)}) — run `/challenge {rel}` again, or restamp."
        )
    print(line, file=sys.stderr)
    sys.exit(2)


def _plan_gate(tool_input: dict[str, object]) -> NoReturn:
    plan = tool_input.get("plan")
    if not isinstance(plan, str):
        claim = "the hook cannot read this plan's text"
    elif _stamp_hash(plan) is not None:
        claim = "the plan text says it was challenged — check the stamp is real"
    else:
        claim = "the plan carries no `Challenged:` stamp"
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                f"challenge-gate: {claim}. Present it anyway, or run /challenge first."
            ),
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def _event() -> dict[str, object] | None:
    """The event is an input this repo does not own: one shape, else None."""
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            return None
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        return None
    return data


def _spec_path(tool_input: dict[str, object], root: Path) -> Path | None:
    """The edited file, only when it resolves to <root>/specs/phase-*.md."""
    fp = tool_input.get("file_path")
    if not isinstance(fp, str) or not fp:
        return None
    try:
        path = Path(fp).resolve(strict=True)
        specs = (root / "specs").resolve(strict=True)
    except OSError:
        return None
    if path.parent != specs or not SPEC_NAME.match(path.name):
        return None
    return path


def _print_spec_hash(arg: str) -> NoReturn:
    """`--spec-hash <path>`: the path must resolve to a phase spec under
    ./specs; the hash is printed alone so a stamp can be written from it."""
    path = _spec_path({"file_path": arg}, Path.cwd())
    text = _spec_text(path) if path is not None else None
    if text is None:
        print(
            "challenge-gate: --spec-hash takes a phase spec under ./specs",
            file=sys.stderr,
        )
        sys.exit(2)
    print(spec_hash(text))
    sys.exit(0)


def main() -> NoReturn:
    if len(sys.argv) == 3 and sys.argv[1] == "--spec-hash":
        _print_spec_hash(sys.argv[2])
    if len(sys.argv) != 1:
        print(
            "challenge-gate: usage: --spec-hash <specs/phase-N-slug.md>",
            file=sys.stderr,
        )
        sys.exit(2)
    data = _event()
    if data is None:
        sys.exit(0)
    event, tool = data.get("hook_event_name"), data.get("tool_name")
    ti = data["tool_input"]
    assert isinstance(ti, dict)  # _event checked it; this keeps the type narrow

    if event == "PreToolUse" and tool == "ExitPlanMode":
        _plan_gate(ti)

    root_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if event == "PostToolUse" and tool in EDIT_TOOLS and root_env:
        try:
            root = Path(root_env).resolve(strict=True)
        except OSError:
            sys.exit(0)
        path = _spec_path(ti, root)
        if path is not None:
            _spec_reminder(path, root)

    sys.exit(0)


if __name__ == "__main__":
    main()
