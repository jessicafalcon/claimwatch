"""Pins for .claude/hooks/challenge-gate.py: a reminder after an edit to an
unstamped, undelivered phase spec; an `ask` — and only ever an `ask` — before
ExitPlanMode; the documented fail-open cases. Spawned the way Claude Code
spawns it (the event as JSON on stdin, CLAUDE_PROJECT_DIR in the env) against
a tmp project. Offline; the hook reads one file head and writes nothing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "challenge-gate.py"
PROPOSED = "# Phase 9 — study\n\n**Status: PROPOSED — do not start until approved.**\n"
APPROVED = "# Phase 9 — study\n\n**Status: APPROVED 2026-09-06 — in progress.**\n"
DELIVERED = (
    "# Phase 9 — study\n\n"
    "**Status: APPROVED 2026-09-06 — DELIVERED 2026-09-20, PR open.**\n"
)
STAMP = "Challenged: 2026-09-05, round 1 — approve with amendments\n"
NOT_STAMPS = (
    "Challenged by a reviewer, informally.\n",
    "Challenged: 2026-09-05\n",  # date only, no round and verdict
    "Challenged: 9999-99-99, round 1 — approve\n",  # not a calendar date
    "**Challenged: 2026-09-05, round 1 — approve**\n",  # bolded
    "  Challenged: 2026-09-05, round 1 — approve\n",  # not at line start
)


def _hook(
    stdin: str | bytes, project: Path | None
) -> subprocess.CompletedProcess[bytes]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    data = stdin.encode() if isinstance(stdin, str) else stdin
    return subprocess.run(
        [sys.executable, str(HOOK)], input=data, capture_output=True, env=env
    )


def _spec(tmp_path: Path, body: str | bytes, name: str = "phase-9-study.md") -> Path:
    (tmp_path / "specs").mkdir(exist_ok=True)
    path = tmp_path / "specs" / name
    path.write_bytes(body.encode() if isinstance(body, str) else body)
    return path


def _edit(path: Path | str, tool: str = "Edit", event: str = "PostToolUse") -> str:
    return json.dumps(
        {
            "hook_event_name": event,
            "tool_name": tool,
            "tool_input": {"file_path": str(path)},
        }
    )


def _plan(plan: object, tool: str = "ExitPlanMode") -> str:
    ti = {} if plan is None else {"plan": plan}
    return json.dumps(
        {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti}
    )


def _quiet(res: subprocess.CompletedProcess[bytes]) -> None:
    assert res.returncode == 0 and res.stderr == b"" and res.stdout == b""


def _reminds(res: subprocess.CompletedProcess[bytes]) -> None:
    assert res.returncode == 2, res
    assert b"/challenge specs/phase-9-study.md" in res.stderr
    assert b"Traceback" not in res.stderr and res.stdout == b""


def test_unstamped_undelivered_spec_edit_reminds_whatever_its_status(tmp_path: Path):
    for body in (PROPOSED, APPROVED, "# a spec with no status line\n"):
        _reminds(_hook(_edit(_spec(tmp_path, body)), tmp_path))
    for tool in ("Write", "MultiEdit", "NotebookEdit"):
        _reminds(_hook(_edit(_spec(tmp_path, PROPOSED), tool=tool), tmp_path))


def test_a_full_stamp_or_a_delivered_status_is_quiet(tmp_path: Path):
    _quiet(_hook(_edit(_spec(tmp_path, PROPOSED + STAMP)), tmp_path))
    _quiet(_hook(_edit(_spec(tmp_path, APPROVED + STAMP)), tmp_path))
    _quiet(_hook(_edit(_spec(tmp_path, DELIVERED)), tmp_path))


def test_only_the_declared_stamp_shape_counts(tmp_path: Path):
    """The stamp is a closed shape: `Challenged: <date>, round <k> — …` at
    line start, unbolded, a real calendar date. Anything else still reminds."""
    for not_stamp in NOT_STAMPS:
        _reminds(_hook(_edit(_spec(tmp_path, PROPOSED + not_stamp)), tmp_path))


def test_files_that_are_not_phase_specs_directly_under_specs_are_skipped(
    tmp_path: Path,
):
    for name in ("TEMPLATE.md", "notes.md", "phase-9.md", "phase-9-study.txt"):
        _quiet(_hook(_edit(_spec(tmp_path, PROPOSED, name)), tmp_path))
    nested = tmp_path / "specs" / "sub"
    nested.mkdir()
    (nested / "phase-9-study.md").write_text(PROPOSED)
    _quiet(_hook(_edit(nested / "phase-9-study.md"), tmp_path))
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "phase-9-study.md").write_text(PROPOSED)
    _quiet(_hook(_edit(docs / "phase-9-study.md"), tmp_path))
    _quiet(_hook(_edit("/elsewhere/repo/specs/phase-9-study.md"), tmp_path))
    sibling = tmp_path / "specs-other"
    sibling.mkdir()
    (sibling / "phase-9-study.md").write_text(PROPOSED)
    _quiet(_hook(_edit(sibling / "phase-9-study.md"), tmp_path))


def test_a_symlink_under_specs_is_resolved_not_followed(tmp_path: Path):
    outside = tmp_path / "outside.md"
    outside.write_text(PROPOSED)
    (tmp_path / "specs").mkdir()
    link = tmp_path / "specs" / "phase-9-study.md"
    link.symlink_to(outside)
    _quiet(_hook(_edit(link), tmp_path))
    # A `..` path that normalises back under specs/ is still a spec.
    real = _spec(tmp_path, PROPOSED, "phase-8-cost.md")
    dotted = tmp_path / "specs" / ".." / "specs" / "phase-8-cost.md"
    res = _hook(_edit(dotted), tmp_path)
    assert res.returncode == 2 and b"specs/phase-8-cost.md" in res.stderr
    assert real.is_file()


def test_a_spec_the_hook_cannot_decode_or_read_fails_open(tmp_path: Path):
    _quiet(_hook(_edit(_spec(tmp_path, b"# spec \xff\xfe not utf-8\n")), tmp_path))
    _reminds(_hook(_edit(_spec(tmp_path, "")), tmp_path))  # empty = a new spec
    gone = tmp_path / "specs" / "phase-9-gone.md"
    _quiet(_hook(_edit(gone), tmp_path))  # no such file
    directory = tmp_path / "specs" / "phase-9-dir.md"
    directory.mkdir()
    _quiet(_hook(_edit(directory), tmp_path))


def test_plan_gate_always_asks_and_names_the_plans_claim(tmp_path: Path):
    cases: list[tuple[object, bytes]] = [
        ("# Plan\n1. build B3.3\n", b"no `Challenged:` stamp"),
        ("# Plan\n" + STAMP, b"says it was challenged"),
        (None, b"cannot read this plan"),
        (7, b"cannot read this plan"),
        (["a"], b"cannot read this plan"),
    ]
    for plan, expected in cases:
        res = _hook(_plan(plan), tmp_path)
        assert res.returncode == 0 and res.stderr == b"", plan
        out = json.loads(res.stdout)["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse"
        assert out["permissionDecision"] == "ask"
        assert expected in out["permissionDecisionReason"].encode(), plan


def test_plan_gate_asks_without_a_project_dir(tmp_path: Path):
    res = _hook(_plan("# Plan\n"), None)
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_the_hook_never_emits_allow_or_deny():
    """Across every input shape this file exercises, the only decision word in
    the hook's stdout is `ask` — the closed set a reminder may use."""
    inputs = [_plan(p) for p in ("x", "# Plan\n" + STAMP, None, 7)]
    inputs += [
        _plan("x", tool="Bash"),
        _edit("/x/specs/phase-9-study.md"),
        "not json",
        "",
    ]
    for stdin in inputs:
        out = _hook(stdin, None).stdout
        assert b'"allow"' not in out and b'"deny"' not in out, stdin


def test_malformed_oversized_or_foreign_events_fail_open(tmp_path: Path):
    spec = _spec(tmp_path, PROPOSED)
    shapes: list[str | bytes] = [
        "not json",
        "",
        json.dumps([1, 2]),
        json.dumps(
            {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": "s"}
        ),
        json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "ExitPlanMode",
                "tool_input": [],
            }
        ),
        json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": 7},
            }
        ),
        json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": ""},
            }
        ),
        json.dumps({"hook_event_name": "Stop", "tool_name": "Edit", "tool_input": {}}),
        _edit(spec, tool="Bash"),
        _edit(spec, event="PreToolUse"),
        b"\xff\xfe" + _edit(spec).encode(),
        (" " * (4 * 1024 * 1024)) + _edit(spec),  # over MAX_EVENT_BYTES
    ]
    for bad in shapes:
        res = _hook(bad, tmp_path)
        assert res.returncode == 0 and b"Traceback" not in res.stderr, bad[:60]
        assert res.stderr == b"", bad[:60]
    _quiet(_hook(_edit(spec), None))  # no CLAUDE_PROJECT_DIR
    _quiet(_hook(_edit(spec), tmp_path / "gone"))  # a project dir that does not exist
