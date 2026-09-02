# DECISIONS.md — why-not-X log

One entry per non-obvious choice. **"Decisions still in force"** (first) is the
binding set — ≤ 15 entries, by component, each linking to the phase entry that
argued it. **"Process"** records how the phases are run. **"Gotchas"** records
stack surprises found live. **"Appendix — by phase"** is the full log, oldest
first; an entry a later phase reverses is annotated **Superseded by …** in
place and never deleted.

## Decisions still in force

**Method**

- **Deterministic first; a language model decides in exactly one place.**
  Rules, SQL and arithmetic decide everything that can be decided that way;
  the model reads only the reviews the rules could not label, its output
  passes an eval gate before any chart uses it, and with no API key the
  pipeline still runs and shows a gray "unclassified" band. ([Brief §2.1](PROJECT_BRIEF.md); [Phase 0a](#phase-0a))
- **Every number carries one of four evidence tags**, and every model default
  is either sourced or visibly declared unsourced. `BACKING.md` is the
  contract; `make check-backing` enforces the mechanical half. ([Brief §2.4](PROJECT_BRIEF.md); [Phase 0a](#phase-0a))
- **No dbt, no ORM, no vector store, no cloud VMs.** At ~8 SQL files plain
  SQL is clearer than a framework; knowing when not to use a tool is part of
  the study. ([Brief §2.2](PROJECT_BRIEF.md))
- **No pandas on a pipeline path.** SQL does the work; Python glues with
  DuckDB and stdlib `csv`/`json`, so every transformation is a query anyone
  can re-run. ([PLAN §4.9](docs/PLAN.md); [Phase 0a](#phase-0a))
- **The held-out split is `sha256(review_id) % 5`, never random.** The eval
  set is the same on every machine and every run. ([PLAN §4](docs/PLAN.md);
  [Phase 0a](#phase-0a))
- **Pattern-matching lives in `rules.yaml` and Python, never in SQL.** SQL that
  carries no regex carries no dialect, which is what keeps it portable.
  ([PLAN §4.10](docs/PLAN.md); [Phase 0a](#phase-0a))
- **Formulas are data.** `models/cost_model.py::FORMULAS` is the only place a
  formula is written; the study renders from it and a test pins the outputs.
  ([PLAN §4](docs/PLAN.md); [Phase 0a](#phase-0a))
- **Classification grain: one row per review × theme.** A review carrying K
  themes writes K rows, a review with none writes one `positive`/`unclassified`
  row; a "theme share" counts theme rows. This is what a theme chart means.
  ([Brief §5](PROJECT_BRIEF.md); [Phase 0b](#phase-0b))

**Warehouse**

- **One seam knows DuckDB from Snowflake; the SQL is identical for both.**
  `pipeline/warehouse.py` (`connect`, `run_sql_file`) is the only database-driver
  import; DuckDB is the permanent path and Snowflake is the Phase-10
  demonstration (its connector defers, no import in Phase 1). SQL stays ANSI —
  no reader function, no regex, no clock — which is what keeps it portable.
  ([PLAN §4.1](docs/PLAN.md); [Phase 1](#phase-1))
- **Raw is append-only, idempotent on `(source, external_id, content_hash)`;
  staging keeps the latest capture.** A re-run of an unchanged review inserts
  nothing, an edited review appends a new row, so "run twice, counts unchanged"
  holds; `run_id` is stamped in Python (never in SQL) and is in no natural key
  and no mart. ([PLAN §4 decision 2](docs/PLAN.md); [Phase 1](#phase-1))

**Data**

- **Publish aggregates and code, never the raw review corpus.** The corpus
  is gitignored; hand labels are stored as ids plus labels, no text; CI and
  tests run on a hand-written synthetic fixture; a fresh clone scrapes before
  real charts appear. ([Phase 0a](#phase-0a), PLAN §6.1)
- **Scrape politely, never evade.** Low rate, identifying User-Agent,
  robots.txt honoured, pages cached. If a platform blocks, the fallback is a
  manually captured snapshot tagged Measured — not circumvention. Each
  source's terms position is recorded here when its scraper lands.
  ([Phase 0a](#phase-0a), PLAN §6.2)

**Process**

- See the Process section below.

## Process

- **Workflow machinery established before any pipeline code (2026-09-01).**
  Adapted from the sibling project `ontime-rate-recovery-pipeline`
  (`docs/PLAN.md` §2 has the piece-by-piece verdicts). Three load-bearing
  mechanisms: a spec layer (`specs/TEMPLATE.md`: Invariants / Evidence /
  Record updates / Threat model, one DONE command); phase = branch = PR =
  review gate (`/review-round`, STOP-on-findings, the two-round cap, the
  developer merges); pins and a frozen synthetic fixture so "did it work" is
  a command. The offline guards (`review_gate.py`, `check_docs.py`,
  `check_backing.py`, `review_common.py`) carry their hardening from day one
  (spec-path validation, unexpanded `$(value)` + `_Q` quoting, one-line
  refusals) rather than earning it incident by incident.
- **Phase 0 split into 0a (machinery) and 0b (contracts); Phase 3 into 3a
  (snapshots + polite sources) and 3b (Trustpilot, its own session per the
  brief); Phase 5 into 5a (label sample + wall) and 5b (rules).** The brief's
  rule "done-when is a test or make target" needs the gate to exist before the
  contracts it checks; hand-labeling is human hours, not a session. Numbering
  otherwise follows PROJECT_BRIEF.md §9; each phase's contract is its spec in
  `specs/`, and the "Delivered" paragraph is appended to the spec, never to the
  brief.
- **`SPEC.md` names BACKING rows, never unbuilt `make` targets (round 1,
  2026-09-01).** `check_docs.py` treats SPEC.md as a LIVING doc (every `make`
  mention must exist), while BACKING.md's Pending rows may name paths not
  built yet. Rather than a class change in the guard, the rule is editorial:
  a SPEC.md panel cites its BACKING row id (`B<beat>.<n>`); BACKING carries
  the future paths. Rejected: exempting SPEC.md's `make` mentions (a living
  doc that names commands that do not exist is exactly what the check is for).
- **No symbol-trace check.** The reference's `TRACES` table (doc → exact
  source token) is not adopted: no doc cites a symbol by identity yet, deleted
  symbols are grepped under "Before reporting DONE" item 1, and the coherence
  audit reads the records against the code. Revisit when a doc names a guard
  or function by identity.
- **No mutation sweep, no round tags.** The reference's `mutate.py` and
  `round_tag.py` (~26 KB plus tests) earned their keep on multi-branch SQL and
  a write-back contract; nothing here has that shape yet. BACKLOG row with a
  trigger. `/review-round N` ranges over `main...HEAD`; N is a label.
- **Review agents are selected by diff surface, not run wholesale.** Table in
  CLAUDE.md; `/review-round` classifies `git diff --name-only` and prints the
  list before spawning. A fifth agent, `study-editor`, exists because this
  project's deliverable is prose with rules (brief §2.3, §2.5) that no code
  reviewer checks.
- **The run-tests hook is wired locally, not committed.** A committed
  `settings.json` would auto-execute an inbound branch's hook for anyone
  opening the repo in Claude Code; `tests/test_claude_config.py` pins that
  only agent/command prose and hook scripts are tracked.
- **Naming.** Package and project name `friction_ledger` / "The Friction
  Ledger"; the directory `claimwatch` is left alone (a rename buys nothing
  and breaks the remote).

## Gotchas (stack surprises found live)

None yet. Each entry: the surprise, the official-docs check, what we did.

## Appendix — by phase

### Phase 0a

Branch `phase-0a-machinery`, spec `specs/phase-0a-machinery.md`. The ten
defaults from `docs/PLAN.md` §6, approved 2026-09-01:

1. **Corpus vs. clone-and-run** — labels as ids + labels, corpus gitignored,
   synthetic fixture for CI; a fresh clone scrapes first.
2. **Trustpilot terms** — polite fetch; on refusal, the manual snapshot path;
   no evasion.
3. **Metabase open-source has no dashboards-as-code** — Phase 9 drives it
   through the HTTP API from a small YAML, idempotently; the static HTML
   export is the permanent artifact.
4. **A bot committing to `main`** — one written exception: the weekly
   workflow's identity commits only under `data/snapshots/`; a CI check
   refuses any other path from that author (Phase 4).
5. **Model API** — the Anthropic API via the `anthropic` package (Phase 6);
   key in `.env` only; prompt and model id versioned in `classified_reviews`.
6. **Naming** — `friction_ledger`; directory unchanged.
7. **Phase 0 split** — 0a machinery, 0b contracts.
8. **Hand labeling** — human hours between 5a and 5b; planned on the
   calendar, not in a session.
9. **Open DAMIR is large** — Phase 7 fetches one or two months, filters,
   caches under `data/`, records file names and hashes in BACKING; nothing
   large is committed.
10. **Naming-the-target check** — agent-only for now (BACKLOG row).

Also decided in this phase: Python 3.12 via `uv`, dev dependencies only
(`pytest`, `ruff`, `pre-commit`); `duckdb` lands in Phase 1. The distribution
name in `pyproject.toml` is `friction-ledger` (what PEP 503 normalizes to); the
importable package, when one exists, is `friction_ledger`. CLAUDE.md landed at
~340 lines against PLAN's ~250, and review rounds 1–2 took it to ~390
(plain-layer openers, two writing rules): the five contracts, the agents table
and the tooling index each earn their lines, so the cap is restated as ~400 and
the coherence audit reports growth. `check_backing.py`
lets a **Pending** row name a SQL file not built yet — the brief writes BACKING
before code, so every row starts Pending and flips when its mart lands;
requiring the file for Pending rows would make Phase 0b un-passable. The
hook's matcher is widened to `.sql`, `.yaml` and `.yml`: SQL files, `rules.yaml`
and the workflow files are code in this repo.

**Review round 1 (2026-09-01).** Five agents (code-reviewer,
functionality-tester, security-reviewer, study-editor, coherence-auditor) on
`main...HEAD`: 44 findings, no BLOCKER. Dispositions: 16 correctness fixes,
one per commit (two survived hand-mutations pinned, `sql/../x` traversal
refused, vacuous passes on missing spec sections and same-page anchors closed,
the hook parsed strictly and tested, BASE covered by the both-origins test, one
Makefile-target parser); four fix amendments recorded in the spec's Invariants
(source shape as a closed parse, every named test id checked across Evidence /
Invariants / Threat model, the Pending exemption in invariant 3, "SPEC.md names
BACKING rows"); one records-and-voice commit (this entry, CLAUDE.md's plain
openers and neutral phrasing, BACKING.md's header, the hook's trust boundary
stated, `# v4.4.0`); four BACKLOG rows (link-check edge cases, a second
BACKING table, the render-time Pending check, label arity). One process
lesson: a test helper that piped pytest through `tail` hid a red suite for two
commits; commits are gated on pytest's own exit code since.

**Review round 2 (2026-09-01).** The same five agents on `main...HEAD`: 48
findings, two BLOCKERs (the source shape accepted any backticked text; only two
of the four REQUIRED sections were checked for presence). Correctness findings
sat both inside round-1 fixes and on code round 1 had left untouched, so the
two-round cap did not fire; the source shape was re-implemented once against
its invariant (closed at both ends: URL, link to a URL, two-segment dataset
name) rather than patched. Dispositions: a six-row amendment (source shape,
row ids checked, four REQUIRED sections, `Freeze:` grants exactly, diff paths
read whole with `-z`, `.claude/**/*.md` a document class); fourteen fixes one
per commit (the BACKLOG count no longer vacuous or keyed on the word "Item",
fenced headings are not anchors, `slug()` emits one hyphen per space — the
accepted BACKLOG row's trigger fired —, `.gitignore` covers `.env*`, the hook's
four open exits named and its timeout tested, `UV_OFFLINE=1` under every test,
Evidence rows 1 and 6 pinned, three survived mutations pinned); one wording
commit; this records-and-voice commit (CLAUDE.md opens with the customer, the
Architecture gets a plain sentence, two writing rules — hypothesis not
verdict, name the sampling bias — join Writing rules, "beats" is glossed
once, BACKING.md's rules block and Tag column are glossed, the brief's
provenance columns match the code's four, PLAN's three splits and four hook
suffixes, `/review-round` gains the phase-exit branch, the repo description
passes the dinner-table test). One process lesson, repeated: a commit helper
that piped pytest through `tail` hid a red suite for two commits; both were
folded before push and the helper checks pytest's exit code directly.

### Phase 0b

Branch `phase-0b-contracts`, spec `specs/phase-0b-contracts.md`. Depends on
Phase 0a (PR #1) merged. Wrote the two contract files the gate checks, plus one
guard:

- **`SPEC.md`** — the five parts (beats) and the exact chart list: 19 panels
  across Beats 1–5, each citing its `B<beat>.<n>` BACKING row and naming the tag
  it will wear. Every panel is Pending today (no number before its data lands).
  The rating-trend panel (B1.2) names the negative self-selection of unsolicited
  platforms; B2.5 is framed as the hypothesis, not the verdict. Ten-term
  glossary, an everyday example each.
- **`BACKING.md`** — the full 19-row table, every row Pending; a Pending row may
  name a `sql/marts/` file not built yet (the tag says so). Sources are `—`
  where the number is measured or documented in a later phase; `open-damir` on
  the two open-data rows.
- **Classification grain — one row per review × theme** (closes the label-arity
  BACKLOG row): stated in SPEC.md's Beat 2 and CLAUDE.md's Classification
  contract before any chart is frozen; the code invariant (`classified_reviews`
  grain) lands in Phase 5b. Rejected: one `theme` column per review — a
  multi-theme review could not then be counted per theme.
- **Citation guard** — one addition to `check_backing.py` (check 7): SPEC.md
  `B<beat>.<n>` tokens (outside code fences) and BACKING row ids reconcile both
  ways; an absent SPEC.md is OK. No new `make` target — it runs inside `make
  check-backing`. Pinned by `tests/test_check_backing.py::test_spec_citations`.
  Rejected: a separate `check-spec` target and a check in `check_docs` (which
  does not parse the BACKING table); a "prose-only" marker column (the id in
  SPEC.md is the single source of "cited").
- Tag-on-panel presence and tag-match stay editorial (study-editor,
  coherence-auditor); the render-time "a Pending panel shows no number" refusal
  is still a BACKLOG row for Phase 9.

**Review round 1 (2026-09-01).** Four agents (code-reviewer,
functionality-tester, study-editor, coherence-auditor; security-reviewer not
triggered — no sensitive surface): eight findings, no BLOCKER. Five
wording/record fixes batched in one commit (four SPEC.md voice rewrites, the
spec title to APPROVED, the stale BACKLOG parenthetical); one BACKLOG row
accepted (the citation guard strips fenced blocks but not inline code spans,
count 5 → 6); two spec-sanctioned deferrals accepted (the Phase 5b grain code
test; the render-time no-number check). The gate stayed 7/7 and the two-round
cap did not apply (round 1).

### Phase 1

Branch `phase-1-schema`, spec `specs/phase-1-schema.md`. Depends on Phase 0b
(PR #2) merged. Built the empty warehouse: raw + staging DDL for reviews with
the four provenance columns, the DuckDB/Snowflake seam, the two frozen fixture
sets, `tests/pins.py`, and the portability + idempotency guards. No mart, no
scraper, no model.

- **All 13 marts (and `platform_snapshots`) are deferred to the phases that
  land their upstreams; Phase 1 builds raw + staging for reviews only.** Every
  mart depends on data a later phase produces — snapshots (Phase 3), the gated
  classifier (5b–7), the cost model / simulator (8), or the whole pipeline
  (Beat 5) — so building any now would either reach into a future phase or fix a
  table's columns before its subsystem is designed. Every BACKING row stays
  Pending; `check-backing` sees 19 rows, 0 marts, 0 orphans. **This narrows the
  brief's Phase 1 "All DDL (raw/staging/marts)" to the layers whose upstream
  exists.** The narrowing is recorded here and flagged in the spec for the
  developer's call; PROJECT_BRIEF.md is not silently edited. Rejected: empty
  mart stubs (assert a schema before its subsystem exists); building the four
  snapshot marts now (`platform_snapshots` is Phase 3's table — one phase, one
  diff). `theme_share_by_month` (B2.2, monthly × segment) stays distinct from
  `theme_share_by_segment` (B2.5).
- **The warehouse seam and idempotent raw** — promoted to "Decisions still in
  force" above (Warehouse).
- **`run_id` is stamped in Python, not SQL; in FIXTURE mode it is the fixture
  name.** So `sql/` stays clock-free, a changing `run_id` never duplicates a row
  or moves a number, and the synthetic rebuild is byte-stable, not merely
  count-stable. Rejected: `run_id` from `now()` in SQL.
- **The fixture is read in Python (stdlib csv) and inserted with a portable
  guard** — DuckDB's `read_csv` is dialect-bound, so the load lives in the
  driver, not in a `sql/` file (no pandas). `insert … select … where not exists`
  is ANSI.
- **`sql/raw/` joins `sql/staging/` and `sql/marts/`** as a table-DDL directory
  (raw table creation is SQL, scanned by the portability guard), added to the
  Repo map and the SQL-file convention.
- **One validating CLI behind `make`; `reset` is the only destructive target,
  gated by `$(origin CONFIRM)`.** `rebuild`/`idempotency-check` take
  `TARGET`/`FIXTURE` as a closed set validated in Python; an environment
  `CONFIRM=yes` does not confirm a `reset`. Mirrors the SPEC/BASE shape.

**Gotchas:** none — DuckDB's `create or replace`, `insert … where not exists`
and `information_schema.tables` behaved as the official docs describe.

**Review round 1 (2026-09-02).** Five agents (code-reviewer,
functionality-tester, security-reviewer, study-editor, coherence-auditor) on
`main...HEAD`: 11 findings, no BLOCKER. functionality-tester: works — DONE green,
all five hand-mutations caught. security-reviewer and study-editor: pass (two
optional voice suggestions declined — no regression). Dispositions: two
correctness fixes, one per commit — the staging `content_hash` tiebreak now
pinned by a both-insertion-orders test (invariant 3), and `reset` refuses a
non-duckdb TARGET with the CLI's one-line refusal instead of an uncaught
ValueError; one coverage-tests commit (the `RATING_RANGE` span, `reset()`
deletion scope, and `main()`-level exit-2 on a refused value); one record/wording
commit (the zero-row phrasing clarified — `make rebuild` is 0/0 on a fresh
warehouse, raw being append-only; the stale `ci.yml` repo-map one-liner; the spec
title to APPROVED). The two-round cap did not apply (round 1).
