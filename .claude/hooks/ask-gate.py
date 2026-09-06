#!/usr/bin/env python3
# .claude/hooks/ask-gate.py — tracked; wired in the gitignored
# .claude/settings.local.json (CLAUDE.md → Project tooling); pinned by
# tests/test_ask_gate.py.
#
#   PreToolUse (matcher: Bash) — the STOPs that wait for the developer's word
#   (CLAUDE.md → Working with the model: a push or a PR, a destructive or
#   network target, a merge) become a permission prompt instead of a sentence
#   the model has to remember. Every segment of the command (split on &&, ||,
#   ;, | and newlines) is matched against a CLOSED set of prefixes; a hit
#   answers `ask` with the STOP's reason. `ask` is the only decision it ever
#   emits — never `allow`, never `deny`: the developer decides at the prompt.
#
# Fails OPEN — exit 0, no output — on a malformed or oversized event, another
# tool, or a command that is not a string. A reminder, not a security control:
# a command that reaches the same target another way (a script, `sh -c`) is
# not caught, and the `confirm` goal's own gate in the Makefile still holds.
from __future__ import annotations

import json
import re
import sys
from typing import NoReturn

MAX_EVENT_BYTES = 1024 * 1024
_SEGMENT = re.compile(r"&&|\|\||;|\||\n")
# (pattern anchored at the segment's start, the reason the prompt shows)
STOPS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"git\s+push(?=\s|$)"),
        "STOP 3: push only after the review verdicts are approved.",
    ),
    (
        re.compile(r"gh\s+pr\s+create(?=\s|$)"),
        "STOP 3: a PR opens only on the developer's word.",
    ),
    (
        re.compile(r"gh\s+pr\s+merge(?=\s|$)"),
        "the developer merges (squash), never Claude.",
    ),
    (
        re.compile(r"make(?:\s+\S+)*\s+confirm(?=\s|$)"),
        "STOP 4: a destructive or network target; the developer runs it.",
    ),
)


def stop_reason(command: str) -> str | None:
    """The first STOP a segment of the command starts with, else None."""
    for segment in _SEGMENT.split(command):
        head = segment.strip()
        for pattern, reason in STOPS:
            if pattern.match(head):
                return reason
    return None


def _event() -> dict[str, object] | None:
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


def main() -> NoReturn:
    data = _event()
    if data is None or data.get("tool_name") != "Bash":
        sys.exit(0)
    if data.get("hook_event_name") != "PreToolUse":
        sys.exit(0)
    tool_input = data["tool_input"]
    assert isinstance(tool_input, dict)  # _event checked it
    command = tool_input.get("command")
    reason = stop_reason(command) if isinstance(command, str) else None
    if reason is None:
        sys.exit(0)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"ask-gate: {reason}",
        }
    }
    print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
