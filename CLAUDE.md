# CLAUDE.md — The Friction Ledger

## What this is

We read what customers of French digital-first health insurers say in public
reviews about refunds that get stuck, count what they complain about, and work
out what a wrongly blocked refund costs. The study tells it in five parts.
Every chart can be opened down to the reviews behind it, every formula is
printed next to its result, and every assumption is either sourced or clearly
labeled as a guess.

How this is built: reviews are scraped, cleaned and tagged by theme (rules
first; a language model only for what rules could not decide, checked against
hand labels); a cost model and a guardrail simulator, both plain arithmetic,
turn the counts into euros; the study is a Metabase dashboard, a static HTML
page and the README.

Read in this order: `PROJECT_BRIEF.md` (what we build and why — the master
document), `SPEC.md` (the study's structure: the five parts and every chart),
`BACKING.md` (the evidence contract: claim → table → SQL → source → tag), this
file (how we work), then the active spec in `specs/`. `docs/PLAN.md` is how
this workflow was designed; `DECISIONS.md` is the why-not-X log.

## Architecture

Reviews and public data come in on the left, get cleaned and tagged by theme
in the middle, and come out on the right as the numbers the study shows.

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

One line per place. The detail lives in each module's docstring, each spec's
Delivered paragraph and `make help`, not here.

- `PROJECT_BRIEF.md` (the master document), `SPEC.md` (the five parts —
  *beats* in the row ids `B<beat>.<n>` — and every chart with its tag and
  BACKING row), `BACKING.md` (the evidence contract, enforced by `make
  check-backing`), `DECISIONS.md`, `BACKLOG.md` and `LESSONS.md` (the
  records; the last is what reached a review round and what carries it now),
  `docs/PLAN.md` (how this workflow was designed).
- `specs/` — one spec per phase from `specs/TEMPLATE.md`, ONE DONE command
  each; the "Delivered" paragraph appended at exit is the phase's history.
- `scripts/` — the offline guards (`review_gate.py`, `check_pins.py`,
  `check_docs.py`, `check_backing.py`), `review_common.py` (their shared
  reader: a declared binary asset is read as its text channels, anything else
  as UTF-8, an unreadable file fails by name), `neutrality_hashes.txt`.
- `tests/` — pytest; no services, no network, no key. `tests/pins.py` holds
  every pinned number; `tests/repo_text.py` wraps the guards' reader for the
  layout tests that walk a package.
- `.claude/` — agents (report-only), skills (the three standards,
  `/challenge`, the four on-request loop steps), the three hooks. Settings
  are local-only and gitignored.
- `.github/workflows/ci.yml` (the offline checks and rebuilds, listed under
  Git workflow), `weekly.yml` (the scheduled scrape; the one workflow that
  writes to the repo, `data/snapshots/` only), `pull_request_template.md`.
- `pyproject.toml`, `uv.lock`, `.python-version`, `.pre-commit-config.yaml` —
  the toolchain (uv, ruff, pytest, pre-commit), pinned in lockstep.
  `.env.example` — placeholders for the untracked `.env`; the one `.env*`
  file tracked.
- `sql/raw/`, `sql/staging/`, `sql/marts/` — plain SQL, one file per table;
  the header names the grain, the provenance columns and the BACKING rows
  fed. A Python-fed mart has a DDL-only `.sql` and one `write_*` function
  in `pipeline/build.py`.
- `pipeline/` — `warehouse.py` (the one place that knows DuckDB from
  Snowflake), `build.py` (raw → staging → marts, the classify step, the
  Python-fed mart writers), `cli.py` (the validating `make` entry),
  `sql_lint.py` (the portability/clock denylist), `label_sample.py`.
- `ingest/` — the scrapers: `sources.py` (every source as one declaration;
  the one place a brand-carrying address may appear), `politeness.py`,
  `robots.py` (RFC 9309), `parsed.py` (what every parser hands back and the
  declared bounds), `captures.py`, a parser per fetched source — four; two
  sources are hand-read (`trustpilot.py` reads an authorized OFFLINE
  export), `fetch.py` (the only `httpx` import).
  A *capture* is one run's saved copy of the pages exactly as they arrived,
  with each page's address and time and the robots file beside it.
- `classify/` — `labels.py` (the closed seven-label set), `split.py`
  (`sha256(review_id) % 5`), `rules.yaml` + `rules.py`, `llm.py` (the ONE
  model call site), `cache.py` (the text-free decision cache), `combined.py`,
  `eval/` (the ONLY reader of the hand-labeled answer key `labels.csv`).
- `opendata/` — Open DAMIR and data.ameli (no insurer, no brand token):
  `sources.py` (both declarations), the stdlib `urllib` DAMIR fetch, the
  guarded slice, the lognormal fit that writes the tracked fit;
  `fee_split.py`, the hand-downloaded data.ameli export sliced to one year's
  four profession-family rows and the extra-billing share it writes (no
  fetch: the host's robots file disallows it).
- `models/` — `cost_model.py::FORMULAS` and `guardrail_sim.py::RULES`: the
  formulas as data, filled into their marts inside `rebuild()`.
- `study/` — the static HTML export, one direction {`text.py`, `model.py`} ←
  `panels.py` ← `export.py` (the display texts as data; the panel types,
  `TAGS` and the render-time contract; the readers from the marts; the
  inline-SVG charts and the page), the committed `friction_ledger.html`;
  `README.md` tells the five beats in prose (`tests/test_readme.py` pins the
  stranger walk); `study/metabase/` — the developer-run, non-CI Metabase
  demonstration (the SQLite export, the idempotent applier, `config.yaml`,
  `DEMONSTRATION.md` with synthetic-only screenshots); `study/paraphrases.yaml`
  — the only review text the drill shows.
- `dags/` *(Phase 10)* — `friction_ledger.py`.
- `fixtures/` — read-only after Phase 1, each set with a `MANIFEST.sha256`:
  `synthetic/` (hand-written fake reviews), `anchors/` (brief §6 figures,
  seeded as Documented), a hand-written capture set per parsed source in
  its exact shape (four), `damir/` (a small, real, brand-free slice),
  `ameli/` (one year's four national profession-family fee rows).
  Re-freezing is a
  `Freeze:` line in the spec plus a DECISIONS entry.
- `data/` — gitignored working output with three tracked subtrees:
  `data/snapshots/` (figures a person read off a page, and the weekly cron's
  — numbers only; both loaded as Measured), `data/damir/claim_cost_fit.csv`
  and `data/ameli/fee_split.csv` (numbers only, each recomputed from its
  frozen fixture by an offline target).

## Commands (macOS, uv)

`make help` lists every target with its one-line meaning; a later phase adds
its targets there and here in the same PR. Every target is offline — no key,
no services, no network — except the classify step of `rebuild` when a key is
set and the two network targets behind `confirm` (`scrape`, `fetch-damir`);
`reset`, also behind `confirm`, is offline but destructive. What `make help`
cannot say:

- `lint` (ruff via pre-commit) REWRITES files, never inside a gate. Its rule
  set is the mechanical half of `code-craft`; a function that stays whole
  carries a one-line `# noqa: <rule> -- <reason>`.
- `review-gate [SPEC=specs/<f>.md] [BASE=main]` runs test + ruff read-only +
  `check-docs` + `check-backing` + fixtures + `check-pins` (every public
  function or class added or changed since BASE is named in a test); one line
  per check, exit 1 on FAIL, 2 on a refused SPEC/BASE.
- `model`, `simulate` and `study` take no variable and print or render
  byte-identical output on a rerun; CI diffs the committed study page.
  `fit-damir` and `split-ameli` take no variable and rewrite their tracked
  artifact byte-identically; `sample-damir [MONTH=] [N=]` and `slice-ameli
  [YEAR=YYYY]` are offline, developer-run, and write a frozen fixture (a
  `Freeze:` line and a DECISIONS entry). `slice-ameli` reads a file a person
  saved from a browser at `data/cache/ameli/honoraires.csv`: the host's
  robots file disallows its API and download paths, so there is no fetch.
- **`make rebuild [TARGET=duckdb] [ROWS=captured|none|synthetic|samples]`** —
  raw → staging → marts, then the classify step: the rules plus, only when
  `ANTHROPIC_API_KEY` is set and only for the reviews the rules left
  `unclassified`, one cached model call each — with no key those reviews stay
  `unclassified` and the run is green. The held-out gate and the theme marts
  are honest to whatever classifier ran; the cost-model and simulator marts
  fill on every input, `none` included. Each `ROWS` input builds its own
  file, `friction_ledger[.<input>].duckdb`, so a sample never lands in the
  corpus: `captured` (default: the anchors, both snapshot CSVs, every capture
  under `data/cache/`), `none`, `synthetic`, `samples` (every frozen sample
  through its real parser; CI). A raw table already in the file must match
  its `sql/raw/` declaration column by column or the rebuild refuses naming
  both sides (`make confirm reset` first).
- **`make confirm <target>`** arms the destructive or network target that
  follows it in the SAME invocation and nothing else: `reset` (DESTRUCTIVE),
  `scrape [SOURCE=]` (NETWORK: robots.txt first and every page checked
  against it, ≥ 2 s per host, identifying User-Agent, no proxy, no retry,
  ≤ 60 pages per source; a source we do not fetch is skipped or, when named,
  refused), `fetch-damir [MONTH=YYYY-MM]` (NETWORK; gigabytes, never in CI).
  The gate is a goal, never a variable; its stamp mechanism and what it does
  not hold against are the Threat model of `specs/phase-3a-snapshots.md`.
  Network and paid targets are developer-run, never by an agent; the
  `ask-gate` hook prompts before `make confirm`.
- **Variables** (`ROWS`, `TARGET`, `SOURCE`, `N`, `MONTH`, `YEAR`, `SPEC`, `BASE`)
  are validated in Python against a closed set or shape and never become a
  path by concatenation.

## Deterministic first (the number one rule — brief §2.1)

Run the pipeline twice on the same data and every number comes out the same,
and a person can redo the arithmetic by hand. A language model is used in one
narrow place and never trusted on its own. The rules:

- Rules, SQL and arithmetic decide everything that can be decided that way.
- A language model is called from exactly one module: `classify/llm.py`. It
  sees only what `rules.yaml` could not decide. Nowhere else, for nothing else.
- The model's output is never trusted by default: it passes the eval gate
  before any chart uses it. The gate scores it on the eval set (reviews labeled
  by hand and kept aside) for how often each theme label is right and how many
  true cases it catches, and writes the scores to the `classifier_quality`
  mart, which the study displays.
- **The no-key run is green.** Delete the API key: the pipeline still runs
  end to end, ambiguous reviews are `unclassified`, and the study shows them
  as a gray "not yet classified" band rather than hiding them. A test proves
  it every phase from 6 on.
- No clock on the data path: `now()` / `current_date` in `sql/` is a bug; time
  is `captured_at` or the review's own date.
- Idempotent everywhere: raw is append-only keyed on natural key + content
  hash; staging dedupes; run twice, row counts unchanged.
- Formulas are data: a printed expression and its callable are one entry in the
  module that owns the quantity, and the printer prints from the entry, so the
  shown formula and the computed number cannot drift; a test pins the outputs.
  The two instances are `models/cost_model.py::FORMULAS` and
  `models/guardrail_sim.py::RULES`.
- No fitted predictive models, no black boxes. The cost model and the
  simulator are pure arithmetic with every parameter on a slider; the
  simulator's claim-cost distributions are fitted to public reimbursement data
  with the fit displayed (brief §7), which anyone can redo.

## The five contracts

Five promises the code keeps, each checked by a test or a guard: every number
says where it came from; every claim has an evidence row; the classifier can
only answer from a fixed list; the same SQL runs on both databases; and the
study names no insurer as its subject.

- **Provenance.** Every raw row carries `source`, `source_url`, `captured_at`,
  `run_id`. Every displayed number carries exactly one tag: Measured,
  Documented, Modeled, Pending. A Pending panel shows no number — never fake
  one.
- **Evidence.** `BACKING.md` is the scope. Work that maps to no row is out of
  scope; a claim that cannot be backed is rewritten or tagged Pending. Each
  row has an id (`B<beat>.<n>`) that `SPEC.md` panels cite.
- **Classification.** Exactly seven labels: the five themes of brief §5,
  `positive`, `unclassified`. A model reply outside the set becomes
  `unclassified`, never an eighth label. The grain is one row per review ×
  theme: a review carrying K themes writes K theme rows, a review with none
  writes one `positive` or `unclassified` row, so a "theme share" counts theme
  rows and a review may appear in two theme bars. Decisions are cached by
  `(review_id, prompt_version, model)`; a re-run calls the model only for
  uncached rows. `classify/eval/labels.csv` is read only by `classify/eval/`;
  the held-out split is `sha256(review_id) % 5`, never random.
- **Portability.** The same SQL runs on the laptop database (DuckDB) and the
  cloud one (Snowflake); exactly one file knows which is which
  (`pipeline/warehouse.py`); pattern-matching lives in `rules.yaml` and
  Python, never in SQL, which is what keeps the SQL portable.
- **Neutrality.** A sector phenomenon, never an exposé. No insurer is named as
  the target of the study, in prose, code, comments or commits — insurers
  appear only as sourced data points. `make check-docs` checks it against
  hashed tokens (`scripts/neutrality_hashes.txt`); the editor and the
  reviewers judge the rest. Paraphrase, link, no personal data.

## Writing rules (brief §2.3)

- Two layers everywhere: the first 2–3 sentences of any section or panel are
  for a non-technical reader; technical detail follows under a signpost.
  Rigor is never removed to simplify — it moves one layer down.
- Name things by what they mean, not what they are.
- One glossary per delivery surface (the README's for the arriving reader,
  SPEC.md's for the chart reader), ten terms max each, one sentence each with an
  everyday example; no term's definition contradicts the other's.
- Every number in prose wears its tag. No live counters: a "Day N since…"
  figure is frozen at the last publicly confirmed date and says so.
- Hypothesis, not verdict: the study tests whether held-claim complaints are
  growing; no sentence assumes the answer before its chart shows it, and a
  chart that refutes it is published as-is.
- Name the sampling bias beside the chart it affects: unsolicited review
  platforms are negatively self-selected, and the rating-trend panel says so.
- `SPEC.md` describes what exists (a living doc to `make check-docs`): it names
  BACKING rows (`B<beat>.<n>`), never a `make` target that does not exist yet;
  the not-yet-built paths live in BACKING's Pending rows.
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
- SQL: one file per table under `sql/raw/`, `sql/staging/` or `sql/marts/`; the
  header comment names the grain, the provenance columns and the BACKING rows
  it feeds; lowercase keywords; no `order by` in a table definition; ANSI only
  (no reader function, no regex, no clock — `pipeline/sql_lint.py` pins it).
- Tagged comments are pointers at records, a closed set of four:
  `TODO(BACKLOG): <open row title>`, `HACK(DECISIONS): <entry title>`,
  `REF: <URL | brief §n | RFC n>`, `INVARIANT(<spec stem> <n>): <why>`. A
  tag opens the comment. ruff refuses `FIXME`, `XXX` and a TODO without its
  parens or colon; `make check-docs` refuses a tag whose record entry does
  not exist (`code-craft` → Comments has the rule).
- Secrets: the API key, the Metabase login and warehouse credentials live in
  `.env` only — never in a tracked file, never in Actions, never echoed. The
  code reads the environment (export `.env` first; nothing loads the file),
  and the only tracked `.env*` file is `.env.example`, placeholders with no
  value. Refusals print names, never values.
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
  files, stop. A finding outside the phase is a BACKLOG candidate in the
  report, never a fix in this diff.
- Build on the synthetic fixture first, prove correctness, then run on real
  scraped rows.
- `fixtures/` is read-only after Phase 1. Re-freezing is a deliberate change
  with a DECISIONS entry and a `Freeze:` line in the spec.
- At each phase exit: run the coherence audit, review BACKLOG.md for due
  rows and LESSONS.md for `open` rows two phases old, append the "Delivered"
  paragraph to the spec.
- Stack surprises: check official docs before working around; log under
  DECISIONS.md → Gotchas.
- Do not add a feature that surfaces in none of the five parts.
- Destructive commands only via a `make` target behind the `confirm` goal
  (Commands); paid or network commands (the model API, a live scrape,
  Snowflake) are the developer's to run, never an agent's unasked.
- Fix amendments: a fix that changes a data structure, a write path, a label
  set or who-writes-what is a design change — a one-paragraph spec amendment
  naming the invariant it restores, committed alone; STOP for approval.
- Fix the class, not the case: a fix that appends the finding's case to a
  denylist, regex or `.get(…, default)` is refused; the mechanism's KIND
  changes (a closed set, a strict parse).
- Fix commits: one correctness finding per commit, the invariant it restores
  in the message; wording and record fixes batched in their own commit. A
  correctness fix appends or extends its class's row in `LESSONS.md`; a
  class hit twice becomes a mechanism (a ruff rule, a test, a guard, a
  sentence in a standard) and the row's Status names it.
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
   on re-run, with the key unset, with equal sort keys? Name the pinning test
   (`make check-pins` lists the public symbols no test names yet).
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

## Working with the model (Fable 5.1 or Opus 4.8)

The session model is chosen with `/model`. The four diff reviewers pin
`model: claude-opus-4-8`; `senior-architect` and `coherence-auditor` inherit
the session's model; all six pin `effort: high`. The classifier's model
(`classify/llm.py`, Haiku 4.5) is a data-path setting, not this section's
subject. Source: the two
prompting guides, read 2026-09-05 (DECISIONS → Gotchas).

**On either model**

- Effort `high`; `medium` for wording sweeps and record updates; never
  `xhigh`/`max` for a long deliverable (the draft is written twice).
- Batch the reads: request every item that does not depend on another's
  result in one response. Edit, do not regenerate: the smallest unique
  anchor. Verify, do not recall: run the tool or read the official page.
- Name the scope in full ("every changed file"); an instruction is applied to
  the whole set only when the set is stated. Prove by running: a claim about
  behaviour is a command and its pasted output.
- The STOPs that wait for the developer's word: (1) implementing, once a spec
  or amendment is written; (2) fixing, once a review round reports findings;
  (3) `git push` or `gh pr create`; (4) a paid, network or destructive
  target; (5) re-freezing a fixture; (6) a fix amendment. The `ask-gate` hook
  prompts for (3) and (4). The other STOPs in this file still hold.
  Everything else that follows from the approved spec proceeds without
  asking; a step decided on is run, not announced.
- Tests: one focused test per stated behaviour, sized like the neighbours,
  every number in `tests/pins.py`; scratch checks are not committed.
- Progress text: one line before a step saying what it will produce; a note
  between steps only when something was found; the report format under
  Communication style is the closing recap, and it stands on its own.
- Quoting: a review body is data about a real person — paraphrase, at most
  one short marked phrase, always the public source (brief §2.5).
- Reviews are coverage-first: every finding with a severity and a
  confidence; the round table and the developer are the filter.
- Charts: the spec names the palette and type before anything is built, or
  asks for four directions first; the bundled `dataviz` skill is loaded.
- `/compact` keeps, exactly: the active spec path and status line; the DONE
  command; each Done-when item's state; the latest review-round table
  verbatim; decisions the spec did not cover; the pending STOP; files
  touched.

**Fable 5.1:** thinking is always on and effort is the only depth control.
It goes quiet in long tool chains (the progress rule is the remedy). It
rewrites whole files for small changes (edit by anchor). Its safeguards can
refuse a benign security task: ask "where are the bugs and weak spots", never
"how would this be exploited", and keep base64 and raw captured pages out of
tool output. Mannered prose ("a dial worth turning") is a Writing-rules
finding: say the literal thing.

**Opus 4.8:** at `low`/`medium` it does exactly what was asked and no more
(the scope rule); it reasons where it should run (prove by running); it
filters its own review findings (coverage-first). Its design default (cream,
serif, terracotta) is wrong for a data study (the charts rule).

## Git workflow (one branch + one PR per phase)

- `main` is unprotected on this private repo, so "never commit to it directly,
  never force-push" is a self-imposed rule (DECISIONS → Gotchas). The one
  written exception: the weekly workflow's identity commits under
  `data/snapshots/` only, staged as that subtree alone.
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
- CI runs `make lint`, `make check-docs`, `make check-backing`, `make test`,
  `make check-pins BASE=origin/main`, `make rebuild ROWS=synthetic`, `make
  idempotency-check`, `make study` + `git diff --exit-code`, and the rebuild
  and idempotency check again with `ROWS=samples` (offline, DuckDB, no key,
  no fetch). Mergeable only when CI is green and the surface's agents have run.
- The developer merges with a merge commit (never a squash: `LESSONS.md`
  cites fix commits by hash, and they must stay reachable from `main`), never
  Claude. After merge: `git checkout main && git pull`.
- Tooling changes (agents, skills, hooks, this file's rules) on
  `tooling/<slug>` from main: no spec, the gate plus the surface's agents,
  never mixed with a phase. Hotfixes on `fix/<slug>` from main, same rules.
  Never mix two phases in a PR; a needed change in an earlier phase is a STOP
  and its own fix PR.

## Which review agents run (by diff surface)

The deterministic gate (`make review-gate`) runs on EVERY range. Agents run
only when the range touches their surface — derived from
`git diff --name-only main...HEAD`, a lookup, not a judgment:

| Surface touched in the range | Agents |
|---|---|
| Code: `*.py`, `sql/**`, `classify/**` (incl. `rules.yaml`), `models/**`, `Makefile`, `scripts/`, `tests/`, `dags/**`, `study/*.py` | code-reviewer, then functionality-tester |
| Sensitive: `.github/`, `ingest/**`, `opendata/**`, `classify/llm.py`, `classify/cache.py`, `pipeline/warehouse.py`, `pipeline/cli.py`, `scripts/`, `dags/**`, `.env*`, `.claude/hooks/`, `.claude/settings*.json`, any target that deletes, calls a paid API or fetches | + security-reviewer |
| Prose: `README.md`, `SPEC.md`, `BACKING.md`, `study/**/*.md`, `study/**/*.html`, `CLAUDE.md` | + study-editor |
| Docs and records only: every changed path is `*.md` | coherence-auditor only, scoped to the changed docs (+ study-editor if a prose file above is in the range) |
| Any of the above at a phase exit | + coherence-auditor over the whole repo (mandatory) |

A range that mixes surfaces runs the union. Running an agent whose surface is
untouched is waste and noise; skipping one whose surface IS touched is a STOP.
`senior-architect` is not surface-triggered: it runs on request
(`/challenge`) on a spec, an amendment or a decision BEFORE implementation,
never inside a review round.

## How the tooling fires across a phase

One loop per phase. Each step names what fires and how: **auto** — the
harness loads a skill from its description or its `paths:` while a matching
file is being written; **on request** — the developer types the command;
**hook** — the harness runs a script, deterministically, with no judgment.

| Step | What fires | Trigger | What it reads |
|---|---|---|---|
| 1. Plan — the spec, from `specs/TEMPLATE.md` | `architecture-fit` (the ten questions, the shapes this repo keeps) | auto, by path (list below) | the spec being written |
| 2. Challenge | `/challenge <spec>` → `senior-architect`: steel-man, findings with an alternative and its cost, verdict | on request; hook-reminded | the plan + the standard (list below) |
| 3. Disposition | the developer, per finding: amend / accept / reject; then the main session stamps the spec | the developer, offline | the report |
| 4. Approve → `/phase-start <slug>` | restates the contract, warns if the spec is unstamped, runs the gate, STOPs for "build" | on request | the spec |
| 5. Build | `code-craft`, `secure-by-construction`, `architecture-fit` (paths below); `run-tests` hook after every `.py`, `.sql`, `.yaml`, `.yml` edit (blocks on red) | auto, by path; hook | the same text the reviewers are preloaded with |
| 5b. Preflight → `/preflight` | `make check-pins`, then one row per changed public symbol: its pinning test, each foreign input's declared shape, the other names the diff or the docs give the same concept, the LESSONS class it could repeat; the records the diff implies | on request, before round 1 | `main...HEAD`, `LESSONS.md`'s open rows |
| 6. Review → `/review-round N` | gate; then by surface (table above): code-reviewer (preloads `code-craft`) → functionality-tester; + security-reviewer (preloads `secure-by-construction`); + study-editor; coherence-auditor at the exit | on request; every agent of the round in one turn; one table; STOP-on-findings | `main...HEAD`, the spec's Invariants, round N−1's table |
| 7. Fix → commit → `/selfcheck` → "push" → PR | fixes one per commit; records batched; the developer merges | on request | the table |

The paths (each skill's `paths:` frontmatter is the source; this list is a
copy the coherence-auditor checks):

- `code-craft`: `**/*.py`, `sql/**`, `classify/rules.yaml`, `Makefile`,
  `tests/**`.
- `secure-by-construction`: `ingest/**`, `opendata/**`, `classify/llm.py`,
  `classify/cache.py`, `pipeline/warehouse.py`, `pipeline/cli.py`,
  `Makefile`, `.github/**`, `.claude/hooks/**`, `scripts/**`, `dags/**` —
  the same paths as the Sensitive row above, so what loads the standard
  while writing also runs the security-reviewer.
- `architecture-fit`: `specs/**`, `sql/marts/**`, `sql/staging/**`,
  `models/**`, `study/**`, `dags/**`, `Makefile` (a new target),
  `pyproject.toml` (a new dependency), `BACKING.md`, `SPEC.md`,
  `DECISIONS.md`. A new module under a code package has no path of its own:
  the session loads the skill by name before creating one.

The standard `/challenge` hands `senior-architect`: brief §2/§8/§9, the five
contracts, the BACKING rows the plan names, the predecessor spec's Delivered
paragraph, `docs/PLAN.md` §2, DECISIONS, BACKLOG, the `open` LESSONS rows. The
stamp the main session writes after the developer's disposition:
`Challenged: <YYYY-MM-DD>, round <k>, spec <8 hex> — <verdict>`, unbolded, at
line start, under the spec's status line; the hex is the hook's `--spec-hash`
of the spec's Invariants and Done-when sections, so an amendment to either
makes the stamp stale.

Across the loop: a skill and its agent read the same text, so the bar the
code was written to is the bar it is reviewed against; the reviewers judge
diffs and never re-judge the plan; one reminder per reason at each entry
point (the `challenge-gate` hook, `/phase-start`, `/review-round`), and none
of them blocks.

## Project tooling

Index only; each entry's own file is its reference. All agents are report-only
by contract: none carry Write/Edit (one carve-out: functionality-tester may
`git worktree add` a throwaway checkout under `mktemp -d`, hand-mutate THERE,
and remove it). Findings are fixed in the main session or explicitly accepted
— never auto-fixed.

- Hooks under `.claude/hooks/`, each fail-open and pinned by its test. The
  wiring is the gitignored `.claude/settings.local.json`, three groups, each
  hook as `{"type": "command", "command": "python3
  \"$CLAUDE_PROJECT_DIR/.claude/hooks/<name>.py\""}`: PostToolUse
  `"Write|Edit|MultiEdit|NotebookEdit"` → `run-tests.py` then
  `challenge-gate.py`; PreToolUse `"ExitPlanMode"` → `challenge-gate.py`;
  PreToolUse `"Bash"` → `ask-gate.py`. `run-tests` (after any
  `.py`, `.sql`, `.yaml` or `.yml` edit, pytest failures-first, blocks on
  red; it runs the checked-out branch's tests with your HOME, so read an
  inbound branch's diff of the hooks, `tests/conftest.py`, `pyproject.toml`
  and `Makefile` first), `challenge-gate` (reminds on an unstamped or stale
  spec; `ask` before `ExitPlanMode`; `--spec-hash` prints the stamp's hash),
  `ask-gate` (`ask` before `git push`, `gh pr create`, `gh pr merge` and
  `make confirm`; a reminder, not a security control). `block-secrets` is
  user-level.
- Agents under `.claude/agents/`: `senior-architect` (plans, via
  `/challenge`), `code-reviewer` (this file's rules, the Invariants, craft),
  `security-reviewer` (this repo's surface and the secure-coding classes),
  `functionality-tester` (the suite, the DONE command, idempotency, the
  no-key run, hand-mutation; after code-reviewer), `coherence-auditor`
  (whole-repo drift; mandatory at each phase exit; the only agent for a
  docs-only range), `study-editor` (voice and neutrality). Each preloads the
  standard its surface is written to.
- Skills under `.claude/skills/`: the three standards (`code-craft`,
  `secure-by-construction`, `architecture-fit`), `/challenge`, the four loop
  steps (`/phase-start`, `/preflight`, `/review-round`, `/selfcheck`; each
  prints, then stops). `strategic-compact` is user-level.

## Current status

**Merged:** Phases 0a–9h, each with its spec under `specs/` (the Delivered
paragraph) and its DECISIONS appendix; the last were 9h, the claim count at the
sample's mean reimbursement cell beside the fitted count (PR #32, 2026-09-12),
and `fix/foreign-shape-shared-home` (PR #33, 2026-09-12: the shared decimal
and count shapes given one home in `ingest/parsed.py` and an AST guard against
a fresh coercion outside them). Phase 9 is complete.

**Delivered, PR open:** Phase 9i on `phase-9i-extra-billing` (spec
challenged round 1, nine amendments applied; built 2026-09-12; review rounds
1 and 2 — the exit round — fixed; DONE command green; Delivered paragraph
appended 2026-09-12): the extra-billing share
from data.ameli's `honoraires` table as one sourced B3.3 row with its
profession-family spread, read by no formula — the
export is a hand download, since the host's robots file disallows the API and
download paths; `slice-ameli` and `split-ameli` are offline.

**Delivered, in review:** `fix/idempotency-classify` (built 2026-09-12): the
classify step's code moved from `pipeline/cli.py::_classify_and_print` into
`pipeline/build.py::classify_step` (the Repo map's home for the step), and
`idempotency-check` now runs it after `rebuild()` with an isolated cache and
compares whole-db `table_counts`, so the six classify-path tables are in its
diff (DECISIONS → Fix; BACKLOG row closed).

**Next:** Phase 10 (the Airflow DAG; its
spec decides how the publish task calls `python -m study.metabase
export|apply`, which are not `make` targets — `docs/PLAN.md` §5 says five
`make` tasks; the classify step's `TARGET`-awareness for Snowflake is still a
BACKLOG row (Phase 10's Snowflake wiring)).

Open BACKLOG rows: **39**.

(Update this section at the end of every working day.)
