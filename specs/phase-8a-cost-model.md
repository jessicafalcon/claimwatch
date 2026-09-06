# Phase 8a — Cost model: formulas as data, sourced defaults, the crossover (PROPOSED)

Contract for the `phase-8a-cost-model` branch. Source: PROJECT_BRIEF.md §7 (the
deterministic cost model) and §9 Phase 8 ("Cost model + guardrail simulator"),
the cost-model half of a Phase 8 split: 8a lands Beat 3 (B3.1–B3.4); 8b lands
the guardrail simulator and the hold timer (B4.1–B4.3). Depends on Phase 7b
merged (PR #15, the fit `data/damir/claim_cost_fit.csv` this phase reads).

**Status: PROPOSED — do not start until approved.** No new dependency: the
arithmetic is stdlib `math`; the marts are filled through the existing DuckDB
seam.

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
data" means the model is an ordered list where each entry carries three
things: a name, the formula written out as text, and the function that
computes it. The study prints the text; a test evaluates the function at the
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

- `make model` — prints the parameter table (each row sourced-with-citation or
  unsourced-with-range), the formula table (each expression beside its value at
  the defaults, per scenario) and the crossover; a second run prints identical
  text. Offline, no variable, writes nothing.
- `make idempotency-check ROWS=synthetic` — two rebuilds, each running the new
  model step after the classify step; per-table row counts unchanged, the three
  model marts included.
- `make check-backing` — B3.1–B3.4 now Modeled, each naming a `sql/marts/` file
  that exists; B4.1–B4.3 still Pending and named.
- `make test` — the pins over the defaults, the formulas-equal-mart proof, the
  closed sourcing set, the by-hand recomputation of every sourced default, the
  crossover rule, the byte-stable marts, the import allowlist for `models/`.
  Green with the key unset (nothing on this path calls a model).

## Done-when

1. **The formulas are data, in one place, printed beside their values.**
   `FORMULAS` is an ordered tuple of (name, expression text, callable);
   `make model` prints each expression beside the value it produces at the
   defaults; the `cost_model_outputs` mart holds the same (scenario, name,
   expression, value) rows; a test evaluates every callable at the defaults and
   asserts the mart's values equal them and the pins. *Evidence: row 1.*
2. **Every parameter is sourced or declared unsourced, nothing in between.**
   `PARAMETERS` is ordered; each carries a default, a unit, a `sourcing` from
   the closed set {`sourced`, `unsourced`}, and either a citation (sourced) or
   an explore-the-range low and high (unsourced). The `cost_model_params` mart
   holds one row per parameter with those cells; a test refuses a third kind of
   sourcing, a sourced parameter with no citation, an unsourced one with no
   range. *Evidence: row 2.*
3. **The sourced defaults are recomputed from the record by arithmetic shown.**
   Revenue per member = annual recurring revenue / members; the fraud pool =
   the published savings figure; mean claim = `exp(mu + sigma² / 2)` over the
   fit read from `data/damir/claim_cost_fit.csv` by a strict reader; claim
   volume = refunded total / mean claim. Each is either a cited parameter or a
   `FORMULAS` entry; a test recomputes every one of them the hand way, and the
   fit reader refuses a file with an unknown, missing or non-numeric name.
   *Evidence: row 3.*
4. **The curves cross, and the marker sits at the default.** `cost_curves`
   holds fraud saved, friction cost and net at every point of a fixed flag-rate
   grid, per scenario; exactly one row per scenario is marked as the default
   flag rate ("you are here"); the crossover is the first grid point where net
   is negative (null when none), reported as a `FORMULAS` entry so it prints
   with its rule; a test pins it and checks the first-negative rule by hand.
   *Evidence: row 4.*
5. **The §7 guardrail toggles recompute the same formulas.** Scenarios are a
   closed set {`baseline`, `ask_once`, `hold_timer`, `both`}: `ask_once` sets
   contacts to one, `hold_timer` halves the churn probability, `both` applies
   both; every outputs and curves row carries its scenario; an unknown scenario
   name is refused; a test proves each scenario differs from the defaults in
   exactly its toggled parameters. *Evidence: row 5.*
6. **The model marts are part of every rebuild, byte-stable, and need no
   key.** Every `ROWS` input fills the three marts after the classify step; two
   rebuilds give identical rows; every row carries `run_id` and the `Modeled`
   tag; `models/` imports no clock, random-number, network, database or
   model-client module; `make model` twice prints identical text. *Evidence:
   row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `make model` prints `name = expression → value` per formula; `tests/test_cost_model.py::test_formulas_evaluate_to_the_pins`, `tests/test_model_marts.py::test_outputs_mart_equals_formulas_at_defaults`, `tests/test_cost_model.py::test_make_model_prints_each_expression_beside_its_value` |
| 2 | `tests/test_cost_model.py::test_parameters_sourcing_is_a_closed_set`, `::test_sourced_needs_a_citation_unsourced_needs_a_range`, `tests/test_model_marts.py::test_params_mart_has_one_row_per_parameter` |
| 3 | `tests/test_cost_model.py::test_sourced_defaults_recomputed_by_hand` (revenue per member, mean claim, claim volume from the pinned `mu`/`sigma`); `tests/test_damir.py::test_read_fit_returns_the_pinned_fit`, `::test_read_fit_refuses_unknown_missing_or_non_numeric_names` |
| 4 | `tests/test_cost_model.py::test_crossover_is_first_grid_point_with_negative_net`, `::test_curves_mark_exactly_one_default_per_scenario`; `make model` prints the crossover line |
| 5 | `tests/test_cost_model.py::test_scenarios_are_a_closed_set`, `::test_each_scenario_changes_only_its_toggled_parameters` |
| 6 | `tests/test_model_marts.py::test_three_marts_filled_on_every_input`, `::test_two_rebuilds_identical_model_mart_rows`, `::test_rows_carry_run_id_and_modeled_tag`, `::test_models_imports_no_clock_rng_network_db_or_model`, `::test_make_model_is_byte_identical_on_rerun`; `tests/test_no_key.py::test_no_key_model_marts_are_filled` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all parameter sets and scenarios, every number in a Beat 3 mart equals a `FORMULAS` callable evaluated over that set — never a literal typed anywhere else. | `tests/test_model_marts.py::test_outputs_mart_equals_formulas_at_defaults` — a mart value edited by hand, or a callable changed, fails against the other. |
| For all parameters, `sourcing` is one of two words, a sourced one carries a citation and an unsourced one carries a range. | `tests/test_cost_model.py::test_parameters_sourcing_is_a_closed_set` — a parameter declared `estimated`; `::test_sourced_needs_a_citation_unsourced_needs_a_range`. |
| For all sourced defaults, the value the model uses equals the hand recomputation from the cited record (the brief's §6 figures, the pinned fit). | `tests/test_cost_model.py::test_sourced_defaults_recomputed_by_hand` — recompute with `math` from `tests/pins.py`. |
| For all runs — any `ROWS` input, key set or unset, first or second rebuild — the three marts' rows are identical, and `make model`'s text is identical. | `tests/test_model_marts.py::test_two_rebuilds_identical_model_mart_rows`, `::test_make_model_is_byte_identical_on_rerun`, `tests/test_no_key.py::test_no_key_model_marts_are_filled`. |
| For all scenarios, the outputs are the same `FORMULAS` over a parameter set that differs from the defaults in exactly the scenario's toggled parameters; a name outside the set is refused. | `tests/test_cost_model.py::test_each_scenario_changes_only_its_toggled_parameters`, `::test_scenarios_are_a_closed_set` — `evaluate(scenario="fix_4")`. |
| For all flag-rate grids, the reported crossover is the first grid point with negative net (null when none) and exactly one grid point per scenario is the default. | `tests/test_cost_model.py::test_crossover_is_first_grid_point_with_negative_net` — a grid whose net never turns negative; `::test_curves_mark_exactly_one_default_per_scenario`. |
| For all files read as the fit artifact, only the declared names with numeric values are accepted; an unknown, missing or non-numeric name refuses with the name, never a silent default. | `tests/test_damir.py::test_read_fit_refuses_unknown_missing_or_non_numeric_names` — a file with `mu` missing; one with `mean` added; one with `sigma,abc`. |
| For all modules under `models/`, no clock, random-number, network, database or model-client module is imported (the layer computes; it never reads a warehouse or the wall clock). | `tests/test_model_marts.py::test_models_imports_no_clock_rng_network_db_or_model` — the source scanned for `random`, `time`, `datetime`, `httpx`, `urllib`, `anthropic`, `duckdb`. |

## Pinned decisions (do not re-litigate)

- **Formulas and parameters are data in `models/cost_model.py`.** `FORMULAS`
  is an ordered tuple of `Formula(name, expression, fn)`; `PARAMETERS` an
  ordered tuple of `Parameter(name, default, unit, sourcing, citation, low,
  high)`; `evaluate(params, scenario)` runs the list in order, each callable
  reading the parameters and the results before it. The proposed table is
  appended below. Rejected: formulas in a YAML the code evaluates from text (a
  string that can drift from what runs, and evaluating text is the wrong kind
  of guard); a formula typed in SQL (a second copy, and `exp` is a dialect
  risk). Satisfies invariants 1–2.
- **Sourced defaults cite the record the way the anchors do; the fit is read
  beside its writer.** Annual recurring revenue, members, the fraud-savings
  figure and the refunded total are `sourced` parameters whose citation is
  `PROJECT_BRIEF.md §6` — the anchors' `seeded_from` precedent, because a
  disclosure page's address carries the brand and may live only in
  `ingest/sources.py` (DECISIONS → Phase 3a, D1). `mu` and `sigma` are
  `sourced` parameters read by `opendata/fit.py::read_fit` (the writer's
  sibling, the one place that knows the artifact's shape: declared names,
  numeric values, refuses anything else) with the citation
  `data/damir/claim_cost_fit.csv` ← `open-damir`; mean claim and claim volume
  are `FORMULAS` entries, printed with the caveat that a DAMIR cell is an
  aggregated total, so the mean approximates a claim's cost. `cost_per_contact`
  is `unsourced` unless the developer hands a citable public benchmark before
  "build" (then a one-cell flip in `PARAMETERS`, no design change; brief §7
  allows either). Rejected: a second anchors CSV under `fixtures/` for five
  figures the brief carries (a fixture change, and `fixtures/` is read-only);
  the fit reader in `models/` (a second module knowing the artifact's shape).
  Satisfies invariants 2–3 and 7.
- **Three DDL-only Python-fed marts, one writer, a model step in every
  rebuild; `make model` prints and writes nothing.** `sql/marts/
  cost_model_params.sql`, `cost_model_outputs.sql` and `cost_curves.sql` are
  `create or replace table (…)` shapes run by the generic marts loop (so the
  tables always exist after a rebuild — the `classifier_quality` precedent);
  `pipeline/build.py::write_model_marts(conn, rows, run_id)` clears and
  inserts the three in one transaction, rows in `FORMULAS` and grid order;
  `pipeline/cli.py`'s rebuild runs the model step after the classify step on
  every input with `run_id` = the input name (the classify precedent); `make
  model` (no variable) computes and prints, so the developer reads the
  arithmetic without a warehouse. Rejected: `create … as select` marts over a
  parameters table (arithmetic in SQL — a second copy of the formulas and a
  portability risk); filling inside `rebuild()` (its callers read a counts
  dict; the 7a reasoning holds). Satisfies invariants 1 and 4.
- **A fixed flag-rate grid; the crossover is the first negative net; the
  default is marked.** The grid is 0.000 to 0.200 in steps of 0.005 (41
  points), per scenario; `flag_rate` is an `unsourced` parameter whose default
  lies on the grid, and that row is the "you are here" marker; the crossover
  is the first grid point whose net is negative, or null when none, and is a
  `FORMULAS` entry (`crossover_flag_rate`) whose expression text states the
  rule. Rejected: a bisection root (harder to redo by hand — the grid *is* the
  arithmetic); an analytic root (none exists with the exponential term).
  Satisfies invariant 6.
- **Scenarios are a closed set of parameter overrides applied before
  evaluation.** `SCENARIOS`: `baseline` (no override), `ask_once` (`contacts`
  → 1), `hold_timer` (`churn_prob` → default / 2), `both` (the union) — the
  effects brief §7 states, labeled illustrative; `make model` prints each
  scenario's overrides. Every outputs and curves row carries `scenario`, which
  is what lets 8b's "the curves move" panels read these marts unchanged.
  Rejected: one mart per scenario (four copies of one shape); free-text
  scenario names (an open set). The hold timer's own arithmetic — N days, €X,
  the synthetic claims — is 8b. Satisfies invariant 5.
- **Written numbers are rounded to fixed places; the pins hold the rounded
  values.** Euro values to 2 decimals, rates and shares to 6, counts whole
  (the `opendata/fit.py` precedent), applied at the one writer and in `make
  model`'s printer, so mart rows and printed text are byte-identical across
  runs and machines. Rejected: `Decimal` arithmetic end to end (the
  exponential term forces float anyway). Satisfies invariant 4.

### The parameter table as proposed (defaults; every unsourced one is a guess to explore, never a fact)

| Name | Default | Unit | Sourcing | Citation or range |
|---|---|---|---|---|
| `arr_eur` | 800,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 (public disclosure: "€800M+ annual recurring revenue") |
| `members` | 1,000,000 | members | sourced | PROJECT_BRIEF.md §6 ("1M+ members") |
| `fraud_pool_eur` | 4,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 ("~€4M fraud savings (2024)"), presented as a lower bound |
| `refunded_eur` | 350,000,000 | € / year | sourced | PROJECT_BRIEF.md §6 ("€350M+ claims refunded per year") |
| `mu`, `sigma` | 3.809814, 2.187981 | log-euros | sourced | `data/damir/claim_cost_fit.csv` (`open-damir`, July 2025, legal reimbursement only) |
| `flag_rate` | 0.05 | share of claims | unsourced | 0.00–0.20 |
| `fp_share` | 0.50 | share of flagged | unsourced | 0.10–0.90 |
| `contacts` | 3 | contacts per stuck claim | unsourced | 1–8 |
| `cost_per_contact` | 8 | € | unsourced (flips to sourced if a public benchmark is handed over before build) | 2–30 |
| `churn_prob` | 0.05 | probability | unsourced | 0.00–0.30 |
| `k` | 8 | — (diminishing-returns constant) | unsourced | 2–20 |

The formulas, in order (brief §7, plus the three derived defaults and the
crossover): `customer_value = arr_eur / members`; `mean_claim = exp(mu +
sigma² / 2)`; `claims = refunded_eur / mean_claim`; `flagged = claims ×
flag_rate`; `false_pos = flagged × fp_share`; `fraud_saved = fraud_pool_eur ×
(1 − e^(−k × flag_rate))`; `friction_cost = false_pos × (contacts ×
cost_per_contact + churn_prob × customer_value)`; `net = fraud_saved −
friction_cost`; `crossover_flag_rate = the first grid flag rate with net < 0`.
Their values at the defaults are computed at build and pinned in
`tests/pins.py`; this spec names none, so no number is stated before its
formula runs. If the defaults put the crossover outside the grid or the marker
right of it, the chart is published as it comes out (SPEC.md → "hypothesis,
not verdict") — the defaults are not tuned to tell a story; a change to one is
a `PARAMETERS` cell with its range, recorded.

## Scope (files)

- `models/__init__.py`, `models/cost_model.py` — new package: `Parameter`,
  `Formula`, `PARAMETERS`, `FORMULAS`, `SCENARIOS`, `FLAG_RATE_GRID`,
  `evaluate`, `curves`, `format_model`; the teaching docstring. (The package
  is on `architecture-fit`'s paths; `models/guardrail_sim.py` is 8b.)
- `opendata/fit.py` — `read_fit(path) -> Fit`: the strict reader of the
  artifact its `write_fit` writes.
- `sql/marts/cost_model_params.sql`, `sql/marts/cost_model_outputs.sql`,
  `sql/marts/cost_curves.sql` — DDL only; headers name grain, provenance
  (`run_id`, `tag`) and the rows fed (B3.3+B3.4, B3.1, B3.2).
- `pipeline/build.py` — `write_model_marts`; the three names run in the
  generic marts loop unchanged (DDL only) and are filled by the model step.
- `pipeline/cli.py` — the model step after `_classify_and_print` in rebuild;
  the `model` subcommand (no variable).
- `Makefile` — `model` target, `.PHONY`, help line; the header comment's
  "model (8)" becomes what exists.
- `tests/test_cost_model.py`, `tests/test_model_marts.py` — new;
  `tests/test_damir.py` (`read_fit`), `tests/test_no_key.py` (the model step),
  `tests/pins.py` (the defaults' outputs, the crossover, the curve-row count).
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `BACKING.md`, `SPEC.md`
  (tag markers only), this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 8a entry: the 8a/8b split and its seam; the six
  pinned decisions with their rejected alternatives; the `cost_per_contact`
  sourcing outcome; Gotchas if any (DuckDB `double`/`null` binding, the
  `create or replace` + delete/insert order).
- [ ] `BACKLOG.md` — new row: a citable customer-contact cost benchmark
  (trigger: one found → `cost_per_contact` flips to sourced); the "data.ameli
  practitioner-fee distributions" row's trigger re-checked (8a does not need
  it; re-deferred to 8b/the study, trigger reworded); count updated.
- [ ] `CLAUDE.md` — Current status; Commands (`model`: offline, no variable,
  prints and writes nothing; the rebuild's model step); Repo map (`models/`
  loses "(Phase 8)", names `cost_model.py::FORMULAS` as landed and
  `guardrail_sim.py` as 8b; `sql/marts/` line counts the three new Python-fed
  marts); BACKLOG count.
- [ ] `BACKING.md` — B3.1, B3.2, B3.3, B3.4 Pending → Modeled (files exist);
  the note under the table on the `open-damir` upstream updated: B3.3 now
  displays the fit through `mean_claim`; B4.1–B4.3 stay Pending, named for 8b.
- [ ] `SPEC.md` — Beat 3 panels B3.1–B3.4: the "(Pending until the model mart
  lands)" / "(Pending)" markers removed, tag stays *Modeled* — the tag state
  moving as planned, not a chart change (the Beat 2 precedent after 7a). No
  panel added, none reworded beyond the marker.
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
  set as data, not `if` chains; no literal number in the writer; rounding at
  the writer only; the model step placement; scope (Beat 3 only — a hold
  duration or a synthetic claim in this diff is 8b's).
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
  fact; the sourced citations name the brief section, never a company page;
  "aggregated cell, not a claim" stays beside `mean_claim`; no banned word.
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
- **data.ameli practitioner-fee distributions** — BACKLOG (Phase 7b), trigger
  re-checked at this exit: 8a needs only the DAMIR amount fit.
- **A sensitivity table or a fitted anything** — the model is the arithmetic
  shown; no optimizer, no calibration of the unsourced defaults to data
  (brief §2.1, §10).
