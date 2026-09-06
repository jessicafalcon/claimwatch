# Phase 8a — Cost model: formulas as data, sourced defaults, the crossover (PROPOSED)

Contract for the `phase-8a-cost-model` branch. Source: PROJECT_BRIEF.md §7 (the
deterministic cost model) and §9 Phase 8 ("Cost model + guardrail simulator"),
the cost-model half of a Phase 8 split: 8a lands Beat 3 (B3.1–B3.4); 8b lands
the guardrail simulator and the hold timer (B4.1–B4.3). Depends on Phase 7b
merged (PR #15, the fit `data/damir/claim_cost_fit.csv` this phase reads).

**Status: PROPOSED — do not start until approved.** No new dependency: the
arithmetic is stdlib `math`; the marts are filled through the existing DuckDB
seam. Amended 2026-09-06 after challenge round 1 (the dispositions are the
last section); every amendment is folded into the sections it changes.

Challenged: 2026-09-06, round 1, spec f52519a7 — approve with amendments (all amended, questions answered)

## Why

Beat 3 puts a euro figure on a wrongly held claim: how many claims a flag rate
holds, how many of those are legitimate, what the fraud caught is worth, what
the friction costs, and where the two curves cross (SPEC.md Beat 3). Every one
of those numbers must come from a formula the reader can see beside it, over
parameters that are either cited or openly marked as guesses (brief §2.4, §7).
Phase 7b landed the sourced input the claim-volume formula needs — the
lognormal fit over a real Open DAMIR slice — but no mart and no displayed
number: B3.1–B3.4 are still Pending.

Why a split, and not one Phase 8. Brief §9's Phase 8 is the cost model **and**
the guardrail simulator **and** the computed hold-timer threshold. Written as
one spec it carries eight pinned decisions and seven BACKING flips, over the
~6 cap (CLAUDE.md → Workflow rules). The seam is the one the brief itself
draws: §7's formulas and guardrail toggles are the cost model (8a, Beat 3);
the synthetic claims drawn from the fit, the hold durations and the day/euro
threshold are the simulator (8b, Beat 4). 8a leaves 8b a scenario column on
every output row, so the "curves move" panels of Beat 4 read the same marts.
Phase 7 was split the same way (7a/7b; DECISIONS → Phase 7b).

*Teaching note (lands in code and, in Phase 9, the README).* "Formulas are
data" means the model is an ordered list where each entry carries a name, the
formula written out as text, whether it is a single number or a point read off
the whole curve, and the function that computes it. The study prints the
text; a test evaluates the function at the
defaults and pins the result; the mart stores both side by side. The printed
formula and the computed number therefore cannot drift apart, because they are
one entry — 1:1 by construction, not by discipline (docs/PLAN.md §4 decision 5).

## The central constraint

**No number reaches a Beat 3 mart except through `models/cost_model.py`'s
ordered `FORMULAS` evaluated over its declared `PARAMETERS` — no random draw,
no clock, no key, no arithmetic in SQL — so two runs are byte-identical and
every value can be redone by hand from the expression printed beside it.**

## DONE command

```
make model && make idempotency-check ROWS=synthetic && make check-backing && make test
```

- `make model` — prints the parameter table (every row with its range; a
  sourced one with its citation), the formula table (each expression beside
  its value at the defaults, per scenario) and the two crossovers; a second run
  prints identical text. Offline, no variable, writes nothing.
- `make idempotency-check ROWS=synthetic` — two rebuilds, the model marts
  filled inside `rebuild()` on each; per-table row counts unchanged, the three
  model marts included. Their counts are constant by construction, so the
  proof that the *rows* are identical is the test named under Done-when 6,
  not this diff.
- `make check-backing` — B3.1–B3.4 now Modeled, each naming a `sql/marts/` file
  that exists; B4.1–B4.3 still Pending and named.
- `make test` — the pins over the defaults, the formulas-equal-mart proof, the
  closed sourcing set, the by-hand recomputation of every sourced default, the
  crossover rule, the byte-stable marts, the import allowlist for `models/`.
  Green with the key unset (nothing on this path calls a model).

## Done-when

1. **The formulas are data, in one place, printed beside their values.**
   `FORMULAS` is an ordered tuple of (name, expression text, kind, callable),
   `kind` from the closed set {`point`, `curve`}; `make model` prints each
   expression beside the value it produces at the defaults; the
   `cost_model_outputs` mart holds the same (scenario, name, expression, value)
   rows; a test evaluates every callable at the defaults and asserts the mart's
   values equal them and the pins. *Evidence: row 1.*
2. **Every parameter carries a range; every one is sourced or declared
   unsourced, nothing in between.** `PARAMETERS` is ordered; each carries a
   default, a unit, a `low` and `high` the study's sliders span, and a
   `sourcing` from the closed set {`sourced`, `unsourced`}; a sourced one also
   carries a citation and its range is the record's own bounds (rule under the
   parameter table); an unsourced one's range is the explore-the-range span.
   The `cost_model_params` mart holds one row per parameter with those cells;
   a test refuses a third kind of sourcing, a sourced parameter with no
   citation, any parameter whose range does not contain its default.
   *Evidence: row 2.*
3. **The sourced defaults are recomputed from the record by arithmetic shown,
   and the mean claim wears its bias.** Revenue per member = annual recurring
   revenue / members; the fraud pool = the published savings figure; mean
   claim = `exp(mu + sigma² / 2)` over the fit read from
   `data/damir/claim_cost_fit.csv` by a strict reader; claim volume = refunded
   total / mean claim; the median cell (`emp_p50`, read from the same
   artifact) is printed beside the mean as the contrast, with the caveat that a
   DAMIR cell sums one or more claims, so the mean overstates a claim's cost
   and the claim count and friction cost are understated. Each is either a
   cited parameter or a `FORMULAS` entry; a test recomputes every one of them
   the hand way, and the fit reader refuses a file with an unknown, missing or
   non-numeric name. *Evidence: row 3.*
4. **The curves cross, and the marker sits at the default.** `cost_curves`
   holds fraud saved, friction cost and net at every point of a fixed flag-rate
   grid, per scenario; exactly one row per scenario is marked as the default
   flag rate ("you are here"); two `curve`-kind `FORMULAS` entries print with
   their rules: the crossover is the first grid point where net is negative,
   and the marginal crossover is the first grid point whose net is below the
   previous point's (each null when none); a test pins both and checks both
   rules by hand. *Evidence: row 4.*
5. **The §7 guardrail toggles recompute the same formulas.** Scenarios are a
   closed set {`baseline`, `contacts_once`, `churn_halved`, `both`}, named by
   their effect so 8b's simulated hold timer needs no second `hold_timer`
   name: `contacts_once` sets contacts to one (brief §7's one-shot documents),
   `churn_halved` halves the churn probability (brief §7's hold timer), `both`
   applies both; every outputs and curves row carries its scenario; an unknown
   scenario name is refused; a test proves each scenario differs from the
   defaults in exactly its toggled parameters. *Evidence: row 5.*
6. **The model marts are part of every rebuild, byte-stable, and need no
   key.** `rebuild()` fills the three marts after `build_derived` on every
   `ROWS` input, so `idempotency-check` and every caller see them; two
   rebuilds give identical rows; every row carries `run_id` and the `Modeled`
   tag; `models/` imports no clock, random-number, network, database or
   model-client module and nothing from `opendata/`, `pipeline/` or `ingest/`
   (the fit is handed in by the caller); `make model` twice prints identical
   text. *Evidence: row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `make model` prints `name = expression → value` per formula; `tests/test_cost_model.py::test_formulas_evaluate_to_the_pins`, `tests/test_model_marts.py::test_outputs_mart_equals_formulas_at_defaults`, `tests/test_cost_model.py::test_make_model_prints_each_expression_beside_its_value` |
| 2 | `tests/test_cost_model.py::test_parameters_sourcing_is_a_closed_set`, `::test_sourced_needs_a_citation_every_range_holds_its_default`, `tests/test_model_marts.py::test_params_mart_has_one_row_per_parameter` |
| 3 | `tests/test_cost_model.py::test_sourced_defaults_recomputed_by_hand` (revenue per member, mean claim, claim volume from the pinned `mu`/`sigma`; the `mu`/`sigma` ranges from `n`), `::test_mean_claim_prints_its_bias_and_the_median_cell`; `tests/test_damir.py::test_read_fit_returns_the_pinned_fit`, `::test_read_fit_refuses_unknown_missing_or_non_numeric_names` |
| 4 | `tests/test_cost_model.py::test_crossover_is_first_grid_point_with_negative_net`, `::test_marginal_crossover_is_first_grid_point_below_the_previous`, `::test_curves_mark_exactly_one_default_per_scenario`; `make model` prints both crossover lines |
| 5 | `tests/test_cost_model.py::test_scenarios_are_a_closed_set`, `::test_each_scenario_changes_only_its_toggled_parameters` |
| 6 | `tests/test_model_marts.py::test_three_marts_filled_on_every_input`, `::test_two_rebuilds_identical_model_mart_rows`, `::test_rows_carry_run_id_and_modeled_tag`, `::test_models_imports_only_stdlib_math`, `::test_make_model_is_byte_identical_on_rerun`; `tests/test_no_key.py::test_no_key_model_marts_are_filled` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all parameter sets and scenarios, every number in a Beat 3 mart equals a `FORMULAS` callable evaluated over that set — never a literal typed anywhere else. | `tests/test_model_marts.py::test_outputs_mart_equals_formulas_at_defaults` — a mart value edited by hand, or a callable changed, fails against the other. |
| For all parameters, `sourcing` is one of two words, every parameter carries a range containing its default, and a sourced one also carries a citation. | `tests/test_cost_model.py::test_parameters_sourcing_is_a_closed_set` — a parameter declared `estimated`; `::test_sourced_needs_a_citation_every_range_holds_its_default` — a sourced parameter with an empty citation; a default outside its range. |
| For all sourced defaults, the value the model uses equals the hand recomputation from the cited record (the brief's §6 figures, the pinned fit). | `tests/test_cost_model.py::test_sourced_defaults_recomputed_by_hand` — recompute with `math` from `tests/pins.py`. |
| For all runs — any `ROWS` input, key set or unset, first or second rebuild — the three marts' rows are identical, and `make model`'s text is identical. | `tests/test_model_marts.py::test_two_rebuilds_identical_model_mart_rows`, `::test_make_model_is_byte_identical_on_rerun`, `tests/test_no_key.py::test_no_key_model_marts_are_filled`. |
| For all scenarios, the outputs are the same `FORMULAS` over a parameter set that differs from the defaults in exactly the scenario's toggled parameters; a name outside the set is refused. | `tests/test_cost_model.py::test_each_scenario_changes_only_its_toggled_parameters`, `::test_scenarios_are_a_closed_set` — `evaluate(scenario="fix_4")`. |
| For all flag-rate grids, the reported crossover is the first grid point with negative net, the reported marginal crossover is the first grid point whose net is below the previous point's (each null when none), and exactly one grid point per scenario is the default. | `tests/test_cost_model.py::test_crossover_is_first_grid_point_with_negative_net` — a grid whose net never turns negative; `::test_marginal_crossover_is_first_grid_point_below_the_previous` — a grid whose net only rises; `::test_curves_mark_exactly_one_default_per_scenario`. |
| For all files read as the fit artifact, only the declared names with numeric values are accepted; an unknown, missing or non-numeric name refuses with the name, never a silent default. | `tests/test_damir.py::test_read_fit_refuses_unknown_missing_or_non_numeric_names` — a file with `mu` missing; one with `mean` added; one with `sigma,abc`. |
| For all modules under `models/`, only stdlib modules that neither read a clock nor draw a random number are imported — no `opendata/`, `pipeline/` or `ingest/` module, no network, database or model-client module (the layer computes over what it is handed; it never reads a file, a warehouse or the wall clock). | `tests/test_model_marts.py::test_models_imports_only_stdlib_math` — every import in `models/` is from a closed allowlist (`math`, `dataclasses`, `typing`, `collections.abc`); the source scanned for `random`, `time`, `datetime`, `httpx`, `urllib`, `anthropic`, `duckdb`, `opendata`, `pipeline`, `ingest`. |

## Pinned decisions (do not re-litigate)

- **Formulas and parameters are data in `models/cost_model.py`; the layer is
  handed the fit and computes.** `FORMULAS` is an ordered tuple of
  `Formula(name, expression, kind, fn)` with `kind` from the closed set
  {`point`, `curve`}: a `point` entry is evaluated once per parameter set,
  its callable reading the parameters and the results before it; a `curve`
  entry is evaluated once per scenario over the grid's rows (the two
  crossovers). `PARAMETERS` is an ordered tuple of `Parameter(name, default,
  unit, sourcing, citation, low, high)`; `defaults(fit)` builds the parameter
  set from the static table plus the `mu`, `sigma` and `emp_p50` rows the
  caller's `Fit` supplies, so `models/` reads no file; `evaluate(params,
  scenario)` runs the point entries in order; `curves(params, scenario)` runs
  the grid and the curve entries; one `rounded(unit, value)` is the single
  rounding site the writer, the printer and the tests call. Rejected:
  formulas in a YAML the code evaluates from text (a string that can drift
  from what runs, and evaluating text is the wrong kind of guard); a formula
  typed in SQL (a second copy, and `exp` is a dialect risk); the crossover as
  a `point` entry that re-runs the grid at every grid point (41 grids per
  scenario for one number); `models/` importing `opendata.fit` to read the
  artifact at import time (the layer would depend on the package whose
  sibling is the network fetch). Satisfies invariants 1–2 and 8.
- **Every parameter carries a range; sourced defaults cite the record the
  way the anchors do; the fit is read beside its writer.** Annual recurring
  revenue, members, the fraud-savings figure and the refunded total are
  `sourced` parameters whose citation is `PROJECT_BRIEF.md §6` — the anchors'
  `seeded_from` precedent, because a disclosure page's address carries the
  brand and may live only in `ingest/sources.py` (DECISIONS → Phase 3a, D1).
  That citation is second-hand: §6 records the four figures as "public
  disclosures" with no address, each given as a floor ("1M+", "€800M+",
  "€350M+", "~€4M"), and the study says so beside them ("as disclosed; a lower
  bound"). When the developer hands over a disclosure address, it becomes a
  brand-free declaration in `ingest/sources.py` under D1 and the citation
  points there (a BACKLOG row with that trigger; a DECISIONS extension and a
  security-reviewer surface when it fires, not this phase). The range rule,
  one per sourcing: a sourced figure the record gives as a floor has `low` =
  the default and `high` = twice it — the upper end is the study's stated
  exploration bound, printed as such, never a fact; `mu` and `sigma` have
  `low`/`high` = the fit ± 2 standard errors, `se_mu = sigma / √n` and
  `se_sigma = sigma / √(2n)` over the artifact's `n`, arithmetic printed;
  an unsourced parameter's range is the explore-the-range span in the table.
  `mu`, `sigma` and `emp_p50` are `sourced` parameters read by
  `opendata/fit.py::read_fit` (the writer's sibling, the one place that knows
  the artifact's shape: the declared names, numeric values, refuses anything
  else; returns the `Fit` and the deciles `write_fit` wrote) with the citation
  `data/damir/claim_cost_fit.csv` ← `open-damir`; the caller (`rebuild`, the
  `model` subcommand) reads once and hands the result to `defaults(fit)`.
  Mean claim and claim volume are `FORMULAS` entries; `mean_claim`'s
  expression text carries the bias direction — a DAMIR cell sums one or more
  claims, so the mean overstates a claim's cost and `claims` and
  `friction_cost` are understated, the flattering direction — and the
  `median_cell` entry (`emp_p50`, the middle cell) prints beside it as the
  contrast a reader needs to see how wide the lognormal's tail is.
  `cost_per_contact` is `unsourced` unless the developer hands a citable
  public benchmark before "build" (then a one-cell flip in `PARAMETERS`, no
  design change; brief §7 allows either). Rejected: a second anchors CSV
  under `fixtures/` for five figures the brief carries (a fixture change, and
  `fixtures/` is read-only); the fit reader in `models/` (a second module
  knowing the artifact's shape); a range only on unsourced parameters (brief
  §3 Beat 3 asks for a slider on every assumption, and the widest real
  uncertainty — `claims` through `mu`/`sigma` — would be the one a reader
  could not move); the fixture's arithmetic mean as a third sibling (it needs
  a new artifact row from 7b's writer and a re-run of `fit-damir`: a tracked
  artifact change, deferred to a BACKLOG row). Satisfies invariants 2–3 and 7.
- **Three DDL-only Python-fed marts, one writer, filled inside `rebuild()`;
  `make model` prints and writes nothing.** `sql/marts/cost_model_params.sql`,
  `cost_model_outputs.sql` and `cost_curves.sql` are `create or replace table
  (…)` shapes run by the generic marts loop (so the tables always exist after
  a rebuild — the `classifier_quality` precedent);
  `pipeline/build.py::write_model_marts(conn, fit, run_id)` clears and inserts
  the three in one transaction, rows in `FORMULAS` and grid order, and
  `rebuild()` calls it after `build_derived` on every input, so
  `idempotency_check` (which calls `rebuild()` only) and every other caller
  see filled marts and the returned counts dict includes them; the model
  marts need nothing from the classify step, which is why 7a's reason for
  filling `classifier_quality` outside `rebuild()` (its callers read a counts
  dict, and the classify step reads a key) does not apply here. `make model`
  (no variable) computes and prints, so the developer reads the arithmetic
  without a warehouse. Rejected: `create … as select` marts over a parameters
  table (arithmetic in SQL — a second copy of the formulas and a portability
  risk); a model step in `pipeline/cli.py` after the classify step (the
  proposal before the challenge: `idempotency_check` would have diffed three
  empty tables, 0 → 0). Satisfies invariants 1 and 4.
- **A fixed flag-rate grid; two crossovers, both grid rules; the default is
  marked.** The grid is 0.000 to 0.200 in steps of 0.005 (41 points), per
  scenario; `flag_rate` is an `unsourced` parameter whose default lies on the
  grid, and that row is the "you are here" marker. Two `curve` entries:
  `crossover_flag_rate`, the first grid point whose net is negative — where
  the two curves cross, past which the flags as a whole cost more than they
  recover; and `marginal_crossover_flag_rate`, the first grid point whose net
  is below the previous point's — past which each extra flag costs more than
  it recovers, which comes earlier; each null when none, each expression text
  stating its rule. The chart's sentence names the crossing; the marginal
  point is printed beside it (SPEC.md B3.2 reworded, Record updates). Net is
  zero at the origin and concave in the flag rate, so each rule fires at most
  once and the "first" is well defined; a test states that as the hand check.
  Rejected: a bisection root (harder to redo by hand — the grid *is* the
  arithmetic); an analytic root (none exists for the crossing with the
  exponential term; the marginal one has a closed form, but a second method
  for one of two points is a second copy); one crossover only (the proposal
  before the challenge: the chart sentence describes the marginal point while
  the drawn crossing is the total one, and the default marker sits between
  them, so the sentence and the point would disagree). Satisfies invariant 6.
- **Scenarios are a closed set of parameter overrides applied before
  evaluation, named by their effect.** `SCENARIOS`: `baseline` (no override),
  `contacts_once` (`contacts` → 1; brief §7's one-shot documents),
  `churn_halved` (`churn_prob` → default / 2; brief §7's hold timer), `both`
  (the union) — the effects brief §7 states, labeled illustrative; `make
  model` prints each scenario's overrides. Every outputs and curves row
  carries `scenario`, which is what lets 8b's "the curves move" panels read
  these marts unchanged; 8b's simulated hold timer gets its own name in the
  same column, no collision. Rejected: one mart per scenario (four copies of
  one shape); free-text scenario names (an open set); `ask_once`/`hold_timer`
  (the proposal before the challenge: `hold_timer` would collide with 8b's
  simulated timer in the same column). The hold timer's own arithmetic — N
  days, €X, the synthetic claims — is 8b. Satisfies invariant 5.
- **Written numbers are rounded to fixed places at one site; the pins hold
  the rounded values.** Euro values to 2 decimals, rates and shares to 6,
  counts whole (the `opendata/fit.py` precedent), applied by
  `models/cost_model.py::rounded(unit, value)` — the writer, `make model`'s
  printer and the tests all call it, so mart rows and printed text are
  byte-identical across runs and machines. Rejected: `Decimal` arithmetic end
  to end (the exponential term forces float anyway); rounding in the writer
  and again in the printer (two sites for one rule). Satisfies invariant 4.

### The parameter table as proposed (defaults; every unsourced one is a guess to explore, never a fact; every row has a range)

| Name | Default | Unit | Sourcing | Citation | Range (`low`–`high`) |
|---|---|---|---|---|---|
| `arr_eur` | 800,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 (public disclosure, second-hand: "€800M+ annual recurring revenue") | the floor and twice it: 800M–1.6B (exploration bound) |
| `members` | 1,000,000 | members | sourced | PROJECT_BRIEF.md §6 ("1M+ members") | 1M–2M (exploration bound) |
| `fraud_pool_eur` | 4,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 ("~€4M fraud savings (2024)"), presented as a lower bound | 4M–8M (exploration bound) |
| `refunded_eur` | 350,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 ("€350M+ claims refunded per year") | 350M–700M (exploration bound) |
| `mu`, `sigma` | 3.809814, 2.187981 | log-euros | sourced | `data/damir/claim_cost_fit.csv` (`open-damir`, July 2025, legal reimbursement only) | the fit ± 2 standard errors from the artifact's `n` (arithmetic printed) |
| `emp_p50` | 49.76 | € | sourced | the same artifact (the middle DAMIR cell; the contrast printed beside `mean_claim`) | itself (a read figure; the slider is `mu`/`sigma`) |
| `flag_rate` | 0.05 | share of claims | unsourced | — | 0.00–0.20 |
| `fp_share` | 0.50 | share of flagged | unsourced | — | 0.10–0.90 |
| `contacts` | 3 | contacts per stuck claim | unsourced | — | 1–8 |
| `cost_per_contact` | 8 | € | unsourced (flips to sourced if a public benchmark is handed over before build) | — | 2–30 |
| `churn_prob` | 0.05 | probability | unsourced | — | 0.00–0.30 |
| `k` | 8 | — (diminishing-returns constant; brief §7 "k ≈ 8, stated as an assumption") | unsourced | — | 2–20 |

The formulas, in order (brief §7, plus the three derived defaults, the
contrast and the two crossovers). Point entries: `customer_value = arr_eur /
members`; `mean_claim = exp(mu + sigma² / 2)` (its expression text carries the
bias caveat: a DAMIR cell sums one or more claims, so this overstates a claim
and understates `claims` and `friction_cost`); `median_cell = emp_p50` (the
contrast); `claims = refunded_eur / mean_claim`; `flagged = claims ×
flag_rate`; `false_pos = flagged × fp_share`; `fraud_saved = fraud_pool_eur ×
(1 − e^(−k × flag_rate))`; `friction_cost = false_pos × (contacts ×
cost_per_contact + churn_prob × customer_value)`; `net = fraud_saved −
friction_cost`. Curve entries: `crossover_flag_rate = the first grid flag rate
with net < 0`; `marginal_crossover_flag_rate = the first grid flag rate whose
net is below the previous grid point's`. Their values at the defaults are
computed at build and pinned in `tests/pins.py`; this spec names none, so no
number is stated before its formula runs. (The challenger computed them from
the record as a plausibility check, and the crossing lands inside the grid
with the default marker left of it; the pins are still typed only from the
built output.) If the defaults put a crossover outside the grid or the marker
right of it, the chart is published as it comes out (SPEC.md → "hypothesis,
not verdict") — the defaults are not tuned to tell a story; a change to one is
a `PARAMETERS` cell with its range, recorded.

## Scope (files)

- `models/__init__.py`, `models/cost_model.py` — new package: `Parameter`,
  `Formula`, `PARAMETERS`, `FORMULAS`, `SCENARIOS`, `FLAG_RATE_GRID`,
  `defaults`, `evaluate`, `curves`, `rounded`, `format_model`; the teaching
  docstring; stdlib `math` only. (The package is on `architecture-fit`'s
  paths; `models/guardrail_sim.py` is 8b.)
- `opendata/fit.py` — `read_fit(path) -> tuple[Fit, list[Decile]]`: the
  strict reader of the artifact its `write_fit` writes, the mirror of that
  writer's shape.
- `sql/marts/cost_model_params.sql`, `sql/marts/cost_model_outputs.sql`,
  `sql/marts/cost_curves.sql` — DDL only; headers name grain, provenance
  (`run_id`, `tag`) and the rows fed (B3.3+B3.4, B3.1, B3.2).
- `pipeline/build.py` — `write_model_marts(conn, fit, run_id)`, called by
  `rebuild()` after `build_derived`; the three names run in the generic marts
  loop unchanged (DDL only).
- `pipeline/cli.py` — the `model` subcommand (no variable): reads the fit,
  prints `format_model`. No change to the rebuild path (it is inside
  `build.rebuild`).
- `Makefile` — `model` target, `.PHONY`, help line; the header comment's
  "model (8)" becomes what exists.
- `tests/test_cost_model.py`, `tests/test_model_marts.py` — new;
  `tests/test_damir.py` (`read_fit`; and
  `test_no_new_mart_files_and_marts_are_phase_8` loses its
  `cost_model_params.sql` assertion, keeping the `guardrail_sim.sql` half for
  8b — a 7b placeholder giving way as planned, not a weakened test),
  `tests/test_no_key.py` (the model marts under a no-key rebuild),
  `tests/pins.py` (the defaults' outputs, both crossovers, the `mu`/`sigma`
  ranges, the curve-row count).
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `BACKING.md`, `SPEC.md`
  (tag markers, the B3.2 crossing sentence and the B3.4 slider list), this
  spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 8a entry: the 8a/8b split and its seam; the six
  pinned decisions with their rejected alternatives (the challenge round's
  four reversals named as such: marts filled inside `rebuild()`, two
  crossovers, scenarios by effect, a range on every parameter); the
  `cost_per_contact` sourcing outcome; the second-hand citation for the four
  scale anchors; Gotchas if any (DuckDB `double`/`null` binding, the `create
  or replace` + delete/insert order).
- [ ] `BACKLOG.md` — three new rows: a citable customer-contact cost
  benchmark (trigger: one found → `cost_per_contact` flips to sourced); the
  four scale anchors' disclosure addresses (trigger: the developer hands one
  over → a brand-free declaration in `ingest/sources.py` under D1, the
  citation cell points there); the fixture's arithmetic mean as a third
  sibling beside `mean_claim` (trigger: Phase 9 wants a `claims` slider
  spanning it → one `mean` row from `opendata/fit.py::write_fit`, a re-run of
  `fit-damir`, a DECISIONS line for the tracked-artifact change). The
  "data.ameli practitioner-fee distributions" row's trigger re-checked (8a
  does not need it; re-deferred to 8b/the study, trigger reworded); count
  updated.
- [ ] `CLAUDE.md` — Current status; Commands (`model`: offline, no variable,
  prints and writes nothing; `rebuild` fills the model marts after the marts
  loop); Repo map (`models/` loses "(Phase 8)", names
  `cost_model.py::FORMULAS` as landed and `guardrail_sim.py` as 8b;
  `sql/marts/` line counts the three new Python-fed marts); BACKLOG count.
- [ ] `BACKING.md` — B3.1, B3.2, B3.3, B3.4 Pending → Modeled (files exist);
  the note under the table on the `open-damir` upstream updated: B3.3 now
  displays the fit through `mean_claim` with the median cell beside it;
  B4.1–B4.3 stay Pending, named for 8b. B4.1's mapping, decided here and
  recorded there: the `contacts_once` rows of `cost_curves` are the "curves
  move" half of B4.1, but Beat 4 flips as one beat in 8b, so B4.1 stays
  Pending on `guardrail_sim` now and 8b's spec re-points its mart cell to
  `cost_curves` (scenario `contacts_once`) beside the simulator's hold
  durations when it lands Beat 4.
- [ ] `SPEC.md` — Beat 3 panels B3.1–B3.4: the "(Pending until the model mart
  lands)" / "(Pending)" markers removed, tag stays *Modeled* — the tag state
  moving as planned, not a chart change (the Beat 2 precedent after 7a). Two
  deliberate wording changes, and no other: B3.2's crossing sentence becomes
  "Where the curves cross, the flags as a whole cost more than they recover;
  the earlier point where each extra flag starts to cost more than it
  recovers is printed beside it" (the sentence now names the drawn crossing,
  not the marginal point); B3.4's slider list names all six unsourced
  parameters — the false-positive share, the churn probability, contacts per
  stuck claim, the flag rate, the diminishing-returns constant and the cost
  per contact. No panel added.
- [ ] README — none (no README.md exists yet; it lands in Phase 9; the
  formulas-as-data teaching sentence lives in `models/cost_model.py`'s
  docstring until then).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make model` runs `uv run python -m pipeline model` with no
variable (the `fit-damir` shape): it reads `models/` and the tracked fit
artifact, prints, and writes nothing. Run twice: identical text. No
credentials: identical text (nothing on the path reads a key). The rebuild's
model step adds no variable to `rebuild` and no path derived from user input.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `model` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_model_marts.py::test_make_model_is_byte_identical_on_rerun` (the target exists, takes nothing, prints the same twice) |

## Review & stack risk

- **code-reviewer** (triggered — `*.py`, `sql/**`, `Makefile`, `tests/`): the
  formulas as the one place (a formula string typed anywhere else — SQL, the
  printer, a test — is a finding); the closed sourcing set and closed scenario
  set as data, not `if` chains; no literal number in the writer; one rounding
  site (`rounded`), called, never re-implemented; `write_model_marts` inside
  `rebuild()` after `build_derived`; `models/` imports stdlib `math` only;
  scope (Beat 3 only — a hold duration or a synthetic claim in this diff is
  8b's).
- **security-reviewer** (mandatory by lookup — `opendata/fit.py` and
  `pipeline/cli.py` are on the Sensitive list): `read_fit` as a strict parse
  of a tracked, numbers-only file (declared names, numeric values, size cap,
  refuses by name); no new network, paid or delete path; `make model` and the
  `model` subcommand unarmed and variable-free; the `GATED` set unchanged.
- **functionality-tester** (after code-reviewer): the DONE command; the
  no-key run; hand-mutation in a worktree — a callable's operator changed
  fails the pins, a mart value edited fails the formulas-equal-mart test, a
  `sourcing` cell changed to a third word is refused, a grid with no negative
  net yields a null crossover.
- **study-editor** (triggered — BACKING claim cells, CLAUDE.md, the SPEC tag
  markers): every unsourced default reads as a guess to explore, never a
  fact; the sourced citations name the brief section, never a company page,
  and say they are second-hand floors; the bias caveat and the median cell
  stay beside `mean_claim`; the two SPEC sentences read in the two-layer
  voice; no banned word.
- **coherence-auditor** at exit: SPEC Beat 3 panels no longer say Pending and
  BACKING B3 rows are Modeled with existing files; CLAUDE.md's repo map no
  longer says `models/ (Phase 8)`; BACKING's `open-damir` note no longer says
  B3.3 stays Pending; the 8b rows (B4.1–B4.3) still Pending and named; the
  Makefile header names `model` as built; PLAN §5's one-row Phase 8 is
  reconciled by the DECISIONS entry (the 7a/7b precedent).
- Stack risk (verify in the first hour): DuckDB binding of Python `None` into
  a `double` column for a null crossover, and of large floats without a
  rounding surprise, through the existing `run_sql_file` / parameterised
  insert path; `create or replace table` in the generic loop followed by
  delete/insert in the same connection (the `classifier_quality` precedent —
  confirm the order holds under `idempotency-check`). Compute the defaults'
  outputs before any pin is typed; if the story does not hold at the
  defaults, STOP and report — do not tune a default to make it hold. Findings
  go to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- **Phase 8b — the guardrail simulator and the hold timer (B4.1–B4.3):**
  synthetic claims drawn from the fit by quantile (no random draw), hold
  durations before and after each fix, the computed day/euro threshold
  ("holds beyond N days on claims under €X are net-negative in expectation"),
  the `guardrail_sim` and `sla_threshold` marts. B4.4 stays a design panel
  (Pending, no number) until an outcome log exists — not a Phase 8 deliverable.
- **Slider recompute in the study** — how a static page recomputes `FORMULAS`
  when a slider moves is Phase 9's decision; 8a's marts hold the defaults and
  the curve grid, and `expression` is the text the page prints (the 1:1
  mirror). A pre-computed parameter sweep mart is refused here (a parameter ×
  grid explosion for a question Phase 9 has not asked).
- **A citable customer-contact cost benchmark** — BACKLOG row with its
  trigger; until then `cost_per_contact` is a declared guess.
- **The four scale anchors' disclosure addresses** — BACKLOG row; until one
  is handed over the citation is the brief's §6, said to be second-hand.
- **The fixture's arithmetic mean as a third sibling beside `mean_claim`** —
  BACKLOG row; it needs a new artifact row from 7b's writer and a re-run of
  `fit-damir` (a tracked-artifact change with its DECISIONS line).
- **data.ameli practitioner-fee distributions** — BACKLOG (Phase 7b), trigger
  re-checked at this exit: 8a needs only the DAMIR amount fit.
- **A sensitivity table or a fitted anything** — the model is the arithmetic
  shown; no optimizer, no calibration of the unsourced defaults to data
  (brief §2.1, §10).

## Challenge round 1 — dispositions (2026-09-06)

`/challenge` on the spec as first committed (8fe2182): 0 BLOCKER, 5
should-fix, 4 suggestions, 2 questions; verdict "approve with amendments".
Every finding is folded into the sections above; this block is the record of
what each became.

- **#1 mean-claim divisor, unvalidated tail, no range** — amend: the bias
  direction in `mean_claim`'s expression text, `median_cell` (`emp_p50`) as
  the printed contrast, ± 2 standard-error ranges on `mu`/`sigma`; the sample
  mean deferred to a BACKLOG row. Restores invariant 3 (the value the model
  uses is recomputed from the record, and the record's limits are shown).
- **#2 `idempotency-check` never sees a CLI model step** — amend: the marts
  are filled inside `rebuild()` after `build_derived`. Restores invariant 4.
- **#3 the chart sentence names the marginal point, the mart the crossing** —
  amend: two `curve` entries; SPEC B3.2 reworded (Record updates). Restores
  invariant 6.
- **#4 no range on sourced parameters** — amend: every parameter carries a
  range; the sourced rule (floor and twice it; the fit ± 2 SE). Invariant 2
  reworded.
- **#5 SPEC B3.4 lists three sliders, the mart six** — amend: the sentence
  change is a named Record update.
- **#6 `hold_timer` collides with 8b** — amend: `contacts_once`,
  `churn_halved`, `both`.
- **#7 a curve quantity in a per-point list** — amend: `Formula.kind` ∈
  {`point`, `curve`}.
- **#8 `models/` reads the artifact through `opendata`; two rounding sites** —
  amend: `defaults(fit)` takes the caller's `Fit`; one `rounded(unit, value)`.
  Invariant 8 tightened to an import allowlist.
- **#9 the 7b placeholder test goes red** — amend: named in Scope.
- **#10 is "PROJECT_BRIEF.md §6" a followable citation?** — answered: no, it
  is second-hand, and the spec and the study say so; the four figures are
  floors; an address, when handed over, becomes a D1 declaration (BACKLOG
  row).
- **#11 does B4.1 flip in 8a?** — answered: no; Beat 4 flips as one beat in
  8b, which re-points B4.1's mart cell to `cost_curves` (Record updates).
