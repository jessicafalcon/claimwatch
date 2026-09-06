"""Pins for .claude/hooks/ask-gate.py: an `ask` — and only ever an `ask` —
before a Bash command whose segment starts a push, a PR, a merge or a
`confirm`-armed target; silence for everything else and for every malformed
event. Spawned the way Claude Code spawns it. Offline; writes nothing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "ask-gate.py"


def _hook(stdin: str | bytes) -> subprocess.CompletedProcess[bytes]:
    data = stdin.encode() if isinstance(stdin, str) else stdin
    return subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True)


def _bash(command: object, tool: str = "Bash", event: str = "PreToolUse") -> str:
    return json.dumps(
        {
            "hook_event_name": event,
            "tool_name": tool,
            "tool_input": {"command": command},
        }
    )


def _asks(res: subprocess.CompletedProcess[bytes]) -> str:
    assert res.returncode == 0 and res.stderr == b"", res
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "ask"
    return out["permissionDecisionReason"]


def _quiet(res: subprocess.CompletedProcess[bytes]) -> None:
    assert res.returncode == 0 and res.stdout == b"" and res.stderr == b"", res


def test_each_stop_asks_with_its_reason():
    assert "STOP 3" in _asks(_hook(_bash("git push origin HEAD")))
    assert "STOP 3" in _asks(_hook(_bash("git push --force-with-lease")))
    assert "PR opens" in _asks(_hook(_bash("gh pr create --title x")))
    assert "merges" in _asks(_hook(_bash("gh pr merge 12 --squash")))
    assert "STOP 4" in _asks(_hook(_bash("make confirm reset")))
    assert "STOP 4" in _asks(_hook(_bash("make -j2 confirm scrape")))


def test_a_stop_inside_a_compound_command_still_asks():
    for cmd in (
        "cd /x && git push",
        "make test; make confirm fetch-damir",
        "git status || gh pr create",
        "git log | head\ngit push",
        "  git push",
    ):
        assert _asks(_hook(_bash(cmd))), cmd


def test_everything_else_is_silent():
    for cmd in (
        "git status",
        "git push-notes",  # not the push subcommand
        "gh pr view 12",
        "make test && make review-gate",
        "make reset",  # unarmed: the Makefile's own gate refuses it
        "echo 'git push'",  # the words inside an argument, not a segment head
        "grep -n 'make confirm' CLAUDE.md",
        "",
    ):
        _quiet(_hook(_bash(cmd)))


def test_other_tools_events_and_malformed_input_fail_open():
    for stdin in (
        _bash("git push", tool="Edit"),
        _bash("git push", event="PostToolUse"),
        _bash(7),
        _bash(None),
        json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash"}),
        json.dumps({"tool_input": "git push"}),
        json.dumps([1]),
        "not json",
        "",
        b"\xff\xfe",
        (" " * (1024 * 1024)) + _bash("git push"),  # over MAX_EVENT_BYTES
    ):
        res = _hook(stdin)
        assert res.returncode == 0 and b"Traceback" not in res.stderr, stdin[:40]
        _quiet(res)


def test_the_hook_never_emits_allow_or_deny():
    for cmd in ("git push", "git status", "make confirm reset", "x"):
        out = _hook(_bash(cmd)).stdout
        assert b'"allow"' not in out and b'"deny"' not in out, cmd
