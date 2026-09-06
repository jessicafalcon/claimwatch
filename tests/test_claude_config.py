"""Pins for what Claude Code configuration is tracked (spec Phase 0a,
invariant 6; done-when 5): prose (agents, commands, skills) and hook scripts
only. A tracked settings.json or .mcp.json would auto-run an inbound branch's
hooks or MCP servers for anyone opening the repo. Offline; reads git only."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

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
# Each agent's model and effort, pinned by id: `model: opus` is an alias that
# drifts with the build (DECISIONS → Gotchas, 2026-09-05).
AGENT_MODELS = {
    "code-reviewer": ("claude-opus-4-8", "high"),
    "security-reviewer": ("claude-opus-4-8", "high"),
    "functionality-tester": ("claude-opus-4-8", "high"),
    "study-editor": ("claude-opus-4-8", "high"),
    "coherence-auditor": ("inherit", "high"),
    "senior-architect": ("inherit", "high"),
}
# One standard, two readers: the skill an agent is preloaded with.
AGENT_SKILLS = {
    "code-reviewer": ["code-craft"],
    "security-reviewer": ["secure-by-construction"],
    "senior-architect": ["architecture-fit"],
}
STANDARDS = ("code-craft", "secure-by-construction", "architecture-fit")
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# The only shell a skill may pre-approve: read-only git, prefix form.
READ_ONLY_BASH = {
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git status:*)",
    "Bash(git show:*)",
}


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text()
    assert text.startswith("---\n"), path
    block = text.split("---\n", 2)[1]
    data = yaml.safe_load(block)
    assert isinstance(data, dict), path
    return data


def _agent(name: str) -> Path:
    return ROOT / ".claude" / "agents" / f"{name}.md"


def _skill(name: str) -> Path:
    return ROOT / ".claude" / "skills" / name / "SKILL.md"


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
        text = _agent(name).read_text()
        tools = re.search(r"^tools:\s*(.*)$", text, re.M)
        assert tools, name
        assert not EDIT_TOOLS & {t.strip() for t in tools.group(1).split(",")}, name


def test_every_agent_pins_its_model_effort_and_preloaded_skill():
    """The frontmatter is a closed table: an id, never the drifting alias."""
    assert set(AGENT_MODELS) == set(AGENTS)
    for name, (model, effort) in AGENT_MODELS.items():
        fm = _frontmatter(_agent(name))
        assert fm.get("model") == model, name
        assert fm.get("effort") == effort, name
        assert fm.get("skills") == AGENT_SKILLS.get(name), name
    for name in AGENT_SKILLS:
        for skill in AGENT_SKILLS[name]:
            assert skill in SKILLS, (name, skill)


def test_skills_grant_only_read_only_tools():
    """A skill's pre-approved tools never include an editor, and its shell is
    the read-only git set in prefix form (`Bash(git diff:*)`) — the one form
    the permission syntax documents; `Bash(git *)` is either a no-op or every
    subcommand. The three standards are background knowledge, not commands."""
    for name in SKILLS:
        fm = _frontmatter(_skill(name))
        granted = fm.get("allowed-tools", [])
        if isinstance(granted, str):
            granted = [g.strip() for g in granted.split(",")]
        assert isinstance(granted, list), name
        assert not EDIT_TOOLS & set(granted), name
        for tool in granted:
            if tool.startswith("Bash"):
                assert tool in READ_ONLY_BASH, (name, tool)
        assert "disallowed-tools" not in fm or set(fm["disallowed-tools"]) >= EDIT_TOOLS
    for name in STANDARDS:
        fm = _frontmatter(_skill(name))
        assert fm.get("user-invocable") is False, name
        assert isinstance(fm.get("paths"), list) and fm["paths"], name


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
