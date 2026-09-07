"""Pins for scripts/check_pins.py (the review gate's `pins` line): the pure
change reader on planted sources, the rule end to end in a throwaway git repo,
and the CLI's one-line refusal. Offline, no services; never runs on this
repo's own branch state, which is the gate's job, not the suite's."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_pins
from review_common import Refused

ROOT = Path(__file__).resolve().parent.parent

BASE_SRC = """
def alpha(x):
    return x

def _helper():
    return 1

class Row:
    pass

def gone():
    return 0

def main():
    pass
"""
HEAD_SRC = '''
# a comment, then alpha re-formatted but not changed
def alpha(x):
    return x


def _helper():
    return 2


class Row:
    """A docstring counts as a change."""


def beta(y):
    return y


def main():
    return 1
'''


def test_symbol_changes_marks_new_and_changed_public_defs_only():
    """Formatting and comments do not count; a private def, `main` and a
    deleted def never appear; a body or docstring change is `changed`."""
    assert set(check_pins.public_defs(BASE_SRC)) == {"alpha", "Row", "gone"}
    assert check_pins.symbol_changes(BASE_SRC, HEAD_SRC) == {
        "Row": "changed",
        "beta": "new",
    }
    assert check_pins.symbol_changes(None, HEAD_SRC) == {
        "alpha": "new",
        "Row": "new",
        "beta": "new",
    }
    assert check_pins.names_in(["calls beta()"], "beta")
    assert not check_pins.names_in(["betamax"], "beta")


def _git(cwd: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
        "HOME": str(cwd),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    res = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env=env, check=True
    )
    return res.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_unpinned_applies_the_rule_over_a_real_range(tmp_path: Path):
    """New def → a test in the diff must name it; changed def → any test;
    new mart → a changed test names the table; an unchanged test file that
    names a new def does not count."""
    _git(tmp_path, "init", "-q")
    _write(
        tmp_path,
        "models/m.py",
        "def alpha():\n    return 1\n\n\ndef keep():\n    return 2\n",
    )
    _write(tmp_path, "tests/test_old.py", "from models.m import alpha, keep, gamma\n")
    _write(tmp_path, "sql/marts/old_mart.sql", "create table old_mart (x integer);\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _write(
        tmp_path,
        "models/m.py",
        "def alpha():\n    return 10\n\n\ndef keep():\n    return 2\n\n\n"
        "def beta():\n    return 3\n\n\ndef gamma():\n    return 4\n",
    )
    _write(tmp_path, "tests/test_new.py", "from models.m import beta\n")
    _write(tmp_path, "sql/marts/new_mart.sql", "create table new_mart (x integer);\n")
    _write(tmp_path, "sql/marts/old_mart.sql", "create table old_mart (y integer);\n")
    _write(tmp_path, "ingest/_private.py", "def _only():\n    return 0\n")
    _write(tmp_path, "notes/free.py", "def unwatched():\n    return 0\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "head")
    assert check_pins.source_at(tmp_path, base, "models/m.py").startswith("def alpha")
    assert check_pins.source_at(tmp_path, base, "tests/test_new.py") is None
    assert check_pins.unpinned(tmp_path, base) == [
        "models/m.py::gamma — new, no test in the diff names it",
        "sql/marts/new_mart.sql — new mart, no test in the diff names new_mart",
    ]
    # an unknown base is a refusal, never an empty green list
    with pytest.raises(Refused, match="^refusing: git merge-base no-such-rev"):
        check_pins.unpinned(tmp_path, "no-such-rev")


def test_cli_refuses_a_bad_base_with_one_line():
    res = subprocess.run(
        [sys.executable, "scripts/check_pins.py", "--base=-x"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    assert res.stderr.strip() == "refusing: BASE must be a plain git rev, got '-x'"
    assert res.stdout == ""
