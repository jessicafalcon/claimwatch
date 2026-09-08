"""Pins for the mechanical half of code-craft that lives in ruff's config:
every `noqa` that suppresses a function-shape or boolean-flag rule carries a
`-- <reason>`; RUF100 (in pyproject) deletes a noqa that suppresses nothing;
the tag rule sets (TD, FIX) are selected with exactly the three ignores whose
record side check-docs carries. Offline; reads git and pyproject only."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from tests.repo_text import repo_text

ROOT = Path(__file__).resolve().parent.parent
SHAPE_RULES = re.compile(r"# noqa: [^\n]*\b(?:C901|PLR09\d\d|FBT\d\d\d)\b[^\n]*")
WITH_REASON = re.compile(r"# noqa: (?:[A-Z]+\d+, )*[A-Z]+\d+ -- \S")


def _tracked_python() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "*.py", ".claude/hooks/*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / p for p in out.split("\0") if p]


def test_every_shape_rule_noqa_carries_its_reason():
    missing: list[str] = []
    seen = 0
    for path in _tracked_python():
        if path == Path(__file__).resolve():
            continue  # this file spells the pattern it looks for
        for n, line in enumerate(repo_text(path).splitlines(), 1):
            m = SHAPE_RULES.search(line)
            if m is None:
                continue
            seen += 1
            if not WITH_REASON.match(m.group(0)):
                missing.append(f"{path.relative_to(ROOT)}:{n}")
    assert missing == [], missing
    assert seen >= 1  # the rule is exercised, not vacuous


def test_ruff_selects_the_tag_rules_with_exactly_the_record_side_ignores():
    """Invariant: FIXME and XXX never merge, and a TODO carries its parens and
    colon — ruff's half of the tag rule. TD003, FIX002 and FIX004 are off
    because check-docs check 7 verifies the record entry instead; no other
    ignore, or the half silently widens."""
    lint = tomllib.loads(repo_text(ROOT / "pyproject.toml"))["tool"]["ruff"]["lint"]
    assert {"TD", "FIX", "RUF100"} <= set(lint["select"])
    assert lint["ignore"] == ["TD003", "FIX002", "FIX004"]
