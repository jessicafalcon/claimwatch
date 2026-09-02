# Phase 3a — Snapshots and the remaining polite sources (PROPOSED)

Contract for the `phase-3a-snapshots` branch. Source: PROJECT_BRIEF.md §9
Phase 3 (scraper fleet + snapshots), split by `docs/PLAN.md` §5 into 3a (this
phase: `platform_snapshots` seeded from the §6 anchors, the polite sources) and
3b (Trustpilot, its own session). Depends on `phase-2-scraper` merged (PR #4).

**Status: PROPOSED — do not start until approved.** No new dependencies:
every parser here is stdlib `json` and, if a page has no machine-readable
block, stdlib `html.parser`; `pyyaml` stays pre-approved and unused (nothing
here is a rules file); anything else is a STOP-and-ask. No pandas on any
pipeline path.

**Decisions the developer takes at approval** (each pinned below with a
recommendation; the spec is not approvable with one open):
- **D1 — an address that carries the brand.** The App Store id is a number; a
  Google Play package id and an Opinion Assurances profile path are not — they
  spell the insurer. Recommended: a listing address is a sourced data point and
  may sit in `ingest/sources.py` and nowhere else (no prose, comment, commit,
  test name or fixture repeats it; the future hashed naming check excludes that
  field), as the BACKLOG naming row already assumes for URL columns. If
  declined, those sources stay unfilled and are refused before any request.
- **D2 — re-freeze `fixtures/anchors/`.** The seed's `segment` column holds a
  channel (`invited`) for the two app-store rows, and two peer rows share every
  key column. The fixture needs `profile` and `channel` columns and
  `digital-first` on the two app rows (pinned decision 1). A fixture that
  seems wrong is reported, never repaired silently: this is the report.
- **D3 — anchors are Documented.** Brief §6 says the anchors "appear in the
  study with Measured tags"; they are figures a person read off public pages
  at scoping, not captures of ours, so they are Documented (§2.4) and the
  three BACKING rows flip Pending → Documented here. Brief §6 is reworded on
  approval, as §9 was for Phases 1 and 2.
- **D4 — `FIXTURE` becomes `ROWS`** (`captured | none | synthetic | samples`),
  the BACKLOG row's trigger being this spec (pinned decision 5).
- **D5 — the first review source is Opinion Assurances, with at least one
  traditional peer profile declared beside the studied insurer's** — subject
  to the hand checks in Review & stack risk. Which peers, by address, is the
  developer's list.
- **D6 — the page ceiling** `MAX_PAGES` rises from 10 (the App Store feed's
  own cap) to 60 per source per run; each source declares its own cap under
  it.

## Why

Phase 2 built the collector and proved it on a frozen sample, but the one
source it declared asks crawlers not to read its review feed, so the warehouse
still holds no real row. Phase 3a lands three things the study cannot start
without. First, the platform ratings over time — `platform_snapshots` — seeded
from the verified figures in the brief and marked as such, so Beat 1's rating
trend, channel gap and Beat 2's peer context can show numbers with the tag they
deserve. Second, the first real reviews, from the first source whose robots file
allows it. Third, the generalisation Phase 2 deliberately skipped: a source
declares its own parser and cache root, so the second platform costs a
declaration, not a branch. Five BACKLOG rows fall due here and each is closed
or re-deferred. Phase 3b adds Trustpilot; Phase 4 puts the captures on a
schedule so the series accrues.

**Teaching notes (become code comments / README lines at build — CLAUDE.md →
Teaching rule).**
- *A snapshot is a photograph of a public page's headline numbers.* A review
  platform shows, on each insurer's page, an average rating and a review count.
  We do not compute those; we record them as they stood at a moment, with the
  page address and the time. Repeated weekly, the photographs become a time
  series. The brief's §6 figures are earlier photographs taken by hand, so they
  are loaded first and marked as seeded.
- *Machine-readable blocks on ordinary web pages.* Most review and store pages
  carry, inside the page, a small block written for search engines
  (`<script type="application/ld+json">`, in the schema.org vocabulary) that
  states the rating and count as plain data. Reading that block is the boring,
  standard way: it is meant to be read by machines, it has a declared shape,
  and it does not depend on how the page looks. A page with no such block is
  parsed from its HTML to a shape we declare after reading it by hand.
- *One declaration per source.* Each thing we read from is declared once, in
  one file: which platform, which address, which parser, which cache
  directory, which segment and channel it belongs to, and whether its site
  lets us fetch it. Every other module reads those facts from the declaration
  and none knows a platform by name.

## The central constraint

**Phase 1's review shape and Phase 2's load path, manners and run-twice
property do not move: `raw_reviews` keeps its ten columns and `load_reviews`
its guard; every new row of every new table carries the four provenance
columns; the anchors seed the same eight rows in every rebuild input but
`none`; a rebuild reads no clock and no network; the test suite opens no
socket; every live fetch is run by the developer.** Segment attribution joins
on `source_url` by exact value or on a column written in Python, never a
pattern in SQL. No reviewer name is read by any parser. `check-backing` stays
clean: three marts land, three rows flip, zero orphans.

## DONE command

```
make rebuild && make idempotency-check ROWS=captured
```

- `make rebuild` — `ROWS` defaults to `captured`: the anchors seed
  `raw_platform_snapshots` (8 rows, Documented), every capture under
  `data/cache/` is parsed by its source's declared parser into `raw_reviews`
  and `raw_platform_snapshots` (Measured), staging and the three marts are
  built, and the per-table counts print followed by reviews per month for
  every source with rows. Precondition: the developer has run `make scrape
  CONFIRM=yes` once and at least one review source was allowed — that run is
  Done-when 4's proof, and the first time `make scrape` runs green against a
  live host since the robots gate was rebuilt (A1, A6). If no candidate's
  robots file allows its review pages, the phase STOPs on the hand checks
  below, before any code: no real rows, no DONE command (disposition in
  Review & stack risk).
- `make idempotency-check ROWS=captured` — rebuilds the corpus twice into a
  throwaway database and diffs every table's count.
- Also green: `make rebuild ROWS=samples && make idempotency-check
  ROWS=samples` (CI: every frozen sample through its real parser, offline,
  pinned in `tests/pins.py`); `make rebuild ROWS=synthetic && make
  idempotency-check` (Phase 1's line: raw 40 / staging 39, now with
  `raw_platform_snapshots` 8); `make rebuild ROWS=none` (zero rows, every
  table present); `make test`; `make check-backing` (19 rows, 3 marts, 0
  orphans); `make check-docs`.

## Done-when

1. **`platform_snapshots` lands, seeded from the anchors and marked as such.**
   `raw_platform_snapshots` (append-only, natural key `(source, profile,
   captured_at)` + content hash of rating and count) and
   `stg_platform_snapshots` exist; the eight anchor rows load from
   `fixtures/anchors/` with `seeded_from` filled and read back as
   `Documented`; a captured row has `seeded_from` empty and reads back as
   `Measured`; every row carries `source`, `source_url`, `captured_at`,
   `run_id`, `profile`, `segment`, `channel`; a re-seed and a second rebuild
   add no row. *Evidence: row 1.*
2. **Three marts land and three BACKING rows flip; one stays Pending.**
   `sql/marts/rating_trend.sql` (B1.2), `channel_gap.sql` (B1.3),
   `peer_ratings.sql` (B2.3) build from `stg_platform_snapshots`, each row
   carrying its point's tag; BACKING flips those rows Pending → Documented
   with sources of the declared shape; B1.4 `platform_stats` stays Pending
   (one-star share and response lag are not in the snapshot shape — BACKLOG
   row, trigger 3b); SPEC.md's three panels say what they now show; `make
   check-backing` prints 19 rows, 3 marts, 0 orphans. *Evidence: row 2.*
3. **Every source declares its parser, cache root, host, page cap, profile,
   segment and channel; nothing branches on a name.** `ingest/sources.py`
   holds the closed tuple; `pipeline/build.py` loads every declared source's
   captures through the declared parser; the cache root is bound once; a
   capture's meta is validated against its source's declared host; a review
   row's segment comes from `source_pages` (one row per declared page
   address, written in Python at rebuild) joined on exact `source_url`; the
   SQL lint refuses `like`, `similar to` and `regexp` alike. *Evidence: row 3.*
4. **The first real rows.** After the developer's `make scrape CONFIRM=yes`,
   the DONE command prints `raw_reviews` > 0 from the first allowed review
   source, `raw_platform_snapshots` = 8 + the captured listings, the three
   marts populated, and every count unchanged on the second rebuild; a second
   `make scrape` of unchanged pages then adds no raw row. The run is also the
   first live check of the rebuilt robots gate, the per-host interval and the
   Crawl-delay path, on every declared host. *Evidence: row 4.*
5. **The rebuild input is named by what it is, and every frozen sample runs
   offline.** `ROWS` is the closed set `{captured, none, synthetic, samples}`
   (`captured` the default for `rebuild`, `synthetic` for
   `idempotency-check`); `samples` reads every frozen sample under
   `fixtures/<parser>/` through its real parser, in CI; the new samples
   (`fixtures/opinion-assurances/`, `fixtures/listings/`) are hand-written,
   fake and nameless with a MANIFEST; `fixtures/app-store/robots.txt` is
   re-frozen to the real rule and a test reads it through `ingest/robots.py`.
   *Evidence: row 5.*
6. **The matcher is linear, and no parser reads a name.** A robots pattern
   with thirty wildcards against a long non-matching path answers in
   milliseconds and the matching table stands; no parser reads an `author`,
   pseudonym or name field, and the health-details BACKLOG row's trigger (a
   tracked snapshot commit or a published excerpt) is not reached here.
   *Evidence: row 6.*

(6 items. Each is a contract, not a narrative.)

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `tests/test_snapshots.py::test_anchors_seed_eight_documented_rows_with_provenance`, `::test_a_captured_snapshot_reads_back_as_measured`, `::test_reseeding_and_rebuilding_add_no_snapshot_row`, `::test_anchor_row_outside_the_declared_shape_is_refused` (a rating `6.0`, a count `-1`, a segment outside the closed set, a missing column); `tests/test_provenance.py::test_every_raw_table_has_four_provenance_columns` (extended over every `raw_*` table) |
| 2 | `tests/test_marts.py::test_rating_trend_matches_pins`, `::test_channel_gap_matches_pins`, `::test_peer_ratings_matches_pins` (the anchors' rows, `tests/pins.py`), `::test_every_mart_row_carries_exactly_one_tag`; `make check-backing` prints `check-backing OK: 19 rows, 3 marts`; `tests/test_sql_portable.py::test_every_sql_file_is_portable_and_clock_free` over the new files |
| 3 | `tests/test_ingest_layout.py::test_every_source_declares_parser_cache_host_cap_and_attribution`, `::test_no_module_branches_on_a_platform_name` (no `== "app-store"` / `"opinion-assurances"` / `"google-play"` comparison outside `ingest/sources.py` and the parsers' own `SOURCE` constants), `::test_the_cache_root_is_bound_once`; `tests/test_ingest_rebuild.py::test_meta_is_validated_against_the_sources_declared_host`, `::test_every_captured_review_joins_exactly_one_declared_page`; `tests/test_sql_portable.py::test_pattern_matching_is_refused_in_sql` (`like`, `similar to`, `regexp` planted) |
| 4 | The DONE command's output on the developer's machine, pasted into the Delivered paragraph (counts per table, reviews per month per source, `idempotency-check OK`); `make scrape CONFIRM=yes` run twice, the second adding no raw row (`make rebuild` counts unchanged); functionality-tester reruns the DONE command on that cache; the tests of row 3 pin the same path on captures they write |
| 5 | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set`, `::test_idempotency_check_variables_are_a_closed_set` (re-pinned to `ROWS` and the four names); `tests/test_cli.py::test_each_input_builds_its_own_database` (re-pinned); `tests/test_ingest_rebuild.py::test_samples_load_every_frozen_sample_through_its_parser` (pins per sample); `tests/test_fixtures_frozen.py::test_manifests_match` (extended to the two new directories); `tests/test_opinion_assurances_parser.py::test_sample_is_obviously_fake_and_nameless`, `tests/test_listing_parser.py::test_sample_is_obviously_fake_and_nameless`; `tests/test_robots.py::test_the_frozen_app_store_robots_file_disallows_the_sample_feed`; `.github/workflows/ci.yml` runs `ROWS=samples` in place of `FIXTURE=app-store` |
| 6 | `tests/test_robots.py::test_a_pathological_pattern_matches_in_linear_time`, `::test_pattern_matching_and_precedence` (the table, unchanged); `tests/test_opinion_assurances_parser.py::test_author_fields_are_never_read`, `tests/test_listing_parser.py::test_only_the_aggregate_rating_is_read`, `tests/test_app_store_parser.py::test_author_fields_are_never_read` (unchanged); security-reviewer confirms no name in a tracked file and nothing under `data/` tracked or excerpted |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For all snapshot rows, the four provenance columns are non-empty, `profile`, `segment` and `channel` are values from their closed sets, and the row reads back `Documented` iff it was seeded from the anchors and `Measured` otherwise; a re-seed or a second rebuild changes no count. | `tests/test_snapshots.py::test_anchors_seed_eight_documented_rows_with_provenance`, `::test_a_captured_snapshot_reads_back_as_measured`, `::test_reseeding_and_rebuilding_add_no_snapshot_row` — the anchors loaded twice, a capture loaded twice: eight plus one, both times |
| 2. For all rebuild inputs but `none`, the anchors seed the same eight rows and the three marts are byte-identical across two rebuilds under different wall-clock times; a Pending row's mart does not exist. | `tests/test_marts.py::test_marts_are_byte_stable_across_rebuilds` (clock patched to two instants), `::test_rating_trend_matches_pins` and siblings; `make check-backing` (orphans) |
| 3. For all declared sources, the parser, cache directory, host, page addresses and attribution are read from the declaration; no module outside `ingest/sources.py` and the parsers' own constants compares a platform or source name; a capture's meta is accepted iff its `source_url` host is the declaring source's host. | `tests/test_ingest_layout.py::test_no_module_branches_on_a_platform_name`, `::test_the_cache_root_is_bound_once`; `tests/test_ingest_rebuild.py::test_meta_is_validated_against_the_sources_declared_host` — a meta on another allowed host refuses; the allowlist shrunk in a test does not unload a declared source's capture |
| 4. For all captured review rows, `(source, source_url)` joins exactly one `source_pages` row, and for all files under `sql/`, no `like`, `similar to` or regex function appears: attribution is exact-value or Python-written, never a pattern in SQL. | `tests/test_ingest_rebuild.py::test_every_captured_review_joins_exactly_one_declared_page` — a capture under a declared source joins; a page address outside the declaration is counted as an unattributed row and the test fails; `tests/test_sql_portable.py::test_pattern_matching_is_refused_in_sql` |
| 5. For all requests the fetcher makes to any host, the host's robots file was read first and allowed the path under both our group and `*`, the identifying User-Agent is set, the previous request to that host was ≥ 2 s earlier (more if asked), and there is no retry, proxy or rotation; matching a pattern takes time linear in its length times the path's. | `tests/test_app_store_fetch.py` (unchanged, now over a source parameter), `tests/test_fetch_sources.py::test_two_sources_on_two_hosts_keep_two_clocks`, `::test_a_disallow_on_one_host_stops_that_source_only`; `tests/test_robots.py::test_a_pathological_pattern_matches_in_linear_time` — thirty `*` against a 300-character non-matching path under 50 ms |
| 6. For all parsers, no author, pseudonym or name field is read; a page outside the declared shape refuses the whole page naming page, item and field; the listing parser accepts exactly one `AggregateRating` per page; every frozen sample is fake, nameless and hashes to its MANIFEST. | `tests/test_opinion_assurances_parser.py::test_author_fields_are_never_read`, `::test_missing_required_field_refuses_the_page`, `::test_refusal_names_page_item_and_field`; `tests/test_listing_parser.py::test_only_the_aggregate_rating_is_read`, `::test_two_aggregate_ratings_refuse_the_page`, `::test_no_aggregate_rating_refuses_the_page`; `tests/test_fixtures_frozen.py::test_manifests_match` |
| 7. For all `ROWS` values, the set is closed and each input builds its own database file; under `samples`, every declared parser's frozen sample loads through that parser and matches its pins. | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set`, `tests/test_cli.py::test_each_input_builds_its_own_database`, `tests/test_ingest_rebuild.py::test_samples_load_every_frozen_sample_through_its_parser` — a parser with no sample directory is a test failure, not a skip |

## Pinned decisions (do not re-litigate)

- **The snapshot shape, seeded from the re-frozen anchors (D2, D3).**
  `raw_platform_snapshots`: `source` (the platform slug, as `raw_reviews`),
  `profile` (the declared source name — `fr-digital-first` for the studied
  insurer, `peer-<segment>-<n>` for the anchors' anonymous peers), `segment`
  (closed set `digital-first | traditional | digital-challenger`), `channel`
  (`invited | unsolicited`), `rating` (`decimal(2,1)`, 0.0–5.0), `review_count`
  (integer ≥ 0), `source_url`, `captured_at` (text, the anchors' `YYYY-MM-DD`
  or the fetch stamp), `run_id`, `seeded_from` (`PROJECT_BRIEF §6` for an
  anchor, empty for a capture), `content_hash` (rating and count). Natural
  key `(source, profile, captured_at)` + hash, the Phase 1 guard shape;
  `stg_platform_snapshots` keeps the latest hash per key and derives `tag`
  (`case when seeded_from = '' then 'Measured' else 'Documented' end` — an
  exact comparison, portable) and `month` (`substr(captured_at, 1, 7)`). The
  anchors CSV is parsed strictly in Python (`csv`, closed sets, numeric
  ranges; a bad row refuses the seed); `fixtures/anchors/` is re-frozen with
  `profile` and `channel` columns and `digital-first` on the two app rows
  (`Freeze: fixtures/anchors/`, MANIFEST in the diff, DECISIONS entry) — the
  frozen shape has no profile, so two traditional peers collide on every key
  and the app rows carry a channel where a segment belongs. For a captured
  snapshot, `profile`, `segment` and `channel` are written in Python from the
  source declaration. The anchors seed in every input but `none`. Satisfies
  invariants 1 and 2. Rejected: repairing the seed's meaning in staging (`case
  when segment = 'invited'…` — a fixture fixed in SQL); Measured for anchors
  (a person's reading at scoping is a documented public figure, not our
  capture); a Python-side dedup (the guard is the warehouse's, as in Phase 1).
- **Three marts, three flips to Documented, one row stays Pending.**
  `rating_trend` (B1.2): one row per `(channel, segment, source, profile,
  month)`, the latest snapshot in that month with its `rating`,
  `review_count`, `captured_at`, `tag` — the panel shows the unsolicited
  channel and states the sampling bias beside it. `channel_gap` (B1.3): one
  row per `(segment, channel, source, profile)`, the latest snapshot, with its
  tag — invited beside unsolicited for one segment. `peer_ratings` (B2.3): one
  row per `(segment, source, profile)` over the unsolicited channel, the
  latest snapshot, with its tag and date. All three are window-function
  selects over `stg_platform_snapshots` in the `stg_reviews` shape (no
  `order by` at the top level, no clock, no pattern). BACKING: B1.2, B1.3,
  B2.3 flip Pending → **Documented**, source cell
  `` `fixtures/anchors/platform_snapshots_seed.csv` `` plus the platform
  roots the seed names; the flip to Measured is Phase 4's, when scheduled
  captures make the series ours and every seeded point is marked in the chart
  (SPEC.md's panels already say "marked as seeded"). SPEC.md's three panels
  drop "(Pending until…)" and say "Documented for the seeded points; each
  point carries its own tag in the mart"; the header sentence "Today every
  row is Pending" goes. B1.4 `platform_stats` stays Pending: one-star share
  and response lag are not in the snapshot shape; a BACKLOG row triggers on
  3b, whose page carries the star distribution. Satisfies invariant 2 and
  the central constraint. Rejected: one shared `platform_latest` mart under
  three rows (the names are Phase 0b's chart list; three small files read as
  three charts); flipping to Measured on the strength of one live capture (a
  chart is as strong as its weakest displayed point until the seeded points
  are the minority and marked — Phase 4's condition); landing
  `platform_stats` half-filled.
- **A source is a declaration; a parser is declared beside it (BACKLOG rows
  "capture path hardwired" and "`DEFAULT_CACHE` / `ALLOWED_HOSTS`").**
  `ingest/sources.py::Source` (frozen dataclass): `name`, `platform`, `host`,
  `parser` (one of the closed set of parser modules — `app_store` (the feed),
  `opinion_assurances` (review pages, also yielding the page's aggregate as a
  snapshot), `listing` (a store or platform page's `AggregateRating` only)),
  `page_url(n)`, `pages` (≤ `politeness.MAX_PAGES`, now 60 — D6), `profile`,
  `segment`, `channel`, `listing` (the address the id was read from — D1),
  `fetchable`, `terms`, `declared_on`. Each parser exposes `parse_page(body,
  page_url, captured_at, source) -> Parsed(reviews, snapshots)` and names the
  body's file extension (`json` or `html`) and its sample directory
  (`fixtures/<parser-slug>/`). The cache root is bound once
  (`ingest/sources.py::CACHE_ROOT`, `data/cache/`); a source's cache
  directory is `CACHE_ROOT / platform / name`; `pipeline/build.py` and
  `pipeline/cli.py` import it and iterate `SOURCES`, dispatching to
  `source.parser`; `run_id` for a captured row is the capture's path relative
  to the cache root. `read_meta` validates `source_url`'s host against the
  declaring source's `host`, not the live `ALLOWED_HOSTS` (which stays the
  fetch-time allowlist in `politeness.py`, widened to every declared host; a
  test pins the two agree). Attribution for reviews: `source_pages`
  (`sql/raw/raw_source_pages.sql`, one row per declared source × page
  address: `source`, `source_url`, `profile`, `segment`, `channel`,
  `captured_at` = `declared_on`, `run_id`), written in Python at every
  rebuild through the same guard — the closed set of `source_url` values a
  source can produce, so `stg_reviews join raw_source_pages using (source,
  source_url)` is exact-value and a test pins that every captured review row
  joins exactly one. `pipeline/sql_lint.py` gains `like` and `similar to`
  (a declared widening, recorded). Satisfies invariants 3 and 4. Rejected: a
  `segment` column on `raw_reviews` (Phase 1's shape; a design change for a
  join that exact values give); a pattern over `source_url` in SQL (the
  Portability contract); deriving `ALLOWED_HOSTS` from the declarations (a
  circular import, and the allowlist is a fetch-time knob by design);
  attribution through `run_id` (in no mart, by decision).
- **The first review source is Opinion Assurances; Google Play and the App
  Store contribute listings only (D1, D5).** Positions before any fetch,
  each *recalled from general knowledge and unverified until the developer's
  browser check* (Review & stack risk) — a hand check that contradicts a line
  here is a STOP, and the line is corrected at approval:
  (a) `itunes.apple.com` — the feed: disallowed for every crawler, verified
  2026-09-02 (Phase 2); stays `fetchable=False`.
  (b) `apps.apple.com` — the listing page by numeric id: recalled as allowed
  to `*` (the pages are search-indexed) and carrying a JSON-LD block with
  `aggregateRating.ratingValue` and `reviewCount`; declared as a `listing`
  snapshot source for the studied insurer.
  (c) `play.google.com` — the details page: recalled as allowed to `*` and
  carrying JSON-LD `aggregateRating` (`ratingValue`, `ratingCount`); its
  reviews are loaded by an internal call under `/_/`, recalled as disallowed,
  and are not a public feed in any case — so a `listing` snapshot source only,
  reviews recorded not fetchable with that reason as `terms`. Its package id
  spells the brand: D1.
  (d) `www.opinion-assurances.fr` — the insurer profile pages: robots and
  terms unknown; the page shows the review list, the average and the count.
  The parser reads the page's JSON-LD `Review` items if the page carries them
  (`reviewRating.ratingValue`, `datePublished`, `name`, `reviewBody`;
  `author` never read) and its `AggregateRating` as one snapshot row per
  capture; if the page has no such block, a stdlib `html.parser` walk to a
  shape declared from the developer's view-source notes (element, attribute,
  field, for rating, date, title, body, next-page link), settled at approval
  in one paragraph appended here. Declared sources: the studied insurer's
  profile (`profile fr-digital-first`, `digital-first`, `unsolicited`) and
  at least one traditional peer's (`traditional`, `unsolicited`), more at the
  developer's choice — the same parser, another address; profile paths spell
  the brand: D1. A terms clause forbidding automated reading is a STOP for
  reviews (the source is declared not fetchable with the clause as its
  `terms`), whatever robots says.
  (e) Trustpilot — Phase 3b, unchecked here.
  `MAX_PAGES` is 60 (D6): a first capture takes the most recent pages up to
  the source's cap, ≥ 2 s apart (a minute or two per profile); older history
  is not fetched and the review series starts where the capture starts, said
  beside the chart. The manual snapshot path (a figure read by hand, tagged
  Measured) is not built here: a listing whose host refuses is recorded and
  waits for 3b's path. Satisfies invariants 5 and 6. Rejected: Google Play
  reviews through the internal call (not a public feed; recalled disallowed;
  the kind of reading Phase 2 refused); a second User-Agent or a proxy for
  any host (never); a paid review-data API (a dependency and a cost for
  numbers the public page shows).
- **`ROWS` names the rebuild input; `samples` runs every frozen sample (D4,
  BACKLOG rows "`FIXTURE=cache` naming" and "frozen `robots.txt` read by
  nothing").** `make rebuild [ROWS=captured|none|synthetic|samples]` and
  `make idempotency-check [ROWS=…]` replace `FIXTURE`, same closed-set shape
  (validated in Python, never a path), defaults unchanged in meaning
  (`captured` for `rebuild`, `synthetic` for `idempotency-check`);
  `warehouse.database_for` names the files `friction_ledger.duckdb`
  (captured) and `friction_ledger.<input>.duckdb`; `reset` drops that set.
  `samples` reads, for every parser a declared source names,
  `fixtures/<parser-slug>/` as one capture of a sample declaration whose
  `profile`, `segment` and `channel` are the literal `sample` — labels that
  exist only in the samples database. Three sample directories: the existing
  `fixtures/app-store/` (its `robots.txt` re-frozen to the real rule,
  `User-agent: *` / `Disallow: /*/rss/*`, so the frozen capture documents
  why its source is not fetched; `tests/test_robots.py` reads it through
  `Robots.parse` and asserts the sample's page address is disallowed), and two
  new hand-written, fake, nameless ones: `fixtures/opinion-assurances/` (two
  review pages in the page's declared shape, one aggregate, a review shared
  across pages, a last page with no reviews) and `fixtures/listings/` (one
  page per listing host in its JSON-LD shape). Each has a `MANIFEST.sha256`;
  `Freeze:` lines below; malformed variants are built in tests by mutation.
  Every doc, the Makefile, CI and the tests move from `FIXTURE` to `ROWS` in
  one commit; DECISIONS marks Phase 2's `FIXTURE` decision superseded.
  Satisfies invariant 7. Rejected: keeping `FIXTURE` and recording why (the
  name calls the real corpus a fixture, which the study-editor found and the
  writing rule forbids); one `ROWS` value per platform sample (the set would
  grow with every parser; `samples` is one input and CI runs it once).
- **The robots matcher matches directly, in linear time (BACKLOG row
  "wildcard backtracking bound").** `ingest/robots.py::_matches` becomes a
  two-pointer glob match (`*` any run, trailing `$` anchors, everything else
  literal; anchored at the path's start) with no regex, so time is bounded by
  pattern length × path length and a pathological file cannot stall `make
  scrape`. The matching table (`$`, inner `*`, longest match, Allow on a tie)
  is unchanged and its test stands. A new pin: thirty wildcards against a
  300-character non-matching path under 50 ms. Satisfies invariant 5.
  Rejected: a cap on the number of `*` per pattern (a denylist on the input;
  the kind change is the fix); `fnmatch` (translates to the same regex).

(6 pinned decisions.)

## Scope (files)

New code:
- `ingest/sources.py` — `Source`, `CACHE_ROOT`, `SEGMENTS`, `CHANNELS`, the
  parser closed set, `SOURCES` (the Phase 2 source kept as declared; the
  listing sources; the Opinion Assurances profiles — the studied insurer and
  the peers, D1 and D5), `sample_source(parser)`.
- `ingest/listing.py` — the JSON-LD `AggregateRating` parser (one per page,
  strict; `Parsed(snapshots=[one row])`). `ingest/opinion_assurances.py` —
  the review-page parser (JSON-LD `Review` items or the declared HTML shape;
  `author` never read; the aggregate as one snapshot row).
  `ingest/app_store.py` — `parse_page` returns `Parsed`; `read_captures`,
  `read_meta`, `capture_pages` move to a parser-neutral `ingest/captures.py`
  (one reader for every parser, the extension from the parser).
- `ingest/fetch.py` — `scrape(source, …)` reads host, robots address, page
  addresses, cap and parser from the declaration; two hosts keep two clocks
  (already the `PoliteClient` shape). `ingest/robots.py` — `_matches`
  rewritten (pinned decision 6). `ingest/politeness.py` — `ALLOWED_HOSTS`
  widened to every declared host, `MAX_PAGES = 60`.
- `pipeline/build.py` — `INPUTS = ("captured", "none", "synthetic",
  "samples")`; `seed_anchors` (strict CSV → `raw_platform_snapshots`),
  `load_snapshots`, `write_source_pages`; capture loading iterates `SOURCES`.
  `pipeline/cli.py` — `--rows`; the no-captures hint names the cache root;
  `scrape` lists every declared source's host in its prompt.
  `pipeline/warehouse.py` — `database_for(rows)`. `pipeline/sql_lint.py` —
  `like`, `similar to`.
- `sql/raw/raw_platform_snapshots.sql`, `sql/raw/raw_source_pages.sql`,
  `sql/staging/stg_platform_snapshots.sql`, `sql/marts/rating_trend.sql`,
  `sql/marts/channel_gap.sql`, `sql/marts/peer_ratings.sql`.
- `Makefile` — `ROWS` replaces `FIXTURE` (`unexport`, help lines, the two
  recipes). `.github/workflows/ci.yml` — `ROWS=synthetic`, `ROWS=samples`.

Fixtures (frozen this phase; see the `Freeze:` lines):
- `fixtures/anchors/platform_snapshots_seed.csv` re-frozen with `profile` and
  `channel` (D2); `fixtures/app-store/robots.txt` re-frozen to the real rule;
  `fixtures/opinion-assurances/` and `fixtures/listings/` new, each with
  `MANIFEST.sha256`.

New and extended tests:
- `tests/test_snapshots.py`, `tests/test_marts.py`, `tests/test_listing_parser.py`,
  `tests/test_opinion_assurances_parser.py`, `tests/test_fetch_sources.py`
  new; `tests/test_robots.py`, `tests/test_ingest_layout.py`,
  `tests/test_ingest_rebuild.py`, `tests/test_provenance.py`,
  `tests/test_sql_portable.py`, `tests/test_makefile.py`, `tests/test_cli.py`,
  `tests/test_fixtures_frozen.py`, `tests/conftest.py` (`ROWS` scrubbed in
  place of `FIXTURE`), `tests/pins.py` (anchor rows per mart; the new
  samples' counts) extended.

Records (see Record updates): `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`,
`BACKING.md`, `SPEC.md`, `PROJECT_BRIEF.md`, `docs/PLAN.md`, this spec.

Freeze: fixtures/anchors/
Freeze: fixtures/app-store/
Freeze: fixtures/opinion-assurances/
Freeze: fixtures/listings/

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 3a entry: the snapshot shape and the anchors
      re-freeze (D2) and tag (D3); the three marts and the Documented flip;
      the source declaration and parser dispatch; the terms position of each
      candidate under "Scrape politely" (App Store listing, Google Play
      listing and its reviews, Opinion Assurances, with dates and the hand
      check's verdicts); D1 as a standing neutrality decision; the `ROWS`
      rename with a supersede pointer on Phase 2's `FIXTURE` decision; the
      linear matcher; the `like` widening of the lint; Gotchas from the first
      live run
- [ ] `BACKLOG.md` — five rows closed (struck + "DONE Phase 3a"): the
      wildcard bound, the `DEFAULT_CACHE` / `ALLOWED_HOSTS` binding, the
      `FIXTURE=cache` naming, the hardwired capture path, the permissive
      frozen `robots.txt`; rows opened: B1.4 `platform_stats` waits for the
      star distribution (trigger 3b); the weekly run stops at the first page
      with no unseen review (trigger Phase 4); the manual snapshot path for a
      refusing listing host (trigger 3b); the health-details row untouched
      (its trigger is not reached)
- [ ] `CLAUDE.md` — Current status; Commands (`ROWS`, `scrape`'s hosts and
      cap); Repo map (`ingest/captures.py`, `listing.py`,
      `opinion_assurances.py`, the three marts, the two new fixture sets,
      `sql/marts/` no longer empty); Architecture unchanged; BACKLOG count
- [ ] `BACKING.md` — B1.2, B1.3, B2.3 Pending → Documented with sources of the
      declared shape; B1.4 unchanged (Pending, its reason in BACKLOG)
- [ ] `SPEC.md` — the three panels' tag sentences and the header's "Today
      every row is Pending" (a tag change, not a chart change — flagged here,
      approved with the spec)
- [ ] `PROJECT_BRIEF.md` — §6: anchors "appear in the study with Documented
      tags, marked as seeded" (D3); §9 Phase 3 unchanged in meaning
- [ ] `docs/PLAN.md` — §5 row 3a: the DONE command and the sources as built
- [ ] README — none (Phase 9)
- [ ] `specs/phase-3a-snapshots.md` — this spec; the shape paragraph for
      Opinion Assurances if HTML (pinned decision 4d) at approval; the
      "Delivered" paragraph at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

No new target. Three existing targets change shape: `scrape` reaches more
hosts and more pages; `rebuild` and `idempotency-check` take `ROWS` in place
of `FIXTURE`; `reset`'s closed set of files follows the new input names.
Settled shape unchanged: one Python process validates each value against a
closed set, derives every path from the validated name, prompts on a tty,
then acts; every recipe is one line; every user variable reaches Python
unexpanded and single-quoted via `$(call _Q,$(value VAR))` and is `unexport`ed.

**What `scrape` reaches and costs.** Hosts: exactly `ALLOWED_HOSTS` —
`itunes.apple.com` (declared, refused before any request), `apps.apple.com`,
`play.google.com`, `www.opinion-assurances.fr`; a source on any other host is
refused before a request. Per source per run: one `robots.txt` plus at most
`pages` (≤ 60) page requests, ≥ 2 s apart or the host's Crawl-delay up to 60
s — a listing is two requests; a review profile up to about two minutes. Run
twice: the same again into a second capture directory (public pages, no
cost, no key); the second rebuild then adds zero raw rows if nothing changed
(invariant 1 and Phase 2's invariant 3). No credentials: none needed, none
read (`ingest/` never opens `.env`; the test stands). Refused (robots
disallow, a non-robots body, non-200, timeout, a Crawl-delay above the
ceiling): one line naming host, status and address, no retry, exit 2; the
run goes on to the next source. Personal data: review pages carry pseudonyms
and free text, listing pages carry none; every page is archived as served
under gitignored `data/`; no parser reads an author field; nothing under
`data/` is tracked or excerpted in this phase.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `scrape` | `SOURCE` empty → every declared source (refused ones report one line each, the rest fetch); `CONFIRM` empty → prompt on a tty, refuse non-interactively, no request | `SOURCE` refused — a declared name, never a path; the capture directory is derived from the declaration | one literal arg; not a declared name → refused | `unexport`ed; validated in Python; `CONFIRM=yes` from the environment → `$(origin)` = `environment` → refused, no request | `CONFIRM=yes` counts only from the command line | `tests/test_makefile.py::test_scrape_requires_command_line_confirm`, `::test_scrape_source_is_a_closed_set`, `::test_scrape_variables_reach_python_as_one_literal`; `tests/test_cli.py::test_cli_scrape_reports_each_refused_source_and_fetches_the_rest` |
| `rebuild` | `ROWS` → `captured` (zero captures → the anchors only, with a one-line hint) | refused (closed set of four names) | one literal arg; refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set` (re-pinned to `ROWS`), `tests/test_cli.py::test_cli_refuses_bad_fixture_with_exit_2` (renamed to `…bad_rows…`) |
| `idempotency-check` | `ROWS` → `synthetic` | refused | refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_idempotency_check_variables_are_a_closed_set` (re-pinned) |
| `reset` | unchanged: prompt or refuse | n/a (no path taken) | n/a | `CONFIRM=yes` from the environment does not confirm | command line only | `tests/test_makefile.py::test_reset_requires_command_line_confirm`, `tests/test_cli.py::test_reset_removes_only_the_db_and_wal` (the file set re-pinned to the `ROWS` names) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").
The range touches Code (`ingest/**`, `pipeline/**`, `sql/**`, `Makefile`,
`tests/`), Sensitive (`ingest/**`, `.github/workflows/ci.yml`, the network
target) and Prose (`SPEC.md`, `BACKING.md`, `CLAUDE.md`). The union runs:
code-reviewer, functionality-tester, **security-reviewer (mandatory — new
hosts, a new parser of pages written by strangers)**, study-editor
(`SPEC.md`'s panel sentences, `BACKING.md`'s claims, `CLAUDE.md`), and
coherence-auditor at exit.

- **code-reviewer** (triggered): `raw_reviews` and `load_reviews` untouched;
  every new raw table carries the four provenance columns; no clock and no
  pattern in `sql/`; the three marts are window selects with no `order by`;
  nothing branches on a platform name; the cache root is bound once; `ROWS`
  a closed set; the matcher regex-free; the samples frozen; scope (every
  file maps to a snapshot row, a source, a BACKLOG row or a record).
- **security-reviewer** (mandatory): scrape conduct on four hosts — robots
  read first per host, both groups consulted, the interval per host, the
  User-Agent, no retry, proxy or rotation; the terms positions recorded for
  each source and `fetchable=False` where a site says no; D1 honoured (an
  address that spells a brand appears in `ingest/sources.py` only); no name
  or real review in any tracked file (the two new samples are fake by
  construction); `data/` still gitignored and nothing under it excerpted;
  CI still `contents: read` and offline; `.env` never read by `ingest/`.
- **functionality-tester** (triggered): the DONE command on the developer's
  cache; Phase 1's line still green; `ROWS=samples` and `ROWS=none` green;
  the anchors seeded identically under every input but `none`; the
  strict-parse negatives of both new parsers; two captures of unchanged
  pages add no row; a shrunk allowlist does not unload a declared source's
  capture; hand-mutations: read `author`, let a second `AggregateRating`
  through, branch on a platform name, put `like` in a mart, restore the
  regex matcher.
- **study-editor** (triggered): `SPEC.md`'s three panel sentences and the
  header in the two-layer voice; `BACKING.md`'s three flipped claims; the
  sampling-bias sentence still beside B1.2; no insurer named in any prose
  the phase touches.
- **coherence-auditor** at exit: `SPEC` ↔ `BACKING` ↔ `sql/marts` reconcile
  (3 marts, 3 Documented, 16 Pending); no "Today every row is Pending"; the
  Repo map names the new modules and marks `sql/marts/` as populated; every
  `FIXTURE` mention is gone from every doc, the Makefile and CI; DECISIONS
  carries each candidate's position; brief §6 says Documented; the five
  BACKLOG rows are struck with the right phase and the count matches.
- **Stack risk — the developer's hand checks, in a browser, before this spec
  is approved (an agent runs no fetch).** Each answer goes into pinned
  decision 4 and DECISIONS; a verdict that contradicts a recalled position
  corrects the spec, never the check.
  1. `https://www.opinion-assurances.fr/robots.txt` — the `User-agent: *`
     group (and any group naming a crawler like ours): is the studied
     insurer's profile page allowed, and its second page of reviews (note the
     exact addresses of page 1 and page 2, and any `Crawl-delay`)?
  2. The site's terms page (CGU / mentions légales): any clause on automated
     access, extraction or reproduction — quote the clause's location, not
     its text, in the check notes. A forbidding clause is a STOP for reviews.
  3. The studied insurer's profile page, view-source: does it carry `<script
     type="application/ld+json">`? Does the block hold `aggregateRating`
     (`ratingValue`, `reviewCount` or `ratingCount`) and a `review` list
     (`reviewRating.ratingValue`, `datePublished`, `reviewBody`, a title)?
     How many reviews per page? If there is no block: for one review, the
     element and attribute that carry the rating, the date, the title, the
     body, and the next-page link.
  4. `https://play.google.com/robots.txt` — the `*` group against the
     details page (`/store/apps/details?id=…&hl=fr&gl=FR`) and against `/_/`.
     The details page, view-source: a JSON-LD block with `aggregateRating`
     (`ratingValue`, `ratingCount`)? Is the number in the source itself, or
     only drawn after the page loads (then the fetcher will not see it)?
  5. `https://apps.apple.com/robots.txt` — the `*` group against
     `/fr/app/id1277025964`. The listing, view-source: a JSON-LD block with
     `aggregateRating` (`ratingValue`, `reviewCount`)?
  6. For each candidate: the approximate page size and whether the site
     answered a plain browser request with a challenge page (a challenge is a
     block; the manual path is 3b's).
  **Disposition if no review source is allowed:** STOP at approval. The
  phase re-scopes to snapshots from anchors plus the allowed listings, the
  DONE command becomes `make rebuild ROWS=samples && make idempotency-check
  ROWS=samples`, and "the first real rows" moves again with its reason in
  DECISIONS — never a workaround. **The first live run is itself the check**
  of the robots gate rebuilt under A1 and A6 (Done-when 4); its result goes to
  DECISIONS → Gotchas whatever it is.

## Out of scope (deferred, recorded)

- Trustpilot, its bot handling and the manual snapshot path for a refusing
  host — Phase 3b (PLAN §5).
- B1.4 `platform_stats` (one-star share, response lag) — BACKLOG row opened
  here, trigger 3b (the star distribution is on that platform's page).
- The weekly schedule and the `data/snapshots/` commit — Phase 4; the
  stop-at-first-known-page optimisation of a re-fetch — BACKLOG row, trigger
  Phase 4.
- Per-review theme charts that consume `source_pages` (B2.2, B2.5) — Phases
  5b–7; the join is landed and pinned here, the charts are not.
- The health-details rule for excerpts — BACKLOG row untouched; its trigger
  (a tracked snapshot commit or a published excerpt) is Phase 4's or 9's.
- Classification, the cost model, the study — Phases 5–9.
