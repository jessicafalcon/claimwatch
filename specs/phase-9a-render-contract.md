# Phase 9a — The render contract and Beat 1 (PROPOSED)

Contract for the `phase-9a-render-contract` branch. Source: PROJECT_BRIEF.md §9
Phase 9 ("The study"), split permanent-artifact-first after the `/challenge`
round of 2026-09-07 (DECISIONS → Phase 9). Depends on Phase 8b merged.

**Status: PROPOSED — do not start until approved.** No new dependencies: the
export is one Python module over `duckdb` + stdlib `csv`/`json`/`html`, and
charts are hand-written inline SVG (no chart library, no CDN, no pandas — PLAN
§4.6, §4.9).
Challenged: 2026-09-07, round 1, spec 82e44990 — approve with amendments (all applied)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

## Why

The study has been a promise on paper: SPEC.md names five beats and every
chart, BACKING.md holds each number's query and source, but nothing renders
them for a reader. Phase 9 turns the marts into the study a stranger can read.
It is split because Phase 9 carries three delivery formats (Metabase, static
HTML, README) over ~19 panels — far past the ~6-item cap — and because the
`/challenge` round found that the static HTML export, not Metabase, is the
permanent, CI-checkable, deterministic artifact the other formats are built on
(DECISIONS decision 3; brief §4.4). So the export goes first.

This is not a fix PR: it introduces a new surface (`study/`), a new command
(`make study`) and the render contract every later render phase inherits. It
renders Beat 1 as the proving ground — Beat 1 mixes a Pending panel (B1.1, the
hero case, not yet curated) with Documented panels (B1.2–B1.4, the anchors),
so one beat exercises both the render and the Pending-no-number refusal. Beat 1
carries no Modeled panel, no counted `unclassified` series and no review-text
drill-through; those first appear in Beats 2–3, so this phase fixes the contract
for **Measured / Documented / Pending** panels and 9b/9c extend it (the counted
band, `FORMULAS` `expression_text`, text drill-through), each a tested decision
in its own phase.

## The central constraint

**The export invents no number and drifts from no number: a panel with no data
renders a labelled state and never a value, every shown number carries its one
tag and reproduces its mart, and `make study` writes byte-identical bytes on a
re-run and matches the committed baseline.** The marts, SPEC.md's beat
structure, BACKING.md's rows and tags, and `tests/pins.py` do not move while
`study/` is built around them.

## DONE command

```
make rebuild ROWS=synthetic && make study && git diff --exit-code -- study/
```

- `make rebuild ROWS=synthetic` builds the one byte-stable input,
  `data/friction_ledger.synthetic.duckdb`: Beat 1's Documented points are the
  frozen anchors only, so the render cannot drift with the weekly cron (which
  never touches the synthetic file). Reproduces the existing synthetic rebuild.
- `make study` renders `study/friction_ledger.html` from that DB and
  `models/cost_model.py::FORMULAS`; a contract breach (an untagged panel, a
  Pending panel carrying a value, two tags) exits non-zero with one line naming
  the panel id.
- `git diff --exit-code -- study/` proves the render matches the committed
  baseline; any drift fails. `make study` run twice writing identical bytes is
  pinned separately (`tests/test_export.py::test_make_study_is_byte_identical_on_rerun`).
  CI runs this same sequence (Record updates).

## Done-when

1. **The export is one deterministic, self-contained file, rendered from the
   frozen synthetic DB.** `study/export.py` renders `study/friction_ledger.html`
   — inline SVG, no CDN, no external asset, no render timestamp — from
   `data/friction_ledger.synthetic.duckdb` and `FORMULAS`; a re-run writes
   identical bytes, and the render matches the committed baseline. *Evidence:
   rows 1, 2, 3.*
2. **A panel with no data renders a labelled state, never a value or a blank:**
   a Pending panel renders a gray placeholder carrying no value, and a
   Documented/Measured panel whose mart is empty renders a distinct "no data
   yet" state — never an empty box, a dropped panel, or a fabricated number
   (SPEC.md "shows a gray not-yet state"; brief §2.4). *Evidence: rows 4, 5.*
3. **Every rendered number carries exactly one tag and equals its mart.** The
   renderer refuses a panel that resolves to no tag or more than one, and
   refuses a Pending panel whose data carries a value; each refusal is one line
   naming the panel id, exit non-zero; no number is recomputed in the renderer
   (PLAN §4.7; brief §2.4). *Evidence: rows 6, 7.*
4. **The render contract for Measured/Documented/Pending panels is fixed once,
   here.** The panel is data — `(id, backing_row, tag, kind, data)`; the chart
   types per Beat 1 panel are named; the palette is chosen from four directions
   at build start (dataviz loaded) and pinned in one place `export.py` reads;
   the drill-to-evidence link shape (panel → its BACKING row id and source) is
   fixed; SVG numbers are formatted byte-stably (fixed precision, sorted
   attributes, locale-independent). 9b/9c extend the contract for the counted
   `unclassified` series, `expression_text` and text drill-through. *Evidence:
   rows 8, 9.*
5. **Beat 1 renders, tags honest, bias stated.** B1.1 (Pending, gray
   placeholder), B1.2 rating trend, B1.3 channel gap and B1.4 stat row render
   from `rating_trend`, `channel_gap`, `platform_stats`; each Documented point
   and each Measured point carries its own tag; the sampling-bias note renders
   beside B1.2; B1.4 states beside the chart that the response-rate comparison
   waits for a second platform's figures (no fixture re-freeze). *Evidence: rows
   10, 11.*

(5 items, ≤ 6.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` (render twice, diff, no difference) |
| 1 | `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp` |
| 1 | `make study && git diff --exit-code -- study/` exits zero (render matches the committed baseline) |
| 2 | `tests/test_export.py::test_a_pending_panel_renders_a_gray_placeholder_with_no_value` |
| 2 | `tests/test_export.py::test_a_documented_panel_with_an_empty_mart_renders_no_data_yet` (render over `ROWS=none`) |
| 3 | `tests/test_export.py::test_a_pending_panel_with_a_value_is_refused_one_line_nonzero` |
| 3 | `tests/test_export.py::test_a_panel_with_no_tag_or_two_tags_is_refused` |
| 4 | `tests/test_export.py::test_every_panel_renders_its_backing_row_id_and_source_link` |
| 4 | `tests/test_export.py::test_svg_numbers_are_fixed_precision_and_locale_independent` (render under `LANG=C` and a UTF-8 locale, identical bytes) |
| 5 | `tests/test_export.py::test_beat1_panels_render_each_point_with_its_own_tag` (numbers pinned in `tests/pins.py`) |
| 5 | `tests/test_export.py::test_b1_2_renders_the_sampling_bias_note` and `::test_b1_4_states_the_response_comparison_waits` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all runs of `make study` over the same DB, the output bytes are identical, and they match the committed baseline. | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` — render twice, diff; and `make study && git diff --exit-code` over the frozen synthetic DB. |
| For all rendered SVG numbers, formatting is fixed-precision and locale-independent (no `repr`-style float, attributes sorted). | `tests/test_export.py::test_svg_numbers_are_fixed_precision_and_locale_independent` — render under `LANG=C` and a UTF-8 locale; expect identical bytes. |
| For all panels whose BACKING row is Pending, the rendered panel contains no data value. | `tests/test_export.py::test_a_pending_panel_with_a_value_is_refused_one_line_nonzero` — hand a Pending panel a value; expect a one-line refusal naming the panel id and a non-zero exit, not a rendered number. |
| For all Documented/Measured panels whose mart is empty, the panel renders a labelled "no data yet" state distinct from Pending, never a blank or a fabricated value. | `tests/test_export.py::test_a_documented_panel_with_an_empty_mart_renders_no_data_yet` — render over `ROWS=none`; expect the "no data yet" state for B1.2–B1.4, not a crash or a blank. |
| For all rendered numbers, exactly one evidence tag is attached. | `tests/test_export.py::test_a_panel_with_no_tag_or_two_tags_is_refused` — a panel resolving to zero or two tags refuses. |
| For all rendered numbers, the value equals the value in its mart (no re-computation in the renderer). | `tests/test_export.py::test_beat1_panels_render_each_point_with_its_own_tag` — the rendered figure equals the mart row, pinned in `tests/pins.py`. |
| For all self-containment: the output loads no CDN, no external asset, and carries no render timestamp. | `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp` — scan the HTML for `http(s)://`, `<script src`, `<link href`, and a date-shaped render stamp; expect none. |

(The invariant that review text a panel shows passes through the one
excerpt/paraphrase path is authored as a contract here but has no falsifying
scenario until text ships; its enforcing test lands in 9b — see pinned decision
below and Out of scope.)

## Pinned decisions (do not re-litigate)

- **The permanent artifact is the static HTML export, rendered first from the
  frozen synthetic DB; Metabase is a later, non-CI demonstration read on top of
  it.** `make study` reads `data/friction_ledger.synthetic.duckdb` (Beat 1's
  Documented points are frozen anchors only, byte-stable), never the `captured`
  DB the weekly cron grows. Alternatives rejected: Metabase-first (needs Docker,
  cannot end CI-green — brief §4.4, DECISIONS decision 3); rendering from
  `captured` (the baseline would drift with every weekly run). Satisfies
  invariant 1.
- **`study/export.py` renders from the marts and `FORMULAS`, never recomputing
  a number.** Alternative rejected: the renderer doing its own arithmetic — it
  would let the shown number drift from the mart. Satisfies the value-equals-
  mart invariant.
- **The render contract is data checked at render time, not editorial trust:** a
  panel is `(id, backing_row, tag, kind, data)`; the renderer refuses a
  Pending-with-value, a no-tag and a two-tag panel, and renders a distinct "no
  data yet" state for an empty non-Pending mart, all by construction.
  Alternative rejected: leaving tag / no-number to `study-editor` and
  `coherence-auditor` (they still read, but the guard is mechanical — the
  render-time-no-number BACKLOG row asked for the test). Satisfies the Pending,
  empty-mart and one-tag invariants.
- **Charts are hand-written inline SVG with byte-stable formatting** — fixed
  decimal precision (`format`, not `repr`), sorted attributes, locale-
  independent. Alternative rejected: a chart library (a CDN or build step,
  breaking self-containment and determinism). Satisfies invariants 1 and 2 (the
  formatting invariant). No new dependency.
- **The palette is chosen from four directions at build start (dataviz loaded)
  and pinned in one place `study/export.py` reads; chart types are named now.**
  Alternative rejected: naming a full palette in this spec before the dataviz
  pass — premature. Satisfies the CLAUDE.md charts rule.
- **The excerpt/paraphrase rule is authored here as a DECISIONS contract (the
  one render path for review text: paraphrase, at most one short marked phrase,
  always the public source — brief §2.5), but its enforcing test lands in 9b
  where review text first ships.** Alternative rejected: writing the enforcing
  test in 9a — Beat 1 ships no text (B1.1 Pending), so the test would have no
  falsifying scenario. The "Health details in review bodies" BACKLOG row stays
  open (re-scoped), not struck.

(6 pinned decisions, ≤ 6.)

## Scope (files)

- `study/export.py` — the renderer (new module; loads no key, no network).
- `study/__init__.py`, `study/__main__.py` — the package and its validating
  entry for `study`.
- `Makefile` — the `study` target (no variable; reads the synthetic DB; check
  in CI via `git diff --exit-code`).
- `study/friction_ledger.html` — the committed rendered bytes (the baseline).
- `.github/workflows/ci.yml` — add `make study` + the `git diff --exit-code`
  check to the offline run (after the synthetic rebuild it already does).
- `tests/test_export.py` — the contract and Beat 1 pins.
- `tests/pins.py` — the Beat 1 rendered numbers.
- `scripts/check_docs.py` — only if `study/` needs a new allowed path (its
  `STUDY_GLOBS` already include `study/**/*.html`; likely no change).
- `SPEC.md` — only the Beat 1 "Under the hood" note if it must name the render
  path; no chart or beat changes (a beat change is a design STOP).
- `BACKING.md` — no tag flips (Beat 1 rows are already Documented); a render-home
  note only if needed.
- `README.md` — the `make study` command line and one sentence on the export.
- `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, this spec — per Record updates.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9 entry: the permanent-artifact-first split and its
  sub-phase sequence; the render contract; the frozen-synthetic render input;
  the SVG byte-formatting rule; the palette direction chosen; the
  excerpt/paraphrase contract (test deferred to 9b); supersede nothing.
- [ ] `BACKLOG.md` — close the render-time-no-number row (*"A Pending row has no
  number in SPEC" is not checked mechanically*, struck + "DONE Phase 9a") and
  the *§6 response figures are not seeded* row (stated-waits); the *Health
  details arrive in review bodies* row stays **open**, re-scoped to 9b; update
  the BACKLOG count.
- [ ] LESSONS.md — none until a review round reports a correctness finding; then
  backtick it and the fix commit writes the row.
- [ ] `CLAUDE.md` — Current status; Commands (`make study`); Repo map (`study/`
  first render); the CI list (add `make study` check); allowlist (no change — no
  new dependency); BACKLOG count.
- [ ] `BACKING.md` — no tag change; a render-home note only if needed.
- [ ] `SPEC.md` — only if the Beat 1 "Under the hood" note must name the render.
- [ ] `README.md` — `make study` and one sentence on the static export.
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. `make study` runs `uv run python -m study export` with no variable:
it reads `data/friction_ledger.synthetic.duckdb` (a table this repo built) and
the tracked `FORMULAS`, writes one file under `study/`, and CI asserts no drift
with `git diff --exit-code`. Run twice: identical bytes. No credentials:
identical bytes (nothing on the path reads a key — the export is a read over
marts already built, no classify step, no fetch). No new input the repo does not
own: the marts are this repo's own tables and `FORMULAS` is tracked data.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `study` | no variable | no variable | no variable | no variable | not gated (no delete, no network, no paid call) | `tests/test_export.py::test_make_study_is_byte_identical_on_rerun` (the target exists, takes nothing, writes the same bytes twice) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/*.py`, `Makefile`, `tests/`): the render
  contract as data, not `if` chains on panel titles; no number recomputed in the
  renderer (every figure read from a mart or `FORMULAS`); the Pending-with-value
  / no-tag / two-tag refusals and the empty-mart "no data yet" state by
  construction; the SVG byte-formatting rule (fixed precision, sorted attrs,
  locale-independent); no literal Beat 1 number in `export.py`; inline SVG with
  no CDN, no external asset, no timestamp; scope (Beat 1 + the Measured/
  Documented/Pending contract only — a Beat 2–5 panel, the counted `unclassified`
  series, a Metabase script or the README in this diff is out of scope).
- **security-reviewer** (triggered — `study/__main__.py` is a CLI entry,
  `.github/workflows/ci.yml` is on the Sensitive list, and the render is the
  first surface that could emit review text): the export reads marts and writes
  one file, no network, no key, no shell; the excerpt/paraphrase path as the one
  route for review text (contract now, test in 9b); no personal data in the
  rendered HTML; the committed `friction_ledger.html` carries no brand token —
  pinned by `make check-docs` check 6 (its `STUDY_GLOBS` and neutrality suffixes
  already scan `study/**/*.html`), so a Documented point opens to its platform
  root and PROJECT_BRIEF §6, never a profile page (D1, BACKING note).
- **functionality-tester** (triggered): the DONE command; the negative tests (a
  Pending panel handed a value refuses; a no-tag panel refuses); render over a
  fresh `ROWS=none` rebuild — B1.2–B1.4 show the "no data yet" state, not a
  crash or a blank; the two-locale byte-identity check.
- **study-editor** (triggered — `README.md`, `SPEC.md` note, the rendered study
  prose): two-layer voice on the Beat 1 panel text; neutrality (no editorial
  sentence about one insurer); the sampling-bias note beside B1.2; banned words
  absent.
- **coherence-auditor** at exit (mandatory, phase exit): SPEC ↔ BACKING ↔ marts
  ↔ the rendered study agree for Beat 1; the sub-phase sequence recorded; the
  render-time-no-number and §6-response-figures BACKLOG rows struck, the Health-
  details row still open; no stale "Phase 9 not started" sentence.
- Stack risk: byte-stable hand-written SVG is the first-hour risk — verify a
  legible, theme-safe axis/label/legend for a line chart (B1.2), a grouped
  comparison (B1.3) and a stat row (B1.4), and that two renders (and two
  locales) produce identical bytes, before rendering all of Beat 1; the dataviz
  skill is loaded for every chart. Any surprise goes to DECISIONS → Gotchas;
  STOP before a workaround.

## Out of scope (deferred, recorded)

- The counted `unclassified` series as a first-class gray series — Phase 9b
  (Beat 2, where it is a real counted number that can be falsified).
- The excerpt/paraphrase enforcing test — Phase 9b, where review text first
  ships (the rule is a DECISIONS contract in 9a; the *Health details arrive in
  review bodies* BACKLOG row stays open, re-scoped).
- `FORMULAS` `expression_text` rendering — Phase 9c (Beat 3, the first Modeled
  panels).
- Beats 2–5 HTML render — later render phases (9b–9e), each its own spec.
- The README and the stranger acceptance test — Phase 9f.
- The Metabase demonstration (HTTP-API-from-YAML, idempotent, non-CI) — 9g.
- The claims sample-mean slider (*The claim-cost mean is the lognormal mean, not
  the fixture's arithmetic mean* BACKLOG row) — its own model phase before Beat 3
  renders.
- data.ameli practitioner fees (*data.ameli practitioner-fee distributions are
  not ingested* BACKLOG row) — its own opendata phase, non-blocking; the study
  states the DAMIR-only basis until then.
- B3.3 headline-figure mart re-point, the `guardrail_sim` SQL-aggregate test, the
  `pipeline_row_counts` fold — their beat's render phase (9c, 9d, 9e).
- Curating B1.1's hero case with its public link (flips B1.1 Pending →
  Documented) — a content task recorded in BACKLOG, not this phase; 9a renders
  B1.1 as the Pending placeholder.
