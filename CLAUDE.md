# CLAUDE.md — The Friction Ledger

## What this is

A public-data study of why health-insurance refunds get stuck, where every
chart drills down to its raw evidence, every formula is printed next to its
output, and every assumption is either sourced or clearly labeled as a guess.
We read what customers of French digital-first health insurers say in public
reviews, count what they complain about, and work out what a wrongly blocked
refund costs. The study tells it in five parts.

How this is built: reviews are scraped, cleaned and tagged by theme (rules
first; a language model only for what rules could not decide, checked against
hand labels); a cost model and a guardrail simulator, both plain arithmetic,
turn the counts into euros; the study is a Metabase dashboard, a static HTML
page and the README.

Read in this order: `PROJECT_BRIEF.md` (what we build and why — the master
document), `SPEC.md` (the frozen study structure — Phase 0b), `BACKING.md`
(the evidence contract: claim → table → SQL → source → tag), this file (how we
work), then the active spec in `specs/`. `docs/PLAN.md` is how this workflow
was designed; `DECISIONS.md` is the why-not-X log.

## Architecture

```
 Review platforms      Open health data      Company disclosures
 (unsolicited voices)  (claim cost distros)  (revenue, fraud savings)
        \                     |                      /
         v                    v                     v
          scrape -> load_raw -> clean -> classify -> publish     (one Airflow DAG, Phase 10)
                              |
                              v
                  Warehouse (DuckDB by default; Snowflake behind TARGET=)
                   raw  ->  staging  ->  marts
                 (as-scraped, (clean,      (study-ready
                  provenance)  deduped)     metrics)
                              |
             +----------------+----------------+
             v                                 v
     Deterministic models              The study
     (cost model, guardrail sim)  ->   (Metabase + HTML export + README)

 classify: rules.yaml decides the clear cases -> the model sees only the rest
           -> eval gate vs held-out hand labels -> theme label | unclassified
```

## Repo map

- `PROJECT_BRIEF.md` — the master document. `SPEC.md` *(Phase 0b)* — the five
  beats and the exact chart list, each with its tag and BACKING row.
  `BACKING.md` — the evidence contract (§8 of the brief); `make check-backing`
  enforces it. `DECISIONS.md`, `BACKLOG.md` — the records.
- `docs/PLAN.md` — the design of this workflow: adopt/adapt/drop verdicts on
  the reference project, the phase re-cut, the decisions taken.
- `specs/` — one spec per phase from `specs/TEMPLATE.md`, ONE DONE command
  each. The "Delivered" paragraph is appended to the spec at exit.
- `scripts/` — the offline guards, none a pytest file: `review_gate.py`,
  `check_docs.py`, `check_backing.py`, `review_common.py` (shared).
- `tests/` — pytest; no services, no network, no API key. `tests/pins.py`
  *(Phase 1)* holds every pinned number.
- `.claude/` — agents (report-only), commands, the run-tests hook. Settings
  are local-only and gitignored.
- `.github/workflows/ci.yml` — lint, check-docs, check-backing, test.
  `weekly.yml` *(Phase 4)* — the scheduled scrape + snapshot commit.
  `.github/pull_request_template.md` — the PR body.
- `pyproject.toml`, `uv.lock`, `.python-version`, `.pre-commit-config.yaml` —
  the toolchain (uv, ruff, pytest, pre-commit), versions pinned in lockstep.
- *(Phase 1)* `sql/staging/`, `sql/marts/` — plain SQL, one file per table;
  `pipeline/warehouse.py` — the one place that knows DuckDB from Snowflake;
  `fixtures/synthetic/` — hand-written fake reviews, read-only after Phase 1;
  `fixtures/anchors/` — the brief's §6 public figures with source URLs.
- *(Phase 2+)* `ingest/` — scrapers and snapshot capture. *(Phase 5+)*
  `classify/` — `rules.yaml`, `rules.py`, `llm.py` (the ONE model call site),
  `eval/` (the only reader of `labels.csv`). *(Phase 8)* `models/` —
  `cost_model.py` (`FORMULAS`), `guardrail_sim.py`. *(Phase 9)* `study/` —
  Metabase setup + the HTML export. *(Phase 10)* `dags/friction_ledger.py`.
- `data/` — gitignored working output (corpus, cached pages, `*.duckdb`);
  `data/snapshots/` *(Phase 4)* is the one tracked subtree.

## Commands (macOS, uv)

`make help` lists them. Each later phase adds its targets here in the same PR.

- `make setup` — `uv sync`, `pre-commit install`
- `make test` — pytest; offline, no services, no key
- `make lint` — ruff via pre-commit (rewrites files; never inside a gate)
- `make check-docs` — links/anchors, named make targets, banned words,
  glossary size, BACKLOG count (`scripts/check_docs.py`)
- `make check-backing` — BACKING rows ↔ `sql/marts` files ↔ tags ↔ sources
- `make review-gate [SPEC=specs/<f>.md] [BASE=main]` — test + ruff (read-only)
  + check-docs + check-backing + fixtures; with SPEC, Evidence ids and
  Record-updates files. One line per check, exit 1 on FAIL, 2 on a refused
  SPEC/BASE. `/review-round N` runs it first.

## Deterministic first (the number one rule — brief §2.1)

Run the pipeline twice on the same data and every number comes out the same,
and a person can redo the arithmetic by hand. A language model is used in one
narrow place and never trusted on its own. The rules:

- Rules, SQL and arithmetic decide everything that can be decided that way.
- A language model is called from exactly one module: `classify/llm.py`. It
  sees only what `rules.yaml` could not decide. Nowhere else, for nothing else.
- The model's output is never trusted by default: it passes the eval gate
  (scored on the eval set — reviews labeled by hand and kept aside — for how
  often each theme label is right and how many true cases it catches; the
  scores land in the `classifier_quality` mart and are displayed in the study)
  before any chart uses it.
- **The no-key run is green.** Delete the API key: the pipeline still runs
  end to end, ambiguous reviews are `unclassified`, and the study shows them
  as a gray "not yet classified" band rather than hiding them. A test proves
  it every phase from 6 on.
- No clock on the data path: `now()` / `current_date` in `sql/` is a bug; time
  is `captured_at` or the review's own date.
- Idempotent everywhere: raw is append-only keyed on natural key + content
  hash; staging dedupes; run twice, row counts unchanged.
- Formulas are data: `models/cost_model.py::FORMULAS` is the only place a
  formula is written; the study renders from it; a test pins the outputs.
- No fitted predictive models, no black boxes. The cost model and the
  simulator are pure arithmetic with every parameter on a slider; the
  simulator's claim-cost distributions are fitted to public reimbursement data
  with the fit displayed (brief §7), which anyone can redo.

## The five contracts

Five promises the code keeps, each checked by a test or a guard: every number
says where it came from; every claim has an evidence row; the classifier can
only answer from a fixed list; the same SQL runs on both databases; no insurer
is the target.

- **Provenance.** Every raw row carries `source`, `source_url`, `captured_at`,
  `run_id`. Every displayed number carries exactly one tag: Measured,
  Documented, Modeled, Pending. A Pending panel shows no number — never fake
  one.
- **Evidence.** `BACKING.md` is the scope. Work that maps to no row is out of
  scope; a claim that cannot be backed is rewritten or tagged Pending. Each
  row has an id (`B<beat>.<n>`) that `SPEC.md` panels cite.
- **Classification.** Exactly seven labels: the five themes of brief §5,
  `positive`, `unclassified`. A model reply outside the set becomes
  `unclassified`, never an eighth label. Decisions are cached by
  `(review_id, prompt_version, model)`; a re-run calls the model only for
  uncached rows. `classify/eval/labels.csv` is read only by `classify/eval/`;
  the held-out split is `sha256(review_id) % 5`, never random.
- **Portability.** The same SQL runs on the laptop database (DuckDB) and the
  cloud one (Snowflake); exactly one file knows which is which
  (`pipeline/warehouse.py`); pattern-matching lives in `rules.yaml` and
  Python, never in SQL, which is what keeps the SQL portable.
- **Neutrality.** A sector phenomenon, never an exposé. No insurer is named as
  the target of the study, in prose, code, comments or commits — insurers
  appear only as sourced data points. Paraphrase, link, no personal data.

## Writing rules (brief §2.3)

- Two layers everywhere: the first 2–3 sentences of any section or panel are
  for a non-technical reader; technical detail follows under a signpost.
  Rigor is never removed to simplify — it moves one layer down.
- Name things by what they mean, not what they are.
- One glossary, ten terms max, one sentence each with an everyday example.
- Every number in prose wears its tag. No live counters: a "Day N since…"
  figure is frozen at the last publicly confirmed date and says so.
- `SPEC.md` is a living document: it names BACKING rows (`B<beat>.<n>`), never
  a `make` target that does not exist yet; the not-yet-built paths live in
  BACKING's Pending rows.
- Banned words, checked by `make check-docs` over CLAUDE.md, README, SPEC,
  BACKING and `study/` (this fenced block is the one place they may appear):

  ```
  orchestration leverage robust scalable cutting-edge llm-powered
  state-of-the-art seamless comprehensive production-ready powerful
  ```

  Say instead: "runs every night", "handles new reviews without redoing old
  work", "a language model reads each review and tags what it's about".

## Conventions

- Python 3.12 (`.python-version`). Type hints everywhere. No pandas on a
  pipeline path — SQL does the work; Python glues (DuckDB + stdlib csv/json).
- Dependencies: ask before adding ANY package. Pre-approved by phase:
  `duckdb` (1); `pyyaml`, `httpx` (2); `anthropic` (6);
  `snowflake-connector-python` (10); Airflow and Metabase via Docker only;
  dev: `pytest`, `ruff`, `pre-commit`. Anything else is a STOP-and-ask.
- SQL: one file per table under `sql/staging/` or `sql/marts/`; the header
  comment names the grain, the provenance columns and the BACKING rows it
  feeds; lowercase keywords; no `order by` in a table definition.
- Secrets: the API key and warehouse credentials live in `.env` only — never
  in a tracked file, never in Actions, never echoed. Refusals print names,
  never values.
- Scraping: ≥ 2 s between requests to one host, identifying User-Agent,
  robots.txt honoured, pages cached under `data/`. No proxies, no evasion.

## Teaching rule

The first time a stack concept appears in a session (DuckDB vs Snowflake
dialect, an Airflow DAG and BashOperators, Metabase drill-through, GitHub
Actions cron, a precision/recall eval gate, content-hash idempotency), add a
2–4 sentence plain-language explanation of what it is and why it is used here,
BEFORE the implementation. Every line merged must be explainable by the
developer in a design review. Prefer the boring, standard way over the clever
one, and write one sentence in the README about why.

## Workflow rules

- The spec in `specs/` is the contract. Its DONE command is the only
  definition of done. Do not weaken failing tests. If a spec, a fixture,
  BACKING.md or the brief seems wrong, STOP and report — never silently repair.
- Specs follow `specs/TEMPLATE.md`; its four REQUIRED sections — Invariants,
  Evidence, Record updates, Threat model — are mandatory.
- Invariants before mechanisms: properties ("for all X, Y holds"), each with
  the scenario test that falsifies it, written before any pinned decision
  names a mechanism.
- A phase spec is finalized only after its predecessor merges. The FIRST
  commit on a phase branch is the spec (or its reconciliation amendment);
  STOP for approval before implementing.
- ≤ ~6 pinned decisions / Done-when items per spec. Split otherwise.
- One phase, one session, one diff. If a session reaches for a future phase's
  files, stop.
- Build on the synthetic fixture first, prove correctness, then run on real
  scraped rows.
- `fixtures/` is read-only after Phase 1. Re-freezing is a deliberate change
  with a DECISIONS entry and a `Freeze:` line in the spec.
- At each phase exit: run the coherence audit, review BACKLOG.md for due
  rows, append the "Delivered" paragraph to the spec.
- Stack surprises: check official docs before working around; log under
  DECISIONS.md → Gotchas.
- Do not add a feature that surfaces in none of the five beats.
- Destructive commands (dropping a DuckDB file, truncating a table): only via
  a `make` target that prompts unless `CONFIRM=yes` is given on the command
  line — tested with `$(origin CONFIRM)`.
- Paid or network commands (the model API, a live scrape, Snowflake): never
  run by an agent unasked; the developer runs them.
- Fix amendments: a fix that changes a data structure, a write path, a label
  set or who-writes-what is a design change — a one-paragraph spec amendment
  naming the invariant it restores, committed alone; STOP for approval.
- Fix the class, not the case: a fix that appends the finding's case to a
  denylist, regex or `.get(…, default)` is refused; the mechanism's KIND
  changes (a closed set, a strict parse).
- Fix commits: one correctness finding per commit, the invariant it restores
  in the message; wording and record fixes batched in their own commit.
- Review cap: if two consecutive review rounds report correctness findings
  only in the previous round's fixes, stop patching. Write the invariant,
  re-implement against it ONCE, one scoped re-review. A human applies this by
  comparing two tables; `/review-round` prints the reminder, never a verdict.
- Commit at every green state with a descriptive message.
- End each loop with: what changed + decisions the spec didn't cover.

### Before reporting DONE

1. For every symbol deleted or renamed: grep the whole repo (docs, specs,
   Makefile, CI, `.claude/`) and list each hit you updated.
2. For every Done-when item: name the test or command output that proves it.
3. For every new Makefile target with a variable, a delete, a paid call or a
   fetch: show behavior for an empty value, `../x`, a value containing `"; `,
   the variable set from the environment, and no credentials.
4. For every new write path, rule or formula: can it give a different answer
   on re-run, with the key unset, with equal sort keys? Name the pinning test.
5. For every new number a reader sees: its tag and its BACKING row.
6. List every record file touched and every one the change implies you should
   have touched.
7. For each decision the spec didn't cover: the two alternatives not taken and
   why, one line each.
8. For every guard at an input the repo does not own (a scraped page, a model
   reply, a CLI's output): the closed set or declared shape it accepts, the
   test that pins it, and what an unrecognised input does (it refuses or
   becomes `unclassified`).

## Communication style (chat, comments, docs, commits)

- Result first: what changed / passed / failed, then details.
- Plain English, short sentences. No task restatement, no "I will now…", no
  closing summary that repeats the middle.
- One sentence if it fits. Explanations ≤ 4 sentences.
- The banned-word list above applies to chat too. Show the property.
- Code comments only where the code can't say it. One-line docstrings unless
  behavior is non-obvious.
- Reports after a task: files touched, commands run, result, open risks, next
  step. Nothing else.

## Git workflow (one branch + one PR per phase)

- `main` is protected: never commit to it directly; never force-push. The one
  exception, written down when Phase 4 lands: the weekly workflow's identity
  commits under `data/snapshots/` only.
- Review gate BEFORE the remote: run the agents on the finished work and
  report verdicts. Do NOT push or open a PR until the developer has seen the
  verdicts and says to.
- STOP-on-findings: when any agent returns findings, STOP and report them
  verbatim. Do NOT fix anything until the developer has reviewed the issue AND
  the proposed fix and says proceed.
- One consolidated report, not one per agent: wait for every agent in the
  round to finish, then one table over all findings followed by one verdict
  line per agent.
- Start each phase with `/phase-start <slug>` (main, pull, branch, restate the
  spec). Commits small, at green states, prefixed `phase-N:`.
- PR via `gh pr create` when Done-when passes AND verdicts are approved. Body:
  the PR template. Title `Phase N — <name>`.
- CI runs `make lint`, `make check-docs`, `make check-backing`, `make test`
  (Phase 1 adds the synthetic rebuild). Mergeable only when CI is green and
  the surface's agents have run.
- The developer merges (squash), never Claude. After merge: `git checkout
  main && git pull`.
- Hotfixes on `fix/<slug>` from main, same rules. Never mix two phases in a
  PR; a needed change in an earlier phase is a STOP and its own fix PR.

## Which review agents run (by diff surface)

The deterministic gate (`make review-gate`) runs on EVERY range. Agents run
only when the range touches their surface — derived from
`git diff --name-only main...HEAD`, a lookup, not a judgment:

| Surface touched in the range | Agents |
|---|---|
| Code: `*.py`, `sql/**`, `classify/**` (incl. `rules.yaml`), `models/**`, `Makefile`, `scripts/`, `tests/`, `dags/**`, `study/*.py` | code-reviewer, then functionality-tester |
| Sensitive: `.github/`, `ingest/**`, `classify/llm.py`, `pipeline/warehouse.py`, `.env*`, `.claude/hooks/`, `.claude/settings*.json`, any target that deletes, calls a paid API or fetches | + security-reviewer |
| Prose: `README.md`, `SPEC.md`, `BACKING.md`, `study/**/*.md`, `study/**/*.html`, `CLAUDE.md` | + study-editor |
| Docs and records only: every changed path is `*.md` | coherence-auditor only, scoped to the changed docs (+ study-editor if a prose file above is in the range) |
| Any of the above at a phase exit | + coherence-auditor over the whole repo (mandatory) |

A range that mixes surfaces runs the union. Running an agent whose surface is
untouched is waste and noise; skipping one whose surface IS touched is a STOP.

## Project tooling

Index only. All agents are report-only by contract: none carry Write/Edit
(one carve-out: functionality-tester may `git worktree add` a throwaway
checkout under `mktemp -d`, hand-mutate THERE, and remove it). Findings are
fixed in the main session or explicitly accepted — never auto-fixed.

- `run-tests` hook — `.claude/hooks/run-tests.py` (tracked); after any `.py`,
  `.sql`, `.yaml` or `.yml` edit in this repo, runs pytest and blocks on red;
  "no tests collected" is a skip. It runs the checked-out branch's tests on
  your machine with your HOME; the reduced environment keeps environment
  credentials out of the suite and nothing else. Before letting Claude edit on
  an inbound branch, read its diff of `.claude/hooks/`, `tests/conftest.py`,
  `pyproject.toml` and `Makefile` — the hook fires before any review round.
  Wiring is local-only by design: copy into the gitignored
  `.claude/settings.local.json`:
  `{"hooks": {"PostToolUse": [{"matcher": "Write|Edit|MultiEdit|NotebookEdit",
  "hooks": [{"type": "command", "command": "python3
  \"$CLAUDE_PROJECT_DIR/.claude/hooks/run-tests.py\""}]}]}}`.
- `block-secrets` hook — `~/.claude/hooks/block-secrets.py` (user-level,
  already wired); blocks writes containing secret-looking values.
- `code-reviewer` — diff review against this file (deterministic first,
  provenance, tags, formulas, portability, allowlist, scope).
- `security-reviewer` — mandatory when CI, `.env`, a scraper, the model call,
  Snowflake, the weekly commit, `.claude/hooks/`, `.claude/settings*.json`, or
  a destructive target is touched.
- `functionality-tester` — the suite, the spec's DONE command, Evidence rows,
  idempotency, the no-key run, hand-mutation. After code-reviewer.
- `coherence-auditor` — whole-repo drift audit (SPEC ↔ BACKING ↔ marts ↔
  study ↔ README). MANDATORY at each phase exit; the ONLY agent for a
  docs-only range.
- `study-editor` — voice and neutrality (brief §2.3, §2.5) on README, SPEC,
  BACKING claims, `study/`, this file.
- `/review-round N` — gate → invariants → agents by surface → one table →
  "Cap is the architect's call".
- `/selfcheck` — verifies the last commit, then stops.
- `/phase-start <slug>` — main, pull, branch, restate the spec, print the
  BACKING rows in scope, run the gate, stop.
- `strategic-compact` skill — user-level; suggests /compact at breakpoints.

## Current status

**Phase 0a — Workflow machinery** (`phase-0a-machinery`, spec
`specs/phase-0a-machinery.md`): built; review round 1 dispositions landed;
PR pending. The gate, the three guards, five agents, three commands, the hook,
CI, the spec template and the four record files. No pipeline code, no data, no
study text. Next: Phase 0b — `SPEC.md` (five beats, exact chart list, each
panel citing its BACKING row id), the full `BACKING.md` table, the glossary.

Open BACKLOG rows: **7**.

(Update this section at the end of every working day.)
