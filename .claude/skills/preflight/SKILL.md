---
name: preflight
description: Pre-review self-check on the current branch, after the build and before /review-round 1 — run make check-pins, then walk every public symbol the range added or changed with one fixed row (its pinning test, each foreign input's declared shape, the other names the diff or the docs give the same concept, the LESSONS class it could repeat), list the record files the diff implies, print, then STOP. Read-only, report-only; the same checklist the reviewers apply, run by the author first.
# On request only: the developer types /preflight; the model never invokes it.
disable-model-invocation: true
---

Run the pre-review self-check on the current branch. Read-only and
report-only: no edits, no fixes, no commits. The output is a table the
developer reads before spending a review round; a red row is fixed in the
main session, on the developer's word, before `/review-round 1`.

## 1. The range

`git diff --name-only main...HEAD`. On `main`, or with an empty range, print
one line — `preflight: nothing since main` — and STOP.

## 2. The mechanical half

Run `make check-pins` and paste its lines. It names every public function or
class the range added or changed under a code package that no test names (a
new one must be named by a test file the range changed) and every new mart
file no changed test names. Red here is red below, whatever the table says.

## 3. The lessons in force

Read `LESSONS.md`: the rows whose Status is `open` are the finding classes
that reached a review round before and have no mechanism yet. Each is a
column-4 question below. A `promoted` row is already a check or a standard
sentence; do not re-ask it.

## 4. One row per changed symbol

For every public symbol `check-pins` considers (added or changed, under
`models/`, `pipeline/`, `classify/`, `ingest/`, `opendata/`, `study/`, `dags/`,
`scripts/`, `.claude/hooks/`) and every changed file under `sql/`:

| Symbol | Pinning test | Foreign inputs → declared shape | Same concept, other names | Lesson class risked |
|---|---|---|---|---|

- **Pinning test** — `tests/<file>.py::test_<name>`, the one that fails if
  the symbol's behaviour changes; `check-pins` proves a name is mentioned,
  this column proves the behaviour is asserted. "none" is a red row.
- **Foreign inputs → declared shape** — each input the repo does not own
  that the symbol reads (a page, a reply, a CLI variable, a file under
  `data/`, hook stdin, an env var) and the closed set, anchored regex or
  bounded parse that accepts it, or "none read". An input with no shape is
  a red row (code-craft → Guards).
- **Same concept, other names** — grep the diff, `SPEC.md`, `BACKING.md`,
  the spec and the mart headers for the quantity or rule this symbol
  names; list every distinct name found. Two names for one concept is a
  red row; the canonical one is the mart's or BACKING's.
- **Lesson class risked** — the open LESSONS row this symbol could repeat,
  and in one clause why it does not; or "—".

## 5. The records the diff implies

List the record files in the range (`CLAUDE.md`, `DECISIONS.md`,
`BACKLOG.md`, `LESSONS.md`, `SPEC.md`, `BACKING.md`, the spec) beside the
ones the change implies: a new target → `CLAUDE.md` Commands and `make help`;
a mart or a tag change → `BACKING.md` and `SPEC.md`; a workaround → a
DECISIONS Gotcha; a deferral → a BACKLOG row; a fix from a review round → a
LESSONS row. Missing is a red row.

## 6. Verdict, then STOP

One line: `preflight clean — /review-round 1` or `preflight: <n> red rows —
fix before /review-round 1`, then the red rows repeated. Do not fix anything;
the developer decides which rows to act on (CLAUDE.md → STOP-on-findings
holds for the author's own findings too).
