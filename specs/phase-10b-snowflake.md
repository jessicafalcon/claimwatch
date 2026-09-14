# Phase 10b — the Snowflake seam and the Snowflake run

Contract for the `phase-10b-snowflake` branch. Source: PROJECT_BRIEF.md §9
Phase 10 ("run once against a Snowflake trial; screenshot; confirm the DuckDB
path still passes — done when both targets run green"), §2 ("Nothing
load-bearing sits on a free trial … One config flag switches between them;
the SQL is written once, portable"), §4.4 (the "Full (demonstration)" run
mode: "Same SQL, different connection string"); `docs/PLAN.md` §4.1 (the
warehouse seam) and §5 row 10. The second half of the Phase 10 split
(DECISIONS → Phase 10a): 10a built the DAG, the stage split, `publish`, the
one engine-name constant and its layout test; this phase wires the seam's
second branch and runs it once. Seeded, as `specs/phase-10a-airflow.md` → Out
of scope records, by 10a's challenge round 1 findings #1–#4, #7, #9, #15 and
#17, and by BACKLOG rows 33 and 50. Depends on Phase 10a merged (PR #39,
2026-09-13).

**Status: APPROVED 2026-09-13 — in progress.** One new Python
dependency, pre-approved for this phase by CLAUDE.md → Conventions:
`snowflake-connector-python`, as an **optional extra** `snowflake` in
`pyproject.toml` (installed by `uv sync --extra snowflake`, never by `make
setup`, CI or the suite; the lock file resolves it so `--locked` stays
green). The phase is **non-CI** in the 9g/10a shape: an offline,
CI-checkable core (the seam's second branch proved against a fake driver,
the threading, the refusals, the layout tests) plus a developer-run
demonstration (the one Snowflake run over the synthetic fixture, recorded as
text).
Challenged: 2026-09-13, round 1, spec 014db324 — approve with amendments (0 BLOCKER, 3 should-fix, 2 suggestion, 1 question; developer disposition "fix all": findings 1/2/3 amended as one provenance-and-determinism reword — done-when 4 scopes byte-identity to a same-target rerun and names cross-engine equality a count-and-value check, done-when 6 records the BACKLOG-33 schema name Documented-by-hand and makes the fake→real trust boundary explicit; finding 5 amended — the credit-spend disclosure in the threat model and the caution line in DEMONSTRATION.md and README; finding 6 amended — stack risk 2 names the direct begin/commit/rollback calls on the wrapped cursor; finding 4 rejected — done-when 1 and 3 stay compound and are reviewed as such, a seam-refactor-only PR would carry no user-visible Done-when and add a merge; no new challenge round)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

*The stack, in plain words (Teaching rule).* **Snowflake** is a database that
runs in the cloud instead of in a file on a laptop: you log in with an
account name and a user, pick a "warehouse" (the computer that runs your
queries, billed by the second) and a "database", and send it the same kind
of SQL DuckDB runs. The brief keeps it as a demonstration only — a free trial
expires, so nothing the study needs may depend on it — and the way to make
that true is that the SQL files are identical for both engines and exactly
one Python file knows which engine is on the other end of the connection. A
**qmark cursor** is the driver setting that makes a query's placeholders `?`
on Snowflake as they are on DuckDB, so the SQL in `pipeline/build.py` is not
rewritten per engine.

## Why

Brief §9 ends Phase 10 with "both targets run green" and brief §4.4 promises
one config flag and one SQL. Today `TARGET=snowflake` is a declared name the
seam refuses by design (`warehouse.WIRED` is `(duckdb,)`), and BACKLOG rows 33
and 50 name two things only the second engine can prove: that the schema name
is read from the engine rather than spelled, and that the classify step's
writes follow `TARGET` rather than the laptop file. 10a left the code ready
for a parameter change with no literal to miss; this phase makes the change
and runs it. It is a phase, not a fix PR, because it adds a dependency, a
credential set, a network path and a demonstration.

What 10a's challenge round settled, and this spec does not reopen:

- **The cloud never holds the corpus** (round 1, #1 — the BLOCKER). A trial
  account is a third party's disk; the captured reviews are real people's
  words under brief §2.5. So `TARGET=snowflake` takes fixture inputs only,
  refused by name otherwise, at every entry that takes a target.
- **One connection shape, one error type, one catalog reader, all in the
  seam** (#2, #3, #4). The Snowflake driver's cursor shape, its upper-cased
  catalog answers and its error class are the seam's business; every other
  module keeps calling `conn.execute(...).fetchall()` and catching
  `warehouse.DriverError` exactly as it does today.
- **A schema per input** (#7), **a secret that is a string** (#9), **a
  demonstration that pastes counts and a schema name and nothing else**
  (#15), **`make setup` drops the extra** (#17).

## The central constraint

**The DuckDB path is byte-for-byte what 10a merged — every target, test,
CI step and committed artifact runs with no extra installed, no
`SNOWFLAKE_*` in the environment and no socket opened — and the corpus
input has no cloud location at all.** The phase changes where a connection
comes from, never what runs over it: no SQL file changes, no number moves,
no fixture is re-frozen, no BACKING tag changes, and `study/friction_ledger.html`
does not change.

## DONE command

```
make rebuild ROWS=synthetic && make idempotency-check ROWS=synthetic && make publish ROWS=synthetic && uv run pytest tests/test_warehouse.py tests/test_snowflake_seam.py tests/test_cli.py tests/test_ingest_layout.py tests/test_rebuild.py tests/test_makefile.py tests/test_metabase_apply.py tests/test_beat2.py tests/test_no_key.py -q
```

- `make rebuild ROWS=synthetic` — the DuckDB whole through the reshaped seam
  (the wrapped connection, the seam-owned catalog reads): the same counts
  `tests/test_rebuild.py` pins.
- `make idempotency-check ROWS=synthetic` — the run-twice property, classify
  step included, now over a scratch location the seam hands out (a temp
  directory on DuckDB); every count unchanged.
- `make publish ROWS=synthetic` — the export through the seam's connection,
  byte-identical to 10a's bytes for the same input.
- the pytest line — the seam's second branch against the fake driver (the
  cursor wrapper, `execute_string` for a multi-statement file, the case-folded
  catalog, the folded error, the schema per input, the scratch schema created
  and dropped), the CLI's refusals (a corpus input on the cloud target, a
  missing variable by name, a missing extra by name, a driver error as one
  line), the three layout guards (no engine name, no driver import, no
  catalog query or credential name outside the seam), the threaded classify
  step and export, the `publish TARGET=` recipe, the no-key run.

The Snowflake run itself is not in the DONE command: it needs an account and
the network (developer-run, never CI, never an agent's — CLAUDE.md →
Workflow rules); done-when 6 records it.

## Done-when

1. **The seam returns one connection shape on both targets, owns the one
   error type, and is the only module that imports a driver.**
   `warehouse.connect(target, database=)` returns an object with
   `execute(sql, params=None)` → an object carrying `fetchone`, `fetchall`
   and `description`, `executemany(sql, rows)`, and `close()`; the DuckDB
   branch wraps the DuckDB connection and the Snowflake branch wraps a
   `qmark` cursor of the connector, imported inside the branch only, so the
   DuckDB path never loads it and a missing extra is one refusal line naming
   `uv sync --extra snowflake`. `warehouse.run_sql_file` runs a file's
   several statements on either branch. `warehouse.DriverError` is a class the
   seam owns; each branch folds its driver's error into it, so
   `pipeline/build.py`, `study/` and the CLI catch one name as they do today.
   The DuckDB-only `import pandas` probe guard moves from `build.py` into the
   DuckDB branch's `executemany`, so no engine knowledge is left in the build.
   `WIRED` becomes both targets in one place. *Evidence: rows 1, 2, 3.*
2. **Catalog reads are the seam's, and their answers are case-folded.**
   `warehouse.tables(conn)`, `warehouse.columns(conn, table)` and
   `warehouse.table_exists(conn, table)` replace the `information_schema`
   queries in `pipeline/build.py` (`_columns`, `_table_exists`,
   `table_counts`) and `study/panels.py` (the mart probe); they read the
   engine's default schema and fold every name to lower case before
   comparing or returning, so `STG_REVIEWS` from Snowflake and `stg_reviews`
   from DuckDB are one table. The strings `information_schema` and
   `current_schema` occur in `pipeline/warehouse.py` only — a layout test
   refuses them elsewhere, the class of BACKLOG row 33. *Evidence: rows 4, 5.*
3. **Every (input, target) pair has its own location, and a corpus input has
   none on the cloud.** `warehouse.location_for(target, rows, root=None)`
   answers the DuckDB file per input (today's `database_for`, unchanged for
   the laptop) or the Snowflake schema per input, `friction_ledger_<input>`
   inside `SNOWFLAKE_DATABASE`, and raises naming both for `captured` or
   `samples` on the cloud target; every CLI path that takes a target
   (`rebuild` in all four stages, `idempotency-check`, `publish`) folds that
   into one refusal line, so the trial cannot hold a real review by
   construction. `idempotency-check`'s throwaway is `warehouse.scratch(target,
   rows)`, a context manager yielding a location that is never an input's own
   (a temp directory on DuckDB; a `create schema` … `drop schema` pair on
   Snowflake, dropped on exit even after a failure). `reset` keeps the DuckDB
   file: a cloud schema is dropped by the developer in the console, never by
   a `make` target. *Evidence: rows 6, 7, 8.*
4. **`TARGET` reaches the classify step, the idempotency check and the
   export.** `classify_step(location, run_id, *, target, cache_path, decide)`
   opens its connections on `target`; `build.CLASSIFY_TARGETS` is gone and
   the CLI resolves every stage against `WIRED`; `idempotency_check(target,
   rows)` counts on the target; `make publish [TARGET=] [ROWS=]` exports the
   named target's marts (`study.metabase export --target`), byte-identical on a
   rerun of the same (target, input) — cross-engine equality is a count-and-value
   check in the demonstration, never a byte compare (two engines' float
   formatting differs; pinned decision 4). `make study`, `label-sample` and
   `classify-eval` stay on
   the laptop file by contract (the tracked page renders the frozen synthetic
   input; the corpus never leaves the laptop; the eval reads the synthetic
   laptop file). BACKLOG row 50 closes. *Evidence: rows 9, 10, 11.*
5. **Credentials are six strings read by name in the seam, refused by name,
   never printed, and never seen by the suite.** `SNOWFLAKE_ACCOUNT`,
   `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD` (a password or a programmatic access
   token — both strings; no key-pair file, no `*_PATH` variable exists),
   `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, and the optional
   `SNOWFLAKE_ROLE` are read from the environment inside the Snowflake branch
   only; a missing required one is one refusal line naming the names that are
   missing, never a value; a driver refusal (a bad login, a stopped
   warehouse) is one line naming the driver's error class and the variables
   involved, never a value and never the driver's message verbatim.
   `.env.example` gains the six placeholders; `tests/conftest.py::_scrub_env`
   deletes every `SNOWFLAKE_*` before each test; the layout test that keeps
   `os.environ` reads of the model key in `classify/llm.py` extends to
   `SNOWFLAKE_` in the seam. The Snowflake path is credential-gated like the
   model key, not `confirm`-gated: with no credentials it refuses; with them
   it runs, developer-run. *Evidence: rows 12, 13, 14.*
6. **The demonstration is committed as text over the synthetic fixture, and
   the DuckDB path is unchanged.** `pipeline/DEMONSTRATION.md` walks the
   developer's run — `uv sync --extra snowflake`, the exported `.env`, `make
   rebuild TARGET=snowflake ROWS=synthetic` (all stages, no model key: the
   no-key run), `make idempotency-check TARGET=snowflake ROWS=synthetic`
   (OK), `make publish TARGET=snowflake ROWS=synthetic` — and pastes only the
   count table (the same table, table for table, that the DuckDB run of the
   same input prints), the idempotency line and the schema name; no account
   locator, no host, no console screenshot (the console's address bar carries
   the account — the brief's "screenshot" is met by 10a's DAG grid, and the
   deviation is recorded in DECISIONS). BACKLOG row 33 closes with the schema
   name the engine returned in the run, recorded Documented-by-hand in the doc;
   the seam test pins the case-fold logic only, never the engine's schema, so a
   hand-written fake's answer is never mistaken for the offline closure. The
   fake (`tests/fake_snowflake.py`) proves the branch's shape offline and the
   real driver is never in CI, so the five stack-risk unknowns are verified
   against the official docs in the first hour and, with the run's count table
   and schema name, recorded Documented-by-hand in DECISIONS → Gotchas (the
   fake→real trust boundary; brief §2 keeps Snowflake non-load-bearing, so no
   study number rests on the run). CI's whole run, `make study` + `git diff
   --exit-code` included, is the DuckDB-unchanged proof. *Evidence: rows 15, 16.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_snowflake_seam.py::test_the_snowflake_branch_wraps_a_qmark_cursor_in_the_seams_shape` — with a fake `snowflake.connector` in `sys.modules`: `connect("snowflake", …)` sets `paramstyle` to `qmark` before connecting, `execute` returns an object with `fetchone`/`fetchall`/`description`, `executemany` and `close` reach the cursor and connection |
| 1 | `tests/test_snowflake_seam.py::test_run_sql_file_runs_every_statement_of_a_file_on_both_branches` — a three-statement file: DuckDB leaves three effects; the fake records one `execute_string` call carrying all three |
| 1 | `tests/test_snowflake_seam.py::test_each_branch_folds_its_drivers_error_into_the_seams_one_type` — the fake raises its own `Error`; the caller catches `warehouse.DriverError`; a DuckDB syntax error is the same type; `tests/test_snowflake_seam.py::test_a_missing_extra_is_one_refusal_line_naming_the_sync_command` — `sys.modules["snowflake"] = None`; `tests/test_warehouse.py::test_wired_is_exactly_the_targets_connect_opens` (rewritten: both targets open, the fake standing in for the second); `tests/test_ingest_layout.py::test_no_module_outside_the_seam_imports_a_database_driver` (existing) |
| 2 | `tests/test_snowflake_seam.py::test_catalog_answers_are_case_folded_on_both_branches` — the fake answers `STG_REVIEWS`/`RATING`; `tables`, `columns`, `table_exists("stg_reviews")` agree with DuckDB's answers for the same schema; `tests/test_rebuild.py::test_table_counts_reads_the_default_schema_from_the_engine` (existing, now through the seam) |
| 2 | `tests/test_ingest_layout.py::test_no_module_outside_the_seam_queries_the_catalog` — `information_schema` and `current_schema` planted in `build.py` or `panels.py` fail it; `tests/test_beat2.py::test_the_mart_probe_sees_only_the_default_schema` (existing, through the seam) |
| 3 | `tests/test_snowflake_seam.py::test_location_for_is_a_file_per_input_on_duckdb_and_a_schema_per_input_on_snowflake` — `location_for("duckdb", rows, root) == database_for(rows, root)` for every input; `location_for("snowflake", "synthetic")` is `friction_ledger_synthetic`; `captured`/`samples` raise naming input and target |
| 3 | `tests/test_cli.py::test_cli_refuses_a_corpus_input_on_the_cloud_target_on_every_path` — parametrised over `rebuild` × four stages, `idempotency-check`, `publish` (via `study.metabase`): `TARGET=snowflake ROWS=captured\|samples` is one line, exit 2, nothing connected (the fake's `connect` never called) |
| 3 | `tests/test_snowflake_seam.py::test_scratch_creates_and_drops_a_schema_that_is_no_inputs_own` — the fake records `create schema` then `drop schema` on the same name, the drop also after a raised error inside the block, and the name is not `location_for` of any input; on DuckDB the scratch is a temp directory removed on exit; `tests/test_cli.py::test_cli_reset_refuses_non_duckdb_target` (existing, kept: `reset` stays on the file) |
| 4 | `tests/test_snowflake_seam.py::test_the_classify_step_writes_land_on_the_target` — `classify_step(..., target="snowflake")` over the fake: every `delete`/`insert` into `stg_classified_reviews`, the three post-classify marts, `pipeline_row_counts` and `classifier_quality` is recorded by the fake and none by a DuckDB file; `tests/test_cli.py::test_cli_rebuild_refuses_a_target_the_seam_cannot_open` (existing, now over `WIRED` alone for every stage; the `CLASSIFY_TARGETS` test deleted with the constant) |
| 4 | `tests/test_rebuild.py::test_idempotency_check_counts_on_the_target` — the fake sees both rebuilds and both count reads; the DuckDB call is unchanged (`tests/test_idempotency.py`, existing) |
| 4 | `tests/test_makefile.py::test_publish_passes_target_and_rows_unexpanded_as_one_literal` — `make -n publish` shows `--target=… --rows=…` only, both origins; `tests/test_metabase_apply.py::test_export_command_refuses_a_target_outside_wired_by_name` and `::test_export_reads_the_named_targets_marts` (the fake's connection is the one read) |
| 5 | `tests/test_snowflake_seam.py::test_a_missing_credential_is_refused_by_name_and_no_value_is_printed` — each of the five required variables unset in turn: one line naming the missing names; a set value never appears in stdout or stderr; `SNOWFLAKE_ROLE` absent is not a refusal |
| 5 | `tests/test_snowflake_seam.py::test_a_driver_refusal_is_one_line_naming_the_class_and_the_variables_not_the_message` — the fake's `connect` raises with a message carrying a planted value; the CLI line carries the class name and the variable names and not the value; `tests/test_ingest_layout.py::test_ingest_never_reads_env_or_credentials` (existing) and `::test_credential_names_are_read_in_the_seam_only` — `SNOWFLAKE_` outside `pipeline/warehouse.py`, `.env.example` and `tests/` is a hit |
| 5 | `tests/test_cli.py::test_env_scrub_covers_every_snowflake_variable` — `_scrub_env`'s set covers every name the seam reads (read from the seam's own tuple); `tests/test_no_key.py::test_no_key_rebuild_classify_step_is_green` (existing) |
| 6 | `pipeline/DEMONSTRATION.md` — the pasted count table, the `idempotency-check OK` line, the schema name; `make check-docs` scans it; `tests/test_snowflake_seam.py::test_demonstration_doc_exists_and_names_no_account_or_host` — the doc exists, links resolve, and carries no `.snowflakecomputing.com`, no `SNOWFLAKE_ACCOUNT=` value, no `https://` |
| 6 | CI: `make rebuild ROWS=synthetic`, `make idempotency-check`, `make study` + `git diff --exit-code`, `make rebuild ROWS=samples` + `make idempotency-check ROWS=samples` (existing steps, no extra installed); `tests/test_offline.py` and `tests/conftest.py::_no_network` (existing — no socket in the suite) |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For every module outside `pipeline/warehouse.py`, the code path is the same on both targets: no engine name, driver import, catalog query, schema name or credential name is spelled there. | `tests/test_ingest_layout.py::test_no_module_outside_the_seam_spells_an_engine_name`, `::test_no_module_outside_the_seam_imports_a_database_driver`, `::test_no_module_spells_an_engines_schema_name` (existing), `::test_no_module_outside_the_seam_queries_the_catalog`, `::test_credential_names_are_read_in_the_seam_only` (new) — a planted literal, import, `information_schema`, `current_schema` or `SNOWFLAKE_` outside the seam |
| 2. For every (input, target) pair, a rebuild lands in a location that belongs to that pair and to nothing else, and the corpus inputs have no cloud location. | `tests/test_snowflake_seam.py::test_location_for_is_a_file_per_input_on_duckdb_and_a_schema_per_input_on_snowflake`; `tests/test_cli.py::test_cli_refuses_a_corpus_input_on_the_cloud_target_on_every_path`; `tests/test_rebuild.py::test_the_database_file_is_derived_from_the_input_never_named` (existing) |
| 3. For every catalog answer the seam gives, names are lower case on both engines, so an equality on a table or column name holds the same way on both. | `tests/test_snowflake_seam.py::test_catalog_answers_are_case_folded_on_both_branches` — the fake's upper-cased answers |
| 4. For every refusal on the cloud path — a missing extra, a missing variable, a driver error, a corpus input — the process prints one line naming names and exits 2, never a value and never a traceback. | `tests/test_snowflake_seam.py::test_a_missing_extra_is_one_refusal_line_naming_the_sync_command`, `::test_a_missing_credential_is_refused_by_name_and_no_value_is_printed`, `::test_a_driver_refusal_is_one_line_naming_the_class_and_the_variables_not_the_message`; `tests/test_cli.py::test_cli_refuses_a_corpus_input_on_the_cloud_target_on_every_path` |
| 5. For every run of the suite, of CI and of any target with `TARGET` unset or `duckdb`, no driver but DuckDB is imported, no `SNOWFLAKE_*` value is read, no socket opens, and every output is 10a's output. | `tests/conftest.py::_scrub_env` and `::_no_network` over the whole suite; `tests/test_snowflake_seam.py::test_the_duckdb_branch_never_imports_the_connector` — `sys.modules` after a DuckDB rebuild holds no `snowflake`; CI's `make study` + `git diff --exit-code`; `tests/test_rebuild.py`'s pinned counts |
| 6. For every path that takes a target, every connection it opens — the build, the classify step, the count, the export — is on that target. | `tests/test_snowflake_seam.py::test_the_classify_step_writes_land_on_the_target`; `tests/test_rebuild.py::test_idempotency_check_counts_on_the_target`; `tests/test_metabase_apply.py::test_export_reads_the_named_targets_marts` — the fake records every connection opened and a DuckDB file records none |
| 7. For every scratch the seam hands out, it exists for the block and not after, whatever happens inside the block, and it is never an input's own location. | `tests/test_snowflake_seam.py::test_scratch_creates_and_drops_a_schema_that_is_no_inputs_own` |

## Pinned decisions (do not re-litigate)

- **Both branches are wrappers with one shape; the seam owns the error type;
  the connector is an optional extra imported inside its branch.** DuckDB's
  connection already has the shape (`execute` returns the connection, which
  carries `fetchone`/`fetchall`/`description`); the wrapper over it is one
  thin class so that `DriverError` can be a seam-owned class both branches
  fold into, and so the DuckDB-only pandas-probe guard has a DuckDB-only
  home. The Snowflake wrapper sets `paramstyle = "qmark"` on the connector
  module before connecting (the module-level setting the connector documents;
  the seam is the only importer, so nothing else observes it), runs
  `run_sql_file` through `execute_string` (the connector's multi-statement
  entry: every `sql/` file holds two to eight statements), and folds
  `snowflake.connector.Error` into `DriverError`. The extra keeps `uv sync
  --locked`, CI and `make setup` connector-free (#17) — the DuckDB path is
  the permanent one and must not grow a cloud dependency. *Rejected: a
  `DriverError = (duckdb.Error, snowflake.connector.Error)` tuple (imports
  the connector on the DuckDB path); the connector as a plain dependency
  (every laptop clone downloads a cloud driver it never uses); rewriting
  `build.py`'s placeholders per engine (the SQL would fork).* Satisfies
  invariants 1, 4, 5.
- **Catalog reads are three seam functions with lower-cased answers;
  `information_schema` and `current_schema` are spelled in the seam only.**
  Snowflake upper-cases unquoted identifiers, so `table_name = 'stg_reviews'`
  lists nothing there while DuckDB answers `stg_reviews`: the compare folds
  in the seam, once, and every caller (`_columns`, `_table_exists`,
  `table_counts`, the mart probe) becomes a call. `check_raw_declaration`'s
  scratch table and its column compare keep their logic in `build.py` and
  read through `warehouse.columns`. *Rejected: quoting every identifier in
  `sql/` (a rewrite of every file for one engine's folding rule, and a
  reader-hostile SQL); a per-engine `table_schema` literal (the row-33
  mutation the suite could not see).* Satisfies invariants 1, 3.
- **A location per (input, target), from the seam; the cloud holds fixture
  inputs only; the idempotency scratch is a seam context manager; `reset`
  stays the DuckDB file.** `location_for` generalises `database_for` (which
  stays, unchanged, for the laptop callers — `study/export.py`,
  `label_sample.py`, `classify-eval`, the tests): a file per input on DuckDB,
  the schema `friction_ledger_<input>` per input on Snowflake, and no
  answer for `captured` or `samples` on the cloud — the refusal the CLI
  prints on every target-taking path (#1). `scratch(target, rows)` is a temp
  directory on DuckDB and a `create schema`/`drop schema` pair on Snowflake
  (`try`/`finally`), named so it can never equal an input's location (#7).
  `reset` deletes laptop files and refuses the cloud target by name as today:
  a `make` target must not drop a cloud schema (Conventions: destructive
  commands are the `confirm` gate's, and the gate is a goal, not a value the
  network would see). *Rejected: one shared schema for every input (the
  samples fixture in the synthetic tables — 10a's `database_for` argument
  again); a `SNOWFLAKE_SCHEMA` variable (an input's location chosen by the
  environment, A8 (e)); `make confirm reset TARGET=snowflake` dropping the
  schema (a destructive network act from make).* Satisfies invariants 2, 7.
- **`TARGET` threads by parameter through `classify_step`,
  `idempotency_check` and `publish`; `study`, `label-sample` and
  `classify-eval` stay on the laptop file.** The three that take a target
  today already resolve it against the seam; the classify step's own set
  (`CLASSIFY_TARGETS`, 10a review round 2 #10) existed only to refuse what
  this phase wires, and goes. The page renders the frozen synthetic input by
  the 9a contract and is a tracked file — a second engine under it is a
  second render path for bytes CI diffs; `label-sample` draws from the
  corpus, which has no cloud location; `classify-eval` reads the synthetic
  laptop file the eval gate was written against. *Rejected: `TARGET` on
  `study` (a tracked byte-identical page over two engines' float formatting);
  a global "current target" (hidden state — 10a's rejection).* Satisfies
  invariant 6.
- **Six `SNOWFLAKE_*` strings, read by name in the seam, refused by name;
  credential-gated, not `confirm`-gated.** The names are the connector's own
  parameters; `SNOWFLAKE_PASSWORD` carries a password or a programmatic
  access token — a string either way, so no variable ever names a file (#9;
  `secure-by-construction`: a secret is never a path the code opens). The
  refusal lists missing names; a driver refusal names its class and the
  variables and never relays the driver's message (it can carry the account
  or the host). The path runs when the credentials are exported and refuses
  when they are not, like the model key: the `confirm` gate arms a closed
  goal set from make's own goal list and knows no variable, so gating one
  `TARGET` value would make the gate value-aware — the design 3a refused.
  `_scrub_env` covers the names so an exported `.env` in the developer's
  shell cannot reach a test. *Rejected: key-pair authentication (a private
  key file on disk named by a variable — the path-valued secret #9 refuses);
  `make confirm rebuild TARGET=snowflake` (a value-aware gate).* Satisfies
  invariants 4, 5.
- **The demonstration is text: the count table, the idempotency line, the
  schema name — no console screenshot.** #15 verbatim. A screenshot of the
  Snowflake console shows the account locator in its address bar and the
  user in its corner; a terminal screenshot adds nothing to the pasted
  table and is not diffable. The brief's "screenshot" is 10a's DAG grid;
  the deviation is one DECISIONS line. The DuckDB count table for the same
  input sits beside it in the doc, table for table equal — the "both targets
  run green" of brief §9, printed. *Rejected: a redacted console screenshot
  (a hand edit the reviewers cannot verify); the count tables asserted
  byte-equal in a test (the cloud is never in the suite).* Satisfies the
  central constraint; evidence rows 15, 16.

## Scope (files)

- `pipeline/warehouse.py` — the wrapped connection (both branches),
  `DriverError` as a class, `WIRED = TARGETS`, `CLOUD`, `location_for`,
  `scratch`, `tables`/`columns`/`table_exists`, the credential read, the
  lazy import; `default_schema` becomes internal.
- `pipeline/build.py` — `_columns`/`_table_exists`/`table_counts` through the
  seam; `_no_pandas_probe` and `_insert_rows`' guard move out; `classify_step`
  and `_staged_review_rows` take `target`; `idempotency_check` over
  `scratch`; `CLASSIFY_TARGETS` deleted; `rebuild` over `location_for`.
- `pipeline/cli.py` — `TARGET` against `WIRED` on every stage; the corpus
  refusal on the cloud target; `_classify_and_print(location, rows, target)`.
- `study/metabase/export.py`, `study/metabase/__main__.py` — `--target`;
  `build_sqlite(target, location)`. `study/panels.py` — the mart probe
  through `warehouse.table_exists`.
- `Makefile` — `publish [TARGET=]`; `make help` lines for `rebuild`,
  `idempotency-check`, `publish` naming both targets.
- `pyproject.toml` (the `snowflake` extra, the allowlist comment), `uv.lock`
  (re-locked once), `.env.example` (six placeholders).
- `tests/fake_snowflake.py` (new — the recording fake connector module),
  `tests/test_snowflake_seam.py` (new), `tests/conftest.py` (`_scrub_env`),
  `tests/test_warehouse.py`, `tests/test_cli.py`, `tests/test_ingest_layout.py`,
  `tests/test_rebuild.py`, `tests/test_makefile.py`,
  `tests/test_metabase_apply.py`, `tests/test_beat2.py`, `tests/pins.py`.
- `pipeline/DEMONSTRATION.md` (new — the walk, the pasted tables, and the
  credit-spend caution).
- `README.md` (Running it: the cloud run in one paragraph — the extra, the
  six names, fixture inputs only, the caution that an exported `.env` lets any
  process in that shell spend trial credits, and the one sentence on why a
  wrapper and an extra rather than an ORM), `CLAUDE.md` (Commands: `TARGET` on the three
  targets, `make setup` drops the extra; Conventions allowlist; Repo map;
  Current status; BACKLOG count), `DECISIONS.md`, `BACKLOG.md`,
  `docs/PLAN.md` (§5 row 10: 10b delivered), this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 10b entry (the six pinned decisions with their
  rejected alternatives; the screenshot deviation; challenge disposition);
  the "still in force" seam bullet updated (Snowflake wired, not
  "Phase-10b"); Gotchas for every connector or dialect surprise the first
  hour finds
- [ ] `BACKLOG.md` — rows 33 and 50 closed (struck + "DONE Phase 10b"); the
  count in CLAUDE.md updated
- [ ] `LESSONS.md` — round 1 reported the `site-fix` class (the corpus guard
  missed the `scratch` site): that row gains the 10b instance; the
  `unshaped-input` row's fix/idempotency-classify clause is updated to the
  renamed idempotency-check test and its 10b closure
- [ ] `specs/phase-1-schema.md` — the two Evidence/Invariant cites of the
  retired `test_snowflake_target_defers_to_phase_10` annotated as superseded in
  10b (a dated annotation of the historical record, not a rewrite)
- [ ] `CLAUDE.md` — Current status (Phase 10 complete); Commands (`TARGET`
  on `rebuild`, `idempotency-check`, `publish`; the extra; `WIRED` no longer
  "duckdb alone"); Conventions allowlist (10b landed); Repo map
  (`pipeline/DEMONSTRATION.md`); BACKLOG count
- [ ] BACKING.md — none: no row's tag or source changes (the cloud run feeds no number)
- [ ] SPEC.md — none: no chart or beat changes
- [ ] `README.md` — Running it (the cloud run paragraph)
- [ ] `docs/PLAN.md` — §5 row 10 marks 10b delivered
- [ ] `specs/phase-10b-snowflake.md` — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

Three existing targets accept a second `TARGET` value (`rebuild`,
`idempotency-check`) or gain the variable (`publish`); with that value each
touches the network (the connector's HTTPS to the account) and spends trial
credits (warehouse seconds). Nothing new deletes: `reset` keeps its DuckDB
set and a cloud schema is the developer's console act. No paid API is added:
the classify step on the cloud target calls the model exactly as on the
laptop — when a key is set, for uncached rows only, through the one call
site.

Settled shape (unchanged): one Python process validates the value, derives
every location from it, then acts; every recipe is one line; every user
variable reaches Python unexpanded and single-quoted and is `unexport`ed.
`TARGET` and `ROWS` are already on that list.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `rebuild TARGET=` (every `STAGE`) | → `duckdb`, today's behaviour | refused by name, exit 2: not in `WIRED` | refused by name, exit 2 (one literal, never a shell word) | validated the same; the recipe reads `$(value TARGET)` | n/a — no confirm gate; the cloud path is credential-gated | `tests/test_cli.py::test_cli_rebuild_refuses_a_target_the_seam_cannot_open` (existing, over `WIRED`), `tests/test_makefile.py::test_pipeline_variables_reach_python_as_one_literal` (existing, `TARGET`) |
| `rebuild TARGET=snowflake ROWS=` | `ROWS` empty → `captured` → refused: the corpus has no cloud location | refused by name (`INPUTS`) | refused by name | the same | n/a | `tests/test_cli.py::test_cli_refuses_a_corpus_input_on_the_cloud_target_on_every_path` |
| `idempotency-check TARGET=` | → `duckdb` | refused by name | refused by name | the same | n/a | `tests/test_cli.py::test_cli_idempotency_check_refuses_a_target_outside_wired` (renamed from `..._refuses_non_duckdb_target`: snowflake is now valid, a target outside `WIRED` is refused); the corpus-input test above |
| `publish TARGET=` | → `duckdb` (10a's behaviour) | refused by name, exit 2 (`resolve_choice` over `WIRED`) | refused by name | the same | n/a | `tests/test_makefile.py::test_publish_passes_target_and_rows_unexpanded_as_one_literal`; `tests/test_metabase_apply.py::test_export_command_refuses_a_target_outside_wired_by_name` |
| the credentials (`SNOWFLAKE_*`) | a required one missing → one line naming the missing names, exit 2, nothing connected | n/a — no variable is a path; a value is handed to the connector as a string and never opened as a file | n/a — no shell; the connector builds the request | the ONLY way they arrive (the exported `.env`); never a command-line variable, never Actions, never the suite (`_scrub_env`) | n/a | `tests/test_snowflake_seam.py::test_a_missing_credential_is_refused_by_name_and_no_value_is_printed`, `::test_a_driver_refusal_is_one_line_naming_the_class_and_the_variables_not_the_message`; `tests/test_cli.py::test_env_scrub_covers_every_snowflake_variable`; `tests/test_ingest_layout.py::test_credential_names_are_read_in_the_seam_only` |

Run twice: a second cloud rebuild is the idempotent rebuild (raw append-only;
the same fixture inserts nothing) and costs another few warehouse seconds; a
second `publish` writes identical bytes. No credentials: the cloud path
refuses by name before any socket; the DuckDB path never reads them. What the
gate does not hold against, stated: a developer's shell with `.env` exported
lets any process in that shell — an agent's `make rebuild TARGET=snowflake`
included — reach the trial with the fixture inputs; the corpus refusal
(invariant 2) bounds the data such a run can hold but not the trial credits it
spends, and the `ask-gate` hook does not prompt for it (it prompts for `make
confirm`); `pipeline/DEMONSTRATION.md` and README carry a caution line, and
stack risk 5 confirms auto-suspend is on so a forgotten warehouse does not bill
idle time. What the trial holds at
most: the synthetic fixture's hand-written reviews and the `none` input's
empty tables, in two schemas, plus a scratch schema during a check.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `pipeline/**`, `study/**/*.py`, `Makefile`,
  `tests/`): the wrapper is one shape and one class per branch, the catalog
  fold happens once, `location_for` and `scratch` are the only location
  sources, `classify_step` opens nothing on `LOCAL`, the refusals sit at the
  CLI boundary (LESSONS `traceback-at-boundary`), the deleted
  `CLASSIFY_TARGETS` leaves no reference (Before reporting DONE #1), scope.
- **security-reviewer** (mandatory — `pipeline/warehouse.py`,
  `pipeline/cli.py`, `.env.example`, credentials, a network path, a new
  dependency): the six names read in the seam only, a value never printed or
  relayed, the corpus refusal on every path, the extra's pin and the
  lock, the fake driver in `tests/` opening no socket, the demonstration
  text carrying no account or host.
- **functionality-tester** (triggered): the DONE command; the negative tests
  (`TARGET=snowflake ROWS=captured` on each path, each credential unset in
  turn, `sys.modules["snowflake"] = None`, a planted `information_schema` in
  `build.py`, a planted `SNOWFLAKE_` read in `cli.py`, a fake that raises
  mid-`scratch`); the no-key run; the run-twice check; the DuckDB counts
  unchanged.
- **study-editor** (triggered — `README.md`, `CLAUDE.md`,
  `pipeline/DEMONSTRATION.md`): the Teaching-rule sentences, the two-layer
  voice of the cloud paragraph, the demonstration's caption ("synthetic
  fixture data — not a study finding"), no insurer named, no banned word.
- **coherence-auditor** at exit (mandatory, whole repo — Phase 10 is
  complete): every "until Phase 10b" / "Phase 10b threads" sentence gone
  (`warehouse.py`'s docstring, `WIRED`'s comment, `build.py`'s classify-step
  and idempotency docstrings, `cli.py`'s comments, `pyproject.toml`'s
  allowlist comment, `tests/test_warehouse.py::test_snowflake_target_defers_to_phase_10`
  and the `refuses_non_duckdb_target` names, CLAUDE.md Commands "duckdb
  alone until Phase 10b", DECISIONS "still in force", BACKLOG 33 and 50,
  PLAN §5); `make help` ↔ CLAUDE.md Commands ↔ README "Running it" agree on
  `TARGET` and the extra; the DuckDB counts in `tests/pins.py` untouched.
- **Stack risk (verify in the first hour, against the official docs; STOP and
  report before any workaround — Workflow rules → Stack surprises; log under
  DECISIONS → Gotchas):**
  1. **The trial's login policy.** Snowflake enforces multi-factor
     authentication on password logins for human users on new accounts;
     the string alternatives are a programmatic access token in
     `SNOWFLAKE_PASSWORD` or a user of type `SERVICE`. Confirm which the
     trial accepts before wiring the branch; a key-pair file is not an
     option (pinned decision 5).
  2. **Multi-statement files and transactions.** `execute_string` runs each
     `;`-separated statement; confirm it honours `begin transaction` …
     `commit`/`rollback` — including the direct `conn.execute("begin
     transaction")`/`commit`/`rollback` calls `build.py` issues on one wrapped
     cursor with autocommit off, not only the statements inside `execute_string`
     — and that `create or replace table … as select` with `text`,
     `decimal(2,1)` and a window function runs as written in `sql/`.
  3. **Case-folding and the catalog's spellings.** `information_schema`
     answers upper-cased names; confirm `is_nullable` (`YES`/`NO`),
     `ordinal_position` and `data_type` spellings so `check_raw_declaration`'s
     scratch compare reads both sides in the engine's own words as designed.
  4. **`qmark` binding of the raw loaders' form.** The append-only insert is
     `insert … select ?, … where not exists (…)`; confirm the connector binds
     a `Decimal`, a `date` string and a `bool` through `select ?` without a
     cast, else the seam's branch is the place for the difference, never
     `sql/`.
  5. **Credits.** A synthetic rebuild is seconds on the smallest warehouse;
     confirm the trial's auto-suspend is on so a forgotten warehouse does
     not bill idle time.

## Out of scope (deferred, recorded)

- **A cloud `reset`.** Dropping the two fixture schemas and any stale scratch
  is the developer's console act; a `make` target that deletes on the
  network is refused by pinned decision 3. Reopen only if a schema is ever
  left behind by a crash the `finally` did not reach — then a BACKLOG row.
- **The corpus on the cloud.** Refused by construction (invariant 2), by
  brief §2.5; not a deferral — a boundary.
- **`make study` over the captured corpus** (BACKLOG, opened by 10a) and
  **B2.1 in the HTML page** (BACKLOG, 9g), **the per-review drill's public
  address** (BACKLOG, 9b) — untouched.
- **The DAG on the cloud target.** The DAG holds no `TARGET` (10a, invariant
  1: no input choice under `dags/`); a company run would set `TARGET` in its
  environment as the demonstration sets `ROWS`. Nothing to build; one
  sentence in `dags/DEMONSTRATION.md` is not needed because the compose
  already documents the environment path.

## Delivered (2026-09-13)

The warehouse seam's second branch, wired and proved offline. Both engines
return one connection shape (`execute`/`executemany`/`executescript`/`close`)
and fold their driver's error into `warehouse.DriverError`; the Snowflake
connector is an optional extra (`uv sync --extra snowflake`) imported lazily
inside its branch, so the DuckDB path loads no cloud driver and a missing extra
is one refusal line. The DuckDB-only no-pandas probe moved into the DuckDB
`executemany`. Catalog reads became three seam functions
(`tables`/`columns`/`table_exists`), case-folded, so `information_schema`,
`current_schema` and the six `SNOWFLAKE_*` names live in the seam alone — two
new layout guards in `tests/test_ingest_layout.py`, the class of BACKLOG row 33.
`location_for` gives every (input, target) its own location and refuses a corpus
input on the cloud target; `scratch` is a temp dir on DuckDB and a create/drop
schema on Snowflake, `reset` stays the DuckDB file. `TARGET` threads by
parameter through `classify_step`, `idempotency_check` and the Metabase export;
`CLASSIFY_TARGETS` is gone and every CLI stage resolves against `WIRED`, closing
BACKLOG row 50. Six credentials read by name in the seam, refused by name, never
printed, scrubbed from the suite; credential-gated, not `confirm`-gated. The
whole was proved against `tests/fake_snowflake.py` (a recording fake connector,
no socket): the qmark cursor, `execute_string`, the error fold, the case-fold,
`scratch`, the classify-path writes on the target, the credential and driver
refusals, the corpus refusal on every path. The DuckDB path is byte-for-byte
10a's — the study page unchanged, the counts unchanged, no extra installed, no
socket. `pipeline/DEMONSTRATION.md` walks the developer's one cloud run; its
Snowflake count table and schema name, and the connector/dialect Gotchas of the
first hour, are recorded Documented-by-hand after the run (the fake→real trust
boundary; done-when 6). Challenge round 1 approved with amendments (findings
1/2/3/5/6 amended, 4 rejected); Phase 10 completes when this merges.
