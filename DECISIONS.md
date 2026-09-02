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
  - *App Store customer-reviews feed (Phase 2).* A public, keyless JSON feed
    Apple publishes per app and storefront for syndication — no login, no
    API key, no page scraping. Read at the feed's own cap (ten pages), with
    the manners above and `robots.txt` read first; a disallow, a block or a
    non-200 stops the run with one line and no retry. The pages are archived
    under gitignored `data/` and never published; the reviewer's name is never
    read into the warehouse. **Position as of 2026-09-02: the host's
    `robots.txt` disallows the feed path for every crawler (`User-agent: *`,
    `Disallow: /*/rss/*`).** The first live run fetched one capture before
    the matcher was corrected (see Gotchas); that capture and its database
    were deleted the same day. The source stays declared as a data point (id
    and listing address) but marked not to fetch — `fetchable=False`, with
    this reason recorded as its `terms` — so the fetcher refuses it before
    any request, even if the host's file reads differently on a later day
    (amendment A5); the fallback is the manual snapshot path above (Phase
    3a's `platform_snapshots`), never a different User-Agent or a
    "syndication feeds don't count" reading.
    ([Phase 2](#phase-2))
  - *Google Play listing (Phase 3a).* The app's store page, read for its
    machine-readable rating block (schema.org JSON-LD `AggregateRating`) and
    nothing else — one page, no reviews. **Position as of 2026-09-02:** the
    host's `robots.txt` catch-all group disallows `/_`, `/store/getreviews`
    and `/store/xhr` and does not disallow the details page; Google's terms
    forbid automated access only where it breaches robots.txt. Fetchable. Its
    reviews load through the disallowed `/_` call and are never fetched.
    ([Phase 3a](#phase-3a))
  - *App Store listing (Phase 3a).* Allowed by `robots.txt`, **forbidden by
    Apple's website terms of use** ("Your Use of the Site": no robot, spider,
    page-scrape or automated means to access or copy the site; no robots.txt
    carve-out; read 2026-09-02). Declared not fetchable; its rating and count
    are read by hand and entered in `data/snapshots/manual_snapshots.csv`,
    tagged Measured. The by-id address also answers a redirect to a slug
    address (Gotchas). ([Phase 3a](#phase-3a))
  - *Opinion Assurances profile pages (Phase 3a).* `robots.txt` allows the
    profile and its path-based pages (`…-page<n>.html`) and disallows every
    address with a query string; the site's conditions générales (V.3) forbid
    automated extraction **without prior written authorization**, and V.1
    reproduction without written agreement. **Position as of 2026-09-02: the
    developer holds the site's written authorization** (requested and granted
    2026-09-02), recorded as the source's `terms`; the study publishes
    aggregates and paraphrases only (brief §2.5). Fetchable: the studied
    insurer's profile, up to its own page count, ≥ 2 s apart; the reviewer
    pseudonym is never read. ([Phase 3a](#phase-3a))
- **An address that spells the brand is a sourced data point and lives in
  `ingest/sources.py` only (Phase 3a, decision D1).** A store package id or a
  profile path names the insurer where a numeric store id does not. It may
  appear in the source declaration — the `pages` and `listing` fields — and
  nowhere else: no prose, comment, commit message, test name, fixture or
  tracked data file repeats it (the hand-entry file names the source by its
  declared name). The future hashed naming check excludes those two fields.
  ([Phase 3a](#phase-3a))
- **A scraped page is parsed strictly to a declared shape; the page is the
  unit of refusal.** A feed item missing or mis-typing a required field, a
  rating outside 1–5 or a non-ISO timestamp refuses the whole page, naming
  page, item and field; nothing partial is loaded and nothing is defaulted.
  Widening the shape is a tested change in `ingest/app_store.py`, never a
  `.get(…, default)`. ([PLAN §2](docs/PLAN.md) Boundary row; [Phase 2](#phase-2))

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

Each entry: the surprise, the official-docs check, what we did.

- **Phase 2 — the live feed, checked by the first run (2026-09-02).** An agent
  runs no fetch, so the build session could not check the feed; the developer's
  first `make scrape CONFIRM=yes` was the check. Result: the field names match
  the declared shape (8 pages, 316 items, every page parsed, no widening
  needed); the feed ended at page 8 with an empty page, which the fetcher
  treats as the end.
- **Phase 2 — Python 3.12's `urllib.robotparser` matches prefixes only.** The
  same run read the host's `robots.txt`, which carries `Disallow: /*/rss/*`
  under `User-agent: *`, and passed it: the stdlib parser on the pinned
  interpreter ignores `*` and `$` (RFC 9309 wildcard support arrived in
  3.14), so a rule written with a wildcard is invisible to it, and the spec's
  own disallow test used a plain prefix, so the suite could not catch it.
  Official-docs check: the 3.12 `urllib.robotparser` page describes no
  pattern syntax. What we did: fix amendment A1 — our own matcher in
  `ingest/robots.py`, checked for every page, pinned by the real rule against
  the real path; the disallowed capture and its database were deleted; the
  DONE command moved to the frozen-sample form; the terms position above
  records the disallow.

- **Phase 3a — the candidate checks ran from the build session, not by hand
  (2026-09-02).** The spec said the developer would check each candidate's
  robots file, terms and page shape in a browser; the developer asked the
  session to do it. Done with `curl` and the stdlib client, the project's
  User-Agent, one request per page, ≥ 2 s per host, saved outside the repo.
  Midway, the session's permission classifier blocked further downloads from
  `apps.apple.com` and `opinion-assurances.fr` and every local script over the
  saved profile page (it would print review text); two pages were read
  through a text summary instead, and the profile page's structure was dumped
  by the developer with a redacting script (`inspect_oa_structure.py`, text
  nodes replaced by their lengths). Recorded because the spec's stack-risk
  section assumed a hand check.
- **Phase 3a — the App Store listing's by-id address redirects.**
  `https://apps.apple.com/fr/app/id<n>` answers 301 to a slug address that
  spells the app's name; the fetcher follows no redirect and refuses a non-200,
  so even under permission the declared address would have to be the slug
  (D1). Moot: Apple's terms forbid the fetch and the figures are hand-read.
- **Phase 3a — Opinion Assurances carries no JSON-LD; it carries microdata.**
  The listing parser's assumption (a `<script type="application/ld+json">`
  block) does not hold there: the profile page marks its data inline with
  schema.org `itemscope`/`itemprop` attributes — 40 `review` scopes a page,
  each with a `reviewRating` (`ratingValue` as a `meta content`) and an
  `author` scope (never read); one `AggregateRating` (`ratingValue`,
  `ratingCount` as `meta content`); the star distribution and the response
  figures are layout text (progress bars, labels), not data. Official-docs
  check: schema.org documents both encodings; the WHATWG microdata spec
  defines the attributes. What we did: a second parser walking microdata with
  the stdlib HTML parser (`ingest/opinion_assurances.py`), the field
  addresses declared in its header from the structure dump.

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
  Pending; `check-backing` sees 19 rows, 0 marts, 0 orphans. **This narrowed the
  brief's Phase 1 "All DDL (raw/staging/marts)" to the layers whose upstream
  exists.** On the developer's call (2026-09-02) PROJECT_BRIEF.md §9 Phase 1 was
  reworded to match ("raw and staging DDL in this phase; each mart lands with its
  upstream"), rather than leaving the brief and the phase disagreeing. Rejected: empty
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

### Phase 2

Branch `phase-2-scraper`, spec `specs/phase-2-scraper.md`. Depends on Phase 1
(PR #3) merged. Built the first scraper end to end on the frozen sample: the
App Store customer-reviews feed → byte-exact captures → the strict parser →
Phase 1's raw shape and guard → staging → reviews per month. One source, no
mart, no model.

- **The one source is the App Store feed, declared in `ingest/sources.py`**
  (name, app id, country — a data point, never a name in prose; the developer
  fills the app id). `source` = `app-store`, `external_id` = the item's id,
  `source_url` = the feed page URL, `captured_at` stamped once per run at
  fetch (UTC, the synthetic fixture's format), `review_date` = the date part
  of the item's own timestamp, no timezone arithmetic. Rejected: Opinion
  Assurances (HTML, stricter terms — Phase 3a); Trustpilot (3b); a per-app
  column in raw (the shape is Phase 1's; the app is recoverable from
  `source_url`; segment attribution is Phase 3a's table).
- **The strict parser and the scrape manners** — promoted to "Decisions still
  in force" above (Data).
- **Captures are archived per run, never overwritten:**
  `data/cache/app-store/<source>/<captured_at>/page-<n>.json` beside
  `page-<n>.meta.json` (`source_url`, `captured_at`, `status`) and the
  `robots.txt` obeyed. A second capture of unchanged pages adds no raw row
  (the content hash), which is what proves "re-scrape → nothing new" on real
  rows. Rejected: one overwritten cache per source (loses the history the
  proof needs).
- **`rebuild` reads captures by default; `FIXTURE` names the rebuild input:
  `{cache, empty, synthetic, app-store}`.** `cache` is the real run (a clone
  runs `make rebuild` and gets data once it has scraped), `app-store` runs the
  frozen sample through the real parser (CI does, offline). `run_id` is the
  capture id in cache mode, the fixture name otherwise — no clock. Rejected: a
  second variable; keeping `empty` as the default.
- **Reviews per month is a query, not a mart** (`pipeline/metrics.py`, printed
  by `rebuild`, pinned by a test). No SPEC.md panel shows it, so a
  `sql/marts/` file would be an orphan under BACKING.md's rule; it surfaces in
  Beat 5 through B5.2 `pipeline_row_counts` (BACKLOG row). **This narrows the
  brief's Phase 2 "one trivial mart (reviews per month)" to the brief's own
  Done-when wording, "one queryable metric".** On the developer's call at the
  exit audit (2026-09-02) PROJECT_BRIEF.md §9 Phase 2 was reworded to match,
  as Phase 1's was, together with its Done-when (the exit-audit entry
  below). Rejected: a new BACKING
  row (a new study claim needs a SPEC.md panel); flipping B5.2 early with a
  partial mart.
- **Review round 1 (2026-09-02) — four fix amendments, approved and built:**
  A1 robots matched by `ingest/robots.py` (RFC 9309) for every page, with
  Crawl-delay raising the per-host wait — the stdlib parser is gone; A2 one
  database file per rebuild input (`warehouse.database_for`), so a fixture
  never lands in the corpus and `reset` drops the closed set; A3 a page the
  strict parser refuses is archived as `page-<n>.refused.json` (kept, never
  loaded) and a malformed stored page is a one-line refusal from `rebuild`;
  A4 capture meta parsed strictly (`captured_at` a real instant, `source_url`
  https on an allowed host, `status` 200). Rejected: patching the stdlib
  parser's output (a denylist of paths — the kind change is the fix);
  truncating raw on rebuild (raw is append-only; separate files keep both
  properties); dropping refused pages (the evidence is the point).
- **Review round 2 (2026-09-02) — amendment A5, approved and built:** we
  treat a reply as the site's rules file only when it looks like one — plain
  text, or carrying a rule line; a decorated error page that answers "OK" is
  a refusal, never permission (superseded in part by A6 below);
  `AppStoreSource` carries `fetchable` and `terms`, so a recorded terms
  position is declared in code and refused before any request rather than
  inferred from a live fetch; we pick the block of rules written for our
  crawler by looking for its name inside the whole User-Agent line, so a
  version suffix no longer drops us into the catch-all block (superseded by
  A6 below). Rejected: trusting any 200 (the round 1 failure class again);
  keeping the position only in this file (a robots hiccup would silently
  re-enable the fetch); exact token equality (a group written for us with a
  version suffix fell through to `*`, permissively).
- **Review round 3 (2026-09-02) — amendment A6, approved and built; the
  review cap.** Rounds 2 and 3 had each found the previous round's robots
  fix permissive at an edge, so the cap applied: stop patching, state the
  invariant, rebuild the check once. The invariant: a feed page is asked for
  only if the reply reads as the site's rules file on its own terms and the
  path is allowed by both the rules written for us and the rules written for
  everyone. In practice: the body alone decides whether there is a file to
  obey (every line rule-shaped, a `User-agent:` line unless the file is only
  sitemaps, no rule before the first group; the content-type is archived
  beside it, never trusted); our block is the one naming our product token,
  never the rest of the User-Agent line, and the everyone block always
  applies beside it, so a wide match can only tighten; the longer of the two
  waits wins; which rules bind us is never a caller's value. Round 4, the
  one scoped re-review the cap allows, found four parser edges (a `Sitemap:`
  between two `User-agent:` lines fusing groups, a colon-bearing error body
  read as rules-free, a leading byte-order mark, a second wait in one
  group); each landed as one fix with its pin and none changed the
  invariant. Rejected: a third patch to the matcher (the cap); trusting the
  content-type (the round 3 hole); requiring a closed set of directive keys
  (`Host:` and `Clean-param:` are real and harmless; the shape is the
  guard, the `User-agent:` requirement the authority).
- **The sample is a new frozen fixture, `fixtures/app-store/`,** hand-written
  in the feed's exact shape (placeholder author labels, bodies marked
  fictional, app id 0): a real captured page would publish raw corpus and
  reviewer names. Malformed variants are built in tests by mutation, never
  committed. `Freeze: fixtures/app-store/` in the spec; MANIFEST in the diff.
  Rejected: a sample under `ingest/` or `tests/` (outside the MANIFEST
  discipline); a scrubbed real page.
- **`make scrape` is CONFIRM-gated like `reset` and developer-run.** Prompt on
  a tty, otherwise `CONFIRM=yes` from the command line only; SOURCE is a closed
  set of declared names; the fetcher is imported only inside the command, so a
  rebuild never loads `httpx`; the test suite blocks every socket (conftest).
- **`httpx` added (pre-approved); `pyyaml` deferred** to `rules.yaml` (5b) —
  nothing in Phase 2 needs YAML.
- **Exit audit (2026-09-02) — amendment A7 and three record corrections,
  approved and built.** A7: Done-when items 3 and 4 still said "real rows"
  after A1 moved the DONE command to the frozen sample; they now say what the
  phase proves (rows from a capture, the sample being one) and the real-rows
  proof moves to Phase 3a. **This narrows the brief's Phase 2 Done-when,
  "`make rebuild` produces real rows"; on the developer's call PROJECT_BRIEF.md
  §9 Phase 2 was reworded to match** — the frozen-sample form, with real rows
  landing in Phase 3 from the first source whose robots file allows its feed —
  so Phase 3's "all sources land with provenance" no longer assumes Phase 2
  landed one. The corrections: `pipeline/build.py` now runs every SQL file
  through `warehouse.run_sql_file`, the seam this file, PLAN §4.1 and Phase
  1's Delivered name (it had no caller since Phase 1); `MAX_CRAWL_DELAY_S =
  60.0` (a host asking for a longer wait is a one-line refusal, not a day-long
  sleep) is written into the spec's politeness decision — it had a pin and no
  record; `docs/PLAN.md` §5 rows 1 and 2 are corrected in place (raw and
  staging DDL only; the feed's host disallows the path, the metric is a query,
  the DONE command is the sample form). Two BACKLOG rows opened for Phase 3a:
  the capture path is hardwired to one platform, and the frozen `robots.txt`
  is permissive and read by nothing. CLAUDE.md stands at 443 lines
  against the ~400 cap after the status paragraph was cut back to the plain
  layer — reported, as the cap asks. Rejected: leaving the brief and the phase
  disagreeing (the Phase 1 precedent went the other way); dropping
  `run_sql_file` from the four records instead of calling it (the seam is the
  design; the bypass was the drift).

**Gotchas:** the live feed is unverified at build — see Gotchas above.

### Phase 3a

Branch `phase-3a-snapshots`, spec `specs/phase-3a-snapshots.md` (approved
2026-09-02 with amendment A1). Depends on Phase 2 (PR #4) merged. Built the
platform-snapshot table and its four marts, turned every source into a
declaration, added the listing parser and the Opinion Assurances parser,
renamed the rebuild input, closed five BACKLOG rows.

- **The candidate checks, and what they decided (2026-09-02).** Three sites
  were checked before approval (Gotchas; positions under "Scrape politely").
  No candidate allowed reviews on its own terms: Opinion Assurances forbids
  automated extraction without written authorization, Apple forbids robots
  on its listing, Google Play allows its listing and not its reviews. The
  spec was re-scoped to snapshots (its own disposition), then amended at
  approval when the developer obtained Opinion Assurances' written
  authorization (A1): its profile pages are the phase's review source.
  Rejected: fetching a page whose terms say no because its robots file says
  yes (both bind us); Google Play reviews through the internal call (not a
  public feed, and disallowed).
- **`platform_snapshots`: anchors Documented, our captures Measured (D2,
  D3).** `raw_platform_snapshots` keyed on `(source, profile, captured_at)` +
  a hash of five measures (rating, count, one-star share, response rate,
  response delay); `origin` ∈ {anchor, manual, fetch} decides the tag in
  staging by an exact comparison. `fixtures/anchors/` was re-frozen
  (`Freeze:` in the spec, MANIFEST regenerated): the Phase 1 file had no
  profile (two peers collided on every key), carried a channel where a
  segment belongs on the two app rows, and omitted the brief's Opinion
  Assurances anchor (534 reviews, 23.1 % one-star, 82 % answered, 1.5 days,
  no rating) — nine anchors now, not eight; PROJECT_BRIEF.md §6 says
  Documented on the developer's call. Rejected: Measured for anchors (a
  person's reading at scoping, without a capture time of ours); repairing
  the seed's meaning in SQL; keeping the page's full-precision rating as text
  (`decimal(4,3)`, rounded half-even, keeps every displayed value exactly).
- **Four marts, four flips to Documented.** `rating_trend` (B1.2),
  `channel_gap` (B1.3), `platform_stats` (B1.4), `peer_ratings` (B2.3) are
  window selects over `stg_platform_snapshots`, each row carrying its point's
  tag; BACKING flips the four rows Pending → Documented with the anchors file
  and the platform roots as sources; the flip to Measured is Phase 4's, when
  scheduled captures make the series ours. SPEC.md's header and four panels
  say so. Rejected: one shared mart under four rows; flipping to Measured on
  a few 2026-09-02 points; leaving B1.4 Pending (the Opinion Assurances page
  and the anchors carry its numbers).
- **A source is a declaration (pinned decision 3).** `ingest/sources.py::Source`
  carries platform, host, parser (a closed set of module names), the page
  addresses (the closed set of `source_url` values), profile, segment,
  channel, the listing address, `fetchable` and `terms`, `declared_on`;
  `CACHE_ROOT` is the one binding of the cache root; `ingest/captures.py`
  reads any parser's captures back and checks the meta's host against the
  declaring source's host, not the fetch-time allowlist; `pipeline/build.py`
  iterates the declarations and dispatches to the declared parser; nothing
  compares a platform name (a test greps for it). Reviews get their segment
  from `raw_source_pages` — one row per declared page address, written in
  Python at every rebuild — joined on exact `source_url`; `pipeline/sql_lint.py`
  refuses `like` and `similar to` beside `regexp`. Rejected: a `segment`
  column on `raw_reviews` (Phase 1's shape); a pattern over the address in
  SQL; deriving the allowlist from the declarations (a circular import; the
  allowlist is a fetch-time knob).
- **The listing parser reads one machine-readable block and nothing else.**
  `ingest/listing.py`: the page's `<script type="application/ld+json">`
  objects, exactly one carrying `aggregateRating`, its `ratingValue` (0–5)
  and `ratingCount` or `reviewCount` as digit strings or numbers; a second
  block, none, or a value outside the shape refuses the page naming the
  field; `name`, `author`, `url` and review items are never read.
  `fixtures/listings/` is its hand-written, fake sample (`Freeze:` in the
  spec).
- **The hand-entry path is a tracked CSV, not a make target.**
  `data/snapshots/manual_snapshots.csv`: eight columns (a declared source name
  whose `fetchable` is False, a day, five numbers, the word `page`), parsed
  strictly by `make rebuild`; platform, address and attribution come from the
  declaration, so the file carries no address and no name. Rejected: a `make
  snapshot` target with eight variables (eight threat-model rows for a CSV
  edit); the address in the file (D1); a clock stamp for a manual row (the
  reader states the day).
- **`ROWS` names the rebuild input (D4); `samples` runs every frozen sample.**
  `captured | none | synthetic | samples` replace `cache | empty | synthetic |
  app-store` (Phase 2's `FIXTURE` decision is superseded by this one); a
  sample is read under a declaration whose profile, segment and channel are
  the literal `sample`. `fixtures/app-store/robots.txt` re-frozen to the real
  rule and read by a test. Rejected: keeping `FIXTURE` (the name called the
  corpus a fixture); one value per sample.
- **The robots matcher matches directly.** `_matches` is a two-pointer glob
  with one fallback to the last `*`; time is bounded by pattern × path
  length; the matching table is unchanged. Rejected: a cap on `*` per pattern
  (a denylist on the input); `fnmatch` (the same regex underneath).
- **The Opinion Assurances parser reads schema.org microdata** —
  *(filled in when the parser lands: the field addresses for the rating,
  the date, the body and the review identifier, from the structure dump.)*
