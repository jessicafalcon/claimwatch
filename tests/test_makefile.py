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

ROOT = Path(__file__).resolve().parent.parent
SCRUB = ("SPEC", "BASE", "MAKEFLAGS", "MFLAGS")


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
