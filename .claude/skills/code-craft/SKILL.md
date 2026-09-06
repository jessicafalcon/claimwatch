---
name: code-craft
description: The senior craft standard for this repo's Python, SQL, Makefile and tests — the ladder (spec, reuse, stdlib, the engine, an installed dependency, one line, the minimum), naming by meaning, function shape, guards at foreign inputs, error policy, data shapes across boundaries, duplication versus speculation, constants, comments, types, SQL and test quality. Loads while code is being written; the code-reviewer is preloaded with the same text.
user-invocable: false
paths:
  - "**/*.py"
  - "sql/**"
  - "classify/rules.yaml"
  - "Makefile"
  - "tests/**"
---

Standing instructions while writing code here. CLAUDE.md's rules come first
(deterministic first, the five contracts, the allowlist); this is the craft
under them. Where a bar below conflicts with a spec's pinned decision, the
spec wins and the conflict is reported.

## Before writing: the ladder

Code that is not written cannot break. Understand the change first (read
the task, the spec item, every file it touches, the real flow), then stop at
the first rung that holds:

1. **Does the spec ask for it?** Not in a Done-when item → not built. If a
   Done-when item itself looks unnecessary, that is a STOP-and-report
   (Workflow rules), never a silent skip: the spec is the contract.
2. **Already here?** A helper, a guard, a dataclass, a make target, a fixture
   a few files over → reuse it. Re-implementing what exists is the most
   common finding.
3. **Stdlib does it?** `csv`, `json`, `hashlib`, `dataclasses`, `pathlib`,
   `statistics`, `functools`, `itertools`.
4. **The engine does it?** A SQL constraint, a `distinct`, a `group by`
   over a Python loop; a DuckDB catalog query over a hand-parsed file.
5. **An installed dependency does it?** `duckdb`, `pyyaml`, `httpx`,
   `anthropic`, nothing else (Conventions: a new package is a STOP).
6. **One line?** Then one line.
7. **Only then** the minimum that passes the test.

Two rungs work → take the higher one. Two stdlib forms, same size → the one
that is right on the edge case: fewer lines, never a weaker algorithm.

A bug fix is a root cause: grep every caller of the function before editing
and fix the shared function once (one guard there is a smaller diff than one
per caller, and it does not leave a sibling caller broken).

A deliberate simplification with a known ceiling (a linear scan, a single
lock, a naive heuristic) is a BACKLOG row with its trigger, not a comment:
the row is where deferrals are counted and reviewed at each phase exit.

Not lazy about: understanding the problem; guards at inputs the repo does not
own; the error policy; the pinning test (one focused test per behaviour, no
more); anything the spec names. The explanation is held to the same bar: after
the code, at most three lines — what was skipped and when to add it.

## Naming by meaning (brief §2.3)

- A name says what a thing means, not what it is: `held_claim_share`, not
  `pct_col3`; `write_classified_reviews`, not `process`.
- Functions start with a verb; a predicate reads as a question
  (`is_fetchable`, `has_snapshot`).
- Tests state the behaviour and the condition:
  `test_rebuild_twice_changes_no_row_count`, never `test_rebuild_works`.
- The only abbreviations are the study's own (`B2.4`, `raw_`, `stg_`) and
  the source's own column names (`PRS_REM_MNT`, kept verbatim so a reader
  can find them in the source).

## Function shape

- One job per function. A function that reads, decides and writes is three.
- Signals, not verdicts: ~40 lines, 4 parameters, 3 levels of nesting. Past
  a signal, either split or write the one-line reason it stays whole.
- No boolean flag parameter. Two functions, or an argument from a closed
  set (`Literal[...]` / an enum) whose name says what it means.
- Early return over nesting. Validate at the top; the happy path is flat.
- A return value means one thing. `None` for "not run" and `None` for
  "unclassified" in the same function is a bug waiting; `unclassified` is a
  label, not an absence.
- Inputs are not mutated. Declarations and rows are frozen dataclasses
  (`ingest/sources.py`, `ingest/parsed.py` set the pattern).

## Guards at inputs the repo does not own

Foreign inputs: a scraped page, a robots file, the model's reply, a DAMIR
row, a CLI variable, hook stdin, an env var, a file name under `data/cache/`.

- Accept a closed set or a declared shape (an anchored regex, a typed parse,
  a bounded integer) and refuse everything else by NAME — never by coercing
  to the nearest valid value.
- No `.get(…, default)` on foreign JSON; no `try: int(x) except: 0`.
- Refuse loudly at the process boundary: exit 2 with one line naming the
  input, or `ValueError` naming the field. The three hooks under
  `.claude/hooks/` are the documented fail-opens, each listing its cases in
  its header; a new fail-open needs the same.
- Fix the class, not the case: a denylist, a regex of bad cases or a
  special-case branch is refused; the mechanism's KIND changes (closed set,
  strict parse, derived value).

## Error policy

- No bare `except`, no `except Exception`, no swallowed exception, no
  exception downgraded to a `print`.
- An error message carries the NAME of what failed (file, column, variable,
  source slug) and at most the shape or length of a foreign value; never a
  review body, a person, a key.
- Exceptions inside the library, exit codes only at the process boundary
  (`pipeline/cli.py`, the scripts).
- The paid path raises one typed error with one line (`ModelError`), never
  a traceback.

## Data shapes across a boundary

- A row or a declaration crossing a module boundary is a frozen dataclass or
  a `TypedDict`, not a `dict[str, Any]` or a tuple with positional meaning.
- Values that always travel together are one type (the four provenance
  columns; a snapshot's five figures).
- A caller does not reach into another module's dict layout; it asks a
  function. No `a.b().c().d()` chains.

## Duplication versus speculation (both are findings)

- The same SQL fragment in two marts → a staging table. The same guard in two
  CLIs → one function in the shared module. A label set, a column list or a
  threshold written twice → one declaration imported twice.
- No parameter, branch, abstraction or config layer for a case that does not
  exist yet (brief §2.2: every tool earns its maintenance cost). A second
  case that is not in a spec is a BACKLOG row, not an `if`.

## Constants

- A bare number or string a reader cannot source is named, and either
  carries its source in the comment (a URL, a brief §) or is pinned in
  `tests/pins.py`. Model defaults follow the parameter rule (sourced, or
  declared unsourced in code).

## Comments and docstrings

- A comment says why, never what. Commented-out code is deleted.
- Docstrings are one line unless the behaviour is non-obvious.
- The SQL header comment (grain, provenance columns, BACKING rows fed) is
  required; it is the one comment a file must have.

## Types

- Hints on every public function and every dataclass field. `Any` at a
  boundary is a guard that has not been written yet.

## SQL

- One file, one table. Lowercase keywords. Explicit column lists — no
  `select *` in a staging table or a mart. CTEs named by meaning. No
  `order by` in a table definition. No dialect form, no regex, no clock
  (`pipeline/sql_lint.py` pins it). Pattern-matching lives in `rules.yaml`
  and Python.

## Makefile

- One-line recipes. A variable is validated in Python, reaches it through
  `$(call _Q,$(value VAR))`, is `unexport`ed, and never becomes a path by
  concatenation. A destructive, paid or fetching target is armed only by the
  `confirm` goal in the same invocation.

## Tests

- One behaviour per test; arrange, act, assert; the name states the
  behaviour. One focused test per stated behaviour, sized like the
  neighbouring test files.
- A test that re-implements the code under test proves nothing; assert on
  outputs and pinned numbers (`tests/pins.py` holds every pinned number).
- No network, no service, no key; `tmp_path` never `data/`; fixtures are
  read-only.
- Scratch checks run and are thrown away; they are not committed as tests.
- Every new write path, rule or formula: "can it answer differently on
  re-run, with the key unset, with equal sort keys?" — name the test that
  pins the answer.
