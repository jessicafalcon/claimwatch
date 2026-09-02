# Phase 0a — Workflow machinery (APPROVED)

Contract for the `phase-0a-machinery` branch. Source: PROJECT_BRIEF.md §9
Phase 0, split per `docs/PLAN.md` §5 (approved 2026-09-01): 0a builds the gate,
0b writes the contracts the gate then checks. Depends on nothing.

**Status: APPROVED 2026-09-01 — in progress.** No runtime dependencies.
Dev group only: `pytest`, `ruff`, `pre-commit`. Python 3.12 via `uv`. The ten
decisions in `docs/PLAN.md` §6 are taken at their stated defaults (recorded in
`DECISIONS.md` by this phase).

## Why

Every later phase is judged by a command (`make review-gate`) before any agent
reads it. That command, the docs guard, the evidence-contract guard, the review
agents and the hook have to exist and be proven on themselves before the first
contract file or the first line of pipeline code — otherwise Phase 0b's
SPEC/BACKING are reviewed by opinion, and the brief's rule "done-when is a test
or make target" cannot hold for them.

## The central constraint

**No pipeline code, no data, no study text lands in this phase.** `BACKING.md`
is a header and an empty table; `SPEC.md` does not exist yet; `sql/` does not
exist. The gate must be green on an empty project and red on planted
violations in throwaway trees.

## DONE command

```
make review-gate SPEC=specs/phase-0a-machinery.md
```

- `make test` — the guard pins (`tests/test_review_tools.py`,
  `tests/test_check_docs.py`, `tests/test_check_backing.py`,
  `tests/test_makefile.py`, `tests/test_claude_config.py`) green, offline.
- `ruff check` + `ruff format --check` — read-only lint green.
- `make check-docs` — links green over every doc; named targets, banned words
  and glossary size green over the living docs (CLAUDE.md, README, SPEC,
  BACKING) plus `study/`; BACKLOG count green.
- `make check-backing` — the empty table passes (no rows, no `sql/marts/`).
- Evidence rows — every test id and target below exists; Record updates —
  every listed file is in `git diff main...HEAD`.

## Done-when

1. **The offline gate runs green on a clean checkout with no services.**
   *Evidence: row 1.*
2. **The gate refuses what it must refuse, in one line, never a traceback:** a
   SPEC outside `specs/`, a missing Evidence test id, a Record-updates file
   absent from the diff, a `fixtures/` change with no `Freeze:` line in the
   spec. *Evidence: row 2.*
3. **The docs are load-bearing:** every relative link and anchor resolves;
   every `make` target a living doc names exists; no banned word in a living
   doc (CLAUDE.md, README, SPEC, BACKING) or under `study/`; the glossary (when it exists) has ≤ 10 terms; the
   "Open BACKLOG rows: **N**" count matches. Each check reports an error on a
   planted violation. *Evidence: row 3.*
4. **The evidence contract is checked mechanically:** a non-Pending BACKING
   row whose SQL file is missing, any row whose tag is outside the four, or a
   Measured or Documented row with no source, fails; a `sql/marts/*.sql` no row names fails;
   the empty table passes. *Evidence: row 4.*
5. **Claude Code config tracked in git is prose and hook scripts only:**
   nothing under `.claude/` but `agents/*.md`, `commands/*.md`, `hooks/*.py`
   is tracked; `.claude/settings*.json` and `.mcp.json` are gitignored.
   *Evidence: row 5.*
6. **CI is green on the Phase 0a PR** with SHA-pinned actions, `uv sync
   --locked`, `permissions: contents: read`, `persist-credentials: false`.
   *Evidence: row 6 — verified on first push; BACKLOG row until then.*

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `make review-gate` prints `review-gate OK: 5/5 checks` (no SPEC: test, lint, docs, backing, fixtures) / `review-gate OK: 7/7 checks` with SPEC (+ evidence, records) |
| 2 | `tests/test_review_tools.py::test_spec_outside_specs_is_refused`, `::test_gate_fails_on_a_missing_evidence_test_id`, `::test_gate_fails_on_a_record_file_absent_from_the_diff`, `::test_fixture_change_without_freeze_line_fails`, `::test_cli_refusals_are_one_line_exit_2`, `::test_collected_tests_finds_the_suite`, `::test_make_review_gate_refuses_end_to_end` |
| 3 | `tests/test_check_docs.py::test_check_links_reports_a_broken_link_and_anchor`, `::test_check_make_targets_reports_an_unknown_target`, `::test_check_banned_words_reports_each_hit`, `::test_check_glossary_reports_an_eleventh_term`, `::test_check_backlog_count_reports_a_mismatch`, `::test_every_named_make_target_exists_today`; `make check-docs` prints `check-docs OK` |
| 4 | `tests/test_check_backing.py::test_empty_table_is_ok`, `::test_missing_sql_file_fails`, `::test_tag_outside_the_four_fails`, `::test_measured_without_source_fails`, `::test_orphan_mart_sql_fails`, `::test_pending_row_is_ok_without_source`; `make check-backing` prints `check-backing OK: 0 rows, 0 marts` |
| 5 | `tests/test_claude_config.py::test_tracked_claude_config_is_prose_and_hook_scripts_only`, `::test_settings_and_mcp_are_gitignored` |
| 6 | GitHub Actions `ci / lint-test` green on the PR |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all SPEC values, the gate acts only on an existing file under `specs/`; nothing else is derived from the value. | `tests/test_review_tools.py::test_spec_outside_specs_is_refused` — `../x`, absolute, a directory, empty |
| For all user variables of a `make` target, the value reaches Python as ONE single-quoted literal with no shell or make-function expansion, from either origin, and is validated there. | `tests/test_makefile.py::test_user_variable_reaches_python_as_one_literal_from_both_origins` — `"; echo pwned; "`, `$(shell …)`, env vs command line via `make -n` |
| For all BACKING rows, the tag is one of exactly four; a Measured or Documented row names a source of the declared shape (a URL, a markdown link, or a backticked dataset name — each `;`-separated part); every SQL path given resolves under `sql/`; a non-Pending row's SQL file exists (a Pending row may name a file not built yet). For all `sql/marts/*.sql`, at least one row names it. An empty table with no marts is OK. *(Amended round 1.)* | `tests/test_check_backing.py::test_tag_outside_the_four_fails`, `::test_measured_without_source_fails`, `::test_missing_sql_file_fails`, `::test_sql_path_traversal_is_refused`, `::test_pending_row_is_ok_without_source`, `::test_orphan_mart_sql_fails`, `::test_empty_table_is_ok` |
| For all docs-guard checks, a violating input makes the check report an error (no check is vacuous-green). | `tests/test_check_docs.py::test_check_links_reports_a_broken_link_and_anchor`, `::test_check_make_targets_reports_an_unknown_target`, `::test_check_banned_words_reports_each_hit`, `::test_check_glossary_reports_an_eleventh_term`, `::test_check_backlog_count_reports_a_mismatch` |
| For all doc citations of a `make` target, the target exists as an exact token in the Makefile; a partial rename fails. | `tests/test_check_docs.py::test_partial_rename_is_a_failure`, `::test_every_named_make_target_exists_today` |
| For all tracked paths under `.claude/`, the file is agent or command prose or a hook script. | `tests/test_claude_config.py::test_tracked_claude_config_is_prose_and_hook_scripts_only` |
| For all `fixtures/**` changes on a branch, the spec declares `Freeze:` or the gate FAILs (fixtures are read-only after the phase that froze them). | `tests/test_review_tools.py::test_fixture_change_without_freeze_line_fails` |

**Amendment (review round 1, 2026-09-01)** — four dispositions that change a
mechanism's kind or the contract, written before any fix was implemented:

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| **Source shape.** For all Measured or Documented rows, the source cell parses to the declared shape; a placeholder of any spelling (`TBD`, `?`, `—`) is refused. Replaces the denylist of known placeholders (Boundary contract: a closed shape, not a list of bad cases). Restores invariant 3. | `tests/test_check_backing.py::test_measured_without_source_fails` — `TBD`, `?`, `—`, empty all fail; a URL, a markdown link, a backticked name pass |
| **Every named test exists.** For all test ids a spec names — in Evidence, Invariants and Threat model alike — the id is collected by pytest; a section the template marks REQUIRED that is missing, or an Evidence section naming no test, is a FAIL, never a vacuous pass. | `tests/test_review_tools.py::test_invariant_and_threat_model_ids_are_checked`, `::test_gate_fails_on_a_missing_or_empty_required_section` |
| **Pending exemption (invariant 3 reworded).** The file-exists clause holds for non-Pending rows; every given path still resolves under `sql/`. The code, BACKING.md and DECISIONS already stated this; the spec was the outlier. | `tests/test_check_backing.py::test_pending_row_is_ok_without_source`, `::test_sql_path_traversal_is_refused` |
| **SPEC.md names BACKING rows, never `make` targets** (a rule, not code): SPEC.md stays a LIVING doc whose every `make` mention must exist; a chart says which BACKING row backs it, and BACKING's Pending rows carry the not-yet-built paths. Recorded in CLAUDE.md → Writing rules and DECISIONS.md. | `tests/test_check_docs.py::test_every_named_make_target_exists_today` (SPEC.md is in LIVING) |

**Amendment (review round 2, 2026-09-01)** — six dispositions that change a
mechanism's kind or the contract, written before any fix was implemented:

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| **Source shape, closed at both ends (restates amendment row 1).** For all Measured or Documented rows, every `;`-separated part of the source cell is exactly one of: a URL `https?://…` with no whitespace; a markdown link whose destination is such a URL; a backticked dataset name of two or more lowercase segments joined by `-`, `_`, `.` or `/` (`open-damir-2026-01`, `fixtures/anchors/seed.csv`). Nothing trails a part. So `` `TBD` ``, a link whose destination is `javascript:…` or `../x`, a blank backtick and "URL then prose" are all refused — the shape is the rule, not a list of bad cases. The SQL-file cell's "no file yet" spelling is likewise declared: blank or `—`, nothing else. | `tests/test_check_backing.py::test_measured_without_source_fails`, `::test_source_shapes_accepted` |
| **Every row carries its id.** For all BACKING rows, the claim cell starts with `B<beat>.<n>` followed by a space; a row without it is a FAIL (the id is what SPEC.md cites, so it is checked, not asserted). | `tests/test_check_backing.py::test_claim_without_row_id_fails` |
| **Every REQUIRED section is present (restates amendment row 2).** For all four sections the template marks REQUIRED — Evidence, Invariants, Record updates, Threat model — a missing one is a FAIL, never silence. | `tests/test_review_tools.py::test_gate_fails_on_a_missing_or_empty_required_section` |
| **A `Freeze:` line grants exactly what it names.** For all `fixtures/**` changes, a `Freeze: fixtures/<name>/` line (trailing slash) covers that directory and requires `fixtures/<name>/MANIFEST.sha256` in the diff; a `Freeze: fixtures/<path>` line covers that one file; a path named in the line never widens to its parent. | `tests/test_review_tools.py::test_fixture_change_without_freeze_line_fails` |
| **Diff paths are read exactly.** For all paths `git diff` reports, the gate reads each one whole (`-z`, split on NUL), so a path with a space, a quote or a non-ASCII letter still matches `fixtures/` and the record list. | `tests/test_review_tools.py::test_diff_paths_are_read_exactly` |
| **Tracked prose under `.claude/` is a document class.** For all `.claude/**/*.md`, every relative link resolves and every `make` target named exists — the same checks as a living doc, minus banned words and the glossary (an agent may name a banned word to flag it). | `tests/test_check_docs.py::test_every_named_make_target_exists_today`, `::test_tooling_prose_is_checked` |

Also restored in this round, mechanism unchanged in kind: the BACKLOG count
check errors (never returns green) when a record file is absent and skips the
header row by position, not by the word "Item"; `anchors()` strips fenced
blocks before reading headings; the hook names all four fail-open exits in its
header and reads its timeout from `RUN_TESTS_TIMEOUT` (digits only, else 120 s)
so the blocking branch is tested; the study glob covers `study/**/*.html`;
`.gitignore` covers `.env*`; every test runs with `UV_OFFLINE=1` so no test can
download; a new test pins the gate's printed line per check (Evidence row 1)
and one pins `ci.yml`'s SHA pins, read-only token and `--locked` (row 6).
Amendment row 4 above (SPEC.md names BACKING rows) is vacuous until `SPEC.md`
exists in Phase 0b — `check_docs` skips an absent living doc.

## Pinned decisions (do not re-litigate)

- **Gate scripts are stdlib-only and hardened from day one** — spec-path
  validation, `$(call _Q,$(value VAR))` quoting, `unexport`, one-line
  refusals with exit 2. Satisfies invariants 1–2. Rejected: a lighter gate
  that earns hardening incident by incident (the reference's round 1).
- **No mutation sweep and no round tags** (`docs/PLAN.md` §2). The sweep is a
  BACKLOG row with the trigger "a bug in `classify/` or `models/` a green
  suite missed"; `/review-round N` ranges over `main...HEAD` and N is a label.
  Rejected: copying the reference's 26 KB of tooling before a survivor class
  exists.
- **Hook wiring is local-only.** `.claude/hooks/run-tests.py` is tracked;
  `.claude/settings*.json` and `.mcp.json` are gitignored; a test pins what is
  tracked. Satisfies invariant 6. Rejected: a committed `settings.json` (it
  would auto-run an inbound branch's hook for anyone opening the repo).
- **`check_backing.py` reads the brief's §8 table shape exactly** — columns
  `Study claim | Mart table | SQL file | Upstream source | Tag`; SQL file is a
  path under `sql/`; tag ∈ {Measured, Documented, Modeled, Pending}; Pending
  rows may have an empty source. Satisfies invariant 3. Rejected: a YAML
  sidecar (two places to keep in step).
- **Python 3.12 via `uv`, dev dependencies only.** `duckdb` lands in Phase 1,
  `pyyaml`/`httpx` in Phase 2, `anthropic` in Phase 6, the Snowflake
  connector in Phase 10. Rejected: installing the whole allowlist up front.
- **Package and project name `friction_ledger` / "The Friction Ledger"**; the
  directory `claimwatch` is left alone (PLAN §6.6 default).

## Scope (files)

- `CLAUDE.md` (v0 from PLAN §7), `DECISIONS.md`, `BACKLOG.md`, `BACKING.md`
  (header + empty table), `PROJECT_BRIEF.md` (one sentence in §9 pointing at
  the 0a/0b and 5a/5b split in `docs/PLAN.md`), `docs/PLAN.md` (this branch
  tracks it), `specs/TEMPLATE.md`, `specs/phase-0a-machinery.md`
- `Makefile` (`setup test lint check-docs check-backing review-gate help`),
  `pyproject.toml`, `uv.lock`, `.python-version`, `.pre-commit-config.yaml`,
  `.gitignore`, `.github/workflows/ci.yml`, `.github/pull_request_template.md`
- `scripts/{review_common,review_gate,check_docs,check_backing}.py`
- `.claude/agents/{code-reviewer,security-reviewer,functionality-tester,coherence-auditor,study-editor}.md`,
  `.claude/commands/{review-round,selfcheck,phase-start}.md`,
  `.claude/hooks/run-tests.py`
- `tests/{conftest,test_review_tools,test_check_docs,test_check_backing,test_makefile,test_claude_config}.py`

## Record updates (REQUIRED)

- [x] `DECISIONS.md` — new file: "Decisions still in force", "Process", Phase
      0a entry (the ten PLAN §6 defaults, each one line)
- [x] `BACKLOG.md` — new file: mutation sweep deferred; CI green unverified
      until first push; naming-the-target check is agent-only
- [x] `CLAUDE.md` — new file (v0); Current status; Commands; BACKLOG count
- [x] `BACKING.md` — new file: header, §8 rules, empty table
- [x] SPEC.md — none (Phase 0b)
- [x] README.md — none (Phase 9; PROJECT_BRIEF.md is the front door until then)
- [x] `PROJECT_BRIEF.md` — the one-sentence split pointer in §9
- [x] `docs/PLAN.md` — status line; the round-1 corrections
- [x] `specs/TEMPLATE.md` — new file
- [x] `specs/phase-0a-machinery.md` — this spec; the "Delivered" paragraph
      appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

`review-gate` takes `SPEC` and `BASE`. Nothing in this phase deletes, calls a
paid API, or touches the network (`make setup`'s `uv sync` is the one download,
a setup step outside the gate).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `make review-gate SPEC=` | no SPEC → checks a–d only, prints `SKIP evidence, records` | refused, exit 2, one line | one literal argv token; refused as not-a-file; nothing runs | reaches the recipe as one literal, validated in Python like a command-line value | n/a (no CONFIRM in 0a) | `tests/test_makefile.py::test_user_variable_reaches_python_as_one_literal_from_both_origins`, `tests/test_review_tools.py::test_spec_outside_specs_is_refused` |
| `BASE=` | defaults to `main` | validated `[\w./-]+`, no leading `-`, else refused; a well-formed but unknown or `..`-shaped rev is not refused by Python — git rejects it and the gate prints one FAIL line | one literal; refused | same | n/a | `tests/test_review_tools.py::test_base_is_validated` |

Stated residual: `MAKEFLAGS='SPEC=…'` is a make-level override; the threat
model is "mistakes, not a user who controls the environment".

## Review & stack risk

- **code-reviewer** (triggered — scripts, tests, Makefile): the guards against
  CLAUDE.md v0; stdlib-only; one-line refusals; no clock, no network.
- **security-reviewer** (triggered — CI workflow, `.gitignore`, hook): SHA
  pins, `--locked`, `contents: read`, `persist-credentials: false`, no secret
  in any file, `.gitignore` covers `.env*`, `data/`, `*.duckdb`,
  `.claude/settings*.json`, `.mcp.json`.
- **functionality-tester** (triggered): the DONE command; plants each
  violation in a tmp tree and shows the one-line FAIL; runs the hook on a
  failing test and shows exit 2.
- **study-editor** (triggered — CLAUDE.md prose): the banned-word list is
  honoured in the file that states it; the one-line description passes the
  dinner-table test.
- **coherence-auditor** at exit: CLAUDE.md Repo map lists only *(Phase N)*
  dirs; PLAN §2 verdicts match what was built; BACKLOG count.
- Stack risk: `uv` resolving Python 3.12 on this macOS; ruff and pre-commit
  versions pinned in lockstep (`pyproject` dev group ↔ `.pre-commit-config`
  rev). Verify in the first hour.

## Out of scope (deferred, recorded)

- `SPEC.md`, the full `BACKING.md` table, the glossary — Phase 0b.
- Mutation sweep — BACKLOG row.
- `weekly.yml` — Phase 4.
- Any `sql/`, `fixtures/`, `pipeline/` file — Phase 1.

## Delivered (2026-09-01, PR pending)

As planned, plus: a self-check found and fixed one gate bug live (`pytest
--collect-only` under a doubled `-q` printed no node ids). Review round 1
(five agents) reported 44 findings, no BLOCKER: 16 correctness fixes landed
one per commit, four fix amendments (source shape as a closed parse, every
named test id checked, the Pending exemption in invariant 3, "SPEC.md names
BACKING rows"), one records-and-voice commit, four BACKLOG rows. 59 tests;
`make review-gate SPEC=specs/phase-0a-machinery.md` prints `7/7`. CI green is
verified on first push (BACKLOG row).
