"""Pin for the craft rule "past a signal, either split or write the one-line
reason it stays whole": every `noqa` that suppresses a function-shape or
boolean-flag rule carries a `-- <reason>`; RUF100 (in pyproject) deletes a
noqa that suppresses nothing. Offline; reads git only."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

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
        for n, line in enumerate(path.read_text().splitlines(), 1):
            m = SHAPE_RULES.search(line)
            if m is None:
                continue
            seen += 1
            if not WITH_REASON.match(m.group(0)):
                missing.append(f"{path.relative_to(ROOT)}:{n}")
    assert missing == [], missing
    assert seen >= 1  # the rule is exercised, not vacuous
