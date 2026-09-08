# Phase 9b — Beat 2: the counted band and the drill-through (PROPOSED)

Contract for the `phase-9b-beat-2` branch. Source: PROJECT_BRIEF.md §9 Phase 9
("The study"), sub-phase 9b of the permanent-artifact-first split (DECISIONS →
Phase 9a). Depends on Phase 9a merged (PR #21, 2026-09-08).

**Status: PROPOSED — do not start until approved.** No new dependencies: Beat 2
renders through the 9a contract (`duckdb` + stdlib, hand-written inline SVG); the
drill-through is plain `<details>` HTML, no script.

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

Beat 2 is the part the whole pipeline exists to produce: the five themes counted
over time and by segment, the classifier's own score beside them, and the peer
ratings that keep any one insurer from being read alone. Its marts have been
built and honest since Phases 5b–7a; nothing renders them. 9a fixed the render
contract for Measured / Documented / Pending panels on Beat 1 and deferred three
things to the beat where each first becomes a real, falsifiable number: the
counted `unclassified` series, the review-text drill-through under the 9a
excerpt/paraphrase contract, and a Measured panel whose input is the review
corpus rather than an anchor.

This is not a fix PR: it adds five panels, two chart kinds (a metric table and
the drill list), one contract extension (a declared absence in a metric cell),
and the first surface that lists reviews one by one — which is where the
"Health details arrive in review bodies" BACKLOG row, open since Phase 2, is
finally decided by a mechanism.

## The central constraint

**The band is counted, the trail is complete, the text stays out: every
`unclassified` row the marts hold renders as its own gray share, every theme bar
opens to the full list of reviews behind it, and no review title or body reaches
the export — while the 9a contract (one tag per number, a Pending panel shows
none, byte-identical on rerun, the committed baseline) and the Beat 2 marts do
not move.** `sql/`, `pipeline/`, `classify/`, `tests/pins.py`'s existing pins,
SPEC.md's beat structure and BACKING.md's row set stay as they are.

## DONE command

```
make rebuild ROWS=synthetic && make study && git diff --exit-code -- study/ && uv run pytest tests/test_beat2.py -q
```

- `make rebuild ROWS=synthetic` builds the frozen input: the synthetic reviews
  through the rules with no key, so the `unclassified` band is the honest
  no-key band (7 of 39 reviews today) and `classifier_quality` carries two
  null-metric rows (0 predicted, 0 actual). Reproduces the existing synthetic
  rebuild.
- `make study` renders Beats 1 and 2 into `study/friction_ledger.html`; a
  contract breach exits non-zero with one line naming the panel.
- `git diff --exit-code -- study/` proves the render matches the committed
  baseline (byte identity on rerun is pinned by 9a's test and inherited).
- `uv run pytest tests/test_beat2.py -q` proves what the byte-check cannot see:
  the band is counted, the drill is complete, no review text is present, the
  null metric is a labelled absence, the corpus statement is data-derived.

## Done-when

1. **Beat 2 renders, every value equal to its mart, every point tagged.** B2.1
   renders the Pending placeholder; B2.2 the theme share month by month from
   `theme_share_by_month`; B2.3 the peer ratings from `peer_ratings`; B2.4 the
   per-label precision and recall from `classifier_quality`; B2.5 the share by
   segment from `theme_share_by_segment`. No number is recomputed in the
   renderer; the rendered figures are pinned in `tests/pins.py`. *Evidence: rows
   1, 2.*
2. **The `unclassified` share is a counted series, shown and never hidden.** In
   B2.2 and B2.5 every cell whose mart holds an `unclassified` row renders that
   share as the one gray series named "not yet classified", outside the
   categorical palette and never coloured as a theme; the synthetic render is a
   no-key render, so the band it shows is the no-key band. *Evidence: rows 3,
   4.*
3. **Every theme bar opens to the complete list of reviews behind it, and the
   export carries no review text.** Each label's drill list holds one row per
   theme row in the marts (platform, review month, rating, public source link),
   in a total order; the export reads neither `title` nor `body`, and no run of
   four consecutive words from any review's title or body appears in the
   output — the 9a excerpt/paraphrase contract's enforcing test. *Evidence: rows
   5, 6, 7.*
4. **A metric whose denominator is zero renders a labelled absence, never a
   number, a zero or a blank.** B2.4's null precision/recall cells (0 predicted,
   0 actual) show "no held-out case" with the integer counts beside it; a null
   cell that declares no such absence is still refused by name (9a). *Evidence:
   row 8.*
5. **Beat 2's Measured panels say which corpus they count, from the data.** The
   corpus statement is derived from the classified rows' `run_id` (a value of
   the closed `ROWS` set): a fixture input renders "hand-written fixture
   reviews — a proof of the pipeline, not a finding"; more than one `run_id`
   or one outside the set refuses in one line. B2.5 states the traditional
   column waits; B2.3 states the placed points and labels each by platform;
   B2.2 states the review × theme grain (shares can sum past 1). *Evidence:
   rows 9, 10, 11.*

(5 items, ≤ 6.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_beat2.py::test_beat2_panels_render_each_value_equal_to_its_mart` (rendered figures equal the mart rows, pinned in `tests/pins.py`) |
| 1 | `tests/test_beat2.py::test_b2_1_renders_the_pending_placeholder_with_no_value`; `make study && git diff --exit-code -- study/` exits zero |
| 2 | `tests/test_beat2.py::test_every_unclassified_row_renders_as_the_gray_series` (every cell with an `unclassified` mart row has a gray point with that share; the series uses the neutral token, never a categorical slot) |
| 2 | `tests/test_beat2.py::test_a_theme_named_unclassified_cannot_take_a_categorical_slot` (the series builder refuses to place the band on a theme slot) |
| 3 | `tests/test_beat2.py::test_every_theme_bar_drills_to_its_complete_review_list` (rows per label == `theme_rows` summed over cells; each row carries platform, month, rating, link) |
| 3 | `tests/test_beat2.py::test_the_export_reads_neither_title_nor_body` (a recording connection sees no query naming either column) and `::test_no_review_text_run_appears_in_the_export` (for every synthetic review, no 4-word run of its title or body is in the HTML) |
| 3 | `tests/test_beat2.py::test_drill_rows_are_in_a_total_order_under_equal_keys` (two reviews equal on platform, month and rating render in the same order on every run) |
| 4 | `tests/test_beat2.py::test_a_zero_denominator_metric_renders_a_labelled_absence_not_a_number` and `::test_a_null_cell_with_no_declared_absence_is_still_refused_by_name` |
| 5 | `tests/test_beat2.py::test_the_corpus_statement_is_derived_from_run_id` (synthetic → the fixture sentence) and `::test_two_run_ids_or_one_outside_the_set_refuse_one_line` |
| 5 | `tests/test_beat2.py::test_b2_5_states_the_traditional_column_waits` and `::test_b2_2_states_the_review_times_theme_grain` |
| 5 | `tests/test_beat2.py::test_b2_3_states_placed_points_and_labels_each_point_by_platform` |

The 9a tests are inherited unchanged: byte identity on rerun, no CDN / asset /
timestamp, the one-tag and Pending-with-value refusals, locale independence.
`test_every_panel_renders_its_backing_row_id_and_source_link` now walks nine
panels.

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all cells of `theme_share_by_month` and `theme_share_by_segment` that hold an `unclassified` row, the rendered panel shows that share as the gray "not yet classified" series; it is never dropped, merged or coloured as a theme. | `tests/test_beat2.py::test_every_unclassified_row_renders_as_the_gray_series` — count the gray points against the mart's `unclassified` rows; and `::test_a_theme_named_unclassified_cannot_take_a_categorical_slot`. |
| For all Beat 2 shares, the plotted position is the share itself, never a cumulative stack (the grain is review × theme, so shares in a cell can sum past 1 and a stack would draw a number no mart holds). | `tests/test_beat2.py::test_b2_2_plots_each_share_against_the_axis_not_stacked` — a cell whose shares sum past 1 renders every point at `_y_of(share)`. |
| For all theme bars, the drill list is complete — one row per theme row in the mart — and in a total order, so equal sort keys render identically on every run. | `tests/test_beat2.py::test_every_theme_bar_drills_to_its_complete_review_list`; `::test_drill_rows_are_in_a_total_order_under_equal_keys`. |
| For all renders, no review title or body text is read or emitted: the export's queries name neither column and no four-word run of any review's text appears in the output. | `tests/test_beat2.py::test_the_export_reads_neither_title_nor_body` (a recording connection); `::test_no_review_text_run_appears_in_the_export`. |
| For all metric cells whose denominator is zero, the rendered cell is a labelled absence carrying its integer counts, never a value; a null cell with no declared absence is refused by name. | `tests/test_beat2.py::test_a_zero_denominator_metric_renders_a_labelled_absence_not_a_number`; `::test_a_null_cell_with_no_declared_absence_is_still_refused_by_name`. |
| For all Beat 2 Measured panels, the corpus statement is a function of the classified rows' `run_id`, which is exactly one value of the closed `ROWS` set; anything else refuses. | `tests/test_beat2.py::test_the_corpus_statement_is_derived_from_run_id`; `::test_two_run_ids_or_one_outside_the_set_refuse_one_line`. |
| For all rendered Beat 2 numbers, the value equals its mart row and carries exactly one tag (9a's contract, extended to the new panels and the table kind). | `tests/test_beat2.py::test_beat2_panels_render_each_value_equal_to_its_mart`; 9a's `test_a_panel_with_no_tag_or_two_tags_is_refused` over a table panel. |
| For all runs over the same DB, the output bytes are identical and match the committed baseline (9a, inherited). | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun`; the DONE command's `git diff --exit-code`. |

## Pinned decisions (do not re-litigate)

- **The static export's drill-through is a link list, never a text list.** Each
  theme bar opens (plain `<details>`) to one row per review: platform, review
  month, rating, and the public source link — no title, no body, no reviewer
  field, no platform review id. Review text is an audit trail for the developer,
  not a citation for the reader (brief Beat 2), and the export is the published
  artifact (brief §2.5: aggregated results and code, never the corpus); text
  excerpts belong to the developer-run, unpublished Metabase demonstration (9g).
  This is the mechanism that closes the "Health details arrive in review
  bodies" row. *Rejected: rendering the rule token that fired as the "one short
  marked phrase" — it needs the renderer to re-run the rules over review text
  (a classification outside `classify/`, and a text read); rendering a
  truncated body — a truncation is not a paraphrase and can still carry a
  condition.* Satisfies invariants 3 and 4.
- **The `unclassified` band is one fixed gray series outside the categorical
  palette.** It takes the palette's neutral token (`muted`), never a slot of
  `SERIES_LIGHT`/`SERIES_DARK`; the series builder refuses to place it on a
  slot; it renders whenever its mart row exists, named "not yet classified".
  *Rejected: a sixth categorical colour — the band is an absence of a decision,
  not a sixth theme, and the five-slot order is the CVD-safety mechanism.*
  Satisfies invariant 1.
- **Chart kinds: B2.2 one line per label (shares, `pct`, domain 0–1); B2.3 and
  B2.5 grouped bars; B2.4 a new `table` kind; the drill list a `<details>`
  block under B2.2/B2.5 sharing one list per label.** Lines, not a stacked
  area, because the grain sums past 1 (invariant 2). One list per label serves
  both B2.2 (rows show the month) and B2.5 (the totals) without duplicating
  rows. *Rejected: a stacked area (draws a cumulative number no mart holds); a
  script-driven drill (breaks self-containment).* Satisfies invariants 2, 3.
- **A declared absence is data on the Point, distinct from a null cell.**
  `Point` gains `absent: str` — the labelled reason ("no held-out case"); the
  B2.4 builder sets it exactly when `predicted == 0` or `actual == 0` and
  carries the integer counts; a `value is None` with no `absent` in a
  non-Pending panel stays a refusal by name (9a's `_require`). *Rejected:
  rendering 0.0 (a number the mart does not hold); a dash (a blank).* Satisfies
  invariant 5.
- **The corpus statement is read from `stg_classified_reviews.run_id`, a value
  of the closed `ROWS` set, never from the DB filename or a caller flag** (the
  `caller-sourced` LESSONS class). A fixture input (`synthetic`, `samples`)
  renders the "proof of the pipeline, not a finding" sentence on every Beat 2
  Measured panel; `captured` renders the corpus sentence; `none` renders the
  9a "no data yet" state. *Rejected: deriving it from `DEFAULT_DB`'s name — the
  render would then trust its caller.* Satisfies invariant 6.
- **Profile display names are one closed lookup, refused by name when a profile
  is unknown.** `_PROFILE_NAMES` gains the two traditional peers; a profile the
  lookup does not hold refuses in one line rather than rendering the raw key
  (9a round 2, CR#20 accepted as 9b scaffolding; the `unshaped-input` class).
  Satisfies the one-tag / value-equals-mart invariant's neighbour: nothing raw
  from a mart reaches the page unnamed.

(6 pinned decisions, ≤ 6.)

## Scope (files)

- `study/panels.py` — new: `beat1_panels` moved verbatim from `export.py`,
  `beat2_panels` and the Beat 2 mart readers, the drill rows reader, the corpus
  statement, `_PROFILE_NAMES` (the `architecture-fit` skill loaded by name
  before the module is created).
- `study/export.py` — the `table` kind and its renderer, the drill-list
  renderer, `Point.absent`, the gray series token, the page assembling Beats
  1–2; the contract (`check_panel`, `_require`, `_n`) unchanged in kind.
- `study/friction_ledger.html` — the committed baseline, re-rendered.
- `tests/test_beat2.py` — new: the Evidence rows above.
- `tests/test_export.py` — the panel-walk tests now cover nine panels; imports
  follow the move.
- `tests/pins.py` — the Beat 2 rendered figures.
- `SPEC.md` — Beat 2: one sentence per B2.2/B2.5 naming the drill list (what a
  row shows, that no review text is shown) and one under B2.4 naming the
  "no held-out case" state; no chart, row id or tag changes.
- `BACKING.md` — no tag flips (B2.2/B2.4/B2.5 are Measured, B2.3 Documented,
  B2.1 Pending); a render-home note only if `make check-backing` needs one.
- `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, this spec — per Record updates.
  (No `README.md`: Phase 9f's deliverable.)

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9b entry: the link-list drill (the closing
  mechanism for the health-details row; text excerpts → 9g, unpublished); the
  gray band outside the palette; lines-not-stack on the review × theme grain;
  the declared absence on `Point`; the run_id-derived corpus statement; the
  `study/panels.py` split; supersede nothing.
- [ ] `BACKLOG.md` — close *Health details arrive in review bodies* (struck +
  "DONE Phase 9b": the export reads neither text column, pinned by test);
  the *"vs traditional" half of B2.2/B2.5 is empty* row stays open (stated
  beside B2.5, as its trigger says); open a row for the corpus-statement
  wording once a `captured` render is first published (9f); update the count.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Repo map (`study/panels.py`, Beat 2 rendered,
  9c next); BACKLOG count; Commands unchanged (`make study` takes nothing new).
- [ ] BACKING.md — none unless `make check-backing` asks for a render-home note
  (Beat 2 rows keep their tags; the drill is a panel detail, not a new claim).
- [ ] `SPEC.md` — the three sentences under Scope (a panel detail, not a chart
  change: the row ids, tags and chart meanings are unchanged, so BACKING's row
  set is untouched).
- [ ] README — none (the repo has no README yet; Phase 9f).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make study` is unchanged: no variable, reads the synthetic DB and
tracked data, writes one file. Run twice: identical bytes. No credentials:
identical bytes. The one new input class the export reads is review-level
rows from the repo's own staging table — platform, month, rating, source link —
through the same `_require` boundary as 9a; the source link is rendered as a
live `href` only when it is `http(s)` (9a, round 1 SR#16), and neither text
column is ever selected.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `study` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` (unchanged) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `tests/`): the band as a series
  built from the mart's own `unclassified` row (never synthesised as
  `1 − sum`); no share recomputed; lines not stack; the drill list read through
  one query with a total `order by`; the `table` kind and `Point.absent`
  extending the contract without an `if` on a panel id; `_PROFILE_NAMES` as a
  closed lookup; the `beat1_panels` move verbatim; scope (Beats 3–5, the
  README, Metabase, `FORMULAS` `expression_text` are out).
- **security-reviewer** (triggered — the first surface listing reviews one by
  one): the export selects neither `title` nor `body` (pinned by the recording
  connection test); no reviewer field, no platform review id on the page; the
  source link `http(s)`-only; the committed HTML carries no brand token (`make
  check-docs` check 6 over `study/**/*.html`); no personal data can reach the
  page by construction, not by editing.
- **functionality-tester** (triggered): the DONE command; the drill count per
  label against the mart's `theme_rows`; the two negative refusals (a null cell
  with no declared absence; two `run_id` values); a render over `ROWS=none`
  (B2.2–B2.5 "no data yet", no crash); two renders identical; the 4-word-run
  scan over every synthetic review.
- **study-editor** (triggered — SPEC.md sentences, the rendered Beat 2 prose):
  the hypothesis stated as a test, not a verdict (B2.5 asserts no gap before
  its chart); the corpus sentence plain; "not yet classified" named by meaning;
  the placed-point note beside B2.3; banned words absent; no editorial
  sentence about one insurer.
- **coherence-auditor** at exit (mandatory): SPEC ↔ BACKING ↔ marts ↔ the
  rendered Beat 2 agree; the health-details row struck and the traditional row
  still open; CLAUDE.md's status names 9c next; the 9a Delivered paragraph's
  "9b lands the excerpt/paraphrase enforcing test" satisfied by name.
- Stack risk: `<details>`/`<summary>` renders without script in every browser
  the page targets and is byte-stable — verify in the first hour; the metric
  table's ASCII/entity escaping under the two-locale test; a drill list over a
  `captured` DB may run to thousands of rows — the page size is a 9f concern
  (the BACKLOG row above), not a reason to sample the trail here. Any surprise
  goes to DECISIONS → Gotchas; STOP before a workaround.

## Out of scope (deferred, recorded)

- Text excerpts in a drill-through — the developer-run Metabase demonstration
  (9g), never the published export (pinned decision 1; DECISIONS 9b).
- A traditional-mutuelle source — the open BACKLOG row; B2.5 states the wait.
- Curating B2.1's five paraphrased examples with links (flips B2.1 Pending →
  Documented) — a content task, BACKLOG.
- `FORMULAS` `expression_text` rendering — 9c (Beat 3, the first Modeled panels).
- Beats 3–5, the README + stranger test, Metabase — 9c–9g, each its own spec.
- The page-size and corpus-sentence wording of a first `captured` render — 9f
  (the BACKLOG row this phase opens).
- A `decided_by` column on `stg_classified_reviews` (rules vs model per row,
  which would let the drill say who decided) — a staging-schema change
  belonging to an earlier phase; BACKLOG candidate, not this diff.
