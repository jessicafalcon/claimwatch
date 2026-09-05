"""Pins for what Claude Code configuration is tracked (spec Phase 0a,
invariant 6; done-when 5): prose (agents, commands, skills) and hook scripts
only. A tracked settings.json or .mcp.json would auto-run an inbound branch's
hooks or MCP servers for anyone opening the repo. Offline; reads git only."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = re.compile(
    r"^\.claude/(agents|commands)/[a-z-]+\.md$"
    r"|^\.claude/skills/[a-z-]+/SKILL\.md$"
    r"|^\.claude/hooks/[a-z-]+\.py$"
)
AGENTS = (
    "code-reviewer",
    "security-reviewer",
    "functionality-tester",
    "coherence-auditor",
    "study-editor",
    "senior-architect",
)
COMMANDS = ("review-round", "selfcheck", "phase-start")
SKILLS = ("challenge", "code-craft", "secure-by-construction", "architecture-fit")
HOOKS = ("run-tests", "challenge-gate")


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
    for name in SKILLS:
        assert (ROOT / ".claude" / "skills" / name / "SKILL.md").is_file(), name
    for name in HOOKS:
        assert (ROOT / ".claude" / "hooks" / f"{name}.py").is_file(), name


def test_settings_and_mcp_are_gitignored():
    for path in (
        ".claude/settings.json",
        ".claude/settings.local.json",
        ".mcp.json",
        ".env",
        ".env.local",
        ".envrc",
        ".env-prod",
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


def test_ci_workflow_is_pinned_and_read_only():
    """Evidence row 6, the half that needs no push: every action is SHA-pinned,
    the token is read-only, checkout keeps no credentials, uv syncs --locked."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    uses = re.findall(r"uses:\s*(\S+)", ci)
    assert uses and all(
        re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in uses
    ), uses
    assert re.search(r"^permissions:\n  contents: read$", ci, re.M)
    assert "persist-credentials: false" in ci
    assert "uv sync --locked" in ci
    assert "secrets." not in ci
