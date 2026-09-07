"""Pins for scripts/review_gate.py and scripts/review_common.py (spec Phase 0a,
invariants 1 and 7; done-when 2). Pure functions are exercised directly; the
CLI refusals by spawning the script. Offline, no services."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review_gate
from review_common import (
    Refused,
    read_text_or_error,
    readable,
    resolve_spec,
    run,
    section,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "ok.md").write_text("# ok\n")
    (tmp_path / "outside.md").write_text("# an existing file outside specs/\n")
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
        "outside.md",  # exists, is a file — only the specs-parent check refuses it
        "specs/../outside.md",
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


def test_run_reports_a_missing_command():
    code, out = run(["definitely-not-a-command-xyz"], ROOT)
    assert code == 127 and out == "command not found: definitely-not-a-command-xyz"


def test_run_reports_output_that_is_not_text():
    """The subprocess-output boundary: a byte that does not decode is one
    line naming the command, never a traceback."""
    emit = "import sys; sys.stdout.buffer.write(b'ok\\xff')"
    code, out = run([sys.executable, "-c", emit], ROOT)
    assert (code, out) == (1, f"output of {sys.executable} is not UTF-8 text")


def test_read_boundary_reports_by_name_and_skips_in_a_loop(tmp_path: Path):
    """read_text_or_error names the path relative to root (its name when it
    is not under root); readable() collects the line and goes on."""
    good = tmp_path / "good.md"
    good.write_text("fine\n")
    latin = tmp_path / "latin.md"
    latin.write_bytes(b"caf\xe9\n")
    assert read_text_or_error(good, tmp_path) == ("fine\n", None)
    assert read_text_or_error(latin, tmp_path) == (None, "latin.md: not UTF-8 text")
    assert read_text_or_error(tmp_path / "gone.md", tmp_path) == (
        None,
        "gone.md: cannot be read: No such file or directory",
    )
    assert read_text_or_error(latin, tmp_path / "elsewhere") == (
        None,
        "latin.md: not UTF-8 text",
    )
    errors: list[str] = []
    seen = [f.name for f, _ in readable([latin, good], tmp_path, errors)]
    assert (seen, errors) == (["good.md"], ["latin.md: not UTF-8 text"])


def test_every_script_reads_and_runs_through_the_shared_boundary():
    """The class fix for traceback-at-boundary, pinned as a layout rule: no
    module under scripts/ reads a file or spawns a process on its own; the
    one reader and the one runner live in review_common.py."""
    own = re.compile(r"\.read_text\(|\.read_bytes\(|\bopen\(|\bsubprocess\b")
    offenders = [
        f"{p.name}:{n}"
        for p in sorted(ROOT.glob("scripts/*.py"))
        if p.name != "review_common.py"
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if own.search(line)
    ]
    assert offenders == [], offenders
    common = (ROOT / "scripts" / "review_common.py").read_text()
    assert common.count(".read_text(") == 1 and common.count("subprocess.run(") == 1


def test_section_matches_heading_prefix():
    text = "## Evidence (REQUIRED)\nbody\n## Next\nother\n"
    assert section(text, "Evidence").strip() == "body"
    assert section(text, "Missing") == ""


def _spec(
    evidence: str, invariants: str = "| i | prose |", threat: str = "None"
) -> str:
    """A spec with all four REQUIRED sections; only Evidence varies."""
    return (
        f"## Evidence (REQUIRED)\n{evidence}\n## Invariants (REQUIRED)\n{invariants}\n"
        f"## Record updates (REQUIRED)\n- [ ] README — none\n"
        f"## Threat model (REQUIRED …)\n{threat}\n"
    )


def test_evidence_ids_continue_the_previous_file():
    spec = (
        "## Evidence (REQUIRED)\n| 1 | `tests/test_a.py::test_x`, `::test_y`; "
        "`make check-docs` prints ok |\n| 2 | `tests/test_b.py::test_z` |\n## Next\n"
    )
    tests, targets, errors = review_gate.evidence_ids(spec)
    assert errors == []
    assert tests == [
        "tests/test_a.py::test_x",
        "tests/test_a.py::test_y",
        "tests/test_b.py::test_z",
    ]
    assert targets == ["check-docs"]


def test_bare_test_id_without_a_file_is_an_error():
    """`::test_y` with no file on its own line is an error; the file context of
    the previous ROW never carries over (a same-named test elsewhere must not
    make it pass)."""
    spec = _spec("| 1 | `tests/test_a.py::test_x` |\n| 2 | `::test_y` |")
    tests, _, errors = review_gate.evidence_ids(spec)
    assert tests == ["tests/test_a.py::test_x"]
    assert errors == ["test id without a file: ::test_y"]
    assert review_gate.check_evidence(spec, {"tests/test_a.py::test_x"}, set()) == [
        "test id without a file: ::test_y"
    ]


def test_gate_fails_on_a_missing_evidence_test_id():
    spec = _spec("| 1 | `tests/test_a.py::test_x` / `make nope` |")
    errors = review_gate.check_evidence(
        spec, collected={"tests/test_a.py::test_other"}, declared={"test"}
    )
    assert any("tests/test_a.py::test_x" in e for e in errors)
    assert any("make nope" in e for e in errors)
    assert review_gate.check_evidence(spec, {"tests/test_a.py::test_x"}, {"nope"}) == []


def test_invariant_and_threat_model_ids_are_checked():
    """A test named only in Invariants or Threat model must exist too — an
    invariant with a made-up pin was green before."""
    spec = _spec(
        "| 1 | `tests/test_a.py::test_x` |",
        invariants="| inv | `tests/test_b.py::test_ghost` |",
        threat="| t | … | `tests/test_c.py::test_phantom` |",
    )
    errors = review_gate.check_evidence(spec, {"tests/test_a.py::test_x"}, set())
    assert errors == [
        "spec names a test that does not exist: tests/test_b.py::test_ghost",
        "spec names a test that does not exist: tests/test_c.py::test_phantom",
    ]


def test_gate_fails_on_a_missing_or_empty_required_section():
    """A spec missing ANY of the four REQUIRED sections, or an Evidence section
    naming no test, must FAIL — never pass because nothing was found."""
    assert review_gate.missing_sections("## Why\nprose\n") == [
        "spec has no Evidence section (REQUIRED)",
        "spec has no Invariants section (REQUIRED)",
        "spec has no Record updates section (REQUIRED)",
        "spec has no Threat model section (REQUIRED)",
    ]
    assert review_gate.check_evidence("## Why\nprose\n", set(), set()) == [
        "spec has no Evidence section (REQUIRED)",
        "spec has no Invariants section (REQUIRED)",
        "spec has no Threat model section (REQUIRED)",
    ]
    for gone in ("Invariants", "Threat model"):
        full = _spec("| 1 | `tests/test_a.py::test_x` |")
        without = full.replace(f"## {gone}", "## Other")
        assert review_gate.check_evidence(
            without, {"tests/test_a.py::test_x"}, set()
        ) == [f"spec has no {gone} section (REQUIRED)"], gone
    # present but empty is missing too
    empty = _spec("| 1 | `tests/test_a.py::test_x` |", invariants="   ")
    assert review_gate.check_evidence(empty, {"tests/test_a.py::test_x"}, set()) == [
        "spec has no Invariants section (REQUIRED)"
    ]
    only_targets = _spec("| 1 | `make test` |")
    assert review_gate.check_evidence(only_targets, set(), {"test"}) == [
        "Evidence names no test id"
    ]
    fails, warns = review_gate.check_records("## Why\nprose\n", {"CLAUDE.md"})
    assert fails == ["spec has no Record updates section (REQUIRED)"] and warns == []
    assert (
        review_gate.missing_sections(_spec("| 1 | `tests/test_a.py::test_x` |")) == []
    )


def test_gate_fails_on_a_record_file_absent_from_the_diff():
    spec = (
        "## Record updates (REQUIRED)\n"
        "- [ ] `DECISIONS.md` — entry\n"
        "- [x] `CLAUDE.md` — status\n"
        "- [ ] `docs/PLAN.md` — status; mention `uv` in passing\n"
        "- [ ] README — none\n"
        "## Threat model\n"
    )
    fails, warns = review_gate.check_records(
        spec, diff={"DECISIONS.md", "BACKLOG.md", "scripts/x.py"}
    )
    assert fails == [
        "Record updates lists CLAUDE.md but it is not in the diff",
        "Record updates lists docs/PLAN.md but it is not in the diff",
    ]
    assert warns == ["record file in the diff but not listed: BACKLOG.md"]
    # "README — none" is not a path; neither is `uv`
    assert review_gate.record_paths(spec) == [
        "DECISIONS.md",
        "CLAUDE.md",
        "docs/PLAN.md",
    ]


def test_fixture_change_without_freeze_line_fails():
    """A grant covers exactly what it names: a directory needs its MANIFEST in
    the diff; a file grant covers that file only; nothing widens to a parent."""
    diff = {"fixtures/synthetic/reviews.csv", "scripts/x.py"}
    assert review_gate.check_fixtures(None, diff)  # no spec → any fixture change fails
    assert review_gate.check_fixtures("no freeze here", diff)
    assert review_gate.check_fixtures("Freeze: fixtures/anchors/\n", diff)  # other dir
    # a file grant covers that one file, not its directory
    assert review_gate.check_fixtures(
        "Freeze: fixtures/synthetic/MANIFEST.sha256\n", diff
    ) == [
        "fixture changed with no `Freeze:` line covering it: "
        "fixtures/synthetic/reviews.csv"
    ]
    assert (
        review_gate.check_fixtures(
            "Freeze: fixtures/synthetic/reviews.csv\n",
            {"fixtures/synthetic/reviews.csv"},
        )
        == []
    )
    # a directory grant needs its MANIFEST in the diff …
    assert review_gate.check_fixtures("Freeze: fixtures/synthetic/\n", diff) == [
        "`Freeze: fixtures/synthetic/` grants a directory but "
        "fixtures/synthetic/MANIFEST.sha256 is not in the diff"
    ]
    # … and then covers every file under it
    with_manifest = diff | {"fixtures/synthetic/MANIFEST.sha256"}
    assert (
        review_gate.check_fixtures("Freeze: fixtures/synthetic/\n", with_manifest) == []
    )
    # `fixtures/` alone or `fixtures/MANIFEST.sha256` never unlocks the tree
    for wide in ("Freeze: fixtures/\n", "Freeze: fixtures/MANIFEST.sha256\n"):
        assert review_gate.check_fixtures(wide, with_manifest), wide
    assert review_gate.check_fixtures("Freeze: none\n", {"scripts/x.py"}) == []
    assert review_gate.check_fixtures(None, {"scripts/x.py"}) == []


def test_diff_paths_are_read_exactly():
    """`git diff --name-only` C-quotes non-ASCII paths and a space would split
    one; `-z` output is read whole so `fixtures/` still matches."""
    out = 'fixtures/h\u00e9llo.csv\0fixtures/spa ce.csv\0fixtures/we"ird.csv\0'
    paths = review_gate.diff_paths(out)
    assert paths == {
        "fixtures/h\u00e9llo.csv",
        "fixtures/spa ce.csv",
        'fixtures/we"ird.csv',
    }
    assert all(p.startswith("fixtures/") for p in paths)
    assert review_gate.diff_paths("") == set()
    assert len(review_gate.check_fixtures(None, paths)) == 3


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


def test_gate_prints_one_line_per_check_and_the_total(monkeypatch, tmp_path: Path):
    """Evidence row 1: the printed shape — `ok   <check>` per check and
    `review-gate OK: 8/8 checks` with a SPEC, `6/6` without — pinned with every
    subprocess stubbed green (the real gate runs `make test`, which is this suite)."""
    spec = tmp_path / "specs" / "s.md"
    spec.parent.mkdir()
    spec.write_text(_spec("| 1 | `tests/test_a.py::test_x` |"))
    monkeypatch.setattr(review_gate, "ROOT", tmp_path)
    monkeypatch.setattr(review_gate, "run", lambda cmd, cwd: (0, ""))
    monkeypatch.setattr(review_gate, "make_targets", lambda root: set())
    monkeypatch.setattr(review_gate, "unpinned", lambda root, base: [])
    monkeypatch.setattr(
        review_gate,
        "collected_tests",
        lambda root: (0, {"tests/test_a.py::test_x"}, ""),
    )
    monkeypatch.setattr(review_gate, "resolve_spec", lambda arg, root=None: spec)
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        assert review_gate.main(["--spec=specs/s.md"]) == 0
    lines = buf.getvalue().splitlines()
    assert lines == [
        "ok   test",
        "ok   lint",
        "ok   docs",
        "ok   backing",
        "ok   fixtures",
        "ok   pins",
        "ok   evidence",
        "ok   records",
        "review-gate OK: 8/8 checks",
    ]
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert review_gate.main([]) == 0
    assert buf.getvalue().splitlines() == [
        "SKIP evidence, records (no SPEC)",
        "ok   test",
        "ok   lint",
        "ok   docs",
        "ok   backing",
        "ok   fixtures",
        "ok   pins",
        "review-gate OK: 6/6 checks",
    ]


def test_range_checks_report_a_failed_diff_as_one_fail_and_no_paths(monkeypatch):
    """The two range checks (fixtures, pins) share one diff: when git cannot
    produce it, one FAIL line names the command and the record check gets no
    paths — never a green fixtures line over an unknown range."""
    monkeypatch.setattr(review_gate, "run", lambda cmd, cwd: (128, "fatal: bad"))
    results, diff = review_gate.range_checks(None, "nowhere")
    assert diff == set()
    assert results == [
        ("fixtures", False, "git diff nowhere...HEAD failed: fatal: bad")
    ]
    monkeypatch.setattr(review_gate, "run", lambda cmd, cwd: (0, ""))
    monkeypatch.setattr(review_gate, "unpinned", lambda root, base: ["x::y — new"])
    results, diff = review_gate.range_checks(None, "main")
    assert results == [("fixtures", True, ""), ("pins", False, "x::y — new")]


def test_collected_tests_finds_the_suite():
    """The Evidence check reads real node ids (a bare count would make every
    Evidence row FAIL — pyproject's addopts="-q" plus -q did exactly that)."""
    code, ids, _ = review_gate.collected_tests(ROOT)
    assert code == 0
    assert "tests/test_review_tools.py::test_collected_tests_finds_the_suite" in ids
    assert "tests/test_review_tools.py::test_cli_refusals_are_one_line_exit_2" in ids


def test_make_review_gate_refuses_end_to_end():
    """Through make, not the script: the value crosses the Makefile quoting and
    Python refuses in one line, exit 2, nothing runs, nothing is expanded."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("SPEC", "BASE", "MAKEFLAGS", "MFLAGS")
    }
    for var in ("SPEC=../x", 'SPEC="; echo pwned; "', "SPEC=specs", "BASE=-x"):
        res = subprocess.run(
            ["make", "review-gate", var],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 2, (var, res.stdout, res.stderr)
        refusals = [ln for ln in res.stderr.splitlines() if ln.startswith("refusing:")]
        assert len(refusals) == 1 and "Traceback" not in res.stderr, (var, res.stderr)
        # make echoes the recipe (the literal value inside quotes); had the shell
        # run it, `pwned` would stand alone on a line.
        assert "pwned" not in [ln.strip() for ln in res.stdout.splitlines()]
