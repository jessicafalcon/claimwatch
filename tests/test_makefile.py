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
from review_common import make_targets  # noqa: E402

from pipeline.build import INPUTS  # noqa: E402
from pipeline.cli import Refused, confirmed, resolve_choice  # noqa: E402
from pipeline.warehouse import TARGETS  # noqa: E402

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


def test_reset_requires_command_line_confirm():
    """`confirmed` gates on the value AND its origin; the recipe passes the true
    `$(origin CONFIRM)`, so an environment CONFIRM=yes cannot pose as one from
    the command line."""
    assert confirmed("yes", "command line") is True
    assert confirmed("yes", "environment") is False
    assert confirmed("", "command line") is False
    assert confirmed("no", "command line") is False
    from_cmdline = _make_n("reset", {"CONFIRM": "yes"}, {})
    assert "--confirm='yes'" in from_cmdline
    assert "--confirm-origin='command line'" in from_cmdline
    from_env = _make_n("reset", {}, {"CONFIRM": "yes"})
    assert "--confirm-origin='environment'" in from_env


# --- Phase 2: the network target (scrape) ---


def test_scrape_source_is_a_closed_set():
    """SOURCE validates against the declared names; a value is never a path."""
    from ingest.sources import source_names

    names = source_names()
    assert resolve_choice("", names, names[0]) == names[0]
    for bad in BAD_VALUES + ("fixtures/app-store", "app-store"):
        with pytest.raises(Refused):
            resolve_choice(bad, names, names[0])


def test_scrape_requires_command_line_confirm():
    """The recipe passes SOURCE unexpanded and the true `$(origin CONFIRM)`; an
    environment CONFIRM=yes reaches Python as origin `environment`, which
    `confirmed()` rejects — so an agent's or a CI's non-interactive call never
    fetches."""
    from_cmdline = _make_n("scrape", {"CONFIRM": "yes", "SOURCE": "x"}, {})
    assert "--source='x'" in from_cmdline
    assert "--confirm='yes'" in from_cmdline
    assert "--confirm-origin='command line'" in from_cmdline
    from_env = _make_n("scrape", {}, {"CONFIRM": "yes", "SOURCE": "x"})
    assert "--source='x'" in from_env
    assert "--confirm-origin='environment'" in from_env
    assert confirmed("yes", "environment") is False


@pytest.mark.parametrize(
    "var, flag", [("SOURCE", "--source"), ("CONFIRM", "--confirm")]
)
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
