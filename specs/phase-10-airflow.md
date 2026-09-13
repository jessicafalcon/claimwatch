# Phase 10 — the Airflow DAG and the Snowflake demonstration (PROPOSED)

Contract for the `phase-10-airflow` branch. Source: PROJECT_BRIEF.md §9 Phase 10
("Wrap the working steps in the one-screen DAG; run once against a Snowflake
trial; screenshot; confirm the DuckDB path still passes"), §4 (the DAG of five
tasks, the one-flag warehouse), §4.4 (the "Full (demonstration)" run mode);
`docs/PLAN.md` §5 row 10 and §2 ("Airflow contains no logic" — BashOperators
over `make` targets, five tasks, one screen). Depends on Phase 9i merged (PR
#34) and the four small PRs after it (#35–#38), all on `main` 2026-09-13.

**Status: PROPOSED — do not start until approved.** One new Python package,
pre-approved for this phase by CLAUDE.md → Conventions:
`snowflake-connector-python`, declared as an **optional extra** (`uv sync
--extra snowflake`), imported inside the Snowflake branch of the one seam and
nowhere else, so the DuckDB path installs and runs without it (brief §4.4: "no
accounts"). Airflow runs via Docker only (Conventions), like Metabase in 9g.
The phase is **non-CI** in the 9g shape: an offline, CI-checkable core (the
DAG file's shape, the stage split of `rebuild`, the `publish` target, the
seam's refusals, the `TARGET` threading) plus a developer-run demonstration
(the Airflow run and the one Snowflake run, both over hand-written synthetic
reviews, recorded with screenshots).

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

*The stack, in plain words (Teaching rule).* **Airflow** is a scheduler that
runs a list of commands in a fixed order and shows each run as a row of green
or red boxes; the list is written as a small Python file called a **DAG**
(directed acyclic graph — steps with arrows, no loops). A **BashOperator** is
the kind of step that runs one shell command; ours each run one `make`
target, so the DAG holds no logic of its own and the same commands run by hand
on a laptop. **Snowflake** is a cloud database; our SQL is plain enough to run
there unchanged, and one file (`pipeline/warehouse.py`) is the only place that
knows which engine it is talking to. The brief keeps both as a demonstration:
run once, screenshot, keep the config; the laptop path (DuckDB) stays the
permanent one.

## Why

Beat 5 promises the reproducibility section a DAG diagram beside the row counts
and the one rebuild command (brief §3 Beat 5), the architecture names one
Airflow DAG as the thing that runs scrape → load_raw → clean → classify →
publish (brief §4; CLAUDE.md → Architecture), and §4.4 promises a "Full
(demonstration)" run mode on Snowflake with the same SQL. None of that exists:
there is no `dags/`, `TARGET=snowflake` raises a deliberate Phase-10
`NotImplementedError`, and three parts of the pipeline open a DuckDB connection
by name whatever `TARGET` says (BACKLOG "The classify-step mart writes are not
warehouse-aware"). This is the last phase of the brief; it is a phase, not a
fix PR, because it adds a package, a new top-level directory, two `make`
surfaces and a threading change across the build.

Two things the brief's one-line phase leaves open, decided here:

- **The five tasks versus the existing targets.** `make rebuild` already runs
  load, clean and classify in one process. The DAG's three middle tasks are the
  three stages of that one function, selected by a closed `STAGE` variable —
  not three re-implementations and not one task named `rebuild` with the brief's
  names dropped.
- **What "publish" runs.** `python -m study.metabase export|apply` are module
  commands, not `make` targets (CLAUDE.md → Current status). The DAG's
  `publish` task is a new `make publish` that writes the file Metabase reads
  (the SQLite export); `apply` stays developer-run because it needs a running
  Metabase and credentials. The permanent HTML page is not re-rendered by the
  DAG: `make study` renders the committed page over the frozen synthetic input
  by contract (9a), and a DAG run must not rewrite a tracked file.

## The central constraint

**The DuckDB path is unchanged in behaviour: every existing target, test and
committed artifact runs and reads the same with no Snowflake package
installed, no `SNOWFLAKE_*` variable set, no Docker and no key.** The phase
adds an engine branch, a stage selector and two files; it moves no number,
re-freezes no fixture, changes no BACKING tag, and leaves
`study/friction_ledger.html` byte-identical. The brief's own DONE line — "both
targets run green" — is read as: the Snowflake run once, and the DuckDB run
green *after* it.

## DONE command

```
make idempotency-check ROWS=synthetic && make rebuild ROWS=synthetic STAGE=load && make rebuild ROWS=synthetic STAGE=clean && make rebuild ROWS=synthetic STAGE=classify && make publish ROWS=synthetic && uv run pytest tests/test_dag.py tests/test_warehouse.py tests/test_rebuild.py tests/test_cli.py -q
```

- `make idempotency-check ROWS=synthetic` — the run-twice property over the
  whole pipeline (classify step included, PR #35), now through a seam call
  that takes the caller's `TARGET` (default DuckDB); every count unchanged on
  the second run.
- the three `make rebuild … STAGE=` calls in order — the DAG's middle three
  tasks, run by hand; the table counts they leave equal the counts one
  `make rebuild ROWS=synthetic` prints (pinned in `tests/test_rebuild.py`).
- `make publish ROWS=synthetic` — the DAG's last task: writes
  `data/metabase/metabase.sqlite` from the synthetic marts, byte-identical on a
  rerun, needing no credentials and no network.
- `uv run pytest tests/test_dag.py tests/test_warehouse.py tests/test_rebuild.py
  tests/test_cli.py -q` — the DAG file's shape (five `make` tasks, no logic),
  the seam's refusals by name with no socket and no driver import, the stage
  split's equality, and the CLI's closed `STAGE` set and the two-target
  `idempotency-check`.

The `scrape` task is not in the DONE command: it is the network target
(`make confirm scrape`, developer-run), unchanged by this phase.

## Done-when

1. **The DAG is five `make` tasks in the brief's order and holds no logic.**
   `dags/friction_ledger.py` declares one DAG (`dag_id="friction_ledger"`,
   `schedule=None`, `catchup=False`) of five `BashOperator`s with task ids
   `scrape`, `load_raw`, `clean`, `classify`, `publish`, chained linearly, each
   `bash_command` one `make` invocation of a target `make help` lists
   (`confirm scrape`, `rebuild STAGE=load`, `rebuild STAGE=clean`, `rebuild
   STAGE=classify`, `publish`) run from the repo root; the file imports Airflow
   and the stdlib only, defines no function, no branch and no SQL, and fits on
   one screen (≤ 40 lines). Airflow is never imported by the suite: the test
   reads the file with `ast`. *Evidence: rows 1, 2.*
2. **`rebuild` runs one stage at a time and the stages add up to the whole.**
   `make rebuild [STAGE=all|load|clean|classify]` (default `all`, validated in
   Python against the closed set) runs `load` (raw DDL + every load for the
   input), `clean` (staging + marts + the model, simulator and facts writers) or
   `classify` (the classify step) into the input's own file; the three in order
   leave, table for table, the counts one whole rebuild leaves; a stage run twice
   adds nothing; `clean` and `classify` over a file with no earlier stage refuse
   in one line naming the missing table. *Evidence: rows 3, 4, 5.*
3. **`make publish [ROWS=]` writes the file Metabase reads, and nothing else.**
   It calls `study.metabase export` for the named input (default `captured`),
   byte-identical on a rerun, refusing a missing warehouse by name; it rewrites
   no tracked file and needs no credentials. `apply` stays a module command,
   developer-run. *Evidence: rows 6, 7.*
4. **The seam's Snowflake branch is real, credentialed from the environment, and
   refuses by name.** `pipeline/warehouse.py::connect("snowflake")` reads
   `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_WAREHOUSE`,
   `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA` and one secret (`SNOWFLAKE_PASSWORD`
   or the token/key the first hour settles — stack risk 3) from the environment,
   refuses a missing one in one line naming the variable and never a value,
   opens no socket before every name is present, and imports the connector
   inside the branch — a missing package is refused by name with the `uv sync
   --extra snowflake` line. `.env.example` carries the placeholders.
   *Evidence: rows 8, 9, 10.*
5. **Every data-path connection takes the caller's `TARGET`, so a target's
   tables land in that target's warehouse.** The classify step
   (`pipeline/build.py::classify_step`, its staged-review read and its mart
   writes), `idempotency_check`, the Metabase export's mart reads and the study
   export's read open their connections through the seam with the `TARGET` they
   were given; the engine names are spelled in `pipeline/warehouse.py` only
   (`TARGETS` and a `LOCAL` constant), never as a literal elsewhere;
   `idempotency-check` accepts both targets (`reset` stays DuckDB-only: it
   deletes files). The no-key run stays green. *Evidence: rows 11, 12, 13, 14.*
6. **The demonstration is committed, over synthetic reviews only, and the DuckDB
   path is green after it.** `dags/DEMONSTRATION.md` records (a) the Airflow run:
   the one-container compose under `dags/` brought up, the DAG parsed, the five
   tasks green, one screenshot of the grid captioned *synthetic fixture data —
   not a study finding*; (b) the Snowflake run: `make rebuild TARGET=snowflake
   ROWS=synthetic` and `make idempotency-check TARGET=snowflake ROWS=synthetic`
   with their printed counts, the schema name `default_schema` returned there
   (closes the BACKLOG row "The Snowflake half of `default_schema` is
   unpinnable offline"), and any dialect surprise logged under DECISIONS →
   Gotchas; (c) `make rebuild` on DuckDB green afterwards. No captured review
   leaves the laptop: both runs load `ROWS=synthetic`. The README's Beat 5 and
   the page's B5.2 panel name the DAG file; SPEC B5.2 and BACKING B5.2 cite it.
   *Evidence: rows 15, 16, 17.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_dag.py::test_the_dag_is_five_make_tasks_in_the_briefs_order_with_no_logic` — `ast` over `dags/friction_ledger.py`: five `BashOperator` calls, the task-id tuple in order, one `>>` chain, no `def`/`if`/`for`, ≤ 40 lines, imports from `airflow`/`datetime` only |
| 1 | `tests/test_dag.py::test_every_dag_task_runs_one_declared_make_target` — each `bash_command` is `cd <root> && make <goal…>` whose goals are in `scripts/review_common.py::make_targets`, and variables in it are in the CLI's closed sets |
| 2 | `tests/test_rebuild.py::test_three_stages_in_order_equal_one_whole_rebuild` — `table_counts` after `load`, `clean`, `classify` equal one `rebuild` + `classify_step` over the same input |
| 2 | `tests/test_rebuild.py::test_a_stage_run_twice_adds_no_rows` and `::test_clean_or_classify_before_load_refuses_naming_the_missing_table` |
| 2 | `tests/test_makefile.py::test_stage_is_a_closed_set` — empty → `all`; `load`/`clean`/`classify` accepted; `../x`, `"; `, `Load`, `all,load` refused by name, exit 2; env-exported value validated the same |
| 3 | `tests/test_makefile.py::test_publish_passes_rows_unexpanded_as_one_literal` and `make -n publish` shows `python -m study.metabase export --rows=…` only |
| 3 | `tests/test_review_drill.py::test_sqlite_export_is_byte_identical_on_a_rerun` (existing, cited) and `::test_publish_refuses_a_missing_warehouse_by_name` |
| 4 | `tests/test_warehouse.py::test_snowflake_refuses_a_missing_variable_by_name_before_any_import_or_socket` — six unset/partly set environments, each refusal names the first missing variable, `snowflake` absent from `sys.modules`, the suite's socket guard untouched |
| 4 | `tests/test_warehouse.py::test_snowflake_refuses_a_missing_driver_by_name` — every variable set, the import blocked via `sys.modules[...] = None`: one line naming the package and the extra |
| 4 | `tests/test_warehouse.py::test_a_refusal_never_echoes_a_value` — a distinctive fake secret in the environment appears in no refusal |
| 5 | `tests/test_rebuild.py::test_the_classify_step_opens_every_connection_for_the_callers_target` — a recording seam substituted for `warehouse.connect` sees only the given target on every open |
| 5 | `tests/test_ingest_layout.py::test_no_module_outside_the_seam_spells_an_engine_name` — the literals `"duckdb"`/`"snowflake"` occur in `pipeline/warehouse.py` (and `tests/`) only |
| 5 | `tests/test_cli.py::test_cli_idempotency_check_accepts_both_targets` (replaces `test_cli_idempotency_check_refuses_non_duckdb_target`) and `::test_cli_reset_stays_duckdb_only` |
| 5 | `tests/test_no_key.py` (whole module, existing) green; `make rebuild ROWS=synthetic` with the key unset prints the rules-only line |
| 6 | `tests/test_dag.py::test_demonstration_doc_and_synthetic_screenshot_exist_and_links_resolve` — the 9g pattern: the doc, its links, the screenshot under `dags/screenshots/`, the caption in the PNG's text chunk |
| 6 | `make check-docs` — the hashed-token scan over `dags/DEMONSTRATION.md` and the PNG's text (a `dags/screenshots/` `.png` entry joins `scripts/review_common.py::BINARY_ASSETS`) |
| 6 | `dags/DEMONSTRATION.md` — the pasted counts of the Snowflake rebuild and idempotency check, the schema name, then the DuckDB `make rebuild` line after it; `tests/test_backing.py` and `make check-backing` green with B5.2's new source |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For every task of the DAG, the task is one `make` invocation of a declared target and nothing else: no function, branch, SQL or transformation lives under `dags/`. | `tests/test_dag.py::test_the_dag_is_five_make_tasks_in_the_briefs_order_with_no_logic` — a `def`, an `if`, a second statement in a `bash_command`, or a goal `make help` does not list |
| 2. For every `ROWS` input, the three stages run in order leave, table for table, the counts one whole rebuild leaves, and any stage run again adds no row. | `tests/test_rebuild.py::test_three_stages_in_order_equal_one_whole_rebuild`, `::test_a_stage_run_twice_adds_no_rows` |
| 3. For every `TARGET`, every table the pipeline writes and every mart the exports read is in that target's warehouse: no module outside the seam decides the engine. | `tests/test_rebuild.py::test_the_classify_step_opens_every_connection_for_the_callers_target` — a connection opened for another target than the caller's; `tests/test_ingest_layout.py::test_no_module_outside_the_seam_spells_an_engine_name` — an engine literal outside `warehouse.py` |
| 4. For every incomplete Snowflake environment, `connect("snowflake")` refuses in one line naming the missing variable or package, prints no value, imports no driver and opens no socket. | `tests/test_warehouse.py::test_snowflake_refuses_a_missing_variable_by_name_before_any_import_or_socket`, `::test_a_refusal_never_echoes_a_value` |
| 5. For every DuckDB target this phase touches (`rebuild` and its stages, `publish`, `idempotency-check`), the run needs no key, no network, no Docker and no Snowflake package, and its outputs are the pre-phase outputs. | the DONE command with `ANTHROPIC_API_KEY` unset and the extra not installed; `tests/test_no_key.py`; CI's `make study` + `git diff --exit-code` (the page is byte-identical) |
| 6. For every artifact this phase commits or sends off the laptop (the Snowflake run, every screenshot), the input is `ROWS=synthetic`: no captured review text reaches a third party or the repo. | `tests/test_dag.py::test_demonstration_doc_and_synthetic_screenshot_exist_and_links_resolve` (the doc states the input; the PNG carries the caption); `make check-docs` over the PNG text; security-reviewer reads the screenshot |

## Pinned decisions (do not re-litigate)

- **The DAG is five `BashOperator`s over `make`, `schedule=None`, one screen.**
  PLAN §2 "Airflow contains no logic" adopted verbatim: the DAG file is a list
  of commands and arrows. `schedule=None` (triggered by hand): the scheduled
  scrape in practice is the Actions cron (brief §4.4), and a container left
  running must not fetch the network on its own — the network target stays
  developer-run. *Rejected: `@weekly` mirroring the cron (a second unattended
  scraper); PythonOperators calling `pipeline.build` (logic in the DAG, and the
  container would need the project importable).* Satisfies invariant 1.
- **The middle three tasks are `STAGE=` selections of the one `rebuild`, not new
  targets or a second build path.** `rebuild()` gains a `stages` parameter over
  a closed ordered set; `all` is the whole; each stage opens one connection and
  runs the same functions the whole runs, in the same order, so there is one
  write path and the stage split cannot drift from the whole. *Rejected: three
  new `make` targets `load-raw`/`clean`/`classify` (three recipes for one
  function; `make help` and the closed-set tests triple); renaming the tasks to
  `rebuild` (the brief's five names are the architecture diagram).* Satisfies
  invariant 2.
- **`publish` is a `make` target that writes the Metabase SQLite export; `apply`
  stays developer-run.** The export is offline, deterministic and credential-
  free, so a DAG task can run it unattended; `apply` needs a running Metabase
  and a login. The HTML page is not in `publish`: it renders the frozen
  synthetic input by the 9a contract and is a tracked file. *Rejected: the DAG
  calling `python -m study.metabase export` directly (a task that is not a
  `make` target — the one-target-per-task rule); `publish` also running
  `apply` when credentials are exported (behaviour that depends on the
  environment, and a conditional in the DAG's task).* Satisfies invariants 1, 5.
- **Snowflake is an optional extra, imported inside the seam's branch, with
  credentials read from the environment by name.** The `snowflake` extra keeps
  the DuckDB path free of the connector (brief §4.4: no accounts, a laptop
  forever); the lazy import keeps `tests/test_warehouse.py`'s no-driver-at-
  module-level pin; the names are refused by name (Secrets convention).
  *Rejected: a hard dependency (every clone pulls a cloud connector it never
  uses); a `[snowflake]` section in a config file (a second place for
  credentials).* Satisfies invariant 4.
- **The engine name is decided in `pipeline/warehouse.py` only; every data-path
  caller passes `TARGET` through.** `classify_step` takes the target beside the
  database (as `connect` does), `_staged_review_rows` asks the seam whether the
  warehouse exists instead of testing a file path, the exports take a
  connection from the seam, and a `LOCAL` constant replaces every `"duckdb"`
  literal outside the seam — the layout test then pins the class, not the case
  (LESSONS `site-fix`). `reset` keeps `('duckdb',)` through the constant: it
  deletes files, and Snowflake objects are dropped by hand in the trial.
  *Rejected: a `target` default of `"duckdb"` on each function (the literal at
  every site — BACKLOG row 50's shape again); a global "current target"
  setting (hidden state on the data path).* Satisfies invariant 3.
- **Both demonstration runs load `ROWS=synthetic`; the compose is one container
  under `dags/`.** No captured review body goes to a cloud trial or into a
  screenshot (the 9g compose mounts only the export directory for the same
  reason); the synthetic input is the corpus for both runs and the caption says
  so. Airflow runs as `standalone` in one container built `FROM
  apache/airflow:<tag>` plus `uv`, the repo mounted at a fixed path,
  `UV_PROJECT_ENVIRONMENT` pointed inside the container so the host's `.venv` is
  never touched. *Rejected: the official multi-service compose (Postgres,
  Redis, five Airflow services for one DAG); the corpus in the Snowflake run
  (real review text off the laptop).* Satisfies invariant 6.

## Scope (files)

- `dags/friction_ledger.py` (new — the DAG), `dags/docker-compose.yml`,
  `dags/Dockerfile` (new — the one-container Airflow), `dags/DEMONSTRATION.md`,
  `dags/screenshots/01-dag-run.png` (new — the walk and the captioned grid).
- `pipeline/warehouse.py` — the Snowflake branch (env names, lazy import,
  refusals), `LOCAL`, `exists()` (does this target's warehouse hold a table
  yet — the seam's answer to `_staged_review_rows`'s file test).
- `pipeline/build.py` — `STAGES`, `rebuild(…, stages=)`, `classify_step(target,
  …)`, `idempotency_check` through the seam for both targets; every `"duckdb"`
  literal → `warehouse.LOCAL`.
- `pipeline/cli.py` — `--stage` on `rebuild` (closed set), `idempotency-check`
  over `TARGETS`, `reset` over `(LOCAL,)`, the refusal arms for the seam's
  new errors.
- `study/metabase/export.py`, `study/metabase/__main__.py` — the export reads
  through the seam's connection (`--target`), `--rows` unchanged.
- `study/export.py` — the study export's `connect(LOCAL, …)` (no behaviour
  change).
- `Makefile` — `STAGE` joins the `unexport` list and `rebuild`'s recipe; the
  `publish` target (`ROWS`, `TARGET`); `make help` lines.
- `pyproject.toml`, `uv.lock` — the `snowflake` optional extra.
- `.env.example` — the `SNOWFLAKE_*` placeholders.
- `scripts/review_common.py` — `BINARY_ASSETS` gains `dags/screenshots/` `.png`.
- `tests/test_dag.py` (new), `tests/test_warehouse.py`, `tests/test_rebuild.py`,
  `tests/test_cli.py`, `tests/test_makefile.py`, `tests/test_ingest_layout.py`,
  `tests/test_review_drill.py`, `tests/test_repo_text.py`, `tests/pins.py`.
- `study/text.py`, `study/friction_ledger.html` — B5.2's panel names the DAG
  file (one sentence; the page re-rendered and committed).
- `SPEC.md` (B5.2: the DAG file beside the one command — a design change,
  approved with this spec), `BACKING.md` (B5.2's source column gains
  `dags/friction_ledger.py`; no tag changes), `README.md` (Beat 5: the DAG
  sentence and one sentence on why it holds no logic; Running it: `STAGE`,
  `publish`, the Airflow and Snowflake walks in one paragraph each),
  `CLAUDE.md` (Commands, Repo map — `dags/` loses its *(Phase 10)* marker —
  Current status, the architecture block's caption), `DECISIONS.md`,
  `BACKLOG.md`, this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 10 entry (the six pinned decisions with their
  rejected alternatives); Gotchas for every dialect or Airflow surprise the
  first hour finds; the "still in force" warehouse bullet loses "its connector
  defers, no import in Phase 1"
- [ ] `BACKLOG.md` — rows closed: "The classify-step mart writes are not
  warehouse-aware" (DONE Phase 10), "The Snowflake half of `default_schema`
  is unpinnable offline" (DONE Phase 10, the schema name recorded); rows
  opened as the build finds them; the count in CLAUDE.md updated
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Commands (`rebuild [STAGE=]`, `publish`,
  `idempotency-check [TARGET=]`, the `snowflake` extra); Repo map (`dags/`
  built; `pipeline/warehouse.py` "the one place that knows DuckDB from
  Snowflake" now literally true); Conventions allowlist unchanged (the
  package was pre-approved); BACKLOG count
- [ ] `BACKING.md` — B5.2's source column (`pipeline/build.py;
  dags/friction_ledger.py`); no tag changes
- [ ] `SPEC.md` — B5.2 names the DAG file beside the one command (approved
  with this spec; no chart added, no beat changed)
- [ ] `README.md` — Beat 5 and Running it, as under Scope
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

Three targets take a variable or reach a service: `rebuild` gains `STAGE`
(offline), `publish` takes `ROWS` and `TARGET` (offline on DuckDB), and
`TARGET=snowflake` on `rebuild`, `idempotency-check` and `publish` reaches a
cloud database with credentials. `scrape` and `confirm` are unchanged. Nothing
new deletes; no paid API is added (the classify step's key path is unchanged).

Settled shape (unchanged): one Python process validates the value, derives
every path from it, then acts; every recipe is one line; every user variable
reaches Python unexpanded and single-quoted (`$(call _Q,$(value VAR))`) and is
`unexport`ed — `STAGE` joins that list.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `rebuild STAGE=` | → `all` (the whole, today's behaviour) | refused by name, exit 2: not in `all\|load\|clean\|classify` | refused by name, exit 2 (reaches Python as one literal, never a shell word) | validated the same (`resolve_choice`); the recipe reads `$(value STAGE)` | n/a — no confirm gate | `tests/test_makefile.py::test_stage_is_a_closed_set`, `::test_pipeline_variables_reach_python_as_one_literal` (parametrised with `STAGE`) |
| `publish ROWS= TARGET=` | `ROWS` → `captured`, `TARGET` → `duckdb` | refused by name (argparse `choices` = `INPUTS` / `TARGETS`) | refused by name | validated the same | n/a | `tests/test_makefile.py::test_publish_passes_rows_unexpanded_as_one_literal`; `tests/test_review_drill.py::test_publish_refuses_a_missing_warehouse_by_name` |
| `TARGET=snowflake` on `rebuild`, `idempotency-check`, `publish` | a missing `SNOWFLAKE_*` variable → one line naming it, exit 2, no socket, no driver import | n/a — no path is derived from a credential; the database, schema and warehouse names are passed to the connector as parameters, never interpolated into SQL | n/a — no shell; the connector takes parameters | credentials come ONLY from the environment (the exported `.env`); never in a tracked file, never in Actions (CI runs no Snowflake target) | n/a | `tests/test_warehouse.py::test_snowflake_refuses_a_missing_variable_by_name_before_any_import_or_socket`, `::test_a_refusal_never_echoes_a_value`; `tests/test_claude_config.py`/`tests/test_weekly.py` (no workflow names a `SNOWFLAKE_*` variable) |

Run twice, no credentials: `rebuild TARGET=snowflake` twice is the idempotent
rebuild on the other engine (raw append-only on the natural key; the
demonstration runs `idempotency-check` there to show it); with no credentials it
refuses before any connection. What it costs: a Snowflake trial's free credits,
developer-run, never by an agent and never in CI. The Airflow container is
developer-run: its `scrape` task is the same `make confirm scrape` (robots
first, ≥ 2 s per host, identifying User-Agent, ≤ 60 pages per source), triggered
by hand, never on a schedule.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `pipeline/**`, `study/**/*.py`, `Makefile`,
  `dags/**`, `tests/`): the stage split is one write path, the seam threading
  is by parameter not by literal, the DAG holds no logic, the closed sets,
  the refusal arms at the CLI boundary for the seam's new errors
  (LESSONS `traceback-at-boundary`), the no-key path, scope.
- **security-reviewer** (mandatory — `pipeline/warehouse.py`, `pipeline/cli.py`,
  `Makefile`, `.env.example`, `scripts/`, `dags/**`, a network engine with
  credentials, a Docker container that mounts the repo): the `SNOWFLAKE_*`
  names never echo a value; the connector receives parameters, never an
  interpolated string; the extra is pinned in `uv.lock`; the compose mounts
  the repo and the DAG's tasks run `make` only; the Snowflake run and the
  screenshot are over synthetic reviews; it **reads the committed screenshot**
  for any leaked text or brand.
- **functionality-tester** (triggered): the DONE command; the negative tests
  (`STAGE=../x`, `clean` before `load`, a partial Snowflake environment, a
  fake secret in a refusal, a second `BashOperator` statement planted in the
  DAG); the no-key run; the run-twice check on DuckDB; hand-mutation: a
  `"duckdb"` literal planted in `build.py` must fail the layout test.
- **study-editor** (triggered — `README.md`, `SPEC.md`, `BACKING.md`,
  `study/text.py`, `dags/DEMONSTRATION.md`): the two-layer voice of the DAG and
  Snowflake paragraphs, the Teaching-rule sentences, the caption on the
  screenshot, no insurer named, no banned word.
- **coherence-auditor** at exit (mandatory, whole repo — the brief's last
  phase): every "Phase 10" forward reference resolves (`warehouse.py`'s
  docstring and error, `build.py`'s and `cli.py`'s comments, DECISIONS "still
  in force", BACKLOG rows 33 and 50, CLAUDE.md's Repo map marker and
  Architecture caption, PLAN §5); SPEC B5.2 ↔ BACKING B5.2 ↔ the page's panel
  ↔ README Beat 5 name the same file; `make help` ↔ CLAUDE.md Commands ↔
  README "Running it" agree on `STAGE` and `publish`; whether the finished
  project reads as complete (brief §9 has no Phase 11).
- **Stack risk (verify in the first hour; STOP and report before any
  workaround — Workflow rules → Stack surprises; log under DECISIONS →
  Gotchas):**
  1. **The Airflow image and the DAG's imports.** The current release is
     Airflow 3.3.1 (2026-08-12; the docs' compose names `apache/airflow:3.3.1`).
     Airflow 3 moved `BashOperator` to the standard provider
     (`airflow.providers.standard.operators.bash`) and ships it in the image;
     confirm the import path against the running image and that `airflow
     standalone` runs the scheduler, the DAG processor and the UI in one
     container before pinning the compose. If `standalone` is not fit for the
     demonstration, the fallback is the documented LocalExecutor compose,
     scoped as an amendment.
  2. **`uv` inside the container.** The image's Python is not the project's
     interpreter; `uv run` must resolve the project into a container-local
     environment (`UV_PROJECT_ENVIRONMENT`) from the mounted repo, with
     `--locked` honoured, and `make` must be present in the image. Confirm the
     first task runs before wiring the rest.
  3. **Snowflake's login policy for the connector.** Snowflake enforces
     multi-factor authentication on password logins for human users; a trial
     may refuse a plain password from the connector. Read the current
     connector docs; if a password is refused, the one secret becomes a
     programmatic access token or a key-pair file path (read by name, never
     tracked), decided in the first hour and recorded — the invariant (refuse
     by name, no value) holds either way.
  4. **Dialect surprises the lint cannot see.** Snowflake folds unquoted
     identifiers to upper case, so an `information_schema` lookup comparing
     `table_name = 'stg_reviews'` matches nothing there; `create or replace`,
     `insert … select` and the DDL types are ANSI and should hold. Every
     difference found is fixed inside the seam or as ANSI SQL that DuckDB
     also runs (the central constraint), never as an engine branch outside
     `warehouse.py`; each goes to Gotchas.

## Out of scope (deferred, recorded)

- **`make study` over the captured corpus.** The study export renders the
  frozen synthetic input by contract and the DAG does not touch it; whether a
  reader's own corpus page is a `ROWS=` on `study` is a BACKLOG row this spec
  opens if it is not already there (README "Running it" says `make rebuild
  ROWS=captured && make study` fills Beat 2 from real data, while `make study`
  reads the synthetic file — a docs-versus-code finding for BACKLOG, not this
  phase).
- **A scheduled Airflow run.** `schedule=None` by pinned decision; the Actions
  cron is the schedule in practice (brief §4.4). Reopen if the DAG is ever
  deployed at a company, where the schedule would be set there.
- **Snowflake in CI.** Never: CI is offline, credential-free and DuckDB-only
  (CLAUDE.md → Git workflow). The Snowflake run is developer-run, once, and
  recorded.
- **The per-review drill's public address** (BACKLOG, open since 9b) and
  **B2.1 in the HTML page** (BACKLOG, 9g) — untouched; neither surfaces in
  this phase's beat.
