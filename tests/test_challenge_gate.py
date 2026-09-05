"""Pins for .claude/hooks/challenge-gate.py: a reminder after an unstamped
PROPOSED spec edit, an `ask` before ExitPlanMode on an unstamped plan, and the
documented fail-open cases. Spawned the way Claude Code spawns it (the event
as JSON on stdin, CLAUDE_PROJECT_DIR in the env) against a tmp project.
Offline; the hook reads one file and writes nothing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "challenge-gate.py"
PROPOSED = "# Phase 9 — study\n\n**Status: PROPOSED — do not start until approved.**\n"
STAMP = "\nChallenged: 2026-09-05, round 1 — approve with amendments\n"


def _hook(stdin: str, project: Path | None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _spec(tmp_path: Path, body: str, name: str = "phase-9-study.md") -> Path:
    (tmp_path / "specs").mkdir(exist_ok=True)
    path = tmp_path / "specs" / name
    path.write_text(body)
    return path


def _edit(path: Path, tool: str = "Edit") -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": str(path)},
        }
    )


def _plan(plan: object) -> str:
    ti = {} if plan is None else {"plan": plan}
    return json.dumps(
        {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "tool_input": ti}
    )


def test_unstamped_proposed_spec_edit_reminds_with_exit_2(tmp_path: Path):
    spec = _spec(tmp_path, PROPOSED)
    res = _hook(_edit(spec), tmp_path)
    assert res.returncode == 2
    assert "/challenge specs/phase-9-study.md" in res.stderr
    assert "Traceback" not in res.stderr


def test_stamped_or_approved_spec_edit_is_quiet(tmp_path: Path):
    stamped = _spec(tmp_path, PROPOSED + STAMP)
    _quiet(_hook(_edit(stamped), tmp_path))
    approved = _spec(tmp_path, PROPOSED.replace("PROPOSED — do not start", "APPROVED"))
    res = _hook(_edit(approved), tmp_path)
    assert res.returncode == 0 and res.stderr == ""


def _quiet(res: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert res.returncode == 0 and res.stderr == "" and res.stdout == ""
    return res


def test_files_that_are_not_phase_specs_are_skipped(tmp_path: Path):
    for name in ("TEMPLATE.md", "notes.md", "phase-9.md"):
        _quiet(_hook(_edit(_spec(tmp_path, PROPOSED, name)), tmp_path))
    elsewhere = tmp_path / "docs"
    elsewhere.mkdir()
    (elsewhere / "phase-9-study.md").write_text(PROPOSED)
    _quiet(_hook(_edit(elsewhere / "phase-9-study.md"), tmp_path))
    outside = json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/elsewhere/repo/specs/phase-9-study.md"},
        }
    )
    _quiet(_hook(outside, tmp_path))


def test_unstamped_plan_asks_once_and_a_stamped_plan_passes(tmp_path: Path):
    res = _hook(_plan("# Plan\n1. build B3.3\n"), tmp_path)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    decision = out["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "ask"
    assert "/challenge" in decision["permissionDecisionReason"]
    _quiet(_hook(_plan("# Plan\n" + STAMP), tmp_path))


def test_unknown_plan_shape_fails_open(tmp_path: Path):
    """The ExitPlanMode payload is undocumented: no `plan` string means no gate."""
    for plan in (None, 7, ["a"], {"text": "x"}):
        _quiet(_hook(_plan(plan), tmp_path))


def test_malformed_input_and_missing_project_dir_fail_open(tmp_path: Path):
    spec = _spec(tmp_path, PROPOSED)
    shapes = (
        "not json",
        "",
        json.dumps([1, 2]),
        json.dumps({"hook_event_name": "PostToolUse", "tool_input": "a string"}),
        json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": 7},
            }
        ),
        json.dumps({"hook_event_name": "Stop", "tool_name": "Edit", "tool_input": {}}),
        _edit(spec, tool="Bash"),
    )
    for bad in shapes:
        res = _hook(bad, tmp_path)
        assert res.returncode == 0 and "Traceback" not in res.stderr, bad
    _quiet(_hook(_edit(spec), None))  # no CLAUDE_PROJECT_DIR
    gone = tmp_path / "gone" / "specs" / "phase-9-study.md"
    res = _hook(_edit(gone), tmp_path / "gone")
    assert res.returncode == 0 and "Traceback" not in res.stderr
