# Phase 10a — the Airflow DAG

Contract for the `phase-10a-airflow` branch. Source: PROJECT_BRIEF.md §9 Phase 10
("Wrap the working steps in the one-screen DAG; run once against a Snowflake
trial; screenshot; confirm the DuckDB path still passes"), §3 Beat 5 (the
reproducibility section's DAG diagram), §4 (the DAG of five tasks), §4.4 (the
"Full (demonstration)" run mode); `docs/PLAN.md` §5 row 10 and §2 ("Airflow
contains no logic" — BashOperators over `make` targets, five tasks, one
screen). Phase 10 is split in two on the ≤ ~6 done-when rule, the way Phases
0, 3, 5 and 9 were (challenge round 1, finding 8): **10a** is the DAG, the
stage split of `rebuild`, the `publish` target, the one engine-name constant,
and the Airflow demonstration — DuckDB only; **10b** is the seam's Snowflake
branch, the `TARGET` threading and the Snowflake run, its spec written after
10a merges (Out of scope, last section). Depends on Phase 9i merged (PR #34)
and the four small PRs after it (#35–#38), all on `main` 2026-09-13.

**Status: APPROVED 2026-09-13 — in progress.** No new Python dependency:
the DAG file is read by the suite with `ast`, never imported; Airflow runs via
Docker only (CLAUDE.md → Conventions), in one container built from the
official image plus `make` and `uv`. The phase is **non-CI** in the 9g shape:
an offline, CI-checkable core (the DAG file's shape, the stage split, the
`publish` target, the engine-name constant and its layout test, the compose
file's mounts) plus a developer-run demonstration (the Airflow run over
hand-written synthetic reviews, recorded with one captioned screenshot).
Challenged: 2026-09-13, round 1, spec 4a421afb — rework (1 BLOCKER, 12 should-fix, 4 suggestion, 1 question; all amended: the 10a/10b split, #1–#4, #7, #9, #15, #17 recorded as 10b's seeds; #18 verified live the same day — the image's Python-3.12 variant tag, stack risk 1; re-stamped 2026-09-13 after amendment A1 — invariant 5 restated exactly and Done-when 5's mount clause, the developer's disposition of review round 1 #2/#3, no new challenge round)

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules).

*The stack, in plain words (Teaching rule).* **Airflow** is a scheduler that
runs a list of commands in a fixed order and shows each run as a row of green
or red boxes; the list is written as a small Python file called a **DAG**
(directed acyclic graph — steps with arrows, no loops). A **BashOperator** is
the kind of step that runs one shell command; ours each run one `make`
target, so the DAG holds no logic of its own and the same five commands run
by hand on a laptop. The brief keeps Airflow as a demonstration of the shape
a company would schedule; the schedule in practice is the weekly Actions cron
(brief §4.4), so the DAG is triggered by hand.

## Why

Beat 5 promises the reproducibility section a DAG diagram beside the row
counts and the one rebuild command (brief §3), and the architecture names one
Airflow DAG as the thing that runs scrape → load_raw → clean → classify →
publish (brief §4; CLAUDE.md → Architecture). There is no `dags/` today. This
is a phase, not a fix PR, because it adds a new top-level directory, a Docker
runner, a `make` variable and a `make` target, and a Beat 5 text change.

Two things the brief's one line leaves open, decided here:

- **The five tasks versus the existing targets.** `make rebuild` already runs
  load, clean and classify in one process. The DAG's three middle tasks are the
  three stages of that one function, selected by a closed `STAGE` variable —
  not three re-implementations and not one task named `rebuild` with the
  brief's names dropped.
- **What "publish" runs.** `python -m study.metabase export|apply` are module
  commands, not `make` targets (CLAUDE.md → Current status). The DAG's
  `publish` task is a new `make publish` that writes the file Metabase reads
  (the SQLite export); `apply` stays developer-run because it needs a running
  Metabase and credentials. The permanent HTML page is not re-rendered by the
  DAG: `make study` renders the committed page over the frozen synthetic input
  by contract (9a), and a DAG run must not rewrite a tracked file — enforced
  by the container's read-only mount (done-when 5), not by a sentence.

## The central constraint

**The DuckDB path is unchanged in behaviour: every existing target, test and
committed artifact runs and reads the same with no Docker and no key, and
`study/friction_ledger.html` changes only by the one B5.2 sentence that names
the DAG's five tasks.** The phase adds a stage selector, a target, a constant
and a directory; it moves no number, re-freezes no fixture, changes no BACKING
tag, and touches no engine but DuckDB (`TARGET=snowflake` keeps its
deliberate refusal until 10b).

## DONE command

```
make idempotency-check ROWS=synthetic && make rebuild ROWS=synthetic STAGE=load && make rebuild ROWS=synthetic STAGE=clean && make rebuild ROWS=synthetic STAGE=classify && make publish ROWS=synthetic && uv run pytest tests/test_dag.py tests/test_rebuild.py tests/test_cli.py tests/test_makefile.py tests/test_ingest_layout.py tests/test_beat5.py -q
```

- `make idempotency-check ROWS=synthetic` — the run-twice property over the
  whole pipeline, classify step included (PR #35), unchanged by the stage
  split; every count unchanged on the second run.
- the three `make rebuild … STAGE=` calls in order — the DAG's middle three
  tasks, run by hand; the table counts they leave equal, table for table, the
  counts one `make rebuild ROWS=synthetic` leaves (pinned in
  `tests/test_rebuild.py`).
- `make publish ROWS=synthetic` — the DAG's last task: writes
  `data/metabase/metabase.sqlite` from the synthetic marts, byte-identical on
  a rerun, needing no credentials and no network.
- the pytest line — the DAG file's shape (five `make` tasks in order, no
  logic, its task ids equal to the page's tuple), the compose file's mounts and
  environment, the stage split's equality and refusals, the CLI's closed
  `STAGE` set, the `publish` recipe, the engine-name constant's layout test,
  and Beat 5's re-rendered panel.

The `scrape` task is not in the DONE command: it is the network target
(`make confirm scrape`, developer-run), unchanged by this phase.

## Done-when

1. **The DAG is five `make` tasks in the brief's order, holds no logic, and
   Beat 5 shows the same five names.** `dags/friction_ledger.py` declares one
   DAG (`dag_id="friction_ledger"`, `schedule=None`, `catchup=False`) of five
   `BashOperator`s with task ids `scrape`, `load_raw`, `clean`, `classify`,
   `publish`, chained linearly, each `bash_command` one bare `make` invocation
   of a target `make help` lists (`confirm scrape`, `rebuild STAGE=load`,
   `rebuild STAGE=clean`, `rebuild STAGE=classify`, `publish`) run from the
   repo root, with no `ROWS` on the command line (the input is the run's
   environment, done-when 5); the file imports Airflow and the stdlib only,
   defines no function, no branch and no SQL, and fits on one screen (≤ 40
   lines). Airflow is never imported by the suite: the test reads the file
   with `ast`. The page's B5.2 panel, the README's Beat 5 and SPEC.md's B5.2
   row show the five task names in order as a text diagram beside the one
   command, from one tuple in `study/text.py` that the `ast` test pins equal
   to the DAG's task ids, so the diagram cannot drift from the file.
   *Evidence: rows 1, 2, 3.*
2. **`rebuild` runs one stage at a time and the stages add up to the whole.**
   `make rebuild [STAGE=all|load|clean|classify]` (default `all`, validated in
   Python against the closed set) runs `load` (raw DDL + every load for the
   input), `clean` (staging + marts + the model, simulator and facts writers)
   or `classify` (the classify step) into the input's own file; the three in
   order leave, table for table, the counts one whole rebuild leaves; a stage
   run twice adds nothing; `clean` or `classify` over a file with no earlier
   stage refuses in one line naming the missing table. *Evidence: rows 4, 5, 6.*
3. **`make publish [ROWS=]` writes the file Metabase reads, and nothing else.**
   It calls `study.metabase export` for the named input (default `captured`),
   byte-identical on a rerun, refusing a missing warehouse by name; it rewrites
   no tracked file and needs no credentials. `apply` stays a module command,
   developer-run. *Evidence: rows 7, 8.*
4. **The engine name is spelled in the seam only.** `pipeline/warehouse.py`
   exports `LOCAL = "duckdb"` beside `TARGETS`; every `connect("duckdb", …)`
   outside the seam (`pipeline/build.py` — the classify step, the idempotency
   count, `_staged_review_rows`; `pipeline/cli.py` — the `reset` and
   `idempotency-check` closed sets; `pipeline/label_sample.py`;
   `study/export.py`; `study/metabase/export.py`) becomes `connect(LOCAL, …)`
   or `(LOCAL,)`, and a layout test refuses an engine-name literal
   (`"duckdb"`, `"snowflake"`) in any module outside the seam and `tests/` —
   the class, not the site (LESSONS `site-fix`), so 10b's threading is a
   parameter change with no literal left to miss. No behaviour changes: the
   constant is the same string. *Evidence: rows 9, 10.*
5. **The demonstration is committed, over synthetic reviews only, and the
   container can neither read the corpus nor write the repo.** `dags/` holds a
   `Dockerfile` (`FROM apache/airflow:3.3.1-python3.12` — the official image's
   Python-3.12 variant, matching `.python-version`; `make` by apt as root, `uv`
   by pip as `airflow`, the documented extension pattern) and a one-service
   `docker-compose.yml` running `airflow standalone` with: the tracked
   top-level paths the tasks read, each mounted **read-only** under a fixed
   path (amendment A1; the first draft mounted the whole repo); `data/` a
   container-private named volume with
   the three tracked numbers-only subtrees (`data/snapshots/`, `data/damir/`,
   `data/ameli/`) bound read-only inside it, so the rebuild reads its fit and
   its snapshots and writes its DuckDB file, its captures, its decision cache
   and its export into the volume, never the host; `ROWS=synthetic`,
   `UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR` (both outside the mount),
   `UV_LOCKED=1`, `PYTHONDONTWRITEBYTECODE=1` in `environment:`; **no
   `env_file:`** (the `classify` task is the no-key run by construction; the
   scrape has no credential); the UI bound to `127.0.0.1`. The `scrape` task is
   the real polite fetch into the volume; the demonstration's `load` reads the
   synthetic fixture from the read-only repo, so no captured review is in any
   table the run builds or the screenshot shows. `dags/DEMONSTRATION.md` walks
   the run — the image built, the DAG parsed, the five tasks green, one
   screenshot of the grid under `dags/screenshots/` captioned *synthetic
   fixture data — not a study finding* in its pixels and its text chunk — and
   pastes only the task list and states (no host path, no account, no
   address). *Evidence: rows 11, 12, 13.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_dag.py::test_the_dag_is_five_make_tasks_in_the_briefs_order_with_no_logic` — `ast` over `dags/friction_ledger.py`: five `BashOperator` calls, the task-id tuple in order, one `>>` chain, no `def`/`if`/`for`/`try`, no second statement in a `bash_command`, ≤ 40 lines, imports from `airflow`/`datetime` only |
| 1 | `tests/test_dag.py::test_every_dag_task_runs_one_declared_make_target_with_no_rows_argument` — each `bash_command` is one `make <goal…>` run with `cwd=REPO` (no `cd`, no `&&`, no `;`) whose goals are in `scripts/review_common.py::make_targets`, whose variables are `STAGE` only and in its closed set, and which carries no `ROWS=` |
| 1 | `tests/test_dag.py::test_the_pages_task_tuple_equals_the_dags_task_ids` and `tests/test_beat5.py::test_b52_note_names_the_five_tasks_in_order` — `study/text.py::DAG_TASKS` equals the `ast`-read ids; the rendered B5.2 note carries them in order; `make study` + `git diff --exit-code` in CI (the page re-rendered once, committed) |
| 2 | `tests/test_rebuild.py::test_three_stages_in_order_equal_one_whole_rebuild` — `table_counts` after `load`, `clean`, `classify` equal one `rebuild` + `classify_step` over the same input, table for table (not a sum) |
| 2 | `tests/test_rebuild.py::test_a_stage_run_twice_adds_no_rows` and `::test_clean_or_classify_before_load_refuses_naming_the_missing_table` |
| 2 | `tests/test_makefile.py::test_stage_is_a_closed_set` — empty → `all`; `load`/`clean`/`classify` accepted; `../x`, `"; `, `Load`, `all,load` refused by name, exit 2; `::test_pipeline_variables_reach_python_as_one_literal` parametrised with `STAGE`; `::test_env_exported_stage_reaches_the_recipe_and_is_validated_in_python` (the container's mechanism) |
| 3 | `tests/test_makefile.py::test_publish_passes_rows_unexpanded_as_one_literal` — `make -n publish` shows `python -m study.metabase export --rows=…` only, from both origins |
| 3 | `tests/test_review_drill.py::test_sqlite_export_rating_is_exact_and_row_order_is_stable` (existing — two exports over the same warehouse compare equal as bytes) and `::test_export_refuses_a_missing_mart_by_name` (existing); `tests/test_metabase_apply.py::test_export_command_refuses_rows_outside_the_set_by_name` (the `--rows` closed set, exit 2, nothing built) |
| 4 | `tests/test_ingest_layout.py::test_no_module_outside_the_seam_spells_an_engine_name` — the literals `"duckdb"`/`"snowflake"` occur in `pipeline/warehouse.py` (and `tests/`) only; a planted `connect("duckdb"` in `build.py` fails it |
| 4 | `tests/test_warehouse.py::test_local_is_the_duckdb_target` — `LOCAL in TARGETS`, `connect(LOCAL, database=":memory:")` answers `select 1` |
| 5 | `tests/test_dag.py::test_the_compose_mounts_the_repo_read_only_isolates_data_carries_no_env_file_and_binds_the_ui_locally` — `pyyaml` over `dags/docker-compose.yml`: one service; the repo bind `:ro`; `data/` a named volume; the three tracked subtrees `:ro`; `ROWS: synthetic`; no `env_file`; ports `127.0.0.1:8080:8080`; `UV_PROJECT_ENVIRONMENT`/`UV_CACHE_DIR` not under the mount path |
| 5 | `tests/test_dag.py::test_demonstration_doc_and_synthetic_screenshot_exist_and_links_resolve` — the 9g pattern: the doc, its links, the screenshot under `dags/screenshots/`, the caption in the PNG's text chunk; `make check-docs` scans both (a `dags/screenshots/` `.png` entry joins `scripts/review_common.py::BINARY_ASSETS`) |
| 5 | `dags/DEMONSTRATION.md` — the pasted task list and states; security-reviewer and study-editor read the screenshot |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For every task of the DAG, the task is one `make` invocation of a declared target and nothing else: no function, branch, SQL, transformation or input choice lives under `dags/`. | `tests/test_dag.py::test_the_dag_is_five_make_tasks_in_the_briefs_order_with_no_logic`, `::test_every_dag_task_runs_one_declared_make_target_with_no_rows_argument` — a `def`, an `if`, a second statement in a `bash_command`, a `ROWS=`, or a goal `make help` does not list |
| 2. For every `ROWS` input, the three stages run in order leave, table for table, the counts one whole rebuild leaves, and any stage run again adds no row. | `tests/test_rebuild.py::test_three_stages_in_order_equal_one_whole_rebuild`, `::test_a_stage_run_twice_adds_no_rows` |
| 3. For every module outside `pipeline/warehouse.py`, the engine is a name imported from the seam, never a literal. | `tests/test_ingest_layout.py::test_no_module_outside_the_seam_spells_an_engine_name` — a planted literal |
| 4. For every DuckDB target this phase touches (`rebuild` and its stages, `publish`, `idempotency-check`), the run needs no key, no network and no Docker, and its outputs are the pre-phase outputs. | the DONE command with `ANTHROPIC_API_KEY` unset; `tests/test_no_key.py`; `tests/test_beat5.py::test_beat_five_render_is_byte_stable`; CI's `make study` + `git diff --exit-code` |
| 5. For every run of the container, no captured review is in a table it builds or a screenshot it yields, and no file under the repo is written: the input is `ROWS=synthetic` from the environment and the repo mount is read-only. | `tests/test_dag.py::test_the_compose_mounts_the_repo_read_only_isolates_data_carries_no_env_file_and_binds_the_ui_locally`; `::test_demonstration_doc_and_synthetic_screenshot_exist_and_links_resolve`; `make check-docs` over the PNG text; security-reviewer reads the screenshot |
| 6. For every text surface that shows the DAG's steps (the page, the README, SPEC.md), the names are the DAG's task ids in the DAG's order. | `tests/test_dag.py::test_the_pages_task_tuple_equals_the_dags_task_ids`; `tests/test_beat5.py::test_b52_note_names_the_five_tasks_in_order`; `tests/test_dag.py::test_the_readme_and_spec_name_the_dags_tasks_in_the_dags_order` (the README's Beat 5 walk and SPEC.md's B5.2 row) |

**Amendment A1 (review round 1, 2026-09-13, security-reviewer #2 and #3) —
the container reads the tracked tree only.** Invariant 5 restored and made
exact: *for every run of the container, every path it can read under the
repo mount is a tracked path or one of the three numbers-only `data/`
subtrees; no gitignored file of the checkout is readable inside it.* The
`..:/opt/friction-ledger:ro` bind broke it: the named volume overlaid
`data/` only, so the root `.env` (the API key and the warehouse credentials),
`.git/`, `.venv/`, `.claude/settings.local.json` and `.mcp.json` rode into
the container readable, while the compose's own header and pinned decision 5
said no credential was mounted, and
`test_the_compose_mounts_the_repo_read_only…` checked `env_file` and
`environment:` only. Mechanism: the whole-repo bind is replaced by one
read-only bind per tracked top-level path the five tasks read — `Makefile`,
`pyproject.toml`, `uv.lock`, `.python-version`, `pipeline/`, `ingest/`,
`classify/`, `models/`, `opendata/`, `study/`, `sql/`, `fixtures/`, `dags/`
— beside the unchanged `data/` volume and its three `:ro` subtrees; nothing
else exists under the mount, so a gitignored file cannot be there whatever
its name (`.env*`, `*.pem`, `credentials*` included). Falsified by
`tests/test_dag.py::test_the_compose_mounts_only_tracked_paths_the_tasks_read`:
(a) every bind source is a tracked top-level entry of `HEAD` (`git ls-tree`),
never `..`, `.`, `.claude`, `.github` or a gitignored name; (b) the mounted
set covers every `ROOT / "<top>"` the source packages read
(`pipeline/`, `classify/`, `opendata/`, `ingest/`, `models/`, `study/`,
grepped from the source), every package `model_call_sites` scans
(`_CODE_PACKAGES`), the packages themselves and the four project files — so
a new read path outside the mounts names itself. The 9g compose was already
this shape (the export directory alone); 10a's first draft mounted the tree
for convenience. *Not taken: overlaying each local-only path with an empty
mount (`/dev/null` for a file, `tmpfs` for a directory) — five lines, but
it protects named paths only, and the credential patterns `.gitignore`
declares are globs (`.env*`, `*.pem`, `credentials*`), so a `.envrc` or a
`credentials.json` at the root would still be readable: the case, not the
class; a `git archive` export mounted in its place — a stale copy, the
rejection of pinned decision 5.* Cost: a new tracked top-level path a task
reads is one compose line, which the test names. The demonstration is
re-run by the developer over the amended compose (Docker, never CI) and the
screenshot re-captured only if the grid changes; the DAG file is untouched.

## Pinned decisions (do not re-litigate)

- **The DAG is five `BashOperator`s over bare `make` commands, `schedule=None`,
  one screen; the demonstration's input is the container's environment.**
  PLAN §2 "Airflow contains no logic" adopted verbatim: the DAG file is a list
  of commands and arrows, production-shaped (no `ROWS`, so a company run loads
  what it captured); the demonstration sets `ROWS=synthetic` in the compose
  `environment:`, which the Makefile already documents as a value that reaches
  the recipe and is validated in Python. `schedule=None` (triggered by hand):
  the scheduled scrape in practice is the Actions cron (brief §4.4), and a
  container left running must not fetch the network on its own. *Rejected:
  `ROWS=synthetic` in the `bash_command` (an input choice in the DAG, and a
  DAG that can never run the corpus); `@weekly` (a second unattended
  scraper); PythonOperators (logic in the DAG).* Satisfies invariants 1, 5.
- **The middle three tasks are `STAGE=` selections of the one `rebuild`, not
  new targets or a second build path.** `rebuild()` gains a `stages` parameter
  over a closed ordered set; `all` is the whole; each stage opens one
  connection and runs the same functions the whole runs, in the same order, so
  there is one write path and the stage split cannot drift from the whole; the
  equality test compares table for table, so a stage boundary drawn elsewhere
  (the facts writer under `load`) fails it. *Rejected: three new `make` targets
  (three recipes for one function; `make help` and the closed-set tests
  triple); renaming the tasks to `rebuild` (the brief's five names are the
  architecture diagram).* Satisfies invariant 2.
- **`publish` is a `make` target that writes the Metabase SQLite export; `apply`
  stays developer-run; the HTML page is not in it.** The export is offline,
  deterministic and credential-free, so a DAG task can run it unattended;
  `apply` needs a running Metabase and a login; the page renders the frozen
  synthetic input by the 9a contract and is a tracked file. *Rejected: the DAG
  calling `python -m study.metabase export` directly (a task that is not a
  `make` target); `publish` running `apply` when credentials are exported
  (behaviour that depends on the environment).* Satisfies invariants 1, 4.
- **One constant, `warehouse.LOCAL`, replaces every engine literal outside the
  seam, and a layout test pins the class.** The literal `"duckdb"` at eight
  sites is BACKLOG row 50's shape ("not warehouse-aware"); replacing the
  literal everywhere now, with a test that refuses a new one, means 10b
  threads `TARGET` by parameter with nothing to grep for. `reset` and
  `idempotency-check` keep their DuckDB-only closed sets as `(LOCAL,)` until
  10b lifts the second. *Rejected: fixing the literal only in `classify_step`
  (the site, not the class); a global "current target" setting (hidden state
  on the data path).* Satisfies invariant 3.
- **The container mounts the repo read-only and owns its `data/`; the tracked
  numbers-only subtrees are bound in read-only.** The 9g compose mounts only
  the export directory so the corpus never reaches a third-party image; here
  the tasks must read the repo and write a warehouse, so the repo is `:ro`, the
  writes go to a named volume at `data/`, and the three tracked subtrees the
  rebuild reads (`snapshots`, `damir`, `ameli` — numbers only) are nested
  read-only binds inside it. `uv`'s environment and cache live outside the
  mount; no `env_file`; the UI on the loopback address. Then "no tracked file
  rewritten" and "no corpus in the container" are enforced by the mounts, and
  the Threat model's row is fillable. *Rejected: the whole repo read-write
  (the first draft — `.env`, `data/cache/` bodies, `*.duckdb` and `.git`
  handed to the image); a copy of the repo into the image at build time (a
  stale corpus baked into a layer).* Satisfies invariant 5.
- **One container, `airflow standalone`, from a two-line Dockerfile on the
  image's Python-3.12 variant.** The official image's default Python is 3.13
  (verified 2026-09-13; the project pins 3.12), so the tag is
  `apache/airflow:3.3.1-python3.12` and `uv` downloads no interpreter. The
  official image has no `make` (docs: no `build-essential`) and no `uv`; the
  documented extension pattern adds an apt package as root and a pip package
  as `airflow`. `standalone` runs the scheduler, the DAG processor, the API
  server and the executor in one process over the bundled SQLite metadata
  database — enough for a hand-triggered demonstration. *Rejected: the official
  multi-service compose (Postgres, Redis, five Airflow services for one DAG);
  Airflow installed on the host (Conventions: Docker only).* Stack risk 1
  verifies it before the stamp.

## Scope (files)

- `dags/friction_ledger.py` (new — the DAG), `dags/Dockerfile`,
  `dags/docker-compose.yml` (new — the one-container Airflow),
  `dags/DEMONSTRATION.md`, `dags/screenshots/01-dag-run.png` (new — the walk
  and the captioned grid).
- `pipeline/warehouse.py` — `LOCAL`.
- `pipeline/build.py` — `STAGES`, `rebuild(…, stages=)`, the stage refusal
  naming the missing table; every `"duckdb"` literal → `LOCAL`.
- `pipeline/cli.py` — `--stage` on `rebuild` (closed set), `reset` and
  `idempotency-check` over `(LOCAL,)`.
- `pipeline/label_sample.py`, `study/export.py`, `study/metabase/export.py` —
  their `connect("duckdb", …)` → `connect(LOCAL, …)` (no behaviour change).
- `Makefile` — `STAGE` joins the `unexport` list and `rebuild`'s recipe; the
  `publish` target (`ROWS`); `.PHONY`; `make help` lines.
- `scripts/review_common.py` — `BINARY_ASSETS` gains `dags/screenshots/` `.png`.
- `tests/test_dag.py` (new), `tests/test_rebuild.py`, `tests/test_cli.py`,
  `tests/test_makefile.py`, `tests/test_ingest_layout.py`,
  `tests/test_warehouse.py`, `tests/test_metabase_apply.py`, `tests/test_beat5.py`,
  `tests/test_repo_text.py`, `tests/pins.py`; `tests/conftest.py` — `STAGE`
  joins `_scrub_env`; the source-package walkers (`tests/test_number_shapes.py`,
  `tests/test_csv_readers.py`) — `dags/` joins the packages walked
  (`scripts/check_pins.py` already walked it; unchanged).
- `study/text.py` (`DAG_TASKS`, the B5.2 note's one sentence),
  `study/friction_ledger.html` (re-rendered once, committed).
- `SPEC.md` (B5.2: the five task names beside the one command — a text change
  to an existing row, approved with this spec; no chart added, no beat
  changed), `README.md` (Beat 5: the five names and one sentence on why the
  DAG holds no logic; Running it: `STAGE`, `publish`, the Airflow walk in one
  paragraph, and the caveat that `make study` renders the frozen synthetic
  input — the captured render is a BACKLOG row this phase opens), `CLAUDE.md`
  (Commands, Repo map — `dags/` loses its *(Phase 10)* marker — Current
  status, the architecture block's caption), `DECISIONS.md`, `BACKLOG.md`,
  this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 10a entry (the split and the six pinned decisions
  with their rejected alternatives; challenge round 1's disposition); Gotchas
  for every Airflow or image surprise the first hour finds
- [ ] `BACKLOG.md` — rows opened: "`make study` renders the frozen synthetic
  input while the README's Running it says the captured rebuild fills Beat 2"
  (trigger: a `ROWS=` on `study`, or the README sentence rewritten — one or
  the other); rows 33 and 50 re-pointed at 10b; the count in CLAUDE.md
  updated
- [ ] `LESSONS.md` — the `traceback-at-boundary` row (round 1 #1: the seam's
  `NotImplementedError` out of `main`; `warehouse.WIRED`) and the `unpinned`
  row (round 1 #6: invariant 2's pins over `synthetic` only) extended by
  their fix commits
- [ ] `CLAUDE.md` — Current status (10a/10b); Commands (`rebuild [STAGE=]`,
  `publish [ROWS=]`); Repo map (`dags/` built); Architecture caption; BACKLOG
  count
- [ ] BACKING.md — none: B5.2's source stays `pipeline/build.py` (the DAG feeds no number; it is cited in SPEC.md's row text and the page)
- [ ] `SPEC.md` — B5.2's text names the five tasks in order beside `make rebuild`
- [ ] `README.md` — Beat 5 and Running it, as under Scope
- [ ] `docs/PLAN.md` — the Phase 10 row notes the 10a/10b split
- [ ] `specs/phase-10a-airflow.md` — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

Two targets take a variable (`rebuild STAGE=`, `publish ROWS=`; both offline)
and one runner fetches: the Airflow container, whose `scrape` task is the
unchanged `make confirm scrape`. Nothing new deletes; no paid API is added; no
credential is read (the container has no `env_file`, so the classify task is
the no-key run).

Settled shape (unchanged): one Python process validates the value, derives
every path from it, then acts; every recipe is one line; every user variable
reaches Python unexpanded and single-quoted (`$(call _Q,$(value VAR))`) and is
`unexport`ed — `STAGE` joins that list.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `rebuild STAGE=` | → `all` (the whole, today's behaviour) | refused by name, exit 2: not in `all\|load\|clean\|classify` | refused by name, exit 2 (reaches Python as one literal, never a shell word) | validated the same (`resolve_choice`); the recipe reads `$(value STAGE)` | n/a — no confirm gate | `tests/test_makefile.py::test_stage_is_a_closed_set`, `::test_pipeline_variables_reach_python_as_one_literal` (parametrised with `STAGE`), `::test_env_exported_stage_reaches_the_recipe_and_is_validated_in_python` |
| `publish ROWS=` | → `captured` | refused by name, exit 2 (`resolve_choice` over `INPUTS`, the same guard as `rebuild`) | refused by name | validated the same | n/a | `tests/test_makefile.py::test_publish_passes_rows_unexpanded_as_one_literal`; `tests/test_metabase_apply.py::test_export_command_refuses_rows_outside_the_set_by_name`; `tests/test_review_drill.py::test_export_refuses_a_missing_mart_by_name` |
| the Airflow container (`dags/docker-compose.yml`) | no `ROWS` in the environment → the DAG loads `captured` from the volume's captures (a company run); the demonstration sets `synthetic` | a `ROWS`/`STAGE` value planted in the compose environment reaches the recipe as one literal and is refused by name in Python, the same path as the command line | same | that IS the mechanism: `ROWS=synthetic` in `environment:` reaches the recipe and is validated; the repo is `:ro`, so no environment value can make a task write a tracked file | the `scrape` task's `make confirm scrape` arms from make's own goal list, the weekly.yml precedent (`$(origin MAKECMDGOALS)` is `default`) | `tests/test_dag.py::test_the_compose_mounts_the_repo_read_only_isolates_data_carries_no_env_file_and_binds_the_ui_locally`; `tests/test_makefile.py::test_confirm_is_a_goal_of_the_same_invocation` (existing) |

Run twice: a second DAG run is the idempotent rebuild (raw append-only; the
same synthetic input inserts nothing) and a second `publish` writes identical
bytes. No credentials: none are mounted or read; a key is never in the
container, so the classify task cannot pay. What the container fetches: the
`scrape` task is the same polite fetch (robots first, ≥ 2 s per host,
identifying User-Agent, ≤ 60 pages per source), triggered by hand, never on a
schedule; `uv` resolves the project into its own environment from the lock on
the first task (network once, `--locked`).

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `pipeline/**`, `study/**/*.py`, `Makefile`,
  `dags/**`, `tests/`): the stage split is one write path and the equality is
  table for table, the constant replaces every literal, the DAG holds no
  logic, the closed sets, the stage refusal at the CLI boundary (LESSONS
  `traceback-at-boundary`), scope.
- **security-reviewer** (mandatory — `pipeline/cli.py`, `Makefile`,
  `scripts/`, `dags/**`: a container that mounts the repo and fetches): the
  mounts (`:ro` repo, the private volume, the nested read-only subtrees), no
  `env_file`, the loopback bind, the Dockerfile's root-then-airflow pattern
  and pinned tags, the DAG's commands are `make` only; it **reads the
  committed screenshot** for any leaked text or brand.
- **functionality-tester** (triggered): the DONE command; the negative tests
  (`STAGE=../x`, `clean` before `load`, a second statement or a `ROWS=`
  planted in a `bash_command`, a `"duckdb"` literal planted in `build.py`, an
  `env_file:` planted in the compose); the no-key run; the run-twice check.
- **study-editor** (triggered — `README.md`, `SPEC.md`, `study/text.py`,
  `dags/DEMONSTRATION.md`): the two-layer voice of the DAG paragraph and the
  Teaching-rule sentences, the five names as a text diagram, the caption on
  the screenshot, the `make study` caveat, no insurer named, no banned word.
- **coherence-auditor** at exit (mandatory, whole repo): every "Phase 10"
  forward reference now reads 10a/10b (`warehouse.py`'s docstring and error,
  `build.py`'s and `cli.py`'s comments, DECISIONS "still in force", BACKLOG
  rows 33 and 50, CLAUDE.md's Repo map marker and Architecture caption, PLAN
  §5); SPEC B5.2 ↔ the page's panel ↔ README Beat 5 ↔ `DAG_TASKS` ↔ the DAG
  file name the same five steps; `make help` ↔ CLAUDE.md Commands ↔ README
  "Running it" agree on `STAGE` and `publish`; 10b finds `LOCAL` and the
  layout test in place.
- **Stack risk (verify BEFORE the stamp where marked, else in the first hour;
  STOP and report before any workaround — Workflow rules → Stack surprises;
  log under DECISIONS → Gotchas):**
  1. **Verified before the stamp (2026-09-13, the developer's Docker run):**
     `apache/airflow:3.3.1` `standalone` runs the scheduler, the DAG
     processor and the API server in one container and executed the
     `example_bash_operator` DAG's `BashOperator` tasks green (its two
     designed skips aside). Two findings: the image's default Python is
     **3.13**, so the Dockerfile uses the `-python3.12` variant tag (done-when
     5); and the simple auth manager logs a "deployment shape looks like
     production" warning because the API server binds every interface inside
     the container — expected, the compose publishes it on the Mac's loopback
     port only, and the generated admin password stays in the container's log
     (`docker logs`). Still first-hour: that a read-only DAG folder parses. A
     taken host port is remapped in the compose, not in the DAG.
  2. **`BashOperator`'s import path.** In Airflow 3 it lives in the standard
     provider (`airflow.providers.standard.operators.bash`), shipped in the
     image; confirm against the running image before pinning the `ast` test's
     import allowlist.
  3. **`make` and `uv` in the image.** The official image has no
     `build-essential` (docs, read 2026-09-13), so the Dockerfile installs
     `make` by apt as root and `uv` (the pinned `0.12.5`) by pip as `airflow`;
     confirm `uv run --locked` resolves the project into
     `UV_PROJECT_ENVIRONMENT` from a read-only mount with the cache outside it,
     and that the first task runs, before wiring the rest.
  4. **A read-only repo under `uv run`.** `uv` must not need to write under the
     project (`.venv`, `uv.lock`, `__pycache__`); the three environment
     variables in done-when 5 are the answer, verified by the first task.

## Out of scope (deferred, recorded)

- **Phase 10b — the Snowflake seam and the Snowflake run.** Its spec is
  written after 10a merges (Workflow rules: a spec is finalized only after
  its predecessor merges), against the invariant challenge round 1 named:
  *for every target, the seam is the only module that knows the engine — its
  connection shape, its catalog answers, its error type, its input isolation,
  and which inputs it may hold.* It absorbs, as Done-when items each with a
  test that fails offline against a fake driver, round 1's findings: **#1
  (BLOCKER)** a cloud target takes only fixture inputs — `TARGET=snowflake`
  with `ROWS ∉ (synthetic, none)` refused by name at the CLI, so the trial can
  never hold the corpus by construction; **#2** `connect()` returns one
  connection shape (execute → fetchone/fetchall/description, executemany,
  close) and the Snowflake branch is a wrapper over a qmark cursor; **#3** the
  seam owns the catalog reads (`exists`, `columns`, `tables`) with a
  case-folded compare, `information_schema` pinned to `warehouse.py`; **#4**
  one seam-owned error type both branches fold the driver's into, and the
  layout test pins "no `import duckdb|snowflake` outside the seam"; **#7**
  input isolation on Snowflake (a schema per input from the seam, or a stated
  single fixture schema); **#9** the secret is a string, never a path; **#15**
  the demonstration pastes only the count table and the schema name; **#17**
  CLAUDE.md Commands notes that `make setup` drops the `snowflake` extra.
  With them: the `snowflake` optional extra, `SNOWFLAKE_*` read by name,
  `TARGET` threaded through `classify_step`, `idempotency-check` and the
  exports, BACKLOG rows 33 and 50, and the round's stack risks on the trial's
  login policy and the dialect's case-folding. PLAN §5 row 10 reads 10a/10b
  at 10a's exit.
- **`make study` over the captured corpus.** The study export renders the
  frozen synthetic input by contract; the README's Running it says otherwise
  (round 1, finding 16). This phase adds the caveat sentence to the README
  edit it already makes and opens the BACKLOG row for the target; the
  captured render itself is not this phase.
- **A scheduled Airflow run.** `schedule=None` by pinned decision; the Actions
  cron is the schedule in practice (brief §4.4). Reopen if the DAG is ever
  deployed at a company, where the schedule would be set there.
- **The per-review drill's public address** (BACKLOG, open since 9b) and
  **B2.1 in the HTML page** (BACKLOG, 9g) — untouched.
