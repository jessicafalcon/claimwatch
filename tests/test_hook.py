"""Pins for .claude/hooks/run-tests.py: fails open where documented, blocks on
a red or hung suite. The hook is spawned the way Claude Code spawns it (the
event as JSON on stdin, CLAUDE_PROJECT_DIR in the env) against a tmp project
holding one test file. Offline; the only network is none."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "run-tests.py"
VENV_BIN = str(Path(sys.executable).parent)  # pytest on PATH for the tmp project
RED = "def test_bad():\n    assert False\n"
GREEN = "def test_ok():\n    assert True\n"


def _hook(stdin: str, project: Path | None) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": VENV_BIN + os.pathsep + os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def _project(tmp_path: Path, body: str) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(body)
    return tmp_path


def _event(project: Path, name: str = "tests/test_x.py") -> str:
    return json.dumps({"tool_input": {"file_path": str(project / name)}})


def test_green_suite_exits_0(tmp_path: Path):
    p = _project(tmp_path, GREEN)
    res = _hook(_event(p), p)
    assert res.returncode == 0 and "tests green" in res.stderr


def test_red_suite_blocks_with_exit_2_and_the_tail(tmp_path: Path):
    p = _project(tmp_path, RED)
    res = _hook(_event(p), p)
    assert res.returncode == 2
    assert "TESTS FAILING" in res.stderr and "test_bad" in res.stderr


def test_sql_and_yaml_edits_run_the_suite(tmp_path: Path):
    p = _project(tmp_path, RED)
    for name in ("sql/marts/x.sql", "classify/rules.yaml", "ci.yml"):
        assert _hook(_event(p, name), p).returncode == 2, name


def test_non_code_and_outside_files_are_skipped(tmp_path: Path):
    p = _project(tmp_path, RED)  # red, but never run
    res = _hook(_event(p, "CLAUDE.md"), p)
    assert res.returncode == 0 and res.stderr == ""
    outside = json.dumps({"tool_input": {"file_path": "/elsewhere/repo/x.py"}})
    assert _hook(outside, p).returncode == 0


def test_malformed_input_fails_open(tmp_path: Path):
    p = _project(tmp_path, RED)
    shapes = (
        "not json",
        "",
        json.dumps([1, 2]),
        json.dumps({"tool_input": "a string"}),
        json.dumps({"tool_input": {"file_path": 7}}),
        json.dumps({"tool_input": {}}),
    )
    for bad in shapes:
        res = _hook(bad, p)
        assert res.returncode == 0 and "Traceback" not in res.stderr, bad
    assert _hook(_event(p), None).returncode == 0  # no CLAUDE_PROJECT_DIR
