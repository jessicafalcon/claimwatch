# Phase 9e — Beat 5: how this was built, and where the rigor lives (PROPOSED)

Contract for the `phase-9e` branch. Source: PROJECT_BRIEF.md §9 Phase 9 ("The
study"), sub-phase 9e of the permanent-artifact-first split (DECISIONS → Phase
9a); brief §2.1 (deterministic first) and §3 Beat 5. Depends on Phase 9d merged
(PR #27, 2026-09-10). Beats 1–4 render; this phase adds Beat 5, the study's
closing part — the checkable facts and the reproducibility counts — and flips
BACKING B5.1 and B5.2 from Pending to Measured.

**Status: PROPOSED — do not start until approved.** No new dependencies: Beat 5
renders through the 9a/9c contract (`duckdb` + stdlib, hand-written inline SVG);
no script, no new `make` target, no new chart `Kind`. Two new Python-fed marts
(`determinism_facts`, `pipeline_row_counts`), each a DDL-only `.sql` filled by a
writer in `pipeline/build.py`, the same shape as `classifier_quality`.

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
  review corpus: one place a model makes a decision, the count of formulas the
  study displays, the closed set of evidence tags every number wears. They are
  constant whatever data is loaded and whether the API key is set, so they are
  **Measured and not corpus-gated** — they show real numbers on the committed
  synthetic page — and each is counted at build time from a code constant, so a
  displayed fact cannot drift from the code it describes.
- **B5.2 — reproducibility** is row counts at each pipeline stage: a
  review-corpus surface like Beat 2. It is **Measured behind the corpus gate** —
  real counts over a captured input, the labelled fixture-state note over the
  frozen synthetic input, "no data yet" over `none` — reusing the Phase 9b gate
  unchanged. The eval scores are B2.4's `classifier_quality` (referenced, not a
  second copy); the one rebuild command is prose.

Landing `pipeline_row_counts` also closes a standing BACKLOG row: the
`reviews_per_month` query in `pipeline/metrics.py` is pipeline-health with no
BACKING row of its own (an orphan under BACKING's rule). It folds into this mart
under B5.2 and `pipeline/metrics.py` is deleted.

## The central constraint

**Every Beat 5 number on the page equals a cell of `determinism_facts` or
`pipeline_row_counts`, carries that mart row's own tag, and the B5.1 facts do not
move when reviews or the API key are absent — the page over `ROWS=none` shows the
same B5.1 facts as over `ROWS=synthetic`, B5.2 shows the same corpus-gated state
Beat 2 shows for the same input, and a re-render is byte-identical.** No new chart
kind, no script, no new `make` target moves while Beat 5 renders; the corpus gate
(`_corpus_series`, `_STATE_OF_INPUT`) is reused, not changed.

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
   filled in `rebuild()` from code constants — the one model-decision module
   (value 1), the number of formula entries the study displays, the size of the
   closed evidence-tag set — and B5.1 renders them as a `stat_row`, Measured,
   not corpus-gated, each fact carrying the mart row's tag. Every fact equals its
   code constant and is unchanged over `ROWS=none`, `synthetic` and `captured`.
   *Evidence: row 2.*
3. **B5.2 draws the reproducibility counts, corpus-gated.** `pipeline_row_counts`
   is filled in the classify path with one row per declared pipeline stage (each
   count equal to a direct count of that stage's table) plus the per-(source,
   month) review breakdown folded in from `pipeline/metrics.py`; B5.2 renders it
   as a `table` behind the corpus gate — the fixture-state note over the frozen
   synthetic input, real counts only over a captured input — with the eval gate
   (B2.4) and the one rebuild command named in the note. `pipeline/metrics.py` is
   deleted. *Evidence: row 3.*
4. **No new chart `Kind`, no key, deterministic.** Beat 5 reuses `stat_row` and
   `table`; the page renders with the key unset; every B5.1 fact over `ROWS=none`
   equals its value over `ROWS=synthetic`; B5.2 shows the same gated state Beat 2
   shows for the same input; `make study` is byte-identical on a rerun.
   *Evidence: row 4.*
5. **BACKING B5.1 and B5.2 flip to Measured.** Both rows name their mart and
   `.sql`, tag Measured; `make check-backing` stays green and no mart is an
   orphan (the two new marts each carry a row; `reviews_per_month` no longer
   exists to be one). *Evidence: row 5.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat5.py::test_beat_five_renders_both_panels`; `make study && git diff --exit-code` (DONE command) |
| 2 | `tests/test_beat5.py::test_b51_facts_equal_code_constants`; `tests/test_beat5.py::test_b51_facts_constant_over_inputs_and_no_key` |
| 3 | `tests/test_beat5.py::test_b52_stage_counts_equal_direct_counts`; `tests/test_beat5.py::test_b52_is_corpus_gated`; `tests/test_beat5.py::test_reviews_per_month_folded_and_metrics_module_gone` |
| 4 | `tests/test_beat5.py::test_beat_five_no_new_kind`; `tests/test_beat5.py::test_beat_five_render_is_byte_stable` |
| 5 | `make check-backing` (in `make review-gate`); `tests/test_beat5.py::test_backing_b5_rows_measured_no_orphan` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For every number a Beat 5 panel shows, it equals a cell of `determinism_facts` or `pipeline_row_counts` and carries that mart row's `tag`. | `tests/test_beat5.py::test_every_beat_five_number_is_a_tagged_mart_cell` — mutate one mart cell in a scratch DB; the rendered number moves with it, and no cell carries a tag off its row. |
| For every B5.1 fact, its value equals the code constant it counts and is identical over `ROWS=none`, `synthetic` and `captured` and with the API key unset. | `tests/test_beat5.py::test_b51_facts_constant_over_inputs_and_no_key` — a B5.1 fact differs between two inputs, differs with the key unset, or differs from the constant. |
| For B5.2, a fixture input renders the fixture-state note and no counts, `none` renders "no data yet", and counts render only over a captured input — the same gate states Beat 2 shows. | `tests/test_beat5.py::test_b52_is_corpus_gated` — B5.2 renders counts over `synthetic`, or its state disagrees with Beat 2's for the same input. |
| For every declared pipeline stage, `pipeline_row_counts` carries exactly one stage row whose count equals a direct `count(*)` of that stage's table, and the review breakdown carries one row per (source, month). | `tests/test_beat5.py::test_b52_stage_counts_equal_direct_counts` — a stage missing or doubled, or a count that disagrees with the table's own `count(*)`. |
| For Beat 5, the page renders with the key unset and a re-render of the same marts is byte-identical. | `tests/test_beat5.py::test_beat_five_render_is_byte_stable` — a no-key render errors, or the bytes differ on a second render. |

## Pinned decisions (do not re-litigate)

- **Two marts, two homes, by what the number is about.** `determinism_facts`
  (B5.1) is filled in `rebuild()` beside the model and simulator marts —
  keyless, on every input including `none`, covered by `idempotency-check` — and
  is not corpus-gated, because a repo fact is constant whatever data is loaded.
  `pipeline_row_counts` (B5.2) is filled in the classify path (`_do_rebuild` →
  `_classify_and_print`) after `stg_classified_reviews` exists, so it can count
  the classified stage, and is corpus-gated. Rejected: one mart for both — they
  differ in gate and in fill site; filling B5.2 inside `rebuild()` — the
  classified stage is not built yet there. Satisfies invariants 2, 3, 4.
- **B5.1 facts are build-time counts from code constants, not prose.** Three
  facts, each a count read from the code it describes: the one module that calls
  the model (`classify/llm.py` — value 1), the number of formula entries the
  study displays (`models/cost_model.py::FORMULAS` and
  `models/guardrail_sim.py::RULES`), and the size of the closed evidence-tag set
  (`study/model.py::TAGS`). Rendered Measured. Rejected: a prose/hero panel with
  no numbers — SPEC B5.1's tag is Measured, and a counted fact cannot drift from
  the code, where a sentence can. Satisfies invariant 2.
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
- **`reviews_per_month` folds into `pipeline_row_counts`; `pipeline/metrics.py`
  is deleted.** The per-(source, month) review counts become rows of the B5.2
  mart (grain: one row per stage, and one per source×month for the review
  breakdown), so a claim that had no BACKING row now sits under B5.2, and the
  orphan-risk module is gone. `make rebuild`'s "reviews per month" print reads
  the mart. Rejected: leaving `pipeline/metrics.py` — the orphan risk the BACKLOG
  row named persists, and two places would count reviews per month. Closes
  BACKLOG "`reviews_per_month` is a query … not a mart".
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
  row per stage, one per source×month review row), the provenance columns and
  B5.2.
- `pipeline/build.py` — `write_determinism_facts` (called in `rebuild()`) and
  `write_pipeline_row_counts` (called in the classify path); the two marts added
  wherever `classifier_quality` is handled in the marts loop.
- `pipeline/cli.py` — `_classify_and_print` calls `write_pipeline_row_counts`;
  the "reviews per month" print reads the mart, not `pipeline/metrics.py`.
- `pipeline/metrics.py` — deleted (its reviews-per-month query folded into the
  mart writer).
- `study/panels.py` — `beat5_panels`; the `determinism_facts` reader and the
  corpus-gated `pipeline_row_counts` reader; the two marts added to the
  read-column allowlist and (for B5.2) to the corpus-gate mart set.
- `study/export.py` — one `_BEATS` row for Beat 5.
- `study/text.py` — the Beat 5 display texts (fact labels, stage names, the B5.2
  note with the rebuild command, the blurbs).
- `study/model.py` — only if a Beat 5 label or absence word is needed the
  contract does not already carry (expected: none).
- `study/friction_ledger.html` — the regenerated committed page.
- `tests/test_beat5.py` — the phase's tests (Evidence rows above).
- `tests/pins.py` — the Beat 5 pinned numbers.
- `tests/test_ingest_rebuild.py` — the reviews-per-month assertion updated to
  read the mart (was `pipeline/metrics.py`).
- `BACKING.md`, `SPEC.md`, `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md` — records
  (below).

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9e entry (the two marts and their two homes, B5.1
  facts as build-time counts, B5.2 corpus-gated with the eval scores referenced
  not copied, `reviews_per_month` folded and `pipeline/metrics.py` deleted).
- [ ] `BACKLOG.md` — row "`reviews_per_month` is a query in `pipeline/metrics.py`,
  not a mart" struck (DONE Phase 9e); count decremented; the 9f/9g rows stand.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then
  backtick it and the fix commit writes the row.
- [ ] `CLAUDE.md` — Current status; Repo map (`study/` renders Beats 1–5; the two
  new Python-fed marts named beside `classifier_quality`; `pipeline/metrics.py`
  removed from the repo map and the `reviews_per_month` mention); BACKLOG count.
- [ ] `BACKING.md` — B5.1 → `determinism_facts` / `sql/marts/determinism_facts.sql`,
  Measured; B5.2 → `pipeline_row_counts` / `sql/marts/pipeline_row_counts.sql`,
  Measured (already named).
- [ ] `SPEC.md` — only if a chart or beat changed (Beat 5's two rows are
  described already; expected: the "(Pending …)" clauses on B5.1/B5.2 removed
  now that they render — a wording reconciliation, not a design change).
- [ ] `README.md` — none (the README is Phase 9f).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches the
network. Beat 5 renders through the existing `make study` (no variable,
byte-identical, no key, no fetch); the two marts fill through the existing
`make rebuild` path. Deleting `pipeline/metrics.py` is a source-file removal, not
a `make`-target delete of data.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `sql/**`, `pipeline/**`, `tests/`):
  deterministic-first, one-number-one-tag provenance, formulas/text as data, the
  two new marts' SQL is ANSI and portable (no reader function, no clock), the
  read-column allowlist, that B5.1 is not corpus-gated by design and B5.2 is, the
  `metrics.py` deletion leaves no dangling import; then this spec's Invariants.
- **security-reviewer** (not triggered — no CI, `.env`, credentials, network,
  paid API, hooks, settings or destructive `make` target in the range; the
  `metrics.py` deletion is a source file, not a data-delete target).
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  command, the fact-equals-constant and stage-count-equals-direct-count tests,
  the no-key/`ROWS=none` run, the corpus-gate states, idempotency, the
  byte-identical study, and that `pipeline/metrics.py` is gone with its reviews
  count still printed.
- **study-editor** (triggered — `study/` prose, `SPEC.md`, `CLAUDE.md` change):
  the Beat 5 blurbs and note for the two-layer rule, neutrality (no insurer
  named), the "facts you can check" voice, and no banned word.
- **coherence-auditor** at exit (mandatory, whole repo): SPEC Beat 5 ↔ BACKING B5
  rows ↔ the two marts ↔ the Beat 5 panels; the stale "Beats 1–4 render" and
  `pipeline/metrics.py` mentions gone; the closed BACKLOG row struck; forward
  coherence to 9f (README, the stranger acceptance test, the live-slider
  decision) and 9g (Metabase).
- Stack risk: `information_schema` row-count reads are the shape `table_counts`
  already uses — verify the new mart's own row does not count itself into a moving
  target (the fill runs once, after the other tables, over a fixed stage list);
  confirm `pipeline_row_counts` fills over `ROWS=synthetic` in the classify path
  but stays empty on the `rebuild()`-only `idempotency-check` path without
  breaking the count diff (an empty table is 0 both runs). Check the official
  DuckDB docs before any workaround; a surprise goes to DECISIONS → Gotchas.

## Out of scope (deferred, recorded)

- The README, the stranger acceptance test, and the live-slider decision (Phase
  9f, BACKLOG).
- The Metabase review-level drill demonstration (Phase 9g, BACKLOG).
- A B5.1 fact that counts the rendered page itself (e.g. "0 untagged numbers on
  the page") — self-referential; `check_panel` already enforces one tag per
  number, so the fact is the tag-set size, not a page scan.
