# Phase 9b — Beat 2: the corpus gate, the counted band and the trail

Contract for the `phase-9b-beat-2` branch. Source: PROJECT_BRIEF.md §9 Phase 9
("The study"), sub-phase 9b of the permanent-artifact-first split (DECISIONS →
Phase 9a). Depends on Phase 9a merged (PR #21, 2026-09-08) **and on the fix PR
`fix/theme-marts-run-id` merged** (the two theme marts carry `run_id`; challenge
round 1, finding 3).

**Status: APPROVED 2026-09-08 — in progress.** No new dependencies: Beat 2
renders through the 9a contract (`duckdb` + stdlib, hand-written inline SVG); no
script, no `<details>`, no new `make` target.
Challenged: 2026-09-08, round 1, spec 198ff491 — rework (all findings applied)
Fix amendment: 2026-09-08, round 1 — a panel's notes are a sequence
(study-editor #2, #3); appended to Invariants below. This makes the challenge
stamp stale (the hash covers Invariants); re-challenge is the developer's call.

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

Beat 2 is the part the whole pipeline exists to produce: the five themes counted
over time and by segment, the classifier's own score beside them, and the peer
ratings that keep any one insurer from being read alone. Its marts have been
built and honest since Phases 5b–7a; nothing renders them. 9a fixed the render
contract for Measured / Documented / Pending panels on Beat 1 and deferred to
this beat the counted `unclassified` series, the review-text rule's enforcing
test, and the first Measured panel whose input is the review corpus rather than
an anchor.

The challenge round (2026-09-08, rework) moved the centre of the phase. The
committed page renders from the frozen synthetic fixture (9a), and the brief
says three times that a share over fake reviews is never shown as a number
(§3 Beat 2 "until real, it's tagged Pending — never faked"; §10; §2.4). So the
first thing Beat 2 needs is a **corpus gate**: a panel whose numbers derive from
the review corpus renders a number only when the rows it counts came from a
captured input, and renders a labelled no-number state over a fixture. The
second thing it does not need is a per-review list: no declared source yields a
per-review public address (every parser stores the page address, which on a
captured input spells the brand — DECISIONS D1), so a row-per-review list could
be neither traced nor published. The trail the export gives is the mart's own
`reviews` and `theme_rows` integers beside each share — stored in 7a precisely
so the share can be redone by hand — and the structural guarantee that the
export never reads a text column. The review-level drill lives where the brief
puts it: the Metabase demonstration (9g) over the reader's own rebuild.

This is not a fix PR: it adds five panels, a chart kind (the metric table), two
contract extensions (the corpus gate; a declared absence in a metric cell), the
band's colour as a closed choice, and the module split the renderer needs to
stay one layer per file.

## The central constraint

**A number that derives from the review corpus is rendered only over a captured
input; over a fixture the panel renders a labelled state and no number; every
rendered number equals a mart row and carries one tag; no review text is ever
read by the export — while the 9a contract (byte-identical on rerun, the
committed baseline, the one-tag and Pending refusals) and the Beat 2 marts do
not move.** `sql/`, `pipeline/`, `classify/`, the existing pins in
`tests/pins.py`, SPEC.md's beat structure and BACKING.md's row set stay as they
are (the one SQL change, `run_id` on the two theme marts, lands in its own fix
PR before this branch starts).

## DONE command

```
make rebuild ROWS=synthetic && make study && git diff --exit-code -- study/ && uv run pytest tests/test_beat2.py -q
```

- `make rebuild ROWS=synthetic` builds the frozen input: the synthetic reviews
  through the rules with no key; every classified row and both theme marts
  carry `run_id = 'synthetic'`. Reproduces the existing synthetic rebuild.
- `make study` renders Beats 1 and 2 into `study/friction_ledger.html`: B2.1
  Pending, B2.3 the anchors chart, B2.2/B2.4/B2.5 the labelled fixture state
  with no number. A contract breach exits non-zero with one line naming the
  panel.
- `git diff --exit-code -- study/` proves the render matches the committed
  baseline (byte identity on rerun is 9a's test, inherited).
- `uv run pytest tests/test_beat2.py -q` proves what the baseline bytes cannot
  show, because the baseline shows no corpus number: over a test-owned copy of
  the synthetic DB whose `run_id` is rewritten to `captured`, the builders
  produce every value equal to its mart, the band on the neutral token, the
  counts beside each share, the declared absences; the renderers are proven
  over hand-built panels against pinned HTML fragments; the column allowlist
  and the corpus gate's refusals are exercised directly.

## Done-when

1. **Beat 2 renders into the baseline honestly.** B2.1 renders the Pending
   placeholder; B2.3 renders the peer ratings from `peer_ratings` (Documented
   anchors, the one Beat 2 chart in the committed page), each point labelled by
   platform and the placed-point rule stated beside it; B2.2, B2.4 and B2.5
   render the labelled fixture state — "built from hand-written fixture
   reviews: the pipeline's proof, not a finding" — carrying no number, distinct
   from Pending and from "no data yet". *Evidence: rows 1, 2, 3.*
2. **The corpus gate is data, checked at render time.** For a panel whose
   numbers derive from the review corpus, the builder reads the mart's own
   `run_id`; exactly one value of `pipeline.build.INPUTS` is accepted;
   `captured` renders the numbers, a fixture input (`synthetic`, `samples`)
   renders the fixture state, `none` renders 9a's "no data yet"; two values or
   one outside the set refuse in one line naming the panel. *Evidence: rows 4,
   5.*
3. **Over a captured input every Beat 2 value equals its mart, and the band is
   counted.** From a test-owned copy of the synthetic DB with `run_id`
   rewritten to `captured`: B2.2 is one line per theme with the share plotted
   against the axis (never stacked — the review × theme grain can sum past 1);
   B2.5 grouped bars by segment; B2.4 the per-label table; the `unclassified`
   share is one series on the neutral token named "not yet classified", present
   in the legend with its count in every render (0 when the mart holds no such
   row); `positive` rows are excluded from the theme series and the exclusion
   stated; `reviews` and `theme_rows` render beside each share. Rendered figures
   pinned in `tests/pins.py`. *Evidence: rows 6, 7, 8, 9.*
4. **The export reads only an allowlisted column set, so review text cannot
   reach the page.** Every query the export runs projects only columns of one
   closed allowlist (checked on the cursor's description, so `select *` fails
   by name); `title` and `body` are not in it; every study query passes the
   SQL portability and clock lint. This is the 9a excerpt/paraphrase
   contract's enforcing test and the mechanism that closes the health-details
   BACKLOG row. *Evidence: rows 10, 11.*
5. **A metric cell is a value or a declared absence, never both, never a
   blank.** `Point` carries value xor absence; both set is refused by name in
   `check_panel`; a null mart cell with no declared absence is still refused
   (9a); B2.4's zero-denominator cells (0 predicted or 0 actual) render "no
   held-out case" with the integer counts; a table whose every metric cell is
   absent still renders as a table of absences, not "no data yet". *Evidence:
   rows 12, 13.*

(5 items, ≤ 6.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat2.py::test_b2_1_renders_the_pending_placeholder_with_no_value` |
| 1 | `tests/test_beat2.py::test_b2_3_labels_each_point_by_platform_and_states_placed_points` (values pinned; `_PROFILE_NAMES` covers the four anchor profiles; an unknown profile refuses by name) |
| 1 | `tests/test_beat2.py::test_corpus_panels_render_the_fixture_state_over_synthetic` (B2.2/B2.4/B2.5 carry no digit inside the panel body and the state text; distinct from the Pending and no-data strings); `make study && git diff --exit-code -- study/` exits zero |
| 2 | `tests/test_beat2.py::test_the_corpus_gate_reads_run_id_from_the_mart` (`captured` → numbers; `synthetic`/`samples` → fixture state; `none` → no data yet; the set is `pipeline.build.INPUTS`, imported) |
| 2 | `tests/test_beat2.py::test_two_run_ids_or_one_outside_inputs_refuse_one_line` |
| 3 | `tests/test_beat2.py::test_beat2_values_equal_their_marts_over_a_captured_run_id` (the test-owned copy; figures pinned in `tests/pins.py`) |
| 3 | `tests/test_beat2.py::test_the_unclassified_band_is_the_neutral_token_and_always_in_the_legend` (count per cell equals the mart's row; legend entry present with 0 when absent; a series colour outside the closed choice refuses by name) |
| 3 | `tests/test_beat2.py::test_b2_2_plots_each_share_against_the_axis_not_stacked` (a cell whose shares sum past 1 renders every point at `_y_of(share)`) and `::test_positive_rows_are_excluded_from_the_theme_series_and_stated` |
| 3 | `tests/test_beat2.py::test_reviews_and_theme_rows_render_beside_each_share` |
| 4 | `tests/test_beat2.py::test_every_export_query_projects_only_allowlisted_columns` (a recording connection checks `cursor.description` per query; `select * from stg_reviews` fails by name) |
| 4 | `tests/test_beat2.py::test_every_study_query_passes_the_sql_lint` (`STUDY_QUERIES` through `find_nonportable` and `find_clock`) |
| 5 | `tests/test_beat2.py::test_a_zero_denominator_metric_renders_a_labelled_absence_with_its_counts` and `::test_a_null_cell_with_no_declared_absence_is_still_refused_by_name` |
| 5 | `tests/test_beat2.py::test_a_point_with_both_value_and_absence_is_refused` and `::test_an_all_absent_table_renders_as_a_table_not_no_data` |

The 9a tests are inherited unchanged: byte identity on rerun, no CDN / asset /
timestamp, the one-tag and Pending-with-value refusals, locale independence.
`test_every_panel_renders_its_backing_row_id_and_source_link` now walks nine
panels; imports follow the module split.

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all panels whose numbers derive from the review corpus, a number is rendered only when the classified rows' `run_id` is a captured input; a fixture input renders a labelled state and no number. | `tests/test_beat2.py::test_corpus_panels_render_the_fixture_state_over_synthetic`; `::test_the_corpus_gate_reads_run_id_from_the_mart`. |
| For all corpus panels, the `run_id` the gate reads is exactly one value of the closed `INPUTS` set; anything else refuses in one line. | `tests/test_beat2.py::test_two_run_ids_or_one_outside_inputs_refuse_one_line`. |
| For all cells of the two theme marts that hold an `unclassified` row, the rendered panel shows that share as the neutral-token series; the legend names the band with its count in every render, so absence reads as zero, never as hidden; the series colour is a closed choice. | `tests/test_beat2.py::test_the_unclassified_band_is_the_neutral_token_and_always_in_the_legend`. |
| For all Beat 2 shares, the plotted position is the share itself, never a cumulative stack. | `tests/test_beat2.py::test_b2_2_plots_each_share_against_the_axis_not_stacked`. |
| For all renders, every query the export runs projects only columns of one closed allowlist that holds no text column, and passes the SQL lint. | `tests/test_beat2.py::test_every_export_query_projects_only_allowlisted_columns`; `::test_every_study_query_passes_the_sql_lint`. |
| For all metric cells, exactly one of value and declared absence is set; a zero-denominator cell renders its labelled absence with its counts; a table of absences is still a table. | `tests/test_beat2.py::test_a_point_with_both_value_and_absence_is_refused`; `::test_a_zero_denominator_metric_renders_a_labelled_absence_with_its_counts`; `::test_an_all_absent_table_renders_as_a_table_not_no_data`; `::test_a_null_cell_with_no_declared_absence_is_still_refused_by_name`. |
| For all rendered Beat 2 numbers, the value equals its mart row and carries exactly one tag (9a's contract, extended to the new panels and the table kind). | `tests/test_beat2.py::test_beat2_values_equal_their_marts_over_a_captured_run_id`; 9a's `test_a_panel_with_no_tag_or_two_tags_is_refused` over a table panel. |
| For all runs over the same DB, the output bytes are identical and match the committed baseline (9a, inherited). | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun`; the DONE command's `git diff --exit-code`. |

### Fix amendment — round 1 (2026-09-08): a panel's notes are a sequence

Design change (the `Panel` data structure). `Panel.note: str` becomes
`Panel.notes: tuple[str, ...]`, and `study/export.py` renders one
`<p class="note">` per element (today it renders one). Round 1 found B2.5's
single note packing four ideas (study-editor #2) and the two theme-share
panels naming no sampling bias (study-editor #3); one string can neither
separate the ideas nor host the caveat.

Invariant restored: **for all panels, the second layer is a sequence of short
notes, each rendered as its own block (brief §2.3 — rigor one layer down, kept
scannable); and for all corpus panels drawn from the unsolicited review
platforms (B2.2, B2.5), the negative-self-selection caveat is one of those
notes (brief §2.5), as B1.2 already carries it beside the rating trend.**
Falsified by `tests/test_beat2.py::test_a_panel_renders_one_block_per_note`
and `tests/test_beat2.py::test_b2_2_and_b2_5_name_the_self_selection_bias`. The
committed baseline gains the split notes and the caveat; byte-identical on rerun.

## Pinned decisions (do not re-litigate)

- **The corpus gate: a corpus-derived number renders only over `captured`,
  read from the mart's own `run_id`, never from the DB filename or a caller
  flag.** The theme marts carry `run_id` after the fix PR; `classifier_quality`
  has carried it since 6b; the set is `pipeline.build.INPUTS`, imported. Over
  a fixture the panel renders the labelled fixture state through 9a's state
  machinery. A captured render is a local, developer-run render through
  `write(db=…)` (already the tests' entry), never committed in Phase 9b; whether
  the published study is such a render is 9f's decision (BACKLOG row opened
  here). *Rejected: a sentence beside a Measured fixture number — the brief
  forbids the number, not the sentence; deriving the input from `DEFAULT_DB`'s
  name — caller-sourced.* Satisfies invariants 1, 2.
- **The export's trail is the mart's `reviews` and `theme_rows` beside each
  share, plus the structural no-text guarantee; the per-review drill is the
  Metabase demonstration (9g).** No declared source yields a per-review public
  address (every parser stores the page address, brand-carrying on a captured
  input — D1), so a row-per-review list could be neither traced nor published,
  and each row's rating would be an untagged number with no mart row.
  *Rejected: the per-review link list (challenge round 1, BLOCKER 2); the rule
  token that fired as the "one short marked phrase" (re-runs the rules over
  text inside the renderer).* Satisfies invariants 5, 7.
- **The no-text guarantee is a column allowlist checked on the cursor's
  description, not a denylist on query text.** One closed set of the column
  names the export may read; a query projecting anything else fails by name,
  so `select *` cannot pass. The study's queries are one tuple
  (`STUDY_QUERIES`) and a test runs each through `pipeline/sql_lint.py`, the
  `pipeline/metrics.py` pattern. *Rejected: grepping query text for `title` /
  `body` — a denylist, the `unshaped-input` class; a four-word-run scan — near
  vacuous against French fixture bodies and English page prose.* Satisfies
  invariant 5.
- **The `unclassified` band is one series on the palette's neutral token; the
  series colour is a closed choice on the type.** `Series` carries a colour
  that is a categorical slot `0..4` or the neutral token, refused by name
  outside it — never a sentinel integer reaching `var(--s{slot})`. The band's
  legend entry is fixed in every render with its count. `positive` rows are
  excluded from the theme series (a theme chart counts complaints) and the
  exclusion, with the denominator — every classified review, `positive`
  included — is stated beside the chart; SPEC.md's and BACKING.md's "share of
  negative reviews" wording is corrected to the mart's denominator in this
  phase's docs commit (a claim-cell wording fix, approved in the challenge
  disposition). *Rejected: a sixth or seventh categorical colour (the five-slot
  order is the CVD-safety mechanism); a stacked area (draws a cumulative number
  no mart holds).* Satisfies invariants 3, 4.
- **A metric cell is value xor declared absence.** `Point` gains `absent: str`;
  `check_panel` refuses both set; a null cell with no absence stays 9a's
  refusal; the B2.4 builder sets the absence exactly when `predicted == 0` or
  `actual == 0` and carries the integer counts; the `table` kind dispatches on
  "any cell present" (value or absence), so a table of absences renders as a
  table. *Rejected: rendering 0.0; a dash; a second optional field with no
  refusal (four states, three specified).* Satisfies invariant 6.
- **The module split has one direction: `study/model.py` ← `study/panels.py`
  ← `study/export.py`.** `model.py` holds the types, `TAGS`, `Kind`, `Unit`,
  `check_panel`, `_require`, `RenderRefused`; `panels.py` the builders
  (`beat1_panels` moved verbatim, `beat2_panels`, the readers, the corpus gate,
  `_PROFILE_NAMES` as a closed lookup refusing an unknown profile by name);
  `export.py` the renderers, the page and `write`. The move is its own commit
  so the diff shows a rename and `check-pins` sees the moved symbols named in
  the changed tests. *Rejected: builders importing from `export` (a cycle);
  one 1,100-line file (two layers in one).*

(6 pinned decisions, ≤ 6.)

## Scope (files)

- `study/model.py` — new: the 9a types and contract moved verbatim, plus
  `Point.absent`, the closed series colour, the value-xor-absence refusal (the
  `architecture-fit` skill loaded by name before the module is created).
- `study/panels.py` — new: `beat1_panels` moved verbatim, `beat2_panels`, the
  Beat 2 readers, `STUDY_QUERIES`, the corpus gate, `_PROFILE_NAMES`.
- `study/export.py` — the `table` renderer, the count-beside-share and legend
  rendering, the fixture state, the page assembling Beats 1–2, `write`.
- `study/friction_ledger.html` — the committed baseline, re-rendered.
- `tests/test_beat2.py` — new: the Evidence rows above, including the
  test-owned `captured`-run_id copy of the synthetic DB and the recording
  connection.
- `tests/test_export.py` — imports follow the split; the panel-walk tests cover
  nine panels.
- `tests/pins.py` — the Beat 2 figures over the captured-run_id copy; the pinned
  HTML fragments per kind.
- `SPEC.md` — Beat 2: B2.2/B2.5 "share of negative reviews" → the mart's
  denominator (every classified review), `positive` excluded from the theme
  series and stated; one sentence under B2.2/B2.4/B2.5 naming the fixture state
  the committed page shows; one under B2.4 naming "no held-out case"; the
  trail sentence (counts beside each share; the review-level drill is the
  Metabase demonstration). No row id, tag or chart type changes.
- `BACKING.md` — the B2.2 and B2.5 claim cells' "negative reviews" wording
  corrected to the mart's denominator; no tag flips.
- `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, this spec — per Record updates.
  (No `README.md`: Phase 9f's deliverable.)

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9b entry: the corpus gate (the brief's "never
  faked" applied at render time); the trail as counts, the drill as Metabase
  (9g); the column allowlist; the neutral-token band and the closed series
  colour; `positive` excluded and the denominator wording fix; value xor
  absence; the module direction; the challenge dispositions (round 1, rework,
  all twelve applied); supersede nothing here (the 7a `run_id` supersede line
  lands in the fix PR).
- [ ] `BACKLOG.md` — close *Health details arrive in review bodies* (struck +
  "DONE Phase 9b": the export projects only an allowlisted column set, pinned
  by test); keep *The "vs traditional" half of B2.2/B2.5 is empty* open
  (stated beside B2.5); open *The published study's corpus render* (trigger:
  9f decides whether a captured render is the published page, and its brand-
  address and page-size questions); open *A per-review drill needs a
  per-review public address* (trigger: a source that yields one, or the
  Metabase demonstration 9g); re-point *`make idempotency-check` skips the
  classify step* (its trigger named 9b and fired; the target is
  `pipeline/build.py`, an earlier phase — a `fix/` PR at 9f or Phase 10);
  update the count.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Repo map (`study/model.py`, `study/panels.py`,
  Beat 2 rendered, 9c next); BACKLOG count; Commands unchanged.
- [ ] `BACKING.md` — the two claim-cell wording fixes above; no tag change, no
  row added or removed, so `make check-backing` is unaffected.
- [ ] `SPEC.md` — the Beat 2 sentences under Scope (panel details and one
  wording fix; row ids, tags and chart meanings unchanged).
- [ ] README — none (the repo has no README yet; Phase 9f).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make study` is unchanged: no variable, reads the synthetic DB and
tracked data, writes one file. Run twice: identical bytes. No credentials:
identical bytes. A captured render is not a `make` target in this phase (pinned
decision 1); if 9f adds one it gets its own Threat-model row there. The export's
reads are the repo's own marts through the column allowlist and 9a's `_require`
boundary; the only `href` it renders is a platform root, `http(s)`-only (9a).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `study` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` (unchanged) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `tests/`): the corpus gate keyed
  on the mart's `run_id` against the imported `INPUTS`, never on a filename or
  an `if` on a panel id; the band built from the mart's own `unclassified` row
  (never `1 − sum`); no share recomputed; lines not stack; the colour as a
  closed choice on the type; value xor absence refused in `check_panel`; the
  allowlist on `cursor.description`; the three-module direction with the moves
  verbatim in their own commits; scope (Beats 3–5, the README, Metabase,
  `FORMULAS` `expression_text` are out).
- **security-reviewer** (not triggered — `study/` is not on the Sensitive row
  and the per-review surface is gone; the personal-data guarantee is the
  allowlist test, which code-reviewer and functionality-tester read).
- **functionality-tester** (triggered): the DONE command; the fixture state in
  the baseline for B2.2/B2.4/B2.5 with no digit in the panel body; the
  captured-run_id copy's figures against the marts; the refusals (two run_ids;
  an input outside the set; both value and absence; a null cell with no
  absence; `select *` through the recording connection); a render over
  `ROWS=none` ("no data yet", no crash); two renders identical.
- **study-editor** (triggered — SPEC.md and BACKING.md sentences, the rendered
  Beat 2 prose): the fixture state named by meaning, no hedge; the hypothesis
  stated as a test, not a verdict (B2.5 asserts no gap before its chart); "not
  yet classified" and "no held-out case" plain; the placed-point note beside
  B2.3; the denominator sentence; banned words absent; no editorial sentence
  about one insurer.
- **coherence-auditor** at exit (mandatory): SPEC ↔ BACKING ↔ marts ↔ the
  rendered Beat 2 agree, including the corrected denominator wording; the
  health-details row struck, the two new rows open, the traditional row still
  open; CLAUDE.md's status names 9c next; the 9a Delivered paragraph's "9b
  lands the excerpt/paraphrase enforcing test" satisfied by the allowlist test
  by name.
- Stack risk: the recording connection must see the projected columns of every
  query the builders run (DuckDB's `cursor.description` after `execute`) —
  verify in the first hour that a wrapped connection exposes it without a second
  execution; the metric table's escaping under the two-locale test. Any surprise
  goes to DECISIONS → Gotchas; STOP before a workaround.

## Out of scope (deferred, recorded)

- The per-review drill-through — the Metabase demonstration (9g) over the
  reader's own rebuild, and the BACKLOG row on a per-review public address.
- A captured render as the published page — 9f (the BACKLOG row this phase
  opens).
- A traditional-mutuelle source — the open BACKLOG row; B2.5 states the wait.
- Curating B2.1's five paraphrased examples with links (flips B2.1 Pending →
  Documented) — a content task, BACKLOG.
- `FORMULAS` `expression_text` rendering — 9c (Beat 3, the first Modeled panels).
- Beats 3–5, the README + stranger test, Metabase — 9c–9g, each its own spec.
- A `decided_by` column on `stg_classified_reviews` (rules vs model per row) —
  a staging-schema change belonging to an earlier phase; BACKLOG candidate.

## Challenge dispositions (round 1, 2026-09-08 — rework, all applied)

BLOCKER 1 (fixture shares under Measured) — **amend**: the corpus gate, pinned
decision 1, invariants 1–2. BLOCKER 2 (the per-review list) — **amend**: the
list dropped, the trail is counts beside each share, pinned decision 2. #3
(`run_id` on the theme marts) — **amend** as the fix PR `fix/theme-marts-run-id`
this spec depends on. #4 (`positive`; "negative reviews" wording) — **amend**:
pinned decision 4 and the two claim-cell fixes. #5 (allowlist, not denylist) —
**amend**: pinned decision 3. #6 (value xor absence) — **amend**: pinned
decision 5. Suggestions #7 (module direction), #8 (lint the study queries), #9
(closed series colour) — **amend**, folded into pinned decisions 6, 3, 4.
Questions #10 (security-reviewer not triggered), #11 (a captured render is
local and uncommitted; 9f decides), #12 (the band's legend entry with its count)
— answered in Review & stack risk, pinned decision 1 and pinned decision 4.
