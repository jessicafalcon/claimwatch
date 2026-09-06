# The Friction Ledger — design and plan (Phase 0 proposal)

**Status: APPROVED 2026-09-01; Phase 0a was built on it** (`specs/phase-0a-machinery.md`; the round-1 corrections below are marked). Written 2026-09-01 after reading
`PROJECT_BRIEF.md` and the reference repo `ontime-rate-recovery-pipeline`
(read-only, used as the workflow exemplar). Approve, amend or strike sections;
Phase 0 starts from the approved version. This document is the plan for how we
build; `PROJECT_BRIEF.md` stays the plan for what we build.

The reference project proved a way of working where every phase is
one branch, judged by a command rather than by opinion, with a small set of
review agents that only report. We keep that skeleton, cut everything that
existed for a cloud stack we do not have, and add three guards this project
needs that the reference did not: a check that every study claim maps to a SQL
file and a source, a check that the writing obeys the brief's language rules,
and a wall between the classifier and the hand labels it is scored against.

---

## 1. What the reference taught (and what it cost)

The reference's own `DECISIONS.md` "Process" entry names its three load-bearing
mechanisms: a spec layer with Invariants / Evidence / Record-updates / one DONE
command; phase = branch = PR = review gate with STOP-on-findings and a two-round
cap; determinism plus frozen fixtures so "did it work" is a diff. Those three
transfer intact.

What it cost: `CLAUDE.md` grew to 900 lines (its Commands section became a
second README), `mutate.py` and `round_tag.py` are ~26 KB of tooling with their
own test suites, and the boundary/credential contracts exist because Terraform,
BigQuery and Spanner were in play. Brief §2.2 ("every tool must earn its
maintenance cost") is the filter below.

---

## 2. Adopt / adapt / drop — every piece of the reference workflow

| Reference piece | Verdict | For this project | Lands in |
|---|---|---|---|
| `CLAUDE.md` skeleton (What / Architecture / Repo map / Commands / Determinism / Contracts / Style / Workflow / Before DONE / Git / Which agents run / Tooling / Status) | **Adapt** | Keep the headings, cap at ~400 lines (0a landed at ~340, ~390 after two review rounds; the coherence audit reports growth). Rule: `CLAUDE.md` holds rules and an index; command semantics live in `make help` and the README. Brief §2 supplies the content (Deterministic first, Plain English, Provenance, Neutrality). | Phase 0a |
| `specs/TEMPLATE.md` — Invariants, Evidence, Record updates, Threat model; ONE DONE command; ≤6 done-when items | **Adapt** | Keep all four sections. Threat model narrowed to targets that take a variable, delete, call a paid API, or touch the network (scrapers, LLM, Snowflake). | Phase 0a |
| `docs/PHASES.md` (separate live plan) | **Drop as a file** | Brief §9 is the phase list; each phase gets a spec in `specs/`; the "Delivered" paragraph is appended to the spec, never to the brief. One numbering, one place. | — |
| `docs/ARCHITECTURE.md` | **Drop** | Brief §4 + `SPEC.md` + `BACKING.md` are the architecture. A fourth document breaks §2.2. Stack surprises go to a `## Gotchas` section in `DECISIONS.md`. | — |
| `DECISIONS.md` — why-not-X log, "still in force" set, superseded-in-place | **Adopt** | The brief's "say in the README why not dbt" is literally this file. README links entries. Cap "still in force" at 15. | Phase 0a |
| `BACKLOG.md` — deferred findings with a revisit trigger, reviewed at phase exit | **Adopt** | Verbatim shape. | Phase 0a |
| `scripts/check_docs.py` — links, named make targets, symbol traces, BACKLOG count | **Adapt** | Add two checks from brief §2.3: **banned words** over README / SPEC / study text / CLAUDE (union of the brief's list and the reference's), and **glossary ≤ 10 terms**. | Phase 0a |
| *(none)* | **New: `scripts/check_backing.py`** | The scoping guard brief §8 asks for: every `sql/marts/*.sql` maps to ≥1 BACKING row; every row's SQL file exists; every row's tag ∈ {Measured, Documented, Modeled, Pending}; every Measured/Documented row names a source of a declared shape; a Pending row has no number in SPEC (enforced at render time, Phase 9 — BACKLOG). `make check-backing`. | Phase 0a |
| `scripts/review_gate.py` — test + ruff + check-docs + Evidence ids + Record-updates diff + deleted symbols + fixture freeze | **Adapt, lighter** | test + ruff + check-docs + check-backing + Evidence ids + Record-updates. Keep the 20-line fixture check (`fixtures/` changes need a `Freeze:` line in the spec). Drop `DELETED`. | Phase 0a |
| `scripts/mutate.py` — mutation sweep, 4 Python + 2 SQL operators | **Defer (BACKLOG)** | 20 KB whose value showed at the reference's multi-branch SQL and write-back. Our load-bearing logic (rules classifier, cost formulas) is pinned by goldens plus the Phase 8 "code formulas equal displayed numbers" test. Trigger: a bug in `classify/` or `models/` that a green suite missed. | BACKLOG row |
| `scripts/round_tag.py` + `/review-round N` with local tags | **Adapt, no tags** | `/review-round N`: gate → agents by diff surface → one consolidated table → STOP. Range is always `main...HEAD`; N is a label; "missed in round N−1" labelling works by pasting the previous table into the agent prompt. Solo repo, PR-sized ranges: the tag machinery buys nothing. | Phase 0a |
| `/selfcheck` | **Adapt** | (a) suite, (b) DONE command, (c) **deterministic-first check** replaces the determinism check: any decision made by a model outside `classify/llm.py`; any `now()`/`current_date` in `sql/`; any number in README/study without a tag; (d) fixtures untouched, (e) divergence, (f) eyeball. | Phase 0a |
| `.claude/hooks/run-tests.py` (PostToolUse, fail-open, local wiring only) | **Adopt + widen** | As-is, plus react to `.sql`, `.yaml` and `.yml` edits — SQL files and `rules.yaml` are code here. Wiring stays in gitignored `settings.local.json` (the reference's reason holds: a tracked `settings.json` auto-runs an inbound branch's hook). | Phase 0a |
| `~/.claude/hooks/block-secrets.py` (user-level, PreToolUse) | **Already wired** | Covers the two secrets this repo will ever have: the LLM API key and Snowflake credentials. Nothing to do. | — |
| `strategic-compact` skill (user-level) | **Keep** | Phase boundaries are the natural compact points. | — |
| `code-reviewer` agent | **Adapt** | Project checks replace dbt/GCP ones — see §3. | Phase 0a |
| `security-reviewer` agent | **Adapt** | Different surface: scrape politeness and ToS, PII in review text, the Actions write token, the API key path, no raw corpus tracked — see §3. | Phase 0a |
| `functionality-tester` agent | **Adopt** | Near-verbatim; the edge-case list is replaced (idempotency, no-key run, dialect, tag coverage). | Phase 0a |
| `coherence-auditor` agent | **Adapt** | The cross-stage contract here is `SPEC.md` ↔ `BACKING.md` ↔ `sql/marts` ↔ study panels ↔ README beats. Mandatory at phase exit; only agent for docs-only ranges. | Phase 0a |
| *(none)* | **New: `study-editor` agent** | Voice and neutrality reviewer for brief §2.3 and §2.5: two-layer opening on every section/panel, "name by meaning", no editorial sentence about one company, paraphrase not quote, no personal data, glossary discipline. Runs when `README.md`, `SPEC.md` or `study/**` text changes. Report-only. | Phase 0a |
| `.github/workflows/ci.yml` — SHA-pinned actions, `uv sync --locked`, `contents: read`, concurrency | **Adopt shape** | Steps: `make lint`, `make check-docs`, `make check-backing`, `make test`, `make rebuild FIXTURE=synthetic` (offline, DuckDB, no key; the variable is `ROWS` since Phase 3a). | Phase 0a |
| *(none)* | **New: `.github/workflows/weekly.yml`** | Brief Phase 4. Cron scrape + snapshot commit. Needs `contents: write`, scoped by the workflow adding only `data/snapshots/`. **No API key in Actions, ever** — the cron runs the deterministic path, so every weekly run is a free graceful-degradation proof. | Phase 4 |
| `.github/pull_request_template.md` | **Adopt** | Done-when check / files touched / decisions the spec didn't cover / open risks. | Phase 0a |
| `.gitignore` | **Merge** | Add `.claude/settings.json`, `.claude/settings.local.json`, `.mcp.json`, `.env.*`, `data/` (whole, not just `raw/` and `corpus/` — snapshots that are meant to be tracked live under `data/snapshots/` with a negation rule). | Phase 0a |
| Dialect dispatch macros (jinja, five macros) | **Adapt the idea** | No jinja, no macros. One rule: ANSI SQL both engines run; `tests/test_sql_portable.py` denylists DuckDB-only forms; Phase 10 is the live proof. Regex lives in Python (`rules.yaml`), never in SQL — that is what keeps the SQL portable. | Phase 1 |
| Truth isolation test (`truth/` never a pipeline input) | **Adapt as labels isolation** | `classify/eval/labels.csv` is read only by `classify/eval/`. `tests/test_labels_isolation.py` greps `classify/rules*`, `classify/llm*`, `sql/`, `models/` for the word. The held-out split is by `sha256(review_id) % 5`, never random. | Phase 5a |
| Seeded generator + frozen `fixtures/tiny/` + `make freeze` + MANIFEST | **Adapt, no generator** | `fixtures/synthetic/`: ~40 hand-written, obviously fake reviews covering all seven labels, plus `platform_snapshots_seed.csv` (the brief §6 anchors) and `MANIFEST.sha256`. Read-only after Phase 1. CI rebuilds from it. No generator program — 40 hand-written rows is the boring answer. | Phase 1 |
| `tests/pins.py` (every pinned number in one file) | **Adopt** | Synthetic row counts per stage, §6 anchors, cost-model outputs at defaults. | Phase 1 |
| Golden check-mode targets (`make report`, `make simulate`, `make readme`, byte-identical regeneration) | **Adopt** | `make study` renders the static HTML from marts + formulas and, in check mode, diffs bytes; `make model` prints the cost table vs pins. | Phases 8–9 |
| Terraform, Spanner, BigQuery, Composer, WIF, budgets | **Drop** | Brief §10. | — |
| dbt conventions (schema.yml, vars, unit tests) | **Drop** | Replaced by SQL-file conventions: one file per table; header comment names grain, provenance columns and the BACKING rows it feeds; lowercase keywords; no `order by` in a table definition. | Phase 1 |
| "Airflow contains no logic" | **Adopt verbatim** | BashOperators over `make` targets, five tasks, one screen. | Phase 10 |
| Teaching rule | **Adopt** | First appearance of Airflow, Snowflake, Metabase drill-through, DuckDB, Actions cron, LLM eval gate: 2–4 plain sentences before the code. | Phase 0a |
| Communication style | **Adopt + merge** | Union of banned words; the deterministic check in `check_docs.py` enforces it over README / SPEC / study. | Phase 0a |
| Boundary / Adapter / Credential contracts | **Adapt, minimal** | Two foreign inputs: scraped pages and the model's reply. Both parse strictly to a declared shape; a model reply outside the seven-label set becomes `unclassified`, never a new label. Secrets: `.env` only, never Actions, never a log. | Phases 2, 6 |

---

## 3. The `.claude/` tree and `scripts/` we propose

```
.claude/
├── agents/
│   ├── code-reviewer.md         adapted — checks in §3.1
│   ├── security-reviewer.md     adapted — checks in §3.2
│   ├── functionality-tester.md  adopted — DONE command, idempotency, no-key run
│   ├── coherence-auditor.md     adapted — SPEC ↔ BACKING ↔ marts ↔ study ↔ README
│   └── study-editor.md          NEW — voice, two-layer, neutrality, glossary
├── commands/
│   ├── review-round.md          adapted — no tags; gate → agents by surface → one table → STOP
│   ├── selfcheck.md             adapted — deterministic-first check
│   └── phase-start.md           NEW — checkout main, pull, branch, print the spec's Done-when
│                                      and the BACKING rows in scope; refuse if a spec is missing
└── hooks/
    └── run-tests.py             adopted — matcher widened to .py|.sql|.yaml|.yml

scripts/
├── check_docs.py       links, make targets, BACKLOG count, banned words, glossary size (no symbol traces — DECISIONS)
├── check_backing.py    NEW — the evidence contract (BACKING.md ↔ sql/marts ↔ tags ↔ sources)
├── review_gate.py      lighter: test, ruff, check-docs, check-backing, Evidence ids, Record updates, fixture freeze
└── review_common.py    spec-path validator, section parser, subprocess runner (stdlib only)
```

Wiring for the hook (local only, `.claude/settings.local.json`, gitignored):
`{"hooks":{"PostToolUse":[{"matcher":"Write|Edit|MultiEdit|NotebookEdit","hooks":[{"type":"command","command":"python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/run-tests.py\""}]}]}}`

### 3.1 `code-reviewer` — project-specific checks (these come first)

- **Deterministic first.** A model is called from exactly one module
  (`classify/llm.py`). Any other import of an LLM client, any "smart" fallback,
  any fitted model in `models/` is a BLOCKER.
- **Graceful degradation.** Every path from "no API key" to a green pipeline is
  intact: `classify` writes `unclassified`, never raises; the export draws the
  gray band. FLAG a `KeyError`/`sys.exit` on a missing key.
- **Provenance columns.** Raw tables carry `source`, `source_url`,
  `captured_at`, `run_id`; raw is append-only; staging dedupes on the natural
  key. FLAG a raw `delete`/`update`, a mart with no upstream provenance path.
- **No clock on the data path.** `now()`, `current_date`, `current_timestamp`
  in `sql/` is a bug; time comes from `captured_at` or the review's own date.
- **Formulas mirrored 1:1.** `models/cost_model.py` is the only place a
  formula is written; the study renders from it. A formula string typed
  anywhere else is a finding.
- **Every number tagged.** A chart, panel or README figure without exactly one
  of Measured / Documented / Modeled / Pending is a BLOCKER; a Pending panel
  with a number in it is a BLOCKER (brief §2.4 "never fake").
- **Parameter rule.** Every model default is sourced (citation in a comment
  and in BACKING) or declared unsourced; a bare constant is a finding.
- **Portable SQL.** DuckDB-only or Snowflake-only forms outside the one
  connection module; regex in SQL.
- **Scope guard.** Anything that does not feed a BACKING row; a second model
  call; embeddings; a proxy library; a live counter.
- **Neutrality in code.** An insurer named as the target of the study in a
  comment, identifier, commit message or docstring (data rows and source URLs
  are fine). Hand this to `study-editor` for prose.
- **Dependency allowlist** (proposed, ask before any other): `duckdb`
  (Phase 1); `pyyaml`, `httpx` (Phase 2); `anthropic` (Phase 6); `snowflake-connector-
  python` (Phase 10); dev: `pytest`, `ruff`, `pre-commit`. Airflow and Metabase
  via Docker only. No pandas on a pipeline path.

### 3.2 `security-reviewer` — this repo's surface

- **Scrape conduct.** Rate limit (≥ 2 s between requests to one host),
  identifying User-Agent, `robots.txt` honoured, pages cached under gitignored
  `data/`. FLAG proxies, header rotation, CAPTCHA handling or any evasion — if
  a platform blocks, the fallback is a manually captured snapshot (rating,
  count, URL, date) tagged Measured, never circumvention. Record the ToS
  position per source in `DECISIONS.md`.
- **Personal data.** Reviewer names, emails, claim numbers, health details
  never reach a tracked file or the export; excerpts shown in drill-through are
  paraphrased or minimal and link to the public source. The raw corpus is
  gitignored; a test asserts no `data/corpus/**` is tracked.
- **Secrets.** The API key and Snowflake credentials live in `.env` only, never
  in Actions secrets used by `weekly.yml`, never echoed. `.gitignore` covers
  `.env*`, `data/`, `*.duckdb`, `.claude/settings*.json`.
- **The Actions write token.** `weekly.yml` is the one workflow with
  `contents: write`; it must `git add` only `data/snapshots/`, pin actions by
  SHA, use `persist-credentials` only for that push, and never run on
  `pull_request`. `ci.yml` stays `contents: read`.
- **Destructive targets.** Anything that drops a DuckDB file or truncates a
  table is a `make` target gated on the `confirm` goal of the same invocation
  (`make confirm reset`; Phase 3a's A4 (d) replaced the `CONFIRM=yes`
  variable, whose command-line origin `MAKEFLAGS` can forge).

### 3.3 `study-editor` — the new agent (report-only)

Reads changed prose in `README.md`, `SPEC.md`, `study/**`, `BACKING.md`. Checks:
every section and panel opens with 2–3 sentences a non-technical reader fully
understands, then signposts the technical layer; names are by meaning, not by
mechanism; no sentence is editorial about a single company; quotes are
paraphrased or minimal with a public link; the glossary stays ≤ 10 terms and
new jargon is either in it or rewritten; the one-line repo description passes
the dinner-table test; the rigor sections exist ("How we made sure the numbers
are trustworthy") and were not deleted to simplify. Banned words are the
deterministic check's job — the editor reports only what a grep cannot.

---

## 4. Design decisions to pin in Phase 0 (beyond what the brief already pins)

1. **Warehouse seam.** `TARGET=duckdb|snowflake` is a `make` variable →
   `pipeline/warehouse.py` exposes `connect()` and `run_sql_file()`. The SQL
   files are identical for both. Nothing else knows which engine runs.
2. **Idempotent raw.** Raw is append-only, keyed `(source, external_id,
   content_hash)`; a re-scrape of an unchanged review inserts nothing, an
   edited review inserts a new row. Staging keeps the latest `captured_at` per
   `(source, external_id)`. "Run twice, row counts unchanged" is `make
   idempotency-check` (rebuild twice, diff counts per table).
3. **Classification is data with provenance.** `classified_reviews`:
   `review_id, theme, decided_by ∈ {rules, llm, unclassified}, rules_version,
   prompt_version, model, decided_at`. Model decisions are cached by
   `(review_id, prompt_version, model)`; a re-run calls the model only for
   rows with no cached decision. Killing the key yields `unclassified` rows,
   never an error.
4. **Eval split is deterministic.** `sha256(review_id) % 5`: four folds for
   tuning `rules.yaml`, one held out for the gate. The gate writes
   `classifier_quality (theme, precision, recall, n, rules_version,
   prompt_version)` — a mart the study displays next to the chart it feeds.
5. **Formulas are data.** `models/cost_model.py` holds an ordered `FORMULAS`
   list of `(name, expression_text, callable)`. The HTML export and the README
   render `expression_text`; a test evaluates each callable at the defaults
   against `tests/pins.py`. 1:1 by construction, not by discipline.
6. **The export is deterministic.** `study/export.py` renders one
   self-contained HTML file (inline SVG, no CDN, no render timestamp) from the
   marts and `FORMULAS`; `make study` in check mode diffs the committed bytes.
7. **Tags are enforced at render time.** Every panel in `SPEC.md` names its tag
   and BACKING row; the export refuses a panel with no tag or a Pending panel
   with a value. The gray "unclassified" band is a first-class series.
8. **Synthetic fixture, real anchors.** `fixtures/synthetic/` (hand-written
   reviews, obviously fake) is CI's data; `fixtures/anchors/platform_snapshots_
   seed.csv` holds the §6 public aggregates with `source_url`, `captured_at`
   and `seeded_from = "PROJECT_BRIEF §6"`. Neither is the corpus.
9. **No pandas.** DuckDB and stdlib `csv`/`json` are the glue. One line in the
   README says why.
10. **Regex in Python, not SQL.** `rules.yaml` patterns are applied by
    `classify/rules.py`; SQL never carries a regex, so it never carries a
    dialect.

---

## 5. Phase plan — the brief's §9 with three splits

The brief's numbering is kept. Three phases are split so each stays under six
done-when items and ends in a command; the rest are restated with their DONE
command and the agents their surface triggers.

**Why split Phase 0.** The brief's Phase 0 is "no code", but its own rule 2
("every phase ends with its done-when encoded as a test or make target") needs
the Makefile and the checks to exist before the contracts they check. The
reference learned this the same way and moved tooling to Phase 0. So: 0a builds
the gate, 0b writes the contracts the gate then verifies.

| Phase | Goal | DONE command (proposed) | Agents by surface |
|---|---|---|---|
| **0a — Machinery** | uv + Python 3.12, ruff, pytest, `Makefile` (`setup test lint check-docs check-backing review-gate help`), `scripts/`, CI, hook, the five agents, three commands, `specs/TEMPLATE.md`, `DECISIONS.md` + `BACKLOG.md` opened, `CLAUDE.md` v0 (§2 distilled), `BACKING.md` header + empty table, `.gitignore` merged. Tests pin the guards on throwaway trees. | `make review-gate SPEC=specs/phase-0a-machinery.md` | code-reviewer, functionality-tester, security-reviewer (CI, hook), study-editor (CLAUDE.md prose), coherence-auditor (phase exit) |
| **0b — Contracts** | `SPEC.md` (five beats, exact chart list, each with tag + BACKING row id), `BACKING.md` full table, `CLAUDE.md` final, glossary (≤ 10). | `make review-gate SPEC=specs/phase-0b-contracts.md` (coherence-auditor at exit) | coherence-auditor, study-editor |
| **1 — Schema and empty warehouse** | DDL raw/staging/marts with provenance columns (built: raw and staging only — each mart lands with its upstream; brief §9 reworded, DECISIONS → Phase 1); `pipeline/warehouse.py`; `make rebuild TARGET=duckdb` runs with zero rows AND with `FIXTURE=synthetic`; `fixtures/` frozen with MANIFEST; `tests/pins.py`; SQL portability test. | `make rebuild FIXTURE=synthetic && make idempotency-check` (as run then; `ROWS=synthetic` since Phase 3a) | code-reviewer, functionality-tester |
| **2 — One scraper end to end** | App Store review feed (public JSON, ToS-friendly — recommended over Opinion Assurances) → raw → staging → `reviews_per_month` mart. Strict parse of the feed shape. Politeness settings in one place. (Built: the host's `robots.txt` disallows the feed path for every crawler, so the source is declared and not fetched — DECISIONS → Phase 2 and Gotchas; the metric is a pinned query in `pipeline/metrics.py`, not a mart, until B5.2 lands; real rows move to 3a.) | `make rebuild FIXTURE=app-store && make idempotency-check FIXTURE=app-store` (as run then; `ROWS=samples` since Phase 3a; was `make rebuild` on real rows — moved to 3a by fix amendment A1) | + security-reviewer (network) |
| **3a — Snapshots + remaining polite sources** | `platform_snapshots` seeded from the re-frozen anchors (Documented) plus our own captures and hand-read rows (Measured); four marts (B1.2, B1.3, B1.4, B2.3) flip to Documented; every source a declaration with its parser and terms position; `ROWS` replaces `FIXTURE`. (Built: the Google Play listing is the one automated snapshot; the App Store listing's terms forbid robots, so its figures are hand-read; Opinion Assurances reviews and aggregate under the site's written authorization — DECISIONS → Phase 3a.) | `make rebuild && make idempotency-check ROWS=captured` | + security-reviewer |
| **3b — Trustpilot** | Its own session (brief). Honour blocks: if fetching fails, manual snapshot capture path; no evasion. | same | + security-reviewer |
| **4 — Weekly cron** | `weekly.yml`: scrape + snapshot commit under `data/snapshots/` only; no key. | two scheduled runs visible (BACKLOG row until then) | security-reviewer |
| **5a — Label sample + wall** | `make label-sample N=400` writes a labeling sheet (id, source_url, text) to gitignored `data/`; `classify/eval/labels.csv` schema = id + labels, no text; labels-isolation test; deterministic split. Human labels offline (hours, not a session). | `make test` (isolation + split pins) | code-reviewer, functionality-tester |
| **5b — Rules layer** | `rules.yaml` + `classify/rules.py`; per-theme precision on the tuning folds; share decided by rules reported. No model. | `make classify-eval` prints per-theme precision vs pins | code-reviewer, functionality-tester |
| **6 — Model fallback + gate** | `classify/llm.py` (the one place), cache, held-out gate → `classifier_quality` mart, `unclassified` on no key. | `make rebuild` green with key AND with key unset | + security-reviewer (key path) |
| **7 — Findings marts + open data** | Theme share by month / segment, peer comparison, trend; Open DAMIR slice fetched and cached (large files — slice, never commit); fitted cost distributions with the fit shown. | `make check-backing` shows every Beat 1–2 row populated | code-reviewer, functionality-tester |
| **8 — Cost model + simulator** | §7 formulas as `FORMULAS`; sourced defaults cited in code and BACKING; SLA-timer sim; computed threshold. | `make model` (formulas vs pins) | code-reviewer, functionality-tester |
| **9 — The study** | Metabase (Docker) dashboards via an idempotent API script, drill-throughs; `make study` HTML export; README in the two-layer voice. | `make study` check mode byte-identical; stranger test recorded | study-editor, coherence-auditor |
| **10 — Airflow + Snowflake demo** | One-screen DAG of five `make` tasks; `TARGET=snowflake` run once; DuckDB path still green. | `make rebuild TARGET=duckdb` green after the Snowflake run | + security-reviewer (credentials) |

Checkpoints where stopping still leaves a coherent project: after 4 (a public
time series accruing), after 6 (a gated classifier), after 8 (a recomputable
model).

---

## 6. Risks and decisions that need your call

1. **Corpus vs. clone-and-run.** Brief §2.5 says publish aggregates, not the
   corpus; brief §4.4 says anyone clones and gets data-to-dashboard. Proposed
   resolution: `labels.csv` holds ids + labels (no text); the corpus is
   gitignored; a fresh clone runs `make rebuild` which scrapes first; CI and
   tests run on the synthetic fixture. Cost: a stranger needs ~minutes of
   scraping before real charts appear. Alternative: commit paraphrased excerpts
   only (loses the eval's ability to re-score).
2. **Trustpilot terms and blocking.** Their terms restrict automated access.
   Proposal: polite fetch with a low rate; on refusal, the manual snapshot path
   (the rating and count are on the public page); no evasion, per brief §10.
   Recorded per source in `DECISIONS.md`.
3. **Metabase open-source has no dashboards-as-code export.** Serialization is
   an enterprise feature. Proposal: `study/metabase_setup.py` creates
   questions and dashboards through the HTTP API, idempotently, from a small
   YAML; the static HTML export is the permanent artifact and Metabase is the
   drill-through demo. Stack risk for Phase 9, verified in its first hour.
4. **A bot committing to `main`.** The cron commit conflicts with "never
   commit to main directly". Proposal: a written exception — the workflow
   identity may commit only under `data/snapshots/`; a CI check refuses any
   other path from that author. Alternative: cron opens a PR each week (weekly
   manual merge friction). *(As built in Phase 4 the CI author-path check was
   not needed: `main` is unprotected on this private plan, so the subtree limit
   is staging discipline — `git add data/snapshots/`, pinned by
   `tests/test_weekly.py` — plus `persist-credentials: false` for token hygiene.
   See DECISIONS → Gotchas.)*
5. **Which model API.** The brief does not name one. Assumption: the Anthropic
   API through the `anthropic` package, key from `.env`, prompt and model id
   versioned in `classified_reviews`. The `claude-api` skill is the reference
   when Phase 6 is written.
6. **Naming.** The directory is `claimwatch`; the brief says "The Friction
   Ledger" / `friction-ledger/`. Proposal: project and package name
   `friction_ledger`, README title "The Friction Ledger", directory left alone.
   Pick one before Phase 0a so `pyproject.toml` and the DAG id agree.
7. **Phase 0 split** (§5). Your brief says no code in Phase 0; this plan says
   the gate comes first. One structural change to approve or decline.
8. **Hand labeling is human hours.** 300–500 reviews at ~30 s each is 3–4
   hours of your time between 5a and 5b. Plan the calendar, not a session.
9. **Open DAMIR files are large** (monthly CSVs, hundreds of MB). Phase 7
   fetches one or two months, filters to the needed columns, caches under
   `data/`, and records the exact file names and hashes in BACKING. Nothing
   large is committed.
10. **Naming-the-target check.** A deterministic grep for an
    insurer's name would put that name in the repo. If wanted: a hashed
    denylist (compare `sha256` of lowercased tokens) over `*.py`, `*.sql`,
    `*.md` and commit messages, excluding seed CSVs and URL columns. Otherwise
    leave it to `study-editor`. Your call; default is the agent only.

---

## 7. Proposed `CLAUDE.md` outline (~400 lines, written in 0a, final in 0b)

1. **What this is** — the one-sentence description (dinner-table version) and
   the pointer: brief = what, `SPEC.md` = study structure, `BACKING.md` =
   evidence contract, this file = how we work.
2. **Architecture** — the brief §4 diagram, unchanged.
3. **Repo map** — one line per directory, marked *(Phase N)* until built.
4. **Commands** — one line per `make` target; details live in `make help`.
5. **Deterministic first** — brief §2.1 as rules: one model call site; gate
   before use; no-key run is green; no clock on the data path; formulas are
   data; idempotent raw.
6. **The five contracts** — Provenance (columns + tags), Evidence
   (`BACKING.md` is scope), Classification (seven labels, closed set, cached
   decisions), Portability (ANSI SQL, one seam, regex in Python), Neutrality
   (no target company in prose/code; data rows are data).
7. **Writing rules** — brief §2.3 condensed; the banned-word list; the
   glossary cap; two-layer everywhere.
8. **Conventions** — Python 3.12, type hints, no pandas, SQL file header,
   dependency allowlist by phase, secrets.
9. **Teaching rule** — verbatim from the reference, stack list swapped.
10. **Workflow rules** — spec is the contract; DONE command is the only
    definition of done; invariants before mechanisms; ≤ 6 items; fix
    amendments; STOP-on-findings; one correctness fix per commit; review cap
    is the human's call.
11. **Before reporting DONE** — the reference's list, items 5 and 8 replaced
    by "every new number: its tag and BACKING row" and "every new foreign input:
    the shape it parses to and what an unrecognised input does".
12. **Git workflow** — phase branch, PR, developer merges; the one written
    exception for the snapshot bot.
13. **Which review agents run** — the surface table with this repo's paths.
14. **Project tooling** — index of hooks, agents, commands, skills.
15. **Current status** — pointer paragraph plus the open BACKLOG count.

---

## 8. What happens next

If this plan is approved as written: branch `phase-0a-machinery`, write
`specs/phase-0a-machinery.md` from the template first, STOP for its approval,
then build. If parts are struck, this file is amended and re-read before the
spec is written. Nothing in `docs/` beyond this file is planned.

---

## 9. Amendment 2026-09-05 — the review stack (after Phase 7b)

The §2 table is the approved history and is not rewritten. Three pieces the
reference did not have, all landing on `tooling/review-stack` once the two
platform prompting guides (Fable 5.1, Opus 4.8) were read against this repo:

| Piece | Verdict | For this project |
|---|---|---|
| Model-specific instructions | **New** | CLAUDE.md → "Working with the model": the six named STOPs, effort policy, batch reads, edit-not-regenerate, verify-not-recall, scope and test discipline, the `/compact` keep-list; per-model notes. The agents pin `model:` and `effort:` (the `opus` alias drifts with the build). |
| `senior-architect` agent + `/challenge` skill + `challenge-gate` hook | **New** | A devil's-advocate round on a plan before it is built: steel-man, findings each with an alternative and its cost, advisory verdict, stamped on the spec. The hook reminds; it never denies. |
| `code-craft`, `secure-by-construction`, `architecture-fit` skills | **New** | The three standards, path-scoped and `user-invocable: false`, preloaded into the agent that reviews the same surface ("one standard, two readers", DECISIONS → Process). The examples supplied (TypeScript/React/Supabase checklists) contributed vocabulary only; their web-security and scaling content names a surface this repo does not have (no endpoint, no login, no payments), so it was dropped rather than adapted. |
| `code-reviewer`, `security-reviewer` | **Adapt again** | Coverage-first (the Opus 4.8 recall note), a confidence column, a craft pass (Class `craft` in the round table), the secure-coding classes this repo can exhibit. |
| A lean-mode reference (the ladder, review tags, marker comments, intensity levels) | **Adapt** | The ladder becomes the first section of `code-craft` and the tags the vocabulary of the code-reviewer's craft findings; marker comments are BACKLOG rows here; levels, cards and "question the spec" are dropped (DECISIONS → Process, 2026-09-05). |
| Prose rules that a mechanism can hold | **New** | Ruff rules for the mechanical craft bars; `disable-model-invocation` for the loop steps; the `ask-gate` hook for the push/PR/merge/`confirm` STOPs; the `Challenged:` stamp hashed to the spec's Invariants and Done-when; naming-the-target as a hashed `check-docs` check; CLAUDE.md cut to what is recorded nowhere else. |

CLAUDE.md → "How the tooling fires across a phase" is the one place the
seven-step loop (plan → challenge → disposition → approve → build → review →
fix) names what fires, on which trigger, reading what.

