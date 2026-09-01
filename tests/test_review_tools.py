"""Pins for scripts/review_gate.py and scripts/review_common.py (spec Phase 0a,
invariants 1 and 7; done-when 2). Pure functions are exercised directly; the
CLI refusals by spawning the script. Offline, no services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review_gate  # noqa: E402
from review_common import Refused, resolve_spec, section  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "ok.md").write_text("# ok\n")
    return tmp_path


def test_spec_outside_specs_is_refused(root: Path):
    """`../x`, an absolute path, a directory, empty, and a missing file are all
    refused with one line; only an existing file under specs/ resolves."""
    assert resolve_spec("specs/ok.md", root) == (root / "specs" / "ok.md").resolve()
    for bad in (
        "../x",
        str(root / "specs" / "ok.md"),
        "specs",
        "",
        "   ",
        "specs/nope.md",
    ):
        with pytest.raises(Refused) as exc:
            resolve_spec(bad, root)
        assert "\n" not in str(exc.value)
        assert str(exc.value).startswith("refusing:")


def test_base_is_validated():
    for ok in ("main", "origin/main", "abc123", "v1.2"):
        assert review_gate.resolve_base(ok) == ok
    for bad in ("-x", "--output=x", "a b", "", "main;rm"):
        with pytest.raises(Refused):
            review_gate.resolve_base(bad)


def test_section_matches_heading_prefix():
    text = "## Evidence (REQUIRED)\nbody\n## Next\nother\n"
    assert section(text, "Evidence").strip() == "body"
    assert section(text, "Missing") == ""


def test_evidence_ids_continue_the_previous_file():
    spec = (
        "## Evidence (REQUIRED)\n| 1 | `tests/test_a.py::test_x`, `::test_y`; "
        "`make check-docs` prints ok |\n| 2 | `tests/test_b.py::test_z` |\n## Next\n"
    )
    tests, targets = review_gate.evidence_ids(spec)
    assert tests == [
        "tests/test_a.py::test_x",
        "tests/test_a.py::test_y",
        "tests/test_b.py::test_z",
    ]
    assert targets == ["check-docs"]


def test_gate_fails_on_a_missing_evidence_test_id():
    spec = "## Evidence (REQUIRED)\n| 1 | `tests/test_a.py::test_x` / `make nope` |\n"
    errors = review_gate.check_evidence(
        spec, collected={"tests/test_a.py::test_other"}, declared={"test"}
    )
    assert any("tests/test_a.py::test_x" in e for e in errors)
    assert any("make nope" in e for e in errors)
    assert review_gate.check_evidence(spec, {"tests/test_a.py::test_x"}, {"nope"}) == []


def test_gate_fails_on_a_record_file_absent_from_the_diff():
    spec = (
        "## Record updates (REQUIRED)\n"
        "- [ ] `DECISIONS.md` — entry\n"
        "- [x] `CLAUDE.md` — status\n"
        "- [ ] README — none\n"
        "## Threat model\n"
    )
    fails, warns = review_gate.check_records(
        spec, diff={"DECISIONS.md", "BACKLOG.md", "scripts/x.py"}
    )
    assert fails == ["Record updates lists CLAUDE.md but it is not in the diff"]
    assert warns == ["record file in the diff but not listed: BACKLOG.md"]
    assert review_gate.record_paths(spec) == [
        "DECISIONS.md",
        "CLAUDE.md",
    ]  # "README — none" is not a path


def test_fixture_change_without_freeze_line_fails():
    diff = {"fixtures/synthetic/reviews.csv", "scripts/x.py"}
    assert review_gate.check_fixtures(None, diff)  # no spec → any fixture change fails
    assert review_gate.check_fixtures("no freeze here", diff)
    assert review_gate.check_fixtures(
        "Freeze: fixtures/anchors/MANIFEST.sha256\n", diff
    )  # other dir
    assert (
        review_gate.check_fixtures("Freeze: fixtures/synthetic/MANIFEST.sha256\n", diff)
        == []
    )
    assert review_gate.check_fixtures(None, {"scripts/x.py"}) == []


@pytest.mark.parametrize(
    "argv", [["--spec=../x"], ["--spec=/etc/passwd"], ["--base=-x"]]
)
def test_cli_refusals_are_one_line_exit_2(argv: list[str]):
    res = subprocess.run(
        [sys.executable, "scripts/review_gate.py", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    assert res.stdout == ""
    assert len(res.stderr.strip().splitlines()) == 1
    assert "Traceback" not in res.stderr


def test_collected_tests_finds_the_suite():
    """The Evidence check reads real node ids (a bare count would make every
    Evidence row FAIL — pyproject's addopts="-q" plus -q did exactly that)."""
    ids = review_gate.collected_tests(ROOT)
    assert "tests/test_review_tools.py::test_collected_tests_finds_the_suite" in ids
    assert "tests/test_review_tools.py::test_cli_refusals_are_one_line_exit_2" in ids
