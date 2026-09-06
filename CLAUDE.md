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
document), `SPEC.md` (the study's structure: the five parts and every chart,
settled in Phase 0b), `BACKING.md` (the evidence contract: claim → table → SQL
→ source → tag), this file (how we work), then the active spec in `specs/`.
`docs/PLAN.md` is how this workflow was designed; `DECISIONS.md` is the
why-not-X log.

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

- `PROJECT_BRIEF.md` — the master document. `SPEC.md` — the five
  parts of the study (called *beats* in the row ids `B<beat>.<n>`) and the
  exact chart list, each with its tag and BACKING row.
  `BACKING.md` — the evidence contract (§8 of the brief); `make check-backing`
  enforces it. `DECISIONS.md`, `BACKLOG.md` — the records.
- `docs/PLAN.md` — the design of this workflow: adopt/adapt/drop verdicts on
  the reference project, the phase re-cut, the decisions taken.
- `specs/` — one spec per phase from `specs/TEMPLATE.md`, ONE DONE command
  each. The "Delivered" paragraph is appended to the spec at exit.
- `scripts/` — the offline guards, none a pytest file: `review_gate.py`,
  `check_docs.py`, `check_backing.py`, `review_common.py` (shared).
- `tests/` — pytest; no services, no network, no API key. `tests/pins.py`
  holds every pinned number.
- `.claude/` — agents (report-only), skills (the three standards and
  `/challenge`), commands, the two hooks. Settings are local-only and
  gitignored.
- `.github/workflows/ci.yml` — lint, check-docs, check-backing, test, then
  rebuild + idempotency-check twice: once on the synthetic reviews, once on
  every frozen sample through its real parser. `weekly.yml` — the scheduled
  scrape (`schedule`/`workflow_dispatch`, `contents: write`): `make confirm
  scrape` then `make record-snapshots`, then a fixed brand-free commit of
  `data/snapshots/` only (the one workflow that writes to the repo).
  `.github/pull_request_template.md` — the PR body.
- `pyproject.toml`, `uv.lock`, `.python-version`, `.pre-commit-config.yaml` —
  the toolchain (uv, ruff, pytest, pre-commit), versions pinned in lockstep.
- `sql/raw/`, `sql/staging/`, `sql/marts/` — plain SQL, one file per table:
  reviews (`raw_reviews` carrying each review's `segment`, stamped at load;
  `stg_reviews`), platform snapshots
  (`raw_platform_snapshots`, `stg_platform_snapshots` with each row's tag),
  the declared page addresses with their attribution (`raw_source_pages`, the
  declared-page registry captures are checked against — NOT how a review gets
  its segment, since Phase 7a A1), and the four Beat 1–2 marts they feed
  (`rating_trend`, `channel_gap`, `platform_stats`, `peer_ratings`); plus
  `classifier_quality` (B2.4, Beat 2), the first Python-fed mart — its `.sql` is
  DDL only (the shape), the CLI classify step scores the held-out fold and
  inserts (Phase 6b); plus `stg_classified_reviews` (the persisted review × theme
  classification, Python-fed) and the two theme-share marts over it,
  `theme_share_by_month` (B2.2) and `theme_share_by_segment` (B2.5), grouped by
  the review's `segment` (Phase 7a);
  `pipeline/` —
  `warehouse.py` (the one place that knows DuckDB from Snowflake), `build.py`
  (raw→staging→marts; the review load stamps `segment`;
  `write_classifier_quality` fills the B2.4 mart; `write_classified_reviews` +
  `build_theme_share_marts` fill B2.2/B2.5, run by the classify step and
  excluded from the generic marts loop), `cli.py`/`__main__.py` (the validating
  `make` entry),
  `sql_lint.py` (the portability/clock denylist the tests use),
  `metrics.py` (reviews per month — a pinned query, not a mart; folds into
  B5.2 in Beat 5), `label_sample.py` (the `make label-sample` draw — reads
  `stg_reviews`, writes the gitignored labeling sheet; Phase 5a).
  `fixtures/synthetic/` — hand-written fake reviews, read-only after Phase 1;
  `fixtures/anchors/` — the brief's §6 public figures with source URLs, one
  row per snapshot with its profile, segment, channel and the stat-row
  figures (frozen in Phase 1, re-frozen in Phase 3a; seeded into
  `platform_snapshots` in every rebuild but `ROWS=none`, tagged Documented);
  `fixtures/app-store/` — a hand-written capture of the App Store feed in its
  exact shape: three pages, their meta files and the host's real robots rule
  (frozen in Phase 2, robots re-frozen in 3a); `fixtures/listings/` — a
  hand-written store listing page with its machine-readable rating block
  (frozen in Phase 3a);
  `fixtures/opinion-assurances/` — a hand-written review profile in the page's
  microdata shape, three pages of a fake, nameless profile (frozen in Phase
  3a); `fixtures/trustpilot/` — a hand-written authorized export in
  webscraper.io's column shape, four reviews of a fake, nameless profile
  (frozen in Phase 3c). Every set carries a `MANIFEST.sha256`; `ROWS=samples`
  runs each through its real parser.
- `ingest/` — the scrapers. A *capture* is one run's saved copy of the pages
  exactly as they arrived, with each page's address and time beside it and the
  robots file they were checked against. `politeness.py` (the good manners of
  a fetch in one place: read robots.txt first, say who we are, wait between
  requests, the hosts we may contact), `robots.py` (the robots.txt matcher,
  RFC 9309: `*`, `$`, longest match wins, Crawl-delay; matched directly, in
  linear time), `sources.py` (every source as one declaration: platform,
  host, parser, page addresses, cache directory, profile / segment / channel,
  and whether its site lets us fetch it — the one place a brand-carrying
  address may appear; the one binding of the cache root), `parsed.py` (what
  every parser hands back and how it refuses; the one place the snapshot
  measures and the review ratings — half-steps 1 to 5 — are declared with
  their bounds), `captures.py` (reads captures
  back for any parser; the meta checked against the source's declared host),
  the parsers — `app_store.py` (the review feed), `listing.py` (a store or
  platform page's rating block, one snapshot row), `opinion_assurances.py`
  (a profile page's schema.org microdata: review rows and one snapshot row),
  `trustpilot.py` (a profile's reviews from an authorized export in
  webscraper.io's column shape: review rows, no snapshot) — and `fetch.py` (the
  only `httpx` import; writes captures under `data/cache/<platform>/<source>/`).
  Trustpilot has TWO sources in `ingest/sources.py`, the App Store feed/listing
  split: `fr-digital-first-trustpilot` *(Phase 3b)* is the hand-read snapshot
  (not fetchable — robots disallows our crawler; its 3.9/1,072 rating and count
  are read into `manual_snapshots.csv`), and `fr-digital-first-trustpilot-
  reviews` *(Phase 3c)* is the review corpus, read from a written-authorized
  OFFLINE export (`parser=trustpilot`, `fetchable=False` — the crawler still
  never runs; the export is saved as a capture and read from disk). A live
  fetch and a scheduled refresh stay deferred (BACKLOG). *(Phase 5a)*
  `classify/` — `labels.py` (the closed seven-label set + `review_id`),
  `split.py` (the `sha256(review_id) % 5` held-out split), `eval/` (the ONLY
  reader of the hand-labeled answer key: `labels_io.py`, `precision.py` — the
  tuning-fold scorer — `gate.py` — the held-out precision+recall scorer (Phase
  6b) — and `labels.csv`, carrying the synthetic corpus's ground
  truth since Phase 5b). *(Phase 5b)* `rules.yaml` (the patterns, one group per
  emitting label), `rules.py` (load + word-start match → `(review_id, theme)`
  rows); *(Phase 6a)* `llm.py` (the ONE model call site: lazy `anthropic` import,
  strict closed-set parse of the reply, `None` decider when no key), `cache.py`
  (the gitignored, text-free decision cache under `data/classify/`, keyed
  `(review_id, prompt_version, model)`), `combined.py` (`classify_all`: rules +
  the model for what they left `unclassified` → one row per review × theme,
  Python-only, no mart). *(Phase 7b)* `opendata/` — open-data ingest and the
  claim-cost fit, its own package (DAMIR names no insurer, so no brand token; it
  is not `ingest/`, the review scrapers, nor Phase 8's `models/`): `sources.py`
  (the one Open DAMIR declaration — dataset URL, the `PRS_REM_MNT` column, the
  `;` delimiter, the `YYYY-MM` shape, the cache dir derived from the one
  `CACHE_ROOT` binding), `fetch.py` (the developer-run bulk download over stdlib
  `urllib`, identifying header from `ingest/politeness.py::IDENTIFYING_HEADERS`),
  `slice.py` (the guarded read of the reimbursed-amount column — positive
  numbers only, drop-and-count — and the systematic fixture draw), `fit.py` (the
  log-moments lognormal fit + goodness-of-fit deciles; writes the tracked fit
  artifact). *(Phase 8)* `models/` —
  `cost_model.py` (`FORMULAS`), `guardrail_sim.py`. *(Phase 9)* `study/` —
  Metabase setup + the HTML export. *(Phase 10)* `dags/friction_ledger.py`.
  `fixtures/damir/` — a small, real, brand-free slice of Open DAMIR's
  `PRS_REM_MNT` column with its `MANIFEST.sha256`, drawn by `make sample-damir`,
  read-only after Phase 7b; the fit CI reproduces offline.
- `data/` — gitignored working output (corpus, captured pages, `*.duckdb`);
  `data/snapshots/` is one tracked subtree: `manual_snapshots.csv`, the
  figures a person read off a page whose terms forbid a robot (a declared
  source name, a day, five numbers and the word `page`; it carries no address
  and no person's name), loaded as Measured; and `fetched_snapshots.csv`, the
  weekly cron's fetched figures (a source slug, the capture's instant and the
  five figures; origin `fetch`, also Measured, also no address and no body).
  `data/damir/` (Phase 7b) is the other tracked subtree: `claim_cost_fit.csv`,
  the numbers-only lognormal fit (`mu`, `sigma`, `n` and the goodness-of-fit
  deciles) Phase 8 reads; the raw fetched month under `data/cache/damir/` stays
  gitignored.

## Commands (macOS, uv)

`make help` lists them. Each later phase adds its targets here in the same PR.

- `make setup` — `uv sync`, `pre-commit install`
- `make test` — pytest; offline, no services, no key
- `make lint` — ruff via pre-commit (rewrites files; never inside a gate)
- `make check-docs` — links/anchors, named make targets, banned words,
  glossary size, BACKLOG count (`scripts/check_docs.py`)
- `make check-backing` — BACKING rows ↔ `sql/marts` files ↔ tags ↔ sources ↔
  `SPEC.md` citations (`B<beat>.<n>` both ways)
- `make review-gate [SPEC=specs/<f>.md] [BASE=main]` — test + ruff (read-only)
  + check-docs + check-backing + fixtures; with SPEC, Evidence ids and
  Record-updates files. One line per check, exit 1 on FAIL, 2 on a refused
  SPEC/BASE. `/review-round N` runs it first.
- `make rebuild [TARGET=duckdb] [ROWS=captured|none|synthetic|samples]` —
  build the warehouse from raw (DuckDB; Snowflake defers to Phase 10), print
  reviews per month, then classify `stg_reviews` and print the outcome (reviews
  / theme rows / positive / `unclassified` — the "not yet classified" band). The
  classifier is the rules plus, only when `ANTHROPIC_API_KEY` is set and only for
  the reviews the rules left `unclassified`, one model call each (cached in the
  gitignored `data/classify/decisions.csv`); with no key those reviews stay
  `unclassified` and the run is still green (Phase 6a). It then grades the
  classifier on the held-out fold (fold 4) and writes the `classifier_quality`
  mart (B2.4, precision + recall per label, Measured), printing a one-line gate
  summary; the mart reflects whatever classifier ran, so with no key it is
  rules-only and honest (Phase 6b). It also persists the classification to
  `stg_classified_reviews` and builds the two theme-share marts —
  `theme_share_by_month` (B2.2) and `theme_share_by_segment` (B2.5), the share of
  each theme by segment, `unclassified` shown as its own band; the marts group by
  the review's `segment` (stamped at load) and reflect whatever classifier ran,
  so the no-key run populates them rules-only and honest (Phase 7a). `ROWS` names
  what is
  loaded; each input builds its own database file, so a sample never lands in the
  corpus. The default,
  `captured`, loads the anchors, the hand-read rows in
  `data/snapshots/manual_snapshots.csv`, the fetched series in
  `data/snapshots/fetched_snapshots.csv` and every capture under `data/cache/`
  (with no capture it says so); `none` runs it end to end with zero rows;
  `synthetic` loads the review fixture and the anchors; `samples` runs every
  frozen sample through its real parser (CI does). A raw table already in the
  file must be the one its `sql/raw/` file declares — name, type and
  nullability, column by column in the file's order, read from the engine's
  own catalog; otherwise the rebuild refuses naming the column and both sides,
  since `create table if not exists` would keep the old column and the engine
  would cast into it silently (`make confirm reset` first). Each `sql/raw/`
  file holds exactly one table definition, so nothing else in the file can run
  while that check happens. The file a rebuild writes is always the input's
  own, `friction_ledger[.<input>].duckdb` under `data/`. The Phase 3a DONE
  command is `make rebuild && make idempotency-check ROWS=captured`.
- `make idempotency-check [TARGET=] [ROWS=synthetic]` — rebuild twice, diff
  per-table row counts (the run-twice property as a command); same `ROWS`
  values as `rebuild`, but this one defaults to `synthetic`; pass
  `ROWS=captured` to prove it on real rows.
- `make scrape [SOURCE=<declared name>]` — NETWORK, developer-run, never by an
  agent: fetch each declared source's pages (a review feed, a review profile,
  a store listing) into a new capture under `data/cache/<platform>/<source>/`,
  robots.txt first and every page checked against it, ≥ 2 s apart per host
  (more if the site asks), identifying User-Agent, no proxy, no retry, at most
  60 pages per source. Needs the `confirm` goal before it in the same
  invocation, `make confirm scrape`, as `reset` does (a goal cannot come from
  the environment; a variable's "command line" origin can, through
  `MAKEFLAGS`). A plain run skips, with one line, any source we have
  recorded as one not to fetch (its robots file or its terms say no; the
  reason and date sit beside the source in code and in DECISIONS). It refuses
  — exit 2 — a source named by `SOURCE=` that we do not fetch, one with no
  page address filled in, and one whose page robots.txt disallows.
- `make record-snapshots` — read the captures already on disk under
  `data/cache/` and append each fetchable source's fresh snapshot figures to
  the tracked `data/snapshots/fetched_snapshots.csv` (numbers only: a source
  slug, the capture's instant and the five figures — the address and
  attribution come from the declaration, so no brand and no review body enters
  the file). Offline and non-destructive, so no `confirm` gate; idempotent
  (recording the same capture twice writes no new row). The weekly workflow
  runs it after `make confirm scrape`; `rebuild ROWS=captured` reads the file.
- `make label-sample N=<n>` — draw N reviews for a person to hand-label. The
  draw is written to the gitignored `data/label_sample.csv` (`review_id,
  source_url, text`), read from the built corpus's `stg_reviews`; the reviews
  are taken in `sha256(review_id)` order, so the draw is deterministic and a
  larger N is a superset. N is a positive ASCII integer (validated in Python;
  the output path is fixed, not built from N).
  Offline and non-destructive, so no `confirm` gate; a warehouse with no
  `stg_reviews` writes a header-only sheet and says so. The person appends
  `(review_id, theme)` rows to the tracked, text-free `classify/eval/labels.csv`
  offline — the answer key, read only by `classify/eval/` (Phase 5a).
- `make classify-eval` — the rules classifier's report: rebuild the synthetic
  corpus, run the `rules.yaml` patterns over its `stg_reviews`, and print
  per-theme precision on the four tuning folds (`sha256(review_id) % 5 != 4`)
  plus the share of reviews the rules decided (vs left `unclassified` for the
  model). Offline, no variable, no `confirm` gate; it grades against the
  synthetic ground truth in `labels.csv` and never reads the held-out fold —
  that is Phase 6's gate. `make test` pins the numbers (Phase 5b).
- `make fetch-damir [MONTH=YYYY-MM]` — NETWORK, developer-run, never by an
  agent: download one month of Open DAMIR (France's public aggregated
  reimbursements) into the gitignored `data/cache/damir/`. A plain bulk GET over
  stdlib `urllib` (no key, no account; `ingest/fetch.py` stays the only `httpx`
  import), identifying User-Agent, no proxy, no retry; a re-fetch overwrites the
  same file. Needs `make confirm fetch-damir` in the same invocation, like
  `scrape`. `MONTH` is a closed `YYYY-MM` shape validated in Python; a national
  month is gigabytes, so this never runs in CI (Phase 7b).
- `make sample-damir [MONTH=YYYY-MM] [N=1000]` — offline, developer-run: draw a
  small, representative fixture from a cached month — every k-th valid
  `PRS_REM_MNT` across the whole file (systematic, no RNG, so it is not a biased
  corner) — into the tracked `fixtures/damir/` with its `MANIFEST.sha256`. No
  `confirm` gate; it fetches nothing and deletes no data (Phase 7b).
- `make fit-damir` — offline, deterministic: fit a lognormal to `fixtures/damir/`
  by log-moments (`mu = mean(ln x)`, `sigma = population-std(ln x)` — closed-form,
  no optimizer, no clock, no RNG) and write the tracked `data/damir/
  claim_cost_fit.csv` (`mu`, `sigma`, `n` and the goodness-of-fit deciles Phase 8
  reads). Prints the fit and the fit-vs-real table. A missing fixture is a clear
  message and exit 1 (Phase 7b).
- `make confirm` — arms the destructive or network target that follows it in
  the SAME invocation and nothing else: `make confirm reset`, `make confirm
  scrape`, `make confirm fetch-damir`. The recipe stamps its make process's id;
  the gated target passes
  its own and runs only when the two are one process; the stamp is consumed
  either way, so an earlier `confirm` confirms nothing later. `confirm` arms
  only when `reset`, `scrape` or `fetch-damir` follows it — `make confirm help`
  refuses and
  leaves no stamp — and only from the goal list make itself built (a
  `MAKECMDGOALS` value from the environment, `MAKEFLAGS` or the command line
  has another origin and is refused). The stamp is written only when none is
  there, so a file already sitting in `data/` makes `confirm` refuse rather
  than overwrite it. The gate holds against a variable definition, an
  environment value, `MAKEFLAGS`, a stale invocation and a typo. It does not
  hold against an environment that chooses what make reads or runs
  (`MAKEFILES`, `PATH`), or against a same-user process writing `data/` while
  make runs (the spec's Threat model says so); goals run in order even under
  `make -j`.
- `make reset [TARGET=duckdb]` — DESTRUCTIVE: drop every DuckDB file this repo
  built, the corpus and one per rebuild input; needs `make confirm reset` (no
  variable and no environment value counts).

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
- Formulas are data: `models/cost_model.py::FORMULAS` is the only place a
  formula is written; the study renders from it; a test pins the outputs.
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
  appear only as sourced data points. Paraphrase, link, no personal data.

## Writing rules (brief §2.3)

- Two layers everywhere: the first 2–3 sentences of any section or panel are
  for a non-technical reader; technical detail follows under a signpost.
  Rigor is never removed to simplify — it moves one layer down.
- Name things by what they mean, not what they are.
- One glossary, ten terms max, one sentence each with an everyday example.
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
  files, stop. A finding outside the phase is a BACKLOG candidate in the
  report, never a fix in this diff.
- Build on the synthetic fixture first, prove correctness, then run on real
  scraped rows.
- `fixtures/` is read-only after Phase 1. Re-freezing is a deliberate change
  with a DECISIONS entry and a `Freeze:` line in the spec.
- At each phase exit: run the coherence audit, review BACKLOG.md for due
  rows, append the "Delivered" paragraph to the spec.
- Stack surprises: check official docs before working around; log under
  DECISIONS.md → Gotchas.
- Do not add a feature that surfaces in none of the five parts.
- Destructive commands (dropping a DuckDB file, truncating a table): only via
  a `make` target that refuses unless the `confirm` goal precedes it in the
  same invocation (`make confirm reset`) — a goal, never a variable, since
  `$(origin)` cannot tell a `MAKEFLAGS` definition from the command line;
  tested against the installed make.
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
  closing summary that repeats the middle. A one-line statement of what the
  next step produces is not a restatement; the report format below is the
  recap.
- One sentence if it fits. Explanations ≤ 4 sentences.
- The banned-word list above applies to chat too. Show the property.
- Code comments only where the code can't say it. One-line docstrings unless
  behavior is non-obvious.
- Reports after a task: files touched, commands run, result, open risks, next
  step. Nothing else.

## Working with the model (Fable 5.1 or Opus 4.8)

The session model is chosen with `/model`. The four diff reviewers pin
`model: claude-opus-4-8`; `senior-architect` and `coherence-auditor` run on
the session's model (`model: inherit`); all six pin `effort: high` in
`.claude/agents/*.md`, so a session switch changes only the two that follow
it. The classifier's model (`classify/llm.py`, Haiku 4.5) is a data-path
setting, not this section's subject. Source for the behaviours below: the
Fable 5.1 and Opus 4.8 prompting guides, read 2026-09-05 (DECISIONS →
Gotchas).

**What the session does, on either model**

- Effort. The session runs at `high` (`effortLevel` in the user settings);
  the developer drops to `medium` for wording sweeps and record updates. A
  long deliverable — a spec, the study export, this file — is written at
  `high`, never `xhigh`/`max`, where the draft is written twice (as
  reasoning, then as output).
- Batch the reads. Before a tool call, list what the step needs, then request
  every item that does not depend on another's result in one response.
- Edit, do not regenerate. CLAUDE.md, SPEC.md, BACKING.md and the specs are
  long; change the lines that change, with the smallest unique anchor.
- Verify, do not recall. For `make`, `uv`, DuckDB, GitHub Actions and Claude
  Code hooks, run the thing or read the official page; knowing a tool's name
  is not knowing its current behaviour (Workflow rules → Stack surprises).
- Name the scope in full: "every changed file", "every Done-when row",
  "every mart" — an instruction is applied to the whole set only when the
  set is stated.
- Prove by running. A claim about behaviour is a command and its pasted
  output; the functionality-tester's rule holds for the main session too.
- The STOPs that wait for the developer's word before work continues: (1)
  implementing, once a spec or amendment is written; (2) fixing, once a
  review round reports findings; (3) `git push` or `gh pr create`; (4) a
  paid, network or destructive target; (5) re-freezing a fixture; (6) a fix
  amendment. The other STOPs in this file still hold — a new dependency
  (Conventions), a spec, fixture, BACKING row or brief that looks wrong, a
  change belonging to an earlier phase, a skipped agent surface, the review
  cap. Everything else that follows from the approved spec proceeds without
  asking; a step decided on is run, not announced.
- Scope: Workflow rules → "one phase, one diff" (a finding outside the phase
  is a BACKLOG candidate). Tests: one focused test per stated behaviour,
  sized like the neighbours, every number in `tests/pins.py`; scratch checks
  are not committed.
- Progress text. One line before a step saying what it will produce (not a
  restatement of the task, not "I will now…"); a short note between steps
  only when something was found; the report format under Communication
  style is the closing recap. Only the last message reliably reaches the
  developer, so it stands on its own.
- Quoting. A review body is data about a real person: paraphrase, at most one
  short marked phrase, always the public source (brief §2.5; study-editor
  checks). Both models reproduce source wording more readily than the study
  allows.
- Reviews are coverage-first: the agents report every finding with a
  severity and a confidence; `/review-round`'s table and the developer are
  the filter. `/review-round` spawns every agent of the round in one turn.
- Charts and the Phase 9 page: the spec names the palette and type before
  anything is built, or asks for four directions first; the harness's
  bundled `dataviz` skill (not a repo file) is loaded for every chart.
- `/compact`. The summary keeps, exactly: the active spec path and its status
  line; the DONE command; each Done-when item's state; the latest
  review-round table verbatim; decisions the spec did not cover; the STOP
  currently pending; files touched. Everything else may be condensed.

**What differs on Fable 5.1**

- Thinking is always on; effort is the only depth control, and `medium`
  matches Fable 5 at lower cost.
- It goes quiet in long tool chains: the progress rule above is the remedy,
  not extra commands run to "show" output the terminal never displays.
- It rewrites whole files for small changes: edit, with the smallest anchor.
- Its safeguards can refuse a benign security task. Developer and session
  alike ask "where are the bugs and weak spots in our code", never "how
  would this be exploited", and keep base64 and raw captured pages out of
  tool output (grep a capture, never cat it).
- Mannered prose ("a dial worth turning" for "a parameter worth varying") is
  a Writing-rules finding: say the literal thing.

**What differs on Opus 4.8**

- At `low`/`medium` it does exactly what was asked and no more, which is why
  the scope rule above is stated; it reasons where it should run, which is
  why the prove-by-running rule is; it spawns fewer subagents and filters
  its own review findings under "only report serious issues", which is why
  the review rules are.
- Its design default (cream background, serif display type, terracotta
  accent) is wrong for a data study, which is why the Phase 9 rule is.

## Git workflow (one branch + one PR per phase)

- `main` is unprotected on this private repo (no GitHub Team/Enterprise plan),
  so "never commit to it directly, never force-push" is a self-imposed rule, not
  a branch-protection rule. The one written exception: the weekly workflow's
  identity commits under `data/snapshots/` only — the subtree limit comes from
  the commit staging only `git add data/snapshots/` (no branch-protection rule
  backs it; `persist-credentials: false` is a separate guard that keeps the
  write token off `.git/config`). DECISIONS → Gotchas; revisit if the repo goes public
  or onto a paid plan.
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
  `make rebuild ROWS=synthetic`, `make idempotency-check` and the same two
  with `ROWS=samples` (offline, DuckDB, no key, no fetch). Mergeable only
  when CI is green and the surface's agents have run.
- The developer merges (squash), never Claude. After merge: `git checkout
  main && git pull`.
- Tooling changes (agents, skills, hooks, this file's rules) on
  `tooling/<slug>` from main: no spec, the gate plus the surface's agents,
  never mixed with a phase.
- Hotfixes on `fix/<slug>` from main, same rules. Never mix two phases in a
  PR; a needed change in an earlier phase is a STOP and its own fix PR.

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
paragraph, `docs/PLAN.md` §2, DECISIONS, BACKLOG. The stamp the main session
writes after the developer's disposition: `Challenged: <YYYY-MM-DD>, round
<k>, spec <8 hex> — <verdict>`, unbolded, at line start, under the spec's
status line; the hex is the hook's `--spec-hash` of the spec's Invariants and
Done-when sections, so an amendment to either makes the stamp stale.

Rules that hold across the loop:

- A skill and its agent read the same text (`skills:` preload): the bar the
  code was written to is the bar it is reviewed against. The skill is the
  only copy of a standard; the agent names its sections and how to report.
- `senior-architect` judges plans and never runs inside a review round; the
  reviewers judge diffs and never re-judge the plan.
- One reminder per reason at each entry point — the `challenge-gate` hook
  while the spec is edited, `/phase-start` and `/review-round` when a round
  begins — and none of them blocks; the developer decides.
- The three standards are `user-invocable: false`: standing instructions
  while a matching file is being written, not commands.

## Project tooling

Index only. All agents are report-only by contract: none carry Write/Edit
(one carve-out: functionality-tester may `git worktree add` a throwaway
checkout under `mktemp -d`, hand-mutate THERE, and remove it). Findings are
fixed in the main session or explicitly accepted — never auto-fixed.

- `run-tests` hook — `.claude/hooks/run-tests.py` (tracked); after any `.py`,
  `.sql`, `.yaml` or `.yml` edit in this repo, runs pytest and blocks on red;
  "no tests collected" is a skip. It runs the checked-out branch's tests on
  your machine with your HOME; the reduced environment keeps environment
  credentials out of the suite and nothing else (the hook's alone: the gate and
  CI run the suite with the full environment; Phase 6's no-key test is the
  durable guard). Before letting Claude edit on
  an inbound branch, read its diff of `.claude/hooks/`, `tests/conftest.py`,
  `pyproject.toml` and `Makefile` — the hook fires before any review round.
  Wiring is local-only by design: copy into the gitignored
  `.claude/settings.local.json`:
  `{"hooks": {"PostToolUse": [{"matcher": "Write|Edit|MultiEdit|NotebookEdit",
  "hooks": [{"type": "command", "command": "python3
  \"$CLAUDE_PROJECT_DIR/.claude/hooks/run-tests.py\""}]}]}}`.
- `challenge-gate` hook — reminds you to run `/challenge` on a spec that has
  not been challenged, or whose stamp predates its Invariants or Done-when,
  and never blocks. After an edit to a `specs/phase-*.md` whose status is not
  DELIVERED and which carries no current `Challenged:` stamp, it prints one
  line (on every such edit); before `ExitPlanMode` it answers
  `ask` on every plan, with the plan's own claim in the reason, so the
  developer sees the claim rather than the hook trusting it. Fail-open, and
  `ask` is the only decision it ever emits; `tests/test_challenge_gate.py`
  pins it. How it is wired: `.claude/hooks/challenge-gate.py` (tracked), a
  second entry in the same local PostToolUse group as `run-tests` plus a
  PreToolUse group with `"matcher": "ExitPlanMode"`; whether that matcher
  fires on this build is unverified until the first plan-mode exit
  (BACKLOG).
- `block-secrets` hook — `~/.claude/hooks/block-secrets.py` (user-level,
  already wired); blocks writes containing secret-looking values.
- `senior-architect` — devil's-advocate review of a plan, spec, amendment or
  decision: steel-man first, severity-tagged findings each with a concrete
  alternative and its cost, a "what would have to be true" block, an advisory
  verdict. Report-only; preloads `architecture-fit`; runs via `/challenge`.
- `code-reviewer` — diff review in three passes: this file's rules
  (deterministic first, provenance, tags, formulas, portability, allowlist,
  scope), the spec's Invariants, then senior craft (preloads `code-craft`).
  Coverage-first: every finding with a severity and a confidence; the round
  table filters.
- `security-reviewer` — mandatory when CI, `.env`, a scraper, the model call,
  Snowflake, the weekly commit, `.claude/hooks/`, `.claude/settings*.json`, or
  a destructive target is touched; this repo's surface plus the secure-coding
  classes it can exhibit (preloads `secure-by-construction`).
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
  BACKING rows in scope, warn if unchallenged, run the gate, stop.
- `/challenge [target]` — resolve the plan (a spec path, a DECISIONS anchor,
  or the plan in the conversation), gather the standard, spawn
  `senior-architect`, print the report verbatim and the per-finding
  disposition line, STOP.
- `code-craft`, `secure-by-construction`, `architecture-fit` — the three
  standards under `.claude/skills/`, `user-invocable: false` and path-scoped:
  they load while the matching files are written and are preloaded into the
  agent that checks the same surface.
- `strategic-compact` skill — user-level; suggests /compact at breakpoints.

## Current status

**Tooling — the review stack** (`tooling/review-stack`, no spec: not a phase,
2026-09-05): CLAUDE.md gains "Working with the model" (Fable 5.1 / Opus 4.8)
and "How the tooling fires across a phase"; a `senior-architect` agent and the
`/challenge` skill (a devil's-advocate round on a plan before it is built, with
the `challenge-gate` hook as the reminder); three path-scoped standards
(`code-craft`, `secure-by-construction`, `architecture-fit`) preloaded into the
agent that reviews the same surface; code-reviewer and security-reviewer
rewritten coverage-first with a craft pass and the secure-coding classes this
repo can exhibit; the four diff reviewers pinned to `claude-opus-4-8` at
`high`, `senior-architect` and `coherence-auditor` on `inherit`, also at
`high`. Round 1 of its own review (5 agents, 30 rows) fixed in full. Pilot:
`/challenge` on the Phase 8 spec before it is approved.

**Phase 7b — open data: DAMIR slice + fitted claim-cost distribution** merged to
`main` (PR #15, 2026-09-05; spec `specs/phase-7b-open-data.md`, APPROVED
2026-09-04; amendments A1 + A2 2026-09-05): fixture fetched and frozen, fit
pinned, review round done. The open-data half of the Phase 7 split (7a merged, PR #14). New
`opendata/` package: `make fetch-damir` (network, developer-run, `confirm`-gated)
downloads one Open DAMIR month over stdlib `urllib` into the gitignored
`data/cache/damir/` (the portal serves `A<YYYYMM>.csv.gz`; the cache keeps that
name); `make sample-damir` draws a small, representative systematic fixture of the
`PRS_REM_MNT` column into `fixtures/damir/`; `make fit-damir` fits a lognormal by
log-moments (`mu = mean(ln x)`, `sigma = std(ln x)` — closed-form, no optimizer,
no clock, no RNG) and writes the tracked `data/damir/claim_cost_fit.csv` (`mu`,
`sigma`, `n` + goodness-of-fit deciles) Phase 8 reads. `GATED` extends to
`fetch-damir`; the identifying User-Agent header moved to
`ingest/politeness.py::IDENTIFYING_HEADERS` so the urllib downloader and the httpx
crawler identify us once. **Amendment A1:** the slice keeps only the legal
reimbursement (`PRS_REM_TYP ∈ {0,1}`; type ≥ 2 is a *part supplémentaire*, dropped)
— a two-column declared shape, the fixture carries both columns so the filter is
reproducible offline. **Amendment A2:** `slice.py` reads a file by its gzip magic
bytes, so the gzipped month and the plain fixture read through one path and
`fetch-damir → sample-damir` needs no manual decompression. The frozen fixture is
July 2025 (`A202507`), a systematic `N=5000` draw (mu 3.809814, sigma 2.187981;
sigma within 0.04 % of the full-population value). **No mart, no BACKING flip:**
B3.3 (`cost_model_params`) and B4.3 (`guardrail_sim`) stay Pending — their marts
are Phase 8; 7b lands only the upstream fixture + fit they consume. No new
dependency. The suite is green with no key (the fit is offline arithmetic, no model
on this path). DONE command: `make fit-damir && make idempotency-check
ROWS=synthetic && make check-backing && make test`.

**Phase 7a — findings marts: theme share** merged to `main` (PR #14,
2026-09-05): `classify_all`'s output persisted to `stg_classified_reviews`, and
`theme_share_by_month` (B2.2) + `theme_share_by_segment` (B2.5) count it, grouped
by the load-time `segment` (amendment A1), tagged Measured with `unclassified` as
its own band. The corpus is all `digital-first`, so the "vs traditional" half is
empty (BACKLOG).

Phase 6b (held-out eval gate + `classifier_quality` mart, B2.4) merged to `main`
(PR #13, 2026-09-04): `classify/eval/gate.py` scores precision + recall per label
on the held-out fold alone; the first Python-fed mart, filled by the CLI classify
step; the no-key run populates it rules-only and honest.

Phase 6a (model fallback + graceful degradation) merged to `main` (PR #12,
2026-09-04): the one model call site (`classify/llm.py`, `MODEL =
claude-haiku-4-5`, strict closed-set parse, no key → no decider, `ModelError` on
paid-path API errors), the gitignored text-free decision cache, and
`combined.py::classify_all`; `make rebuild` runs the classify step; the no-key run
is green (durable `tests/test_no_key.py`). `anthropic` (1.3.0) made a direct
dependency; the labels-isolation grep widened to every code surface.

Phase 5b (the rules layer) merged to `main` (PR #11, 2026-09-04). Phase 5a (label
sample + the labels wall) merged (PR #10, 2026-09-04). Phase 4 (the weekly cron)
merged (PR #8, 2026-09-03); the docs hotfix merged (PR #9, 2026-09-04). (Earlier
phase and amendment history is in each spec and DECISIONS.)

Open BACKLOG rows: **34**.

(Update this section at the end of every working day.)
