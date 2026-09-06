#!/usr/bin/env python3
# .claude/hooks/run-tests.py
# PostToolUse hook (matcher: Write|Edit|MultiEdit|NotebookEdit) — runs pytest
# after a .py, .sql, .yaml or .yml file in this project changes. SQL files
# and rules.yaml are code here. Makes a broken test VISIBLE the instant it breaks.
# Runs failures-first and stops at the first (FAST_RED), so red is fast.
#
# This gate deliberately fails OPEN — exit 0, no run — in exactly four cases:
# a malformed or oversized event, no CLAUDE_PROJECT_DIR in the environment, a
# project dir it cannot chdir into, and no pytest on the venv or PATH. It is a
# visibility aid, not a security control. A red suite blocks (exit 2) and so
# does a hung
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
MAX_EVENT_BYTES = 4 * 1024 * 1024  # the harness is the producer; bigger is not ours
# Failures first, stop at the first: a red suite shows in seconds instead of
# the full run; a green suite still runs every test. The gate and CI run the
# suite plain — this is the edit loop's visibility aid, not their check.
FAST_RED = ("-x", "--ff")


def timeout_seconds() -> int:
    """RUN_TESTS_TIMEOUT is foreign input: digits only, else the default."""
    raw = os.environ.get("RUN_TESTS_TIMEOUT", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_TIMEOUT


def edited_code_file(data: object, root: str) -> str | None:
    """The edited path when the event is the one shape we act on: a dict whose
    tool_input carries a str file_path with a code suffix inside this project.
    Anything else is None — fail OPEN, never a traceback."""
    if not isinstance(data, dict):
        return None
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        return None
    fp = ti.get("file_path")
    if not isinstance(fp, str) or not fp.lower().endswith(CODE_SUFFIXES):
        return None  # not code — skip silently; only "tests green" means "ran"
    # Only files inside THIS project — an edit in a sibling repo would
    # otherwise produce a misleading green from a suite that never covers it.
    if not os.path.abspath(fp).startswith(os.path.abspath(root) + os.sep):
        return None
    return fp


def pytest_command() -> list[str] | None:
    """The venv's pytest, else the PATH's, else None (run `make setup`)."""
    venv_pytest = os.path.join(".venv", "bin", "pytest")
    if os.path.exists(venv_pytest):
        return [venv_pytest, *FAST_RED]  # pyproject already sets addopts="-q"
    from shutil import which

    return ["pytest", *FAST_RED] if which("pytest") else None


def _event() -> object:
    """The event as JSON, or None when malformed or over the cap (fail open)."""
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            return None
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def main() -> None:
    data = _event()
    root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    fp = edited_code_file(data, root) if root else None
    if fp is None:
        sys.exit(0)
    try:
        os.chdir(root)
    except OSError:
        sys.exit(0)
    cmd = pytest_command()
    if cmd is None:
        print("[run-tests] pytest not found yet — run `make setup`.", file=sys.stderr)
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
