# Phase 9e — Beat 5: how this was built, and where the rigor lives (PROPOSED)

Contract for the `phase-9e` branch. Source: PROJECT_BRIEF.md §9 Phase 9 ("The
study"), sub-phase 9e of the permanent-artifact-first split (DECISIONS → Phase
9a); brief §2.1 (deterministic first) and §3 Beat 5. Depends on Phase 9d merged
(PR #27, 2026-09-10). Beats 1–4 render; this phase adds Beat 5, the study's
closing part — the checkable facts and the reproducibility counts — and flips
BACKING B5.1 and B5.2 from Pending to Measured.

**Status: APPROVED 2026-09-10 — in progress.** No new dependencies: Beat 5
renders through the 9a/9c contract (`duckdb` + stdlib, hand-written inline SVG);
no script, no new `make` target, no new chart `Kind`. Two new Python-fed marts
(`determinism_facts`, `pipeline_row_counts`), each a DDL-only `.sql` filled by a
writer in `pipeline/build.py`, the same shape as `classifier_quality`, each
single-grain.
Challenged: 2026-09-10, round 1, spec 757bbe04 — rework, all amendments applied (2 BLOCKER, 4 should-fix; one phase kept, reviews_per_month relocated not martified)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

Beat 5 is the study's turn from findings to method: it states the facts a reader
can check for themselves and shows that the whole thing reruns to the same
numbers. Brief §2.1 makes two promises — a language model decides in exactly one
place, and every formula is printed beside its result — and §3 Beat 5 asks the
study to say so plainly and to show its work. Nothing renders it: B5.1 and B5.2
have stood Pending since Phase 0b, waiting (SPEC's own words) "until the pipeline
is complete enough to count." It now is. Beats 3 and 4 render every formula
beside its output; the classifier runs from one module gated against hand
labels; `rebuild()` already computes a per-table row count that
`idempotency-check` diffs. Beat 5 turns those standing facts into two small
panels a reader can audit.

The two rows differ in kind, and the phase treats them differently:

- **B5.1 — the facts you can check** are facts about the repository, not the
  review corpus: how many places a model makes a decision, the count of formulas
  the study defines and displays, the size of the closed set of evidence tags
  every number wears. They are constant whatever data is loaded and whether the
  API key is set, so they are **Measured and not corpus-gated** — they show real
  numbers on the committed synthetic page. Each is counted at build time from the
  code it describes: the model-decision count from the same import-tree walk that
  `tests/test_llm.py::test_only_llm_imports_anthropic` performs (a shared
  helper, so the fact and the guard read one source and the number cannot drift
  from a literal), the formula count from `FORMULAS`/`RULES` bound by a test to
  the formulas the study actually renders, the tag count from `study/model.py::TAGS`.
- **B5.2 — reproducibility** is row counts at each pipeline stage: a
  review-corpus surface like Beat 2. It is **Measured behind the corpus gate** —
  real counts over a captured input, the labelled fixture-state note over the
  frozen synthetic input, "no data yet" over `none` — reusing the Phase 9b gate
  unchanged. The eval scores are B2.4's `classifier_quality` (referenced, not a
  second copy); the one rebuild command is prose.

`pipeline_row_counts` is filled after the classify step, the one write path
`make idempotency-check` does not run (it calls `rebuild()` only) — so, like the
theme marts before it (BACKLOG line 52), its rebuild-stability is proven by a
named `rebuild-then-classify twice` test, not by `idempotency-check`, and that
BACKLOG row grows to name this third classify-path mart.

This phase also removes `pipeline/metrics.py`. Its `reviews_per_month` query is
pipeline health, not a study number, and it has never been on the page; the
Phase 2 BACKLOG row (line 19) worried it would become an orphan mart. The
challenge round settled that a query is **not** an orphan (the orphan rule bites
marts only) and that folding it into `pipeline_row_counts` would make that mart
two-grain — so the query is **relocated** into `pipeline/build.py` beside
`table_counts` (still a printed query, not a mart, its portability lint
re-pointed), `pipeline/metrics.py` is deleted, and `pipeline_row_counts` stays
single-grain.

## The central constraint

**Every Beat 5 number on the page equals a cell of `determinism_facts` or
`pipeline_row_counts`, carries that mart row's own tag, and the B5.1 facts do not
move when reviews or the API key are absent — the page over `ROWS=none` shows the
same B5.1 facts as over `ROWS=synthetic`, B5.2 shows the same corpus-gated state
Beat 2 shows for the same input, and a re-render is byte-identical.** No new chart
kind, no script, no new `make` target moves while Beat 5 renders; the corpus gate
(`_corpus_series`, `_STATE_OF_INPUT`) is reused, not changed; both marts are
single-grain.

## DONE command

```
make review-gate SPEC=specs/phase-9e-beat-5.md && make rebuild ROWS=synthetic && make study && git diff --exit-code
```

- `make review-gate SPEC=…` — the gate green (test, lint, docs, backing,
  fixtures, pins) plus this spec's Evidence ids and Record-update files;
  `tests/test_beat5.py` runs inside `test`, reproducing every pin in
  `tests/pins.py`.
- `make rebuild ROWS=synthetic` — fills the synthetic warehouse the study reads;
  `determinism_facts` filled in `rebuild()` with no key and no reviews,
  `pipeline_row_counts` filled in the classify path.
- `make study && git diff --exit-code` — renders the page and proves it
  byte-identical to the committed `study/friction_ledger.html` (the export's
  determinism, the same check CI runs).

## Done-when

1. **Beat 5 renders.** The page gains a Beat 5 section with panels B5.1 and B5.2,
   added as one `_BEATS` row and a `beat5_panels` builder; the render loop and
   the page shell do not change. *Evidence: row 1.*
2. **B5.1 draws the checkable facts, counted from code.** `determinism_facts` is
   filled in `rebuild()` from the code it describes — the count of modules that
   call the model (via the shared import-tree walk; value 1), the count of
   formula entries the study defines *and* renders, the size of the closed
   evidence-tag set — and B5.1 renders them as a `stat_row`, Measured, not
   corpus-gated, each fact carrying the mart row's tag. Every fact equals the
   quantity it counts, the formula count equals the formulas the Beat 3/4 panels
   actually render, and every fact is unchanged over `ROWS=none`, `synthetic`
   and `captured` and with the key unset. *Evidence: row 2.*
3. **B5.2 draws the reproducibility counts, corpus-gated and rebuild-stable.**
   `pipeline_row_counts` is single-grain — one row per declared pipeline stage,
   each count equal to a direct `count(*)` of that stage's table — filled in the
   classify path; B5.2 renders it as a `table` behind the corpus gate (the
   fixture-state note over the frozen synthetic input, real counts only over a
   captured input), with the eval gate (B2.4) and the one rebuild command named
   in the note. A `rebuild-then-classify twice` test proves its counts unchanged
   on the second run (the guard `idempotency-check` cannot give a classify-path
   mart). *Evidence: row 3.*
4. **No new chart `Kind`, no key, deterministic.** Beat 5 reuses `stat_row` and
   `table`; the page renders with the key unset; every B5.1 fact over `ROWS=none`
   equals its value over `ROWS=synthetic`; B5.2 shows the same gated state Beat 2
   shows for the same input; `make study` is byte-identical on a rerun.
   *Evidence: row 4.*
5. **BACKING B5.1 and B5.2 flip to Measured, `pipeline/metrics.py` is gone.** Both
   rows name their mart, `.sql` and a source cell of the declared shape (the
   repository files the facts are counted from), tag Measured; `make
   check-backing` stays green and no mart is an orphan. `pipeline/metrics.py` is
   deleted, its `reviews_per_month` query relocated to `pipeline/build.py` and
   still printed by `make rebuild`. *Evidence: row 5.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat5.py::test_beat_five_renders_both_panels`; `make study && git diff --exit-code` (DONE command) |
| 2 | `tests/test_beat5.py::test_b51_model_site_count_equals_import_walk`; `tests/test_beat5.py::test_b51_formula_count_equals_rendered_formulas`; `tests/test_beat5.py::test_b51_facts_constant_over_inputs_and_no_key` |
| 3 | `tests/test_beat5.py::test_b52_stage_counts_equal_direct_counts`; `tests/test_beat5.py::test_b52_is_corpus_gated`; `tests/test_beat5.py::test_pipeline_row_counts_stable_across_reclassify` |
| 4 | `tests/test_beat5.py::test_beat_five_no_new_kind`; `tests/test_beat5.py::test_beat_five_render_is_byte_stable` |
| 5 | `make check-backing` (in `make review-gate`); `tests/test_beat5.py::test_backing_b5_rows_measured_no_orphan`; `tests/test_ingest_rebuild.py::test_reviews_per_month_matches_pins` (now importing from `pipeline/build.py`) |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For every number a Beat 5 panel shows, it equals a cell of `determinism_facts` or `pipeline_row_counts` and carries that mart row's `tag`. | `tests/test_beat5.py::test_every_beat_five_number_is_a_tagged_mart_cell` — mutate one mart cell in a scratch DB; the rendered number moves with it, and no cell carries a tag off its row. |
| For every B5.1 fact, its value equals the quantity it counts in the code (the model-site count equals the import-walk result, the formula count equals the formulas the study renders, the tag count equals `len(TAGS)`) and is identical over `ROWS=none`, `synthetic` and `captured` and with the API key unset. | `tests/test_beat5.py::test_b51_model_site_count_equals_import_walk`; `::test_b51_formula_count_equals_rendered_formulas`; `::test_b51_facts_constant_over_inputs_and_no_key` — a fact differs from the quantity it counts, between two inputs, or with the key unset. |
| For B5.2, a fixture input renders the fixture-state note and no counts, `none` renders "no data yet", and counts render only over a captured input — the same gate states Beat 2 shows. | `tests/test_beat5.py::test_b52_is_corpus_gated` — B5.2 renders counts over `synthetic`, or its state disagrees with Beat 2's for the same input. |
| For every declared pipeline stage, `pipeline_row_counts` carries exactly one row whose count equals a direct `count(*)` of that stage's table (single grain — no other grain shares the mart). | `tests/test_beat5.py::test_b52_stage_counts_equal_direct_counts` — a stage missing or doubled, a count that disagrees with the table's own `count(*)`, or a row of a second grain. |
| For `pipeline_row_counts`, a rebuild-through-classify run performed twice leaves every row count unchanged — the idempotency `idempotency-check` cannot prove for a classify-path mart, proven here by a named test. | `tests/test_beat5.py::test_pipeline_row_counts_stable_across_reclassify` — a count changes on the second rebuild-then-classify. |
| For Beat 5, the page renders with the key unset and a re-render of the same marts is byte-identical. | `tests/test_beat5.py::test_beat_five_render_is_byte_stable` — a no-key render errors, or the bytes differ on a second render. |

## Pinned decisions (do not re-litigate)

- **Two marts, two homes, by what the number is about; both single-grain.**
  `determinism_facts` (B5.1) is filled in `rebuild()` beside the model and
  simulator marts — keyless, on every input including `none`, covered by
  `idempotency-check` — and is not corpus-gated, because a repo fact is constant
  whatever data is loaded. `pipeline_row_counts` (B5.2) is filled in the classify
  path (`_do_rebuild` → `_classify_and_print`) after `stg_classified_reviews`
  exists, so it can count the classified stage, and is corpus-gated; because that
  path is outside `idempotency-check`, a `rebuild-then-classify twice` test
  (mirroring `tests/test_theme_share.py::test_rebuild_twice_stable`) proves its
  stability and BACKLOG line 52 grows to name it. Rejected: one mart for both —
  they differ in gate and in fill site; filling B5.2 inside `rebuild()` — the
  classified stage is not built yet there. Satisfies invariants 2, 3, 4, 5.
- **B5.1 facts are build-time counts of the code, each bound to its guard.** The
  model-decision count is the length of the import-tree walk that
  `tests/test_llm.py::test_only_llm_imports_anthropic` already performs — extracted
  to a shared helper so the fact is counted, not a literal, and cannot drift from
  the guard that keeps it 1 (Classification contract: one model call site,
  `classify/llm.py`). The formula count is `len(FORMULAS) + len(RULES)`, bound by
  a test to the number of formula entries the Beat 3/4 panels render, so
  "defined" equals "displayed" (SPEC B5.1: "every formula displayed next to its
  output"). The tag count is `len(study/model.py::TAGS)`. All Measured — measured
  facts about the repository, whose upstream source is the code they are counted
  from (a backticked repo path, the `check_backing` `_DATASET` shape), the
  study's subject here being the repository itself. Rejected: a prose/hero panel
  with no numbers — SPEC B5.1's tag is Measured, and a counted fact cannot drift
  where a sentence can; a bare literal `1` — the challenge showed it would carry
  a "cannot drift" claim no constant backs. Satisfies invariant 2.
- **B5.2 renders the row counts; the eval scores are B2.4, referenced not
  duplicated; the rebuild command is prose.** SPEC B5.2 names three contents; the
  new one is the stage counts (the mart). The eval scores already render as B2.4
  (`classifier_quality`) — B5.2's note points to that panel rather than drawing a
  second copy — and the one command that rebuilds everything is `make rebuild`,
  named in the note as text (no number). Rejected: a second eval table — one
  system, no duplication (`dataviz`); a live "Day N" or clock figure — the
  writing rules forbid it. Satisfies the SPEC row without a new number source.
- **No new chart `Kind` — the 9a/9c contract is reused.** B5.1 is a `stat_row`
  (the three fact cells), B5.2 is a `table` (stage × count, corpus-gated the way
  B2.4's table is). Rejected: a new "facts" or "counts" kind — `stat_row` and
  `table` already fit; the dullest way.
- **`pipeline/metrics.py` is deleted and its query relocated, not martified;
  `pipeline_row_counts` stays single-grain.** `reviews_per_month` is pipeline
  health, never on the page; the challenge settled that a query is not an orphan
  (the orphan rule bites marts only) and that folding it into
  `pipeline_row_counts` would make that mart two-grain (stage×count plus
  source×month). So the query moves to `pipeline/build.py` beside `table_counts`,
  its portability lint (`tests/test_sql_portable.py`) re-points to the new
  location, `make rebuild` still prints it, and `pipeline/metrics.py` is deleted.
  BACKLOG line 19 is struck: the module is gone and the orphan risk it named
  never materialises (no mart is created for the query). Rejected: fold into
  `pipeline_row_counts` — a two-grain mart, orphan-shaped and half-unrendered
  (challenge #6); a new single-grain `reviews_by_month` mart — a third mart plus
  a BACKING row for a non-study number, worse for scope. Satisfies invariant 4.
- **Beat 5 display text lives in `study/text.py` as data.** The three fact
  labels, the B5.2 stage display names, the B5.2 note (the eval-gate pointer and
  the `make rebuild` command string), and every blurb are data beside the Beat
  1–4 texts. Rejected: literals in `panels.py` — text-as-data is the 9c split.
  Satisfies invariant 1.

## Scope (files)

- `specs/phase-9e-beat-5.md` — this spec.
- `sql/marts/determinism_facts.sql` — DDL-only; the header names the grain (one
  row per checkable fact), the provenance columns and B5.1.
- `sql/marts/pipeline_row_counts.sql` — DDL-only; the header names the grain (one
  row per pipeline stage — single grain), the provenance columns and B5.2.
- `pipeline/build.py` — `write_determinism_facts` (called in `rebuild()`),
  `write_pipeline_row_counts` (called in the classify path); the shared
  import-walk helper (or its reuse) behind the model-site fact; the two marts
  added wherever `classifier_quality` is handled in the marts loop; the relocated
  `REVIEWS_PER_MONTH` / `reviews_per_month` (moved from `pipeline/metrics.py`,
  beside `table_counts`).
- `pipeline/cli.py` — `_classify_and_print` calls `write_pipeline_row_counts`;
  the reviews-per-month import re-points to `pipeline/build.py`.
- `pipeline/metrics.py` — **deleted** (its query relocated to `pipeline/build.py`).
- `study/panels.py` — `beat5_panels`; the `determinism_facts` reader and the
  corpus-gated `pipeline_row_counts` reader; the two marts added to the
  read-column allowlist and (for B5.2) to the corpus-gate mart set; the stale
  `pipeline/metrics.py` mention at line 113 re-pointed to the query's new home.
- `study/export.py` — one `_BEATS` row for Beat 5; `_metric_cell` omits the
  empty `(detail)` count span so B5.2's plain stage counts render as a bare value
  (B2.4 always carries a detail, so its bytes are unchanged).
- `study/text.py` — the Beat 5 display texts (fact labels, stage names, the B5.2
  note with the rebuild command, the blurbs).
- `study/model.py` — only if a Beat 5 label or absence word is needed the
  contract does not already carry (expected: none).
- `study/friction_ledger.html` — the regenerated committed page.
- `tests/test_beat5.py` — the phase's tests (Evidence rows above).
- `tests/pins.py` — the Beat 5 pinned numbers.
- `tests/test_ingest_rebuild.py` — the `reviews_per_month` import re-points to
  `pipeline/build.py` (the tests themselves unchanged).
- `tests/test_sql_portable.py` — the `REVIEWS_PER_MONTH` import re-points to
  `pipeline/build.py` (the portability/clock lint of that query text preserved
  at its new home).
- `tests/test_beat2.py` — the `monkeypatch.setattr(cli, "reviews_per_month", …)`
  target confirmed still resolvable after the relocation (cli re-exports it).
- `tests/test_rules.py` — the `test_no_new_mart` pinned mart-file set gains the
  two Beat 5 marts.
- `tests/test_rebuild.py` — `test_zero_row_rebuild`'s by-construction exception
  set gains `determinism_facts` (fills in `rebuild()`); `pipeline_row_counts`
  stays in the empty group (classify-path).
- `tests/test_llm.py` — `test_only_llm_imports_anthropic` reuses
  `pipeline.build.model_call_sites` (the shared walk B5.1 counts from).
- `BACKING.md`, `SPEC.md`, `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`,
  `docs/PLAN.md` — records (below).

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9e entry (the two single-grain marts and their two
  homes; B5.1 facts as build-time counts bound to their guards; B5.2
  corpus-gated with the eval scores referenced not copied and stability proven by
  a named test not `idempotency-check`; `reviews_per_month` relocated not
  martified and `pipeline/metrics.py` deleted). A supersede pointer on the
  existing entry at line 685 ("Reviews per month is a query, not a mart") — the
  module is gone, the query lives in `pipeline/build.py`.
- [ ] `BACKLOG.md` — line 19 (`reviews_per_month` … not a mart) struck (DONE
  Phase 9e — module deleted, query relocated, no mart made); line 52 (classify
  step outside `idempotency-check`) extended to name `pipeline_row_counts` as the
  third uncovered classify-path mart, its stability proven by
  `test_pipeline_row_counts_stable_across_reclassify`; count decremented; the
  9f/9g rows stand.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then
  backtick it and the fix commit writes the row. (The `site-fix` open class is
  the reason the deletion's full reference set is enumerated in Scope.)
- [ ] `CLAUDE.md` — Current status; Repo map (`study/` renders Beats 1–5; the two
  new single-grain Python-fed marts named beside `classifier_quality`;
  `pipeline/metrics.py` removed and the `reviews_per_month` mention re-pointed to
  `pipeline/build.py`); BACKLOG count.
- [ ] `BACKING.md` — B5.1 → `determinism_facts` / `sql/marts/determinism_facts.sql`
  / source `` `classify/llm.py`; `models/cost_model.py`; `study/model.py` `` /
  Measured; B5.2 → `pipeline_row_counts` / `sql/marts/pipeline_row_counts.sql` /
  source `` `pipeline/build.py` `` / Measured.
- [ ] `SPEC.md` — the "(Pending until …)" clauses on B5.1/B5.2 removed now that
  they render (a wording reconciliation, not a design change).
- [ ] README — none (the README is Phase 9f).
- [ ] `docs/PLAN.md` — the stale line-239 mention ("the metric is a pinned query
  in `pipeline/metrics.py` … until B5.2 lands") updated: B5.2 landed; the query
  lives in `pipeline/build.py`, still not a mart.
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches the
network. Beat 5 renders through the existing `make study` (no variable,
byte-identical, no key, no fetch); the two marts fill through the existing
`make rebuild` path. Deleting `pipeline/metrics.py` is a source-file removal (the
query relocated, its lint re-pointed), not a `make`-target delete of data.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `sql/**`, `pipeline/**`, `tests/`):
  deterministic-first, one-number-one-tag provenance, formulas/text as data, the
  two new marts' SQL is ANSI and portable (no reader function, no clock), the
  read-column allowlist, that B5.1 is not corpus-gated by design and B5.2 is, both
  marts single-grain, the `metrics.py` deletion leaves no dangling import and the
  relocated query keeps its portability lint; then this spec's Invariants.
- **security-reviewer** (not triggered — no CI, `.env`, credentials, network,
  paid API, hooks, settings or destructive `make` target in the range; the
  `metrics.py` deletion is a source file, not a data-delete target).
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  command, the fact-equals-code and stage-count-equals-direct-count tests, the
  `rebuild-then-classify twice` stability test, the no-key/`ROWS=none` run, the
  corpus-gate states, idempotency, the byte-identical study, and that
  `pipeline/metrics.py` is gone with its reviews count still printed and still
  portability-linted.
- **study-editor** (triggered — `study/` prose, `SPEC.md`, `CLAUDE.md`,
  `docs/PLAN.md` change): the Beat 5 blurbs and note for the two-layer rule,
  neutrality (no insurer named), the "facts you can check" voice, and no banned
  word.
- **coherence-auditor** at exit (mandatory, whole repo): SPEC Beat 5 ↔ BACKING B5
  rows ↔ the two marts ↔ the Beat 5 panels; the stale "Beats 1–4 render",
  `pipeline/metrics.py` and "until B5.2 lands" mentions gone across CLAUDE.md,
  `study/panels.py` and `docs/PLAN.md`; the closed/extended BACKLOG rows; forward
  coherence to 9f (README, the stranger acceptance test, the live-slider decision)
  and 9g (Metabase).
- Stack risk: `information_schema` row-count reads are the shape `table_counts`
  already uses — verify the new marts' own rows do not count themselves into a
  moving target (each fill runs once, after the other tables, over a fixed list).
  Confirm `pipeline_row_counts` fills over `ROWS=synthetic` in the classify path
  but stays empty on the `rebuild()`-only `idempotency-check` path without
  breaking that target's count diff (an empty table is 0 both runs), and that the
  `rebuild-then-classify twice` test is the guard that path cannot be.
  DuckDB binds Python `None` into a typed column as SQL NULL (Phase 8a Gotcha) —
  the fact/count writers write no NULLs. Check the official DuckDB docs before any
  workaround; a surprise goes to DECISIONS → Gotchas.

## Out of scope (deferred, recorded)

- The README, the stranger acceptance test, and the live-slider decision (Phase
  9f, BACKLOG lines 72/73).
- The published study's captured corpus render — B5.2 shows the fixture note on
  the committed synthetic page, like B2.2/B2.4/B2.5 (Phase 9f, BACKLOG line 69).
- The Metabase review-level drill demonstration (Phase 9g, BACKLOG).
- A B5.1 fact that scans the rendered page for untagged numbers — self-referential
  and unnecessary; `check_panel` already enforces one tag per number, so the
  tag-count fact stands in for that guarantee, not a page scan.
