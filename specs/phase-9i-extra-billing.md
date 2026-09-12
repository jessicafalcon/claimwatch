# Phase 9i — the extra-billing share

Contract for the `phase-9i-extra-billing` branch. Source: post-plan extension —
BACKLOG row *data.ameli practitioner-fee distributions are not ingested*
(opened at Phase 7b, re-deferred at the 8a and 8b exits to the study), the
second of the two data phases pulled out of Phase 9's render (DECISIONS →
Phase 9a); PROJECT_BRIEF.md §7 names data.ameli beside Open DAMIR. Depends on
Phase 9h merged (PR #32) and `fix/foreign-shape-shared-home` (PR #33,
2026-09-12).

**Status: APPROVED 2026-09-12 — in progress.** No new dependencies: the
reader is stdlib `csv`, the arithmetic is two sums and a division, the rest is
the existing formulas-as-data path (`models/cost_model.py`,
`pipeline/build.py::write_model_marts`, `study/panels.py`).

Challenged: 2026-09-12, round 1, spec 5e0d85ff — approve with amendments (all nine applied)

## Why

Beat 3 anchors the size of a claim to Open DAMIR: the amount the Assurance
Maladie reimbursed, per aggregated cell. The insurers this study reads about
are complementary insurers, and what they refund is the rest of the bill: the
share of the public tariff the Assurance Maladie leaves to the patient, and
whatever the practitioner billed above that tariff — *extra billing*
(dépassement d'honoraires). That second part is absent from the DAMIR
reimbursement by construction: the public insurer reimburses none of it. The
page today says nothing about it, so a reader has no way to tell in which
direction the DAMIR anchor misses a complementary insurer's claim.

The BACKLOG row asked for "a practitioner-fee distribution … fitted the same
closed-form way". The dataset was read on 2026-09-12 before this spec was
written (the Phase 7b rule: confirm the source before anything is built), and
it does not hold that. data.ameli's `honoraires` dataset (Caisse nationale de
l'Assurance Maladie, Open Database License, last modified 2025-12-15, 66,480
rows) has one row per year (2010–2024) × profession × territory, and each row
carries that year's **total fees at the tariff** (`hono_sans_depassement_totaux`)
and **total extra billing** (`depassements_totaux`) in whole euros, the
per-practitioner means of both, and the sector-2 extra-billing rates. It is
annual per-practitioner totals, not per-act or per-claim amounts: there is no
claim-cost distribution here to fit a lognormal to, and the brief's §7 clause
"data.ameli for practitioner-level fees" cannot feed the simulator's draw.
What the dataset uniquely supplies — and the DAMIR reimbursement cannot — is
the **extra-billing share**: of everything liberal practitioners billed in a
year, the part above the tariff, `extra / (tariff + extra)`. So the row's
trigger is reinterpreted, as 9h's was: the phase lands that share as one
sourced row of B3.3, with its spread across the four profession families the
dataset publishes, and a note that says what it means for the mean claim.

The figures in this paragraph are the spec's, read off the portal, not the
page's — the page shows only mart cells typed from the built output. For 2024
at the national level the four top-level families (`Ensemble des médecins`,
`Ensemble des chirurgiens-dentistes`, `Sages-femmes`, `Ensemble des auxiliaires
médicaux`) sum to about €51.5 bn at the tariff and €10.7 bn above it — a share
near 17 % — ranging from about 1 % (auxiliaires médicaux) to about 49 %
(chirurgiens-dentistes). The 38 national profession rows nest (the four
families contain the rest: généralistes and spécialistes under médecins, five
professions under auxiliaires), so a sum over all 38 double-counts; the closed
four-label set is the whole.

One more fact read before writing: `https://data.ameli.fr/robots.txt` says
`User-agent: *` / `Disallow: /api/`, `/explore/download`,
`/explore/dataset/*/download`. The export lives under those paths. This repo
honours a host's robots file over its own convenience (Phase 2 declared the
App Store feed and did not fetch it; Phase 3a hand-read the listing whose terms
forbid robots; Phase 3c imported an authorized offline export), so **there is
no fetch target in this phase**: the developer downloads the dataset's CSV
export in a browser — a person, not a robot — and places it under the
gitignored cache; every command in the phase is offline. (Full disclosure for
the record: the spec's research made six small metadata requests to the API
with an identifying User-Agent before the robots file was read. None of that
output is used as data; the fixture comes from the developer's own download.)

This is a phase, not a fix PR: it declares a second open-data source, adds a
frozen fixture and a tracked artifact with its own reader, a parameter to the
model and a row to the page — a data structure, a write path and who-writes-what.

*Teaching note (lands in code and README at build).* In France a practitioner's
fee has a public tariff; the Assurance Maladie reimburses a set share of the
tariff and never the part billed above it. That part, the extra billing, and the
unreimbursed share of the tariff are what a complementary insurer covers. So a
distribution of what the Assurance Maladie reimbursed (DAMIR) describes the
public side of the same bill, and the extra-billing share is the one public
number that says how large the part it never sees is.

## The central constraint

**Every modeled number the page shows today keeps its value; the phase adds
one sourced row and its note beside the mean claim, and no formula reads it.**
`fixtures/damir/`, `data/damir/claim_cost_fit.csv`, every `FORMULAS` entry and
every pinned output stay as they are on every scenario; the DAMIR anchor is not
re-based; `len(FORMULAS)` stays 15 (B5.1 does not move). The new artifact is
recomputed from the new frozen fixture by an offline command and is byte-equal
to the committed file; no command in the phase touches the network.

## DONE command

```
make review-gate SPEC=specs/phase-9i-extra-billing.md && make split-ameli && make rebuild ROWS=synthetic && make study && git diff --exit-code -- data/ameli/fee_split.csv study/friction_ledger.html
```

- `make review-gate SPEC=…` — the suite (every pin below), ruff read-only,
  check-docs, check-backing, the fixture guard (the `Freeze: fixtures/ameli/`
  grant with its `MANIFEST.sha256` in the diff), check-pins, this spec's
  Evidence ids and Record-updates files.
- `make split-ameli` — recompute the fee split from `fixtures/ameli/` and
  write `data/ameli/fee_split.csv`; offline, no variable, byte-identical on a
  rerun (`rebuild` and `study` never write it, so the diff proves nothing
  without the re-run — the 9h lesson).
- `make rebuild ROWS=synthetic && make study` — the model marts carry the new
  row with no key, and the committed page equals the render (the file `study`
  reads is the synthetic one; `ROWS=none` is proven by the marts test).
- `git diff --exit-code -- …` — the committed artifact equals the recompute
  and the committed page equals the render.

## Done-when

1. **The second source is declared and read to a declared shape.** One
   declaration under `opendata/` names the dataset (its address, its `;`
   delimiter, the six columns read, the national codes `region = 99` /
   `departement = 999`, and the closed four-family label set); the slice
   reader opens the developer's hand-downloaded export (UTF-8, an optional
   byte-order mark on the header), refuses by name a year with no national
   rows before it looks at families (round 1, #8), keeps the year's four
   national family rows, and refuses by name a missing column, a family
   missing or repeated, or a family whose total is a suppressed token (`NS`,
   `NC`) or not a whole-euro total in the **bounded euro-total shape** declared
   in `ingest/parsed.py` beside the count shapes — ASCII digits, below one
   trillion (no national annual total reaches it), refused by name; never
   `count_in_range`, whose ceiling (2³¹ − 1, about €2.1 bn) is below the data,
   never a bare `int()` (round 1, #1) — a dropped family would silently move
   the national total; every other row is dropped and counted. *Evidence: row
   1.*
2. **The fixture is the four rows of one year, frozen; the artifact is plain
   arithmetic over it, tracked and byte-stable.** `make slice-ameli YEAR=YYYY`
   writes `fixtures/ameli/ameli-national.csv` (four columns:
   `annee;profession_sante;hono_sans_depassement_totaux;depassements_totaux`,
   four rows) and its `MANIFEST.sha256`; `make split-ameli` reads the fixture,
   computes each family's share `extra / (tariff + extra)` and the
   all-families share over the summed totals, writes `data/ameli/fee_split.csv`
   (`name,value`; whole euros; shares at six places) and prints them; a test
   recomputes every share with a plain division and asserts the pinned values;
   the committed file equals the recompute. *Evidence: row 2.*
3. **The artifact's name set is one public constant and its reader is
   strict.** `FEE_SPLIT_FIELD_NAMES` is what the writer emits, the reader
   requires and the tracked-files test reads — that test walks one closed map
   `{artifact path: name set}` over both open-data artifacts, the same three
   checks per entry, not a second `if` branch (round 1, #4); `read_fee_split`
   parses values in the repo's shared shapes (`DECIMAL_SHAPE` for the shares,
   the bounded euro-total shape for the totals, `valid_year`'s shape for the
   year — round 1, #1), refuses a missing, extra or duplicate name, a
   non-numeric or non-finite value, a share outside `[0, 1]`, a total off its
   shape and an oversized file, each by name, and returns the same split
   whatever the row order. *Evidence: row 3.*
4. **The model carries the row and nothing already shown moves.**
   `parameters(inputs)` — one container `cost_model.ModelInputs(fit,
   fee_split)` read by one `pipeline/build.py::read_model_inputs`, so a later
   input is a field, not a signature (round 1, #7) — gains `extra_billing_share`
   after `emp_mean`: sourced, cited to the artifact and the dataset, default
   the all-families share, `low`/`high` the lowest and highest family share — a
   spread read from the data, a third row that is not "an assumption on a
   slider", so the read-figure BACKLOG row's trigger is re-pointed, not claimed
   unfired (round 1, #2; Done-when 6); no formula reads it; every pinned parameter cell, output, crossover and Beat 4
   pin holds; `cost_model_params` has 17 rows on `none`, `synthetic` and
   `samples`, identical across two rebuilds, with no key. *Evidence: row 4.*
5. **The page shows the row and says only what its cells show.** B3.3 renders
   `extra_billing_share` through `PARAMETER_NAMES` (`"Share of fees billed
   above the tariff"`, a percentage) with its citation and range like every
   sourced row; the panel's blurb names it and its range clause becomes "and,
   for the inputs the formulas read, the range the study explores" (round 1,
   #2); its note (data in `study/text.py`) says the default is the four
   families together and the range the lowest and highest family share — a
   spread in the data, not a bound the study explores — and that the Assurance
   Maladie reimburses none of the part above the tariff, so that part is absent
   from the reimbursement cells the fit is built on — no figure the marts do
   not hold; B3.3's sources gain the
   artifact and the dataset's address; a name outside the map still refuses;
   every rendered number equals its mart cell. *Evidence: row 5.*
6. **The records say so.** SPEC.md B3.3 names the row as a context figure no
   formula reads; BACKING.md's B3.3 claim cell says the same ("…and, beside
   them, the extra-billing share of national practitioner fees — a context
   figure no formula reads"), its source cell names the dataset and a
   paragraph says what data.ameli holds, what it cannot supply and what the row
   shows (round 1, #5); README Beat 3 names it in one sentence that carries no
   figure — the percentage lives on the page, so `FIGURE_ROWS` does not grow
   (round 1, #9) — and the glossary gains *extra billing*; the BACKLOG row is
   struck with its trigger reinterpreted, the read-figure row's trigger is
   re-pointed ("9i added a third row that is not an assumption on a slider — a
   spread, not a fixed mark; a fourth such row, or a reader confusing a spread
   with an explored range, opens the `ReadFigure` shape" — round 1, #2), and
   one row opened on the complementary-side claim size whose trigger names
   DAMIR's fee and base columns as the route (round 1, #6); DECISIONS records
   the dataset facts, the ODbL attribution, the robots decision and the brief
   §7 clause as read. *Evidence: row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_fee_split.py::test_slice_keeps_the_four_national_family_rows_of_the_year`, `tests/test_fee_split.py::test_slice_refuses_a_missing_repeated_or_suppressed_family_by_name`, `tests/test_fee_split.py::test_slice_reads_a_bom_header_and_refuses_a_missing_column`, `tests/test_fee_split.py::test_slice_drops_and_counts_every_other_row`, `tests/test_fee_split.py::test_slice_refuses_a_year_with_no_national_rows_by_name`, `tests/test_fee_split.py::test_euro_total_shape_is_ascii_bounded_and_refuses_by_name` |
| 2 | `make slice-ameli YEAR=2024` (developer-run, once); `make split-ameli` prints the split; `tests/test_fee_split.py::test_shares_recomputed_by_hand`, `tests/test_fee_split.py::test_write_fee_split_is_byte_identical_on_rerun`, `tests/test_fee_split.py::test_fee_split_artifact_equals_recompute`, `tests/test_fee_split.py::test_fee_split_freeze_manifest_matches_sha256`, `tests/test_fee_split.py::test_split_ameli_writes_and_prints`, `tests/test_fee_split.py::test_split_ameli_missing_fixture_is_a_message` |
| 3 | `tests/test_fee_split.py::test_fee_split_field_names_is_the_write_order`, `tests/test_fee_split.py::test_read_fee_split_returns_the_pinned_split`, `tests/test_fee_split.py::test_read_fee_split_refuses_unknown_missing_or_non_numeric_names`, `tests/test_fee_split.py::test_read_fee_split_refuses_a_share_outside_zero_one_a_negative_total_and_an_oversized_file`, `tests/test_fee_split.py::test_read_fee_split_is_order_independent`, `tests/test_snapshots.py::test_the_only_tracked_files_under_data_are_hand_read_snapshot_csvs` |
| 4 | `tests/test_cost_model.py::test_extra_billing_share_row_spans_the_family_extremes_and_no_formula_reads_it`, `tests/test_cost_model.py::test_formulas_evaluate_to_the_pins` (unchanged pins), `tests/test_cost_model.py::test_each_scenario_changes_only_its_toggled_parameters`, `tests/test_model_marts.py::test_params_mart_has_one_row_per_parameter`, `tests/test_model_marts.py::test_three_marts_filled_on_every_input`, `tests/test_model_marts.py::test_two_rebuilds_identical_model_mart_rows`, `tests/test_model_marts.py::test_read_model_inputs_refuses_a_malformed_artifact` (extended to the fee split), `tests/test_guardrail_sim.py` and `tests/test_sim_marts.py` (unchanged pins) |
| 5 | `tests/test_beat3.py::test_b3_3_shows_the_extra_billing_share_with_its_family_range`, `tests/test_beat3.py::test_the_extra_billing_note_carries_no_figure_the_marts_do_not_hold`, `tests/test_beat3.py::test_b3_3_and_b3_4_render_every_parameter_with_default_unit_and_range`, `tests/test_beat3.py::test_a_name_outside_the_display_map_refuses_by_name`, `tests/test_beat3.py::test_every_beat3_value_equals_its_mart_cell`; `make study` + `git diff --exit-code` |
| 6 | `make check-docs`, `make check-backing`, `make review-gate SPEC=…` (Record updates); `tests/test_readme.py` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For all exports the slice reads, a kept row is one of the year's four national family rows, each family exactly once with two totals in the bounded euro-total shape; a year with no national rows, a family missing, repeated or suppressed, or a total off its shape refuses by name, never a partial total. | `tests/test_fee_split.py::test_slice_refuses_a_missing_repeated_or_suppressed_family_by_name` — an export lacking `Sages-femmes`, one with it twice, one with `NC` in a total; `::test_slice_keeps_the_four_national_family_rows_of_the_year` — a sub-group row, another year, another region are not kept; `::test_slice_refuses_a_year_with_no_national_rows_by_name` — `2031` names the year, not four families |
| 2. For all fixtures, every share the artifact carries is `extra / (tariff + extra)` of its family, and the all-families share is the same division over the four summed totals — a number a reader redoes in a spreadsheet; the all-families share lies between the lowest and highest family share. | `tests/test_fee_split.py::test_shares_recomputed_by_hand`; `tests/test_cost_model.py::test_extra_billing_share_row_spans_the_family_extremes_and_no_formula_reads_it` |
| 3. For all runs of `split-ameli` over the same fixture, the artifact's bytes are identical, and the committed artifact equals the recompute (no clock, no RNG, closed-form). | `tests/test_fee_split.py::test_write_fee_split_is_byte_identical_on_rerun`, `::test_fee_split_artifact_equals_recompute` |
| 4. For all artifacts, the reader accepts exactly the closed name set with values in the shared shapes (a total only in the bounded euro-total shape declared in `ingest/parsed.py` — never `count_in_range`, never a bare `int()`) and the declared domains, and returns the same split in any row order; anything else refuses by name — never a silent default, never a traceback downstream. | `tests/test_fee_split.py::test_read_fee_split_refuses_unknown_missing_or_non_numeric_names`, `::test_read_fee_split_refuses_a_share_outside_zero_one_a_negative_total_and_an_oversized_file`, `::test_read_fee_split_is_order_independent`, `::test_euro_total_shape_is_ascii_bounded_and_refuses_by_name`; `tests/test_model_marts.py::test_read_model_inputs_refuses_a_malformed_artifact` |
| 5. For every output, crossover and parameter shown before this phase, its value at the defaults is unchanged on every scenario; no formula reads the new row. | `tests/test_cost_model.py::test_formulas_evaluate_to_the_pins` with `COST_OUTPUTS`, `COST_CROSSOVERS`, the mu/sigma ranges and the Beat 4 pins untouched; `::test_extra_billing_share_row_spans_the_family_extremes_and_no_formula_reads_it` (no `FORMULAS` expression names it) |
| 6. For every `ROWS` input, with no key, the params mart carries the new row and two rebuilds give identical rows. | `tests/test_model_marts.py::test_three_marts_filled_on_every_input`, `::test_two_rebuilds_identical_model_mart_rows` |
| 7. For every number Beat 3 renders, it equals a mart cell and carries the row's tag; the note holds no figure the marts do not; a name outside the display map refuses by name. | `tests/test_beat3.py::test_every_beat3_value_equals_its_mart_cell`, `::test_the_extra_billing_note_carries_no_figure_the_marts_do_not_hold`, `::test_a_name_outside_the_display_map_refuses_by_name` |
| 8. For all values of `YEAR`, the value is validated to the century-bounded shape `valid_month` already uses (`20[0-9]{2}`, one shape family) before anything is read and never becomes a path; an empty, path-escaping, metacharacter or environment-set value refuses in one line. | `tests/test_fee_split.py::test_valid_year_refuses_bad_shapes`, `::test_slice_ameli_year_validation_refuses_before_any_read`; `tests/test_makefile.py::test_pipeline_variables_reach_python_as_one_literal` (gains `slice-ameli`/`YEAR`) |
| 9. For all of this phase, no command touches the network: the export is a file a person placed; the tracked artifact and the page are reproduced offline. | `tests/test_fee_split.py::test_fee_split_module_imports_no_network_module` (no `urllib`/`httpx` import in the new module); `make review-gate` offline |

## Pinned decisions (do not re-litigate)

- **The quantity is the extra-billing share over the four top-level families
  at the national level for one year, and its range is the family spread.**
  `extra / (tariff + extra)`: the default over the four summed totals, `low`
  and `high` the lowest and highest family share — a spread read from the
  data, a fourth kind of range beside floor-to-twice, ±2 SE and the fixed
  marks, and the blurb and note say so in those words: it is not a bound the
  study explores, and the row is not an assumption on a slider (round 1, #2).
  The four families are the whole (the 38 national labels nest under them);
  the closed label set lives in the source declaration. *Rejected: a lognormal
  over per-practitioner mean fees (a practitioner-income curve, not a claim
  cost — the BACKLOG row's premise, which the dataset does not support); a
  fixed mark with the spread in prose (a figure in a note must be a mart
  cell); five rows, one per family (clutter in B3.3 for one fact); the duller
  route — the same share from the DAMIR month already ingested, whose fee
  (`PRS_PAI_MNT`) and base (`PRS_REM_BSE`) columns sit on the very cells the
  fit describes, with no second source, no fixture directory and no robots
  question (round 1, #6) — rejected for two reasons: the fixture is a 5,000-cell
  systematic sample where data.ameli's totals are the exhaustive national
  population, and `fixtures/damir/` is frozen with one column pair, so reading
  two more is a re-freeze (a DECISIONS event) for a ratio the brief sources to
  data.ameli by name; the new BACKLOG row names that route for the
  complementary-side share per cell.* Satisfies invariants 2 and 5.
- **No fetch target: the export is a hand download, every command offline.**
  The host's robots file disallows `/api/` and the download paths to every
  crawler; the repo's precedent (Phases 2, 3a, 3c) is to honour it. The
  developer saves the dataset's CSV export from the browser to
  `data/cache/ameli/honoraires.csv` (gitignored; `;`-delimited, the portal's
  default) and runs `make slice-ameli YEAR=YYYY` once. No `confirm` gate is
  needed: nothing fetches, nothing deletes. *Rejected: a `confirm`-gated
  `fetch-ameli` over `urllib` (the DAMIR shape) — against the host's stated
  rule, whatever the API's rate-limit headers suggest; reading the API's JSON
  instead of the export — the same disallowed prefix.* Satisfies invariant 9.
- **One new module, one extended declaration.** `opendata/sources.py` becomes
  the declaration of both open-data sources (the DAMIR block unchanged; a
  data.ameli block: address, delimiter, columns, national codes, the four
  family labels with their artifact slugs, `valid_year`); `opendata/fee_split.py`
  holds the slice reader, the fixture writer, the split arithmetic, the
  artifact writer and reader, and the printer — the `slice.py` + `fit.py` pair
  in one file because the arithmetic is two sums and a division. The one
  addition outside `opendata/` is the bounded euro-total shape in
  `ingest/parsed.py`, beside the count shapes it resembles — the shared home
  the `unshaped-input` class was promoted to (round 1, #1); `models/` imports
  nothing new. *Rejected: a second package; a `fetch.py`-style module with
  nothing to fetch; a total parsed by `count_in_range` (its ceiling is below
  the data) or by bare `int()` (no bound at all).* Satisfies invariants 1, 3,
  4.
- **The artifact is `name,value`, numbers only, one closed name set.**
  `data/ameli/fee_split.csv`: `year`, then per family slug (`medecins`,
  `dentistes`, `sages_femmes`, `auxiliaires`) `tariff_eur_<slug>`,
  `extra_eur_<slug>`, `share_<slug>`, then `tariff_eur_all`, `extra_eur_all`,
  `share_all` — `FEE_SPLIT_FIELD_NAMES`, the writer's order, the reader's
  requirement, the tracked-files test's set (the 9h lesson: no hand-typed
  copy) — that test becomes one closed map over the two open-data artifacts
  walked once, never a second `if` branch (round 1, #4). Euros whole (the source publishes whole euros), shares at six places
  (a range's ends and a default printed as a percentage at one place need no
  more; six matches `_PARAM_DP`). `.gitignore` gains `!data/ameli/`. *Rejected:
  profession labels in the tracked file (a text field the tracked-files guard
  would have to allowlist; the slugs are the closed set); one file for both
  open-data artifacts (two writers, two shapes, two vintages).* Satisfies
  invariants 3, 4.
- **The model takes one container of its inputs; no formula reads the
  split.** `cost_model.FeeSplit(year, share, low, high)` is what the model
  needs from the artifact, and `cost_model.ModelInputs(fit, fee_split)` is
  what `parameters(inputs)`, `defaults`, the printers and the mart writers
  take — one signature change now, and a later input is a field (round 1,
  #7); `pipeline/build.py::read_model_inputs` is the one reader that lifts
  both artifacts (it absorbs `read_model_fit`), so `models/` still reads no
  file; the row's citation is `data/ameli/fee_split.csv ← data-ameli-honoraires
  (<year>)`; `check_parameter` is unchanged (the all-families share lies
  between the family extremes by construction, pinned). *Rejected: a literal
  in `SCALE_PARAMETERS` pinned equal to the artifact (the second-literal
  pattern 8a refused); widening `Fit` with fee fields (a DAMIR shape carrying
  a data.ameli figure — name drift; the container's name says what it holds);
  `parameters(fit, fees)` (every caller changes again at the next input, and
  the simulator's `defaults()` would name an artifact it never reads); a formula that multiplies the insurer's
  refunds by the share (the insurer's claims are not the national fee mix; an
  invented quantity).* Satisfies invariants 5, 6.
- **The page reads the row through the maps it has; one note, data.**
  `PARAMETER_NAMES` gains the entry (a percentage display), B3.3's blurb names
  the share, `study/text.py::EXTRA_BILLING_NOTE` says the four things Done-when
  5 lists and nothing else (pinned like `MEAN_CELL_NOTE`), B3.3's `sources`
  gain the artifact path and the dataset's address; no new `Series` shape, no
  new chart, palette unchanged. *Rejected: a fifth headline row (the headline
  is derived figures from the outputs mart; this is an input row); a new panel
  and BACKING row (a design change for one row).* Satisfies invariant 7.

## Scope (files)

- `opendata/sources.py` — the data.ameli declaration block; the module
  docstring becomes "the open-data sources".
- `ingest/parsed.py` — the bounded euro-total shape beside the count shapes.
- `opendata/fee_split.py` — new: `read_national_families`, `read_fixture`,
  `write_ameli_fixture`, the split arithmetic (`FamilyRow`, `FeeTotals`),
  `FEE_SPLIT_FIELD_NAMES`, `write_fee_split`, `read_fee_split`,
  `format_fee_split`; the manifest is `opendata.slice.freeze_manifest`, reused
  (review round 1, functionality-tester); `opendata/__init__.py` docstring.
- `fixtures/ameli/ameli-national.csv`, `fixtures/ameli/MANIFEST.sha256`
  — the frozen four-row slice (first freeze).
- `data/ameli/fee_split.csv` — the tracked artifact; `.gitignore` gains
  `!data/ameli/`.
- `pipeline/cli.py` — `slice-ameli` (`YEAR`), `split-ameli`; the `model` and
  `simulate` paths read the inputs container; `pipeline/build.py` —
  `read_model_inputs` (absorbs `read_model_fit`), `write_model_marts` /
  `write_sim_marts` take the container.
- `Makefile` — `slice-ameli`, `split-ameli`; `.PHONY`; help lines.
- `models/cost_model.py` — `FeeSplit`, `ModelInputs`, `parameters(inputs)`
  and the callers, the citation; `models/guardrail_sim.py` — its callers' signature
  only, no rule changes; `sql/marts/cost_model_params.sql` — header grain
  comment (17 rows).
- `study/text.py` — the display name, `EXTRA_BILLING_NOTE`; `study/panels.py`
  — B3.3's blurb, note and sources; `study/friction_ledger.html` — re-rendered.
- `tests/pins.py`, `tests/test_fee_split.py` (new), `tests/test_cost_model.py`,
  `tests/test_model_marts.py`, `tests/test_beat3.py`, `tests/test_snapshots.py`
  (the closed artifact map), `tests/test_number_shapes.py` (the new shape is a
  shaped parser),
  `tests/test_makefile.py`, `tests/test_readme.py` (the glossary count).
- `SPEC.md`, `BACKING.md`, `README.md`, `DECISIONS.md`, `BACKLOG.md`,
  `CLAUDE.md`, this spec.

Freeze: fixtures/ameli/

(`fixtures/ameli/` is created new in this phase — its first freeze. The grant
covers the directory and requires its `MANIFEST.sha256` in the diff; it is
read-only after 9i.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9i entry: the dataset as read (grain, columns,
  license, the nested labels), the robots decision (no fetch; hand download;
  the research requests disclosed), the BACKLOG trigger reinterpreted, the
  brief §7 clause as it stands against the dataset, the rejected alternatives
  above, the challenge round
- [ ] `BACKLOG.md` — *data.ameli practitioner-fee distributions are not
  ingested* struck DONE Phase 9i (trigger reinterpreted); one row opened:
  *The claim-cost anchor is the public insurer's reimbursement; a complementary
  insurer's share of the same bill has no anchor* (trigger: a reader or
  reviewer asks for the complementary-side claim size or share — DAMIR's fee
  (`PRS_PAI_MNT`) and base (`PRS_REM_BSE`) columns can supply both per cell,
  at a `fixtures/damir/` re-freeze); the read-figure row's trigger re-pointed
  (round 1, #2); the DAMIR-refresh row's trigger extended to name the fee
  split's vintage; the count updated
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Commands (`slice-ameli`, `split-ameli`;
  the `confirm` set unchanged); Repo map (`opendata/fee_split.py`,
  `fixtures/ameli/`, `data/ameli/`); BACKLOG count
- [ ] `BACKING.md` — B3.3's claim cell names the share as a context figure
  no formula reads (round 1, #5); its source cell gains
  `data-ameli-honoraires`; a paragraph "On the `data-ameli-honoraires`
  upstream (B3.3)" beside the DAMIR one, naming the ODbL attribution; no
  row's tag changes
- [ ] `SPEC.md` — Beat 3: B3.3's sentence names the share, its family
  spread and that no formula reads it (no chart or beat changes; the glossary is at its cap of ten, so the
  term is defined in the panel's note)
- [ ] `README.md` — Beat 3: one sentence naming the share, carrying no
  figure (round 1, #9); the glossary's tenth term, *extra billing*
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

`make slice-ameli` is the one new target that takes a variable (`YEAR`). It
touches no network (it reads a file a person placed), deletes nothing and pays
nothing, so it has no `confirm` gate — the `sample-damir` shape. Settled shape
(Phase 3a): one Python process validates `YEAR` against the century-bounded
shape `valid_month` uses (round 1, #8), then reads the cache file at a constant path and filters rows on the
value; the recipe is one line; `YEAR` reaches Python single-quoted
(`$(call _Q,$(value YEAR))`) and `unexport`ed, and never becomes a path — the
cache and fixture paths are constants. `make split-ameli` takes no variable,
touches no network, deletes nothing — no gate.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `slice-ameli` | refuse (no default year; exit 2) | refuse (the shape is `20[0-9]{2}`) | refuse (the shape rejects `;` and space) | reaches Python and is validated the same; a valid year from the environment filters rows, never names a path | n/a — no confirm goal (nothing fetched or deleted) | `test_valid_year_refuses_bad_shapes`, `test_slice_ameli_year_validation_refuses_before_any_read`, `test_pipeline_variables_reach_python_as_one_literal` |

The two foreign inputs are the hand-placed export (parsed to the declared
shape of Done-when 1; anything off it refuses by name or is dropped and
counted) and the tracked artifact (Done-when 3). Run twice: `slice-ameli`
rewrites the same fixture and manifest; `split-ameli` rewrites the same bytes.
No credentials anywhere on the path; the no-key run is green by construction.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `*.py`, `sql/**`, `models/**`, `Makefile`,
  `tests/`): the closed shapes (the four-label set, the column set, the name
  set), one rounding site, no literal typed where the artifact is the source,
  the parameters signature change carried to every caller, scope (one row,
  no formula).
- **security-reviewer** (mandatory — `opendata/**`, `pipeline/cli.py`, a
  `Makefile` variable): the hand-placed export is parsed to a declared shape,
  streamed row by row with no byte cap and the reason written in the reader
  (review round 1, security #1), and no path is derived from `YEAR`; no network import in the
  new module; the tracked fixture and artifact carry no personal data and no
  brand (profession families and whole-euro totals); `data/cache/ameli/` stays
  gitignored; the robots decision honoured (no fetch code at all).
- **functionality-tester** (after code-reviewer): the DONE command; two
  rebuilds; the no-key run; a hand-corrupted export (a family missing, `NC`,
  a BOM-less header, a `,` delimiter) and a hand-corrupted artifact refused
  by name; every pre-phase pin unchanged.
- **study-editor** (triggered — README, SPEC, BACKING, `study/`): the note
  says the literal thing (what the share is, what the range is, what the
  Assurance Maladie does not reimburse) with no verdict on the insurers; two
  layers; *extra billing* defined once per surface.
- **coherence-auditor** at exit: "the four fit rows … 16 rows" moved to 17
  everywhere (mart header, pins comments, docstrings); "The one declaration
  of the Open DAMIR source" gone from `opendata/sources.py`; the CLAUDE.md
  Repo map names `opendata/fee_split.py`; the BACKLOG row struck and the new row
  present; the DAMIR-refresh row names both vintages; no sentence left saying
  data.ameli is not ingested.
- Stack risk (verify in the first hour, with the developer's downloaded file
  in hand — as of the stamp the export has not been downloaded, so this is
  the first hour's STOP and the fixture is cut then, not before; round 1,
  #10): the export's delimiter and header as the browser saves them (the
  API export was `;` with a UTF-8 byte-order mark; the browser's "Export"
  dialog offers a delimiter choice — the reader declares `;` and refuses
  another); whether the four family labels are spelled in the file exactly as
  the API returned them (accents, the `ODF` parenthetical is on sub-groups
  only); that the four family rows nest cleanly — the sub-rows sum to each
  family and nothing sits outside the four — checked by a ten-line stdlib
  `csv` script over the file, offline. STOP and report before any workaround;
  findings → DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- **A per-act or per-claim fee distribution** — not in data.ameli's
  `honoraires`; DAMIR's own fee (`PRS_PAI_MNT`), base (`PRS_REM_BSE`) and act
  count columns could give the complementary-side claim size per cell — the
  BACKLOG row this phase opens.
- **The fee categories of `honoraires-detailles`** (clinical acts, technical
  acts, flat-rate payments) — annual per-practitioner totals again; no claim
  size in them.
- **A multi-year series of the share, or the per-family rows on the page** —
  one year's four families is the fact B3.3 needs; the Metabase demonstration
  is the exploration surface.
- **A brief §7 edit** — the clause "data.ameli for practitioner-level fees" as
  a simulator draw source does not hold for this dataset; DECISIONS stands as
  the record (round 1, #11: the developer's disposition left the brief
  untouched, so the exit coherence audit treats brief↔DECISIONS as accepted,
  recorded drift); a brief edit remains the developer's call outside this
  diff.

## Amendments

**Round 1 (2026-09-12, challenge, approve with amendments; disposition: fix
all).** Nine findings applied above, each marked "round 1, #n": a bounded
euro-total shape in `ingest/parsed.py` for the totals, never the count shape or
a bare `int()` (#1); the fourth range kind told truthfully in B3.3's blurb and
note and the read-figure BACKLOG trigger re-pointed (#2); two names, `ameli` for
the source and `fee_split` for the artifact and module, the reused test names
prefixed (#3); the tracked-files guard a closed map over both artifacts (#4);
B3.3's BACKING claim cell names the share as a context figure no formula reads
(#5); the DAMIR fee/base-columns route recorded as the rejected duller way and
named in the new BACKLOG row (#6); one `ModelInputs` container instead of
`parameters(fit, fees)` (#7); `valid_year` century-bounded and an absent year
refused by name first (#8); the README sentence carries no figure (#9). The two
questions: the export is not yet downloaded — the first hour's STOP (#10); the
brief §7 clause stands with DECISIONS as its record (#11).
