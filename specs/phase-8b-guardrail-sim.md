# Phase 8b — Guardrail simulator: synthetic claims, the hold timer, the computed threshold

Contract for the `phase-8b-guardrail-sim` branch. Source: PROJECT_BRIEF.md §3
Beat 4 ("Three small fixes, no rebuild required"), §7 (the guardrail toggles
and the computed hold-length threshold — the brief's "SLA threshold") and §9
Phase 8 ("Cost model + guardrail simulator"), the simulator half of the Phase 8
split: 8a landed Beat 3
(B3.1–B3.4, PR #17); 8b lands Beat 4's three number-bearing panels
(B4.1–B4.3). Depends on Phase 8a merged (the `scenario` column on
`cost_model_outputs` and `cost_curves`, `models/cost_model.py::FORMULAS`,
`PARAMETERS`, `rounded`, and `pipeline/build.py::read_model_fit`).

**Status: APPROVED — 2026-09-06.** No new dependency: the normal quantile is
stdlib `statistics.NormalDist` (already used by `opendata/fit.py`); the marts
are filled through the existing DuckDB seam. Amended 2026-09-06 after
challenge round 1 (the dispositions are the last section); every amendment is
folded into the sections it changes.

Challenged: 2026-09-06, round 1, spec 7501f9a3 — approve with amendments (all amended, questions answered)

## Why

Beat 4 says the fix is not a better fraud model but three boring rules around
the one that exists, and it owes the reader two things Beat 3 cannot give: how
long a held claim stays held before and after each fix, and a hold-timer
threshold that is computed, not guessed — "holds beyond N days on claims under
€X are net-negative in expectation", with the arithmetic shown (brief §3 Beat
4, §7). Today B4.1–B4.3 are Pending: the "curves move" rows exist in
`cost_curves` since 8a, but no hold duration and no threshold exist anywhere,
and no synthetic claim has been drawn from the fit Phase 7b produced for
exactly this purpose.

Why this is a phase and not a fix PR: two new marts, a new module under
`models/`, three new formulas and two new parameters in the cost model, a new
`make` target, and three BACKING flips — the seam 8a drew (DECISIONS → Phase
8a) and the second half of brief §9's Phase 8.

*Teaching note (lands in code and, in Phase 9, the README).* A simulator here
is not a random experiment. The claims are the fitted distribution read off at
a thousand evenly spaced quantiles — the same thousand amounts every run, each
one a formula a reader can redo — and the hold timer is a rule applied to each
of them. "Real distribution, synthetic claims": no individual claim is public
(brief §7 says so and so does the study), so the claims are made up, but their
sizes follow the public reimbursement data's shape, and that shape is what
decides how many claims a timer at €X would release.

## The central constraint

**No number reaches a Beat 4 mart except through `models/` — the cost model's
`FORMULAS` for the threshold and `guardrail_sim.py`'s `RULES` for the draw and
the hold — evaluated over declared parameters with no random draw, no clock,
no key and no arithmetic in SQL, so two runs are byte-identical and every
synthetic claim and every hold can be redone by hand from the rule printed
beside it.**

## DONE command

```
make simulate && make idempotency-check ROWS=synthetic && make check-backing && make test
```

- `make simulate` — prints the three rules (each expression beside the value
  it gives at the defaults, on the first synthetic claim and the default
  timer), the threshold table (one line per timer day of the grid: the amount
  and the share of synthetic claims under it, the default marked) and the
  hold-day summary per simulator scenario; a second run prints identical text.
  Offline, no variable, writes nothing.
- `make idempotency-check ROWS=synthetic` — two rebuilds, the two simulator
  marts filled inside `rebuild()` on each; per-table row counts unchanged,
  `guardrail_sim` and `sla_threshold` included. Their counts are constant by
  construction, so the proof that the *rows* are identical is the test under
  Done-when 5, not this diff.
- `make check-backing` — B4.1–B4.3 now Modeled, each naming a `sql/marts/`
  file that exists; B4.4 still Pending and named; no orphan mart.
- `make test` — the hand recomputation of the draw and the threshold, the
  closed outcome set and every branch of the hold rule, the scenario mapping,
  the fixes-never-lengthen-a-hold property, the byte-stable marts, the import
  allowlist for `models/`, the timer formulas' pins in `cost_model_outputs`.
  Green with the key unset (nothing on this path calls a model).

## Done-when

1. **The synthetic claims are the fitted distribution at fixed quantiles,
   never a random draw, and the draw is a printed rule.** `guardrail_sim`
   holds one row per (scenario, claim rank) over a 1,000-point quantile grid;
   the amount at rank `i` is `exp(mu + sigma × z((i − ½) / n))` with `z` the
   standard-normal quantile, evaluated over the `mu`/`sigma` *parameters* (so
   a slider on the fit moves the claims); the rule is a `RULES` entry whose
   text `make simulate` prints; a test recomputes the first, the middle and
   the last amount by hand from the pinned fit, asserts amounts are
   non-decreasing in rank and identical across scenarios, and `models/` still
   imports nothing that reads a clock or draws a random number. *Evidence:
   row 1.*
2. **The timer threshold is three cost-model formulas over two new declared
   guesses, printed beside their values.** `FORMULAS` gains three `point`
   entries — `loop_days`, `friction_per_day`, `timer_amount_eur` — and
   `PARAMETERS` two `unsourced` knobs, `days_per_round` and `timer_days`, each
   with a range containing its default; `cost_model_outputs` carries the three
   per scenario like every formula; `sla_threshold` holds one row per timer
   day of a fixed grid at the baseline parameters — the amount below which a
   hold that long is net-negative in expectation, and the share of the
   synthetic claims under it — with exactly one row marked as the default
   timer; a test recomputes the amount by hand at three grid days, checks it
   is linear in the day with the printed coefficient up to the loop's length
   and constant after it (friction stops accruing when the loop ends), and
   checks the share is non-decreasing in the day. *Evidence: row 2.*
3. **The hold rule is closed: two possible hold lengths, three possible
   outcomes, every branch a hand case.** For every (scenario, claim): the
   loop is `contacts × days_per_round` days; with the timer off, or on but
   the loop no longer than the timer, the hold is the loop
   (`loop_released`); with the timer on and the claim under the threshold the
   hold is the timer (`timer_released` — pay now, audit after); otherwise a
   person is pulled in at the timer and completes the loop (`timer_escalated`,
   hold = the loop). `hold_days ∈ {loop_days, timer_days}` and `outcome` is
   one of the three names; a test walks all four branches with hand cases and
   asserts the outcome set on the built mart is exactly the closed tuple.
   *Evidence: row 3.*
4. **Simulator scenarios are a closed set, each mapped to the cost-curve
   scenario it pairs with, and the timer is set from the un-fixed world.**
   `SIM_SCENARIOS` = `no_fix` → `baseline`, `ask_once` → `contacts_once`,
   `hold_timer` → `churn_halved`, `both_fixes` → `both`; every `guardrail_sim`
   row carries both names so Phase 9 lays hold durations beside the curves on
   one join; an unknown simulator scenario is refused; the timer's amount is
   `timer_amount_eur` evaluated at `baseline`, whatever the scenario (the
   recommendation is made before any fix is applied); a test proves every
   mapped name is in `cost_model.SCENARIOS`, that `evaluate(…, "fix_5")` and
   `simulate(…, "fix_5")` both refuse, and that `hold_timer` uses the
   baseline amount, not `churn_halved`'s. *Evidence: row 4.*
5. **The simulator marts are part of every rebuild, byte-stable, and need no
   key.** `rebuild()` fills `guardrail_sim` and `sla_threshold` after
   `write_model_marts` on every `ROWS` input; two rebuilds give identical
   rows; every row carries `run_id` and the `Modeled` tag; `models/` imports
   only the allowlist (now plus `statistics` and the package's own modules);
   `make simulate` twice prints identical text and writes nothing.
   *Evidence: row 5.*
6. **A fix never lengthens a hold, and the summary the study quotes is
   recomputed from the rows.** For every claim, hold under `ask_once` ≤ hold
   under `no_fix`, hold under `hold_timer` ≤ hold under `no_fix`, and hold
   under `both_fixes` ≤ each single fix — the property the side-by-side chart
   relies on; `summarize(rows)` is the one aggregation site (mean hold days,
   share of claims released by the timer, per scenario) that `make simulate`
   prints; a test recomputes the summary from the built mart with plain
   arithmetic and asserts the monotone property row by row. *Evidence:
   row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_guardrail_sim.py::test_synthetic_amounts_recomputed_by_hand`, `::test_amounts_non_decreasing_and_scenario_invariant`; `tests/test_model_marts.py::test_models_imports_only_stdlib_math` (allowlist widened by `statistics` and `models`); `make simulate` prints the draw's rule text beside the first claim's amount |
| 2 | `tests/test_cost_model.py::test_timer_formulas_recomputed_by_hand`, `::test_formulas_evaluate_to_the_pins` (three more names per scenario); `tests/test_guardrail_sim.py::test_threshold_linear_in_days_and_share_monotone`, `::test_threshold_marks_exactly_one_default_day`; `make simulate` prints the threshold table |
| 3 | `tests/test_guardrail_sim.py::test_hold_rule_every_branch_by_hand`, `tests/test_sim_marts.py::test_outcomes_are_the_closed_set_and_hold_is_loop_or_timer` |
| 4 | `tests/test_guardrail_sim.py::test_sim_scenarios_map_onto_cost_model_scenarios`, `::test_unknown_scenario_refused`, `::test_timer_amount_is_the_baseline_one` |
| 5 | `tests/test_sim_marts.py::test_two_marts_filled_on_every_input`, `::test_two_rebuilds_identical_sim_mart_rows`, `::test_rows_carry_run_id_and_modeled_tag`, `::test_make_simulate_is_byte_identical_on_rerun`; `tests/test_no_key.py::test_no_key_sim_marts_are_filled` |
| 6 | `tests/test_guardrail_sim.py::test_a_fix_never_lengthens_a_hold`, `tests/test_sim_marts.py::test_summary_recomputed_from_the_mart_rows`, `::test_default_day_share_equals_timer_released_share` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all ranks `i` and all scenarios, the synthetic amount at rank `i` is the fitted lognormal evaluated at the fixed quantile `(i − ½) / n` over the `mu`/`sigma` parameters — the same amount in every scenario and every run, non-decreasing in `i`, never a random draw. | `tests/test_guardrail_sim.py::test_synthetic_amounts_recomputed_by_hand` — the first, middle and last amount recomputed with `math` and `statistics` from `tests/pins.py`; `::test_amounts_non_decreasing_and_scenario_invariant` — one amount changed in one scenario. |
| For all parameter sets, the threshold amount is `fp_share × friction_per_day × min(timer_days, loop_days) / (1 − fp_share)` — linear in the timer day with that coefficient up to the loop's length, constant after it — and the share of synthetic claims under it is non-decreasing in the day. | `tests/test_guardrail_sim.py::test_threshold_linear_in_days_and_share_monotone` — a share that falls between two grid days; an amount at day 2d ≤ loop that is not twice the amount at day d; an amount past the loop that differs from the amount at the loop. |
| For all (scenario, claim), `hold_days` is the loop or the timer, `outcome` is one of three names, and the outcome and the hold agree with the rule's four branches. | `tests/test_guardrail_sim.py::test_hold_rule_every_branch_by_hand` — four hand cases (timer off; timer on and loop ≤ timer; timer on, loop > timer, amount under; amount not under); `tests/test_sim_marts.py::test_outcomes_are_the_closed_set_and_hold_is_loop_or_timer`. |
| For all claims, applying a fix never lengthens the hold, and both fixes never lengthen it past either single fix. | `tests/test_guardrail_sim.py::test_a_fix_never_lengthens_a_hold` — row-by-row over the built grid; a rule change that lets an escalated claim outlast the loop fails it. |
| For all simulator scenarios, the paired cost-curve scenario is a member of `cost_model.SCENARIOS`, the timer amount is the baseline evaluation's, and a name outside the set is refused. | `tests/test_guardrail_sim.py::test_sim_scenarios_map_onto_cost_model_scenarios`, `::test_timer_amount_is_the_baseline_one` — `hold_timer`'s releases counted against `churn_halved`'s amount differ; `::test_unknown_scenario_refused`. |
| For all runs — any `ROWS` input, key set or unset, first or second rebuild — the two simulator marts' rows are identical and `make simulate`'s text is identical. | `tests/test_sim_marts.py::test_two_rebuilds_identical_sim_mart_rows`, `::test_make_simulate_is_byte_identical_on_rerun`, `tests/test_no_key.py::test_no_key_sim_marts_are_filled`. |
| For all parameters, the 8a rule still holds — `sourcing` is one of two words, a range contains its default, an unsourced one carries no citation — and the default timer day lies on the day grid (exactly one grid row is the default). | `tests/test_cost_model.py::test_sourced_needs_a_citation_every_range_holds_its_default` (two more rows); `tests/test_guardrail_sim.py::test_threshold_marks_exactly_one_default_day`. |
| For all modules under `models/`, only the import allowlist is used — stdlib that reads no clock and draws no random number, plus the package's own modules — never `random`, `time`, `datetime`, `secrets`, a file, a warehouse, the network or a model client, and never `NormalDist.samples` (the one random method `statistics` carries). | `tests/test_model_marts.py::test_models_imports_only_stdlib_math` — the allowlist is `math`, `statistics`, `dataclasses`, `typing`, `collections`, `__future__`, `models`; the source scanned for the forbidden names, `samples` among them. |

## Pinned decisions (do not re-litigate)

- **The claims are a quantile draw, `n` = 1,000, through stdlib
  `statistics.NormalDist().inv_cdf`; the draw is a printed rule.**
  `models/guardrail_sim.py::QUANTILE_GRID` is the 1,000 midpoints
  `(i − ½) / n` for `i` in 1..1,000; `synthetic_claims(params)` returns one
  `Claim(rank, quantile, amount_eur)` per grid point over the parameters'
  `mu`/`sigma`, rounded at the one site (quantile as `rate`, amount as `eur`).
  The `RULES` entry `synthetic_amount` carries the expression text —
  `exp(mu + sigma * z((rank - 0.5) / n))` with the caveat "a real
  distribution, synthetic claims: no individual claim is public" — beside the
  function. The `mu`/`sigma` ± 2 SE ranges 8a gave the sliders are what a
  reader moves to see the claims shift; `emp_p50` is not read here. Rejected:
  a seeded pseudo-random draw (the seed is a hidden parameter and "redo by
  hand" fails for claim 731); the fixture's 5,000 real cells as the claims (a
  cell is not a claim, the fixture is read-only and lives under a Measured
  tag, and the lognormal is the calibration brief §7 names); an analytic CDF
  only, no per-claim rows (the chart could not be opened down to the claims
  behind it — brief §1); `n` = 5,000 to match the fixture (five times the rows
  for the same shape; 1,000 puts the share-under resolution at 0.1 %, finer
  than any slider). Satisfies invariants 1 and 8.
- **The threshold is Beat 3 arithmetic: three `point` entries in
  `cost_model.py::FORMULAS` over two new `unsourced` parameters, the claim's
  own amount as the ceiling on what a hold can recover.** `days_per_round`
  (default 7 days, range 1–21: one document round trip, a guess) and
  `timer_days` (default 14 days, range 1–60, on the day grid) join
  `KNOB_PARAMETERS`. The entries, appended after `net` so they read
  `customer_value`: `loop_days = contacts * days_per_round`;
  `friction_per_day = (contacts * cost_per_contact + churn_prob *
  customer_value) / loop_days` (the cost model's friction per false positive
  spread evenly over the loop — a stated linear-accrual assumption, printed in
  the text); `timer_amount_eur = fp_share * friction_per_day *
  min(timer_days, loop_days) / (1 - fp_share)` (the text says "friction stops
  accruing when the loop ends" and "a hold planned to run `timer_days`"). The
  arithmetic in words: a held claim of amount `A` is fraud with probability
  `1 − fp_share`, and the most a hold can recover from it is `A`; it is
  legitimate with probability `fp_share` and then costs `friction_per_day`
  for every day held, until the loop ends and the model's friction for that
  claim is fully paid. A hold planned to run `N` days is net-negative in
  expectation when `fp_share × friction_per_day × min(N, loop_days) > (1 −
  fp_share) × A`, which solves to `A < timer_amount_eur`. It prices the
  decision made at day 0 — how long a hold may run — not the choice at day
  `N` to keep holding (the challenge's question 5; the ex-ante reading is the
  one the study's sentence makes, and the amount rises with `N` up to the
  loop, then holds). Using `A` as the recovery ceiling overstates what a hold
  recovers, so the threshold errs toward holding — the conservative
  direction, said beside it, and true on every grid row because the cap
  keeps the friction charged at or under the model's total for that claim.
  The units: `loop_days` and the two new parameters whole (`count`),
  `friction_per_day` and `timer_amount_eur` euros. The reader rule for these
  rows in `cost_model_outputs`: B3.1 prints every `point` row, the three
  timer rows included and labeled "used by Beat 4 at `baseline`"; B4.2 prints
  the three at `baseline` only — the rows at the other scenarios are the same
  formulas over that scenario's parameters, printed for completeness like
  every formula, never read as a recommendation (the `cost_model_outputs.sql`
  header and SPEC B3.1's sentence say so — Record updates). Rejected: an
  unbounded linear threshold (the pre-challenge proposal: past the loop it
  charged friction the model never incurs, so rows past `loop_days` erred
  toward releasing, the opposite of the stated direction, and printed a
  higher amount under `contacts_once` than under `baseline`); the marginal
  reading, the choice at day `N` with only the remaining loop at stake (the
  amount would fall with `N`, the chart's slope reverses, and the sentence
  "holds beyond N days on claims under €X" would describe a threshold that
  loosens as the clock runs); the cost model's average fraud saved per flagged claim as
  the per-claim recovery (the fraud pool is an aggregate floor; a per-claim
  timer needs a per-claim ceiling, and the average would make the threshold
  independent of the claim's size, which is the whole point of "claims under
  €X"); a churn-over-hold-days curve (a second unsourced relationship on top
  of the flat `churn_prob`); a separate formula table in `guardrail_sim.py`
  for the threshold (brief §7: "computed from the Beat 3 model" — it is Beat
  3 arithmetic and belongs in the one `FORMULAS`); an `escalation_days`
  parameter (below). Satisfies invariants 2 and 7.
- **The hold rule and its outcomes are closed data in
  `guardrail_sim.py::RULES`; an escalated claim completes the loop.**
  `Rule(name, text, fn)` is the module's mirror of `Formula`; `RULES` is the
  ordered tuple (`synthetic_amount`, `hold`, `share_under`), each text printed
  by `make simulate` beside its value at the defaults, so the printed rule and
  the computed row are one entry (the 8a shape, second copy of nothing).
  `hold(claim, scenario_params, timer_on, timer_amount)` returns
  `(hold_days, outcome)` with `OUTCOMES = ("loop_released",
  "timer_released", "timer_escalated")`: timer off, or on but
  `loop_days <= timer_days` → the loop, `loop_released`; on and `amount_eur <
  timer_amount` → `timer_days`, `timer_released`; else the loop,
  `timer_escalated` — a person is pulled in at the timer and the claim still
  takes the loop, because a person's turnaround has no public anchor and is
  not modeled (a BACKLOG row with its trigger). The study says so beside the
  chart: for large claims the timer changes who decides, not how long.
  `share_under(claims, amount) = count(amount_eur < amount) / n` is the third
  rule, feeding `sla_threshold`. Rejected: an `escalation_days` guess (a third
  knob with no anchor, and the one that would make the timer look better);
  the timer shortening large holds (assumes the person beats the loop);
  outcomes as free strings (an open set). Satisfies invariants 3 and 4.
- **Simulator scenarios are a closed set carrying the cost-curve scenario
  they pair with; the timer is set from the un-fixed world.**
  `SIM_SCENARIOS` is an ordered tuple of `SimScenario(name, curves_scenario,
  contacts_once, timer_on)`: `no_fix` (`baseline`, no, no), `ask_once`
  (`contacts_once`, yes, no), `hold_timer` (`churn_halved`, no, yes),
  `both_fixes` (`both`, yes, yes). `simulate(params, scenario)` evaluates the
  cost model at `curves_scenario` for that scenario's `loop_days` (so
  `ask_once` runs a one-round loop through the same `FORMULAS`), takes
  `timer_amount_eur` from the `baseline` evaluation, and applies `hold` to
  every synthetic claim. Every `guardrail_sim` row carries `scenario` and
  `curves_scenario`, so Phase 9 lays hold durations beside the curves that
  "move" on one join and never guesses the pairing; the illustrative churn
  halving stays what brief §7 says it is — the cost-model effect the study
  displays beside the timer, not a quantity the simulator derives. Rejected:
  reusing the cost-model names for the simulator (`churn_halved` would name
  an effect the simulator does not compute; the DECISIONS → Phase 8a note
  reserved the simulator its own names); a `hold_timer` scenario added to
  `cost_model.SCENARIOS` with a churn override derived from hold days (a
  churn-versus-days relationship no source gives; brief §7 keeps the halving
  illustrative); the timer amount evaluated at the mapped scenario (the
  recommendation is "at these parameters" — the world before the fix).
  Expected at the defaults, not a STOP: once the loop is one round it ends
  before the default timer, so under `both_fixes` the clock never fires and
  its rows equal `ask_once`'s row for row — two identical bars the study
  labels as such ("with one round, the clock has nothing left to cut"); the
  timer's own effect is read under `hold_timer`. 8a freed the cost-model
  marts' `scenario` column for a simulated timer; 8b does not use it, because
  the simulator computes holds, not churn (the challenge's question 6; a
  DECISIONS sentence). Satisfies invariant 5.
- **Two DDL-only Python-fed marts, one writer, filled inside `rebuild()`
  after the model marts; `make simulate` prints and writes nothing.**
  `sql/marts/guardrail_sim.sql` — grain one row per (scenario, claim rank),
  4 × 1,000 rows: `scenario varchar`, `curves_scenario varchar`, `claim_rank
  integer`, `quantile double`, `amount_eur double`, `loop_days integer`,
  `hold_days integer`, `outcome varchar`, `run_id`, `tag`; the header says
  the per-claim grain exists for the timer's per-claim decision (which
  claims it releases, and at what amount), not for a hold distribution — a
  hold takes two values per scenario. `sql/marts/sla_threshold.sql` — grain
  one row per timer day of the fixed grid 1..60 (60 rows) at the baseline
  parameters: `timer_days integer`, `timer_amount_eur double`, `share_under
  double`, `is_default boolean`, `run_id`, `tag`; no scenario column (the
  recommendation is made once, before any fix). Integer and boolean columns
  are named as such in the DDL so `rebuild`'s catalog check and Snowflake see
  one type (the `cost_curves.is_default` precedent).
  `pipeline/build.py::write_sim_marts(conn, fit, run_id)` clears and inserts
  both in one transaction, rows in scenario / rank and day order, and
  `rebuild()` calls it right after `write_model_marts` on every input, so
  `idempotency_check` and every caller see them (the 8a precedent; `.sql`
  files are `create or replace table (…)` shapes run by the generic marts
  loop). `make simulate` (no variable; the `model` shape) reads the fit,
  prints `format_simulation`, writes nothing. Rejected: an aggregates-only
  mart (no drill-through to the claims behind the chart); a scenario column
  on `sla_threshold` (four recommendations for one decision); folding the
  print into `make model` (one target per stage — the model prints without
  the simulator, and Beat 4's arithmetic is read on its own). Satisfies
  invariant 6.
- **Rounding through 8a's one site; one aggregation site for the summary.**
  Every written or printed number passes `cost_model.rounded`: amounts and
  the threshold `eur`, quantiles and shares `rate`, a hold or a loop `count`
  (whole days), and a mean hold `days` — a new `_ROUNDING` row at two places,
  the one cell `cost_model.py`'s rounding table gains — so no second rounding
  site. `summarize(rows)` returns, per simulator scenario, the mean hold in
  days (`days`) and the share of claims the timer released (`rate`), computed
  with plain `fmean` and a count over the rows; `make simulate` prints it and
  a test recomputes it from the built mart. The share the timer released
  under `hold_timer` and `sla_threshold`'s `share_under` at the default day
  are the same count by construction; a test pins the equality across the two
  marts. The study's Beat 4 headline reads the mart through SQL `avg`/`count`
  in Phase 9, rounded to the same units, and must reproduce `summarize` — a
  Phase 9 test, named here so 9 inherits the guard. Rejected: a summary mart
  (an aggregate of a mart the study can aggregate; a third grain to keep in
  step); rounding the mean at the printer (a second site); the mean as
  `count` (a headline that loses a day of resolution — the pre-challenge
  gap). Satisfies invariant 6.

### The parameters this phase adds (defaults; every one is a guess to explore, never a fact; every row has a range)

| Name | Default | Unit | Sourcing | Citation | Range (`low`–`high`) |
|---|---|---|---|---|---|
| `days_per_round` | 7 | days per document round trip | unsourced | — | 1–21 |
| `timer_days` | 14 | days a hold may run before the clock fires | unsourced | — | 1–60 (on the day grid) |

The formulas added to `FORMULAS`, in order after `net` (all `point`):
`loop_days = contacts × days_per_round`; `friction_per_day = (contacts ×
cost_per_contact + churn_prob × customer_value) / loop_days` (friction assumed
to accrue evenly over the loop and to stop when it ends); `timer_amount_eur =
fp_share × friction_per_day × min(timer_days, loop_days) / (1 − fp_share)` (a
hold planned to run `timer_days` on a claim under this amount is net-negative
in expectation; the claim itself is the ceiling on what a hold can recover, so
this errs toward holding). The
rules in `RULES`: `synthetic_amount = exp(mu + sigma × z((rank − ½) / n))`;
`hold` as the four branches above; `share_under = count(amount_eur < amount) /
n`. Their values at the defaults are computed at build and pinned in
`tests/pins.py`; this spec names none, so no number is stated before its rule
runs. (The session ran the rules over the tracked fit as a plausibility check
before writing this: the loop at the defaults is longer than the default
timer, the default timer's amount lands inside the body of the fitted
distribution rather than in a tail, and each fix shortens the mean hold; the
pins are still typed only from the built output.) If the defaults put the
threshold in a tail or the timer never fires, the chart is published as it
comes out (SPEC.md → "hypothesis, not verdict") — a default is not tuned to
tell a story; a change to one is a `PARAMETERS` cell with its range, recorded.

## Scope (files)

- `models/guardrail_sim.py` — new module (the `architecture-fit` skill loaded
  by name before it is created): `Claim`, `Rule`, `RULES`, `OUTCOMES`,
  `SimScenario`, `SIM_SCENARIOS`, `QUANTILE_GRID`, `TIMER_DAY_GRID`,
  `synthetic_claims`, `hold`, `share_under`, `simulate`, `threshold_table`,
  `summarize`, `format_simulation`; the teaching docstring; imports `math`,
  `statistics`, `dataclasses`, `collections.abc` and `models.cost_model`.
- `models/cost_model.py` — two `KNOB_PARAMETERS` rows, three `POINT_FORMULAS`
  entries and their `_OUTPUT_UNIT` rows (the map became the `Formula.unit`
  field in `fix/cost-outputs-unit`, 2026-09-09), one `_ROUNDING` row (`days`,
  two places); nothing else moves. `models/__init__.py` — the docstring names
  both modules as landed.
- `sql/marts/guardrail_sim.sql`, `sql/marts/sla_threshold.sql` — DDL only;
  headers name grain (and why the per-claim grain exists), provenance
  (`run_id`, `tag`) and the rows fed (B4.1 and B4.3; B4.2).
  `sql/marts/cost_model_outputs.sql` — header only: 4 × 14 rows, and the
  reader rule for the three timer rows (B3.1 prints every `point` row; B4.2
  reads the three at `baseline`).
- `pipeline/build.py` — `write_sim_marts(conn, fit, run_id)`, called by
  `rebuild()` after `write_model_marts`; `table_counts` unchanged (it reads
  the catalog).
- `pipeline/cli.py` — the `simulate` subcommand (no variable; the `model`
  shape): reads the fit once, prints `format_simulation`.
- `Makefile` — `simulate` target, `.PHONY`, help line; the header comment's
  "model (8)" becomes "model, simulate (8)".
- `tests/test_guardrail_sim.py`, `tests/test_sim_marts.py` — new;
  `tests/test_cost_model.py` (the timer formulas by hand; the pins gain three
  names per scenario), `tests/test_model_marts.py` (the allowlist gains
  `statistics` and `models`, the forbidden-name scan gains `samples`;
  `COST_PARAM_ROWS`/`COST_OUTPUT_ROWS` move),
  `tests/test_no_key.py` (the simulator marts under a no-key rebuild),
  `tests/test_damir.py` (`test_cost_model_marts_exist_and_8b_marts_do_not`
  becomes the assertion that all five Python-fed marts exist and no
  damir-named mart does — the 7b/8a placeholder giving way as planned, not a
  weakened test), `tests/pins.py` (the parameter and output row counts, the
  timer formulas' values per scenario, the first/middle/last synthetic
  amounts, the default-day threshold and share, the summary per scenario, the
  two mart row counts).
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `BACKING.md`, `SPEC.md`
  (tag markers and one wording change), this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 8b entry: the six pinned decisions with their
  rejected alternatives (the challenge round's four amendments named as
  such: the threshold capped at the loop, a `days` rounding unit, the
  `both_fixes` bars expected, the reader rule for the timer rows); the "no
  `escalation_days`" and "timer set at baseline" choices as such; one
  sentence on the `scenario` column 8a freed — 8b did not use it, because the
  simulator computes holds, not churn; the "Formulas are data" bullet in
  "still in force" restated as the property (a printed expression and its
  callable are one entry in the module that owns the quantity, and the
  printer prints from the entry) with the two tuples as its instances; the
  widening of the `models/` import allowlist (`statistics`, `models`) with
  the property it keeps; Gotchas if any
  (`NormalDist.inv_cdf` stability across CPython's C and Python paths; DuckDB
  binding of Python `int` into `integer` columns for the day and rank cells).
- [ ] `BACKLOG.md` — rows opened: a person's turnaround on an escalated hold
  is not modeled (trigger: a citable public benchmark on manual claim-review
  turnaround → an `escalation_days` parameter and a fourth branch, a design
  change with its amendment); the `architecture-fit` skill's shape sentence
  "a formula is one entry in `models/cost_model.py::FORMULAS`" widens to name
  `guardrail_sim.py::RULES` on the next tooling branch (a skill is tooling,
  never mixed with a phase); the Phase 9 test that SQL `avg`/`count` over
  `guardrail_sim`, rounded to the same units (`days`, `rate`), reproduces
  `summarize` (trigger: the Beat 4 panel is rendered). The "data.ameli
  practitioner-fee distributions" row's trigger
  re-checked (8b draws from the DAMIR amount fit alone; re-deferred to the
  study). Count updated.
- [ ] `CLAUDE.md` — Current status; Commands (`simulate`: offline, no
  variable, prints and writes nothing; `rebuild` fills the two simulator
  marts after the model marts); Repo map (`models/` names
  `guardrail_sim.py::RULES` as landed, no "(Phase 8b)"; the `sql/marts/`
  line counts five Python-fed marts); Deterministic first — "Formulas are
  data" restated as the property, not a list of places: a printed expression
  and its callable are one entry in the module that owns the quantity, and
  the printer prints from the entry — `cost_model.py::FORMULAS` (the model
  and the timer threshold) and `guardrail_sim.py::RULES` (the draw and the
  hold) are its two instances; BACKLOG count.
- [ ] `BACKING.md` — B4.1 Pending → Modeled, its mart cell re-pointed to
  `cost_curves` (scenario `contacts_once`) and its SQL cell to
  `sql/marts/cost_curves.sql`, as 8a recorded; B4.2 → Modeled on
  `sla_threshold`; B4.3 → Modeled on `guardrail_sim`, upstream `open-damir`
  (the fit the draw reads); B4.4 stays Pending, unchanged. The note under the
  table: the "B4.3 stays Pending" and "B4.1's eventual mapping" paragraphs
  replaced by one paragraph saying what landed — the claims are the fit at
  fixed quantiles (real distribution, synthetic claims), B4.1's hold
  durations are the `ask_once` rows of `guardrail_sim`, B4.2's printed
  arithmetic is the `loop_days` / `friction_per_day` / `timer_amount_eur`
  rows of `cost_model_outputs` at `baseline`.
- [ ] `SPEC.md` — Beat 4 panels B4.1–B4.3: the "(Pending)" / "(Pending until
  the simulator mart lands)" markers removed, tag stays *Modeled* (the tag
  state moving as planned, not a chart change — the Beat 3 precedent after
  8a); B4.4 unchanged. Three deliberate wording changes, and no other: Beat
  4's *Under the hood* sentence says the claims are the fitted distribution
  read at fixed quantiles, not a random draw ("… synthetic claims — the
  distribution fitted to real public reimbursement data, read at a thousand
  evenly spaced points, with the fit shown — …"); B4.3's sentence names what
  the side-by-side shows — the mean hold in days and the share of claims the
  clock released, per fix, with the Beat 3 curves beside them (two hold
  lengths per fix, not a distribution; with one round the clock has nothing
  left to cut); B3.1's sentence adds that the hold timer's three formulas
  print in the same list, used by Beat 4 at the defaults. No panel added.
- [ ] README — none (no README.md exists yet; it lands in Phase 9; the
  "real distribution, synthetic claims" teaching sentence lives in
  `models/guardrail_sim.py`'s docstring until then).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make simulate` runs `uv run python -m pipeline simulate` with no
variable (the `model` shape): it reads `models/` and the tracked fit artifact
through the existing strict reader, prints, and writes nothing. Run twice:
identical text. No credentials: identical text (nothing on the path reads a
key). The rebuild's simulator step adds no variable to `rebuild` and no path
derived from user input. No new input the repo does not own: the only file
read is the tracked fit, through `read_fit`'s declared shape (8a).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `simulate` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_sim_marts.py::test_make_simulate_is_byte_identical_on_rerun` (the target exists, takes nothing, prints the same twice) |

## Review & stack risk

- **code-reviewer** (triggered — `*.py`, `sql/**`, `Makefile`, `tests/`): the
  threshold formulas in `FORMULAS` and nowhere else (a formula string typed
  in the simulator, SQL, the printer or a test is a finding); the draw and
  the hold as `RULES` entries whose text is what prints; the closed
  `OUTCOMES` and `SIM_SCENARIOS` as data, not `if` chains on strings; no
  literal number in the writer; `rounded` called, never re-implemented;
  `write_sim_marts` after `write_model_marts` inside `rebuild()`; the
  allowlist test widened by exactly two names; scope (Beat 4's three
  number-bearing panels only — an outcome log, a per-rule false-positive rate
  or a Phase 9 render in this diff is out of scope).
- **security-reviewer** (mandatory by lookup — `pipeline/cli.py` and the
  `Makefile` are on the Sensitive list): the `simulate` subcommand and target
  unarmed and variable-free; no new file read (the fit through 8a's strict
  reader), no new network, paid or delete path; the `GATED` set unchanged;
  the two new marts carry no address, no body, no name.
- **functionality-tester** (after code-reviewer): the DONE command; the
  no-key run; hand-mutation in a worktree — a `RULES` branch swapped fails
  the hand cases, a threshold operator changed fails the by-hand test and the
  pins, an escalated claim given a shorter hold fails the monotone test, a
  `NormalDist` replaced by a seeded `random` fails the allowlist and the
  by-hand amounts.
- **study-editor** (triggered — BACKING claim cells, CLAUDE.md, the SPEC tag
  markers and one sentence): "synthetic claims, real distribution" said
  wherever a claim count appears; the threshold sentence stays "in
  expectation" and names its conservative direction; the escalation
  simplification is said, not hidden; every new default reads as a guess to
  explore; no banned word.
- **coherence-auditor** at exit: SPEC Beat 4's three panels no longer say
  Pending and BACKING B4.1–B4.3 are Modeled with existing files; B4.4 still
  Pending and named; CLAUDE.md's repo map no longer says `guardrail_sim.py
  (Phase 8b)` and its "Formulas are data" rule names both tuples; BACKING's
  note no longer says "B4.3 stays Pending" or "8b's spec re-points"; the
  Makefile header names `simulate`; the `architecture-fit` skill's shape
  sentence is recorded as stale in BACKLOG (tooling branch), not silently
  edited here.
- Stack risk (verify in the first hour): `statistics.NormalDist().inv_cdf`
  — CPython carries a C implementation and a pure-Python fallback of the
  same algorithm; confirm the 1,000 rounded amounts are byte-identical
  locally and on the CI runner (the `ROWS=synthetic` idempotency-check plus
  the pinned first/middle/last amounts are the proof; if a platform
  difference shows at the sixth place, the pin stays and the Gotcha records
  it). DuckDB binding of Python `int` into `integer` columns for
  `claim_rank`, `loop_days`, `hold_days`, `timer_days`, and of `bool` for
  `is_default`, through the guarded bulk insert of Amendment A1 (`_insert_rows`
  — one `executemany` per mart under `_no_pandas_probe`). Compute the
  defaults' outputs before any pin is typed; if the timer never fires at the
  defaults under `hold_timer`, or the threshold lands in a tail, STOP and
  report — do not tune a default to make the story hold. (Under `both_fixes`
  the clock cannot fire at the defaults — a one-round loop ends first — and
  that is expected, decision 4, not a STOP.) Findings go to DECISIONS.md →
  Gotchas.

## Out of scope (deferred, recorded)

- **B4.4 — count the mistakes:** a false-positive rate per flag rule needs an
  outcome log that does not exist; the panel stays a design panel, Pending,
  with no number (8a's Out of scope; BACKING B4.4 unchanged).
- **A person's turnaround on an escalated hold** — BACKLOG row with its
  trigger; until then an escalated claim completes the loop and the study
  says so.
- **A churn-versus-hold-days relationship** — the simulator does not derive
  the churn effect of the timer; the illustrative halving of brief §7 stays
  the displayed effect (`cost_curves` scenario `churn_halved`), labeled
  illustrative.
- **A per-claim fraud probability that varies with the amount** — no public
  source; `fp_share` is one number for every claim (a slider).
- **Slider recompute and the Beat 4 render** — Phase 9: how the static page
  recomputes `FORMULAS` and `RULES` when a slider moves, the side-by-side
  chart, the SQL aggregate over `guardrail_sim` and the test that it
  reproduces `summarize` (BACKLOG row).
- **data.ameli practitioner-fee distributions** — BACKLOG (Phase 7b),
  trigger re-checked at this exit: the simulator draws from the DAMIR amount
  fit alone.
- **The `architecture-fit` skill's shape sentence** — widened on the next
  tooling branch (BACKLOG row), never in a phase diff.

## Challenge round 1 — dispositions (2026-09-06)

`/challenge` on the spec as first committed (9a267b0): 0 BLOCKER, 4
should-fix, 5 suggestions, 2 questions; verdict "approve with amendments".
The developer approved every recommendation as suggested; every finding is
folded into the sections above, and this block is the record of what each
became.

- **#1 the threshold unbounded past the loop** — amend: `timer_amount_eur`
  charges friction for `min(timer_days, loop_days)` days; the expression
  text says friction stops accruing when the loop ends; invariant 2 is
  "linear up to the loop, constant after"; the "errs toward holding"
  sentence now holds on every grid row. Restores invariant 2.
- **#2 no rounding unit for the mean hold** — amend: a `days` row (two
  places) in `_ROUNDING`, named in Scope, applied in `summarize`; the Phase 9
  BACKLOG row says "the same units". Restores invariant 6.
- **#3 the STOP fires by construction for `both_fixes`** — amend: the STOP
  is scoped to `hold_timer`; decision 4 says the identical bars are expected
  and labeled; SPEC B4.3's sentence names what the side-by-side shows
  (Record updates).
- **#4 no reader rule for the timer rows in `cost_model_outputs`** — amend:
  the rule under decision 2; the mart's header and SPEC B3.1's sentence
  (Scope, Record updates).
- **Q5 which decision the threshold prices** — answered: the hold planned
  at day 0 to run `N` days (ex-ante), the reading the study's sentence
  makes; the expression text says so; the marginal reading is a recorded
  rejection.
- **Q6 the simulator's names stay out of the cost-model marts** — answered:
  yes; the `scenario` column 8a freed is not used, because the simulator
  computes holds, not churn (a DECISIONS sentence).
- **#7 the rule restated as a property** — folded: CLAUDE.md and the
  DECISIONS "still in force" bullet (Record updates).
- **#8 `NormalDist.samples`** — folded: `samples` in the forbidden-name
  scan (invariant 8, Scope).
- **#9 pin `share_under` at the default day against the timer-released
  share** — folded: decision 6, Evidence row 6.
- **#10 the per-claim grain's reason in the header** — folded: decision 5.
- **#11 integer and boolean column types named** — folded: decision 5.

## Amendment A1 — the sim-mart bulk insert (post-approval, review round 1)

Review round 1 (code-reviewer, security notes) found `write_sim_marts` filling
the two marts with a mechanism the approved Scope did not name: a shared helper
`_insert_rows` running one `executemany` per mart under a `_no_pandas_probe`
context manager (a `None` sentinel in `sys.modules["pandas"]` for the duration
of the insert). The Scope named only `write_sim_marts`, and 8a's
`write_model_marts` inserts per row with `conn.execute`, so this was a write-path
change outside the stated scope — a design change owing an amendment.

Reverting to a per-row loop for consistency was tried and **measured**: it runs
the test suite in ~17 min against the guarded `executemany`'s ~2.5 min, because
DuckDB imports `pandas` to type-check every bound value, the import is absent and
uncached, and each ~4,000-row rebuild re-scans `sys.path` per value — a cost
every test that rebuilds pays. The developer chose to keep the optimization
under this amendment rather than accept the regression.

- **Scope.** `pipeline/build.py`'s Beat 4 write path is `write_sim_marts` plus
  the two module-level helpers it uses, `_no_pandas_probe` and `_insert_rows`.
  Both are used only by `write_sim_marts`; `table`/`columns` reach `_insert_rows`
  as caller literals (no foreign input in the SQL), the placeholder count is the
  columns' arity, and the sentinel is set only around the insert and restored in
  `finally`.
- **Invariant it upholds.** Invariant 6 — the two marts' rows are identical on
  any input, key set or unset, and on a re-run: `executemany` inserts the
  pre-built rows in scenario / rank and day order, byte-identical to the per-row
  path (`tests/test_sim_marts.py::test_two_rebuilds_identical_sim_mart_rows`,
  `::test_no_key…`). No literal number is typed on the path; the guard touches no
  data. `write_model_marts` (a few hundred rows) keeps its per-row insert — the
  probe cost is negligible there — so the two writers differ by row scale, on
  purpose.
- **Record.** DECISIONS → Phase 8b Gotchas describes the probe, the sentinel and
  the measured suite times.
