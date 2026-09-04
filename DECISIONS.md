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
  holds; `run_id` is stamped in Python (never in SQL) and is in no natural
  key; every mart carries it as provenance, so a displayed point can be
  traced to the run that wrote it. ([PLAN §4 decision 2](docs/PLAN.md);
  [Phase 1](#phase-1))

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
    (Phase 2's amendment A5); the fallback is the manual snapshot path above (Phase
    3a's `platform_snapshots`), never a different User-Agent or a
    "syndication feeds don't count" reading.
    ([Phase 2](#phase-2))
  - *Google Play listing (Phase 3a).* The app's store page, read for its
    machine-readable rating block (schema.org JSON-LD `AggregateRating`) and
    nothing else — one page, no reviews. **Position as of 2026-09-02:** the
    host's `robots.txt` (https://play.google.com/robots.txt) catch-all group
    disallows `/_`, `/store/getreviews` and `/store/xhr` and does not disallow
    the details page; the Google Play Terms of Service
    (https://play.google.com/about/play-terms/) forbid automated access only
    where it breaches robots.txt. Fetchable. Its reviews load through the
    disallowed `/_` call and are never fetched. ([Phase 3a](#phase-3a))
  - *App Store listing (Phase 3a).* Allowed by `robots.txt`, **forbidden by
    Apple's website terms of use**
    (https://www.apple.com/legal/internet-services/terms/site.html, "Your Use
    of the Site": no robot, spider, page-scrape or automated means to access
    or copy the site; no robots.txt carve-out; read 2026-09-02). Declared not
    fetchable; its rating and count are read by hand and entered in
    `data/snapshots/manual_snapshots.csv`, tagged Measured. The by-id address
    also answers a redirect to a slug address (Gotchas). ([Phase
    3a](#phase-3a))
  - *Opinion Assurances profile pages (Phase 3a).* `robots.txt`
    (https://www.opinion-assurances.fr/robots.txt) allows the profile and its
    path-based pages (`…-page<n>.html`) and disallows every address with a
    query string; the site's conditions générales, read 2026-09-02 on the
    site's own terms page (its address is not recorded here), forbid in V.3
    automated extraction **without prior written authorization**, and in V.1
    reproduction without written agreement. **Position as of 2026-09-02: the
    developer holds the site's written authorization** (requested and granted
    2026-09-02), recorded as the source's `terms`; the study publishes
    aggregates and paraphrases only (brief §2.5). Fetchable: the studied
    insurer's profile, up to its own page count, ≥ 2 s apart; the reviewer
    pseudonym is never read. ([Phase 3a](#phase-3a))
  - *Trustpilot review profile (Phase 3b).* The studied insurer's Trustpilot
    profile, read for its TrustScore and review count. **Position as of
    2026-09-03: not fetchable.** `robots.txt` (read on both
    https://www.trustpilot.com/robots.txt and https://fr.trustpilot.com/robots.txt,
    2026-09-03) names many crawlers explicitly and ends with a catch-all group
    `User-agent: *` / `Disallow: /`; our User-Agent is in no named group, so
    under RFC 9309 the catch-all governs and every path is disallowed. Declared
    `fetchable=False`, refused before any request; its rating and count are read
    by hand into `data/snapshots/manual_snapshots.csv`, tagged Measured (3.9 on
    1,072 reviews, 2026-09-03), on the `fr-digital-first` profile so the point
    joins the Trustpilot anchors' series. The review-profile parser and a frozen
    sample are not built — no page may be fetched, so none may be frozen — and
    are re-deferred to a future written authorization (BACKLOG). ([Phase
    3b](#phase-3b)) *Superseded by [Phase 3c](#phase-3c) (partly): the
    authorization arrived, so the reviews are now imported OFFLINE (a parser on
    a second source); the crawler ban stands, so the source stays
    `fetchable=False`.*
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
  rating outside the scale the shape declares, or a non-ISO timestamp refuses
  the whole page, naming page, item and field; nothing partial is loaded and
  nothing is defaulted. Widening a shape is a tested change in the parser that
  declares it — `ingest/app_store.py`, and since Phase 3a `ingest/listing.py`
  and `ingest/opinion_assurances.py` (the review half-steps and the
  aggregate's 0..5, A6/A8) — never a `.get(…, default)`. ([PLAN
  §2](docs/PLAN.md) Boundary row; [Phase 2](#phase-2))

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
  first live `make scrape` was the check (gated then by `CONFIRM=yes`; since
  Phase 3a's A4 (d) by `make confirm scrape`). Result: the field names match
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
- **GNU Make reports a `MAKEFLAGS` definition as `command line`.** With
  `MAKEFLAGS='CONFIRM=yes'` in the environment, `$(origin CONFIRM)` is
  `command line` and the recipe sees the value exactly as if typed — 3.81 on
  macOS and 4.x alike, by design: a definition in `MAKEFLAGS` is a
  command-line definition. So `$(origin)` cannot gate a destructive target.
  Goals cannot travel that way (`MAKEFLAGS='confirm'` adds no goal; an
  environment `MAKECMDGOALS` changes the variable's text, not the goal list),
  which is what Phase 3a's A4 (d) builds on. Found by review round 3
  (security-reviewer), 2026-09-02.
- **`create table if not exists` keeps the old column, and the engine casts
  into it.** After A6 widened `raw_reviews.rating` to `decimal(2, 1)`, a
  rebuild on the file built before it left the `integer` column in place
  and DuckDB rounded every half-step on insert (109 of 534) — no error, no
  warning, counts unchanged twice. Official-docs check: DuckDB's `if not
  exists` is a no-op on an existing table; an insert casts implicitly
  between numeric types. What we did: A7 — the rebuild reads the existing
  table's columns and the file's back through `information_schema` and
  refuses on a difference. Found by the first `make confirm scrape`,
  2026-09-03.
- **A structure dump names the fields, not their nesting or their values'
  shape.** The Opinion Assurances dump of 2026-09-02 listed the classes and
  microdata properties a review carries; the hand-written sample then
  guessed that `h4.oa_text` sits inside `div.oa_description` (it follows
  it) and that `ratingValue` is a digit (the site rates in half stars:
  `1.5`, `4.5`). Both guesses were pinned by tests against the sample, so
  the tests were green and the first live page refused twice — the refusal
  is the design working, the guesses were the cost. What we did: A5 and A6
  (Phase 3a); and the rule for 3b's Trustpilot: freeze the sample from one
  permitted real page, names replaced, before the parser is written — a
  guessed nesting is a second shape the tests cannot see. Found by the first
  `make confirm scrape`, 2026-09-03.

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
- **`run_id` is stamped in Python, not SQL; for a fixture input (`FIXTURE`
  then, `ROWS` since Phase 3a) it is the input's name.** So `sql/` stays
  clock-free, a changing `run_id` never duplicates a row or moves a number,
  and the synthetic rebuild is byte-stable, not merely count-stable. Rejected:
  `run_id` from `now()` in SQL.
- **The fixture is read in Python (stdlib csv) and inserted with a portable
  guard** — DuckDB's `read_csv` is dialect-bound, so the load lives in the
  driver, not in a `sql/` file (no pandas). `insert … select … where not exists`
  is ANSI.
- **`sql/raw/` joins `sql/staging/` and `sql/marts/`** as a table-DDL directory
  (raw table creation is SQL, scanned by the portability guard), added to the
  Repo map and the SQL-file convention.
- **One validating CLI behind `make`; `reset` is the only destructive target,
  gated by the `confirm` goal of the same invocation.** `rebuild`/
  `idempotency-check` take `TARGET`/`ROWS` as a closed set validated in
  Python. The gate was `$(origin CONFIRM)` from Phase 1 to Phase 3a's review
  round 3, when a definition supplied through `MAKEFLAGS` in the environment
  was shown to report `command line` (GNU Make 3.81 and 4.x alike); a goal
  cannot arrive that way, so `make confirm reset` stamps the make process's id
  and `reset` runs only in that process (A4 (d), [Phase 3a](#phase-3a)). The
  stamp is created exclusively (A8 (d)); `confirm` arms `reset` or `scrape`
  alone and reads a goal list of make's own origin only (A9 (a)); what the
  gate does not hold against — an environment that chooses what make reads or
  runs (`MAKEFILES`, `PATH`), a same-user process writing `data/` while make
  runs — is written in the spec's Threat model; goals run in order under `-j`
  (`.NOTPARALLEL:`, exit pass 2026-09-03). Mirrors the SPEC/BASE shape for the
  variables.

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
  `{cache, empty, synthetic, app-store}`.** *Superseded by Phase 3a's `ROWS`
  entry: `{captured, none, synthetic, samples}`.* `cache` is the real run (a
  clone runs `make rebuild` and gets data once it has scraped), `app-store`
  runs the frozen sample through the real parser (CI does, offline). `run_id`
  is the capture id in cache mode, the fixture name otherwise — no clock.
  Rejected: a second variable; keeping `empty` as the default.
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
- **`make scrape` is gated like `reset` and developer-run.** Prompt on a tty,
  otherwise `make confirm scrape` only (A4 (d)); SOURCE is a closed
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
- **`platform_snapshots`: anchors Documented, our captures and hand-read
  rows Measured (D2, D3).** `raw_platform_snapshots` keyed on `(source,
  profile, origin, source_url, captured_at)` (A2; `(source, profile,
  captured_at)` before round 1) + a hash of five measures (rating, count,
  one-star share, response rate, response delay); `origin` ∈ {anchor, manual,
  fetch} decides the tag in staging by an exact comparison.
  `fixtures/anchors/` was re-frozen (`Freeze:` in the spec, MANIFEST
  regenerated): the Phase 1 file had no profile (two peers collided on every
  key), carried a channel where a segment belongs on the two app rows, and
  omitted the brief's Opinion Assurances anchor (534 reviews, 23.1 % one-star,
  82 % answered, 1.5 days, no rating) — nine anchors now, not eight;
  PROJECT_BRIEF.md §6 says Documented on the developer's call. Rejected:
  Measured for anchors (a person's reading at scoping, without a capture time
  of ours); repairing the seed's meaning in SQL; keeping the page's
  full-precision rating as text (`decimal(4,3)`, rounded half-even, keeps
  every displayed value exactly). The anchors' addresses are platform roots,
  not profile pages: a profile address spells the brand and may sit only in
  `ingest/sources.py` (D1), so a Documented point opens to its platform and to
  the brief's §6, not to a page — the trade D1 makes, stated in BACKING's note
  on the rating rows. A figure the brief dates to a month is placed on the
  15th of that month, and one it dates to a season on the 15th of that
  season's first month ("early 2025" is 2025-01-15); one it dates to a span
  of years is placed at mid-year of the span's first year ("2025–2026" is
  2025-06-15); one it
  does not date is placed on the day of the figure it was gathered beside (the
  Google Play figure beside the App Store's, 2024-09-15; the Opinion
  Assurances figures beside the June 2026 reading, 2026-06-15). A figure the
  brief gives as a range is stored at the range's midpoint, rounded to the
  column ("~2.7–3.8" is 3.250), and a figure it does not give at all is left
  empty (two peers' review counts; `review_count` is nullable like the other
  measures — A4 (e), re-frozen 2026-09-03). The day, and a midpoint, are
  placements, not readings.
- **Four marts, four flips to Documented.** `rating_trend` (B1.2),
  `channel_gap` (B1.3), `platform_stats` (B1.4), `peer_ratings` (B2.3) are
  window selects over `stg_platform_snapshots`, each row carrying its point's
  tag; BACKING flips the four rows Pending → Documented with the anchors file
  and the platform roots as sources; the flip to Measured waits until the
  points we measure make the series ours — NOT Phase 4 (Phase 4 gave the
  fetched points a tracked home but decided the rows stay Documented, since a
  handful of weekly points is not yet the series — see the Phase 4 entry).
  SPEC.md's header and four panels say so. Rejected: one shared mart under four rows; flipping to Measured on
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
  refuses `like` and `similar to` beside `regexp`. The lint is a denylist by
  design (Phase 1) and is widened only with a record here: review round 2
  added `ilike` and `rlike`, the pattern keywords both engines accept that the
  first set missed; round 3 added DuckDB's `glob` keyword and its tilde
  operators (`~~` is `like`, `~` a regex match, `!~~` and `~~*` their
  variants), caught by the one character all of them carry, which no portable
  statement uses. Rejected: a `segment`
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
- **A2 (after review round 1): the snapshot key names its declaration, a
  same-key pair refuses, the stat row is one row per stat.** The natural key
  of `raw_platform_snapshots` gains `origin` and `source_url` — the address a
  row was read from is its declaration: a platform root for an anchor, the
  listing address for a hand-read row, the page for a capture — so a hand-read
  figure equal to an anchor's is a row of its own and two hand-entered sources
  cannot collide (a check at declaration pins that none share a platform and
  listing). A row whose key already sits in raw under other figures is refused
  at load with one line naming the line and the fix (`make confirm reset`,
  then `make rebuild`): that arises only from a corrected hand entry or a
  re-frozen seed, and the corpus is rebuilt from tracked inputs. Staging
  therefore keeps every raw row and no `order by` carries `content_hash`;
  when two points share a day in a mart, `precedence` (a capture, then a hand
  entry, then an anchor — a closed `case`, exact and portable) and the
  address decide. `platform_stats` is one row per (segment, source, profile,
  stat) over a closed set of four stats, each the latest reading of that stat
  with its own provenance, so a capture that reads one figure never blanks
  another. Rejected: a load-sequence column so the later entry wins (a second
  order on the data path, a number no page produced); coalescing each stat
  column from its own latest row inside one row (three provenances in one
  row); DuckDB's `unpivot` for the stat rows (a dialect word; four selects
  stacked with `union all` say the same in ANSI).
- **The Opinion Assurances parser reads schema.org microdata, and its review
  id is a content hash (A1).** `ingest/opinion_assurances.py` walks the page
  once with the stdlib HTML parser: each `itemscope` of type `review` yields
  one row — `rating` from the `reviewRating` scope's `<meta itemprop=
  "ratingValue" content>` (a half-step 1–5, A6), `review_date` from the description's
  own sentence "Avis publié le dd/mm/yyyy suite à une expérience le
  dd/mm/yyyy" (the first date; the second is the experience date), `body`
  from `h4.oa_text`, `title` empty (the page has none); the `author` scope
  (a pseudonym and a member link) is skipped in full; the page's one
  `AggregateRating` (`ratingValue`, `ratingCount` as `meta content`) yields
  the snapshot row; a page with the aggregate and no review is the end of the
  list; a page with neither is refused. **The page marks no stable review
  identifier** (the only per-review link is the reviewer's member page — an
  author field), so `external_id` is sha256 over the publication date, the
  experience date, the rating and the body: deterministic and author-free,
  taken on the build session's recommendation at the STOP-and-decide the
  spec named (2026-09-02). Cost, in BACKLOG: an edited review is a new
  review, not a new version of one. The one-star share, response rate and
  response delay the page shows are layout text (progress bars, labels), not
  data, and are not read — those figures stay Documented from the anchor
  (BACKLOG). Rejected: the member id as the key (reads the author and
  identifies the reviewer); the position on the page (unstable); parsing the
  layout percentages (presentation, not a declared shape).
- **A3 (after review round 2, approved and built 2026-09-03): attribution
  joins the guards; the sample declaration is a property; a hand entry names
  a source with no parser.** (a) `raw_source_pages` refuses a declared page
  already in raw under another profile, segment or channel, naming the
  address and the fix (`make confirm reset`, then `make rebuild`), so one
  address has one row and the review join is one-to-one by construction; the
  snapshot fingerprint gains `segment`, `channel` and `seeded_from`, so a
  corrected attribution on an existing key is a same-key pair and refuses
  like a corrected figure. (b) `Source.sample`, set only by `sample_source`,
  is what the closed-set check on `segment` and `channel` keys on; a source
  named `sample` without it refuses at declaration; invariant 1 says the
  literal `sample` exists only in the samples database. (c) A hand entry
  names a source with no parser — the set `hand_entries_are_unique` covers —
  so a parsed source declared not fetchable can never take a hand-read row
  that collapses onto its listing's key. Rejected: widening the uniqueness
  check to every non-fetchable source (two declarations would share one key
  by design); `origin` and the attribution in `raw_source_pages` (a page's
  attribution is one fact, not a series); replace-on-change for either table
  (raw is append-only and a replaced row loses its provenance).
- **A4 (after review round 3, approved and built 2026-09-03): every measure's
  bound is its column's; the loader checks its closed sets; a capture's
  address is a declared page; the confirmation is a goal; a ranged anchor is
  a placement.** (a) `ingest/parsed.py::MEASURES` declares the four decimal
  measures once with their columns' precision, scale and range; a hand entry
  loads exactly as written or refuses past the column's digit shape (never
  rounded for the person), a page's figure is rounded half-even to the scale
  at the parse, so the fingerprint is the stored value, pinned by
  re-fingerprinting every loaded row; `load_snapshots` runs a batch in one
  transaction, so a refused batch loads nothing. (b) The loader refuses a
  row whose `origin`, `segment` or `channel` is outside its set — `sample`
  accepted only under the `samples` input, derived from the closed `INPUTS`
  — or whose provenance or profile is empty; a parser-less declaration needs
  a listing address. (c) `read_meta` accepts a page iff its address is one
  of the declaration's pages, exactly; each parser declares `SAMPLE_PAGES`,
  the sample declaration carries them, and `raw_source_pages` is written for
  the sample declarations under `samples`, so every sample review joins one
  page where CI runs it. (d) `make confirm reset` / `make confirm scrape`
  (Gotchas: `$(origin)` cannot tell `MAKEFLAGS` from the command line): the
  `confirm` recipe stamps its make process's id under `data/`, the gated
  recipe passes its own `$$PPID`, Python confirms only when they are one
  process and consumes the stamp either way; pinned against the installed
  make on this machine and in CI. (e) `fixtures/anchors/` re-frozen: the
  three peer rows carry a range's midpoint rounded to the column and an
  empty count where the brief gives none; `review_count` is nullable; the
  placement rule in SPEC's Beat 1, this file and BACKING gains the value
  side. Rejected: bounding by the digit run and letting the engine round
  (the fingerprint would not be the stored value); a per-call `sample` flag
  on the loader (a caller's value); deriving the sample pages from the meta
  files (a declaration read from data); reading make's own argv through `ps`
  (a process tree the recipe does not own); a stamp age check (a clock in
  the CLI; the process id and the consumed stamp hold against a variable, an
  environment, `MAKEFLAGS` and a stale invocation — the residual, a same-user
  process writing `data/` while make runs, is stated in A8 (d)); a zero count for
  a peer the brief does not count (a number no source gave); dropping the
  two peers (two Documented ratings the brief does state).
- **A5 (first live run, approved and built 2026-09-03): the review text is a
  child of the review scope, not of the description.** The first `make
  confirm scrape` fetched the profile's first page and the parser refused
  its first review's `oa_text` as missing: on the live page `h4.oa_text`
  *follows* `div.oa_description` as a sibling (so does `div.oa_commands`),
  while the parser's header, the hand-written sample and the guard (the body
  opened only while the description was open) nested it inside — the
  structure dump gave the fields, never their nesting (Gotchas). Now the
  guard's kind is "this element is the review's text": `oa_text` opens the
  body wherever it sits in the review scope outside the author markup, two
  bodies in one review refuse the page naming the count, and
  `fixtures/opinion-assurances/` is re-frozen in the live nesting. Rejected:
  accepting the body at either place with the nested one preferred (a
  preference is a second shape); the first `oa_text` after the description
  in document order (a position, not a scope); a denylist of layout wrappers
  to skip (a fix for the case).
- **A6 (first live run, approved and built 2026-09-03): a review's rating is
  a half-step, 1 to 5.** With A5 built the same page refused its sixth
  review: `ratingValue` `1.5`. The site rates in half stars (page 1: sixteen
  1s, one 1.5, five 4s, four 4.5s, fourteen 5s); the shape, the parser and
  `raw_reviews.rating integer` allowed a digit only. Now
  `ingest/parsed.py::REVIEW_RATINGS` declares the closed set {1, 1.5, …, 5}
  once beside the snapshot measures; `review_rating` parses a digit or a
  digit and `.5` strictly; the profile parser refuses anything else naming
  the value; `load_reviews` checks every row it is handed against the set
  and inserts nothing on a refusal; `raw_reviews.rating` is `decimal(2, 1)`
  and `stg_reviews` carries it; `content_hash` spells a decimal one way
  (trailing zeros dropped, as `snapshot_hash` does), so the synthetic
  corpus's hashes do not move; the App Store parser keeps its digit rule
  (its feed gives digits, members of the set). The sample is re-frozen with
  one half-step so `ROWS=samples` carries one through the real parser and
  column. The set admits exactly the scale the site declares: each review
  scope carries `worstRating` 1 and `bestRating` 5 (all 534 on the first
  capture; the aggregate declares 0..5), the parser reads both and refuses a
  page declaring another scale naming the bounds, so a value the site does
  not admit (a 0.5, say) is admitted here only when the site admits it — by
  widening the set by hand with that page as evidence, never by the parse.
  Nothing downstream reads a review's rating yet. Rejected: rounding a
  half-step to a digit (an altered figure — a rating the reviewer did not
  give); refusing the page (loses the phase's only review source over a
  value the site gives by design); a free `decimal` in 0–5 (wider than the
  site's shape; admits a malformed value).
- **A7 (first live run, approved and built 2026-09-03): a rebuild refuses a
  raw table that is not its declaration.** The first rebuild after A6 loaded
  into the DuckDB file made before it; `create table if not exists` kept the
  `integer` rating column and the engine rounded 109 half-steps on insert
  without a word — nothing refused, the idempotency check green. A4 (a)
  closes that class at the parse, which cannot see a table whose column is
  not the file's. Now `create_raw` compares every raw table that already
  exists with its file: the declaration is created as a temporary table
  under a scratch name on the same connection, both column lists are read
  back from `information_schema.columns` in the engine's own vocabulary, the
  scratch table dropped, and the first difference refuses the rebuild naming
  table, column and both types, pointing at `make confirm reset`. Rejected:
  dropping and recreating raw on every rebuild (append-only history);
  altering the column in place (engine-specific, and it rewrites history's
  values); a CLAUDE.md note alone (a silent failure; a note stops no build);
  comparing the file's text with a stored copy (a comment edit is not a
  schema change; a schema change can hide in equal bytes across engines).
- **A8 (after review round 4, approved and built 2026-09-03): a raw table is
  compared with its whole declaration; the review loader loads a batch or
  nothing; the aggregate's declared scale is read like a review's; the confirm
  gate says what it holds against; the database file and the label set are
  derived from the input.** (a) `check_raw_declaration` reads name, type and
  nullability by position, for the table and the scratch declaration alike,
  from the schema the engine names (`warehouse.default_schema`); a nullability
  drift refuses like a type — the case A4 (e)'s nullable `review_count`
  opened, a driver `ConstraintException` out of `make rebuild` on a corpus
  built before it; a table already sitting under the scratch name refuses
  naming itself, not the corpus; a raw file is exactly one `create table if
  not exists` statement, comments stripped, and only that statement runs for
  the scratch. (b) `load_reviews` runs its batch in one transaction, as
  `load_snapshots` has since A4 (a). (c) The Opinion Assurances parser reads
  the aggregate scope's `worstRating` and `bestRating` and refuses an
  aggregate declaring a scale other than the rating column's 0..5
  (`AGGREGATE_SCALE`), the same kind of guard A6 gives each review scope
  against its own 1..5 (`REVIEW_SCALE`); the frozen sample already carried 0
  and 5. (d) The confirm stamp is created exclusively, owner-only, so a
  planted file makes `confirm` refuse naming it; a `confirm` that is the last
  goal refuses and leaves no stamp; the Threat model states the residual — a
  same-user process writing `data/` while make runs — because the stamp is a
  file and make has no channel between two recipes but a file. (e) `rebuild`
  takes a root directory and the file is always `database_for(rows, root)`;
  `load_snapshots` takes its input as a required argument. Rejected: comparing
  in the order the catalog returns rows without reading `ordinal_position`
  (unspecified on other engines; since round 5 the ordinal is read and sorted
  on, never the row order); altering a column in place (rewrites history); a
  nonce between the recipes (the channel is the same file); the process start
  time via `ps` and an age check (both rejected in A4 (d)); a check that the
  file's name is the input's (a spelling, not a derivation); a marker table
  naming the input inside each file (a row no source produced, counted by the
  idempotency check). Found by review round 4 (2026-09-03).
- **A9 (after review round 5, approved and built 2026-09-03): the confirm gate
  arms a gated goal or nothing, from make's own goal list; the declared-page
  writer writes a batch or nothing; the `sample` label is the sample
  declaration's row's.** (a) `confirm` arms only when the goal after it is
  `reset` or `scrape` — a closed set, so `make confirm help` refuses and
  leaves no stamp — and only from a goal list whose origin is make's own: the
  recipe passes `$(origin MAKECMDGOALS)` and anything but `default` is
  refused, since a `MAKECMDGOALS` definition from the environment
  (`environment`), from `MAKEFLAGS` or from the command line (`command line`)
  overrides the list make built (probed against GNU Make 3.81); `reset` and
  `scrape` consume the stamp before their own refusals; a stamp create that
  fails for any reason but "already there" refuses with one line. The exit
  pass found two more edges: a parallel run (`make -j2 confirm reset` ran
  `reset` before the stamp existed in 7 of 12 tries) is closed by
  `.NOTPARALLEL:` with a `-j2` pin, and an environment that chooses what make
  reads or runs (`MAKEFILES` with a `$(shell …)` planting the stamp, `PATH`)
  is stated as a residual beside the same-user process (A8 (d)) — refusing
  when `MAKEFILES` is set would only move that boundary one variable. A link
  to nowhere planted at the stamp path is consumed by the next gated run
  rather than wedging the gate. (b) `write_source_pages` runs its batch in one
  transaction, as the two loaders do. (c) `attribution_labels` takes the input
  and the row's profile: the literal `sample` is admitted under `samples` on a
  row whose profile is the sample declaration's, and a real declaration may
  not carry that profile. Rejected: dropping the goal-list check and widening
  the residual (a leaked stamp becomes the ordinary case); a Makefile-side
  `$(filter …)` (it runs on the same overridable variable); a denylist of
  goals that may not follow `confirm`; keying the label on the row's `source`
  (a sample row's source is the real platform's name, as an anchor's is);
  dropping `rows_input` (the input still decides where a sample declaration
  exists). Found by review round 5 (2026-09-03); built in place of a sixth
  round, with one exit pass.

### Phase 3b

Branch `phase-3b-trustpilot`, spec `specs/phase-3b-trustpilot.md`, APPROVED
2026-09-03 with amendment A1. The remaining polite source: Trustpilot, the
platform behind the peer anchors and the studied insurer's Documented rating
series (`fixtures/anchors/platform_snapshots_seed.csv`).

- **A1 — Trustpilot is not fetchable; the hand-read path.** The developer's
  robots check (Phase 0a default #2) is decisive: `www.trustpilot.com` and
  `fr.trustpilot.com` both end their `robots.txt` with `User-agent: *` /
  `Disallow: /`, and our User-Agent (`friction-ledger/…`) matches none of the
  named crawler groups, so under RFC 9309 the catch-all group governs and every
  path is disallowed. No page may be fetched, so none may be frozen — so the
  spec's planned JSON-LD parser (done-when 1) and frozen sample (done-when 4)
  are dropped, and pinned decision 3's hand-read branch is taken, mirroring the
  App Store listing. Trustpilot is declared `fetchable=False` in
  `ingest/sources.py` (`platform=trustpilot`, `parser=None`,
  `host=www.trustpilot.com`, `channel=unsolicited`, `profile=fr-digital-first`,
  `terms` naming the robots rule), refused before any request; its TrustScore
  and count are read by hand into `data/snapshots/manual_snapshots.csv` (3.9 on
  1,072 reviews, 2026-09-03, Measured). Rejected: a different User-Agent to slip
  the catch-all (evasion — never); the Trustpilot Business API (a paid,
  credentialed dependency — a STOP-and-ask, out of scope). The parser and
  sample are re-deferred to a future written authorization (BACKLOG). Approved
  by the developer 2026-09-03 after the robots check. *Superseded by [Phase
  3c](#phase-3c) (partly): the authorization arrived, so the parser and sample
  are built and the reviews imported OFFLINE on a second source; the crawler
  ban stands, so the source stays `fetchable=False` and is never fetched.*
- **The hand-read point reuses its anchor's profile.** The declaration's
  `profile` is `fr-digital-first`, exactly the Trustpilot anchors' profile, so
  `rating_trend` / `peer_ratings` keyed on `(source, profile)` read one series,
  not two — pinned by
  `tests/test_snapshots.py::test_trustpilot_hand_read_row_matches_its_anchor_seed`
  (closes the BACKLOG row "A fetched peer may not join its anchor's series").
- **The brand form.** The profile address's path is the platform name, the
  word `review`, and the insurer's domain; the domain's brand word is already a
  declared brand token, and `trustpilot` and `review` are generic platform/path
  vocabulary added to the test's `ADDRESS_WORDS`, as `opinion assurances
  assureur` and `google play store details` were. No new brand token; the
  address lives only in `ingest/sources.py` (D1).
- **The §6 response figures stay unseeded and B1.4 waits.** Trustpilot's
  response rate and delay are layout text, not data, and Trustpilot is not
  fetched, so no measured response figures land; SPEC B1.4 already states the
  cross-platform comparison waits for a second platform's measured figures
  (BACKLOG, re-deferred to Phase 9).

### Phase 3c

Branch `phase-3c-trustpilot-import`, spec `specs/phase-3c-trustpilot-import.md`,
APPROVED 2026-09-04 with amendment A1. Written authorization from Trustpilot
arrived, so this phase reverses Phase 3b's A1 ("not fetchable, `parser=None`")
for the reviews — but only for an OFFLINE import, not a live fetch.

**Supersedes Phase 3b's A1 (partly):** A1 said Trustpilot is not fetchable and
built no parser, re-deferring both to "a future written authorization." That
authorization is here. The robots ban still stands for our crawler, so the
source stays `fetchable=False`; what changed is that the reviews now arrive as
an authorized offline export and get a parser. A1's rating point (3.9/1,072,
hand-read) is untouched.

- **A1 — reviews are a second source, not a parser on the snapshot source.**
  `read_manual_snapshots` refuses a source that has a parser ("a parsed
  source's figures come from its capture"), so flipping `fr-digital-first-
  trustpilot` to have a parser would drop its hand-read 3.9/1,072 row and
  erase the rating point — the central constraint. So, mirroring the App Store
  feed/listing split, the snapshot source is left untouched and a SECOND source
  `fr-digital-first-trustpilot-reviews` (`platform=trustpilot`,
  `parser=trustpilot`, `fetchable=False`, `host=ca.trustpilot.com`, the one
  authorized profile page) reads the corpus. The rating series is now unchanged
  by construction. Approved by the developer 2026-09-04. Rejected: one source
  with a parser (drops the hand-read row).
- **Authorized offline import, not a live fetch.** The data is an authorized
  third-party export in hand; re-fetching with our crawler is redundant and
  would hit a `Disallow: /` host. So `fetchable=False` (the crawler never
  runs), and the export is saved as a capture and read from disk like any
  parser's. Its `terms` records the authorization minimally, exactly as
  Opinion Assurances does (a reason and a date; evidence held by the developer,
  never committed). Rejected: `fetchable=True` + a live re-scrape; a different
  User-Agent to slip robots (evasion — never).
- **The TrustScore stays hand-read; the corpus is themes only.** Trustpilot's
  3.9 is a weighted TrustScore, not the mean of the 1,050 rows (~4.0), and the
  displayed count (1,072) is not the export's row count (1,050). The reviews
  source emits NO snapshot, so `rating_trend`/`peer_ratings`/`channel_gap` read
  the same figures as before. Recomputing the rating from the corpus would
  fabricate a number. Pinned by `test_marts.py::test_trustpilot_rating_point_
  unchanged_by_corpus`.
- **The review's identity is its content.** The export carries no stable public
  review id (`web_scraper_order` is the scraper's per-run counter), so
  `external_id` is a content hash over (review_date, title, body, rating), like
  `opinion_assurances`; a re-import of the same review is one fingerprint and
  inserts nothing. All 1,050 rows are content-distinct (0 collisions).
- **The date is parsed locale-independently.** The export writes `Month D, YYYY`
  with an English month; the parser reads it with an explicit month table, not
  `strptime('%B')`, so the reading does not depend on the process locale. A
  French month name or a non-date refuses (§8). No clock reaches the data path.

**Gotcha — the offline capture is authored, not fetched.** The export is saved
as a capture (`page-1.csv` + `page-1.meta.json`, `status:200` standing for the
authorized fetch that produced the export) under
`data/cache/trustpilot/fr-digital-first-trustpilot-reviews/` (gitignored). It
is NOT produced by `ingest/fetch.py`; the source stays `fetchable=False` and
`make scrape` refuses it. The frozen sample (`fixtures/trustpilot/`) is a
hand-written, nameless, brand-free capture in the export's exact column shape,
so `ROWS=samples` runs the real parser without committing real reviews.

### Phase 4

Branch `phase-4-weekly-cron`, spec `specs/phase-4-weekly-cron.md`, APPROVED
2026-09-03. A weekly GitHub Actions cron scrapes the fetchable sources and
commits the new rating figures, so the time-series accrues while the rest is
built (PROJECT_BRIEF §9). The developer chose ratings-only over also banking
the review corpus weekly (2026-09-03): the misflagged-claim signal comes from
the already-ingested corpus classified by review date (Beat 2, Phase 5), so
the cron need not commit review bodies — and committing bodies would force the
still-unwritten personal-data excerpt rule.

- **The tracked path is a numbers-only file, not a tracked capture root.**
  `data/snapshots/fetched_snapshots.csv` carries a source slug, the capture's
  instant and the five figures; the address, profile, segment and channel come
  from the declaration (D1), so no brand and no review body enters git. Rejected:
  tracking the raw captures under `data/snapshots/` (commits review bodies —
  health text — with no paraphrase rule written). Closes BACKLOG "Phase 4 has
  no tracked path into `platform_snapshots`".
- **A non-network `record-snapshots` harvests captures to the file.** `make
  record-snapshots` reads the freshest capture per fetchable source via
  `read_captures` (the one parser path, no duplicated extraction) and appends
  each unseen `(source, captured_at)` as numbers; it fetches nothing and
  deletes nothing, so it needs no `confirm` gate. Rejected: a rebuild
  side-effect that writes a tracked file.
- **`rebuild ROWS=captured` reads the tracked file too, and the overlap is a
  no-op.** The fetched row's key `(platform, profile, fetch, pages[0], instant)`
  and fingerprint equal its live-cache twin's exactly — the file stores the
  capture's own instant and the loader derives the address as `pages[0]` (the
  page every fetchable source carries its aggregate on) — so the double read
  never double-counts. Pinned by `test_harvest.py::test_a_fetched_row_and_its_
  cache_twin_are_one_row`. Rejected: reading the file instead of the cache
  (hides a fresh point until the next commit); skipping capture snapshots under
  `captured` (breaks `test_marts.py`'s Measured-fetched-point test).
- **The workflow is `schedule` + `workflow_dispatch`, never `pull_request`.**
  It runs on the repo's own trusted runner on a weekly cron; `make confirm
  scrape` is one invocation (the goal gate arms — its `MAKECMDGOALS` origin is
  make's own `default`, not an environment or command-line definition), then
  `make record-snapshots`, then a commit of `data/snapshots/` only. This
  **resolves the Phase 3a residual** "the confirm gate does not hold against an
  environment that chooses what make reads or runs (`MAKEFILES`, `PATH`)" for
  this context: no untrusted input drives the workflow, so its environment is
  the runner's own. Rejected: refusing when `MAKEFILES` is set (moves the
  boundary one variable, as Phase 3a found).
- **The commit is one bot identity, a fixed brand-free message,
  `data/snapshots/` only.** `data: weekly snapshot <YYYY-MM-DD>`; the message
  is a literal in the tracked `weekly.yml`, so the D1 brand walk (`git
  ls-files`) already scans it, and `test_weekly.py` asserts it. `contents:
  write` is the whole token grant; the subtree limit is what the commit stages.
  This handles the weekly commit under BACKLOG "The D1 walk covers tracked
  files, not commit messages"; the general git-log walk over arbitrary commits
  stays deferred there.
- **B1.2–B1.4 stay Documented.** A handful of weekly points do not make the
  series ours to call Measured (BACKING's rating-row note); the source cells
  gain `data/snapshots/fetched_snapshots.csv` as the Measured points' tracked
  home. Pinned by `test_backing.py`.
