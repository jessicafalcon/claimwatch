# Phase 9d — Beat 4: the three fixes, drawn beside the Beat 3 curves (APPROVED)

Contract for the `phase-9d-beat-4` branch. Source: PROJECT_BRIEF.md §9 Phase 9
("The study"), sub-phase 9d of the permanent-artifact-first split (DECISIONS →
Phase 9a); brief §7 (the guardrail simulator, Beat 4) and §3 Beat 4. Depends on
Phase 9c merged (PR #25, 2026-09-09) and the fix PR `fix/drill-footer-verb`
merged (PR #26, 2026-09-09). The Beat 4 marts already exist and fill on every
rebuild input — Phase 8b landed `guardrail_sim`, `sla_threshold` and the hold
timer's three formulas in `models/cost_model.py` (PR #19). This phase renders
them.

**Status: APPROVED 2026-09-09 — in progress.** No new dependencies: Beat 4
renders through the 9a/9c contract (`duckdb` + stdlib, hand-written inline SVG);
no script, no new `make` target, no new chart `Kind`.
Challenged: 2026-09-09, round 1, spec 50966c34 — rework scoped to B4.1 (all amendments applied)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

Beat 4 is the study's turn from diagnosis to remedy: the answer to a wrongly
held claim is not a better fraud model, it is three plain rules wrapped around
the one that already exists — ask for every document once, put a clock on every
hold, and count how each hold ends. Phase 8b built the remedy as data:
`models/guardrail_sim.py::RULES` runs synthetic claims (the Open DAMIR fit read
at a thousand evenly spaced quantiles) through a hold timer and reports
before-and-after hold durations, `sla_threshold` computes the timer day below
which a hold is net-negative in expectation, and `cost_curves` carries the
toggled scenarios where "the curves move." `make simulate` prints all of it.
Nothing renders it.

Beat 4 is a **Modeled** surface like Beat 3 — every number a mart cell, filled
on every rebuild input, so no corpus gate and the committed page shows real
numbers. It adds one thing Beat 3 did not: the study's first aggregation read on
the page. `guardrail_sim` is per-claim (4,000 rows); the panel quotes two hold
lengths and one released share per scenario, and `models/guardrail_sim.py::summarize`
is the arithmetic that reduces them. This phase reads that reduction on the page
through an ANSI SQL `avg`/`count` group-by and pins it equal to `summarize`,
closing the Phase 8b BACKLOG row that named exactly this test.

The brief promises the reader could toggle each fix. The permanent artifact
carries no script (Phase 9a/9b/9c settled), and the live-control decision is
Phase 9f's. So in Beat 4 the three fixes are **drawn** beside the baseline —
each scenario's curves and holds as static marks a reader compares by eye — not
a control they flip.

## The central constraint

**Every Beat 4 number on the page equals a cell of `cost_curves`,
`guardrail_sim` or `sla_threshold`, carries that mart row's own tag, and does
not move when reviews or the API key are absent — the page over `ROWS=none`
shows the same Beat 4 numbers as over `ROWS=synthetic`, and a re-render is
byte-identical.** No new chart kind, no script, no new `make` target moves while
Beat 4 renders.

## DONE command

```
make review-gate SPEC=specs/phase-9d-beat-4.md && make rebuild ROWS=synthetic && make study && git diff --exit-code
```

- `make review-gate SPEC=…` — the gate green (test, lint, docs, backing,
  fixtures, pins) plus this spec's Evidence ids and Record-update files;
  `tests/test_beat4.py` runs inside `test`, reproducing every pin in
  `tests/pins.py`.
- `make rebuild ROWS=synthetic` — fills the synthetic warehouse the study
  reads, the Beat 4 marts filled with no key and no reviews.
- `make study && git diff --exit-code` — renders the page and proves it
  byte-identical to the committed `study/friction_ledger.html` (the export's
  determinism, the same check CI runs).

## Done-when

1. **Beat 4 renders.** The page gains a Beat 4 section with panels B4.1–B4.4,
   added as one `_BEATS` row and a `beat4_panels` builder; the render loop and
   the page shell do not change. *Evidence: row 1.*
2. **B4.1 draws the net curve for baseline and the three toggled scenarios.**
   `baseline`, `contacts_once`, `churn_halved` and `both` render as four net
   (fraud − friction) curves — one series each, four in all, within the
   five-slot palette — read from `cost_curves` keyed on `scenario`, baseline the
   reference. The hold-duration effect of the fixes is rendered in B4.3.
   *Evidence: row 2.*
3. **B4.2 draws the computed threshold.** The default timer day, its
   net-negative claim amount and the share of claims under it come from
   `sla_threshold`'s `is_default` row, with the arithmetic printed beside it.
   *Evidence: row 3.*
4. **B4.3's aggregate reproduces `summarize`.** The mean hold days per scenario
   are an ANSI SQL `avg`/`count` group-by over `guardrail_sim` (the released
   share the same reduction, `sum(case …)/count(*)`), drawn as a grouped bar
   (scenario × hold days) with the released share a figure in the panel note;
   a test proves that reduction, rounded to the display units, equals
   `models/guardrail_sim.py::summarize` on all four scenarios. *Evidence: row
   4.*
5. **B4.4 is Pending — no number.** The "count the mistakes" panel renders as a
   design placeholder carrying no value; `check_panel` refuses one. *Evidence:
   row 5.*
6. **No corpus gate, no key, deterministic.** Every Beat 4 number over
   `ROWS=none` equals its value over `ROWS=synthetic`, and `make study` is
   byte-identical on a rerun. *Evidence: row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat4.py::test_beat_four_renders_all_four_panels`; `make study && git diff --exit-code` (DONE command) |
| 2 | `tests/test_beat4.py::test_b41_net_curves_are_cost_curves_cells_within_the_palette` |
| 3 | `tests/test_beat4.py::test_b42_threshold_reads_the_default_sla_row` |
| 4 | `tests/test_beat4.py::test_b43_sql_aggregate_equals_summarize` |
| 5 | `tests/test_beat4.py::test_b44_is_pending_and_carries_no_number` |
| 6 | `tests/test_beat4.py::test_beat_four_numbers_equal_over_none_and_synthetic`; `tests/test_beat4.py::test_beat_four_render_is_byte_stable` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For every number a Beat 4 panel shows, it equals a cell of `cost_curves`, `guardrail_sim` or `sla_threshold` and carries that mart row's `tag`. | `tests/test_beat4.py::test_every_beat_four_number_is_a_tagged_mart_cell` — mutate one mart cell in a scratch DB; the rendered number moves with it and no cell carries a tag off its row. |
| For B4.1, each drawn scenario's net curve is one series of `cost_curves` keyed on `scenario`, the series count is ≤ 5, and every drawn number is a `cost_curves` cell carrying that row's `tag`. | `tests/test_beat4.py::test_b41_net_curves_are_cost_curves_cells_within_the_palette` — a B4.1 series whose value is not a `cost_curves` cell for that `scenario`, or a fifth series (the palette refuses slot 5). |
| For every simulator scenario, the reader's SQL aggregate over `guardrail_sim` — mean hold days (`avg`, rounded to `days` = 2 decimals) and timer-released share (`sum(case …)/count(*)`, exact, rounded to `rate` = 6 decimals) — equals `summarize`'s output for that scenario. | `tests/test_beat4.py::test_b43_sql_aggregate_equals_summarize` — a scenario where the SQL reduction and `summarize` disagree after rounding (the boundary case a floating-point summation-order flip would surface). |
| A Pending Beat 4 panel (B4.4) carries no number. | `tests/test_beat4.py::test_b44_is_pending_and_carries_no_number` — a value placed on the panel passes `check_panel`. |
| For every Beat 4 number, the page over `ROWS=none` shows the same value as over `ROWS=synthetic`, and a re-render of the same marts is byte-identical. | `tests/test_beat4.py::test_beat_four_numbers_equal_over_none_and_synthetic`; `::test_beat_four_render_is_byte_stable` — a Beat 4 number differs between the two inputs, or the bytes differ on a second render. |

## Pinned decisions (do not re-litigate)

- **Static comparison, not an interactive toggle.** The three fixes are drawn
  beside baseline as static marks; a reader compares by eye. The alternative —
  an inline script that recomputes on a control — is refused: the permanent
  page carries none (Phase 9a/9b/9c), and the live-control decision is Phase
  9f's (BACKLOG). Satisfies invariant 5.
- **B4.1 draws the net curve for baseline and the three toggled scenarios.**
  `baseline`, `contacts_once`, `churn_halved` and `both` render as four net
  (fraud − friction) curves — one series each, four in all, so the panel stays
  within the five-slot palette (`_series_var` refuses slot 5 loudly). The
  numbers are `cost_curves` cells keyed on `scenario`; the hold-duration effect
  is B4.3's. Rejected: three scenarios × the two curves (fraud + friction)
  each — six-plus series exceed the CVD-validated five-slot palette and would
  refuse to render; `contacts_once` alone — SPEC (B3.1/B3.2) assigns all three
  toggled scenarios to B4.1. Satisfies invariant 2. A one-line SPEC B4.1
  sentence names this four-scenario net comparison (Record updates).
- **No new chart `Kind` — the 9a/9c contract is reused.** B4.1 `curve` (four net
  series with the default-rate marker), B4.2 `curve` (`timer_amount_eur` over
  `timer_days`, the default day a marker) with the net-negative arithmetic in
  the note, B4.3 `grouped_bar` (scenario × hold days, the released share a note
  figure), B4.4 the Pending placeholder. Rejected: a new before/after kind —
  `grouped_bar` already fits. The dullest way.
- **B4.3 aggregates in ANSI SQL, pinned to `summarize`.** The reader's query is
  an `avg`/`count` group-by over `guardrail_sim`, the released share
  `sum(case when outcome = 'timer_released' then 1 else 0 end)` over
  `count(*)` — the portable idiom, not `FILTER` (Snowflake has none) — no
  arithmetic added to the DDL-only mart, rounded to the display units, and a
  test asserts it equals `models/guardrail_sim.py::summarize`. Rejected: a
  Python reduction in the reader — a SQL aggregate is the shape the Phase 8b
  BACKLOG row named and keeps the mart the one source of the numbers. Satisfies
  invariant 3; closes that row. `pipeline/sql_lint.py` must accept the `case`
  idiom (verified before the reader is trusted).
- **Palette and series reuse the existing tokens.** Scenarios take the existing
  series colour tokens; before/after is the point label, not a new colour. No
  new palette entry (`dataviz`: one system, consistent across beats).
- **Beat 4 display text lives in `study/text.py` as data.** The scenario display
  names, the B4.2 threshold sentence (templated from the `sla_threshold` default
  row's cells), the B4.4 placeholder and every note are data beside the Beat 1–3
  texts. Rejected: literals in `panels.py` — text-as-data is the 9c split, and
  the templated sentence cannot drift from the mart cell it prints. Satisfies
  invariant 1.

## Scope (files)

- `specs/phase-9d-beat-4.md` — this spec.
- `study/panels.py` — `beat4_panels`; the `guardrail_sim` aggregate reader and
  the `sla_threshold` threshold reader; the two marts added to the read-column
  allowlist.
- `study/export.py` — one `_BEATS` row for Beat 4.
- `study/text.py` — the Beat 4 display texts (scenario names, the B4.2 sentence
  template, the B4.4 placeholder, the notes).
- `study/model.py` — only if a Beat 4 label or absence word is needed that the
  contract does not already carry (expected: none).
- `study/friction_ledger.html` — the regenerated committed page.
- `tests/test_beat4.py` — the phase's tests (Evidence rows above).
- `tests/pins.py` — the Beat 4 pinned numbers.
- `SPEC.md` — the one B4.1 reconciling sentence (Record updates).

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9d entry (the static-comparison reading, the SQL
  aggregate pinned to `summarize`, no new `Kind`).
- [ ] `BACKLOG.md` — row "No test that a Phase 9 SQL aggregate over
  `guardrail_sim` reproduces `summarize`" struck (DONE Phase 9d); count
  decremented; the 9f rows (published corpus render, tooltip-only trail, live
  sliders) still stand, their triggers unchanged.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row.
- [ ] `CLAUDE.md` — Current status; Repo map (`study/` now renders Beats 1–4; the "Beats 1–3 render" sentence becomes 1–4); BACKLOG count.
- [ ] BACKING — none (B4.1–B4.3 already Modeled from Phase 8b; B4.4 stays Pending; no tag change, `make check-backing` stays green).
- [ ] `SPEC.md` — one clarifying B4.1 sentence: the panel draws the net curve across baseline and the three toggled scenarios (the "curves move" comparison), reconciling the Beat 3 fragment ("the three toggled scenarios are B4.1's") with B4.1's fix heading. No other chart changes.
- [ ] README — none (the README is Phase 9f).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches the
network. Beat 4 renders through the existing `make study` (no variable,
byte-identical, no key, no fetch).

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `tests/`): deterministic-first,
  one-number-one-tag provenance, formulas/text as data, the new SQL aggregate is
  ANSI and portable (no reader function, no clock), the read-column allowlist,
  scope; then this spec's Invariants.
- **security-reviewer** (not triggered — no CI, `.env`, credentials, network,
  paid API, hooks, settings or destructive target in the range).
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  command, the `summarize`-equivalence test, the no-key/`ROWS=none` run,
  idempotency, and the byte-identical study.
- **study-editor** (triggered — `study/` prose and `CLAUDE.md` change): the Beat
  4 blurbs and notes for the two-layer rule, neutrality (no insurer named), and
  the hypothesis-not-verdict voice on the "remedy" framing.
- **coherence-auditor** at exit (mandatory, whole repo): SPEC Beat 4 ↔ BACKING
  B4 rows ↔ the two marts ↔ the Beat 4 panels; the stale "Beats 1–3 render"
  sentence in CLAUDE.md gone; the closed BACKLOG row struck; forward coherence to
  9e (Beat 5) and 9f (README, the live-slider decision).
- Stack risk: DuckDB `avg` over integer `hold_days` returns a double — verify
  the rounding matches `fmean` in `summarize` before trusting the equivalence
  test; the B4.2 curve marker sits at an integer `timer_days` grid point, so
  `check_panel`'s marker-on-grid rule must see it on the drawn grid (the B3.2
  precedent). Check the official DuckDB docs before any workaround; a surprise
  goes to DECISIONS → Gotchas.

## Out of scope (deferred, recorded)

- The published study as a captured render, and the brand-address and page-size
  questions (BACKLOG, Phase 9f).
- A visible per-x-label count under the theme charts (BACKLOG, Phase 9f's
  stranger acceptance test).
- Live sliders / an inline recompute script (BACKLOG, Phase 9f).
- Beat 5, the README, and the Metabase demonstration (Phases 9e–9g).
