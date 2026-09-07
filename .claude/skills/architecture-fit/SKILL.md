---
name: architecture-fit
description: The architecture standard for this repo, applied before adding a module, table, mart, make target, dependency, document or phase — which layer, which BACKING row, which contract and its pinning test, the duller alternative, the maintenance cost, determinism, invariants before mechanisms, the DECISIONS entry, forward coherence. Loads while a spec, a mart or a new module is being written; the senior-architect is preloaded with the same text.
user-invocable: false
paths:
  - "specs/**"
  - "sql/marts/**"
  - "sql/staging/**"
  - "models/**"
  - "study/**"
  - "dags/**"
  - "Makefile"
  - "pyproject.toml"
  - "BACKING.md"
  - "SPEC.md"
  - "DECISIONS.md"
---

Standing questions before anything new is added. Answer each in the spec or
the file header; an unanswered one is a finding the senior-architect will
raise.

## The ten questions

1. **Which layer.** `ingest/` (captures, parsers), `sql/raw` (as-scraped,
   provenance), `sql/staging` (clean, deduped), `sql/marts` (study-ready),
   `classify/` (rules, one model call, eval), `opendata/` (public data, the
   fit), `pipeline/` (the one warehouse seam, the build, the validating CLI,
   the SQL lint), `models/` (formulas as data, the simulator), `study/`
   (render only), `dags/` (no logic), `scripts/` (guards), `tests/`. A piece
   that fits two
   layers is two pieces; a piece that fits none is out of scope.
2. **Which part of the study.** Name the beat and the chart it surfaces in
   (SPEC.md). A feature that surfaces in none of the five parts is not built
   (CLAUDE.md → Workflow rules).
3. **Which BACKING row.** The row id, its tag now and after; a claim with no
   row is rewritten or gets a Pending row first (brief §8). `make
   check-backing` must stay green.
4. **Which contract, which test.** Provenance, evidence, classification,
   portability, neutrality — name the one touched and the test that pins it.
5. **The duller way.** Plain SQL, stdlib, an existing `make` target, a
   BACKLOG row. A new package is a STOP. A framework for eight SQL files, a
   config layer for one value, a plugin system, a second model call site, a
   fourth document, transformation logic inside an Airflow operator, pandas
   on a pipeline path: refused (DECISIONS "still in force").
6. **Maintenance cost (brief §2.2).** What breaks if this is deleted in a
   year? What does it force every later phase to carry? If the answer is
   "nothing" and "nothing", it may not be worth adding either.
7. **Determinism.** Re-run, no key, equal sort keys, the other engine: can
   the answer differ? Which test proves it cannot?
8. **Invariant first, mechanism second.** Write the property ("for every
   review already classified, a re-run changes nothing") and its falsifying
   scenario test before naming the mechanism ("a status column"). A spec's
   Invariants section holds properties only.
9. **The record.** A non-obvious choice gets a DECISIONS entry (the two
   alternatives not taken, one line each); a deferred one gets a BACKLOG row
   with a trigger; a stack surprise goes to Gotchas after the official doc
   was read.
10. **Forward coherence.** Does the next phase (brief §9, split in
    `docs/PLAN.md` §5) find what it needs — the columns, the marts, the
    targets — or an assumption it breaks?

## Shapes this repo keeps

- Raw is append-only on natural key + content hash; staging dedupes; marts
  are one file per table with a header naming grain, provenance and rows.
- A Python-fed mart has a DDL-only `.sql` (the shape) and one writer in
  `pipeline/build.py`, excluded from the generic marts loop, run by the step
  that owns it.
- A source is one declaration in `ingest/sources.py`; a formula or a
  simulator rule is one entry in `models/cost_model.py::FORMULAS` or
  `models/guardrail_sim.py::RULES`; a label is one of seven; a dialect
  difference lives in `pipeline/warehouse.py`.
- A phase is one branch, one spec (≤ ~6 Done-when items, the four REQUIRED
  sections), one DONE command, one PR; the spec is the first commit; a
  fixture changes only with a `Freeze:` line and a DECISIONS entry.

## Writing the spec

- Central constraint: one bolded sentence naming what must not move.
- Done-when items are clauses the code can falsify, each with an Evidence
  row naming a test id or a `make` target that exists.
- Threat model: a row per target that takes a variable, deletes, pays or
  fetches; the five cells; a named test per cell.
- Record updates: every file the phase implies (CLAUDE.md status and
  commands, SPEC.md, BACKING.md tags, DECISIONS, BACKLOG count, LESSONS rows,
  README).
