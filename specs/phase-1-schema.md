# Phase 1 — Schema and the empty warehouse (APPROVED)

Contract for the `phase-1-schema` branch. Source: PROJECT_BRIEF.md §9 Phase 1
(schema and the empty warehouse), scoped by `docs/PLAN.md` §5 row 1 and the
Phase-0 decisions in §4 (1 warehouse seam, 2 idempotent raw, 8 synthetic
fixture + real anchors, 9 no pandas, 10 regex in Python). Depends on
`phase-0b-contracts` merged (PR #2).

**Status: APPROVED 2026-09-01 — in progress.** One dependency change:
`duckdb` (pre-approved for Phase 1, CLAUDE.md → Conventions). No pandas on any
pipeline path; anything beyond `duckdb` is a STOP-and-ask.

## Why

Phase 0b froze what the study claims and where each number will live
(`SPEC.md`, `BACKING.md`: 19 rows, 13 named marts, all Pending). Nothing yet
holds a row. Phase 1 builds the warehouse those numbers land in: the raw and
staging tables for reviews, with the four provenance columns; the one seam that
knows DuckDB from Snowflake; the two frozen fixture sets that stand in for real
data; and the two commands that prove the pipeline runs the same way twice. It
is deliberately data-free — the synthetic fixture is the only "data," and it is
obviously fake. No scraper (Phase 2), no classifier (Phase 5–6), no cost model
(Phase 8), no study text (Phase 9).

**Teaching notes (become code comments / README lines at build — CLAUDE.md →
Teaching rule).**
- *DuckDB vs Snowflake dialect.* DuckDB is a file-on-a-laptop database; Snowflake
  is a cloud one. We write one set of SQL and run it on either by keeping the SQL
  to the shared (ANSI) subset and putting the one connection detail behind
  `pipeline/warehouse.py`. Anything a single engine invents — reading a CSV in
  SQL, a regex function, a clock — is banned so the same file runs on both.
- *Content-hash idempotency.* Each review row carries a `content_hash` — a short
  fingerprint of its text and rating. We only insert a review whose
  (source, id, fingerprint) triple we have not seen, so re-running the scrape on
  an unchanged review adds nothing, while an edited review (new fingerprint) adds
  a new row and the old one is kept for history. That is what lets "run it twice"
  leave every count unchanged.

## The central constraint

**`make rebuild` is deterministic and idempotent — run it twice on the same
fixture and every table's row count is unchanged — and the data path stays
clock-free, dialect-free, and model-free: no `now()`/`current_date` in `sql/`,
no DuckDB-only form, no second database driver, no model call anywhere.** Phase
1 lands no mart, so `BACKING.md` stays all-Pending and no number appears. The
no-key run is green by construction (nothing imports a model). `fixtures/synthetic/`
and `fixtures/anchors/` are frozen at first write and read-only thereafter.

## DONE command

```
make rebuild FIXTURE=synthetic && make idempotency-check
```

- `make rebuild FIXTURE=synthetic` — builds the DuckDB warehouse from raw:
  reads `fixtures/synthetic/` in Python (stdlib csv), inserts into `raw_reviews`
  with the idempotent guard, rebuilds `stg_reviews`; reproduces the
  `tests/pins.py` stage counts. Offline, DuckDB, no key.
- `make idempotency-check` — rebuilds twice and diffs per-table row counts; a
  non-zero diff exits 1. This is the run-twice property as a command.
- Also green: `make rebuild` (no FIXTURE → the zero-row run, end to end — 0/0 on
  a fresh warehouse; raw is append-only, so `make reset` first for a clean 0/0
  after a synthetic build); `make test` (offline, no services, no network);
  `make check-backing` (still 19 rows, 0 marts, 0 orphans — Phase 1 lands no
  mart).

## Done-when

1. **The warehouse seam is the one place that knows the engine.**
   `pipeline/warehouse.py` exposes `connect(target)` and `run_sql_file(conn,
   path)`; only DuckDB is exercised now; the Snowflake branch is a lazy import
   that raises a clear Phase-10 error; no other module imports a database driver.
   *Evidence: row 1.*
2. **`make rebuild` runs end to end on zero rows AND on the synthetic fixture,
   deterministically.** raw → staging with no mart files; the synthetic run
   reproduces the `tests/pins.py` stage counts; a re-run changes no count.
   *Evidence: row 2.*
3. **Raw is append-only with the four provenance columns; staging dedups to the
   latest capture.** Every `raw_reviews` row carries `source`, `source_url`,
   `captured_at`, `run_id`; the natural key is `(source, external_id,
   content_hash)`; `stg_reviews` keeps one row per `(source, external_id)` at the
   latest `captured_at`. *Evidence: row 3.*
4. **The SQL is portable and clock-free.** No file under `sql/` uses a
   DuckDB-only form, a regex, or `now()`/`current_date`/`current_timestamp`;
   portability is a denylist test now and a live Snowflake run in Phase 10.
   *Evidence: row 4.*
5. **Both fixture sets are frozen at first write.** `fixtures/synthetic/`
   (~40 hand-written, obviously fake reviews whose bodies cover all seven
   outcomes) and `fixtures/anchors/` (the §6 aggregates) each match their
   `MANIFEST.sha256`; read-only after this phase. *Evidence: row 5.*
6. **`make idempotency-check` proves run-twice, and the destructive `reset` is
   CONFIRM-gated.** idempotency-check rebuilds twice and diffs per-table counts
   (unchanged); `reset` drops the DuckDB file only with `CONFIRM=yes` given on
   the command line (`$(origin CONFIRM)`). *Evidence: row 6.*

(6 items. Each is a contract, not a narrative.)

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `tests/test_warehouse.py::test_connect_selects_duckdb`, `::test_snowflake_target_defers_to_phase_10`; code-reviewer confirms `pipeline/warehouse.py` is the only database-driver import |
| 2 | `make rebuild FIXTURE=synthetic` completes; `tests/test_rebuild.py::test_zero_row_rebuild`, `::test_synthetic_stage_counts_match_pins`; functionality-tester runs the DONE command |
| 3 | `tests/test_provenance.py::test_raw_reviews_has_four_provenance_columns`; `tests/test_rebuild.py::test_staging_keeps_latest_capture`; `tests/test_idempotency.py::test_edited_review_appends_new_row` |
| 4 | `tests/test_sql_portable.py::test_denylisted_form_is_rejected`, `::test_clock_in_sql_is_rejected` |
| 5 | `tests/test_fixtures_frozen.py::test_manifests_match` |
| 6 | `make idempotency-check` prints per-table counts unchanged; `tests/test_idempotency.py::test_second_rebuild_adds_no_rows`; `tests/test_makefile.py::test_reset_requires_command_line_confirm`, `::test_fixture_outside_the_set_is_refused` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all tables, a second `make rebuild` on the same fixture leaves every row count unchanged. | `tests/test_idempotency.py::test_second_rebuild_adds_no_rows` — rebuild twice, diff counts; any table grows |
| For all `raw_reviews` rows, `source`, `source_url`, `captured_at`, `run_id` are present. | `tests/test_provenance.py::test_raw_reviews_has_four_provenance_columns` — a raw row with a null provenance column |
| For all `(source, external_id)` in staging, exactly one row survives — the one with the latest `captured_at` (ties broken by `content_hash`). | `tests/test_rebuild.py::test_staging_keeps_latest_capture` — two captures of one review; staging keeps the newer. Ties: `::test_staging_tiebreak_is_deterministic_on_equal_captured_at` — equal `captured_at`, survivor is the higher `content_hash` in both insertion orders |
| For all files under `sql/`, no DuckDB-only form, no regex, and no `now()`/`current_date`/`current_timestamp` appears. | `tests/test_sql_portable.py::test_denylisted_form_is_rejected`, `::test_clock_in_sql_is_rejected` — a planted `read_csv`/`now()` string fails |
| For the empty fixture and the synthetic fixture alike, `make rebuild` completes and staging equals dedup(raw). | `tests/test_rebuild.py::test_zero_row_rebuild`, `::test_synthetic_stage_counts_match_pins` |
| For `fixtures/synthetic/` and `fixtures/anchors/`, every file hashes to its `MANIFEST.sha256`. | `tests/test_fixtures_frozen.py::test_manifests_match` — a byte flip in a fixture fails |
| For `TARGET=snowflake` in Phase 1, `connect()` raises a clear Phase-10 error and no module imports snowflake at load time. | `tests/test_warehouse.py::test_snowflake_target_defers_to_phase_10` |

## Pinned decisions (do not re-litigate)

- **All 13 marts (and `platform_snapshots`) are deferred to the phases that land
  their upstreams; Phase 1 builds raw + staging for reviews only.** Every mart
  depends on data a later phase produces — the snapshot marts on
  `platform_snapshots` (Phase 3: `rating_trend` B1.2, `channel_gap` B1.3,
  `platform_stats` B1.4, `peer_ratings` B2.3); the theme marts on the gated
  classifier (`theme_share_by_month` B2.2 and `classifier_quality` B2.4 in
  Phase 5b–6, `theme_share_by_segment` B2.5 in Phase 7); the model marts on the
  cost model / simulator (Phase 8: `cost_model_outputs` B3.1, `cost_curves` B3.2,
  `cost_model_params` B3.3/B3.4, `guardrail_sim` B4.1/B4.3, `sla_threshold`
  B4.2); `pipeline_row_counts` B5.2 on the whole pipeline (Beat 5). Building any
  now either reaches into a future phase or fixes a table's columns before its
  subsystem is designed. All BACKING rows stay Pending; `check-backing` sees 0
  marts, 0 orphans. **This narrows the brief's "All DDL (raw/staging/marts)" to
  the layers whose upstream exists — flagged for your approval below.** Rejected:
  empty mart stubs (assert a schema before the subsystem exists, against
  invariants-before-mechanisms); building the four snapshot marts now
  (`platform_snapshots` is Phase 3's table — one phase, one diff).
  `theme_share_by_month` (B2.2, monthly × segment) stays a distinct mart from
  `theme_share_by_segment` (B2.5) in BACKING and in Phase 7.
- **The warehouse seam: `TARGET=duckdb|snowflake` → `pipeline/warehouse.py`.**
  `connect(target)` + `run_sql_file(conn, path)`; the SQL files are identical for
  both engines; the Snowflake connector is a lazy import (its package is a
  Phase-10 dependency), so Phase 1 needs only `duckdb` and `TARGET=snowflake`
  raises a clear Phase-10 error. Satisfies the portability invariant. Rejected:
  jinja/dialect macros (PLAN §4.10 — regex in Python keeps SQL dialect-free
  instead of templating the dialect in).
- **Idempotent raw keyed `(source, external_id, content_hash)`; staging keeps
  the latest `captured_at`.** `content_hash` is a sha256 of the content fields
  (rating, title, body, review date); a re-scrape of an unchanged review inserts
  nothing, an edited one inserts a new row, and staging deduplicates on
  `(source, external_id)` newest-first with `content_hash` as the deterministic
  tiebreak (equal sort keys resolve the same way every run). Satisfies the
  idempotency and staging invariants. (PLAN §4 decision 2.)
- **`run_id` is stamped in Python, never in SQL; it is in no natural key and in
  no mart.** So `sql/` stays clock-free and a changing `run_id` never duplicates
  a row or moves a study number; in FIXTURE mode `run_id` is the fixture name, so
  the synthetic rebuild is byte-stable, not merely count-stable. Rejected:
  `run_id` from `now()` in SQL (breaks the no-clock rule).
- **The fixture is read in Python (stdlib csv) and inserted with a portable
  guard.** DuckDB's `read_csv` is dialect-bound, so Python reads the CSV and the
  insert is ANSI `insert … select … where not exists (…)`, parameterized. No
  pandas (PLAN §4.9). Satisfies portability. Rejected: `read_csv` in SQL
  (non-portable) — this is why the fixture load lives in the driver, not in a
  `sql/` file.
- **One validating CLI process behind `make`; `reset` is the only destructive
  target, gated by `$(origin CONFIRM)`.** `rebuild` and `idempotency-check` take
  `TARGET` and `FIXTURE` as a **closed set** (`TARGET ∈ {duckdb, snowflake}`,
  `FIXTURE ∈ {empty, synthetic}`) validated in Python — empty → default, `../x`
  or `"; ` → refused, never a path. `reset` drops the DuckDB file only when
  `CONFIRM=yes` comes from the command line. Mirrors the existing SPEC/BASE shape
  (`$(call _Q,$(value VAR))`, `unexport`). Satisfies the threat model. `rebuild`
  itself deletes nothing — it appends to raw and replaces the derived staging
  table — so it is not CONFIRM-gated and is safe for CI.

(6 pinned decisions.)

## Scope (files)

New code:
- `pipeline/warehouse.py` — the seam: `connect(target)`, `run_sql_file(conn,
  path)`; DuckDB now, Snowflake a lazy import that defers to Phase 10.
- `pipeline/__init__.py`, `pipeline/__main__.py` — the validating CLI Make calls
  (`rebuild`, `idempotency-check`, `reset`): validates `TARGET`/`FIXTURE`/
  `CONFIRM`, derives every path in Python, reads the fixture (stdlib csv),
  stamps `run_id`, runs the `sql/` files raw → staging → marts in name order.
- `sql/raw/raw_reviews.sql` — `create table if not exists`: the four provenance
  columns + content columns + `content_hash`; header names grain, provenance
  columns, and the BACKING rows it feeds downstream.
- `sql/staging/stg_reviews.sql` — `create or replace table … as select …` with
  `row_number()` dedup (ANSI, no `qualify`); header names grain and provenance.
- `sql/marts/` — created empty (no `*.sql`): Phase 1 lands no mart.

New fixtures (frozen this phase):
- `fixtures/synthetic/reviews.csv` (~40 rows, all seven outcomes covered by the
  bodies; no theme column — labels are Phase 5) + `fixtures/synthetic/MANIFEST.sha256`.
- `fixtures/anchors/platform_snapshots_seed.csv` (the §6 public aggregates, with
  `source_url`, `captured_at`, `seeded_from`) + `fixtures/anchors/MANIFEST.sha256`.
  Frozen now (fixtures are read-only after Phase 1) though `platform_snapshots`
  first reads it in Phase 3.

New tests:
- `tests/pins.py` — the synthetic stage counts and the seven-outcome coverage
  (the single source of every pinned number; §6-anchor and cost-model pins are
  added in Phases 3 and 8).
- `tests/test_warehouse.py`, `tests/test_rebuild.py`, `tests/test_idempotency.py`,
  `tests/test_provenance.py`, `tests/test_sql_portable.py`,
  `tests/test_fixtures_frozen.py`; extend `tests/test_makefile.py` for the three
  new targets.

Records (see Record updates):
- `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml` + `uv.lock`
  (`duckdb`), `CLAUDE.md`, `DECISIONS.md`, `specs/phase-1-schema.md`.

Freeze: fixtures/synthetic/
Freeze: fixtures/anchors/

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 1 entry: the marts-deferral (with the brief-divergence
      note), the warehouse seam, the idempotent raw key, `run_id` in Python,
      `sql/raw/`; no supersede pointers
- [ ] `CLAUDE.md` — Current status; Commands (`rebuild`, `idempotency-check`,
      `reset`); Repo map (`sql/raw/`, `pipeline/`, `fixtures/`, `tests/pins.py`
      now exist); the SQL-header convention extended to `sql/raw/`; BACKLOG count
      (6, unchanged)
- [ ] `specs/phase-1-schema.md` — this spec; the "Delivered" paragraph at exit
- [ ] BACKLOG — none (no row opened or closed; count stays 6)
- [ ] BACKING — none (Phase 1 lands no mart; every row stays Pending)
- [ ] SPEC — none (no chart or beat changed)
- [ ] README — none (Phase 9; PROJECT_BRIEF.md is the front door until then)
- [ ] PROJECT_BRIEF — none (the "All DDL" narrowing is flagged in this spec for
      your call, not silently edited into the master doc)

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

Three new targets: `rebuild` and `idempotency-check` take `TARGET`/`FIXTURE`;
`reset` deletes the DuckDB file and is CONFIRM-gated. Settled shape (CLAUDE.md,
`specs/TEMPLATE.md`): one Python process validates the value, derives every path
from it, prompts on a tty, then acts; every recipe is one line; every user
variable reaches Python unexpanded and single-quoted via `$(call _Q,$(value
VAR))` and is `unexport`ed. No paid API, no network (offline DuckDB only).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `rebuild` | `TARGET`→duckdb, `FIXTURE`→empty (zero-row run) | refused — validated against a closed set, not a path | one literal arg (no shell/make runs); not in the set → refused | `unexport`ed; validated identically in Python | n/a (no confirm knob) | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set` |
| `idempotency-check` | same defaults; rebuilds twice, diffs counts | refused (closed set) | one literal arg; refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_idempotency_check_variables_are_a_closed_set` |
| `reset` | empty `CONFIRM` ≠ yes → prompt on tty, refuse non-interactively; nothing deleted | `TARGET` refused (closed set) | one literal arg; refused | `CONFIRM=yes` from env → `$(origin CONFIRM)` = `environment` ≠ `command line` → not confirmed → refused | `CONFIRM=yes` counts only from the command line | `tests/test_makefile.py::test_reset_requires_command_line_confirm` |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").
**`docs/PLAN.md` §5 row 1 lists only code-reviewer + functionality-tester — it
assumed a code-only diff. This phase also edits `.github/workflows/ci.yml` (the
`make rebuild FIXTURE=synthetic` step), adds the destructive `reset` target, and
adds `pipeline/warehouse.py` — all three on the Sensitive surface — so
security-reviewer joins; and it edits `CLAUDE.md` prose, so study-editor joins.
The union runs: code-reviewer, functionality-tester, security-reviewer,
study-editor, and coherence-auditor at exit.**

- **code-reviewer** (triggered — `pipeline/**`, `sql/**`, `Makefile`,
  `scripts/`-style CLI, `tests/`): deterministic-first (no model import
  anywhere), no clock on the data path, raw append-only with the four provenance
  columns, staging dedups on the natural key, portable SQL (regex in Python), the
  `duckdb`-only dependency, and scope (every table maps to a BACKING mart or is
  raw/staging plumbing — no orphan mart).
- **security-reviewer** (triggered — `.github/workflows/ci.yml`, the destructive
  `reset` target, `pipeline/warehouse.py`): the new CI step stays `contents:
  read`, offline, no key; `reset` is `$(origin CONFIRM)`-gated and derives its
  path in Python; the DuckDB file lives under `data/` (gitignored, `*.duckdb`
  already covered); no secret, no network, no personal data in a tracked fixture.
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  command; the zero-row and synthetic rebuilds; run-twice idempotency; the
  edited-review append; the frozen-fixture check; `reset` refusing an
  environment `CONFIRM`.
- **study-editor** (triggered — `CLAUDE.md` prose): the Commands / Repo map /
  status edits stay in the two-layer voice, name things by meaning, and add no
  banned word.
- **coherence-auditor** at exit (mandatory): `SPEC` ↔ `BACKING` ↔ `sql/marts`
  still reconcile (0 marts, all Pending); the Repo map marks what now exists; no
  stale "Phase 1 will…" sentence remains; the brief-divergence note is recorded
  in DECISIONS, not silently applied.
- Stack risk: confirm DuckDB's `create or replace` and `insert … where not
  exists` behave as assumed and that the portability denylist neither
  false-positives on legitimate ANSI nor misses a DuckDB-only form; verify
  `content_hash` is stable across runs. Check official docs before any
  workaround; STOP and report; findings go to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- The 13 marts and `platform_snapshots` — their phases (see the first pinned
  decision); each already has a Pending BACKING row.
- The review scraper — Phase 2 replaces the fixture load, writing the same
  `raw_reviews` shape.
- The live dual-engine (Snowflake) proof — Phase 10; Phase 1's guarantee is the
  static portability denylist.
- Hand labels, `classified_reviews`, the cost model, the study export — Phases
  5–9.
