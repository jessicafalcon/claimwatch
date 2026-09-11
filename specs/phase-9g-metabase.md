# Phase 9g — the Metabase demonstration: the review-level drill

Contract for the `phase-9g-metabase` branch. Source: PROJECT_BRIEF.md §4.4 (the
"Full (demonstration)" run mode) and §9 Phase 9 ("The study"), sub-phase 9g of
the permanent-artifact-first split (DECISIONS → Phase 9a). It is the last Phase 9
sub-phase. Depends on Phase 9f merged (PR pending → merged 2026-09-10).

**Status: PROPOSED — do not start until approved.** No new Python dependency:
the applier is stdlib `urllib` (the `opendata/fetch.py` precedent), the config is
`pyyaml` (Phase 2), the marts are `duckdb` + SQL. Metabase runs via Docker, which
CLAUDE.md → Conventions pre-approves ("Airflow and Metabase via Docker only").
The phase is **non-CI**: CI is offline (no Docker), so the live demonstration
cannot end CI-green — the phase splits into an offline, CI-checkable core (the
applier's request bodies, the drill view's column set, the classify-path
idempotency target) and a developer-run demonstration (the live Metabase run and
its committed screenshots).

## Why

The brief promises three delivery surfaces: the permanent HTML export (Phases
9a–9e), the README (9f), and the Metabase dashboard where "every theme bar drills
through to the underlying review excerpts — audit trail, not citation" (brief
§90, §4.4 "Full (demonstration)"). The first two shipped. This is the third, and
it is the one place the study becomes clickable rather than printed: a reader
drills a theme bar down to the individual reviews counted in it.

Three debts were deferred here on purpose, and this phase pays them:

- **The review-level drill** (BACKLOG 70). Beat 2's HTML trail is the mart's
  `reviews`/`theme_rows` counts beside each share; a per-review view lives in
  Metabase over the reader's own rebuild, because the HTML export is
  byte-checked and self-contained and cannot carry a live drill.
- **The visible denominator** (BACKLOG 72). B2.2/B2.5's counts ride in the HTML
  chart's SVG `<title>` tooltip, invisible to print, phone and screen readers.
  Metabase shows the counts as visible cells and the drill shows the rows behind
  them, which is what "visible denominator" asked for.
- **Live exploration** (BACKLOG 73). Beat 3 draws each parameter's range as a
  static mark; the permanent page carries no slider (9f). Metabase's own
  filters and drill are the live exploration a browser script would have been.

It also finally lands B2.1 (Pending since Phase 2): the five-theme taxonomy with
its Documented paraphrased examples, curated with public sources, is the text the
drill shows when a theme is opened. And it pays BACKLOG 52 (the classify-path
marts are not machine-checked for idempotency by a `make` target): the
demonstration rebuilds over captured data, which runs the classify step, so a
sibling idempotency target that runs classify is the natural home for the check.

This is not a fix PR: it adds a delivery surface (a Docker stack and an HTTP-API
applier), a new Documented evidence surface (B2.1), a drill view mart, and a
`make` target. It is deliberately the widest Phase 9 sub-phase; **scope is the
first thing the challenge round should test** (see Review & stack risk).

## The central constraint

**The review-level drill exposes no raw review text and no per-review brand
address: the per-review projection is a fixed non-text allowlist, and the only
text a drilled theme shows is a curated, sourced paraphrase from
`study/paraphrases.yaml` — never a review's own `body`. The offline core (the
applier's request bodies, the drill view's columns, the classify-path
idempotency target) is deterministic and CI-checkable; the live Metabase run is
developer-run.** The five contracts, the marts (`sql/`), the classifier
(`classify/`), the permanent HTML export (`study/export.py`, `panels.py`,
`model.py`, `text.py`, and the committed `friction_ledger.html` — byte-unchanged)
and every existing pin in `tests/pins.py` do not move. No `now()`/`current_date`
enters the data path; the drill orders by the review's own date, never a clock.

## DONE command

```
make rebuild ROWS=synthetic && make idempotency-check-classify && uv run pytest tests/test_metabase_apply.py tests/test_review_drill.py -q && uv run python -m study.metabase apply --dry-run
```

- `make rebuild ROWS=synthetic` builds the frozen input and the drill view over
  it; the view carries only the allowlisted columns and no number over a fixture
  input (the corpus gate, inherited from 9b). Reproduces the synthetic rebuild.
- `make idempotency-check-classify` rebuilds **and classifies** twice into a
  throwaway database and diffs per-table row counts for the three classify-path
  marts (`theme_share_by_month`, `theme_share_by_segment`, `pipeline_row_counts`)
  and `stg_classified_reviews`; green with no key (BACKLOG 52). Prints one line
  per table and `MATCH`/`DIFFER`.
- `uv run pytest tests/test_metabase_apply.py tests/test_review_drill.py -q`
  proves the offline core the live run cannot: the applier builds pinned request
  bodies from the YAML and, given a fake client whose state already holds the
  objects, issues update-not-create (idempotent upsert); the drill view's
  projected columns are exactly the non-text allowlist (`select *` fails by
  name), a synthetic review's distinctive `body` never appears in any drill
  column, and a drilled theme's paraphrase resolves to a `study/paraphrases.yaml`
  entry with a public source.
- `uv run python -m study.metabase apply --dry-run` builds every request body
  from the committed YAML and the running marts' schema and prints them, touching
  no network and needing no credentials — the CI-safe half of the applier.

## Done-when

1. **Metabase is provisioned from committed config, idempotently.** A committed
   `study/metabase/docker-compose.yml` brings up Metabase against the reader's
   rebuilt marts; `study.metabase apply` reads `study/metabase/config.yaml` and
   upserts the collection, questions and dashboard by stable name over the HTTP
   API (stdlib `urllib`), so applying twice creates no duplicate object.
   `--dry-run` builds the request bodies offline. *Evidence: rows 1, 2.*
2. **The review-level drill exposes only non-text, non-brand columns.** The drill
   view projects a fixed allowlist — `review_id, theme, rating, review_date,
   segment, source` (the platform name, never `source_url`) — checked on the
   cursor's description so `select *` or a stray column fails by name; `body`,
   `title` and `source_url` are absent from every drill query. *Evidence: rows 3,
   4.*
3. **A drilled theme's only text is a curated, sourced paraphrase; B2.1 becomes
   Documented.** `study/paraphrases.yaml` carries one paraphrased example per
   theme (five), each with the public source it paraphrases (brief §6); the
   drill shows this text when a theme is opened, never a review `body`; a review
   with no curated paraphrase shows the counted rows and no text. B2.1 moves
   Pending → Documented. *Evidence: rows 5, 6.*
4. **The classify-path marts are machine-checked for idempotency (BACKLOG 52).**
   `make idempotency-check-classify` rebuilds and classifies twice over one
   throwaway database and diffs per-table counts for `theme_share_by_month`,
   `theme_share_by_segment`, `pipeline_row_counts` and `stg_classified_reviews`;
   it is added to CI and is green with `ANTHROPIC_API_KEY` unset. *Evidence: row
   7.*
5. **The no-key run stays green and the applier needs no Anthropic key.** With
   `ANTHROPIC_API_KEY` unset, the rebuild, the classify step, the drill view and
   `apply --dry-run` all succeed; ambiguous reviews are `unclassified` and appear
   in the drill under the "not yet classified" band; the applier's dry-run bytes
   are identical to the keyed run's. *Evidence: rows 8, 9.*
6. **The demonstration is committed and safe by construction.**
   `study/metabase/DEMONSTRATION.md` walks a theme-bar → review drill with
   committed screenshots under `study/metabase/screenshots/`; because the drill
   view (done-when 2, 3) carries no `body`/`title`/`source_url` column, no
   screenshot can show raw review text or a brand address; study-editor and
   security-reviewer confirm the committed artifacts. *Evidence: row 10.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_metabase_apply.py::test_apply_twice_over_existing_state_issues_no_create` |
| 1 | `tests/test_metabase_apply.py::test_dry_run_builds_pinned_request_bodies_without_network` |
| 2 | `tests/test_review_drill.py::test_drill_projects_only_the_non_text_allowlist` |
| 2 | `tests/test_review_drill.py::test_drill_has_no_body_title_or_source_url_column` |
| 3 | `tests/test_review_drill.py::test_drilled_theme_paraphrase_resolves_to_a_sourced_entry` |
| 3 | `tests/test_review_drill.py::test_a_review_body_never_appears_in_any_drill_column` |
| 4 | `make idempotency-check-classify` prints "MATCH" for the four tables; `tests/test_metabase_apply.py::test_classify_path_idempotency_target_matches` |
| 5 | `tests/test_review_drill.py::test_drill_builds_and_bands_unclassified_with_no_key` |
| 5 | `tests/test_metabase_apply.py::test_dry_run_is_identical_with_key_unset` |
| 6 | `tests/test_review_drill.py::test_demonstration_doc_and_screenshots_exist_and_links_resolve` (study-editor + security-reviewer read the screenshots) |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all Metabase objects the applier provisions, applying the same config twice leaves the server unchanged — it upserts by stable name, never creating a duplicate. | `tests/test_metabase_apply.py::test_apply_twice_over_existing_state_issues_no_create` — a fake client pre-loaded with the objects records every request; the second apply issues only PUT/updates, no POST/create. |
| For all rows the drill exposes, the projected column set is a fixed allowlist containing no raw-text column (`body`, `title`) and no per-review brand address (`source_url`). | `tests/test_review_drill.py::test_drill_projects_only_the_non_text_allowlist` — the view's cursor description equals the allowlist; a query naming `body`/`title`/`source_url` fails by name. |
| For all reviews in the drill, any text shown comes from `study/paraphrases.yaml`, never from the review's own `body`; a review with no curated paraphrase shows no text. | `tests/test_review_drill.py::test_a_review_body_never_appears_in_any_drill_column` — a synthetic review with a distinctive body and no curated paraphrase renders no text, and the body string appears in no drill column. |
| For all four classify-path tables, rebuilding and classifying twice over one input leaves per-table row counts unchanged. | `tests/test_metabase_apply.py::test_classify_path_idempotency_target_matches` — the target's two passes diff to zero for the four tables. |
| With `ANTHROPIC_API_KEY` unset, the rebuild, classify, drill view and `apply --dry-run` all succeed and the dry-run bytes are unchanged; ambiguous reviews are `unclassified`. | `tests/test_metabase_apply.py::test_dry_run_is_identical_with_key_unset`; `tests/test_review_drill.py::test_drill_builds_and_bands_unclassified_with_no_key`. |
| For all values the applier reads from the marts' schema and the config, the request bodies it builds are the same on a rerun (no clock, no random, sorted) — the dry-run is byte-stable. | `tests/test_metabase_apply.py::test_dry_run_builds_pinned_request_bodies_without_network` — two dry-runs produce identical bytes pinned in `tests/pins.py`. |

## Pinned decisions (do not re-litigate)

- **The drill's per-review projection is a non-text allowlist; its only text is a
  curated paraphrase.** The allowlist (`review_id, theme, rating, review_date,
  segment, source`) excludes `body`/`title` (personal data — brief §5's example
  bodies name conditions) and `source_url` (the brand-carrying page address —
  D1). The theme's paraphrase is `study/paraphrases.yaml`, human-written and
  sourced. Satisfies invariants 2 and 3. *Rejected: rendering a truncated
  `body` snippet as "one short marked phrase" — raw text carries a name or a
  condition and no per-review public source exists to cite (BACKLOG 70); a
  machine-generated paraphrase — the model is called from exactly one site
  (`classify/llm.py`), never for prose (Deterministic-first).*
- **The applier is a developer-run stdlib `urllib` module reading Metabase
  credentials from `.env`, idempotent by upsert-by-name; it is not a `make`
  target with a variable.** Keeping it a plain `python -m study.metabase apply`
  avoids the `make` variable/`confirm` surface entirely, and localhost
  provisioning is neither paid nor destructive; `--dry-run` is the offline half.
  Satisfies invariant 1 and 6 (byte-stable bodies). *Rejected: a paid/hosted
  Metabase — the demonstration is a laptop, no accounts (§4.4 Portable);
  screenshotting a hand-built dashboard with no config — not reproducible, no
  idempotency to test (§4.4 "keep configs").*
- **B2.1 lands here as Documented, curated in `study/paraphrases.yaml` with
  public sources.** SPEC B2.1 already anticipates it ("Documented — Pending
  until the examples are curated with links"); this realizes the anticipated
  row, not a new chart. Satisfies done-when 3. *Rejected: leaving B2.1 Pending
  and showing the drill with no theme text — the developer's chosen drill shows
  paraphrased text; keeping the text uncited — the paraphrase rule requires the
  public source (brief §2.5).*
- **BACKLOG 52 lands here as `make idempotency-check-classify`.** The
  demonstration rebuilds over captured data, which runs classify, so a sibling of
  `idempotency-check` that runs the classify step is the natural home; it is
  offline and CI-safe, so unlike the rest of the phase it is added to CI.
  Satisfies invariant 4. *Rejected: leaving it to Phase 10's DAG — the
  slow-test coverage stands, but the developer chose to fold it in;
  extending `idempotency-check` itself — that target is `rebuild()`-only by
  contract and CI runs it under `ROWS=samples` where classify would need a key
  path.*
- **The phase's done-when splits into an offline core (DONE command, CI) and a
  developer-run demonstration (the live run + screenshots).** A non-CI phase
  cannot end CI-green on the live run; the testable contracts are the request
  bodies, the drill columns and the classify idempotency. Satisfies the Evidence
  table. *Rejected: making the live run a done-when the suite asserts — CI has no
  Docker; asserting nothing about the applier — the request-body and idempotency
  properties are exactly what a config-as-data applier can be pinned on.*
- **The drill view honors the 9b corpus gate: a share/number derives only from a
  captured input.** The drill over a fixture input (`synthetic`, `samples`)
  renders the labelled fixture state and no counted number, the same rule the
  HTML export keeps. Satisfies the central constraint. *Rejected: a drill that
  shows synthetic counts as numbers — the brief forbids a fake-review number
  three times (§3, §10, §2.4).*

## Scope (files)

- `study/metabase/__init__.py`, `study/metabase/__main__.py` (the `apply`
  entry, `--dry-run`), `study/metabase/apply.py` (YAML → HTTP-API request
  bodies; the upsert; the injected HTTP client seam), `study/metabase/config.yaml`
  (the collection, questions and dashboard as data), `study/metabase/docker-compose.yml`,
  `study/metabase/DEMONSTRATION.md`, `study/metabase/screenshots/` (committed
  PNGs).
- `study/paraphrases.yaml` (B2.1: five themes, each a paraphrase + public
  source) — tracked study content, not a fixture.
- `sql/marts/review_drill.sql` (the drill view: DDL naming the grain — one row
  per review × theme — the non-text allowlist columns, the provenance columns and
  the BACKING rows it feeds; a view over `stg_classified_reviews`, no clock).
- `pipeline/build.py` (`idempotency_check_classify`: rebuild + classify twice,
  diff the four classify-path tables) and `pipeline/cli.py` (its entry).
- `Makefile` (`idempotency-check-classify` target) and `.github/workflows/ci.yml`
  (add it — the offline half only).
- `tests/test_metabase_apply.py`, `tests/test_review_drill.py`, `tests/pins.py`
  (the pinned request bodies and drill fragments).
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `BACKING.md`, `SPEC.md`,
  `README.md`, this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9g entry (the drill allowlist, the applier shape,
  B2.1's realization, the offline/live split, the DuckDB-driver resolution under
  Gotchas); challenge dispositions
- [ ] `BACKLOG.md` — rows closed (70, 72, 73, 52 struck + "DONE Phase 9g") and
  any row opened (a Beat-2 drill note, a longer-scenario label follow-on if
  found)
- [ ] LESSONS.md — none until a review round reports a correctness finding; then
  backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Commands (`idempotency-check-classify`,
  `study.metabase apply`); Repo map (`study/metabase/`, `study/paraphrases.yaml`,
  `sql/marts/review_drill.sql`); Teaching rule (Metabase drill-through, the
  DuckDB driver); BACKLOG count
- [ ] `BACKING.md` — B2.1 Pending → Documented (mart/source cells filled); B2.2's
  drill note if the trail sentence changes
- [ ] `SPEC.md` — B2.1's parenthetical (Documented, curated in
  `study/paraphrases.yaml`); the B2.2 tooltip-trail sentence if the visible
  denominator changes the described behaviour (a design change — STOP first if so)
- [ ] `README.md` — the Metabase demonstration named as the third surface's live
  form; the `make rebuild ROWS=captured` + Metabase reader path
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

The phase adds one `make` target (`idempotency-check-classify`) and one
developer-run network module (`study.metabase apply`, HTTP to localhost Metabase
with credentials from `.env`). `idempotency-check-classify` takes the existing
validated `TARGET`/`ROWS` variables through the same `$(call _Q,$(value VAR))`
path as `idempotency-check` and touches no new input; the applier takes no `make`
variable.

| Target/module | empty | `../x` | `"; ` | env-exported | credentials | Pinned by |
|---|---|---|---|---|---|---|
| `make idempotency-check-classify` | `ROWS=`/`TARGET=` → the CLI's existing closed-set refusal (exit 2), naming the variable | rejected by the same closed-set check (not a path) | single-quoted through `_Q`, reaches Python unexpanded, refused by the closed set | `unexport`ed like the other variables | none — offline, no key needed | `tests/test_cli.py` (the existing variable-validation tests extended to the new subcommand) |
| `study.metabase apply` (module, not a `make` target) | missing `METABASE_URL`/user/password → refuses naming the variable, never the value; `--dry-run` needs none | n/a — no path is built from a variable | n/a — no shell; `urllib` builds the request, no subprocess | reads `.env` only, never Actions | credentials in `.env` only; refusals print names; run twice = idempotent upsert (no duplicate object, no paid call, localhost only) | `tests/test_metabase_apply.py::test_apply_refuses_missing_credentials_by_name` |

Settled shape: one Python process validates, derives the request bodies, and
(for a live apply) prompts/reads `.env` then acts; `--dry-run` builds bodies with
no network and no credentials. No public network, no paid API, nothing deleted.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `study/**/*.py`, `sql/marts/**`, `Makefile`,
  `pipeline/`, `tests/`): the drill view's allowlist and corpus gate, the
  applier's idempotent upsert, formulas-as-data (the config as data), the no-key
  path, scope.
- **security-reviewer** (mandatory — `.github/` (CI edit), a network module with
  credentials, `study/metabase/`): credential handling (`.env` only, refusals
  name not value), the HTTP client (no shell, `urllib` request built from data
  not concatenation), and it **reads the committed screenshots** for any leaked
  raw text or brand address.
- **functionality-tester** (triggered): the DONE command, the four negative
  tests (missing credentials, `select *`, a body string in a drill column,
  double-apply), idempotency (`idempotency-check-classify`), the no-key run.
- **study-editor** (triggered — `SPEC.md`, `BACKING.md`, `README.md`, the
  DEMONSTRATION walkthrough, `study/paraphrases.yaml`): the paraphrases are
  paraphrase-not-quote, sourced, no personal data, no insurer named as target;
  the walkthrough's two-layer voice; **reads the committed screenshots**.
- **coherence-auditor** at exit: SPEC B2.1 ↔ BACKING B2.1 ↔ `study/paraphrases.yaml`
  ↔ the drill view ↔ README align; the "review-level drill is 9g" forward
  references in earlier specs and DECISIONS now resolve to a shipped thing; the
  Phase 9 sub-phase list is complete.
- **Stack risk (verify in the first hour, STOP and report before any
  workaround — Workflow rules → Stack surprises; log under DECISIONS →
  Gotchas):**
  1. **Metabase reading DuckDB.** Metabase ships no DuckDB driver; the community
     driver is a plugin JAR mounted into the container. Verify it connects to the
     rebuilt `.duckdb` file first; the fallback is a `sqlite`/`postgres` export of
     the marts in the same compose stack, or the §4.4 Snowflake full-mode
     connection. Decide before building the config.
  2. **Metabase HTTP API idempotency.** The API creates on POST; the applier must
     GET-then-PUT (upsert by name in a named collection). Verify the session-auth
     and the card/dashboard endpoints against the running version's API before
     pinning the request bodies.
  3. **Screenshot hygiene.** The committed PNGs must be captured over the
     developer's own captured rebuild; confirm the drill view shows no `body`
     before capturing (the allowlist guarantees it, but verify the live view).

## Out of scope (deferred, recorded)

- The HTML export rendering B2.1's paraphrases (a Beat-2 panel) — not this
  phase; the export's B2.1 stays Pending-in-HTML until a later render pass, if
  ever (BACKLOG). This phase ships B2.1's text in Metabase only.
- Snowflake + Airflow full-mode wiring — Phase 10 (the DAG); §4.4 full mode is
  named, not built here.
- The claims sample-mean slider and data.ameli practitioner fees — their own
  pulled-out data phases (DECISIONS → Phase 9a).
- B4.3's four-bar-label overflow (BACKLOG 74) — a Beat-4 follow-on, untouched.
