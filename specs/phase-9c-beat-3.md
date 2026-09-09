# Phase 9c — Beat 3: the first Modeled panels, the formulas beside their numbers (APPROVED)

Contract for the `phase-9c-beat-3` branch. Source: PROJECT_BRIEF.md §9 Phase 9
("The study"), sub-phase 9c of the permanent-artifact-first split (DECISIONS →
Phase 9a); brief §7 (the cost model, Beat 3) and §3 Beat 3. Depends on Phase 9b
merged (PR #23, 2026-09-09) **and on the fix PR `fix/cost-outputs-unit`
merged** (`cost_model_outputs` carries each formula's display unit; pinned
decision 5).

**Status: APPROVED 2026-09-09 — in progress.** No new dependencies: Beat 3
renders through the 9a contract (`duckdb` + stdlib, hand-written inline SVG); no
script, no `<details>`, no new `make` target.
Challenged: 2026-09-09, round 1, spec 8bc38392 — approve with amendments (all applied)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

Beat 3 is where the study turns counted complaints into euros: what a wrongly
held claim costs, as arithmetic a reader can redo by hand. Phase 8a built the
model as data — `models/cost_model.py::FORMULAS`, each printed expression and
its callable one entry — and filled three marts with the expressions, the
values at the defaults, the two curves over the flag rate and every parameter
with its range and sourcing. `make model` prints all of it. Nothing renders it.

Beat 3 is the study's first **Modeled** surface, and it is different from Beats
1–2 in two ways the render contract has not yet met. First, its numbers derive
from no review and no anchor: the marts fill on every rebuild input, `none`
included, so the corpus gate does not apply and the committed page shows real
numbers for the first time beyond the anchors. Second, the thing the brief
promises the reader — "every formula printed above its chart" — is a text
column rendered beside a value, and the brief's rule that the two "mirror 1:1"
has so far been proven at the mart (8a's test) and at the terminal (`make
model`), not on the page. This phase closes that loop at the page: a test walks
the rendered formula rows and requires each expression to equal the `FORMULAS`
entry of the same name and each value to equal its mart cell, so a formula
edited in the module without a rebuild is caught by the page's own test.

The brief also promises sliders. The permanent artifact is a static page with
no script (9a, self-containment; 9b, "no script"), so a slider here is drawn,
not dragged: a range mark — low, default, high — with its unit and, for a
sourced parameter, its citation, styled apart from the "explore the range"
mark an unsourced parameter carries. Because the range is drawn and the
formula is printed beside it, a reader redoes the arithmetic at any point of
the range by hand — that is the exploration the permanent page offers. A
slider that recomputes is a script, and whether the published page carries
one is 9f's decision (a BACKLOG row this phase opens); recomputation in the
repo is `evaluate()` / `curves()` over a changed default, a developer's call,
not a page feature.

This is not a fix PR: it adds four panels, three chart kinds (the formula list,
the curve chart with its markers, the parameter list with its range marks), two
units, the allowlist columns the three marts need, the display texts moved to
their own module, and the module-to-page identity test.

## The central constraint

**Every Beat 3 number on the page is one cell of the three cost-model marts,
rendered under the Modeled tag, and every printed expression is the `FORMULAS`
entry of the same name — the renderer computes nothing, not a curve point, not
a marker, not a note's figure — while the 9a/9b contract (byte-identical on
rerun, the committed baseline, the one-tag, Pending, fixture and value-xor-
absence refusals, the column allowlist) and the three marts do not move.**
`sql/`, `pipeline/`, `models/`, `classify/`, the existing pins in
`tests/pins.py`, SPEC.md's beat structure and BACKING.md's row set and tags
stay as they are (the one mart change, the `unit` column on
`cost_model_outputs`, lands in its own fix PR before this branch starts).

## DONE command

```
make rebuild ROWS=synthetic && make study && git diff --exit-code -- study/ && uv run pytest tests/test_beat3.py tests/test_export.py tests/test_beat2.py -q
```

- `make rebuild ROWS=synthetic` builds the frozen input; `rebuild()` fills the
  three cost-model marts from the tracked fit after the marts loop (8a), so the
  synthetic DB carries 15 parameter rows, 56 output rows and 164 curve rows
  under `run_id = 'model'`. Reproduces the existing synthetic rebuild.
- `make study` renders Beats 1–3 into `study/friction_ledger.html`: the four
  Beat 3 panels carry numbers (the first Modeled numbers in the committed page).
  A contract breach exits non-zero with one line naming the panel.
- `git diff --exit-code -- study/` proves the render matches the committed
  baseline (byte identity on rerun is 9a's test, inherited).
- `uv run pytest tests/test_beat3.py tests/test_export.py tests/test_beat2.py
  -q` proves what the baseline bytes cannot show: every rendered value equals
  its mart cell (over the synthetic DB, whose Beat 3 marts are real numbers,
  and over a test-owned copy with one cell mutated — the page moves with the
  cell); every expression equals `FORMULAS`; the markers sit at the mart's
  crossover rows, stacked when they coincide; the absences, the fixed range
  mark, the refusals; the domain rule; no "source pending" footer; and the
  two inherited files whose panel walks and allowlist checks now cover three
  beats.

## Done-when

1. **Beat 3 renders into the baseline with numbers, on every input.** B3.1
   renders the baseline scenario's fourteen formula rows (twelve point, two
   curve), each expression beside its value and unit; B3.2 renders fraud saved
   and friction cost as two curves over the 41-point flag-rate grid with the
   "you are here" marker at the mart's `is_default` row and the two crossover
   markers at the mart's crossover rows (two markers at one flag rate — the
   baseline's own case — stack their labels, neither hidden); B3.3 renders the
   three derived headline figures BACKING assigns to it (revenue per member,
   the mean claim, the claim volume — baseline rows of `cost_model_outputs`)
   above the sourced parameter rows, and B3.4 the unsourced parameter rows,
   each parameter with its default in its display unit, its prose unit and
   its range mark; every panel and every point is Modeled; no Beat 3 footer
   prints "source pending"; a render over a `ROWS=none` DB shows the same
   Beat 3 numbers (no corpus gate on a Modeled panel). *Evidence: rows 1, 2,
   3.*
2. **Every Beat 3 number equals its mart cell and every expression equals
   `FORMULAS`; the renderer computes nothing.** The value beside each formula,
   each curve point, each parameter's default/low/high and every figure a note
   carries (the crossover the note names) is read from a mart row; the
   expression text on the page equals `Formula.expression` for that name; a
   mutated mart cell moves the page and nothing else does. *Evidence: rows 4,
   5, 6.*
3. **A missing crossover is a declared absence; a single-point range is a
   labelled fixed mark; a bad mart row refuses by name.** A scenario whose
   crossover is null (the mart stores NULL) renders "never crosses on this
   grid" in the formula row and no marker on the chart, with the note saying
   so; a parameter whose `low == default == high` renders "fixed — read from
   the fit", never a zero-width mark; each of a `sourcing` outside the two
   words, a scenario outside `SCENARIOS`, a formula or parameter name outside
   the closed display map, and a null `expression`/`default_value` refuses in
   one line naming the panel, each pinned by its own test. *Evidence: rows 7,
   8, 9.*
4. **Sourced and unsourced parameters are told apart by the mart's `sourcing`
   column, and the split is that column.** B3.3's parameter rows are exactly
   the rows whose `sourcing = 'sourced'` and B3.4's exactly the `'unsourced'`
   rows (never an id list); a sourced row renders its citation text and no
   "explore" label; an
   unsourced row renders "declared unsourced — explore the range" and no
   citation; the two are styled by a closed class lookup keyed on the two
   words. *Evidence: rows 10, 11.*
5. **The no-text guarantee and the no-script guarantee extend over Beat 3.**
   Every Beat 3 query is in `STUDY_QUERIES`, projects only allowlisted columns
   (the allowlist gains the model marts' column names, none a review-text
   column), and passes the SQL lint; the recording connection lists every query
   a three-beat render runs; the page carries no `<script` element at all
   (9a's self-containment test already asserts it, inherited over three
   beats); two renders are byte-identical. *Evidence: rows 12, 13.*

(5 items, ≤ 6.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat3.py::test_b3_1_renders_the_baseline_formula_rows_each_expression_beside_its_value` (fourteen rows, `expression` then value with unit; the scenario is `baseline`; a curve row's value is a flag rate) |
| 1 | `tests/test_beat3.py::test_b3_2_draws_two_curves_and_three_markers_from_the_marts` (41 points per curve; the marker `x` equals `_x_of(flag_rate)` of the `is_default` row and of the two crossover rows; the legend names both curves) and `::test_coincident_markers_stack_their_labels_at_one_x` (the baseline: the default and the marginal crossover both at 0.05 — two labels at one `x`, at the two index offsets, the note naming both figures) |
| 1 | `tests/test_beat3.py::test_b3_3_shows_the_derived_headline_figures_from_the_outputs_mart` (`customer_value`, `mean_claim`, `claims` at baseline, above the parameter rows), `::test_b3_3_and_b3_4_render_every_parameter_with_default_unit_and_range`, `::test_parameter_defaults_render_in_their_display_unit` (ARR as euros, `mu` to six places, a share as a percentage — the `Unit` from the display map, the prose unit beside it), `::test_no_beat3_panel_prints_source_pending` and `::test_beat3_renders_numbers_over_a_none_input` (a `ROWS=none` DB: Beat 2 says "no data yet", Beat 3 shows its numbers); `make study && git diff --exit-code -- study/` exits zero |
| 2 | `tests/test_beat3.py::test_every_beat3_value_equals_its_mart_cell` (the synthetic DB: every rendered value, curve point, default/low/high and the note's crossover figure found in the mart; figures pinned in `tests/pins.py` as `COST_OUTPUTS`, `COST_CROSSOVERS` already are) |
| 2 | `tests/test_beat3.py::test_a_mutated_mart_cell_moves_the_page_and_the_expression_stays` (a test-owned copy with one `value` and one `net` changed: the page shows the new cell; the expression text is unchanged) |
| 2 | `tests/test_beat3.py::test_every_rendered_expression_equals_the_formulas_entry_of_that_name` (walks the rendered B3.1 rows against `models.cost_model.FORMULAS` by name — the module ↔ mart ↔ page identity; and the reverse: every `FORMULAS` name is rendered) and `::test_rows_render_in_formulas_and_parameters_order` (the page's row order is the imported tuples' order, so it matches `make model` line for line) |
| 2 | `tests/test_beat3.py::test_the_curve_domain_rule_is_pinned_over_two_inputs` (the synthetic marts: upper bound 5,000,000 from a 4,530,293.45 maximum; a mutated copy whose maximum crosses a rounding boundary; ticks formatted as euros, never `1.25e+06`) |
| 3 | `tests/test_beat3.py::test_a_null_crossover_renders_a_declared_absence_and_no_marker` (a panel built over the `both` scenario rows: the formula row carries `absent`, the chart has no crossover marker, the note says it never crosses on the grid) |
| 3 | `tests/test_beat3.py::test_a_single_point_range_renders_a_labelled_fixed_mark` (`emp_p50`: no zero-width mark, the label present) |
| 3 | `tests/test_beat3.py::test_a_sourcing_outside_the_two_words_refuses_by_name`, `::test_a_scenario_outside_scenarios_refuses_by_name`, `::test_a_name_outside_the_display_map_refuses_by_name`, `::test_a_null_expression_or_default_refuses_by_name` (one refusal per test, each one line naming the panel) |
| 4 | `tests/test_beat3.py::test_the_sourced_unsourced_split_is_the_marts_sourcing_column` (a copy with one row's `sourcing` flipped moves the row between B3.3 and B3.4) |
| 4 | `tests/test_beat3.py::test_a_sourced_row_shows_its_citation_and_an_unsourced_row_the_explore_label_never_both` |
| 5 | `tests/test_beat2.py::test_every_export_query_projects_only_allowlisted_columns`, `::test_every_query_the_export_runs_is_a_listed_study_query` and `::test_every_study_query_passes_the_sql_lint` (inherited; they walk `STUDY_QUERIES` and a three-beat render); `tests/test_beat3.py::test_the_allowlist_gains_no_review_text_column` (`title`/`body` still absent; the added names are the three marts' columns) |
| 5 | `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp` (inherited; it already asserts no `<script` in the page) and `::test_make_study_is_byte_identical_on_rerun` (inherited) |

The 9a and 9b tests are inherited unchanged except the panel-walk counts
(nine panels → thirteen) and the corpus-gate `none` test, which gains the
Beat 3 assertion. `tests/test_cost_model.py` is unchanged here: the fix PR
extends it for `Formula.unit` and the mart's `unit` column before this branch.

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all Beat 3 numbers on the page (a formula's value, a curve point, a marker's position, a parameter's default/low/high, a figure inside a note), the number is one cell of `cost_model_outputs`, `cost_curves` or `cost_model_params`; the renderer computes none. | `tests/test_beat3.py::test_every_beat3_value_equals_its_mart_cell`; `::test_a_mutated_mart_cell_moves_the_page_and_the_expression_stays`; `::test_b3_2_draws_two_curves_and_three_markers_from_the_marts` (the marker at the mart's crossover row, not at the first curve point whose net is negative — a mutated crossover row moves the marker while the curves stay). |
| For all rendered formula rows, the expression text equals the `FORMULAS` entry of the same name, and every `FORMULAS` name is rendered (the brief's 1:1 mirror, proven at the page). | `tests/test_beat3.py::test_every_rendered_expression_equals_the_formulas_entry_of_that_name`. |
| For all Modeled panels, a number renders on every rebuild input, `none` included; no corpus gate reads them. | `tests/test_beat3.py::test_beat3_renders_numbers_over_a_none_input` (over a `ROWS=none` DB the Beat 2 corpus panels say "no data yet" and every Beat 3 panel shows its numbers). |
| For all parameter rows, exactly one of a citation and the unsourced label renders, decided by the mart's `sourcing` column, which is one of two words; a third word refuses by name; the B3.3/B3.4 parameter-row membership is that column. | `tests/test_beat3.py::test_the_sourced_unsourced_split_is_the_marts_sourcing_column`; `::test_a_sourced_row_shows_its_citation_and_an_unsourced_row_the_explore_label_never_both`; `::test_a_sourcing_outside_the_two_words_refuses_by_name`. |
| For all curve panels, a marker is drawn only at a grid flag rate the mart holds; two markers at one flag rate both render, their labels stacked by a fixed offset; a null crossover draws no marker and renders a declared absence in its formula row and a sentence in the note; a null `value`/`expression`/`default_value` outside that case refuses. | `tests/test_beat3.py::test_a_null_crossover_renders_a_declared_absence_and_no_marker`; `::test_coincident_markers_stack_their_labels_at_one_x`; `::test_a_null_expression_or_default_refuses_by_name`; 9a's `test_a_null_mart_cell_is_refused_by_name_not_a_traceback` over a Beat 3 reader. |
| For all parameter rows whose range is a single point, the range renders a labelled fixed mark, never a zero-width or divided-by-zero geometry. | `tests/test_beat3.py::test_a_single_point_range_renders_a_labelled_fixed_mark`. |
| For all renders, every query the export runs is listed, projects only allowlisted columns (no review-text column), passes the SQL lint; the page carries no script element; two renders are byte-identical (9a/9b, extended). | `tests/test_beat2.py::test_every_export_query_projects_only_allowlisted_columns`; `::test_every_query_the_export_runs_is_a_listed_study_query`; `::test_every_study_query_passes_the_sql_lint`; `tests/test_beat3.py::test_the_allowlist_gains_no_review_text_column`; `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp`; `::test_make_study_is_byte_identical_on_rerun`. |
| For all curve panels, the axis domain is a layout number computed from the mart cells by one fixed rule (lower bound 0; upper bound the two curves' maximum rounded up to one significant figure) and its ticks are formatted as euros; the same cells give the same domain, and no displayed figure is derived from it. | `tests/test_beat3.py::test_the_curve_domain_rule_is_pinned_over_two_inputs`. |
| For all Beat 3 panels, the footer names a repository file or an address, never "source pending". | `tests/test_beat3.py::test_no_beat3_panel_prints_source_pending`. |
| For all Beat 3 panels, every rendered number carries exactly one tag, read from its mart row (`tag` column), and it is Modeled (9a's contract, extended to the three kinds). | `tests/test_beat3.py::test_beat3_points_carry_the_mart_rows_tag_not_a_literal` (a copy with one row's `tag` changed to `Measured` renders a mixed panel naming both chips); 9a's `test_a_panel_with_no_tag_or_two_tags_is_refused` over a curve panel. |

## Pinned decisions (do not re-litigate)

- **A slider is a static range mark; the page carries no script.** Each
  parameter row draws low — default — high as inline SVG from the mart's three
  cells, with the unit beside the default; the sourced mark carries the
  citation text, the unsourced mark the "declared unsourced — explore the
  range" label, the two styled by a closed class lookup on `sourcing`. A slider
  that recomputes is a script, so it is not in the permanent artifact of this
  phase: the drawn range and the printed formula let a reader redo the
  arithmetic at any point of the range by hand, and whether the published page
  carries an inline script (self-contained, no CDN) is 9f's decision — a BACKLOG
  row with that trigger. The brief's word "slider" is met by the drawn range
  plus that trigger, recorded in DECISIONS; BACKING B3.4's claim cell and
  SPEC.md's two "slider" phrases are amended in this phase's records to what
  ships, not read as it. *Rejected: an inline `<script>` recomputing the
  formulas in the browser (a second copy of `FORMULAS`, in a second language,
  that no test pins against the module); `<input type="range">` with no script
  (a control that does nothing reads as broken).* Satisfies invariants 1, 4, 7.
- **B3.1 renders the baseline scenario; the reader takes the scenario from the
  closed `SCENARIOS` set, and the three toggled scenarios are Beat 4's (9d).**
  The formula reader is `_formula_rows(conn, scenario)` with `scenario` checked
  against `models.cost_model.SCENARIOS` (imported) and refused by name outside
  it; B3.1 calls it with `baseline`; B3.2 reads the `baseline` curve rows the
  same way; B3.3 reads its three derived headline figures (`customer_value`,
  `mean_claim`, `claims` — the rows BACKING assigns to B3.3) through the same
  reader at `baseline`, above its parameter rows. 9d's B4.1 ("the curves
  move") reuses both readers with `contacts_once`, so the toggles need no
  second reader. *Rejected: four
  formula lists in Beat 3 (Beat 4's story told early; SPEC.md gives the toggles
  to B4.1); a scenario filter written as a literal in SQL (caller-sourced).*
  Satisfies invariants 2, 3.
- **Three new chart kinds, each a closed addition to `Kind` and
  `_render_body`: `formulas`, `curve`, `parameters`; `Unit` gains `eur` and
  `logeur`.** A `formulas` panel is one `Series` per formula (the display
  name), one `Point` whose `label` is the expression text, `value` the mart's
  value, `unit` the mart's unit, `absent` set when the mart stores NULL; it
  renders as a list of name / expression / value rows. A `curve` panel is one
  or more `Series` over one numeric x axis (the flag rate, `pct`) — two here
  (fraud saved slot 0, friction cost slot 1: the first slots in series order,
  the palette's order being the CVD mechanism, never a semantic colour), and
  9d's B4.1 adds the toggled scenario's pair on the same grid without widening
  the kind — each `Point.label` the grid flag rate, plus `markers`, a tuple of
  `(label, flag_rate)` read from the marts (the `is_default` row; the two
  crossover rows) drawn as labelled vertical rules in tuple order, each label
  at a fixed vertical offset by its index (a layout constant like `_MT`), so
  two markers at one flag rate — the baseline's own case, the default and the
  marginal crossover both at 0.05 — read as stacked labels on one line, neither
  hidden. The y domain is a layout number by one fixed rule: lower bound 0,
  upper bound the two curves' maximum cell rounded up to one significant
  figure (4,530,293.45 → 5,000,000), ticks formatted as euros through
  `_display`, never `{value:g}`'s `1.25e+06`; the rule is one pure function a
  test pins over two inputs, and no displayed figure derives from it. A
  `parameters` panel is one `Series` per parameter (the display name), three
  `Point`s (low, default, high; the default carrying the display `Unit` the
  closed map gives it — ARR as euros, `mu` as log-euros to six places, a share
  as a percentage — with the mart's prose unit and, in `detail`, the citation
  or the unsourced label), rendered as the range mark. Palette inherited (the
  dataviz "Ledger" default, 9a); markers in the ink and muted chrome tokens,
  never a series slot. *Rejected: reusing `table` for the formulas (its cells
  are metric cells with counts, and the expression is text); reusing `line`
  for the curve (no markers, no numeric ticks — a uniform grid would place,
  but the marker refusal needs a kind to key on); one generic kind with a mode
  flag; a fixed euro domain (clips the friction curve the moment a default
  moves).* Satisfies invariants 1, 5, 6, 8, 9.
- **The markers and the note's figure are read from `cost_model_outputs`, never
  found by scanning the curve.** The "you are here" rule is the `is_default`
  row's flag rate; the two crossover rules are the `crossover_flag_rate` and
  `marginal_crossover_flag_rate` rows' values; the note that names the
  crossovers ("at these defaults the curves cross at …; the next flag stops
  paying at …, where the default sits") is a template filled from those rows
  and the `is_default` row, naming both figures, and when a row is NULL the
  note says the curves never cross on the grid and no rule is drawn. The reader chooses nothing: a scan of `net < 0`
  inside the renderer would be a second copy of a `FORMULAS` rule. *Rejected:
  computing the crossing from the two polylines; typing the crossover into the
  note (a literal the mart cannot move — the hypothesis-not-verdict rule).*
  Satisfies invariants 1, 5.
- **`cost_model_outputs` carries each formula's unit, and the unit is a field
  of the `Formula` entry — landed in the fix PR `fix/cost-outputs-unit` before
  this branch.** Today the unit lives in a private map parallel to `FORMULAS`
  (`_OUTPUT_UNIT`, covering the twelve point formulas only, named in no test);
  the mart stores `value` with no unit, so the page could print "1318719.82"
  but not "€ 1,318,719.82". "Formulas are data" says the unit is part of the
  entry: the fix PR adds `unit` to the `Formula` dataclass (the curve formulas
  carry `rate`), `_run_points` and the writer read `f.unit`, the mart's DDL
  gains `unit varchar`, the header's reader rule is corrected to "B3.1 prints
  the baseline scenario's fourteen rows, point and curve; B4.1 the toggled
  scenarios'", and `tests/test_cost_model.py` pins the field and the column.
  It is a mart-shape change in an 8a file, so it is its own PR (CLAUDE.md →
  Git workflow; the 9b `run_id` precedent). The mart column, not only the
  module field, is what Metabase (9g) and `make model` read, so the page, the
  terminal and the dashboard show one unit. The export maps the mart's rounding
  unit to a display unit by a closed lookup (`eur` → `eur`, `rate` → `pct`,
  `count` → `count`, `days` → `days`), refusing a unit outside it.
  *Rejected: a second public dict parallel to `FORMULAS` (the parallel-map
  shape — the `name-drift` class); a unit map keyed on formula names in the
  study (a second copy); free-text units on the outputs mart as the params
  mart has (the params' unit is prose for a person; the outputs' unit selects
  a number format).* Satisfies invariant 1.
- **Display texts live in `study/text.py` (`text.py` ← `panels.py`): the
  closed display-name maps, one entry per formula and per parameter name,
  refusing an unknown name; rows render in `FORMULAS` / `PARAMETERS` order;
  the mart's own name stays visible beside each.** "Name things by what they
  mean": `customer_value` renders as revenue per member per year, `false_pos`
  as wrongly held claims, `timer_amount_eur` as the hold-timer threshold
  amount, with the mart's identifier in the row and the rows ordered in Python
  by the imported tuple's index (the SQL `order by name` stays the tie-free
  read key), so a reader matches `make model` line for line. The parameter
  map's entry is `(display name, Unit)`, so the display unit is one closed
  choice per parameter beside its name, not a second map. A name the map does
  not know refuses by name (the `_PROFILE_NAMES` precedent), so a fifteenth
  formula or a sixteenth parameter added to the model without a study name
  fails the render, never renders an identifier as prose. `text.py` also holds
  the marker labels, the note templates and the absence labels — the 9b exit
  record's "9c splits the note texts and display tables into `study/text.py`
  if it grows further", and it grows here; the existing Beat 1–2 note texts
  move there verbatim in their own commit (the 9b precedent). The words are
  the study-editor's; the mechanism is the closed map. *Rejected: rendering
  the identifier alone; a soft `.get(name, name)` fallback (the `empty-default`
  class); alphabetical rows (`make model` prints tuple order).* Satisfies
  invariant 1 (a wrong name cannot pair with a wrong number) and the
  neutrality/plain-English rules.

(6 pinned decisions, ≤ 6.)

## Scope (files)

- `study/model.py` — `Kind` gains `formulas`, `curve`, `parameters`; `Unit`
  gains `eur` and `logeur`; `Panel` gains `markers: tuple[tuple[str, float],
  ...]`; `check_panel` refuses a marker on a non-curve panel and a marker whose
  flag rate no point of the panel carries (invariant 5).
- `study/text.py` — new (the `architecture-fit` skill loaded by name before
  the module is created): the display-name maps (`(display name, Unit)` per
  parameter; a display name per formula), the marker labels, the note
  templates, the absence labels, the Beat 1–2 note texts moved verbatim in
  their own commit; imports nothing from `panels` or `export`.
- `study/panels.py` — `beat3_panels`, the three readers (`_formula_rows`,
  `_curve_series`, `_parameter_rows`), the unit lookup, the sourcing class
  lookup, the domain rule (one pure function), each panel's `sources` (B3.1–
  B3.3: the fit file `data/damir/claim_cost_fit.csv` as a repository file plus
  the DAMIR address from `opendata/sources.py`; B3.4: `models/cost_model.py`,
  the file that declares the guesses — the params mart's citation string is
  rendered as text and never passed as a source, since "… ← open-damir" is not
  the repository-file shape), the three queries added to `STUDY_QUERIES`, the
  allowlist columns (`scenario`, `name`, `expression`, `unit`, `default_value`,
  `sourcing`, `citation`, `low`, `high`, `flag_rate`, `fraud_saved`,
  `friction_cost`, `net`, `is_default`).
- `study/export.py` — `_render_formulas`, `_render_curve` (numeric x axis,
  euro ticks, markers with the index offset), `_render_parameters` (the range
  mark), the `eur` and `logeur` displays, the Beat 3 header in `_BEATS`, CSS
  for the three kinds and the two sourcing classes. The `_drill` fallback
  ("source pending") is untouched — removing it is a 9a-semantics change, a
  BACKLOG candidate at exit if the auditor asks.
- `study/friction_ledger.html` — the committed baseline, re-rendered with
  Beat 3.
- `tests/test_beat3.py` — new: the Evidence rows above, including the
  test-owned mutated copies of the synthetic DB and the `both`-scenario panel.
- `tests/test_export.py` — the panel-walk tests cover thirteen panels.
- `tests/test_beat2.py` — the `none`-input test stays; the Beat 3 assertion is
  `tests/test_beat3.py::test_beat3_renders_numbers_over_a_none_input` (named
  here: it moved).
- `tests/pins.py` — the rendered Beat 3 fragments per kind; the unit lookup;
  the domain rule's two pinned outputs; the display-name counts (14 formulas,
  15 parameters). `COST_OUTPUTS` and `COST_CROSSOVERS` are reused, not retyped.
- `SPEC.md` — Beat 3: the two "slider" phrases (the intro's "every assumption
  is a slider" and B3.4's "explore the range sliders") become the drawn range
  — one sentence under the intro naming the static range mark (drawn, not
  dragged, in the permanent page: a reader redoes the arithmetic at any point
  of the range by hand); one under B3.1 naming the baseline scenario and that
  the toggles are B4.1's; one under B3.2 naming the "never crosses on this
  grid" state and the stacked markers; one under B3.3 naming the three
  headline figures above the parameter rows; the brief's B2B sentence (one
  employee stuck in a document loop complains to HR, and HR decides renewals)
  placed beside B3.2. No row id, tag or chart-meaning change.
- `BACKING.md` — B3.4's claim cell: "Declared-unsourced parameters as
  explore-the-range sliders" → "Declared-unsourced parameters with their
  explore-the-range span drawn, styled apart"; table, SQL, source and tag
  unchanged, so `make check-backing` is unaffected.
- `specs/phase-9b-beat-2.md` — one word in the Delivered paragraph's handoff:
  the Modeled marts carry `run_id = 'model'` on the baseline (the DB holds
  `'model'`: `rebuild()` passes no `run_id`, so `run_id or "model"`), not
  `'synthetic'`; nothing on the corpus-gate exclusion reads Beat 3's `run_id`.
- `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, this spec — per Record updates.
  (No `README.md`: Phase 9f's deliverable.)

Freeze: none

## Record updates (REQUIRED)

- [x] `DECISIONS.md` — Phase 9c entry: the static range mark and the no-script
  page (the brief's "slider" met by the drawn range plus the BACKLOG trigger;
  a reader redoes the arithmetic by hand); B3.1 at baseline, the toggles Beat
  4's; B3.3's headline figures; the three kinds, the marker offset and the
  domain rule; the markers read from the outputs mart; `Formula.unit` and the
  mart column's fix PR; `study/text.py` and the display-name maps; the
  challenge dispositions (round 1, approve with amendments, all applied);
  supersede nothing.
- [x] `BACKLOG.md` — open *Live sliders need a script the permanent page does
  not carry* (trigger: 9f decides whether the published page may carry an
  inline, CDN-free script that recomputes `FORMULAS`; if yes, the pinning test
  is the module ↔ script identity; if no, the Metabase demonstration 9g is the
  exploration); keep *The claim-cost mean is the lognormal mean, not the
  fixture's arithmetic mean* (the sample-mean slider), *`cost_per_contact` is a
  declared guess* and *The four scale anchors cite `PROJECT_BRIEF.md §6`,
  second-hand* open, each stated beside the parameter it concerns; update the
  count.
- [x] LESSONS.md — none until a review round reports a correctness finding;
  then backtick it and the fix commit writes the row.
- [x] `CLAUDE.md` — Current status; Repo map (`study/text.py`, Beat 3
  rendered, the three kinds, 9d next); BACKLOG count; Commands unchanged.
- [x] `BACKING.md` — B3.4's claim cell reworded to the drawn range (no tag,
  table, SQL or source change).
- [x] `SPEC.md` — the Beat 3 sentences under Scope (no row id, tag or chart
  meaning changes).
- [x] `specs/phase-9b-beat-2.md` — the one-word `run_id` correction under
  Scope (a records fix, batched with this phase's records commit).
- [x] README — none (the repo has no README yet; Phase 9f).
- [ ] `specs/phase-9c-beat-3.md` — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make study` is unchanged: no variable, reads the synthetic DB and
tracked data, writes one file. Run twice: identical bytes. No credentials:
identical bytes. The export's reads are the repo's own marts through the
column allowlist and 9a's `_require` boundary; the only `href` it renders is a
platform root, `http(s)`-only (9a); a citation cell is rendered as escaped
text, never as a link (the fit citation names a repository file and the
anchors' citation is prose).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `study` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` (unchanged) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `tests/`): no arithmetic in the
  renderer (a marker from the outputs mart, never `net < 0` scanned; a domain
  rule that is layout only, one pure function); the scenario checked against
  the imported `SCENARIOS`; the sourcing split read off the column, never an
  id list; the display-name and unit lookups closed and refusing; rows in
  tuple order; the three kinds as closed additions with their refusals in
  `check_panel`; the allowlist gaining no text column; the direction `text.py`
  ← `panels.py` ← `export.py` with the moves verbatim in their own commit;
  scope (Beat 4's toggles, live sliders, the README, Metabase are out).
- **security-reviewer** (not triggered — `study/` is not on the Sensitive row;
  the citation and expression cells are escaped text from the repo's own marts,
  and the no-script test is read by code-reviewer and functionality-tester).
- **functionality-tester** (triggered): the DONE command; the fourteen formula
  rows in the baseline with their expressions verbatim from `FORMULAS`; the
  three markers at the pinned crossovers (0.05, 0.095, 0.05 — the first and
  the last at one `x`, both labels present); the headline figures above
  B3.3's rows; the mutated-copy tests (a cell moves the page; a flipped
  `sourcing` moves a row; a `tag` changed renders both chips; a maximum
  across a rounding boundary moves the domain); the `both`-scenario absence;
  the `emp_p50` fixed mark; the four refusals; no "source pending" on a Beat
  3 footer; a render over `ROWS=none` shows Beat 3 numbers; two renders
  identical; the page has no `<script`.
- **study-editor** (triggered — SPEC.md and BACKING.md sentences, the rendered
  Beat 3 prose): the display names by meaning; the range mark described as
  drawn, not dragged, with no hedge; the note's crossover sentence as a
  reading of the chart, not a verdict ("the default sits one grid step past
  the peak" for the coincident markers); "declared unsourced — explore the range" and "never crosses on this
  grid" plain; the B2B channel sentence in the reader's words; the DAMIR bias
  sentence (`mean_claim`'s expression text) legible on the page; banned words
  absent; no insurer named as the target.
- **coherence-auditor** at exit (mandatory): SPEC ↔ BACKING ↔ the three marts ↔
  the rendered Beat 3 agree (the fourteen names, the fifteen parameters, the
  sourcing of each); the new BACKLOG row open and the three parameter rows
  still open; CLAUDE.md's status names 9d next; the 9b Delivered paragraph's
  "9c — Beat 3 (the first Modeled panels, `FORMULAS` `expression_text`)" met by
  name, and its `run_id` sentence corrected; 9d finds the two readers it
  reuses and a `curve` kind that takes its second pair of series.
- Stack risk: DuckDB's `cursor.description` for the `boolean` `is_default` and
  the NULL `double` crossover through the recording connection (8a confirmed
  the NULL binding on write; verify the read in the first hour); the
  `_display` of seven-digit euros byte-stable under the two-locale test; the
  SVG polyline over 41 points at fixed precision. Any surprise goes to
  DECISIONS → Gotchas; STOP before a workaround.

## Out of scope (deferred, recorded)

- The Beat 4 toggles over the same marts (`contacts_once`, `churn_halved`,
  `both`; B4.1 "the curves move"; B4.2 the hold timer from `sla_threshold`;
  B4.3 from `guardrail_sim`) — 9d, reusing this phase's readers.
- A slider that recomputes — the BACKLOG row this phase opens; 9f decides, 9g
  demonstrates.
- The claims sample-mean slider (a new fit artifact row) and data.ameli
  practitioner fees — the two pulled-out data phases (DECISIONS → Phase 9a;
  BACKLOG rows).
- `cost_per_contact` sourced, and the four scale anchors' disclosure addresses
  — the open BACKLOG rows; the page states each beside its parameter.
- Beat 5, the README + stranger test, Metabase — 9e–9g, each its own spec.
- Removing `_drill`'s "source pending" fallback (a 9a semantics change) — a
  BACKLOG candidate if the exit audit asks; this phase makes it unreachable
  on Beat 3 by naming every source.
- The fix PR `fix/cost-outputs-unit` (`Formula.unit`, the mart column, the
  header sentence, the pins): written by this session on a `fix/` branch from
  `main` after this spec is approved and before `phase-9c-beat-3` builds; the
  gate plus code-reviewer and functionality-tester, no spec; the developer
  merges, then this branch rebases onto `main`.

## Challenge dispositions (round 1, 2026-09-09 — approve with amendments, all applied)

Should-fix #1 (B3.3's headline figures) — **amend**: Done-when 1 and 4,
invariant 4 restated to the parameter rows, pinned decision 2. #2 ("the
exploration is `make model`") — **amend**: Why ¶3 and pinned decision 1 say
what is true. #3 (BACKING B3.4 and SPEC.md's "slider" amended, not read as) —
**amend**: Scope and Record updates; DECISIONS states the brief's word is met
by the drawn range plus the BACKLOG trigger. #4 (the parameters' display
unit) — **amend**: the map carries `(display name, Unit)`, `Unit` gains
`logeur`; pinned decisions 3 and 6. #5 (coincident markers) — **amend**: the
index offset rule and the note naming both figures; pinned decisions 3 and 4;
invariant 5. #6 (the domain rule) — **amend**: stated in pinned decision 3,
invariant 9, one pinning test. #7 (the mart header's reader rule) — **amend**:
in the fix PR's scope, pinned decision 5. #8 (`sources` per panel) —
**amend**: Scope names each; invariant 10. #9 (`study/text.py`) — **amend**:
Scope and pinned decision 6. Suggestions #10 (`Formula.unit`), #11 (`curve`
takes one or more series), #12 (tuple order), #13 (the duplicate no-script
test dropped; 9a's test cited), #14 (four refusal tests), #15 (invariant 3's
private-tuple falsifier dropped), #16 (the DONE command runs the three
changed test files) — **amend**, each folded where named. Questions #17 (the
9b Delivered sentence) — answered: corrected in this phase's records commit,
one word; nothing on the corpus-gate exclusion reads Beat 3's `run_id`. #18
(the fix PR) — answered under Out of scope: this session writes it after
approval, before the build, with findings #7 and #10 in its scope and the
pins in `tests/test_cost_model.py`.
