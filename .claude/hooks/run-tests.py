#!/usr/bin/env python3
# .claude/hooks/run-tests.py
# PostToolUse hook (matcher: Write|Edit|MultiEdit|NotebookEdit) — runs pytest
# after a .py, .sql, .yaml or .yml file in this project changes. SQL files
# and rules.yaml are code here. Makes a broken test VISIBLE the instant it breaks.
#
# This gate deliberately fails OPEN — exit 0, no run — in exactly four cases:
# a malformed event, no CLAUDE_PROJECT_DIR in the environment, a project dir
# it cannot chdir into, and no pytest on the venv or PATH. It is a visibility
# aid, not a security control. A red suite blocks (exit 2) and so does a hung
# one: the timeout is RUN_TESTS_TIMEOUT seconds (digits only, default 120) —
# silence there would hide a real problem. Don't "fix" the open cases into
# fail-closed — that would block all edits on a broken venv.
#
# Wiring is LOCAL-ONLY, in the gitignored .claude/settings.local.json (see
# CLAUDE.md → Project tooling). A tracked settings.json would auto-execute an
# inbound branch's hook for anyone opening the repo.
import json
import os
import subprocess
import sys

CODE_SUFFIXES = (".py", ".sql", ".yaml", ".yml")
DEFAULT_TIMEOUT = 120


def timeout_seconds() -> int:
    """RUN_TESTS_TIMEOUT is foreign input: digits only, else the default."""
    raw = os.environ.get("RUN_TESTS_TIMEOUT", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_TIMEOUT


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        sys.exit(0)

    # The event is an input this repo does not own: parse it to the one shape
    # we act on (a dict with a dict tool_input carrying a str file_path) and
    # fail OPEN on anything else — never a traceback.
    if not isinstance(data, dict):
        sys.exit(0)
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        sys.exit(0)
    fp = ti.get("file_path")
    if not isinstance(fp, str) or not fp.lower().endswith(CODE_SUFFIXES):
        sys.exit(0)  # not code — skip silently; only "tests green" means "ran"

    root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not root:
        sys.exit(0)
    # Only react to files inside THIS project — an edit in a sibling repo would
    # otherwise produce a misleading green from a suite that never covers it.
    if not os.path.abspath(fp).startswith(os.path.abspath(root) + os.sep):
        sys.exit(0)
    try:
        os.chdir(root)
    except OSError:
        sys.exit(0)

    venv_pytest = os.path.join(".venv", "bin", "pytest")
    if os.path.exists(venv_pytest):
        cmd = [venv_pytest]  # pyproject already sets addopts="-q"
    else:
        from shutil import which

        if which("pytest"):
            cmd = ["pytest"]
        else:
            print(
                "[run-tests] pytest not found yet — run `make setup`.", file=sys.stderr
            )
            sys.exit(0)

    # Reduced environment: PATH and HOME only. This keeps ENVIRONMENT credentials
    # (an .env-loaded API key) out of the suite and nothing else — the tests still
    # run as you, with your HOME (CLAUDE.md → Project tooling states the risk).
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    limit = timeout_seconds()
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=limit, check=False, env=env
        )
    except subprocess.TimeoutExpired:
        print(
            f"[run-tests] suite timed out ({limit}s) after editing {fp}.",
            file=sys.stderr,
        )
        sys.exit(2)
    # pytest exit code 5 = "no tests collected" — an early repo, not a failure.
    if res.returncode == 5:
        sys.exit(0)
    if res.returncode != 0:
        print(f"[run-tests] TESTS FAILING after editing {fp}:", file=sys.stderr)
        print("\n".join((res.stdout + res.stderr).splitlines()[-15:]), file=sys.stderr)
        sys.exit(2)

    print(f"[run-tests] tests green after {fp}.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
