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
- **The study's permanent artifact is the static HTML export, and its render
  contract is mechanical, not editorial.** `study/export.py` renders one
  deterministic, self-contained file from the marts and `FORMULAS`; a Pending
  panel shows no number, every rendered number carries exactly one tag and
  equals its mart, and a Documented panel with an empty mart shows a "no data
  yet" state — each refused at render time by construction, not by a reviewer's
  eye. Metabase is a later, non-CI demonstration read on top of it. ([Brief §4.4](PROJECT_BRIEF.md); [Phase 9a](#phase-9a))
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
- **Formulas are data.** A printed expression, its unit and its callable are
  one entry in the module that owns the quantity, and the printer prints from
  the entry, so the shown formula, the number format and the computed number
  cannot drift; a test pins the outputs. Its two instances are
  `models/cost_model.py::FORMULAS` (the model and the hold-timer threshold) and
  `models/guardrail_sim.py::RULES` (the quantile draw and the hold). ([PLAN
  §4](docs/PLAN.md); [Phase 0a](#phase-0a); restated [Phase 8b](#phase-8b); the
  unit joined the entry in [the cost-outputs-unit fix](#fix--cost_model_outputs-carries-the-formulas-unit-2026-09-09-branch-fixcost-outputs-unit))
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
- **One standard, two readers (tooling, 2026-09-05).** The craft, security
  and architecture standards are three skills under `.claude/skills/`
  (`code-craft`, `secure-by-construction`, `architecture-fit`),
  `user-invocable: false` and path-scoped, so they load while the matching
  files are written; each is preloaded (`skills:`) into the agent that
  reviews that surface (code-reviewer, security-reviewer, senior-architect).
  The author and the reviewer read the same text, so the bar cannot drift
  between "how it was written" and "what it is checked against". Rejected:
  a fourth per-diff agent for craft (a second read of every diff and a
  fourth verdict line for one more Class value — craft is code-reviewer's
  third pass instead); copying the generic checklists the examples carried
  (OWASP web classes, npm tooling, React patterns: none of that surface
  exists here, and "skip nitpicks" is the instruction that lowers Opus 4.8's
  review recall).
- **Plans are challenged before they are built (tooling, 2026-09-05).**
  `/challenge` spawns `senior-architect`, a report-only devil's-advocate:
  steel-man first, then findings each with an alternative and its cost, then
  an advisory verdict; the developer's disposition (amend / accept / reject)
  is stamped on the spec as `Challenged: <date>, round <k>, spec <hash> — <verdict>`
  (one closed shape, unbolded, at line start; `specs/TEMPLATE.md` carries
  the slot). The `challenge-gate` hook is a reminder, never a gate: it exits
  2 with one line after an edit to an unstamped phase spec whose status is
  not DELIVERED (the phase's state, not the author's word PROPOSED — five
  earlier specs were first committed already APPROVED), and before
  `ExitPlanMode` it answers `ask` on every plan with the plan's own claim in
  the reason. The stamp is text the model itself can write, so the hook
  shows the claim instead of trusting it (round 1 of the tooling review,
  code-reviewer #3 / security-reviewer #2); a `deny` would block a plan the
  architect chose not to challenge, and caps and dispositions are the
  architect's call. A stamp goes stale when the spec is amended after the
  round; accepted, BACKLOG — superseded the same day by "The `Challenged:`
  stamp is keyed to the spec's Invariants and Done-when" below (the stamp now
  carries the spec hash). The agent judges plans only and never runs
  inside a review round.
- **Per-diff agents are pinned to a model id (tooling, 2026-09-05).**
  `model: claude-opus-4-8`, `effort: high` for code-reviewer,
  security-reviewer, functionality-tester and study-editor;
  `model: inherit`, `effort: high` for senior-architect and
  coherence-auditor (judgment over long reads, on the session's model). The
  session runs Fable 5.1 at `high`; CLAUDE.md → "Working with the model"
  carries what each guide changes here. `high`, not `xhigh`: the developer's
  cost call.
- **The ladder is a section of `code-craft`, not a skill or an agent (tooling,
  2026-09-05).** The lean-mode reference the developer supplied (a ladder:
  YAGNI → reuse → stdlib → native → installed dependency → one line → the
  minimum; five review tags; marker comments as a debt ledger; intensity
  levels) is adapted as the first section of the one craft standard, so the
  writer and the code-reviewer read the same text. Not taken: a standalone
  skill (a fourth standard that drifts from `code-craft`, one more listing
  entry per turn); a new agent (a fifth Opus run per round for a pass the
  code-reviewer's Pass 3 already makes). Dropped: levels, a gain card, a help
  card, marker comments (a BACKLOG row with a trigger is the ledger here),
  "ship the lazy version and question the spec" (the spec is the contract:
  doubting a Done-when item is a STOP-and-report).
- **The mechanical craft bars are ruff rules (tooling, 2026-09-05).**
  Complexity (`C901`, 10), branches (`PLR0912`, 12), statements (`PLR0915`,
  50), positional arguments (`PLR0917`, 5 — not `PLR0913`, which counts
  keyword-only options and declaration fields, the self-documenting shape
  this repo uses), boolean flag parameters (`FBT`), simplifiable forms
  (`SIM`, `RET`, `PIE`), commented-out code (`ERA`), unused arguments (`ARG`).
  No new dependency. The four functions over the complexity bar (two
  parsers' branch-per-tag bodies, the robots line kinds, a declaration's
  validator) carry a `# noqa: … -- <reason>` rather than a refactor: the
  standard asks for the split or the one-line reason, and a refactor of
  `ingest/` is a phase's work, not a lint's; `scrape` was split in round 2
  (its guards and robots capture into two helpers) and lost its three. A
  test pins the reason clause; `RUF100` deletes a `noqa` that suppresses
  nothing. Not taken: hand review of the same bars (drifts, uncounted); a
  stricter `PLR0913` (flags the keyword-only shape). Tests ignore `ARG` and `FBT` (fixtures and lambdas take
  the signature pytest hands them).
- **On-request loop steps are `disable-model-invocation: true` skills
  (tooling, 2026-09-05).** `/review-round`, `/phase-start` and `/selfcheck`
  each ended with a sentence asking the model not to run them; the flag does
  it deterministically and drops them from the model's listing. One layout
  for every piece of tooling prose. Not taken: keeping commands (two
  layouts, prose doing a flag's job).
- **The `Challenged:` stamp is keyed to the spec's Invariants and Done-when
  (tooling, 2026-09-05).** `spec <8 hex>` = sha256 of the two sections,
  trailing whitespace stripped per line; the hook reminds with both hashes
  when they differ. Not taken: restamping per amendment by convention (the
  hook cannot see a convention); hashing the whole spec (a wording edit to
  Why or Scope would stale a stamp the challenge still covers).
- **Naming the target is a hashed `check-docs` check (tooling, 2026-09-05).**
  `scripts/neutrality_hashes.txt` holds sha256 hex of lowercased tokens; the
  check tokenises tracked code, prose and workflow files and the last 50
  commit messages (URLs stripped) and reports file:line and a digest prefix,
  never the word. `ingest/sources.py`, `fixtures/` and `data/` are excluded
  (the D1 record). Not taken: deriving the tokens from the declared page
  addresses at check time (a heuristic over URL paths, the denylist shape
  this repo refuses); a plain denylist (the name in the repo). The hashes are
  the text's guard, not a secret: a short dictionary inverts them.
- **The developer-word STOPs are a hook (tooling, 2026-09-05).**
  `ask-gate.py` answers `ask` before `git push`, `gh pr create`, `gh pr
  merge` and `make … confirm`, seeing through a leading subshell opener, env
  assignment or wrapper word (round 2); never `allow`/`deny`. Not taken: the hooks
  reference's `if: Bash(git push *)` field on a settings entry (documented,
  not verified on this build — a field the build ignores would prompt on
  every Bash call, or never); the user-level `autoMode.soft_deny` list (per
  user, not per repo, and invisible to a test).
- **`run-tests` runs failures-first and stops at the first (tooling,
  2026-09-05).** `-x --ff`: a red suite shows in seconds instead of the full
  56 s; green costs the same. Not taken: `PostToolBatch` (one run per batch
  of edits — listed in the hooks reference, payload unread; a Gotcha to read
  before use); a test-impact plugin (a dependency).
- **CLAUDE.md is cut to what is recorded nowhere else (tooling,
  2026-09-05).** Repo map, Commands and Current status carried the per-phase
  history that the specs' Delivered paragraphs, DECISIONS' appendix and `make
  help` already hold; at 853 lines (54.7 KB) the file cost roughly 14k tokens
  on every turn and inside every custom subagent (which receive CLAUDE.md —
  sub-agents reference, read 2026-09-05). Now 690 lines (43 KB): the three
  sections keep only the semantics `make help` cannot state (the `confirm`
  gate, `ROWS`, the raw-table shape check, the no-key classify step). The
  rules sections are untouched; cut them only when they too carry
  redundancy.
- **The CLAUDE.md cap is 600 lines; the trim rides the next phase's branch
  (2026-09-11).** The BACKLOG row was re-deferred at the 3c, 5a,
  5b and 9g exits and the 6–9f exits did not report the 600 trigger at all;
  at 805 lines the trim cut the file to 592 (597 after Phase 9h's status
  paragraph)
  without touching a rule: the Repo map lost its per-mart and per-module
  history (each module's docstring and each spec's Delivered paragraph hold
  it), Commands lost the per-target lines `make help` prints and the
  `confirm` gate's mechanism (the Threat model of `specs/phase-3a-snapshots.md`
  holds it, and the section now points there), Working with the model and
  Project tooling lost the sentences that restated Workflow rules or a hook's
  own header, and Current status is the pointer paragraph plus the BACKLOG
  count that `docs/PLAN.md` §7 asked for. The rules sections (Deterministic
  first through the agents table) are ~330 lines on their own, so the ~400
  cap of Phase 0a cannot be met while they stand; the cap is restated as 600,
  the number the exits had already used as the trigger. No guard checks it —
  `wc -l` at each exit is the developer's step, as the 0a promise of an audit
  report proved to be. Not taken: moving rules into the three
  standards (a skill loads by path; a rule that applies on every turn belongs
  in the file every turn and every custom subagent receives); a second
  always-loaded file under `docs/` (custom subagents receive CLAUDE.md only —
  sub-agents reference, read 2026-09-05 — so the split would hide the moved
  rules from the reviewers). Written on `tooling/claude-md-trim`, reviewed by
  the docs-only round (coherence-auditor + study-editor, nine wording and
  record findings, all fixed), then folded into `phase-9h-sample-mean` at the
  developer's word — the one exception so far to "never mixed with a phase"
  (CLAUDE.md → Git workflow), taken because the round had already run.

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

- **Phase 4 — `main` is unprotected, so the weekly bot's subtree limit is
  self-discipline, not branch protection (2026-09-03).** This is a private repo
  on a plan without GitHub Team/Enterprise, so branch-protection rules are not
  available and `main` is not a protected branch. Several Phase 4 records first
  said the weekly bot's "commit only under `data/snapshots/`" limit was enforced
  by "branch protection's one written exception"; that rule does not exist.
  GitHub cannot scope a token to a path, so two separate guards stand in, one
  per threat. The subtree limit — which paths get committed — is the commit
  staging only `git add data/snapshots/` (pinned by
  `tests/test_weekly.py::test_workflow_commits_only_data_snapshots`). Token
  hygiene — who can reach the `contents: write` token — is a different control:
  the checkout runs `persist-credentials: false`, keeping the token out of
  `.git/config` during the untrusted `uv sync` and scrape steps, and the push is
  handed it inline via env. This also supersedes the Phase 0a decision #4
  wording "a CI check refuses any other path from that author" (the appendix
  entry, now marked superseded): no such CI check was built; staging discipline
  took its place. Official-docs check: GitHub's branch-protection and rulesets docs
  gate these features on Team/Enterprise for private repos. Revisit if the repo
  goes public or onto a paid plan — then add a real branch-protection rule (or a
  ruleset) that scopes the bot identity to `data/snapshots/`, and this becomes
  enforced rather than self-imposed. Corrected in
  `fix/weekly-branch-protection-wording`.
- **Tooling — `model: opus` drifts with the build (2026-09-05).** Every agent
  said `model: opus`; the subagent reference lists that alias as "the build's
  current Opus", which in this build resolves to Opus 5, not the Opus 4.8 the
  project means. Pinned the full id in the frontmatter. Same reference: the
  agent `effort:` field overrides the session level, and skills accept
  `paths:` (auto-load only under matching globs) and `user-invocable: false`.
  Hooks reference: PostToolUse cannot block (exit 2 shows stderr to the
  model, the edit stands); PreToolUse can answer `allow|deny|ask`; the
  `ExitPlanMode` payload is not documented, so `challenge-gate.py` reads
  `tool_input.plan` when it is a string and otherwise says so in its `ask`
  reason — it asks either way. The permission-rule syntax for a shell
  prefix is `Bash(git diff:*)` (colon); `Bash(git *)` is not documented and
  is either a no-op or every subcommand, so `/challenge` grants the four
  read-only git prefixes by name.
- **Phase 9i — the data.ameli browser export carries two byte-order marks and
  CRLF; one family's sub-rows sum a euro off (2026-09-12).** The API export
  (read during the spec's research) begins with one UTF-8 byte-order mark; the
  same table saved from the portal's Export dialog in a browser begins with
  two (`EF BB BF EF BB BF`) and ends its lines CRLF — `utf-8-sig` strips one
  and leaves `\ufeffannee`, a "missing column" refusal against the real
  file. The slice's declared shape is therefore "the header after any leading
  marks": `opendata/fee_split.py::_iter_rows` opens as plain UTF-8 and strips
  every leading U+FEFF from the first field, pinned by a two-mark CRLF case in
  `tests/test_fee_split.py`. Checked on the developer's file before the
  fixture was cut: the four family rows are present for 2024 with no
  suppressed token; médecins and chirurgiens-dentistes equal their sub-rows'
  sums exactly; `Ensemble des auxiliaires médicaux` is one euro below the sum
  of its five professions on both totals (the publisher's rounding of the
  family row) — the phase reads the four family rows as published and sums
  nothing itself, so the artifact is the table's own figures.


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
   refuses any other path from that author (Phase 4). *(Superseded: `main` is
   unprotected on this private repo and no such CI check was built; Phase 4
   bounds the subtree by staging only `git add data/snapshots/`, pinned by
   `tests/test_weekly.py`. See Gotchas.)*
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
- **Reviews per month is a query, not a mart** (since Phase 9e in
  `pipeline/build.py` beside `table_counts`, printed by `rebuild`, pinned by a
  test — `pipeline/metrics.py` deleted). No SPEC.md panel shows it, so a
  `sql/marts/` file would be an orphan under BACKING.md's rule. *(Phase 9e
  update: the decision stands — the query was NOT folded into B5.2
  `pipeline_row_counts` as the old BACKLOG trigger proposed; the 9e challenge
  (#6) found that fold would make the mart two-grain, and that a query is not an
  orphan, so the query relocated and stays a query.)* **This narrows the
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

### Phase 5a

Branch `phase-5a-label-sample`, spec `specs/phase-5a-label-sample.md`, APPROVED
2026-09-04. PROJECT_BRIEF §9 Phase 5 ("Hand labels + rules layer") is split
5a/5b as `docs/PLAN.md` §5 already named it: 5a is the trust foundation — the
closed label set, a stable review id, `make label-sample`, the text-free answer
key, the deterministic held-out split, and the labels wall — with no rule and no
model (5b writes `rules.yaml`/`rules.py`; 6 the one model call). Splitting keeps
each phase under six done-when items and lets the human labeling happen offline
between the two.

- **The seven labels are defined once, as data, and membership is a check.**
  `classify/labels.py::LABELS` is the five §5 themes (`document-loop`,
  `silent-rejection`, `second-payer`, `support-traction`, `coverage-price`) plus
  `positive` and `unclassified`; the labels reader refuses a theme outside the
  set rather than coercing it. Pinned by `test_labels.py`. Rejected: a free-text
  theme column or a coerce-to-default — either admits an eighth label.
- **`review_id = "{source}:{external_id}"`, derived in Python — no SQL change.**
  `stg_reviews` has no id column (its grain is `(source, external_id)`), so the
  id is that pair joined in `classify/labels.py`; the eval split hashes it and
  the answer key keys on it. A source slug and an external id (a numeric feed id,
  an `OA-…` id, a content hash) carry no `:`, so the join is unambiguous.
  Rejected: adding a `review_id` column to `stg_reviews` — a Phase 1 SQL change,
  hence its own fix PR, not 5a's to make.
- **`make label-sample N=<n>` writes a text sheet to gitignored `data/`; the
  tracked answer key carries no text.** The sheet is `review_id, source_url,
  text` at `data/label_sample.csv` (matched by the gitignored `data/*` rule);
  `classify/eval/labels.csv` is `review_id, theme`, tracked and text-free. The
  draw is `sha256(review_id)` order, first N, capped at the corpus — deterministic
  and nested in N (a larger N is a superset). Pinned by `test_label_sample.py`.
  Rejected: committing the text sheet — would track review bodies and force the
  unwritten personal-data excerpt rule (BACKLOG).
- **The answer key ships header-only.** No fabricated labels — not even for the
  synthetic fixture — land in `classify/eval/labels.csv` before a human labels;
  the reader returns zero rows for a header-only or absent file. This mirrors
  Phase 4's header-only `fetched_snapshots.csv`. The real 300–500 labels are
  human offline work (BACKLOG, opened). *Decision the spec did not spell out:
  the synthetic fixture is left unlabeled in 5a; the reader/split tests use tmp
  labels, so no in-session label generation happens.* **(Superseded in part,
  Phase 5b: the synthetic fixture's 39 ground-truth rows ARE now committed to
  `labels.csv` so `make classify-eval` has something to grade — fabricated
  reviews, no personal data; the real 300–500 labels stay offline. See the
  Phase 5b entry.)**
- **The held-out split is `sha256(review_id) % 5`, fold 4 held out, never
  random.** `classify/split.py::fold` is a pure function of the id's UTF-8 bytes
  (same fold on macOS and Linux); four folds tune in 5b, fold 4 gates in 6.
  Pinned by `test_split.py`. Rejected: `random.shuffle` or a stored split —
  breaks cross-machine reproducibility.
- **`classify/eval/` is the only reader of the answer key.** `test_labels_
  isolation.py` greps `classify/` (minus `eval/`), `pipeline/`, `sql/` and
  `models/` for the reader tokens (`labels.csv`, `labels_io`, `read_labels`,
  `LABELS_CSV`) and finds none. *Decision the spec did not spell out: the grep
  is filename/symbol based, so docstrings elsewhere describe the wall without
  naming the file — `classify/__init__.py` and `label_sample.py` say "the answer
  key", not the filename, on purpose.* Rejected: letting `rules.py`/`llm.py`
  read the labels to "help decide" — the exact leakage the wall stops.

This phase populates no BACKING row: it produces no displayed number. It is the
wall the Phase 6 eval gate writes B2.4 (`classifier_quality`) from, and the
labels B2.2/B2.5 rest on — those rows stay Pending. `make test` (646 tests)
passes.

Review round 1 (code-reviewer, functionality-tester, study-editor,
coherence-auditor; security-reviewer not triggered — no sensitive surface):
functionality-tester WORKS (all six pins bite under hand-mutation), all seven
invariants verified pinned. One should-fix — `positive_int` gated on
`str.isdigit`, true for non-ASCII digits (`N=²` reached `int()` and raised an
uncaught `ValueError`; `N=٣` would parse as 3), breaking the Threat model's
"never a traceback" — fixed by guarding `int()` with `isascii()`, with both
cases pinned. Record/wording nits fixed: the spec approval date (2026-09-04),
the over-cap BACKLOG trigger named to the 5b exit. Accepted to BACKLOG: widen
the labels-isolation grep to `ingest/dags/study/scripts` when 5b/6 add
`rules.py`/`llm.py`.

### Phase 5b

Branch `phase-5b-rules`, spec `specs/phase-5b-rules.md`, APPROVED 2026-09-04.
The second half of the split: the rules layer that reads a review and tags what
it is about — `classify/rules.yaml` (the patterns) + `classify/rules.py` (load,
apply) — graded by `make classify-eval`, which prints per-theme precision on the
four tuning folds. No model (Phase 6), no mart.

- **`rules.yaml` is the only pattern home; one group per emitting label, checked
  at load.** The file maps each of the five §5 themes and `positive` to a list of
  patterns; `classify/rules.py::load_rules` refuses a group keyed by anything
  outside the closed set (including `unclassified`, which is the fallback, not a
  group), so an eighth label is impossible. Pattern-matching lives here and in
  Python, never in SQL — the portability contract. Pinned by `test_rules.py`.
  Rejected: patterns in Python literals (a rule change becomes a code change) or
  in SQL (breaks portability).
- **A pattern matches at a word start (`\b` + literal), not naive substring.**
  `bot` matched `rabotées` under plain substring — a real precision miss the eval
  caught (support-traction fell to 0.80) — so the matching KIND changed to
  word-start (`re.escape`, `\b`-anchored, accent- and case-folded), killing the
  class of short-token over-matches while still matching plurals (`piece` →
  `pieces`). *Fix the class, not the case (CLAUDE.md): the mechanism changed, not
  a denylist entry.* Pinned by `test_rules.py::test_word_start_match_not_naive_substring`.
- **Grain is one row per review × theme; `positive` fires only when no theme
  did; `unclassified` is the single fallback.** A review is scored against every
  theme group (K matches → K rows); a warm word next to a complaint is the
  complaint, not `positive`; a review nothing matches is one `unclassified` row
  for the model to decide. The output is sorted by `(review_id, label)` — a pure
  function of the reviews and `rules.yaml`, byte-identical on re-run. Pinned by
  `test_rules.py`. Rejected: a packed multi-label cell; defaulting no-match to
  `positive` (asserts praise where there is only silence).
- **The synthetic corpus's ground truth is committed to `classify/eval/labels.csv`
  (was header-only in 5a).** The fabricated reviews were written to cover all
  seven labels; their hand labels are the answer key `classify-eval` grades
  against — 39 rows, `review_id, theme`, text-free, closed-set. *This supersedes
  the 5a "ships header-only" decision: 5a fabricated no labels before a human
  labeled; 5b labels the fixture (fake reviews, no personal data, no brand) so
  the rules can be graded on the synthetic corpus (CLAUDE.md → "build on the
  synthetic fixture first").* The real 300–500 labels for the real corpus stay
  offline (BACKLOG); their ids differ, so the two never collide. Rejected: a
  separate synthetic key under `fixtures/` — two answer keys, one reader forked,
  a fixture re-freeze.
- **`make classify-eval` grades the tuning folds only; the held-out fold is
  never read.** The recipe rebuilds the synthetic corpus, then the subcommand
  runs the rules over `stg_reviews` and scores against the answer key for reviews
  with `fold(review_id) != 4` (`classify/split`). The scorer (`classify/eval/
  precision.py`) filters both predictions and labels to the tuning folds before
  counting, so mutating a held-out label changes no printed number. Result: every
  theme's precision is 1.0 on the clean corpus, decided share 27/34 (0.79) — the
  rules decide the clear cases and leave the rest to the model. Pinned by
  `test_classify_eval.py` (including a crafted 0.5 case that proves the formula
  handles < 1.0). Rejected: reading the fixture CSV directly (skips the staging
  dedup); a `ROWS=` variable (real-row eval needs the real labels, offline).
- **`pyyaml` moved from transitive to a direct dependency.** Pre-approved for
  Phase 2 (CLAUDE.md allowlist), first actually used here to read `rules.yaml`;
  `uv lock --offline` moved it into `[project] dependencies` (already in the
  lock, no download). `yaml.safe_load`, never `load`.

This phase populates no BACKING row: per-theme precision and the decided share
are developer-facing tuning numbers read at the command line, not a displayed
study panel, and 5b writes no mart. B2.4 (`classifier_quality`) is the held-out
precision *and recall* the Phase 6 gate writes as a mart; B2.2/B2.5 are the
Phase 7 theme-share marts — all stay Pending. `make test` (670 tests, 24 new)
passes; `make classify-eval` and `make idempotency-check ROWS=synthetic` are
green.

Review round 1 (code-reviewer, functionality-tester, study-editor,
coherence-auditor; security-reviewer not triggered — no sensitive surface): all
pass, no correctness or security findings; functionality-tester WORKS with every
pin biting under hand-mutation (5/5). Applied: dropped a redundant `is_label`
clause at the load check (`RULE_LABELS ⊆ LABEL_SET`); reworded spec invariant 3 /
done-when 2 to name the three-tier fallback (theme → `positive` → `unclassified`);
added a `format_report` render test and a no-warehouse `classify-eval` CLI test
for the two coverage gaps named. Accepted: the already-struck BACKLOG row 20
(refreshed with the 5b test name; count unchanged).

### Phase 6a

Branch `phase-6a-model-fallback`, spec `specs/phase-6a-model-fallback.md`,
APPROVED 2026-09-04. The first half of the Phase 6 split (the architect's call
this session): the one model call site, the decision cache and the no-key
guarantee. The held-out eval gate and the `classifier_quality` mart (B2.4) are
6b. No mart, no BACKING row.

- **One model call site, `classify/llm.py`, key-gated and lazy-imported.** A
  language model is called from this module and nowhere else (the only
  `import anthropic`, imported inside the real-call function), and it sees only
  the reviews `rules.yaml` left `unclassified`. `model_available()` reads the key
  from the environment; with no key `make_model_decider()` returns `None` and the
  unresolved reviews stay `unclassified`. Pinned by `test_llm.py` (one call site,
  lazy import, model input is only rules-unclassified) and the wall
  (`test_labels_isolation.py`). *Rejected: importing `anthropic` at module top (an
  offline/no-key run would load a paid SDK on the data path) or a second call
  site.*
- **Strict closed-set parse of the reply → the seven labels or `unclassified`.**
  `parse_reply` reads only whole tokens equal to a label slug, so a near-miss
  (`document-loop-ish`) is NOT `document-loop` — it, and any free text, becomes
  `unclassified`. `normalize` enforces the review×theme grain (themes win, else
  `positive`, else `unclassified`), so even a misbehaving decider can never add an
  eighth label. Pinned by `test_llm.py::test_reply_outside_the_set_becomes_unclassified`
  and `test_combined.py::test_model_never_adds_an_eighth_label`. *Rejected:
  trusting the reply, or a fuzzy match to the nearest label.*
- **The cache is a gitignored, text-free file keyed `(review_id, prompt_version,
  model)`.** `data/classify/decisions.csv` (columns `review_id, prompt_version,
  model, theme`; a review with two model themes is two rows, one it could not
  place is one `unclassified` row). A run reads it and calls the model only for
  keys absent, then writes it back, sorted, so a re-record is byte-identical and a
  warm re-run makes zero model calls — deterministic despite a non-deterministic
  model. Pinned by `test_cache.py`. *Rejected: committing the cache (corpus-
  derived — brief §2.5 — and a committed synthetic cache would smuggle model
  decisions into the no-key CI run, hiding the gray band); keying without
  `prompt_version`/`model` (a prompt or model change would reuse stale decisions).*
- **`MODEL` and `PROMPT_VERSION` are pinned constants in `classify/llm.py`.** Both
  are in the cache key, so bumping either invalidates the cache by construction.
  `MODEL = "claude-haiku-4-5"` — Haiku, the fast, low-cost tier apt for a
  high-volume classifier over the reviews the rules left `unclassified` (the
  spec's "fast model" — round 1, coherence-auditor: opus was pinned first, then
  reconciled to Haiku); a single constant to change for a higher-judgment tier
  (the study's quality figure, B2.4 in 6b, is measured against whatever model
  ran). The real call is minimal (`model`, `max_tokens`, `system`, `messages`),
  portable across `anthropic` 1.x. *Rejected: a runtime- or
  environment-chosen model (non-reproducible; the cache key would drift silently).*
- **`classified_reviews` stays a Python value; 6a writes no mart and populates no
  BACKING row.** `classify/combined.py::classify_all` combines the rules with the
  cached/model decisions into review×theme rows; it is used by 6b's gate and Phase
  7's marts, not shown as a study number in 6a. B2.2/B2.4/B2.5 stay Pending. *Fix
  the class, not the case is unaffected here — the model is a closed-set parse, not
  a denylist.* *Rejected: materializing a mart now (no panel consumes it until
  6b/7, and a number a reader sees must wear a tag).*
- **`make rebuild` runs the classify step.** After staging, `rebuild` classifies
  `stg_reviews` and prints a summary (reviews / theme rows / positive /
  `unclassified` — the "not yet classified" band), so the no-key guarantee is
  proven end to end through the DONE command; with a key the developer's run
  populates the cache (paid, never an agent's). Over the synthetic corpus the
  rules leave 7 of 39 reviews unclassified (25 theme rows, 7 positive), pinned in
  `tests/pins.py`. *Rejected: a separate `make classify` the DONE does not
  exercise.*

The no-key run is green — the durable guarantee this phase adds and every phase
after keeps (`tests/test_no_key.py`, re-run always): with the key unset,
`make rebuild ROWS=synthetic` exits 0, no Anthropic client is constructed, no
socket opens, and the combined output equals the rules-only output.

`anthropic` (1.3.0) made a direct dependency (pre-approved, Phase 6 allowlist),
imported lazily so a no-key run loads no paid SDK. The labels-isolation grep was
widened to every code surface (`ingest`, `dags`, `study`, `scripts` added to the
swept set), closing the Phase 6 trigger on that BACKLOG row. `make test`
(704 tests) and `make rebuild ROWS=synthetic` (no key) are green.

Review round 1 (all WORKS, no correctness or security findings) reconciled
`MODEL` `claude-opus-5` → `claude-haiku-4-5` (the fast, low-cost classifier tier
the spec's pinned decision names) and added a one-line refusal on the paid path:
a `ModelError` maps an `anthropic.APIError` (a bad model id, a rate limit the
SDK's retries could not clear, a transient network error) to one line naming the
model in `pipeline/cli.main`, never a traceback — the developer-run paid path is
now visible on failure rather than a stack trace. The no-key path never reaches
it. *Fix the class, not the case: a closed exception type mapped to a clean
refusal, the same shape as the `Refused`/`PageShapeError` catches.*

### Phase 6b

Branch `phase-6b-eval-gate`, spec `specs/phase-6b-eval-gate.md`, APPROVED
2026-09-04. The second half of the Phase 6 split: the held-out eval gate and the
`classifier_quality` mart (B2.4) — the one BACKING row this phase populates.

- **The gate scores the held-out fold alone (fold 4), precision AND recall per
  label, in `classify/eval/gate.py`.** It reuses `split.is_heldout` and the
  answer key (through `labels_io`), and takes the classifier's predictions as
  input — a pure function of predictions and labels, like 5b's
  `precision.evaluate`. For a label T on fold 4: `hits = |predicted ∩ actual|`
  (the shared numerator), `precision = hits/predicted`, `recall = hits/actual`,
  each `None` when its denominator is 0 (0/0 is undefined, not 0). Pinned by
  `test_gate.py` (fold-4-only, the formula, a crafted disagreement < 1, null on
  zero). *Rejected: scoring every fold (leaks the tuning folds into the study
  number and lets the gate be tuned against — the split's whole purpose); a
  separate recall-only pass (two scorers drift).*
- **`classifier_quality` is the first Python-fed mart — DDL fed by Python, not
  logic in SQL.** `sql/marts/classifier_quality.sql` is `create or replace table
  … (columns)` with no `select`; it runs in `build_derived` like every mart, so
  the table always exists after a rebuild. The CLI classify step (6a's placement,
  where the model and cache already live) scores fold 4 and calls
  `build.write_classifier_quality`, which clears the table and inserts one row per
  scored label in the gate's fixed label order (byte-stable). *Rejected: a
  `create … as select` mart (there is no SQL source — the metric is computed in
  Python against the answer key, which SQL may not read, portability contract);
  populating inside `rebuild()` (its ~50 callers treat the return as a counts
  dict, and the mart's row count is constant, so populating there costs a
  return-type change for zero idempotency signal — the value-stability is pinned
  by `test_classifier_quality.py::test_two_rebuilds_identical_mart_rows`, which
  the count-diff of `idempotency-check` cannot see).*
- **The mart carries a computed metric's provenance, not a scraped row's.**
  Columns `label, hits, predicted, actual, precision, recall, heldout_fold (= 4),
  answer_key (= 'classify/eval/labels.csv'), run_id, tag (= 'Measured')`. No
  `source_url`, no `captured_at` — a quality metric has no address and no capture
  instant, and a build timestamp would be a clock on the data path. `hits`,
  `predicted`, `actual` are stored so `precision = hits/predicted` redoes by hand
  (brief §2.1). Pinned by `test_classifier_quality.py`. *Rejected: faking
  `source_url`/`captured_at` (dishonest provenance) or a `now()`/`current_date`
  stamp (the banned clock — `sql_lint` forbids it in SQL, and the Python insert
  carries no timestamp).*
- **B2.4 flips Pending → Measured, upstream source `classify/eval/labels.csv`;
  B2.2/B2.5 stay Pending.** The numbers are a direct measurement of the real
  classifier against the real hand labels; the answer key is the honest upstream
  source (accepted by `check-backing`'s dataset-name shape). *Rejected: Modeled
  (there is no model or assumption — a measurement); the theme-share marts are
  Phase 7.*
- **The wall holds, now including the gate; the CLI hands the gate predictions,
  not labels.** `gate.py` lives in `classify/eval/` and reads the answer key
  there; the CLI, `build.py` and everything else pass predictions in and get
  scores back, reading no `labels.csv` (`build.write_classifier_quality` takes the
  provenance strings as parameters, so no reader token enters `build.py` or the
  CLI). Pinned by `test_labels_isolation.py::test_the_gate_is_inside_the_wall`.
  *Rejected: the CLI or `build.py` reading the key (a classifier that sees its own
  answers makes its scores a lie).*
- **No new `make` target; the gate rides `make rebuild`.** The held-out grade is a
  real build output (it lands in the mart and prints a one-line summary under the
  classify summary), unlike 5b's `make classify-eval`, a tuning-fold dev
  diagnostic. *Rejected: a `make classify-gate` — surface the five parts do not
  need (BACKLOG if a developer later needs the report without a full rebuild).*

On the synthetic corpus fold 4 is 5 reviews, all clear cases the rules classify
correctly, so every label present scores 1.0/1.0 and the two labels absent from
fold 4 are `None` — pinned in `tests/pins.py` (`RULES_HELDOUT`). The formula (a
disagreement scores below 1.0) is proven by a crafted unit test, not by this
clean fixture. The no-key run stays green and populates the mart rules-only,
truthfully (lower recall in general; here coincidentally perfect on the five
clear held-out reviews). `make test` (722 tests, 18 new), `make rebuild
ROWS=synthetic`, `make idempotency-check ROWS=synthetic` and `make check-backing`
(B2.4 Measured) are green with no key.

Review round 1 (code-reviewer, functionality-tester, study-editor, coherence-
auditor; security-reviewer not triggered — no sensitive surface): no blockers.
**Amendment A1** applied (spec) — the gate found by the code-reviewer to grade
predictions against the synthetic answer key for *every* input, so
`ROWS=captured|samples` wrote a garbage Measured mart (real ids never match
synthetic labels). Fix: `score_heldout` grades only reviews both classified and in
the answer key (the intersection on the held-out fold), and the CLI writes no mart
when nothing is graded — chosen over a per-input `ROWS == "synthetic"` guard so a
mixed answer key in Phase 7 grades a real corpus against its real labels while
ignoring synthetic labels it did not classify. *Fix the class, not the case: a
coherence precondition on the measurement, not a denylist of inputs.* Two pinning
tests added for the functionality-tester's surviving mutations (the mart's
precision/recall column mapping under asymmetry — invisible on the symmetric
synthetic fold — and the re-populate `delete`). The branch and spec file were
renamed from the doubled `phase-phase-6b-eval-gate` to `phase-6b-eval-gate`
(coherence-auditor; `/phase-start` had prepended `phase-` to a slug already
starting with it). Accepted to BACKLOG: the mart write is not warehouse-aware
(hardcoded DuckDB connection; Snowflake is Phase 10).

### Phase 7a

Branch `phase-7a-findings-marts`, spec `specs/phase-7a-findings-marts.md`,
APPROVED 2026-09-04. Phase 7 cut to its deterministic first half: the
classifier-fed theme-share marts. The open-data half (DAMIR slice + fitted cost
distributions) is Phase 7b.

- **The classification is persisted to `stg_classified_reviews`, then two
  marts count it in SQL.** `classify_all` returned a value only (6a); Phase 7a
  writes it at the `(source, external_id, theme)` grain to a Python-fed staging
  table, so `theme_share_by_month` (B2.2) and `theme_share_by_segment` (B2.5)
  are portable `create … as select` marts over it — SQL does the aggregation,
  the Portability contract holds. *Rejected: aggregating in Python (pandas-free
  counting, and SQL is where the work belongs).*
- **The classify step runs the two theme marts, after filling
  `stg_classified_reviews`; `build_derived`'s marts loop excludes them
  (`POST_CLASSIFY_MARTS`).** They read a table Python fills between staging and
  the rest, so running them in the generic marts pass would build them empty.
  *Rejected: reordering `build_derived` into staging→classify→marts (a wider
  refactor that also forces `classifier_quality`'s DDL to become
  non-destructive); running them empty then again (pointless double build).*
- **Amendment A1: a review's segment is stamped onto the review at load time
  (`raw_reviews.segment`), not joined at query time.** The marts split by
  segment. `raw_source_pages` was built to supply it by an exact `source_url`
  join, but that join matches 0/39 on the synthetic corpus (the fixture's
  `source_url` is a brand-free host root, not a page address) and the
  `source`/platform slug is declared under two segments on the `samples` input
  (real `digital-first` + the per-parser `sample`), so no query-time key
  resolves segment on every input. A review is loaded from exactly one source
  whose `segment` is known in Python then, so `raw_reviews` gains a `segment`
  column (outside the content hash — attribution, like `run_id`), stamped from
  the source (`segment_by_platform` for the segment-less synthetic fixture);
  the marts group by `stg_reviews.segment`, unambiguous on synthetic, captured
  and samples. An existing pre-7a database refuses the rebuild (the A8
  column-check) until `make confirm reset`; CI builds fresh. *Rejected: the
  `source_url` join (0/39 synthetic); the `source`/platform join (two segments
  per platform on samples); re-freezing the synthetic reviews to carry page
  addresses (would inject real-brand URLs into the brand-free corpus).* Decided
  with the developer; committed as the spec amendment alone before the code.
- **The marts carry the Measured tag as their provenance — no `run_id`,
  `source_url` or `captured_at`.** A computed share has no address or capture
  instant; `month` is `substr(review_date, 1, 7)`, the review's own date (no
  clock). The inputs (`reviews`, `theme_rows`) are stored so `share =
  theme_rows/reviews` redoes by hand, and `run_id` lives one hop upstream on
  `stg_classified_reviews`. *Rejected: a scalar `run_id` on a `create … as
  select` mart (no way to inject it in static SQL without templating; the
  upstream table carries it).* *Superseded 2026-09-08 (branch
  `fix/theme-marts-run-id`): the two theme marts do carry `run_id` — it is
  a column of `stg_classified_reviews`, carried through `min()`, no
  scalar needed; the Phase 9b corpus gate reads it. See the fix entry
  below.*
- **B2.2/B2.5 flip Pending → Measured; upstream the four review platforms.**
  The numbers are the gated classifier's own output over the review corpus,
  counted. B1.1 (hero case) and B2.1 (taxonomy examples) stay Pending — they are
  Documented rows with no mart, flipping when their prose is curated with links
  (Phase 9). *Rejected: Modeled (a count, not a model).*
- **The "vs traditional" half is empty.** Every declared source is
  `digital-first`; the marts split by whatever segments the data has. Recorded
  as a BACKLOG row (revisit when a traditional-mutuelle source is added), noted
  beside the B2.5 panel in SPEC.

The multi-segment guard the first design needed is gone with A1 (segment is a
review column, unambiguous). `make rebuild ROWS=synthetic`, `make
idempotency-check ROWS=synthetic`, `make check-backing` (B2.2/B2.5 Measured) and
`make test` are green with no key (test count at build below the round-1 note).

Review round 1 (code-reviewer, functionality-tester, study-editor, coherence-
auditor; security-reviewer not triggered — no sensitive surface): one BLOCKER,
found independently by all three code agents. The two theme-share marts still
joined `raw_source_pages` by `source` — the platform-slug join A1 rejected — so on
the `samples` input, where a platform is declared under two segments, every review
was counted twice (16 reviews → 32 theme rows, `sample` data mis-tagged
`digital-first`). The segment stamped at load was correct but unread by the marts:
A1 was applied everywhere except the two files it existed to fix. Fix: both marts
rewritten to group by `stg_reviews.segment` (joined to `stg_classified_reviews` on
source + external_id), the `raw_source_pages` join removed, the mart headers
corrected. *Fix the class: the marts read the load-time segment A1 added, not a
query-time join.* Two coverage gaps closed — no test built the marts on `samples`
(`test_marts_on_samples_count_each_review_once`), and the `distinct` in the reviews
denominator survived a mutation because no synthetic review is multi-theme
(`test_distinct_denominator_counts_a_multi_theme_review_once`, which crafts one).
One prose reword: the B2.2 no-key note put in plain language (study-editor). Round
2 (the same agents) confirmed the fix under adversarial hand-mutation — both
mutations now fail their guard — with no new code findings; it caught only record
drift (this note's placement and stale counts), corrected here. `make test` is 731
tests; the DONE command and `make review-gate SPEC=…` are green with no key.

### Phase 7b

`specs/phase-7b-open-data.md`, APPROVED 2026-09-04. The open-data half of the
Phase 7 split: a frozen slice of Open DAMIR and the lognormal claim-cost fit that
Phase 8's cost model and simulator consume (PROJECT_BRIEF.md §7). Four decisions,
each surfaced and chosen before the spec:

1. **The fit is a lognormal by log-moments** — `mu = mean(ln x)`,
   `sigma = population-std(ln x)` over the positive reimbursed amounts
   (`opendata/fit.py`). Closed-form, hand-checkable, and identical to the
   lognormal maximum-likelihood fit: no optimizer, no fitted predictive model
   (brief §2.1). Rejected: gamma method-of-moments (less standard for claim cost)
   and empirical-deciles-only (no `mu`/`sigma` to show). Health costs are
   lognormal because a few large claims sit far above many small ones.
2. **The frozen fixture is the sourced sample** — `fixtures/damir/` holds a
   small, real, brand-free slice (the `PRS_REM_MNT` column only), so CI
   reproduces the sourced fit offline. Rejected: pinning over the gitignored real
   month (not reproducible in CI). The fixture is drawn by *systematic* sampling
   (every k-th valid amount across the whole month, `opendata/slice.py`), not the
   first N rows: a DAMIR month is sorted by its aggregation axes, so the first N
   would be one biased corner. Systematic sampling is deterministic (no RNG) and
   spans the file.
3. **The fit artifact is tracked, derived, numbers-only** —
   `data/damir/claim_cost_fit.csv` (a new `!data/damir/` gitignore negation, the
   `data/snapshots/` precedent) carries `mu`, `sigma`, `n` and the goodness-of-fit
   deciles (empirical vs `exp(mu + sigma·z_p)`, "the fit shown"). A test recomputes
   it from the fixture and pins every value; Phase 8 reads it. Rejected:
   recompute-only with nothing committed.
4. **The DAMIR fetch is a new confirm-gated network target** — `make confirm
   fetch-damir [MONTH=YYYY-MM]`, developer-run, never by an agent; `GATED` in
   `pipeline/cli.py` extends from `("reset", "scrape")` to add `"fetch-damir"`.
   `MONTH` is a closed `YYYY-MM` shape validated in Python before any path is
   built. Rejected: folding into `make scrape` (mixes review-platform robots and
   per-source declarations with a plain bulk download).

Also decided in this phase:

- **A second network module, one identity.** The DAMIR download is a plain bulk
  GET over stdlib `urllib` (`opendata/fetch.py`), so `ingest/fetch.py` stays the
  only `httpx` import and no dependency is added. The identifying User-Agent
  header moved from `ingest/fetch.py` to `ingest/politeness.py`
  (`IDENTIFYING_HEADERS`), where the other politeness knobs live, so both the
  httpx crawler and the urllib downloader identify us from one place;
  `tests/test_ingest_layout.py` now pins the header literal in politeness.py.
- **The cache root stays bound once.** `opendata/sources.py` derives its cache
  directory from `ingest.sources.CACHE_ROOT`, not a second `data/cache` literal
  (the single-binding invariant).
- **No mart, no BACKING flip.** 7b lands upstream data + the fit only. B3.3
  (`cost_model_params`) and B4.3 (`guardrail_sim`) stay Pending — their marts are
  Phase 8. `make check-backing` is unchanged (19 rows, 7 marts).
- **`opendata/` is its own package**, distinct from `ingest/` (review scrapers,
  which carry the brand) and Phase 8's `models/` (the formulas that read the fit).
  DAMIR names no insurer, so nothing under `opendata/` carries a brand token.

Gotcha (stack): a national Open DAMIR month is ~5.7 GB uncompressed
(July 2025: 950 MB gzipped, 5.7 GB raw), an order larger than PLAN's "hundreds of
MB". So the real fetch is firmly developer-run and its output stays under the
gitignored `data/cache/damir/`; CI and the DONE command fit only the small frozen
fixture. The reimbursed-amount column is `PRS_REM_MNT`, `;`-delimited, and French
cells may use a `,` decimal separator (the slice guard accepts both).

Gotcha (Amendment A1 — the reimbursement-type column): the official variable
dictionary (`2024_descriptif-variables_open-damir-base-complete.xlsx`) shows
`PRS_REM_MNT` read without a `PRS_REM_TYP` filter pools the legal Assurance
Maladie reimbursement (type 0/1) with *parts supplémentaires* (type ≥ 2). The
slice keeps only `PRS_REM_TYP ∈ {0,1}` so the fit is the claim cost, not a pool —
a closed-set filter, the "fix the class" kind, not a special-case skip. Confirmed
against July 2025: of 35.5 M rows, type 0 = 18.6 M and type 1 = 0.5 M (both legal,
comparable per-row scale), type 99 = 14.4 M and other types the rest; 16.1 M legal
rows carry a positive amount, a large representative population. The fixture
carries both columns so the filter is reproducible offline.

Gotcha (Amendment A2 — the portal serves gzip): the real DAMIR resource is
`A<YYYYMM>.csv.gz`. `cache_path` keeps the `.csv.gz` name and `slice.py` opens a
file by its gzip magic bytes (`\x1f\x8b`), not its name, so one reader serves the
gzipped national month and the plain tracked fixture and `fetch-damir →
sample-damir` needs no manual decompression. Caught when the developer fetched
July 2025; the byte-identical fixture reproduces from the gzip directly.

Finalization (2026-09-05): month 2025-07 (`A202507`), an ordinary non-holiday
month; a systematic `N=5000` draw (its `sigma` within 0.04 % of the full-
population value, vs ~7 % for `N=500`) is the frozen `fixtures/damir/`; the fit
(`mu`, `sigma`, `n` + deciles) is pinned in `tests/pins.py` and committed as
`data/damir/claim_cost_fit.csv`; `_check("damir")` guards the frozen fixture.

### Tooling — the review stack (2026-09-05, branch `tooling/review-stack`)

Not a phase (no spec, no BACKING row): the working method after Phase 7b, from
the two platform prompting guides (Fable 5.1, Opus 4.8; read 2026-09-05) and a
review of the five reviewer/skill examples the developer supplied. Landed:
CLAUDE.md → "Working with the model" and "How the tooling fires across a
phase"; `senior-architect` + `/challenge` + `challenge-gate.py` (pinned by
`tests/test_challenge_gate.py`); the three standards under `.claude/skills/`
preloaded into their agents; code-reviewer rewritten with an Invariants pass
kept, a craft pass added and coverage-first reporting; security-reviewer
extended with the secure-coding classes this repo can exhibit (foreign input
parsed to a shape, paths derived, no shell, decompression caps, safe YAML, the
model prompt as a data boundary, log hygiene, the hooks surface);
`tests/test_claude_config.py` admits `.claude/skills/*/SKILL.md` as tracked
prose. The Process entries above and the Gotcha record the choices.

Round two, the lean pass (same branch, same day), after the developer asked
what a lean-mode reference should contribute and what the workflow itself
should lose: the ladder in `code-craft`; the mechanical craft bars as ruff
rules; the three commands as on-request skills; the stamp keyed to the
spec's hashed sections; naming-the-target as a hashed check; the `ask-gate`
hook; the fast-red `run-tests` hook; CLAUDE.md cut from 853 to 690 lines. Each
choice and its alternatives is a Process entry above; BACKLOG rows 14, 55
and 58 close (BACKLOG.md line numbers, the convention throughout this
file); row 57 was closed by reading the reference and reopened in round 2
until its own trigger — the `ask` prompt observed at a plan-mode exit —
fires. Verified against the official references that day: a
skill's `paths:` auto-loads it while matching files are worked on; an agent's
`skills:` preloads the full text at start; custom subagents receive
CLAUDE.md (Explore and Plan skip it); a PreToolUse matcher is the tool's
name; hooks accept an `if:` permission-rule filter (not used, see the
`ask-gate` entry).
Verdict on the reviewers as they stood: strong on the project's rules and on
conduct, thin on craft and on general secure-coding classes; code-reviewer and
security-reviewer were each partial, and this branch closes both gaps. Its own
round 1 (five agents, 30 consolidated rows, 0 code blockers) was fixed in full.

### Phase 8a

`specs/phase-8a-cost-model.md`, APPROVED 2026-09-06 (challenged round 1, stamp
`f52519a7`). The cost-model half of a Phase 8 split (PROJECT_BRIEF.md §7, Beat 3):
8a lands B3.1–B3.4; 8b lands the guardrail simulator and the hold timer
(B4.1–B4.3). The split follows the seam the brief draws — §7's formulas and
guardrail toggles are the cost model, the synthetic claims and the day/euro
threshold are the simulator — and keeps each spec under the ~6-decision cap (the
7a/7b precedent). 8a leaves 8b a `scenario` column on every output and curve row,
so Beat 4's "the curves move" panels read the same marts.

Six pinned decisions:

1. **Formulas and parameters are data in `models/cost_model.py`; the layer is
   handed the fit and computes.** `FORMULAS` is an ordered tuple of
   `Formula(name, expression, kind, fn)`, `kind ∈ {point, curve}`; `PARAMETERS`
   is a tuple of `Parameter(name, default, unit, sourcing, citation, low, high)`.
   `defaults(fit)` builds the value set from the static table plus the `mu`,
   `sigma`, `emp_p50` rows the caller's `Fit` supplies, so `models/` reads no
   file, no clock, no key (invariant 8, an import allowlist: `math`,
   `dataclasses`, `collections.abc`). Rejected: formulas in a YAML the code
   evaluates from text (a string that can drift, and evaluating text is the wrong
   guard); a formula in SQL (a second copy, and `exp` is a dialect risk); the
   crossover as a `point` entry re-running the grid at every grid point.
2. **Every parameter carries a range; sourced defaults cite the record the way
   the anchors do.** The four scale anchors are `sourced` with citation
   `PROJECT_BRIEF.md §6`, said to be second-hand floors (the anchors' precedent,
   since a disclosure address carries the brand — Phase 3a D1); range = the floor
   to twice it (the study's exploration bound, printed as such). `mu`/`sigma`
   range = the fit ± 2 standard errors (`se_mu = σ/√n`, `se_sigma = σ/√2n`),
   arithmetic printed; `emp_p50`'s range is itself. `mean_claim`'s expression
   text carries the bias direction (a DAMIR cell sums ≥ 1 claims, so the mean
   overstates a claim and understates `claims`/`friction_cost`), and
   `median_cell` prints beside it as the contrast. Rejected: a second anchors CSV
   under read-only `fixtures/`; the fit reader in `models/`; a range only on
   unsourced parameters; the fixture's arithmetic mean as a third sibling (needs
   a new 7b artifact row — a BACKLOG row).
3. **Three DDL-only Python-fed marts, one writer, filled inside `rebuild()`.**
   `cost_model_params`, `cost_model_outputs`, `cost_curves` are `create or
   replace table (…)` shapes run by the generic marts loop (the
   `classifier_quality` precedent); `pipeline/build.py::write_model_marts` clears
   and inserts the three in one transaction, and `rebuild()` calls it after
   `build_derived` on every input — so `idempotency-check` (which calls
   `rebuild()` only) and every caller see filled marts. Rejected: `create … as
   select` (arithmetic in SQL); a model step in `pipeline/cli.py` after the
   classify step (the pre-challenge proposal: `idempotency_check` would have
   diffed three empty tables).
4. **A fixed 41-point flag-rate grid; two crossovers, both grid rules; the
   default is marked.** The grid is 0.000–0.200 step 0.005 per scenario;
   `crossover_flag_rate` is the first grid point with net < 0 (the curves cross),
   `marginal_crossover_flag_rate` the first grid point whose net is below the
   previous point's (each extra flag costs more than it recovers), each null when
   none. Net is concave in the flag rate, so each rule fires at most once.
   Rejected: a bisection or analytic root (the grid *is* the arithmetic a reader
   redoes); one crossover only (the chart sentence and the drawn point would
   disagree).
5. **Scenarios are a closed set of parameter overrides, named by their effect.**
   `SCENARIOS = {baseline, contacts_once, churn_halved, both}` — the §7 effects,
   `both` composing the two atomic toggles so the halving rule is written once.
   Naming by effect (not `ask_once`/`hold_timer`) frees the `scenario` column for
   8b's simulated hold timer with no collision. Rejected: one mart per scenario;
   free-text names.
6. **Written numbers are rounded to fixed places at one site.** Euros to 2, rates
   and log-euros to 6, counts whole, all through `rounded(unit, value)` — the
   writer, `make model`'s printer and the tests call it, so mart rows and printed
   text are byte-identical. Rejected: `Decimal` end to end (the exponential forces
   float anyway); rounding in the writer and again in the printer.

The four amendments folded in after challenge round 1 (recorded in the spec's
disposition block): marts filled inside `rebuild()` (not a CLI step); two
crossovers (not one); scenarios by effect (not `hold_timer`, which would collide
with 8b); a range on every parameter (not only unsourced). Two questions
answered: `PROJECT_BRIEF.md §6` is a second-hand citation the study labels as a
floor (not a followable address); B4.1 flips as one beat in 8b (not in 8a).

Also decided in this phase:

- **`cost_per_contact` stays `unsourced`.** No citable public customer-contact
  cost benchmark was handed over before build; brief §7 allows either. A BACKLOG
  row carries the trigger (one found → a one-cell flip to `sourced`).
- **`opendata/fit.py::read_fit` is the strict mirror of `write_fit`.** It reads
  the tracked numbers-only artifact back to the `Fit` and its deciles — every
  declared name present, numeric and finite, `n` a positive integer, nothing
  else; an unknown, missing, duplicate or non-numeric name refuses with the name.
  A 64 KB size cap refuses a file that is not the shape we wrote. The caller
  (`read_model_fit`) hands the result to the model layer, so `models/` reads no
  file.
- **The `emp_p50` contrast.** The cost model's `Fit` carries `emp_p50` (the
  median DAMIR cell), which the caller lifts from `read_fit`'s deciles — the
  spec's `defaults(fit)` "the caller's `Fit` supplies mu/sigma/emp_p50" made
  concrete as a small `models`-local dataclass, so the layer imports no
  `opendata` type.
- **Gotchas.** DuckDB binds Python `None` into a `double` column as SQL NULL with
  no cast surprise, so a scenario whose net never turns negative stores a null
  crossover (`churn_halved`, `both`); confirmed under `idempotency-check`. The
  `create or replace table` in the generic marts loop followed by delete/insert
  in `write_model_marts` on the same connection is byte-stable across two
  rebuilds (the `classifier_quality` order holds). The defaults' outputs were
  computed before any pin was typed: the baseline curves cross at flag rate 0.095
  with the 0.05 "you are here" marker to its left — the story holds without
  tuning a default.

### Phase 8b

`specs/phase-8b-guardrail-sim.md`, APPROVED 2026-09-06 (challenged round 1, stamp
`7501f9a3`). The simulator half of the Phase 8 split (PROJECT_BRIEF.md §3 Beat 4,
§7): the synthetic claims, the hold timer, and the computed SLA threshold
(B4.1–B4.3). No new dependency — the normal quantile is stdlib
`statistics.NormalDist().inv_cdf`, already used by `opendata/fit.py`.

Six pinned decisions:

1. **The claims are a quantile draw, `n` = 1,000, never a random draw.**
   `guardrail_sim.py::synthetic_claims` reads the fitted lognormal at the 1,000
   midpoints `(i − ½)/n` — the same amounts every run, each `exp(mu + sigma ×
   z((rank − ½)/n))` a reader can redo. Rejected: a seeded pseudo-random draw (the
   seed is a hidden parameter and "redo by hand" fails for claim 731); the
   fixture's 5,000 real cells as the claims (a cell is not a claim, the fixture is
   read-only under a Measured tag); an analytic CDF only (no drill-through to the
   claims); `n` = 5,000 (five times the rows for the same shape).
2. **The threshold is Beat 3 arithmetic: three `point` formulas in
   `cost_model.py::FORMULAS` over two new `unsourced` knobs, capped at the loop.**
   `loop_days = contacts × days_per_round`; `friction_per_day = (contacts ×
   cost_per_contact + churn_prob × customer_value) / loop_days`; `timer_amount_eur
   = fp_share × friction_per_day × min(timer_days, loop_days) / (1 − fp_share)`.
   The `min(…, loop_days)` cap (challenge #1) makes the threshold linear in the
   day up to the loop and constant after — friction stops accruing when the loop
   ends — so "errs toward holding" holds on every grid row. It prices the ex-ante
   decision (a hold planned at day 0 to run `N` days), the reading the study's
   sentence makes (challenge Q5). Rejected: an unbounded linear threshold (past the
   loop it charged friction the model never incurs); the marginal reading (the
   slope reverses); the fraud pool's average as a per-claim ceiling (independent of
   the claim's size); a churn-over-hold-days curve (a second unsourced
   relationship); a separate threshold formula in the simulator (brief §7: computed
   from the Beat 3 model); an `escalation_days` parameter (below).
3. **The hold rule and its outcomes are closed data in `RULES`; an escalated
   claim completes the loop.** `hold(claim, scenario_params, timer_on,
   timer_amount)` → `(hold_days, outcome)` with `hold_days ∈ {loop_days,
   timer_days}` and `OUTCOMES = (loop_released, timer_released, timer_escalated)`.
   For a large claim the timer changes who decides, not how long — a person's
   turnaround has no public anchor (a BACKLOG row with its trigger). Rejected: an
   `escalation_days` guess (the one knob that would make the timer look better);
   the timer shortening large holds; outcomes as free strings.
4. **Simulator scenarios are a closed set carrying the cost-curve scenario they
   pair with; the timer is set from the un-fixed world.** `SIM_SCENARIOS`: `no_fix`
   → `baseline`, `ask_once` → `contacts_once`, `hold_timer` → `churn_halved`,
   `both_fixes` → `both`; `simulate` evaluates the model at `curves_scenario` for
   the scenario's `loop_days` and takes `timer_amount_eur` from the `baseline`
   evaluation, whatever the scenario. Under `both_fixes` the one-round loop (7
   days) ends before the default timer (14), so the clock never fires and its rows
   equal `ask_once`'s — expected and labeled, not a STOP (challenge #3). 8a freed
   the cost-model marts' `scenario` column for a simulated timer; **8b does not use
   it, because the simulator computes holds, not churn** (challenge Q6). Rejected:
   reusing the cost-model names; a `hold_timer` scenario in `cost_model.SCENARIOS`
   with a churn override derived from hold days (a relationship no source gives);
   the timer amount at the mapped scenario.
5. **Two DDL-only Python-fed marts, one writer, filled inside `rebuild()` after
   the model marts.** `guardrail_sim` (4 × 1,000 rows; the per-claim grain exists
   for the timer's per-claim decision, not a hold distribution) and `sla_threshold`
   (60 rows, no scenario column — the recommendation is made once). Integer and
   boolean columns named as such in the DDL (challenge #10, #11; the
   `cost_curves.is_default` precedent). `write_sim_marts` clears and inserts both
   in one transaction after `write_model_marts`; one read of the fit feeds both.
   Rejected: an aggregates-only mart (no drill-through); a scenario column on
   `sla_threshold` (four recommendations for one decision); folding the print into
   `make model` (one target per stage).
6. **Rounding through 8a's one site; one aggregation site for the summary.** A new
   `days` row (two places, challenge #2) in `_ROUNDING` for the mean hold; every
   other number reuses the existing units. `summarize(rows)` is the one
   aggregation site (mean hold days, timer-released share per scenario); the share
   the timer released under `hold_timer` and `sla_threshold`'s `share_under` at the
   default day are the same count by construction, pinned across the two marts
   (challenge #9). Rejected: a summary mart (a third grain); rounding at the
   printer (a second site); the mean as `count` (loses a day of resolution).

The rule restated as a property (challenge #7): a printed expression and its
callable are one entry in the module that owns the quantity, and the printer
prints from the entry — `cost_model.py::FORMULAS` (the model and the timer
threshold) and `guardrail_sim.py::RULES` (the draw and the hold) are its two
instances (CLAUDE.md → Deterministic first). The `models/` import allowlist
widened by `statistics` and `models`, and the forbidden-name scan gained
`samples` (challenge #8) — `NormalDist().samples` is the one random method the
allowed `statistics` carries, the gap the import allowlist cannot close.

**Gotchas.** `statistics.NormalDist().inv_cdf` carries a C implementation and a
pure-Python fallback of the same algorithm; the 1,000 rounded amounts were
byte-identical locally and under `idempotency-check ROWS=synthetic`, and the
first/middle/last amounts are pinned. DuckDB binds Python `int` into the
`integer` columns (`claim_rank`, `loop_days`, `hold_days`, `timer_days`) and
`bool` into `is_default` with no cast surprise. The two sim marts are each filled
with one `executemany`, guarded by `_no_pandas_probe` (Amendment A1): binding a
Python value, DuckDB imports `pandas` to test its type, and with pandas absent (the
no-pandas rule) and a failed import uncached, the ~4,000-row insert re-scans
`sys.path` on every value — a sub-second write becomes ~5 s, and every test that
rebuilds pays it (measured: the per-row loop ran the suite in ~17 min, the guarded
`executemany` in ~2.5 min). A `None` sentinel in `sys.modules` makes the import
fail at once; it is set only around the insert and restored after, and the repo
uses no DuckDB dataframe API. The defaults' outputs were computed before any pin was
typed: the baseline loop (21 days) is longer than the default timer (14), the
default threshold (€42.67) lands inside the body of the distribution (median cell
€49.76) rather than a tail, and each fix shortens the mean hold — the story holds
without tuning a default.

### Tooling — the implementation loop (2026-09-07, branch `tooling/implementation-loop`)

Not a phase (no spec, no BACKING row). After the Phase 8b merge the developer
asked three things of the build step: comments that say their intent, fewer
findings left for the reviewers to catch, and a loop that keeps a fixed
mistake from being made twice. Three commits, one per piece.

1. **Tagged comments are pointers at records.** Four tags, a closed set:
   `TODO(BACKLOG): <open row title>`, `HACK(DECISIONS): <entry title>`,
   `REF: <URL | brief §n | RFC n>`, `INVARIANT(<spec stem> <n>): <why>`. ruff's
   `TD` and `FIX` rule sets refuse `FIXME`, `XXX` and a `TODO` without its
   parens or colon (configuration over a script: the tool ships the check);
   check-docs check 7 verifies the cited entry exists — an open BACKLOG row by
   title (rows are cited by title, never by number: BACKLOG.md's own rule), a
   DECISIONS bold title or heading, a spec file. Rejected: `TODO(BACKLOG-12)`
   by row number (rows shift, and the file forbids it); a `CONCEPT` tag (the
   Teaching rule lives in the README and docstrings, and an untagged comment
   already says why); a `FIXME` allowed with a link (unfinished code does not
   merge — the spec is the contract). Gotcha: TD003's issue-code regex
   (`[A-Z]+-?\d+`) does not read the parens slot, probed live on ruff 0.16.3,
   so TD003 is off and the record side lives in check-docs; FIX002 and FIX004
   are off for the same reason (TODO and HACK are allowed once they cite).
2. **The pin guard turns the most frequent finding class into a red line.**
   `scripts/check_pins.py`: a public top-level function or class added or
   changed in `<base>...HEAD` under a code package is named in a test — a new
   one, in a test file the same range changed; a new mart file is named in a
   changed test. "Changed" is an `ast.dump` difference (formatting and
   comments do not count). It is the gate's `pins` line (8/8 with a spec, 6/6
   without) and `make check-pins [BASE=main]`. Rejected: a coverage tool (a
   new dependency, and line coverage is not the "one test fails when the rule
   moves" property); a suite test that runs it on the checkout (its verdict
   depends on the branch, so `make test` would go red mid-work and the
   `run-tests` hook would block the very edit that adds the test); the
   working-tree diff (the gate reviews commits). Name-mention is the honest
   ceiling of a mechanical check; the behaviour column of `/preflight` is
   where "named" becomes "asserted". The guard flagged its own branch first
   (four helpers in check_docs with no test naming them), the behaviour it is
   meant to catch.
3. **`LESSONS.md` is the learning loop, with a promotion rule so it stays
   read.** One row per correctness finding class a review round reported; the
   fix commit writes it (CLAUDE.md → Fix commits); `/phase-start` prints the
   `open` rows, `/preflight` asks each of every changed symbol, `code-craft`
   points at it. A class hit twice becomes a mechanism and the row says which;
   a promoted class that recurs reopens the row and reworks the mechanism.
   Check-docs check 8 keeps the class set closed and the status shaped.
   Seeded from the fix commits since Phase 0a: eight classes, all promoted at
   seed time — five were already carried by a standard sentence or a check
   (the guards and error-policy sections, RUF100, the fix-the-class rule),
   `unpinned` by piece 2, and three got their sentence on this branch
   (`caller-sourced` → Function shape, `partial-write` → Error policy,
   `name-drift` → Naming plus a `/preflight` column). Rejected: the session's
   auto-memory as the record (per machine, untracked, invisible to the
   reviewers); a free-text log with no class set (the class is what makes two
   hits countable); a lessons section inside DECISIONS (a record of choices,
   not of misses). Also closed here: the BACKLOG row on `architecture-fit`'s
   shape sentence, which now names `RULES` beside `FORMULAS`.

Round 1 (2026-09-07; code-reviewer, functionality-tester, security-reviewer,
study-editor, coherence-auditor scoped to the changed records): 20 rows, 0
BLOCKER, 5 should-fix; the developer chose to fix all twenty rather than defer
any to BACKLOG. Six correctness commits: check-pins reads both sides from git
(a symlink is its blob; a non-text blob is a refusal), a tag comment is a
comment token the tag opens, a table cell keeps a pipe inside backticks,
check-docs reports a non-text file by name, the ruff tag rules are pinned, CI
runs the pin guard with full history. The `traceback-at-boundary` lesson
recurred inside the very tools that enforce it (a strict `read_text` with no
catch), so under the promotion rule its row was reopened and re-closed with a
second standard sentence: a read is a boundary too. `study/` joined the pin
guard's packages before Phase 9 needs it; the template's LESSONS row applies
to no file by default; `/selfcheck` gained the lesson reminder. Question 3 of
the coherence-auditor (a name-mention guard rather than a behaviour one) is
answered as designed: name-mention is the honest ceiling of a mechanical
check, and `/preflight`'s pinning-test column is where "named" becomes
"asserted".

Round 2 (2026-09-07; code-reviewer, functionality-tester, security-reviewer,
coherence-auditor, scoped to the round-1 fixes): 17 rows, 0 BLOCKER, 3
should-fix. Every correctness row sat in or beside round 1's fix of one
finding — the read boundary — which had been applied at the sites the finding
named (checks 7 and 8, `source_at`) and not to the class: the neutrality check
still read raw, the tokenizer's `IndentationError` is not a `TokenError`,
`ast.parse` also raises `ValueError` and `RecursionError`, the runner's decode
branch had no test. That is the `site-fix` lesson recurring inside the fix of a
`traceback-at-boundary` recurrence, and the first of the two rounds the review
cap counts, so the boundary was re-implemented once against its invariant
rather than patched a second time: every file read and every subprocess under
`scripts/` goes through `review_common.read_text_or_error` / `readable` and
`run`, the parse boundaries are closed sets, and a layout test pins that no
other module reads or spawns on its own — the mechanism `site-fix` lacked (a
prose sentence) is now, for reads, a grep test, and in general a `/selfcheck`
step that pastes the grep over the class's sibling sites. The rest of the round:
a failed test listing is a refusal, a `git show` failure carries the runner's
line, `dags/` joins the pin guard's packages, the symlink test keeps its target
under `tmp_path`, the records' "seven" is six, one "slug" is "stem", the
repo-map CI bullet names check-pins, the merge claim says merge commit (the
LESSONS hash rule depends on it), the challenge standard and `architecture-fit`
list the open LESSONS rows. Rejected: guarding the suite's own tests against a
non-UTF-8 tracked file (a test failing with a traceback is a failing test);
rewriting `docs/PLAN.md` (design history).

Round 3 (2026-09-07; code-reviewer, functionality-tester, security-reviewer,
coherence-auditor, scoped to `f663d20`, `a9fb65d`, `43a1369` — the one
re-review the cap allows): 12 rows, 0 BLOCKER, 4 should-fix, all four round-2
findings confirmed closed, and the developer said "fix all". One commit per
class: the parse-error set is exactly what 3.12 raises (a null byte is a
`SyntaxError` with no line, so the `ValueError` arm was dead; the
`RecursionError` arm now has a 100k-attribute chain that reaches it); a
reader that fails hands back nothing to check against — an unreadable record
had read as empty records and an unreadable Makefile as no targets, each a
fan-out of false lines — which is the class round 2's empty test pool
belonged to, so `empty-default` is the ninth LESSONS class, promoted at once
to a code-craft Error-policy sentence; the `scripts/` layout guard is an
import allowlist rather than a regex of spawner names (`os.popen` slipped
past the old one); the suite's five repository scanners read through
`tests/repo_text.py`, one reader that fails by name; and the craft pair (the
dead `err or …` fallbacks, one `shown()` form for a file's name in every
check). Records: the stale test id in the `traceback-at-boundary` row, the
`ask-gate` reason now says merge commit, `/preflight` lists `dags/`, the
architect's fallback standard names the open LESSONS rows. **Reversed on the
developer's word:** round 2 rejected guarding the suite's own tests against a
non-UTF-8 tracked file; round 3's tester showed the gate's `test` line then
carries five tracebacks — the class the branch exists to close, one directory
over — and the developer chose the fix. The neutrality sweep no longer skips a
file that does not decode: every tracked file is text, so one that is not is a
finding by name.

### Fix — the theme marts carry `run_id` (2026-09-08, branch `fix/theme-marts-run-id`)

Not a phase (no spec; a one-finding fix PR from `main`, CLAUDE.md → Git
workflow). The Phase 9b `/challenge` round (finding 3) found that
`theme_share_by_month` and `theme_share_by_segment` were the only marts without
`run_id`, and that Phase 7a's reason — a scalar cannot be injected into static
SQL — did not apply: `run_id` is a column of `stg_classified_reviews`, already in
the marts' `labeled` CTE's source, so it is selected and carried through
`min()`. One value per build (the classify step stamps the rows input), a
build-level constant, so the grain stays `(month, segment, label)` and the
share is never split by `run_id`.

- **Both theme marts carry `run_id`, carried from the classified rows, not
  injected.** The "still in force" rule holds again for every mart: a displayed
  point can be traced to the run that wrote it. The Phase 9b render reads the
  input the counted rows came from off the mart itself — never off a filename or
  a caller flag — to decide whether a corpus-derived number may be shown (the
  brief's "until real, it's tagged Pending — never faked"). *Rejected: reading
  `stg_classified_reviews.run_id` from the renderer (a study read reaching into
  staging; the marts are the study-ready layer); keeping the 7a entry and
  adding the column in 9b (an earlier phase's SQL changes in its own PR);
  grouping the marts by `run_id` (round 1 `c21caed` replaced it with `min()`:
  grouping made `share` correctness depend on the single-value invariant with
  no test to fail if it broke, and a stray second `run_id` would split the
  grain and understate the share).* Pinned by
  `tests/test_theme_share.py::test_theme_marts_carry_the_run_id_they_were_built_from`,
  `::test_theme_grain_stays_unique_under_a_second_run_id` and the column tuples
  in `tests/pins.py`.

### Phase 9a

Branch `phase-9a-render-contract`, spec `specs/phase-9a-render-contract.md`,
challenged round 1 (approve with amendments, all applied). The first sub-phase
of Phase 9 (the study).

- **Phase 9 is split permanent-artifact-first, not by delivery format in the
  brief's order.** A `/challenge` round on the scoping decision (2026-09-07)
  found that the static HTML export — not Metabase — is the permanent,
  CI-checkable, deterministic artifact the other formats are built on (Phase 0a
  decision 3; brief §4.4), CI is offline (no Docker, so a Metabase-first phase cannot end
  CI-green), and Beat 2's drill-through would ship review text before the
  paraphrase rule is written. So the order is: 9a render contract + Beat 1
  (this) → 9b Beat 2 (the counted `unclassified` series, drill-through
  excerpts) → 9c Beat 3 → 9d Beat 4 → 9e Beat 5 → 9f the README + the stranger
  acceptance test → 9g the Metabase demonstration (developer-run, non-CI). Two
  Phase-9-triggered debts were pulled out of render into their own model/opendata
  phases: the claims sample-mean slider and data.ameli practitioner fees.
  *Rejected: Metabase-first (the brief's listing order) — it inverts the
  permanent-vs-demonstration relationship and has no CI-checkable done-when.
  Rejected: merging the README into the export phase — a prose-only surface
  gives study-editor a clean target and owns the stranger test.*
- **The render contract is data, checked at render time.** A panel is
  `Panel(id, backing_row, tag, kind, series)`; `study/export.py::check_panel`
  refuses, in one line, a panel whose tag is not exactly one of the four
  (no tag, or two), a point whose tag is not one of the four, and a Pending
  panel carrying any value. A Documented/Measured panel whose mart is empty
  renders a labelled "no data yet" state — distinct from a Pending placeholder —
  never a blank or a fabricated number. This is what the long-deferred
  render-time-no-number BACKLOG row asked for; `study-editor` and the
  `coherence-auditor` still read, but the guard is mechanical.
- **`make study` renders from the frozen synthetic database.** Beat 1's
  Documented points are the anchors only under `ROWS=synthetic` (the manual and
  fetched snapshot files load only under `captured`), so the committed
  `study/friction_ledger.html` cannot drift with the weekly cron. *Rejected:
  rendering from `captured` — the baseline would change on every weekly run and
  the byte-check would be unmaintainable.*
- **Charts are hand-written inline SVG with byte-stable, locale-independent
  formatting** (fixed 2-decimal coordinates through `_n`, sorted attributes, no
  render timestamp), so two renders — and two locales — produce identical bytes.
  `make study` is added to CI, which renders and `git diff --exit-code`s the
  committed baseline. *Rejected: a chart library — a CDN or build step, breaking
  self-containment and determinism.*
- **The palette is the dataviz reference default ("Ledger"),** chosen from four
  directions at build start (all built on the validated categorical set, so all
  colorblind-safe); it lives in one place `export.py` reads and every later
  render phase inherits it. Chart types were named in the spec; the palette was
  the build-time choice.
- **The excerpt/paraphrase rule is authored here as a contract** (the one render
  path for review text: paraphrase, at most one short marked phrase, always the
  public source — brief §2.5), but Beat 1 ships no review text (B1.1 is
  Pending), so its enforcing test and the first text-drill surface land in 9b.
  The "Health details arrive in review bodies" BACKLOG row stays open,
  re-scoped to 9b, not struck. *Superseded in 9b (exit round): the export has no
  render path for review text at all — the column allowlist and the recording
  connection (`tests/test_beat2.py::test_every_export_query_projects_only_allowlisted_columns`,
  `::test_every_query_the_export_runs_is_a_listed_study_query`) are the
  enforcing tests, and the review-level drill is the Metabase demonstration
  (9g); the paraphrase rule governs that surface and B2.1's documented
  examples when they land.*

Challenge dispositions: the scoping round returned *rework* (the split instinct
right, the order and cut wrong) — the reorder, the excerpt-policy-first rule,
the debt-assignment pass and the up-front render contract were all accepted. The
spec round returned *approve with amendments* (0 BLOCKER, 6 should-fix) — all
applied before the stamp: the frozen-synthetic render input pinned, `make study`
added to CI, the SVG byte-formatting rule pinned, invariant 3 split (the counted
`unclassified` series deferred to 9b), Done-when 4 re-scoped to
Measured/Documented/Pending, the empty-Documented-mart state specified, and the
BACKLOG rows cited by title.

### Phase 9b

Branch `phase-9b-beat-2`, spec `specs/phase-9b-beat-2.md`, challenged round 1
(rework, all twelve findings applied). Beat 2 of the study. Depends on the fix
PR `fix/theme-marts-run-id` (the two theme marts carry `run_id`), merged first.

- **The corpus gate: a number that derives from the review corpus renders only
  over a `captured` input, read from the mart's own `run_id`.** The brief says
  three times a share over fake reviews is never shown as a number (§3 Beat 2,
  §10, §2.4), and the committed page renders over the frozen synthetic fixture.
  So B2.2/B2.4/B2.5 read the classified rows' `run_id` against the imported
  `pipeline.build.INPUTS`: `captured` renders the counted numbers, a fixture
  input (`synthetic`, `samples`) renders a labelled fixture state and no number,
  an absent or empty mart renders 9a's "no data yet". Two run_ids, or one outside
  the set, refuse in one line naming the panel. The input is the mart's own row,
  never the DB filename or a caller flag. A captured render is a local,
  developer-run `write(db=…)`, never committed in 9b (whether the published page
  is such a render is 9f's call — BACKLOG). *Rejected: a sentence beside a
  Measured fixture number — the brief forbids the number, not the sentence;
  deriving the input from the filename — caller-sourced (LESSONS).*
- **The export's trail is the mart's `reviews`/`theme_rows` beside each share,
  plus the structural no-text guarantee; the review-level drill is the Metabase
  demonstration (9g).** No declared source yields a per-review public address
  (every parser stores the brand-carrying page address — D1), so a row-per-review
  list could be neither traced nor published, and each row's rating would be an
  untagged number with no mart row. The counts ride on each point (redone by
  hand). *Rejected: the per-review link list (challenge BLOCKER 2); a rule token
  as the "one short marked phrase" — that re-runs the rules over text inside the
  renderer.*
- **The no-text guarantee is a column allowlist checked on the cursor's
  description, not a denylist on query text.** One closed `ALLOWED_COLUMNS` the
  export may read; `_rows` reads each cursor's own description and refuses any
  other column by name, so `select *` cannot pass and `title`/`body` can never
  reach the page. `STUDY_QUERIES` is every query the export runs, each linted for
  portability and the clock by a test. *Rejected: grepping query text for
  `title`/`body` — a denylist, the `unshaped-input` class; a four-word-run scan
  — near vacuous against French bodies and English page prose.* This closes the
  "Health details arrive in review bodies" BACKLOG row.
- **The `unclassified` band is the palette's neutral token, always in the legend
  with its count; the series colour is a closed choice on the type.** A
  `Series.colour` is a categorical slot `0..4` or the `NEUTRAL` token, refused by
  name outside it (never a sentinel integer reaching an undefined `var(--sN)`).
  The band is emitted even when empty, its legend name carrying its total count,
  so a small or absent band reads as zero, never as hidden. `positive` is
  excluded from the theme bars (a theme chart counts complaints) and the
  denominator — every classified review, `positive` included — is stated beside
  the chart; SPEC and BACKING's "negative reviews" wording is corrected to the
  mart's denominator. *Rejected: a sixth categorical hue (the five-slot order is
  the CVD-safety mechanism); a stacked area (draws a cumulative number no mart
  holds).*
- **A metric cell is a value xor a declared absence.** `Point.absent` carries the
  labelled reason a cell has no value; `check_panel` refuses both set and refuses
  a null cell with neither (9a's null-cell refusal, extended). B2.4's table sets
  the absence exactly when the held-out denominator is zero ("no held-out case")
  and carries the integer count; the `table` kind dispatches on "any cell
  present", so a table of absences renders as a table, not "no data yet".
  *Rejected: rendering 0.0; a dash; a second optional field with no refusal.*
- **The module split has one direction: `model.py` ← `panels.py` ← `export.py`,
  moved verbatim in its own commit.** `model.py` the types and the contract,
  `panels.py` the readers plus the allowlist and the corpus gate, `export.py` the
  renderers and the page. The move is a separate commit so the diff shows the
  rename and `check-pins` sees the moved symbols named in the changed tests.
  *Rejected: builders importing from `export` (a cycle); one 1,100-line file.*

Gotcha: `rebuild()` builds the generic and model/simulator marts but NOT the
classify step (the theme marts B2.2/B2.5 and the filling of classifier_quality
B2.4) — that is `build.classify_step` (the CLI's `_do_rebuild` → `_classify_and_print`
wraps it; fix/idempotency-classify moved the step there). So a test that
needs the Beat 2 marts must run the classify step too; `tests/conftest.py::
build_study_db` does (rebuild + `classify_step` with `decide=None` and its cache
in a temp path, so it is rules-only, deterministic, and writes nothing under
`data/`). A corpus panel over `ROWS=none` (no reviews, no classify)
finds the theme marts absent, not empty, so the gate probes
`information_schema.tables` and renders "no data yet".

Challenge dispositions (round 1, 2026-09-08 — rework, all applied): BLOCKER 1
(fixture shares under Measured) → the corpus gate. BLOCKER 2 (the per-review
list) → the list dropped, the trail is counts. #3 (`run_id` on the theme marts)
→ the fix PR this branch depends on. #4 (`positive`; "negative reviews") → the
neutral-band decision and the two claim-cell fixes. #5 (allowlist not denylist)
→ the column allowlist. #6 (value xor absence) → `Point.absent`. #7–#9 (module
direction, lint the study queries, closed series colour) folded in. #10–#12
(security-reviewer not triggered; a captured render is local and uncommitted;
the band's legend entry with its count) answered in the spec.

Review round 1 (2026-09-08; code-reviewer, functionality-tester, study-editor):
no BLOCKER; fixed in full — the corpus chart kind and the `ROWS=none` render
pinned (`013ebf6`), dead `axis_unit` dropped, the fixture note corrected, two
findings deferred to the rows that own them (`b7a35ff`), and one fix
amendment: a panel's notes are a sequence (`ce405cc`, `3c97ceb`). Round 2
(2026-09-08; the same three agents, the security-reviewer and
coherence-auditor not triggered): 11 rows, 0 BLOCKER, 5 should-fix,
functionality-tester "partially" on one surviving mutation. No correctness
row sat inside a round-1 fix (the cap did not fire); three sat on `900692c`
code round 1 had passed over: the neutral-token render mapping was pinned by
a page-scoped assertion the fixture CSS satisfied (`1b21215`, test-only), the
legend vanished for a band-only panel against invariant 3 (`cee1d1a`), and the
Beat 2 readers wrote the point tag as a literal instead of the mart's column
(`505a5cf`, the `caller-sourced` class). B2.5 got its own denominator and
self-selection notes — the round-1 amendment had reused B2.2's line-chart
wording on a bar chart — and the fixture label lost its mechanism words
(`0d73ffc`). The study-editor's B2.5 rewrite named document-loop alone; the
chart draws every theme per segment, so the note says "each theme's share".

Challenge round 2 (2026-09-08, on the spec as amended, after review round 2):
*approve with amendments* — 0 BLOCKER, 5 should-fix, 2 suggestion, 2
question; the developer chose to fix all. The shared shape: the Invariants
table named tests whose scenario was narrower than the for-all. Applied: the
catalog probe filters on `warehouse.default_schema` (#9, `4e106c4`);
invariant 5 is pinned on a recording connection — every query a render runs
is a listed study query or one of the two catalog reads, so a reader that
bypasses `_rows` fails by name (#1, `ff65c21`); the two remaining page-scoped
assertions assert on their panel (#4, `7912825`, a `site-fix` instance); the
self-selection caveat is derived for every Measured panel whose sources are
the platform roots, not authored per id (#3, `a5f924e`); the CLI's binding of
`database_for(rows)` to `run_id = rows` is pinned with every writer patched
out (#6, `af2c015`); the gate's input-to-state mapping is one closed dict
whose key set a test pins to `INPUTS` (#8, `b6fab49`). Recorded: BACKLOG row
"`make idempotency-check` skips the classify step" re-pointed (#5 — the target
is `pipeline/build.py`, an earlier phase, so a `fix/` PR at 9f or Phase 10);
the tooltip-only trail as a BACKLOG row for 9f's stranger test (#7 — a visible
denominator needs a `Point` field, a design change 9f owns). #2 — `check_panel`
does not refuse a fixture-state panel that also carries content — is a
contract extension: a fix amendment, written alone and stamped, implemented
on approval. *Rejected for #7: parsing the denominator back out of the
formatted `detail` string — a string round-trip where a field belongs.*

Exit round (2026-09-08; code-reviewer, functionality-tester "works", study-
editor, coherence-auditor over the whole repo): 23 rows, 0 BLOCKER, 10
should-fix; fixed in full. Correctness: B2.5 drew every theme where SPEC and
BACKING claim the held-claim share per segment — `_theme_series` now takes a
closed `themes` set and labels B2.5's points by segment through a closed
`_SEGMENT_NAMES` lookup over ingest's `SEGMENTS`, so a traditional source is a
second bar per series with no render change (`eb79c13`, `unpinned`); the
footer's brief §6 citation hung on "any URL present" and is now derived from
the Documented points shown (`a3822f3`, `caller-sourced`); a panel-level
source the drill could not shape fell to "source pending" — now an http(s)
address, a repository file in plain text, or a refusal by name, and B2.4 names
the answer key (`92e29e6`, `empty-default`; the same shape carries 9c's Open
DAMIR fit); three pins — the point tag against a non-Measured row, the probe's
schema filter, the catalog reads through the SQL lint (`5c3b17b`, `b157daa`,
`26264cc`). B2.2 carries the one-segment caveat and row 51 names its segment
filter as the remaining render change (`7f3a78f`). Wording: "switched off"
for "no key", the trail as a tooltip, the brief's Beat 2 line (`82ec471`).
Records: the 9a excerpt-contract bullet superseded above; B1.2 keeps 9a's soft
profile lookup while B2.3's reader refuses (kept deliberately in `9bb76bb` —
a Beat 1 semantics change is out of 9b's scope); the Invariants' falsifier
column extended with the round-2 and challenge-round tests and the round-2
stamp re-hashed (the invariants themselves unchanged); BACKLOG row 69 loses
its B2.4-drill sentence, row 71 gains the `site-fix` reminder and the PLAN §5
split for the next `tooling/` branch. The auditor's four questions, answered:
(1) the three-layer split holds — `_corpus_series` returning `(series,
fixture_text)` is the builder's contract and `check_panel`'s fixture refusal
is the render contract's; two checks, one property, kept; (2) `panels.py` at
~800 lines holds readers, display names, the allowlist, the gate and the note
texts — 9c splits the note texts and display tables into `study/text.py` if it
grows further, not before; (3) the corpus gate stands — a Measured chip beside
"not a result" is honest (the claim is Measured, the input is not real), and
publishing a captured render is 9f's decision with its own Threat-model row
(row 69); (4) "source pending" was the assumption 9c would break — the
repository-file source now carries a Modeled panel's fit file and address.

### Fix — `cost_model_outputs` carries the formula's unit (2026-09-09, branch `fix/cost-outputs-unit`)

Not a phase (no spec; a one-finding fix PR from `main`, CLAUDE.md → Git
workflow). The Phase 9c `/challenge` round (findings 7 and 10, and the spec's
pinned decision 5) found that `cost_model_outputs` stores each formula's value
with no unit, so the study could print "1318719.82" but not a euro figure, and
that the unit lived in a private map beside `FORMULAS` (`_OUTPUT_UNIT`), covering
the twelve point formulas only and named in no test — the parallel-map shape
that lets a name and its unit drift apart (`name-drift`). A mart-shape change in
an 8a file is its own PR before the 9c branch builds (the `run_id` fix's
precedent).

- **The unit is a field of the `Formula` entry, and the mart stores it.**
  `Formula(name, expression, kind, unit, fn)`; `_run_points` rounds by `f.unit`;
  the two curve formulas carry `rate` (their value is a flag rate); the private
  map is gone. `cost_model_outputs` gains `unit varchar`, written from the entry
  by `_insert_output`; a NULL crossover still carries `rate`. `make model`
  prints the unit beside each value (`-> 1318719.82 (eur)`), so the terminal,
  the mart and the page format one number one way; the header's reader rule is
  corrected to what 9c renders (B3.1 the baseline scenario's fourteen rows,
  point and curve; B4.1 the toggled scenarios'; B4.2 the three hold-timer rows
  at baseline). *Rejected: a second public dict parallel to `FORMULAS` (the
  same shape, only public); a unit map keyed on formula names in the study (a
  second copy across a layer); free-text units as the params mart has (a
  parameter's unit is prose for a person; an output's unit selects a number
  format).* Pinned by
  `tests/test_cost_model.py::test_every_formula_carries_a_rounding_unit`
  (every entry's unit is a `_ROUNDING` key and equals `pins.COST_FORMULA_UNITS`;
  the field is required), `::test_make_model_prints_the_unit_beside_each_value`,
  and `tests/test_model_marts.py::test_outputs_mart_carries_each_formulas_unit`
  (every row's unit equals its entry's, the NULL case included).
- **The unit names the dimension the number is read in, not a format bucket.**
  Once printed beside the value, `loop_days -> 21 (count)` misstated a day
  count (review round 1, code-reviewer #2); `loop_days` now carries `days`
  (two places, the rounding table's own row — its value 21.0 unchanged, the
  pins retyped from the built output, `ebcc556`). `friction_per_day` stays
  `eur`: the unit is the currency the number is quoted in, and the entry's
  name carries "per day", as 9c's display name will. *Rejected: printing no
  unit (the terminal and the mart would disagree with the page); a display
  unit distinct from the rounding unit (two fields for one fact).* The
  study-format leg of the invariant — the page formats each value by this
  column — is pinned in 9c when the reader lands (`tests/test_beat3.py`),
  not here (code-reviewer #6). The mart header's reader rule names B3.2's
  markers and leaves the toggled scenarios' rows to `make model` and the
  dashboard until a BACKING row reads them (B4.1's mart of record is
  `cost_curves`; #1). Round 1: code-reviewer 6 findings (2 should-fix),
  functionality-tester "works", every hand-mutation caught, one display pin
  added (`7a2ea22`).

### Phase 9c

Branch `phase-9c-beat-3`, spec `specs/phase-9c-beat-3.md`, challenged round 1
(approve with amendments, all sixteen applied). Beat 3 of the study — the first
Modeled panels. Depends on Phase 9b (PR #23) and the fix PR
`fix/cost-outputs-unit` (PR #24: `Formula.unit`, the outputs mart's `unit`
column), both merged first.

- **The brief's "slider" is met by a drawn range plus a recorded trigger; the
  permanent page carries no script.** Each parameter row draws low — default —
  high as inline SVG from the mart's three cells, the default in its display
  unit beside the mart's prose unit; a sourced row carries its citation as
  escaped text and an unsourced row the label "declared unsourced — explore the
  range", the two styled by a closed class lookup on the mart's `sourcing`
  word. Because the formula is printed beside the range, a reader redoes the
  arithmetic at any point of it by hand — that is the exploration the
  permanent artifact offers. Whether the published page may carry an inline,
  CDN-free script that recomputes `FORMULAS` is 9f's decision (BACKLOG *Live
  sliders need a script the permanent page does not carry*). BACKING B3.4's
  claim cell and SPEC.md's two "slider" phrases were amended to what ships.
  *Rejected: an inline `<script>` recomputing the formulas (a second copy of
  `FORMULAS` in a second language that no test pins against the module); an
  `<input type="range">` with no script (a control that does nothing reads as
  broken).*
- **B3.1 renders the baseline scenario; the scenario is checked against the
  imported `SCENARIOS`; the three toggled scenarios are Beat 4's (9d).** Each
  model mart is read whole and the scenario picked in Python
  (`_scenario_rows`), so no filter value is a literal in the SQL; B3.3's three
  headline figures (`customer_value`, `mean_claim`, `claims` — the rows
  BACKING assigns to it) come through the same reader at the baseline, above
  its parameter rows (`Panel.headline`). 9d's B4.1 reuses `_formula_rows`,
  `_curve_series` and `_curve_markers` with `contacts_once`. *Rejected: four
  formula lists in Beat 3 (Beat 4's story told early); a `where scenario =
  'baseline'` literal (caller-sourced).*
- **Three closed additions to `Kind` — `formulas`, `curve`, `parameters` — and
  two to `Unit` — `eur`, `logeur`; the curve's markers are `(label, x)` pairs
  the contract checks.** A `formulas` panel is one `Series` per entry (the
  display name, the mart's identifier as `Series.key`, one cell whose label is
  the expression); a `curve` panel is series over one numeric x axis with
  `Panel.markers` drawn as labelled vertical rules in tuple order, each label
  one `_MARKER_DY` lower by its index, so the baseline's two rules at 0.05
  read as stacked labels; a `parameters` panel is one `Series` per parameter
  (three cells: low, default, high; `Series.sourcing` the closed style key).
  `check_panel` refuses a marker on a non-curve panel and a marker whose x is
  not the label of a point the panel draws (`x_key`, three places — the grid
  step is 0.005), so a marker between grid points cannot render. The y domain
  is a layout number by one pure rule (`curve_domain`: 0 to the maximum
  rounded up to one significant figure; 4,530,293.45 → 5,000,000) and the
  ticks are euros through `display`, never `{:g}`. Palette inherited; the
  markers and range marks use the ink and muted chrome tokens, never a series
  slot. *Rejected: reusing `table` for the formulas (its cells are metric cells
  with counts); reusing `line` for the curve (no markers, no numeric ticks);
  one generic kind with a mode flag; a fixed euro domain.*
- **The markers and the note's figures are read from `cost_model_outputs`,
  never found by scanning the curve.** The "you are here" rule is the
  `is_default` row's flag rate (exactly one, else refuse); the two crossover
  rules are the `crossover_flag_rate` and `marginal_crossover_flag_rate` rows,
  each drawn only when the mart stores a value; the note beneath the chart is
  `text.crossover_note` filled from those rules and says "never cross" when a
  row is NULL. A test changes every baseline `net` cell to −1 and the page
  does not move — `net` is read by no panel. *Rejected: computing the crossing
  from the two polylines; typing the crossover into the note.*
- **`display` is the `Unit` set's runtime guard and lives in `study/model.py`
  beside the set.** 9a kept it private in `export.py`; the note templates need
  the same percent format for a figure the reader (not the renderer) fills,
  and the direction {`text.py`, `model.py`} ← `panels.py` ← `export.py` (text
  and model are independent leaves) forbids
  panels importing export. One formatter, one place; `export.py` and the tests
  import it. *Rejected: a second percent formatter in `text.py` (a duplicate);
  filling the note in the renderer (a note is data on the panel).*
- **The display texts are data in `study/text.py`, the maps closed and
  ordered.** `FORMULA_NAMES` (14) and `PARAMETER_NAMES` (15, each `(display
  name, Unit)`) are keyed by the mart's own name; a row the map does not know,
  or a map name with no row, refuses by name, so the module, the mart and the
  page are 1:1 in both directions (pinned at the page by
  `tests/test_beat3.py::test_every_rendered_expression_equals_the_formulas_entry_of_that_name`).
  Formula rows render in `FORMULAS` order by iterating the imported tuple;
  parameter rows in the display map's order, which a test pins equal to
  `parameters(read_model_fit())` — the static `PARAMETERS` tuple lacks the
  three fit rows, so the map is the one ordered list the reader can iterate
  without a fit. The Beat 1–2 note constants moved verbatim in their own
  commit (`3ee1468`); the Beat 1–2 display maps (`_PROFILE_NAMES`,
  `_LABEL_NAMES`, `_SEGMENT_NAMES`, `_STAT_LABELS`) stay in `panels.py` — the
  9b exit record asked for the note texts and the *new* display tables, and
  moving four working maps is churn with no invariant behind it. *Rejected: a
  soft `.get(name, name)` (the empty-default class); alphabetical rows.*
- **Two small fields the spec did not name: `Series.key` and
  `Series.sourcing`; one on `Panel`: `headline`.** A formula or parameter row
  needs its mart identifier beside its display name (so the page matches
  `make model` and the identity test maps a rendered row back to `FORMULAS`),
  and a parameter row needs its sourcing word for the closed class lookup; the
  spec's `Point` fields (label, value, tag, unit, absent, detail) cannot carry
  either without positional meaning across the three cells. `Panel.headline`
  holds B3.3's derived figures as formula rows above the parameter rows;
  `_points` walks headline and series alike, so the contract (tags, value xor
  absence) covers both. *Rejected: encoding the identifier in a cell's
  `detail` and the sourcing in another cell's (a tuple with positional
  meaning); deriving sourcing from "detail equals the unsourced label" (a
  text-equality arm, not the column).* Reported for review round 1.

Challenge dispositions are recorded in the spec (round 1, 2026-09-09, approve
with amendments). Supersedes nothing.

### Phase 9d

Branch `phase-9d-beat-4`, spec `specs/phase-9d-beat-4.md`, challenged round 1
(rework scoped to B4.1, all amendments applied; spec `50966c34`). Beat 4 of the
study — the three fixes, drawn beside the Beat 3 curves. Depends on Phase 9c
(PR #25) and the fix PR `fix/drill-footer-verb` (PR #26), both merged first. The
Beat 4 marts already existed from Phase 8b; this phase renders them.

- **The toggled scenarios are drawn beside the baseline, not toggled by a
  control.** The permanent page carries no script (9a/9b/9c), so B4.1 draws the
  net curve for the baseline and all three toggled scenarios as four static
  lines a reader compares by eye; the live-control decision stays Phase 9f's
  (BACKLOG *Live sliders need a script the permanent page does not carry*).
  *Rejected: an inline recompute script (the permanent artifact carries none); a
  control that does nothing (reads as broken).*
- **B4.1 draws the net per scenario (four lines), keyed on `scenario`, within
  the five-slot palette — it does not reuse `_curve_series` with
  `contacts_once`.** This supersedes the Phase 9c entry's forward note ("9d's
  B4.1 reuses `_formula_rows`, `_curve_series` and `_curve_markers` with
  `contacts_once`"): the challenge chose all three toggled scenarios (SPEC
  B3.1/B3.2 assign them to B4.1), and three scenarios × the two curves (fraud +
  friction) is six-plus series against a palette of five (`_series_var` refuses
  slot 5, a CVD-validated cap). One net line per scenario is four series ≤ 5 and
  shows exactly what the fixes move (fraud caught is unchanged). A new reader
  `_net_curves` and a signed `net_domain` (the net dips below zero — the
  crossover; `curve_domain`'s 0-floor would clip it), the significant-figure
  rule factored into `_sig_ceil` and shared. *Rejected: `contacts_once` alone
  (SPEC assigns three); fraud + friction per scenario (exceeds the palette);
  small multiples (a layout the contract does not have, and past the ≤6 cap).*
- **B4.2 is a `stat_row`, not a `curve` (build-time finding, amendment committed
  alone).** The `curve` kind hardwires its x-axis to a flag-rate percent
  (`study/export.py`), so `timer_days` would mislabel. B4.2 shows the three
  cells of `sla_threshold`'s `is_default` row (the timer day, the net-negative
  amount, the share under it) with the arithmetic in the note. *Rejected: B4.2
  as a curve (mislabelled x-axis); the 60-row threshold grid (`make simulate`
  prints it — the page shows the computed answer); extending the curve x-axis
  unit (render-contract surface a stat row does not need).*
- **B4.3 aggregates `guardrail_sim` in one ANSI SQL group-by, pinned to
  `summarize`.** `panels._hold_summary` reads mean hold days (`avg`) and the
  timer-released share (`sum(case when outcome = 'timer_released' …)/count(*)` —
  the portable conditional count, not `filter`), rounded at the model's one site
  (`rounded`); `tests/test_beat4.py::test_b43_sql_aggregate_equals_summarize`
  pins it equal to `models/guardrail_sim.py::summarize` on all four scenarios,
  closing the Phase 8b BACKLOG row that named exactly this test. The released
  share renders as a note figure (only the clock releases claims); B4.3 draws
  one bar per scenario (the shared no-fix baseline and each fix beside it —
  round 1 #15 dropped the before/after pairs that repeated the baseline in three
  colours). *Rejected: a Python reduction in the reader (a SQL aggregate is the
  shape the BACKLOG row named, and keeps the mart the one source); `filter
  (where …)` (not portable to Snowflake).*
- **B4.4 stays Pending — a design panel, no number.** The false-positive rate it
  would show needs an outcome log that does not exist; `check_panel` refuses a
  value on a Pending panel. *Rejected: inventing a placeholder number (the
  provenance contract — never faked).*

Challenge dispositions are recorded in the spec (round 1, 2026-09-09, rework
scoped to B4.1). Supersedes the Phase 9c forward note on B4.1's readers (above).

### Phase 9e

Beat 5 — the checkable facts and the reproducibility counts — renders through the
9a/9c contract (no new chart `Kind`, no `make` target, no dependency), adding two
single-grain Python-fed marts.

- **Two marts, two homes, by what the number is about.** `determinism_facts`
  (B5.1) is filled in `rebuild()` beside the model/simulator marts — keyless, on
  every input including `none`, covered by `idempotency-check` — and is **not**
  corpus-gated, because a repo fact is constant whatever data is loaded, so the
  committed synthetic page shows the numbers. `pipeline_row_counts` (B5.2) is
  filled in the CLI classify path (after `stg_classified_reviews` exists, so the
  classified stage is counted) and **is** corpus-gated like Beat 2 (the fixture
  note over the frozen synthetic input). *Rejected: one mart for both (they
  differ in gate and fill site); filling B5.2 in `rebuild()` (the classified
  stage is not built yet there).*
- **B5.1 facts are build-time counts of the code, each bound to its guard.** The
  model-decision count is the length of `pipeline/build.py::model_call_sites`, the
  same import-tree walk `tests/test_llm.py::test_only_llm_imports_anthropic` now
  reads (shared, so the fact cannot drift from a literal); the formula count is
  `len(models/cost_model.py::FORMULAS)`, bound by a test to the formulas B3.1
  renders (defined == displayed); the tag count is `len(study/model.py::TAGS)` (a
  leaf import, no cycle). All Measured — measured facts about the repository,
  whose upstream source (BACKING) is the code they are counted from. *Rejected: a
  prose panel with no numbers (SPEC B5.1's tag is Measured); a bare literal `1`
  (the challenge showed it carried a "cannot drift" claim no constant backs).*
- **B5.2 renders the stage counts; eval scores are B2.4, referenced not copied;
  the rebuild command is prose.** The mart is single-grain (one row per review
  stage — as scraped, deduped, classified). *Rejected: a second eval table (one
  system, no duplication); a live "Day N" counter (writing rules).*
- **`pipeline/metrics.py` deleted, its `reviews_per_month` query relocated to
  `pipeline/build.py`, not martified.** The challenge (#6) settled that folding it
  into `pipeline_row_counts` would make that mart two-grain, and that a query is
  not an orphan (the rule bites marts only). Closes the Phase 2 BACKLOG row.
  *Rejected: fold into the mart (two-grain, half-unrendered); a new
  `reviews_by_month` mart (a third mart plus a BACKING row for a non-study
  number).*
- **Idempotency of a classify-path mart.** `pipeline_row_counts` is outside
  `make idempotency-check` (which runs `rebuild()` only), like the theme marts, so
  `tests/test_beat5.py::test_pipeline_row_counts_stable_across_reclassify` proves
  its stability; BACKLOG line 52 grows to name it. *Rejected: moving the fill into
  `rebuild()` (the classified stage does not exist there).*

Gotcha (build-time): the one-call-site walk reads every non-test `.py`, so the
literal string `import <sdk>` in a non-test module would count that module and
break `test_only_llm_imports_anthropic`; the needle is built from `_MODEL_CLIENT`
via an f-string, never spelled, so `pipeline/build.py` is not a false match.

Challenge dispositions are recorded in the spec (round 1, 2026-09-10, rework, all
amendments applied). Supersedes the Phase 9d forward note on the classify-path
idempotency class (extended to `pipeline_row_counts`).

### Phase 9f

The README — the third delivery format, telling the five beats in prose — and the
stranger acceptance test that pins the walk from any figure to its BACKING row. No
new dependency, `make` target, mart, chart `Kind` or BACKING row; the committed
page does not change.

- **The permanent artifact stays the byte-checked synthetic render; a captured
  render is the reader's own `make rebuild ROWS=captured && make study`.** The
  committed page is deterministic and CI byte-checks it (9a); a captured render
  would carry corpus state that drifts with the weekly cron and could not be
  byte-checked. This answers the two questions the 9b decision deferred: the
  shipped page carries no per-review address (brand-address), and page size is
  moot since the page is unchanged. No Threat-model row — 9f ships no captured
  render. Closes the "corpus render" BACKLOG row. *Rejected: shipping a captured
  render as the permanent artifact (breaks the byte-check, ships drifting corpus
  state); a second committed captured page beside the synthetic one (two baselines
  to maintain, a brand-address surface with no source that yields a per-review
  address).*
- **The permanent page carries no live slider; live exploration is the Metabase
  demonstration (9g).** Beat 3 already draws each parameter's range as a static
  mark with the formula printed, so a reader redoes the arithmetic by hand. A
  browser control recomputing `FORMULAS` is an inline script — a second copy of
  the formulas in a second language needing its own module↔script identity test —
  and breaks the self-contained, byte-stable artifact (9a/9c). Pinned by the
  existing `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp`;
  the "live sliders" BACKLOG row closes at 9g. *Rejected: an inline CDN-free
  `FORMULAS` recompute (a second formula surface and a page that is no longer
  byte-stable).*
- **The stranger test is a pytest over the README text, not a `check_docs`
  check.** `check_docs` is for structural docs guards (links, banned words,
  glossary, naming) and already scans the README; a content pin — a figure carries
  its tag and its own resolving `B<beat>.<n>` — is a test, in
  `tests/test_readme.py`. The tag check matches only unambiguous shapes (`€`, `%`)
  with no date/version denylist (the `unshaped-input` class); the three Beat 5
  counts sit on fixed template lines the test asserts by shape. *Rejected:
  extending `scripts/check_docs.py` (duplicates link/naming coverage, puts a
  content pin in a structural guard); a "multi-digit count minus dates/versions"
  regex (the denylist is the trap).*
- **The README's figures are the Modeled (Beat 3–4) and the Measured checkable
  facts (Beat 5), not restated Beat 1–2 corpus numbers.** Beat 3–4 read the DAMIR
  fit and fixed parameters, so their euros are corpus-independent and honest on the
  synthetic page; Beat 1–2's counts are described qualitatively with the
  `ROWS=captured` rebuild named, so the shipped synthetic figures are never
  presented as findings. Beat 1's hero stays Pending (no number). *Rejected:
  restating synthetic theme shares as findings (dishonest under the synthetic
  render); a full numeric recap (every restated value a pin that drifts from the
  mart).*

Build amendment (2026-09-10): the challenge-round "Beat 1 Day N" clause was
dropped — BACKING B1.1 is Pending, so the hero shows no number; Invariant 1 and
the tag-template test cover Beat 5's counts only. Restores: a Pending claim shows
no number.

Challenge dispositions are recorded in the spec (round 1, 2026-09-10, approve with
amendments — 5 should-fix and 2 suggestions applied).

Exit reconciliation (2026-09-10, coherence-auditor): the study now ships **one
glossary per delivery surface** — the README's ten reader terms (the four tags,
"Held claim", "Theme share", "The gated classifier", "The crossover", …) and
SPEC.md's chart terms ("Mart", "Provenance", "Eval set", …) — where the brief and
CLAUDE.md's writing rule had said "one glossary". The two are content-coherent (no
definition contradicts the other's) and serve distinct audiences: a stranger
reading the README should not have to open SPEC.md to learn a term. The rule text
in PROJECT_BRIEF §2.3 and CLAUDE.md → Writing rules was amended to "one glossary
per delivery surface, ≤10 terms each"; `make check-docs` already enforces the ≤10
per file. *Rejected: consolidating to a single canonical glossary — it costs the
stranger-facing README its self-contained glossary, against the "reads the README
first" goal.*

### Phase 9g

Branch `phase-9g-metabase`, spec `specs/phase-9g-metabase.md`, challenged round 1
(rework — 2 BLOCKER, 4 should-fix; all applied) then round 2 (approve with
amendments — 1 BLOCKER, 3 should-fix, 1 question; all applied). The Metabase
demonstration: the review-level drill over the reader's own rebuild, the last
Phase 9 sub-phase. Non-CI (CI has no Docker): an offline core CI runs (the
applier's dry-run request bodies, the drill view's + SQLite export's column
allowlist) plus a developer-run live run with synthetic-only screenshots.

- **A recorded deviation from brief §90: the drill's audit trail is counted rows
  plus a sourced theme paraphrase, not per-review excerpts.** §90 as written asks
  the drill to reach "the underlying review excerpts." That is unattainable under
  two contracts already in force: no declared source yields a per-review public
  address (D1 — every parser stores the brand-carrying page address, not a
  per-review URL), and Neutrality/personal data forbids publishing a review's own
  `body` (brief §5 bodies name conditions). So the drill shows per-review rows on
  a non-text allowlist plus, per theme, one Documented paraphrase (B2.1). The
  BACKLOG row *"A per-review drill needs a per-review public address"* stays
  **open, re-deferred**, carrying the surviving reopen trigger: *revisit if a
  source yields a per-review public address*, which external per-review citation
  would need. *Rejected: a truncated `body` snippet as the "one short marked
  phrase" — raw text carries a name/condition and has no per-review public source;
  a machine-generated paraphrase — the model is called from one site
  (`classify/llm.py`), never for prose.*
- **The drill's non-text allowlist holds across the join, and its honesty comes
  from the synthetic input plus a caption, not a corpus gate.** `review_drill`
  joins `stg_classified_reviews` to `stg_reviews` (which carries `body`/`title`),
  so the allowlist (`review_id, theme, rating, review_date, segment, source`) is
  the guard, checked on the joined cursor's description and again in the export
  (`FORBIDDEN_COLUMNS`). The 9b render-time corpus gate lives in `study/panels.py`,
  **not** in the marts Metabase reads — so over `ROWS=synthetic` Metabase shows
  real counts of hand-written fake reviews; the demonstration earns its honesty
  from the synthetic input (only fake reviews exist) and the *synthetic fixture
  data — not a study finding* caption, never from a gate it does not inherit
  (round-2 BLOCKER). `review_id` is the computed `source || ':' || external_id`,
  the one definition in `classify/labels.py::review_id`.
- **Metabase reads a stdlib-`sqlite3` export of the marts through its built-in
  SQLite driver — no DuckDB community driver.** SQLite is an official Metabase
  driver (self-hosted); DuckDB is community-only (a third-party JAR — the "ask
  before ANY package" instinct — whose auto-download of the DuckDB SQLite
  extension would break the offline rebuild). The export is stdlib, offline and
  deterministic: a fixed mart set, ordered rows, DuckDB decimals as their exact
  string (`rating` '4.3' never drifts), byte-identical on a rerun. *Rejected: the
  DuckDB community JAR; a Postgres container + load (a second server for a laptop
  demo); Snowflake full-mode (Phase 10, needs an account).*
- **The applier is a developer-run stdlib-`urllib` module, idempotent by
  upsert-by-name, not a `make` target.** It reads Metabase credentials from `.env`
  (refused by name, never by value) and talks to localhost only; `--dry-run`
  builds the request bodies offline with no credentials. Idempotency: GET the list,
  match by name, PUT if present else POST — a second apply creates no duplicate.
  The HTTP client is an injected seam so the socket-blocking suite tests it with a
  fake client. Keeping it out of `make` avoids the variable/`confirm` surface
  (localhost provisioning is neither paid nor destructive).
- **B2.1 lands Documented, curated in `study/paraphrases.yaml`.** One paraphrased,
  sourced example per theme (paraphrase not quote, no insurer named); it is the
  only text a drilled theme shows. `positive`/`unclassified` carry no theme and no
  paraphrase, so a drill row on either shows its counted columns and no text.
- **BACKLOG 52 was NOT folded in.** The developer's initial "fold it in" was
  reversed by challenge round 1: the classify-path idempotency target is a
  general-pipeline change whose recorded home is its own `fix/idempotency-classify`
  PR, kept off this study-surface diff (one phase, one diff); the property is
  already covered by two slow tests CI runs.

Gotcha (build-time, verified): the Metabase HTTP API is documented live at
`/api/docs` on a running instance; `POST /api/session` returns a session id used
in the `X-Metabase-Session` header; list endpoints return a bare list on some
versions and `{"data": [...]}` on others, so `as_list` accepts both. The pinned
`metabase/metabase` image tag and the exact dashcard body are confirmed against
the running version in the build's first hour (spec stack risk); SQLite is a
built-in driver, so no third-party JAR is mounted. Confirmed 2026-09-11 on
`metabase/metabase:v0.63.16`: the built-in SQLite driver reads the mounted
`data/metabase/metabase.sqlite`, and `PUT /api/dashboard/:id` with a `dashcards`
array attaches the cards — the applier's request bodies matched the running
version, no `apply.py` change needed; the demonstration screenshots (synthetic)
are committed under `study/metabase/screenshots/`. These PNGs are the repo's
first tracked binary assets: the one full-tree neutrality scanner
(`tests/test_ingest_layout.py::test_brand_carrying_strings_appear_only_in_the_declarations`)
reads a declared binary asset (`tests/repo_text.py::BINARY_ASSET_READERS`,
`{.png}`) as the text it carries beside its pixels — every `tEXt`, `zTXt`,
`iTXt` and `eXIf` chunk, decoded — so the pixels are reviewed by eye and the
text channels by the scanner (the macOS screenshots carry an XMP `iTXt` and an
EXIF chunk; review round 1 of this branch asked that they not go unscanned, and
that a text file mis-named `.png` not slip past — the reader refuses a file
without the PNG signature by name). Any other non-UTF-8 tracked file still fails
by name (the traceback-at-boundary guard is unchanged), and the scanner asserts
it read at least one text file and one binary asset, so an empty hit list can
never be vacuous. *Rejected: forbidding text chunks outright — every macOS
screenshot carries them, so the rule would force a strip step on each capture;
scanning them is the same guarantee with no step.* Landed on `fix/9g-demonstration` (the screenshots were unpushed
when PR #30 merged, so its CI never saw them). *Rejected: keeping the repo
binary-free by not committing the screenshots — done-when 5 wants them committed
as the demonstration's evidence.* The image is pinned by the
mutable tag `v0.63.16`, not a content digest (review round 2, security note): the
repo's SHA-pin bar is for GitHub Actions, and this stack is developer-run, never
in CI, so the tag stands with the compose header's "confirm the tag in the spike"
caveat; a digest pin is a later option if demo reproducibility matters. Cross-host
redirects on the applier's HTTP client are refused (`_NoCrossHostRedirect`) so a
3xx cannot carry the session token off the vetted host (round 2, security note).

Exit review of `fix/9g-demonstration` (2026-09-11, five agents, 22 findings, all
fixed). (1) Every committed screenshot carries the caption *synthetic fixture
data — not a study finding* in its pixels (a band drawn under the capture) and in
an iTXt `Comment` chunk, and the doc's alt text repeats it; the pinning test walks
the committed PNGs, so a captionless screenshot fails by name. The committed
bytes are the captioned render of the original capture (drawn by a scratch
script, not tracked), so each PNG now carries an `eXIf` chunk and the caption
`iTXt`, no longer the capture's XMP. (2) The reader for a tracked binary asset
moved from `tests/repo_text.py` into `scripts/review_common.py::read_text_or_error`,
the guards' read boundary, so the suite's scanners and `check_docs`'s naming
check read the same channels (site-fix: round 1 had taught one of the two); an
asset is declared by directory AND suffix (`BINARY_ASSETS`), the PNG chunk kinds
are a closed set (the text kinds read; the specification's pixel, colour, layout
and timing kinds and Apple's `iDOT` skipped; anything else refused by name), each
text chunk is parsed to its declared shape, and IEND ends the walk. *Rejected:
scanning every unknown chunk's body as latin-1 — noise from compressed profiles
and no refusal when a channel is unreadable; refusing by name keeps the set
explicit.* (3) The applier reads its login from the environment; every doc said
"reads `.env`" while nothing loaded the file, so the docs now show the export
step. *Rejected: a `.env` loader in the applier — a second secrets read path for
one developer-run command; the model key has the same convention.* (4)
`.env.example` is the one tracked `.env*` file: placeholders only, un-ignored by
`!.env.example`; recorded in the spec's Scope and CLAUDE.md's Repo map. The
CLAUDE.md-length BACKLOG row is re-deferred once more (805 lines; its own
`tooling/` PR before Phase 10).

### Phase 9h

Branch `phase-9h-sample-mean`, spec `specs/phase-9h-sample-mean.md`, challenged
round 1 (approve with amendments — 0 BLOCKER, 6 should-fix, 3 suggestion, 2
question; the developer's disposition "fix all", every finding applied before
the stamp). The first of the two data phases pulled out of Phase 9's render
(Phase 9a): the claim count at the sample's own mean reimbursement cell, shown
beside the count the lognormal mean gives. The branch also carries the
CLAUDE.md trim and its docs-only round (Process, above).

- **The fit artifact's shape changed: one row, `emp_mean`, appended as the last
  line at six places — the `Freeze:`-style line for a tracked artifact.**
  `fixtures/damir/` is untouched (no re-freeze); `data/damir/claim_cost_fit.csv`
  was regenerated by `make fit-damir` over the frozen fixture and is the
  pre-9h file plus one line (its sha256 pinned as `DAMIR_FIT_PRE_9H_SHA256`,
  `tests/test_damir.py::test_the_old_rows_are_a_byte_prefix_of_the_new_artifact`).
  The name set is one public tuple, `opendata.fit.FIT_FIELD_NAMES`, that the
  writer emits, the reader requires and `tests/test_snapshots.py` reads — the
  hand-typed copy the snapshot test carried was the drift the 9h challenge
  found (#2). `read_fit` refuses a missing, non-numeric, non-finite or
  under-one-cent `emp_mean` by name: it is a divisor downstream, rounded to
  cents first (review round 1, `711864e`). *Rejected: the
  row after `n` (challenge #1) — it breaks the byte-prefix property for a
  grouping no reader sees; two decimals like the deciles (challenge #5) — a
  divisor at two places puts the hand-recomputed count one calculator digit
  from a different whole number (350,000,000 / 847.59 = 412,935.4995), at six
  it is unambiguous (…,935.41); a separate `sample_mean()` handed to a wider
  `write_fit` — a second thing to carry that is never written without the
  first.* The model's own rounding site still quotes the parameter in euros at
  two places (847.59), so the page's cell and the artifact's six-place value
  divide to the same whole count — pinned by
  `tests/test_cost_model.py::test_claims_at_mean_cell_is_the_division_by_hand`.
- **The contrast is a fourth sourced parameter and a thirteenth point formula;
  no existing entry moves.** `fit_parameters` returns `emp_mean` as a fixed
  mark (`low == default == high`, the `emp_p50` precedent — the second such
  row, accepted; a third is the trigger of the new BACKLOG row *Two
  read-figure rows sit under `Parameter`*); `POINT_FORMULAS` gains
  `claims_at_mean_cell = refunded_eur / emp_mean` right after `claims`, which
  nothing downstream reads, so `mean_claim`, `claims`, Beat 4 and the
  simulator keep every pinned value (`tests/pins.py` grows by the new rows and
  counts only). One name travels from the artifact row to the parameter row
  to the display map (`emp_mean`; "Mean reimbursement cell"; "Claims per year
  at the mean cell") — the LESSONS `name-drift` class the challenge caught in
  the spec's four names (#3). *Rejected: `mean_claim` as a parameter ranging
  from the fitted to the sample mean — the formula list would lose the fit's
  derivation and `mu`/`sigma` their reason; switching `claims` to the sample
  mean — a different page, not a contrast, and a Beat 4 re-pin; a live slider
  between the two means — the permanent page carries no script (9f), and the
  BACKLOG row's original trigger ("a `claims` slider") never fired: the phase
  fires on the reader's recompute instead, recorded on the struck row.*
- **The page reads the new row through the maps it already has, and says only
  what its cells show.** `HEADLINE_FORMULAS` gains the fourth name (B3.3's
  headline is one map, the same `Series` shape); `FORMULA_NAMES` and
  `PARAMETER_NAMES` gain one entry each (a name outside them still refuses —
  9c decision 6); the B3.3 note (`study/text.py::MEAN_CELL_NOTE`, data) names
  the two means and their direction and nothing the marts do not hold — no
  maximum cell, no percentage gap, no decile: the goodness-of-fit table is not
  rendered, and at p70–p90 the fit is the heavier side (challenge #8).
  *Rejected: a cell inside the `claims` row — a new `Series` shape for one
  number.*
- **A decision the spec did not cover: B5.1's formula count moved 14 → 15.**
  The determinism-facts stat counts `len(FORMULAS)` from the code (9e), so
  adding a formula moves a Measured number outside Beat 3 by construction —
  the mechanism working, not a value retyped; the README's Beat 5 line and
  `BEAT5_FRAGMENTS` follow it. The spec's central constraint ("every number
  the page shows today keeps its value") meant the modeled values; the
  Delivered paragraph says so. *Rejected: pinning the count at 14 — a repo
  fact that lies; excluding the new formula from the count — a second list.*
- **`make model`'s name column is the longest point-formula name, computed
  once.** The literal 16 misaligned the new nineteen-character row; the width
  is `max(len(f.name))` over `POINT_FORMULAS`, so the next entry cannot
  misalign either (fix the class); the parameter table's literal 16 went the
  same way at review round 2 (`71b0a33`). *Rejected: a shorter name
  (`claims_cell`) to fit the literal — the name is the one the display map and
  the page carry.*
- **Review round 2 (the exit round): the fit reader's foreign shapes are the
  repo's shared ones, and its refusals are bounded on what they print.** A
  value cell is accepted only in `opendata.slice.DECIMAL_SHAPE` (now public:
  plain digits, one separator, an optional minus — the amount reader's shape,
  so `1e5`, `1_000`, `nan`, `inf`, `+3` refuse by name) and `n` only in
  `ingest.parsed.count_in_range` (the one count shape every parser uses); a
  shown token is cut on its printed repr, and a list of stray names shows
  three and counts the rest (`242d3d3`). *Rejected: a second regex in
  `opendata/fit.py` — the `unshaped-input` class's promotion says one shape
  per kind, shared; widening `count_in_range` — ten ASCII digits already hold
  any sample size.* The one-cent floor is bound to the model's euro rounding
  scale by a test (`71b0a33`); the B3.3 note is pinned to carry no figure the
  marts do not hold (`88d1f89`). The round found no correctness finding in
  round 1's fixes, so the review cap did not fire.

### Fix — the shared count and decimal shapes get one home and one alphabet (2026-09-12, branch `fix/foreign-shape-shared-home`)

Not a phase (no spec; a fix PR from `main`, CLAUDE.md → Git workflow). The
amendment is committed alone, before the code. Challenged 2026-09-12, round 1
(`senior-architect`): verdict *rework* — the first draft's mechanism did not
restore the invariant it claimed (`DECIMAL_SHAPE`'s Unicode `\d` still admits
`٣` as `3.0`), and it risked a negative crawl interval and a `name-drift` on
the process id; all five findings folded in below.

The property this fix is written against: **a foreign count or decimal on a
read path is a non-negative ASCII decimal of the one shared shape, or it
declares nothing — refused, or on a scraped page dropped, by name; no
`ingest`/`pipeline`/`opendata` module parses a number outside a shared shape.**

Phase 9h's entry declares `ingest.parsed.count_in_range` "the one count shape
every parser uses" and `opendata.slice.DECIMAL_SHAPE` "the amount reader's
shape" — but the 9h selfcheck found four hand-rolled sites outside them, and
the challenge found the shared decimal shape itself is not ASCII-tight:
- `opendata.slice.DECIMAL_SHAPE` is `r"-?\d+(?:[.,]\d+)?"`, and Python's `\d`
  is Unicode-aware, so `DECIMAL_SHAPE.fullmatch("٣")` is true and `float("٣")`
  is `3.0` (verified). The shape it is supposed to be — plain ASCII digits —
  it is not.
- `ingest/robots.py::_parse_groups` coerces a scraped `Crawl-delay` with bare
  `float(value)` (only `inf`/`nan` caught by `math.isfinite`), so `1e9`,
  `1_000` and `٣` all pass; a leading `-` reaches `fetch.py`'s crawl-interval
  path, where the ceiling check `crawl_delay > MAX_CRAWL_DELAY_S`
  (`ingest/fetch.py:228`) does not catch a negative, so `-5` would set a
  negative interval.
- `pipeline/cli.py` open-codes an ASCII integer three times: `positive_int`
  (`value.isascii() and value.isdigit()`) and the two raw `make_pid.isdigit()`
  at the confirm stamp (not ASCII-guarded).

`unshaped-input` is already `promoted → code-craft → Guards`; a promoted class
that recurs reworks its mechanism, not its row (LESSONS → Promotion).

- **One home, one alphabet.** `DECIMAL_SHAPE` moves down to `ingest.parsed`
  beside `count_in_range` (the import-safe home: the edge already runs
  `opendata/fit.py → ingest.parsed`, never the reverse); `opendata.slice`
  re-exports it, so every current importer (`opendata/fit.py`,
  `tests/test_damir.py`) is unchanged. Its digit class becomes ASCII `[0-9]`
  (not Unicode `\d`), so `٣` is no longer the shape — this extends the 9h
  "shared shapes" decision by one line, and real DAMIR is ASCII so no real
  number changes. A shared ASCII decimal-integer predicate joins the two
  shapes in `ingest.parsed`, named for its shape (an ASCII decimal integer),
  and `count_in_range` is expressed in terms of it (it adds only the
  ten-digit range). *Rejected: a new `shapes.py` module (a package for shapes
  `ingest.parsed` already anchors); leaving `DECIMAL_SHAPE` in `opendata`
  (the two-homes drift the 9h "one shape per kind, shared" rule forbids).*

- **`robots.py`'s `Crawl-delay` reads through the shared decimal shape, then
  keeps its finiteness and `>= 0` guard; a value that is not a non-negative
  finite ASCII decimal declares no delay, by name.** The drop (not refuse)
  stays — a directive RFC 9309 lets us ignore is no reason to distrust the
  file — but `1e9`, `1_000`, `٣` and `-5` now take the "no delay" branch
  instead of a `float`; the `>= 0`/`isfinite` guard is retained after the
  shape check, so nothing negative or non-finite reaches `fetch.py`'s
  interval. *Rejected: dropping the `>= 0` guard on the trust that the shape
  covers it (it does not: the shape admits a sign — Finding 2); refusing the
  whole file on a malformed delay.*

- **`pipeline/cli.py`: `positive_int` reads through `count_in_range` (N is a
  count in range — its own domain); the confirm-stamp `make_pid` reads through
  the shared ASCII decimal-integer predicate, named for its shape, not
  `count_in_range`.** A process id is not a count and not a parser's value, so
  routing it through "a count in range" would misname it (the promoted
  `name-drift` class) and cap it at ten digits for no reason; the shape-named
  predicate holds it to ASCII digits without either. Because `make_pid` goes
  through a shared shape, the layout guard below needs no exemption for it.
  *Rejected: `make_pid` through `count_in_range` (name-drift); a bare
  in-place `isascii()+isdigit()` on `make_pid` (a fourth hand-rolled copy the
  layout guard would then have to exempt — an exemption is a denylist by
  another name).*

- **The reworked mechanism is an AST check, not a substring grep**
  (`tests/test_number_shapes.py`). A test walks the `ast` of every
  `ingest`/`pipeline`/`opendata` module and bans the two loose coercions:
  `.isdigit`/`.isdecimal` (the methods that lie about Unicode) anywhere, and
  `float()` outside the three shaped-decimal parsers (`opendata.slice.parse_amount`,
  `opendata.fit._finite_float`, `ingest.robots._parse_groups` — each matches
  `DECIMAL_SHAPE` first). *Built narrower than this amendment's first
  enumeration (`float`, `int`, `Decimal`, `.isdigit`, `.isdecimal`): a grep of
  the three packages found `int()`/`Decimal()` used at ~8 legitimate sites,
  each already behind a bounded digit shape (a date's `int(m.group(...))`,
  `Decimal(text)` after a `Measure` pattern), so banning them would have forced
  an ever-growing allowlist — the escape hatch the guard exists to avoid, the
  `site-fix`/`empty-default` smell. The two loose coercions carry the class;
  `int`/`Decimal` are left to the shapes that already precede them. Rejected: a
  grep denylist of `float(`/`.isdigit(` (the form the `unshaped-input` row
  retired in tooling round 3 when a spawner-name denylist let `os.popen` slip;
  an alias or a differently-spelled call evades a substring match).*

Scope: `ingest/parsed.py`, `opendata/slice.py`, `ingest/robots.py`,
`pipeline/cli.py`, their tests, and the AST layout test. One commit per
correctness finding (the shape home-and-alphabet move first, then each
routing), the `unshaped-input` LESSONS row's Where cell extended with each and
its Status noting the AST guard as the reworked mechanism. Sensitive surface
(`ingest/**`, `pipeline/cli.py`): the round runs code-reviewer,
functionality-tester and security-reviewer.

### Phase 9i

Branch `phase-9i-extra-billing`, spec `specs/phase-9i-extra-billing.md`,
challenged round 1 (approve with amendments — 0 BLOCKER, 6 should-fix, 3
suggestion, 2 question; the developer's disposition "fix all", every finding
applied before the stamp). The second of the two data phases pulled out of
Phase 9's render (Phase 9a): the extra-billing share from data.ameli's
`honoraires` table as one sourced B3.3 row beside the mean claim.

- **The dataset as read (2026-09-12, the 7b rule: confirm the source before
  anything is built).** data.ameli `honoraires` — Caisse nationale de
  l'Assurance Maladie, Open Database License, last modified 2025-12-15, 66,480
  rows, one row per year (2010–2024) × `profession_sante` × `region` ×
  `departement`; per row the year's total fees at the public tariff
  (`hono_sans_depassement_totaux`) and total extra billing
  (`depassements_totaux`) in whole euros, the per-practitioner means and the
  sector-2 rates; `NS`/`NC` where suppressed; the national rows are
  `region = 99` / `departement = 999`; 38 profession labels at the national
  level, nesting under four families (`Ensemble des médecins`, `Ensemble des
  chirurgiens-dentistes`, `Sages-femmes`, `Ensemble des auxiliaires médicaux`)
  whose sub-rows sum to each family. Annual per-practitioner totals, not
  per-act or per-claim amounts. *So: the BACKLOG row's premise ("a
  practitioner-fee distribution … fitted the same closed-form way") does not
  hold, and the brief's §7 clause "data.ameli for practitioner-level fees" as
  a simulator draw source does not hold for this dataset — the phase records
  the reading here and lands what the table uniquely supplies (the trigger
  reinterpreted, the 9h precedent); the brief's sentence is untouched, the
  developer's call outside this diff (challenge round 1, #11), so the exit
  coherence audit treats brief↔DECISIONS as recorded, accepted drift. The
  same claim stands in two more brief sentences — §7's `claims` bullet
  ("average claim sizes from … Open DAMIR / data.ameli distributions") and
  §9's Phase 7 line ("Ingest Open DAMIR / data.ameli slices; fit the
  claim-cost distributions") — all three read the same way: DAMIR supplies
  the distributions, data.ameli one national share (review round 2,
  coherence #6).*
- **The quantity is the extra-billing share over the four top-level families
  for one year, and its range is the family spread.** `extra / (tariff +
  extra)`: the default over the four summed totals, `low`/`high` the lowest
  and highest family share — a fourth kind of `low`/`high` pair beside
  floor-to-twice, ±2 SE and the fixed marks, named as such in the model's
  docstring, B3.3's blurb ("and, for the inputs the formulas read, the range
  the study explores") and its note (`study/text.py::EXTRA_BILLING_NOTE`: a
  spread in the data, not a bound the study explores; no formula reads the
  row). The read-figure BACKLOG row's trigger is re-pointed, not claimed
  unfired (challenge round 1, #2). *Rejected: a lognormal over
  per-practitioner mean fees (a practitioner-income curve, not a claim cost);
  a fixed mark with the spread in prose (a figure in a note must be a mart
  cell); five rows, one per family (clutter for one fact); a formula that
  multiplies the insurer's refunds by the share (the insurer's claims are not
  the national fee mix — an invented quantity); the duller route of the same
  share from the DAMIR month already ingested, whose fee (`PRS_PAI_MNT`) and
  base (`PRS_REM_BSE`) columns sit on the very cells the fit describes
  (challenge round 1, #6) — the fixture is a 5,000-cell systematic sample
  where data.ameli's totals are the exhaustive national population, and
  `fixtures/damir/` is frozen with one column pair, so reading two more is a
  re-freeze for a ratio the brief sources to data.ameli by name; the new
  BACKLOG row names that route for the complementary-side share per cell.*
- **No fetch target: the export is a hand download; every command offline.**
  `https://data.ameli.fr/robots.txt` says `User-agent: *` / `Disallow: /api/`,
  `/explore/download`, `/explore/dataset/*/download`, and the export lives
  under those paths. The repo honours a host's robots file over its own
  convenience (Phase 2 declared the App Store feed and did not fetch it; 3a
  hand-read the listing whose terms forbid robots; 3c imported an authorized
  offline export), so the developer saves the dataset's CSV export from a
  browser — a person, not a crawler — to the gitignored
  `data/cache/ameli/honoraires.csv` and runs `make slice-ameli YEAR=YYYY` once;
  no `confirm` gate, since nothing fetches or deletes. Disclosed for the
  record: the spec's research made six small metadata requests to the API
  with an identifying User-Agent before the robots file was read; none of that
  output is used as data. *Rejected: a `confirm`-gated `fetch-ameli` over
  `urllib` (the DAMIR shape) — against the host's stated rule, whatever the
  API's rate-limit headers suggest; reading the API's JSON instead of the
  export — the same disallowed prefix.*
- **A bounded euro-total shape, beside the count shapes, for the totals.**
  `ingest.parsed.euro_total_in_range`: the shared ASCII integer shape with a
  ceiling of `10^12 - 1` — no national annual total reaches a trillion euros.
  The count shape's ceiling (`2^31 - 1`, about €2.1 bn) is below the data
  (the all-families tariff total is about €51 bn), so routing a total through
  `count_in_range` would refuse the real file, and a bare `int()` would hold
  no bound (challenge round 1, #1; the `unshaped-input` class). *Rejected:
  widening `count_in_range` (a count column's shape would then admit a value
  its column cannot hold).*
- **One container of the model's inputs.** `cost_model.ModelInputs(fit,
  fee_split)` read by one `pipeline/build.py::read_model_inputs` (which
  absorbed `read_model_fit`); `parameters(inputs)`, `defaults`, the printers
  and the mart writers take it, so a later input is a field, not a new
  signature at every caller (challenge round 1, #7). `cost_model.FeeSplit(year,
  share, low, high)` is what the model needs from the artifact. *Rejected:
  `parameters(fit, fees)` (every caller changes again at the next input, and
  the simulator's `defaults()` would name an artifact it never reads);
  widening `Fit` with fee fields (a DAMIR shape carrying a data.ameli figure
  — name drift); a literal in `SCALE_PARAMETERS` pinned equal to the artifact
  (the second-literal pattern 8a refused).*
- **Two names: `ameli` for the source, `fee_split` for the artifact and its
  module.** `opendata/sources.py` declares both open-data sources;
  `opendata/fee_split.py` holds the slice reader, the fixture writer, the
  split arithmetic, the artifact writer and reader and the printer (the
  `slice.py` + `fit.py` pair in one file — two sums and a division); the
  targets are `slice-ameli [YEAR=]` and `split-ameli` on the `fit-damir`
  verb-source pattern; the artifact is `data/ameli/fee_split.csv`
  (`FEE_SPLIT_FIELD_NAMES`: the year, each family's two totals and share by
  slug, the all-families three; whole euros, shares at six places); the
  fixture is `fixtures/ameli/ameli-national.csv` (challenge round 1, #3).
- **Decisions the spec did not cover.** (a) The fixture carries the six
  columns the slice reads (`annee;profession_sante;region;departement;` the
  two totals), not the four the spec named: one declared shape and one reader
  serve the export and the fixture (the 7b A1 principle), and `split-ameli`
  — which takes no variable — reads the fixture's one year off the file
  (`fixture_year`, refusing two years or none). *Rejected: a four-column
  fixture with a reader that treats the territory columns as optional — a
  lenient shape.* (b) The fit artifact's `name,value` read (the size cap, the
  header, two cells, no duplicate, the closed name set, the cut tokens) moved
  from private helpers of `opendata/fit.py` into public ones the second
  reader shares — `read_name_value_rows(path, names, kind)`, `finite_float`,
  `shown`, `shown_names`, `MAX_ARTIFACT_BYTES` — with `kind` naming the
  artifact in a refusal; the AST guard's `FLOAT_CALLERS` follows the rename
  (`_finite_float` → `finite_float`; the tooling entry above names the old
  spelling as it was). *Rejected: a copy of the reader in `fee_split.py` (the
  `site-fix` class); a third module for the shared read (the pinned "one new
  module").* (c) The tracked-files guard walks one closed map `{artifact
  path: name set}` over both artifacts (challenge round 1, #4).
- **The row's tag is the mart's, Modeled.** The share is a division over two
  published totals, printed in full on the page (the note says the arithmetic
  in words, `make split-ameli` prints it) — the README glossary's Modeled, "a
  number produced by arithmetic we print in full", the footing `emp_mean`
  (an arithmetic mean over the DAMIR fixture) already stands on; Documented
  is "a number from a named public source", which the totals are and the
  share is not. *Rejected (review round 1, code-reviewer #1): a per-row
  Documented tag for a context row — the params mart stamps one tag per
  write, so a per-row tag is a `Parameter` field and a write-path change, a
  fix amendment; it is the read-figure BACKLOG row's territory and its
  trigger now names the tag.*
- **Review round 1 (2026-09-12): twelve findings, none a BLOCKER, one a
  correctness finding — the CLI's read boundary, the `traceback-at-boundary`
  class in LESSONS; every one fixed, the developer's disposition "fix all".
  The correctness fix landed in `f5d278c` with the other code fixes, not
  alone: the one-per-commit rule was missed there and this sentence is its
  record (review round 2, coherence #2).** Code: one euro-total helper for
  both readers; the fixture read once
  (`read_fixture`, the year off the file, replacing `fixture_year`); the
  "no national rows" refusal cuts its tokens like every other; the
  missing-column refusal derives its slice from `FIXTURE_COLUMNS`; the two
  fixture writers named by meaning (`write_ameli_fixture`,
  `write_damir_fixture`); the CLI's read paths catch `(ValueError, OSError)`
  (the `traceback-at-boundary` row's Where cell extended). Security notes:
  the export reader's no-cap reason written in its docstring and the spec's
  bullet corrected. Prose: B3.3's blurb says "context, not a formula input"
  (the row sits among the sourced rows); the "spread, not a bound" clause
  said once, in the note; SPEC's B3.3 sentence split. Record: the spec's
  Scope names the reused `freeze_manifest`. The tag finding (#1) is the
  bullet above.
- **Review round 2, the exit round (2026-09-12): sixteen findings, none a
  BLOCKER, one correctness; every one fixed or re-deferred with a trigger,
  the developer's disposition "fix all".** Correctness (security #1, its own
  commit `bd14315`): `csv.Error` is no `ValueError`, so the round-1 tuple
  still let a corrupt export out as a traceback; the reader now folds the
  parser's failure into the refusal it declares (the `decode_json`
  precedent) — the kind changed, not the tuple; the second hit of the class
  in one phase, so the sentence for `code-craft` is a BACKLOG row for the
  next tooling branch, and the same gap on the pre-9i DAMIR sample path is
  a BACKLOG row, not a fix in this diff. Craft and prose (`e779883`): the
  label set a `frozenset`; the strip declared; the ceiling's redundancy
  said; the test named for `read_model_inputs`; the docstring's third-row
  pointer moved to the fourth; the note says the totals are one year's
  national per-family totals, states the range fact once and ends on its
  caveat. Records (this bullet's commit): CLAUDE.md's status; round 1's
  sentence above; Done-when 2 amended to the six-column fixture the
  DECISIONS bullet already recorded and the stamp re-hashed (the 9b
  precedent: falsifiers and decisions unchanged); the spec's Scope names
  `check-docs` as the glossary cap's guard, not `tests/test_readme.py`; the
  brief drift bullet names all three brief sentences; the no-`SPEC=` gate
  row's trigger, met by this phase's first freeze, re-deferred to a `fix/`
  PR with the wider wording; the skill's "two tracked subtrees" a tooling
  row.

### Fix — the classify step runs inside `idempotency-check` (2026-09-12, branch `fix/idempotency-classify`)

Not a phase (no spec; a design-change fix PR from `main`, CLAUDE.md → Git
workflow). The amendment restores this invariant: **the machine idempotency
check covers every mart the pipeline writes deterministically offline, the
classify-path marts included.** Until now `idempotency_check` called
`rebuild()` only, which stops before the classify step, so
`stg_classified_reviews`, the three `POST_CLASSIFY_MARTS` and
`pipeline_row_counts` never entered its per-table diff — machine-checked only
by two slow scenario tests (BACKLOG, opened `fix/theme-marts-run-id` round 1).
The classify step's code lived in `pipeline/cli.py::_classify_and_print`,
which `pipeline/build.py` cannot import (cli imports build); the Repo map
already names build.py as the home of "the classify step," so this is a
who-writes-what change that restores the documented layering.

- **The classify step's code moves into one `build.py` function,
  `classify_step`, taking a cache path so a throwaway run touches no tracked
  cache.** `_classify_and_print` wraps it and prints; `idempotency_check`
  calls it after `rebuild()` with a cache path inside the tempdir it already
  creates, then compares whole-db `table_counts`. The duplicated
  `_classify_and_build` test helper (a rules-only re-implementation that
  existed only because there was no shared function) is rewritten to a thin
  wrapper over `classify_step`, so the duplication is gone. *Rejected: a new
  `pipeline/classify_step.py` module
  (the amendment scoped it to a build.py function; build.py already owns the
  step per the Repo map); `idempotency_check` importing from `cli` (a layering
  inversion); leaving the two slow scenario tests as the only coverage (the
  BACKLOG row's whole point — the target, not a sibling test, must see the
  marts).*
- **Whole-db `table_counts`, so `classifier_quality` is covered too —
  superseding the amendment's "stays out (corpus-gated)."** Excluding one
  deterministic table would need a denylist-of-one, the smell CLAUDE.md's
  "fix the class, not the case" forbids; including it is stable (delete+insert,
  deterministic offline) and stricter. On an input the answer key does not
  cover it holds 0 rows in both runs (its DDL shell, which `rebuild()` creates —
  `classify_step` leaves it empty when `graded` is false), still equal. *Rejected:
  filtering `classifier_quality` out of the comparison (the denylist);
  passing `classify_step` a `write_quality=False` flag for the idempotency
  path (behavior divergence between the two callers).*
- **No warehouse-awareness change.** The classify step's DuckDB-only
  connection (BACKLOG, `TARGET` not yet threaded) stays as it is; that row is
  Phase 10's Snowflake wiring. This fix is offline, DuckDB-only, no key. One
  PR, one concern.

### Tooling — two skill sentences (2026-09-12, branch `tooling/skill-sentences`)

Not a phase (no spec, no BACKING row). The first of three small PRs before
Phase 10, the BACKLOG row "Two tooling texts lag the code" (Phase 9i exit
audit). Two edits, one commit, records in a second.

- **secure-by-construction counts three tracked `data/` subtrees.** Phase 9i
  added `data/ameli/` beside `snapshots/` and `damir/`, and `.gitignore` and
  CLAUDE.md said so while the standard still said two; the third tracked
  output, `data/ameli/fee_split.csv`, joins the numbers-only list. The
  reviewer preloaded with the text now reads the same count the repo keeps.
- **code-craft → Error policy says a reader owns its failure type.** The
  `traceback-at-boundary` class hit twice in Phase 9i's rounds — a widened
  `(ValueError, OSError)` tuple, then `csv.Error` past it — and CLAUDE.md's
  rule turns a class hit twice into a mechanism. The sentence is the
  mechanism: the parser's own error is folded into the one refusal the
  reader declares (the `decode_json` and `fee_split._iter_rows` shape), so
  the boundary catches one declared set and a wider `except` tuple is never
  the fix. *Rejected: a ruff or AST rule that refuses `csv.Error` in an
  `except` tuple outside a reader (a denylist of one parser; the JSON and
  decode errors would each need their own arm), and waiting for the csv
  fix PR to write the sentence (the standard is what that fix is reviewed
  against, so it lands first).* The test that walks every `csv` reader is
  that fix PR's, the BACKLOG row "Every `csv` reader but one maps
  `ValueError` only…".

### Fix — every `csv` reader owns its failure type (2026-09-12, branch `fix/csv-reader-boundary`)

Not a phase (no spec; a fix PR from `main`, CLAUDE.md → Git workflow; the
BACKLOG row "Every `csv` reader but one maps `ValueError` only…"). The fix
restores this invariant: **for every `csv` reader in the source packages, a
file the parser cannot read (`csv.Error`, a field past `csv.field_size_limit()`)
comes out as the refusal the reader declares, and every CLI read path catches
its declared set — one line and exit 2, never a traceback.** Phase 9i's round 2
folded the parser's error at `fee_split._iter_rows` only; the seven other
readers still let `csv.Error` (no `ValueError` subclass) past `ValueError`
tuples, `CacheError`, `LabelError` and `PageShapeError`, and `sample-damir`
wrapped its read in no `try` at all.

- **Each reader folds `csv.Error` into its own declared type — the kind, not
  a wider tuple.** `_read_csv` → `PageShapeError`; `read_decisions` →
  `CacheError`; `read_labels` → `LabelError`; `slice._iter_rows` and
  `read_name_value_rows` → `ValueError`; `trustpilot.parse` → `refuse(...)`.
  One phrase at every site, "not a CSV the reader can parse", so a reader of
  the refusal sees the same sentence whichever file it was. *Rejected: adding
  `csv.Error` to each boundary's `except` tuple (the class the code-craft
  sentence names as never the fix: every boundary would then have to know
  every parser); one shared `read_csv_or_refuse` helper raising one type (the
  readers declare four different types by design — a cache error is not a
  page-shape error — and the walk test already keeps them uniform).*
- **`read_fixture` reads through `_read_csv` with the fixture's eight columns
  declared (`FIXTURE_REVIEW_COLUMNS`), not through a bare `csv.DictReader`.**
  One strict reader for tracked CSVs in `build.py`; the synthetic fixture's
  header is checked where before it was trusted. *Rejected: a second
  `try/except` in `read_fixture` (a duplicate of `_read_csv` four lines
  apart).*
- **`_do_fit_damir` gets the boundary catch with `_do_sample_damir`, though
  the row named only the sample path.** Both read a DAMIR CSV whose reader
  raises `ValueError` and neither caught it — the same class at a sibling site
  (LESSONS `site-fix`); the fix commit's grep of `read_amounts(` and
  `systematic_sample(` in `cli.py` lists both. *Rejected: fixing the named
  site only (the `site-fix` class, hit six times).*
- **The pin is one walk, not one test per reader.** `tests/test_csv_readers.py`
  scans the six source packages by AST for `csv.reader`/`csv.DictReader` calls
  and asserts the set equals the readers it walks, so a new reader fails the
  suite until it joins the walk; each walked reader is handed a file with one
  field past a narrowed `csv.field_size_limit()` (a pinned 64 characters, the
  limit restored after) and must raise its declared type naming the file. The
  limit is narrowed because the fit artifact's 64 KiB byte cap sits below the
  interpreter's default field limit, so a real over-limit field would refuse
  on size first there; the 9i fee-split test keeps the default limit and a
  140 000-character field. *Rejected: a 140 000-character field at every
  reader (unreachable at the byte-capped artifact); a grep-based site list
  (a `csv.reader` in a comment or string would count; the AST scan is the
  `test_number_shapes.py` shape).*
- **Review round 1 (2026-09-12): eleven findings, one BLOCKER, disposition
  "fix all".** Correctness (code #1, confirmed by the tester running it;
  `360e040`): `cli.main` caught `Refused`, `PageShapeError`, `ModelError` and
  `FetchError` but not `CacheError` or `LabelError` — the two declared types
  this fix folds `csv.Error` into — so a corrupt decision cache left `make
  rebuild`, and a corrupt answer key `make rebuild` and `make classify-eval`,
  as a traceback; one arm for the pair and two CLI boundary tests, each with a
  field past the interpreter's default limit (the synthetic corpus must still
  read, so the narrowed limit of the walk cannot serve there). Craft (the
  next commit): the refusal phrase is `ingest/parsed.py::CSV_UNREADABLE` at
  every site and in the tests — `ingest.parsed` because it is the one
  stdlib-only leaf below every reader's package (`opendata` and `pipeline`
  already take their shapes from it, fix #33; `pipeline` as the home would
  cycle through `classify`), a first `classify → ingest` edge and no edge
  back; the AST scan resolves `import csv as c` and
  `from csv import … [as x]` (code #3, security #1); `_decision`/`_label`
  hold the per-row checks (code #5); the export entry has its own writer
  (code #6); the scanner reads through `tests/repo_text.py` (security #2).
  Records: the code-craft clause is taken back out of the fix PR — a skill
  edit rides a `tooling/` branch (code #2) — and is a BACKLOG row for the
  next one, so the count is 38 again. Accepted with the precedent named:
  the process-global field limit the walk narrows and restores (code #7,
  security confirmed no leak); `read_fixture` now strict on its header
  (security #3, the second bullet above).
- **Round 2's gate caught the arm's import: `LabelError` reaches the CLI
  through `classify.eval.gate`, re-exported, not from the reader module.**
  `tests/test_labels_isolation.py` refuses the reader module's name anywhere
  outside `classify/eval/`, and `360e040` had imported the error type from
  it; the type is the eval package's boundary contract, so the gate — what
  raises it out of `rebuild` — exports it (`bb8d45b`).
  *Rejected: widening the wall's token set with an exception for the error
  type (a denylist edit for one case); catching `Exception` at the CLI (the
  traceback-at-boundary class's opposite failure, a swallowed refusal).*

### Fix — the review gate reads the phase branch's own spec (2026-09-12, branch `fix/review-gate-no-spec`)

Not a phase (no spec; a fix PR from `main`, CLAUDE.md → Git workflow; the
BACKLOG row "`make review-gate` without `SPEC=` is red on a phase branch…",
opened by Phase 3a's functionality-tester and triggered at Phase 9i's exit,
whose first freeze of `fixtures/ameli/` turned the no-SPEC form red on the
branch). The fix restores this invariant: **the gate's verdict on a range does
not depend on whether `SPEC=` was typed — with no `SPEC=` the gate reads the
branch's own spec and runs every check the SPEC form runs; a branch with no
phase spec keeps fixtures read-only; and both summary lines count the same
thing.**

- **The no-SPEC form derives the spec from the branch by the rule
  `/review-round` already applies: `phase-<slug>` → `specs/phase-<slug>.md`.**
  The branch name is `git rev-parse --abbrev-ref HEAD` through the shared `run`
  boundary, parsed to one closed shape (`\Aphase-[0-9]+[a-z]?-[a-z0-9-]+\Z`,
  which every phase branch since 0a matches); anything else — `fix/`,
  `tooling/`, `docs/`, `main`, a detached `HEAD`, a traversal or case variant —
  is no spec, and the SKIP line names the branch. The path is built from the
  matched name, never from the raw output. *Rejected: skipping the fixture
  check with no SPEC (loses the read-only guard on fix branches, where a
  fixture change has no `Freeze:` line to license it, and the two forms would
  still disagree); reading every spec's `Freeze:` lines (a stale grant in an
  old spec would re-license its fixture forever).*
- **A phase branch whose spec file is absent is refused, exit 2, naming the
  branch and the path; a failed git call is refused naming git's line.** The
  first commit on a phase branch is its spec, so a phase branch with none is a
  workflow error, not a branch with no spec; an empty branch name read as "no
  spec" would be the `empty-default` class. `resolve_inputs` is the one seam:
  a typed SPEC is resolved as given and the branch is never consulted.
  *Rejected: falling back to the six range checks on a phase branch with no
  spec (a silent narrowing the developer would read as green).*
- **Both summary lines print `<passed>/<total> checks passed`.** The FAIL line
  counted failures and the OK line counted passes, so `2/8` and `8/8` read as
  the same kind of number and were not.
- Records: the BACKLOG row is DONE (37 open); CLAUDE.md → Commands says the
  no-SPEC rule; the Makefile help line names the default. No LESSONS row: the
  finding was a Phase 3a functionality-tester deferral, not a class a fix
  commit closed against a review round of this branch.
