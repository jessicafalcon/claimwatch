#!/usr/bin/env python3
"""The offline review gate. One process, one line per check, exit 1 on any
FAIL, 2 on a refused SPEC/BASE, never a traceback. Run via
`make review-gate [SPEC=specs/<file>.md] [BASE=main]` — the first thing
`/review-round N` does, before any agent is spawned.

  a. test      — `make test` (last 20 lines on red)
  b. lint      — `ruff check` + `ruff format --check` (read-only; never
                 `make lint`, whose ruff-format hook rewrites files)
  c. docs      — `make check-docs`
  d. backing   — `make check-backing`
  e. fixtures  — `fixtures/**` in `git diff --name-only <base>...HEAD` is a FAIL
                 unless a `Freeze:` line in the spec covers it exactly:
                 `Freeze: fixtures/<name>/` covers that directory and requires
                 its MANIFEST.sha256 in the diff; `Freeze: fixtures/<path>`
                 covers that one file. With no --spec any fixture change is a
                 FAIL (read-only after the phase that froze them)
  f. evidence  — (--spec) the four REQUIRED sections exist; every
                 `tests/….py::test_x` id the spec names — in Evidence,
                 Invariants or Threat model — is collected, and every
                 `make <target>` Evidence names is declared in the Makefile
  g. records   — (--spec) every backticked path on a `- [ ]`/`- [x]` line of
                 the spec's Record updates section is in the diff (FAIL);
                 every record file in the diff NOT on the list is a WARN

Nothing here edits, commits or fixes. Not a pytest file (the run-tests hook)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import (  # noqa: E402
    LIVING_DOCS,
    MAKE_TICK,
    RECORD_DOCS,
    ROOT,
    Refused,
    die,
    make_targets,
    resolve_spec,
    run,
    section,
    tail,
)

_BASE = re.compile(r"^[\w./-]+$")
_TEST_ID = re.compile(r"`(tests/[\w/]+\.py)?(::test_\w+)`")
_MAKE_TICK = MAKE_TICK
_RECORD_LINE = re.compile(r"^- \[[ x]\] (.*)$", re.M)
_TICKED = re.compile(r"`([^`\s]+)`")
# `Freeze: fixtures/<name>/` (a directory) or `Freeze: fixtures/<path>` (one file)
_FREEZE = re.compile(r"^Freeze: (fixtures/[\w.-]+(?:/[\w.-]+)*/?)\s*$", re.M)
MANIFEST = "MANIFEST.sha256"
RECORD_FILES = LIVING_DOCS + RECORD_DOCS + ("PROJECT_BRIEF.md",)


def is_record_path(token: str) -> bool:
    """A backticked token on a checklist line is a record PATH only if it is a
    record file or lives under specs/ or docs/ — `uv` in prose is not one."""
    return token in RECORD_FILES or token.startswith(("specs/", "docs/"))


def resolve_base(arg: str) -> str:
    """`--base` is a git rev used as an argv token: a safe charset and never a
    leading `-` (git would read it as an option). Refused, never a traceback."""
    if not arg or not _BASE.match(arg) or arg.startswith("-"):
        raise Refused(f"refusing: BASE must be a plain git rev, got {arg!r}")
    return arg


def parse_test_ids(body: str) -> tuple[list[str], list[str]]:
    """(test ids, errors) in a section body. A bare `::test_x` continues the
    previous file ON THE SAME LINE; with no file before it on its line it is an
    error, never silently dropped or attached to another row's file."""
    tests: list[str] = []
    errors: list[str] = []
    for line in body.splitlines():
        current = ""
        for m in _TEST_ID.finditer(line):
            if m.group(1):
                current = m.group(1)
            if not current:
                errors.append(f"test id without a file: {m.group(2)}")
                continue
            tests.append(current + m.group(2))
    return tests, errors


def evidence_ids(spec_text: str) -> tuple[list[str], list[str], list[str]]:
    """(test ids, make targets, errors) the Evidence section names."""
    body = section(spec_text, "Evidence")
    tests, errors = parse_test_ids(body)
    return tests, sorted(set(_MAKE_TICK.findall(body))), errors


NAMED_SECTIONS = ("Evidence", "Invariants", "Threat model")
# The four sections specs/TEMPLATE.md marks REQUIRED; a missing one is a FAIL.
REQUIRED_SECTIONS = ("Evidence", "Invariants", "Record updates", "Threat model")


def missing_sections(spec_text: str) -> list[str]:
    return [
        f"spec has no {h} section (REQUIRED)"
        for h in REQUIRED_SECTIONS
        if not section(spec_text, h).strip()
    ]


def named_test_ids(spec_text: str) -> tuple[list[str], list[str]]:
    """(test ids, errors) across every section that names tests — Evidence,
    Invariants ("Falsified by") and Threat model ("Pinned by")."""
    tests: list[str] = []
    errors: list[str] = []
    for heading in NAMED_SECTIONS:
        found, bad = parse_test_ids(section(spec_text, heading))
        tests += found
        errors += bad
    return tests, errors


def check_evidence(
    spec_text: str, collected: set[str], declared: set[str]
) -> list[str]:
    missing = [m for m in missing_sections(spec_text) if "Record updates" not in m]
    if missing:
        return missing  # check_records reports Record updates
    ev_tests, targets, _ = evidence_ids(spec_text)
    tests, errors = named_test_ids(spec_text)
    if not ev_tests and not errors:
        return ["Evidence names no test id"]
    errors += [
        f"spec names a test that does not exist: {t}"
        for t in dict.fromkeys(tests)
        if t not in collected
    ]
    errors += [
        f"Evidence names `make {t}` — not in the Makefile"
        for t in targets
        if t not in declared
    ]
    return errors


def record_paths(spec_text: str) -> list[str]:
    """Every backticked path on a checklist line of Record updates."""
    body = section(spec_text, "Record updates")
    paths: list[str] = []
    for line in _RECORD_LINE.findall(body):
        paths.extend(tok for tok in _TICKED.findall(line) if is_record_path(tok))
    return paths


def check_records(spec_text: str, diff: set[str]) -> tuple[list[str], list[str]]:
    """(FAILs, WARNs): listed-but-absent is a FAIL; a record file in the diff
    but off the list is a WARN."""
    if not section(spec_text, "Record updates").strip():
        return ["spec has no Record updates section (REQUIRED)"], []
    listed = set(record_paths(spec_text))
    fails = [
        f"Record updates lists {p} but it is not in the diff"
        for p in sorted(listed)
        if p not in diff
    ]
    warns = [
        f"record file in the diff but not listed: {p}"
        for p in sorted(diff)
        if is_record_path(p) and p not in listed
    ]
    return fails, warns


def check_fixtures(spec_text: str | None, diff: set[str]) -> list[str]:
    """A `Freeze:` grant covers exactly what it names: a directory (trailing
    `/`, whose MANIFEST must be in the diff) or one file — never its parent."""
    changed = sorted(p for p in diff if p.startswith("fixtures/"))
    if not changed:
        return []
    grants = set(_FREEZE.findall(spec_text or ""))
    errors: list[str] = []
    for g in sorted(grants):
        if g.endswith("/") and g + MANIFEST not in diff:
            errors.append(
                f"`Freeze: {g}` grants a directory but {g}{MANIFEST} is not in the diff"
            )
    for p in changed:
        covered = any(p == g or (g.endswith("/") and p.startswith(g)) for g in grants)
        if not covered:
            errors.append(f"fixture changed with no `Freeze:` line covering it: {p}")
    return errors


def collected_tests(root: Path) -> tuple[int, set[str], str]:
    """(exit code, collected ids, output). A non-zero code means the suite did
    not collect — the caller FAILs evidence explicitly, never via an empty set."""
    # `-o addopts=`: pyproject sets addopts="-q"; a second -q would print only
    # a count, no node ids (found live in Phase 0a).
    code, out = run(
        ["uv", "run", "pytest", "--collect-only", "-q", "-o", "addopts="], root
    )
    ids: set[str] = set()
    for line in out.splitlines():
        if "::" in line and line.startswith("tests/"):
            file, _, rest = line.partition("::")
            ids.add(f"{file}::{rest.split('[')[0].split('::')[-1]}")
    return code, ids, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--spec", default="")
    ap.add_argument("--base", default="main")
    args = ap.parse_args(argv)
    try:
        spec = resolve_spec(args.spec) if args.spec else None
        base = resolve_base(args.base)
    except Refused as exc:
        die(exc)
    spec_text = spec.read_text(encoding="utf-8") if spec else None

    results: list[tuple[str, bool, str]] = []

    code, out = run(["make", "test"], ROOT)
    results.append(("test", code == 0, tail(out)))

    code1, out1 = run(["uv", "run", "ruff", "check", "."], ROOT)
    code2, out2 = run(["uv", "run", "ruff", "format", "--check", "."], ROOT)
    results.append(("lint", code1 == 0 and code2 == 0, tail(out1 + out2)))

    code, out = run(["make", "check-docs"], ROOT)
    results.append(("docs", code == 0, tail(out)))

    code, out = run(["make", "check-backing"], ROOT)
    results.append(("backing", code == 0, tail(out)))

    code, out = run(["git", "diff", "--name-only", f"{base}...HEAD"], ROOT)
    diff = set(out.split()) if code == 0 else set()
    if code != 0:
        results.append(
            ("fixtures", False, f"git diff {base}...HEAD failed: {tail(out, 3)}")
        )
    else:
        errs = check_fixtures(spec_text, diff)
        results.append(("fixtures", not errs, "\n".join(errs)))

    if spec_text is not None:
        code, ids, out = collected_tests(ROOT)
        if code != 0:
            results.append(
                ("evidence", False, "pytest --collect-only failed:\n" + tail(out))
            )
        else:
            errs = check_evidence(spec_text, ids, make_targets(ROOT))
            results.append(("evidence", not errs, "\n".join(errs)))
        fails, warns = check_records(spec_text, diff)
        results.append(
            ("records", not fails, "\n".join(fails + [f"WARN {w}" for w in warns]))
        )
    else:
        print("SKIP evidence, records (no SPEC)")

    failed = 0
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        if detail and (not ok or detail.startswith("WARN")):
            for line in detail.splitlines():
                print(f"     {line}")
        failed += not ok
    total = len(results)
    if failed:
        print(f"review-gate FAILED: {failed}/{total} checks")
        return 1
    print(f"review-gate OK: {total}/{total} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
