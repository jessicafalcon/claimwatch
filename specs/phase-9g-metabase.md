# Phase 9g — the Metabase demonstration: the review-level drill

Contract for the `phase-9g-metabase` branch. Source: PROJECT_BRIEF.md §4.4 (the
"Full (demonstration)" run mode) and §9 Phase 9 ("The study"), sub-phase 9g of
the permanent-artifact-first split (DECISIONS → Phase 9a). It is the last Phase 9
sub-phase. Depends on Phase 9f merged (PR #29, 2026-09-10).

**Status: APPROVED 2026-09-10 — DELIVERED 2026-09-11, PR open.** No new Python dependency:
the applier is stdlib `urllib` (the `opendata/fetch.py` precedent), the
marts→engine export is stdlib `sqlite3`, the config is `pyyaml` (Phase 2), the
drill view is `duckdb` + SQL. Metabase runs via Docker, which CLAUDE.md →
Conventions pre-approves ("Airflow and Metabase via Docker only"); it reads the
marts through its **built-in SQLite driver** — no third-party driver JAR (see
pinned decisions). The phase is **non-CI**: CI is offline (no Docker), so the
live run cannot end CI-green — the phase splits into an offline, CI-checkable
core (the applier's request bodies, the drill view's + SQLite export's column
allowlist) and a developer-run demonstration (the live Metabase run and its
synthetic-only screenshots).
Challenged: 2026-09-10, round 2, spec 9cba5dd4 — approve with amendments (1 BLOCKER, 3 should-fix, 1 question; all applied; re-hashed at exit — the SQLite path refined to data/metabase/ by review round 1 #3, invariants unchanged)
Challenged: 2026-09-10, round 1, spec 76269923 — rework (2 BLOCKER, 4 should-fix; all applied)

## Why

The brief promises three delivery surfaces: the permanent HTML export (Phases
9a–9e), the README (9f), and the Metabase dashboard where a reader drills a theme
bar down toward the reviews behind it (brief §90, §4.4 "Full (demonstration)").
The first two shipped. This is the third, and it is the one place the study
becomes clickable rather than printed.

DECISIONS → Phase 9b deferred the **review-level drill** to here explicitly ("the
review-level drill is the Metabase demonstration (9g) over the reader's own
rebuild"). This phase delivers it: a theme bar opens to the individual review
rows counted under it, over the reader's own captured rebuild.

**A recorded deviation from brief §90 (do not read this as fully met).** §90 as
written asks the drill to reach "the underlying review *excerpts*." That is
unattainable under two contracts this repo already keeps: **no declared source
yields a per-review public address** (DECISIONS → D1 — every parser stores the
brand-carrying page address, not a per-review URL), so a per-review row can be
neither publicly cited nor published as text; and **Neutrality/personal data**
forbids publishing a review's own `body` (brief §5's example bodies name medical
conditions). So the drill's audit trail is **the counted rows plus, per theme, a
sourced paraphrase** — not per-review excerpts. This is a brief-reconciliation
entry (DECISIONS → Phase 9g), not a silent repair: §90's literal "excerpts" is
recorded as unshippable. The row *"A per-review drill needs a per-review public
address"* therefore stays **open, re-deferred**: 9g ships the review-level
*view* over the reader's own rebuild, but its surviving trigger — a source that
yields a per-review public address, which external per-review citation would
need — is unmet, and the DECISIONS §90 entry carries that trigger forward.

It also finally lands **B2.1** (Pending since Phase 2): the five-theme taxonomy
with its Documented paraphrased examples, curated with public sources, is the
text a drilled theme shows.

This closes the tooltip-only trail (*"The B2.2/B2.5 trail is tooltip-only"* —
Metabase shows the counts as visible cells, not a hover title) and the
live-exploration debt (*"Live sliders need a script the permanent page does not
carry"* — Metabase's own filters and drill are the exploration a browser slider
would have been). It does **not** fold in the classify-path idempotency target
(*"`make idempotency-check` skips the classify step…"*): that is a
general-pipeline change whose recorded home is its own `fix/` PR (see
Out of scope), kept off this study-surface diff.

This is not a fix PR: it adds a delivery surface (a Docker stack, a stdlib
marts→SQLite export, and an HTTP-API applier), a new Documented evidence surface
(B2.1), and a drill view mart.

## The central constraint

**The drill exposes no raw review text and no per-review brand address, and every
text a theme shows is a sourced theme-level paraphrase — the audit trail is the
counts, not per-review excerpts, which the D1/Neutrality contracts forbid.**
Concretely: the drill view's per-review projection is a fixed non-text allowlist
that survives the join to the text-bearing `stg_reviews`; the SQLite export
carries the same allowlist and no more; the only text is
`study/paraphrases.yaml`, never a review `body`, never a second model-call site.
The five contracts, the marts (`sql/`), the classifier (`classify/`), the
permanent HTML export (`study/export.py`, `panels.py`, `model.py`, `text.py`, and
the committed `friction_ledger.html` — byte-unchanged) and every existing pin in
`tests/pins.py` do not move. No `now()`/`current_date` enters the data path; the
drill orders by the review's own date.

## DONE command

```
make rebuild ROWS=synthetic && uv run pytest tests/test_metabase_apply.py tests/test_review_drill.py -q && uv run python -m study.metabase apply --dry-run
```

- `make rebuild ROWS=synthetic` builds the frozen input and the `review_drill`
  view over it; the view carries only the allowlisted columns. The
  `ROWS=synthetic` rows are hand-written fake reviews, so any count Metabase
  shows over them is fixture data, not a study finding (the marts carry the
  input's real counts — the HTML render's corpus gate does not live in the mart,
  so the demonstration earns its honesty from the synthetic input and a caption,
  never a gate; see done-when 5). Reproduces the synthetic rebuild.
- `uv run pytest tests/test_metabase_apply.py tests/test_review_drill.py -q`
  proves the offline core the live run cannot: the applier builds pinned request
  bodies from the YAML and, given a fake client whose state already holds the
  objects, issues update-not-create (idempotent upsert); the `review_drill`
  view's projected columns are exactly the non-text allowlist even across the
  `stg_reviews` join (`select *` fails by name), the stdlib `sqlite3` export
  carries the same columns and no `body`/`title`/`source_url`, a synthetic
  review's distinctive `body` appears in no drill column, and a drilled theme's
  paraphrase resolves to a `study/paraphrases.yaml` entry with a public source.
- `uv run python -m study.metabase apply --dry-run` builds every request body
  from the committed YAML and the exported SQLite schema and prints them, byte-
  stable, touching no network and needing no credentials — the CI-safe half.

## Done-when

1. **Metabase is provisioned from committed config over a SQLite export,
   idempotently.** `make rebuild` (then a stdlib `sqlite3` export step) writes the
   drill and aggregate marts to a gitignored `data/metabase/metabase.sqlite`; a committed
   `study/metabase/docker-compose.yml` brings up Metabase reading that file via
   its **built-in SQLite driver**; `study.metabase apply` reads
   `study/metabase/config.yaml` and upserts the collection, questions and
   dashboard by stable name over the HTTP API (stdlib `urllib`), so applying twice
   creates no duplicate object. `--dry-run` builds the request bodies offline.
   *Evidence: rows 1, 2.*
2. **The drill exposes only non-text, non-brand columns, across the join and into
   SQLite.** `review_drill` joins `stg_classified_reviews` (its four columns
   `source, external_id, theme, run_id`) to `stg_reviews` (which also carries
   `body`/`title`) on `(source, external_id)`, and projects a fixed allowlist —
   `review_id` (the computed `source || ':' || external_id`, mirroring
   `classify/labels.py::review_id`), `theme`, `rating`, `review_date`, `segment`,
   `source` (the platform slug, never `source_url`). The allowlist is checked on
   the joined cursor's description so `select *` or a stray `body`/`title`/
   `source_url` fails by name, and the SQLite export copies only those columns.
   `rating` (`decimal(2,1)`) is written to SQLite as a rounded fixed-form string
   (one decimal), so the DuckDB decimal → SQLite (untyped, no decimal) trip is
   exact — `4.3` never surfaces as `4.2999…`; the export orders rows
   deterministically, so it is byte-identical on a rerun. *Evidence: rows 3, 4,
   5.*
3. **A drilled theme's only text is a curated, sourced paraphrase; B2.1 becomes
   Documented.** `study/paraphrases.yaml` carries one paraphrased example per
   theme (five), each with the public source it paraphrases (brief §6); the drill
   shows this theme-level text, never a review `body`; a review with no theme
   paraphrase shows its counted rows and no text. B2.1 moves Pending → Documented.
   *Evidence: rows 6, 7.*
4. **The no-key run stays green and the applier needs no Anthropic key.** With
   `ANTHROPIC_API_KEY` unset, the rebuild, the classify step, the drill view, the
   SQLite export and `apply --dry-run` all succeed; ambiguous reviews are
   `unclassified` and appear in the drill under the "not yet classified" band; the
   applier's dry-run bytes are identical to the keyed run's. *Evidence: rows 8, 9.*
5. **The demonstration is committed, captioned as fixture data, and safe by
   construction.** `study/metabase/DEMONSTRATION.md` walks a theme-bar → review
   drill with **synthetic-only** screenshots under `study/metabase/screenshots/`
   (captured over `ROWS=synthetic`, so every review shown is a hand-written fake);
   the walkthrough and every screenshot caption the view as *synthetic fixture
   data — not a study finding*, so no fake share reads as a result. Two things are
   safe by construction, not by a gate: only fake reviews exist under
   `ROWS=synthetic`, and the drill view (done-when 2, 3) carries no
   `body`/`title`/`source_url` column, so no screenshot can show raw review text
   or a brand address. study-editor confirms the caption on `DEMONSTRATION.md` and
   the screenshots; security-reviewer confirms no leaked text/brand. *Evidence:
   row 10.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_metabase_apply.py::test_apply_twice_over_existing_state_issues_no_create` |
| 1 | `tests/test_metabase_apply.py::test_dry_run_builds_pinned_request_bodies_without_network` |
| 2 | `tests/test_review_drill.py::test_drill_projects_only_the_non_text_allowlist_across_the_join` |
| 2 | `tests/test_review_drill.py::test_sqlite_export_carries_only_the_allowlist_no_body_title_source_url` |
| 2 | `tests/test_review_drill.py::test_sqlite_export_rating_is_exact_and_row_order_is_stable` |
| 2 | `tests/test_review_drill.py::test_review_id_expression_matches_labels_review_id` |
| 3 | `tests/test_review_drill.py::test_drilled_theme_paraphrase_resolves_to_a_sourced_entry` |
| 3 | `tests/test_review_drill.py::test_a_review_body_never_appears_in_any_drill_column` |
| 4 | `tests/test_review_drill.py::test_drill_builds_and_bands_unclassified_with_no_key` |
| 4 | `tests/test_metabase_apply.py::test_dry_run_is_identical_with_key_unset` |
| 5 | `tests/test_review_drill.py::test_demonstration_doc_and_synthetic_screenshots_exist_and_links_resolve` (study-editor + security-reviewer read the screenshots) |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all rows the drill exposes — in the DuckDB view and in the SQLite export — the projected column set is a fixed allowlist containing no raw-text column (`body`, `title`) and no per-review brand address (`source_url`), even though the join reaches `stg_reviews` which carries them. | `tests/test_review_drill.py::test_drill_projects_only_the_non_text_allowlist_across_the_join`; `::test_sqlite_export_carries_only_the_allowlist_no_body_title_source_url` — the joined cursor's / SQLite table's columns equal the allowlist; a query naming `body`/`title`/`source_url` fails by name. |
| The marts Metabase reads carry the input's real counts — only the HTML render blanks a fixture count — so the demonstration earns its honesty from the synthetic input (only fake reviews exist under `ROWS=synthetic`) and a caption, never from a corpus gate it does not inherit; every committed screenshot and `DEMONSTRATION.md` carries the *synthetic fixture data — not a study finding* caption. | `tests/test_review_drill.py::test_demonstration_doc_and_synthetic_screenshots_exist_and_links_resolve` (the doc carries the caption; study-editor confirms it on the screenshots) — an uncaptioned demonstration artifact fails. |
| For all rows, the SQLite export preserves `rating` exactly (a rounded one-decimal fixed form, not a float) and orders rows deterministically, so the exported file is byte-identical on a rerun. | `tests/test_review_drill.py::test_sqlite_export_rating_is_exact_and_row_order_is_stable` — a `4.3` review reads back `4.3`, and two exports of one DB are identical. |
| For all reviews in the drill, any text shown comes from `study/paraphrases.yaml`, never from the review's own `body`; a review with no theme paraphrase shows no text. | `tests/test_review_drill.py::test_a_review_body_never_appears_in_any_drill_column` — a synthetic review with a distinctive body renders no text and the body string appears in no drill column. |
| For all rows, the drill's `review_id` equals `classify/labels.py::review_id(source, external_id)` — one definition of identity, not two. | `tests/test_review_drill.py::test_review_id_expression_matches_labels_review_id` — for every staged row the SQL expression and the Python function return the same string. |
| For all Metabase objects the applier provisions, applying the same config twice leaves the server unchanged — it upserts by stable name, never creating a duplicate. | `tests/test_metabase_apply.py::test_apply_twice_over_existing_state_issues_no_create` — a fake client pre-loaded with the objects records every request; the second apply issues only updates, no create. |
| With `ANTHROPIC_API_KEY` unset, the rebuild, classify, drill view, SQLite export and `apply --dry-run` all succeed and the dry-run bytes are unchanged; ambiguous reviews are `unclassified`. | `tests/test_metabase_apply.py::test_dry_run_is_identical_with_key_unset`; `tests/test_review_drill.py::test_drill_builds_and_bands_unclassified_with_no_key`. |
| For all values the applier reads from the SQLite schema and the config, the request bodies it builds are the same on a rerun (no clock, no random, sorted) — the dry-run is byte-stable. | `tests/test_metabase_apply.py::test_dry_run_builds_pinned_request_bodies_without_network` — two dry-runs produce identical bytes pinned in `tests/pins.py`. |

## Pinned decisions (do not re-litigate)

- **The drill's audit trail is counted rows + a sourced theme paraphrase, not
  per-review excerpts — an explicit, recorded deviation from brief §90.** §90's
  "underlying review excerpts" is unattainable: D1 yields no per-review public
  address and Neutrality forbids publishing a `body`. Recorded as a
  brief-reconciliation entry (DECISIONS → Phase 9g), which carries forward the
  surviving reopen trigger — *revisit if a source yields a per-review public
  address*. The row *"A per-review drill needs a per-review public address"*
  stays **open, re-deferred**: 9g ships the review-level *view*, but external
  per-review citation still needs an address no source yields. Satisfies the
  central constraint. *Rejected: rendering a truncated
  `body` snippet as "one short marked phrase" — raw text carries a name/condition
  and has no per-review public source (D1); a machine-generated paraphrase — the
  model is called from exactly one site (`classify/llm.py`), never for prose.*
- **The drill's per-review projection is a non-text allowlist that holds across
  the `stg_reviews` join; its only text is a curated paraphrase.** The join to
  `stg_reviews` is required (`rating`/`review_date`/`segment` live there, one
  column from `body`/`title`), so the allowlist is enforced on the *joined*
  cursor's description, not the source table's; `review_id` is the computed
  `source || ':' || external_id` (ANSI `||`, portable), mirroring
  `classify/labels.py::review_id`. Satisfies invariants 1, 2, 3. *Rejected:
  claiming the view over `stg_classified_reviews` needs no join — it lacks the
  three columns; a `review_id` column in staging — Phase 5a decided the id is a
  Python join, no earlier SQL changes.*
- **Metabase reads a stdlib-`sqlite3` export of the marts through its built-in
  SQLite driver — no DuckDB community driver.** SQLite is an official Metabase
  driver (verified, [metabase.com/data-sources]); DuckDB is community-only (a
  third-party JAR — the "ask before ANY package" instinct), and its auto-download
  of the DuckDB SQLite extension would break the offline rebuild. The export is
  Python stdlib, offline and deterministic — `rating` is written as a rounded
  one-decimal string (SQLite has no decimal type), rows in a fixed order, so the
  file is byte-identical on a rerun. The stack stays laptop-portable, no account
  (§4.4 Portable). Satisfies done-when 1 and the rating-fidelity invariant.
  *Rejected: the DuckDB community
  JAR (third-party runtime code, version-coupled to Metabase); a Postgres
  container + load (a second server for a laptop demo); Snowflake full-mode
  (Phase 10, needs an account).*
- **The applier is a developer-run stdlib `urllib` module reading Metabase
  credentials from the environment (the developer exports `.env`), idempotent by upsert-by-name; it is not a `make`
  target with a variable.** Keeping it `python -m study.metabase apply` avoids the
  `make` variable/`confirm` surface; localhost provisioning is neither paid nor
  destructive; `--dry-run` is the offline half. Satisfies invariants 4 and 6.
  *Rejected: a paid/hosted Metabase — the demonstration is a laptop, no accounts
  (§4.4); a hand-built dashboard with no config — not reproducible, no idempotency
  to test (§4.4 "keep configs").*
- **B2.1 lands here as Documented, curated in `study/paraphrases.yaml` with
  public sources.** SPEC B2.1 already anticipates it ("Documented — Pending until
  the examples are curated with links"); this realizes the anticipated row.
  Satisfies done-when 3. *Rejected: leaving B2.1 Pending with a text-free drill —
  the drill's whole point is showing the theme's meaning; keeping the paraphrase
  uncited — brief §2.5 requires the public source.*
- **The done-when splits into an offline core (DONE command) and a developer-run
  demonstration with synthetic-only screenshots.** CI has no Docker, so the live
  run cannot be a suite assertion; the request bodies, the drill/SQLite columns
  and the no-key path are what a config-as-data applier can be pinned on.
  Screenshots are captured over `ROWS=synthetic` so no real review can appear in
  the tracked tree. Satisfies the Evidence table and done-when 5. *Rejected:
  screenshots over the developer's captured (real) rebuild — a human-only gate
  over personal data in the tree; asserting the live run in CI — no Docker.*

## Scope (files)

- `study/metabase/__init__.py`, `study/metabase/__main__.py` (the `apply` entry,
  `--dry-run`), `study/metabase/apply.py` (YAML → HTTP-API request bodies; the
  upsert; the injected HTTP-client seam), `study/metabase/export.py` (marts →
  `data/metabase/metabase.sqlite` via stdlib `sqlite3`, allowlisted columns only),
  `study/metabase/config.yaml` (the SQLite connection, questions and dashboard as
  data), `study/metabase/docker-compose.yml`, `study/metabase/DEMONSTRATION.md`,
  `study/metabase/screenshots/` (committed synthetic-only PNGs).
- `study/paraphrases.yaml` (B2.1: five themes, each a paraphrase + public
  source) — tracked study content, not a fixture.
- `sql/marts/review_drill.sql` (the drill view: DDL naming the grain — one row
  per review × theme — the explicit `stg_reviews` join, the non-text allowlist
  columns, the provenance columns and the BACKING rows it feeds; no clock).
- `tests/test_metabase_apply.py`, `tests/test_review_drill.py`, `tests/pins.py`
  (the pinned request bodies and drill fragments).
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `BACKING.md`, `SPEC.md`,
  `README.md`, this spec.
- `.gitignore` (if `data/metabase/metabase.sqlite` is not already covered by `data/`).

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9g entry: the §90 brief-reconciliation deviation
  (excerpts unshippable under D1/Neutrality; audit trail = counts + theme
  paraphrase; carries the *per-review public address* reopen trigger forward);
  the honesty-from-synthetic-input-and-caption note (the corpus gate is a
  render mechanism, absent from the marts Metabase reads); the drill allowlist
  across the join; the rating-as-rounded-string SQLite export; the SQLite-over-DuckDB-JAR
  engine choice (Gotchas); the applier shape; B2.1's realization; the
  offline/synthetic-screenshot split; challenge dispositions (rounds 1–2)
- [ ] `BACKLOG.md` (rows cited by title, never number) — closed, struck +
  "DONE Phase 9g": *"The B2.2/B2.5 trail is tooltip-only"* (visible counts) and
  *"Live sliders need a script the permanent page does not carry"* (live
  exploration). *"A per-review drill needs a per-review public address"* stays
  **open, re-deferred** (the review-level view shipped; the per-review-address
  trigger survives). *"`make idempotency-check` skips the classify step…"*
  re-pointed to a `fix/idempotency-classify` PR (not 9g). A new row opened for
  the HTML export of B2.1's paraphrases (out of scope here)
- [ ] `LESSONS.md` — review round 1 extended `unshaped-input` (reply id +
  `METABASE_URL` shape) and `traceback-at-boundary` (missing mart, live
  `URLError`) with the 9g occurrences
- [ ] `specs/phase-7a-findings-marts.md` — the `build_theme_share_marts` →
  `build_post_classify_marts` rename note (review round 1, #16)
- [ ] `PROJECT_BRIEF.md` — §90 reconciliation note (exit audit): the drill's trail
  is counted rows + a sourced paraphrase, not literal review excerpts (D1/Neutrality)
- [ ] `CLAUDE.md` — Current status; Commands (`study.metabase apply` /
  `export`); Repo map (`study/metabase/`, `study/paraphrases.yaml`,
  `sql/marts/review_drill.sql`); Teaching rule (Metabase drill-through, the
  SQLite export and built-in driver); BACKLOG count
- [ ] `BACKING.md` — B2.1 Pending → Documented (mart/source cells filled)
- [ ] `SPEC.md` — B2.1's parenthetical (Documented, curated in
  `study/paraphrases.yaml`); the B2.2/B2.5 tooltip-trail sentence noting the
  visible-count drill lives in Metabase (a described-behaviour note, not a chart
  change — no HTML change)
- [ ] `README.md` — the Metabase demonstration named as the third surface's live
  form; the `make rebuild ROWS=captured` → SQLite export → Metabase reader path
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

The phase adds **no** `make` target that takes a variable, deletes, calls a paid
API, or touches the public network. It adds one developer-run network module
(`study.metabase apply`, HTTP to **localhost** Metabase with credentials from the environment, the
exported `.env`) and one offline stdlib export (`study.metabase export`, no network, no
credentials).

| Target/module | empty | `../x` | `"; ` | env-exported | credentials | Pinned by |
|---|---|---|---|---|---|---|
| `study.metabase apply` (module, not a `make` target) | missing `METABASE_URL`/user/password → refuses naming the variable, never the value; `--dry-run` needs none | n/a — no path is built from a variable | n/a — no shell; `urllib` builds the request, no subprocess | reads `.env` only, never Actions | credentials in `.env` only; refusals print names; run twice = idempotent upsert (no duplicate object, no paid call, localhost only) | `tests/test_metabase_apply.py::test_apply_refuses_missing_credentials_by_name` |
| `study.metabase export` (offline) | writes `data/metabase/metabase.sqlite` from the running marts; empty marts → an empty allowlisted table, never a body column | n/a — the path is a fixed constant, not a variable | n/a — no shell | needs none | none — offline | `tests/test_review_drill.py::test_sqlite_export_carries_only_the_allowlist_no_body_title_source_url` |

Settled shape: one Python process validates, derives the request bodies / the
export, and (for a live apply) reads `.env` then acts; `--dry-run` and `export`
build with no network and no credentials. No public network, no paid API, nothing
deleted.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/**/*.py`, `sql/marts/**`, `tests/`): the
  drill view's allowlist across the join, the SQLite export's column set and
  rating fidelity, the applier's idempotent upsert, config-as-data, the no-key
  path, scope.
- **security-reviewer** (mandatory — a network module with credentials,
  `study/metabase/`): credential handling (`.env` only, refusals name not value),
  the HTTP client (no shell, `urllib` request built from data), the SQLite export
  cannot carry `body`/`title`/`source_url`, and it **reads the committed
  synthetic screenshots** for any leaked text/brand.
- **functionality-tester** (triggered): the DONE command, the negative tests
  (missing credentials, `select *` across the join, a body string in a drill
  column, double-apply), the no-key run.
- **study-editor** (triggered — `SPEC.md`, `BACKING.md`, `README.md`, the
  DEMONSTRATION walkthrough, `study/paraphrases.yaml`): the paraphrases are
  paraphrase-not-quote, sourced, no personal data, no insurer named as target;
  the walkthrough's two-layer voice; **reads the synthetic screenshots**.
- **coherence-auditor** at exit: SPEC B2.1 ↔ BACKING B2.1 ↔ `study/paraphrases.yaml`
  ↔ the drill view ↔ README align; the "review-level drill is 9g" forward
  references now resolve; the §90 deviation is recorded, not silent; the Phase 9
  sub-phase list is complete.
- **Stack risk (verify in the first hour; STOP and report before any workaround —
  Workflow rules → Stack surprises; log under DECISIONS → Gotchas):**
  1. **Metabase's built-in SQLite driver reads a mounted file.** SQLite is
     official (verified in the record), but confirm the container reads the
     mounted `data/metabase/metabase.sqlite` and one card loads before pinning the config.
     Low risk (file-based native driver); the fallback if it fails is a Postgres
     container + load, scoped then as an amendment.
  2. **Metabase HTTP API idempotency.** The API creates on POST; the applier must
     GET-then-PUT (upsert by name in a named collection). Verify the session-auth
     and card/dashboard endpoints against the running version before pinning the
     request bodies.

## Out of scope (deferred, recorded)

- *"`make idempotency-check` skips the classify step, so the theme marts are not
  machine-checked by the target"*: a separate `fix/idempotency-classify` PR off
  `main`, its own
  commit and review; the property is already covered by
  `tests/test_theme_share.py::test_rebuild_twice_stable` and
  `tests/test_beat5.py::test_pipeline_row_counts_stable_across_reclassify` (slow
  tests CI runs), so this is a target-convenience fix, not a coverage hole. Not in
  this diff (one phase, one diff).
- The HTML export rendering B2.1's paraphrases (a Beat-2 panel) — a new BACKLOG
  row; the export's B2.1 stays Pending-in-HTML. This phase ships B2.1's text in
  Metabase only.
- Snowflake + Airflow full-mode wiring — Phase 10 (the DAG); §4.4 full mode is
  named, not built here.
- The claims sample-mean slider and data.ameli practitioner fees — their own
  pulled-out data phases (DECISIONS → Phase 9a).
- *"B4.3's four bar labels are a latent overflow"* — a Beat-4 follow-on,
  untouched.

## Delivered (2026-09-11)

The Metabase demonstration — the study's clickable third surface, developer-run
and non-CI. A theme bar drills to the review rows behind it over the reader's own
rebuild: `sql/marts/review_drill.sql` is a view (one row per classified review ×
theme) projecting the non-text allowlist `review_id` (`source || ':' ||
external_id`, mirroring `classify/labels.py::review_id`), `theme`, `rating`,
`review_date`, `segment`, `source` — never `body`/`title`/`source_url`, though the
join to `stg_reviews` reaches them, so the projection is the guard (checked on the
joined cursor and again in the export's `FORBIDDEN_COLUMNS`). It is built in the
post-classify path by `build_post_classify_marts` (renamed from
`build_theme_share_marts`). `study/metabase/export.py` copies the marts to a
gitignored `data/metabase/metabase.sqlite` via stdlib `sqlite3` — decimals as
their exact string (`rating` never drifts), ordered rows, byte-identical on a
rerun — which Metabase reads through its built-in SQLite driver (no DuckDB
community JAR). `study/metabase/apply.py` provisions the dashboard from
`config.yaml` over the HTTP API idempotently (stdlib `urllib`, an injected client
seam, upsert by name, credentials from the environment refused by name, `_base_url_ok` and
`_NoCrossHostRedirect` keeping the session token on the vetted host, `--dry-run`
the offline half). The only text a drilled theme shows is B2.1's five Documented,
sourced paraphrases (`study/paraphrases.yaml`) — B2.1 moved Pending → Documented.

Recorded §90 deviation: literal review *excerpts* are unattainable under D1 and
Neutrality, so the audit trail is counted rows + a sourced theme paraphrase, not
per-review excerpts (DECISIONS → Phase 9g; PROJECT_BRIEF §90 annotated). Closed:
the tooltip-only trail and the live-sliders debt (Metabase shows visible counts
and its own exploration); the per-review-public-address row stays open,
re-deferred. BACKLOG 52 was NOT folded in (its own `fix/` PR). No new Python
dependency (Docker/Metabase pre-approved); the committed HTML page is
byte-unchanged.

The offline core is what CI and the DONE command run — `make rebuild
ROWS=synthetic && uv run pytest tests/test_metabase_apply.py
tests/test_review_drill.py -q && uv run python -m study.metabase apply --dry-run`,
all green; `make review-gate SPEC=…` 8/8. The live `docker compose up` + apply +
synthetic-only screenshots are the developer's step; the build's first-hour spike
confirms the built-in SQLite driver reads the mounted file and the exact dashcard
body against `/api/docs`.

Challenge round 1 returned rework (2 BLOCKER — scope, the §90 framing — 4
should-fix; all applied) and round 2 approve-with-amendments (1 BLOCKER — the
corpus gate is render-time, absent from the marts Metabase reads — 3 should-fix, 1
question; all applied), spec `062cf09f`. Review round 1: 0 BLOCKER, functionality
works; 16 findings fixed across six commits (the `unshaped-input` and
`traceback-at-boundary` classes, the least-privilege docker mount, `export --rows`,
tests, wording/records). Round 2: 0 correctness, the cap rule did not fire; 5
notes/record/wording fixed (cross-host redirect refused, the make-rebuild prose,
the image-tag Gotcha, Record-updates reconciled). Exit coherence audit: coherent,
no BLOCKER — the §90-brief annotation and the Phase-10 warehouse-aware BACKLOG row
(now naming `review_drill`) applied at exit.
