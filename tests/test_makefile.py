"""Pins for the Makefile's variable handling (spec Phase 0a, invariant 2 —
"trusted origin"). `make -n` prints the recipe without running it, so these
tests exercise `$(value)` + `_Q` + `unexport` on the REAL Makefile, from both
origins, without spawning the gate. Offline, no services."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from review_common import make_targets

from pipeline.build import INPUTS
from pipeline.cli import CONFIRM_STAMP, Refused, confirmed, resolve_choice
from pipeline.warehouse import TARGETS

pytestmark = pytest.mark.slow  # integration (builds a DuckDB warehouse)

ROOT = Path(__file__).resolve().parent.parent
SCRUB = (
    "SPEC",
    "BASE",
    "TARGET",
    "ROWS",
    "CONFIRM",
    "SOURCE",
    "MAKEFLAGS",
    "MFLAGS",
)

BAD_VALUES = ("../x", '"; echo pwned; "', "$(shell echo x)", "sqlite", "SYNTHETIC")


def _env(extra: dict[str, str]) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k not in SCRUB}
    return {**base, **extra}


def _make_n(target: str, cmdline: dict[str, str], env: dict[str, str]) -> str:
    res = subprocess.run(
        ["make", "-n", target, *(f"{k}={v}" for k, v in cmdline.items())],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=_env(env),
        check=True,
    )
    return res.stdout


@pytest.mark.parametrize("var, flag", [("SPEC", "--spec"), ("BASE", "--base")])
@pytest.mark.parametrize(
    "value", ['"; echo pwned; "', "$(shell echo pwned)", "../x", "a'b"]
)
def test_user_variable_reaches_python_as_one_literal_from_both_origins(
    var: str, flag: str, value: str
):
    """For EVERY user variable, whatever the origin, the recipe carries the
    UNEXPANDED value as one single-quoted token (`'` → `'\\''`) — no shell, no
    make function runs."""
    quoted = "'" + value.replace("'", "'\\''") + "'"
    for origin in ("cmdline", "env"):
        out = _make_n(
            "review-gate",
            {var: value} if origin == "cmdline" else {},
            {var: value} if origin == "env" else {},
        )
        assert f"{flag}={quoted}" in out, (var, origin, out)
        assert "pwned" not in out.replace(value, "")  # nothing expanded or ran


def test_empty_spec_omits_the_flag():
    out = _make_n("review-gate", {"SPEC": ""}, {})
    assert "--spec" not in out and "--base='main'" in out


def test_env_exported_spec_reaches_the_recipe_and_is_validated_in_python():
    """`unexport` does NOT keep an environment value out of the recipe; it only
    strips the child environment. Python is the guard (resolve_spec)."""
    assert "--spec='../x'" in _make_n("review-gate", {}, {"SPEC": "../x"})
    probe = "include Makefile\nprobe:\n\t@echo SPEC_IN_ENV=$${SPEC-unset}\n"
    res = subprocess.run(
        ["make", "-s", "-f", "-", "probe"],
        cwd=ROOT,
        input=probe,
        capture_output=True,
        text=True,
        env=_env({"SPEC": "../x"}),
        check=True,
    )
    assert res.stdout.strip() == "SPEC_IN_ENV=unset"


def test_help_lists_every_declared_target():
    out = subprocess.run(
        ["make", "-s", "help"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    declared = make_targets(ROOT)  # the one parser (review_common)
    assert declared, "no targets parsed"
    names = {line.split()[0] for line in out.splitlines() if line.strip()}
    for target in declared:
        assert target in names, target


def test_make_targets_ignores_variable_assignments(tmp_path: Path):
    """Spaced and unspaced assignments (`foo := 1`, `foo:= 1`, `baz:=3`,
    `qux::= 4`) are variables; only a rule line declares a target."""
    (tmp_path / "Makefile").write_text(
        "foo := 1\nfoo2:= 1\nbaz:=3\nqux::= 4\nbar:\n\tx\ndc::\n\ty\n.PHONY: bar\n"
    )
    assert make_targets(tmp_path) == {"bar", "dc"}


# --- Phase 1: the pipeline targets (rebuild, idempotency-check, reset) ---


def test_rebuild_variables_are_a_closed_set():
    """TARGET/ROWS validate against a closed set; a value is never a path, so
    `../x` or a metacharacter is just a name not in the set."""
    assert resolve_choice("", TARGETS, "duckdb") == "duckdb"  # empty -> default
    assert resolve_choice("duckdb", TARGETS, "duckdb") == "duckdb"
    # Phase 3a: the closed set of rebuild inputs, named by what they are;
    # `make rebuild` defaults to the scraper's captures, CI runs the samples.
    assert INPUTS == ("captured", "none", "synthetic", "samples")
    assert resolve_choice("", INPUTS, "captured") == "captured"
    assert resolve_choice("synthetic", INPUTS, "captured") == "synthetic"
    assert resolve_choice("samples", INPUTS, "captured") == "samples"
    assert resolve_choice("none", INPUTS, "captured") == "none"
    for old in ("cache", "empty", "app-store"):  # Phase 2's names are gone
        with pytest.raises(Refused):
            resolve_choice(old, INPUTS, "captured")
    for bad in BAD_VALUES:
        with pytest.raises(Refused):
            resolve_choice(bad, TARGETS, "duckdb")


def test_idempotency_check_variables_are_a_closed_set():
    assert resolve_choice("", INPUTS, "synthetic") == "synthetic"  # its default
    assert resolve_choice("none", INPUTS, "synthetic") == "none"
    for bad in BAD_VALUES:
        with pytest.raises(Refused):
            resolve_choice(bad, INPUTS, "synthetic")


def test_rows_outside_the_set_is_refused():
    for bad in ("../x", "prod", '"; rm -rf', "SYNTHETIC", "fixtures/app-store"):
        with pytest.raises(Refused):
            resolve_choice(bad, INPUTS, "none")


@pytest.mark.parametrize("target", ["rebuild", "idempotency-check"])
@pytest.mark.parametrize("var, flag", [("TARGET", "--target"), ("ROWS", "--rows")])
def test_pipeline_variables_reach_python_as_one_literal(target, var, flag):
    """Whatever the origin, the recipe carries the UNEXPANDED value as one
    single-quoted token — no shell, no make function runs."""
    value = "$(shell echo pwned)"
    quoted = "'" + value.replace("'", "'\\''") + "'"
    for origin in ("cmdline", "env"):
        out = _make_n(
            target,
            {var: value} if origin == "cmdline" else {},
            {var: value} if origin == "env" else {},
        )
        assert f"{flag}={quoted}" in out, (var, origin, out)
        assert "pwned" not in out.replace(value, "")


def test_reset_and_scrape_take_the_make_pid_not_a_confirm_variable():
    """A4 (d): the gated recipes pass their make process's id (`$$PPID`, the
    recipe shell's parent) and no CONFIRM value of any origin — the variable
    is gone from the recipes, so nothing an environment defines reaches the
    gate."""
    for target in ("reset", "scrape"):
        for origin in ("cmdline", "env"):
            out = _make_n(
                target,
                {"CONFIRM": "yes"} if origin == "cmdline" else {},
                {"CONFIRM": "yes"} if origin == "env" else {},
            )
            assert "--make-pid=$PPID" in out, (target, origin, out)
            assert "--confirm" not in out and "yes" not in out, (target, origin, out)
    out = _make_n("confirm", {}, {})
    assert "--make-pid=$PPID" in out and "--goals='confirm'" in out  # A8 (d)
    assert "--goals-origin='default'" in out  # A9 (a): make's own list, by origin


PROBE = (
    "include Makefile\n"
    # `reset` re-defined as a probe (make warns "overriding commands" and uses
    # this one): a gated goal that asks `confirmed` with its own make process
    # id and deletes nothing — `confirm` arms `reset` or `scrape` alone (A9).
    "reset:\n"
    '\t@uv run python -c "import sys; from pipeline.cli import confirmed; '
    "sys.exit(0 if confirmed('$$PPID') else 3)\"\n"
)


def _probe(goals: list[str], env: dict[str, str]) -> int:
    """Run the real Makefile plus a `reset` goal redefined as a probe that
    asks `confirmed` with its own make process id: 0 when the invocation was
    confirmed, otherwise make's 2 (the recipe exits 3 and make reports a
    failed goal as 2)."""
    res = subprocess.run(
        ["make", "-s", "-f", "-", *goals],
        cwd=ROOT,
        input=PROBE,
        capture_output=True,
        text=True,
        env=_env(env),
    )
    return res.returncode


def test_confirm_is_a_goal_of_the_same_invocation():
    """A4 (d): `make confirm <target>` confirms; the target alone, the goals in
    the other order, a CONFIRM variable from any origin, MAKEFLAGS carrying
    `CONFIRM=yes` or the word `confirm`, MAKECMDGOALS from the environment,
    and a stamp left by an earlier invocation each confirm nothing — a goal
    cannot arrive through the environment, and the stamp names one process
    (round 3, security-reviewer #1)."""
    from pipeline.warehouse import DEFAULT_DB

    existed = DEFAULT_DB.exists()  # the probe's `reset` deletes nothing (A9)
    try:
        assert _probe(["confirm", "reset"], {}) == 0
        assert not CONFIRM_STAMP.exists()  # consumed
        assert DEFAULT_DB.exists() == existed  # the override took: no delete
        assert _probe(["reset"], {}) == 2
        assert _probe(["reset", "confirm"], {}) == 2  # reset runs first: no stamp yet
        assert _probe(["reset", "CONFIRM=yes"], {}) == 2
        assert _probe(["reset"], {"CONFIRM": "yes"}) == 2
        assert _probe(["reset"], {"MAKEFLAGS": "CONFIRM=yes"}) == 2
        assert _probe(["reset"], {"MAKEFLAGS": "confirm"}) == 2
        assert _probe(["reset"], {"MAKECMDGOALS": "confirm"}) == 2
        # A8 (d): a confirm with nothing after it refuses and leaves no stamp,
        # so no armed stamp outlives its invocation.
        assert _probe(["confirm"], {}) == 2
        assert not CONFIRM_STAMP.exists()
        assert _probe(["reset", "confirm"], {}) == 2  # confirm last: refused too
        assert not CONFIRM_STAMP.exists()
        # A stale stamp (an earlier invocation's process id) confirms nothing
        # and is consumed; a planted stamp makes `confirm` itself refuse.
        CONFIRM_STAMP.write_text("99999\n", encoding="utf-8")
        assert _probe(["reset"], {}) == 2  # another process: not this one
        assert not CONFIRM_STAMP.exists()  # and the stale stamp is gone
        CONFIRM_STAMP.write_text("99999\n", encoding="utf-8")
        assert _probe(["confirm", "reset"], {}) == 2  # confirm refuses: file there
        assert CONFIRM_STAMP.read_text(encoding="utf-8") == "99999\n"  # untouched
    finally:
        CONFIRM_STAMP.unlink(missing_ok=True)


def test_a_parallel_run_still_stamps_before_the_gated_goal_runs():
    """`.NOTPARALLEL:` — under `make -j2 confirm reset` make used to start
    `reset` before `confirm` had stamped (7 of 12 runs left an armed stamp
    behind and refused); with goals serialised every run is confirmed and
    consumes its stamp (exit pass, security-reviewer #1, code-reviewer #1)."""
    try:
        for _ in range(8):
            assert _probe(["-j2", "confirm", "reset"], {}) == 0
            assert not CONFIRM_STAMP.exists()
    finally:
        CONFIRM_STAMP.unlink(missing_ok=True)


def test_confirm_arms_a_gated_goal_or_nothing():
    """A9 (a), against the installed make: `make confirm help` refuses and
    leaves no stamp; a MAKECMDGOALS definition from the environment, from
    MAKEFLAGS or from the command line has an origin that is not make's own
    and confirms nothing, leaving no stamp; `make confirm reset` still arms
    (round 5, code-reviewer #2, security-reviewer #1 #2, functionality-tester
    #4 #5)."""
    try:
        assert _probe(["confirm", "help"], {}) == 2
        assert not CONFIRM_STAMP.exists()
        assert _probe(["confirm", "reset"], {"MAKECMDGOALS": "confirm reset"}) == 2
        assert not CONFIRM_STAMP.exists()
        assert _probe(["confirm", "reset", "MAKECMDGOALS=confirm reset"], {}) == 2
        assert not CONFIRM_STAMP.exists()
        env = {"MAKEFLAGS": "MAKECMDGOALS=confirm reset"}
        assert _probe(["confirm", "reset"], env) == 2
        assert not CONFIRM_STAMP.exists()
        assert _probe(["confirm", "reset"], {}) == 0
        assert not CONFIRM_STAMP.exists()  # consumed by the probe
    finally:
        CONFIRM_STAMP.unlink(missing_ok=True)


# --- Phase 2: the network target (scrape) ---


def test_scrape_source_is_a_closed_set():
    """SOURCE validates against the declared names; a value is never a path."""
    from ingest.sources import source_names

    names = source_names()
    assert resolve_choice("", names, names[0]) == names[0]
    for bad in BAD_VALUES + ("fixtures/app-store", "app-store"):
        with pytest.raises(Refused):
            resolve_choice(bad, names, names[0])


def test_scrape_passes_source_unexpanded_and_its_make_pid():
    """The recipe passes SOURCE unexpanded and the make process id; no CONFIRM
    value of any origin reaches Python, so an agent's or a CI's
    non-interactive call never fetches (A4 (d))."""
    from_cmdline = _make_n("scrape", {"CONFIRM": "yes", "SOURCE": "x"}, {})
    assert "--source='x'" in from_cmdline and "--make-pid=$PPID" in from_cmdline
    assert "--confirm" not in from_cmdline
    from_env = _make_n("scrape", {}, {"CONFIRM": "yes", "SOURCE": "x"})
    assert "--source='x'" in from_env and "--confirm" not in from_env
    assert confirmed("") is False and confirmed("not-a-pid") is False


@pytest.mark.parametrize("var, flag", [("SOURCE", "--source")])
def test_scrape_variables_reach_python_as_one_literal(var, flag):
    value = "$(shell echo pwned)"
    quoted = "'" + value.replace("'", "'\\''") + "'"
    for origin in ("cmdline", "env"):
        out = _make_n(
            "scrape",
            {var: value} if origin == "cmdline" else {},
            {var: value} if origin == "env" else {},
        )
        assert f"{flag}={quoted}" in out, (var, origin, out)
        assert "pwned" not in out.replace(value, "")
