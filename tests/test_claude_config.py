"""Pins for what Claude Code configuration is tracked (spec Phase 0a,
invariant 6; done-when 5): prose and hook scripts only. A tracked
settings.json or .mcp.json would auto-run an inbound branch's hooks or MCP
servers for anyone opening the repo. Offline; reads git only."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = re.compile(
    r"^\.claude/(agents|commands)/[a-z-]+\.md$|^\.claude/hooks/[a-z-]+\.py$"
)
AGENTS = (
    "code-reviewer",
    "security-reviewer",
    "functionality-tester",
    "coherence-auditor",
    "study-editor",
)
COMMANDS = ("review-round", "selfcheck", "phase-start")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_tracked_claude_config_is_prose_and_hook_scripts_only():
    tracked = _git(
        "ls-files", "--cached", "--others", "--exclude-standard", ".claude"
    ).stdout.split()
    offenders = [p for p in tracked if not ALLOWED.match(p)]
    assert offenders == [], offenders
    for name in AGENTS:
        assert (ROOT / ".claude" / "agents" / f"{name}.md").is_file(), name
    for name in COMMANDS:
        assert (ROOT / ".claude" / "commands" / f"{name}.md").is_file(), name
    assert (ROOT / ".claude" / "hooks" / "run-tests.py").is_file()


def test_settings_and_mcp_are_gitignored():
    for path in (
        ".claude/settings.json",
        ".claude/settings.local.json",
        ".mcp.json",
        ".env",
        "data/x.duckdb",
        "data/corpus/a.json",
    ):
        assert _git("check-ignore", "-q", path).returncode == 0, (
            f"{path} is not ignored"
        )
    assert _git("check-ignore", "-q", "data/snapshots/a.csv").returncode == 1, (
        "snapshots must be trackable"
    )


def test_every_agent_is_report_only():
    """No agent carries Write or Edit (CLAUDE.md → Project tooling)."""
    for name in AGENTS:
        text = (ROOT / ".claude" / "agents" / f"{name}.md").read_text()
        tools = re.search(r"^tools:\s*(.*)$", text, re.M)
        assert tools, name
        assert not {"Write", "Edit", "MultiEdit", "NotebookEdit"} & {
            t.strip() for t in tools.group(1).split(",")
        }, name
