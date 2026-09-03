# Phase 3a — Snapshots and the remaining polite sources (APPROVED)

Contract for the `phase-3a-snapshots` branch. Source: PROJECT_BRIEF.md §9
Phase 3 (scraper fleet + snapshots), split by `docs/PLAN.md` §5 into 3a (this
phase: `platform_snapshots` seeded from the §6 anchors, the polite sources) and
3b (Trustpilot, its own session). Depends on `phase-2-scraper` merged (PR #4).

**Status: APPROVED 2026-09-02 — in progress.** No new dependencies: the two
parsers here are stdlib `json` over a page's machine-readable block and stdlib
`html.parser` over a page's schema.org microdata; `pyyaml` stays pre-approved
and unused; anything else is a STOP-and-ask. No pandas on any pipeline path.

**Amended at approval (2026-09-02) — A1: Opinion Assurances is authorized.**
The developer holds the site's written authorization to read its pages
automatically (the route the terms' clause V.3 names; requested and reported
granted 2026-09-02). So the source declared not fetchable in the revision below
becomes the phase's first review source — the outcome the first draft aimed
at — with the letter as its terms position, and D5 and D6 return: peer profiles
on the same site may be declared at the developer's choice within the letter's
scope, and `MAX_PAGES` rises to 60 (the studied insurer's profile has 14 pages
of about 40 reviews; a peer with thousands is capped). The page's shape, from
the one download permitted before this amendment: no JSON-LD; schema.org
**microdata** inline — 40 `review` scopes per page, each with a `reviewRating`
(`ratingValue`, `bestRating`, `worstRating`) and an `author` (`Person`, never
read); one `AggregateRating` with `ratingValue` and `ratingCount`; pages
`…-page<n>.html`, path-based, allowed by robots. Three parts of the shape are
still to be read off the structure in the first hour (Review & stack risk):
where the date and the body sit, and whether each review carries a stable
identifier — without one, `external_id` is a STOP-and-decide, not a guess. The
hand-entry path stays for the App Store listing; the Opinion Assurances
aggregate now comes from the fetch. Everything else in the revision stands.

**Revised 2026-09-02, before approval, after the candidate checks.** The
first draft named Opinion Assurances as the first review source and the two
app-store listing pages as snapshot sources. The checks (results under Review
& stack risk; run from the build session at the developer's request, one
request per page with the project's User-Agent, two seconds apart per host)
found that no candidate can supply reviews: Opinion Assurances allows the
pages in `robots.txt` but its terms forbid automated extraction without
written authorization; Apple's website terms forbid robots on the listing
page; Google Play's listing page is allowed by both its robots file and
Google's terms, and its reviews are not. So, on the developer's decision, the
phase is re-scoped to what the spec's own disposition said: **the first real
rows are snapshot rows** — the anchors, one automated capture (the Google Play
listing), and figures read by hand off the pages we may not fetch, entered
through a tracked file and tagged Measured. Written authorization from Opinion
Assurances is requested in parallel (a developer action, outside the repo); if
granted, its reviews are a later phase's source with the letter as the terms
position. The decisions taken: **D1** an address that spells the brand may sit
in `ingest/sources.py` and nowhere else; **D2** `fixtures/anchors/` is
re-frozen with `profile`, `channel` and the B1.4 columns; **D3** anchors are
Documented and brief §6 is reworded; **D4** `FIXTURE` becomes `ROWS`. Dropped:
D5 (peer review profiles — no review source) and D6 (the page ceiling stays at
10 — no multi-page source is fetched).

**Proposed after review round 1 (2026-09-02) — A2: one snapshot row per
declaration and day, no tiebreak; the stat row one row per stat; two sentences
corrected.** *Status: APPROVED 2026-09-02; built in the commits that follow.*
Restores invariant 1 (a snapshot row is one point, keyed on what produced it,
and a rebuild changes no count by chance) and invariant 2 (a mart is the data,
never a hash order). (a) *The key names its declaration* (round 1, findings 1
and 2): `raw_platform_snapshots`' natural key becomes `(source, profile,
origin, source_url, captured_at)` — `source_url` is the platform root for an
anchor, the declared listing address for a hand-read row and the page address
for a capture — so a hand-read figure can never be swallowed by an anchor with
the same numbers, and two declared sources sharing a platform and profile
cannot collide on a day; a declaration test pins that no two hand-entered
sources share `(platform, listing)` — an app's feed and its store listing
share theirs by design, and only a hand-entered row keys on it. (b) *A
same-key pair is refused, not tiebroken* (finding 1): the loader refuses, with
one line naming file, line and fix, a row whose key already sits in raw under
another content hash — that arises only from a corrected hand entry or a
re-frozen seed, and the fix is `make reset CONFIRM=yes` then `make rebuild`,
since the corpus is rebuilt from tracked inputs; `stg_platform_snapshots` and
the four marts drop `content_hash desc` from every `order by`, and a test
asserts the key is unique in raw. (c) *The stat row is one row per stat*
(finding 21): `platform_stats`' grain becomes `(segment, source, profile,
stat)`, `stat` from the closed set `{review_count, one_star_share,
response_rate, response_delay_days}`, `value` the latest non-null reading of
that stat with the tag, address and day of the row it came from — a fetch that
reads one figure never blanks the other two; the pins and B1.4's panel text
follow. (d) *Two sentences say what is true* (findings 12 and 14): Done-when 4
and pinned decision 4 read "a second `make scrape` of unchanged pages adds no
raw review row; each capture adds one snapshot row per profile, since
`captured_at` is in its key — that row is the point on the trend"; pinned
decision 4's STOP-and-decide is recorded as decided — the page marks no
identifier, `external_id` is the content hash of (publication date, experience
date, rating, body), an edited review is a new review, the BACKLOG row carries
the trigger; invariant 6 gains "and derives each review's identifier from its
content, never from its author". Not taken: a load-sequence column so the
later entry wins (a second order on the data path, and raw would carry a
number no page produced); keeping `platform_stats`' grain and taking each
column from its own latest row (three provenances in one row).

**Proposed after review round 2 (2026-09-02) — A3: attribution joins the
guards; the sample declaration is a property, not a name; a hand entry may
name exactly the sources the uniqueness check covers.** *Status: PROPOSED,
awaiting approval; nothing in it is built.* Restores invariant 1 (a row is
keyed on what produced it, and a re-run changes no count by chance), invariant
3 (attribution comes from the declaration, never from a caller's value) and
invariant 4 (a captured review joins exactly one declared page). (a) *A
changed attribution refuses* (round 2, findings 1 and 4): `raw_source_pages`'
guard stays `(source, source_url)` + the attribution hash, but a declared page
whose `profile`, `segment` or `channel` differs from the row already in raw
REFUSES the rebuild with one line naming the address and the fix (`make reset
CONFIRM=yes`, then `make rebuild`), so a re-declaration never appends a second
row for one address and the review join stays one-to-one — pinned by a test
that flips a source's segment in a copied tuple and by the join test extended
to assert the count of `raw_source_pages` rows per address; `snapshot_hash`
gains `segment`, `channel` and `seeded_from`, so a corrected attribution on an
existing key is a same-key pair and refuses like a corrected figure, never
dropped by `where not exists`. (b) *The sample declaration is a property*
(findings 5 and 6): `Source` gains `sample: bool` (True only from
`sample_source`, the frozen samples' declaration), the closed-set check on
`segment` and `channel` keys on it rather than on `name == "sample"`, and
invariant 1 reads "`segment` and `channel` are values from their closed sets,
or the literal `sample` on a row a sample declaration wrote — a label that
exists only in the samples database" with pinned decision 5 unchanged; a
source named `sample` without the property refuses at declaration. (c) *A hand
entry may name exactly the hand-entered sources* (finding 24):
`read_manual_snapshots` accepts a source iff `parser is None` — the same set
`hand_entries_are_unique` covers — so the App Store feed (a review source
declared not fetchable) can no longer receive a hand-read row that collapses
onto the listing's key; the error names the rule ("a hand entry names a source
with no parser"). Not taken: widening the uniqueness check to every
non-fetchable source (two declarations would then share one key by design);
putting `origin` and the attribution into `raw_source_pages` (a page's
attribution is one fact, not a series); a replace-on-change for either table
(raw is append-only, and a replaced row would lose its provenance).

## Why

Phase 2 built the collector and proved it on a frozen sample, but the one
source it declared asks crawlers not to read its review feed, so the warehouse
still holds no real row. Phase 3a lands three things the study cannot start
without. First, the platform ratings over time — `platform_snapshots` — seeded
from the verified figures in the brief and marked as such, then extended by our
own captures: one automated, the rest read by hand where a site's terms say
no robot may read them for us. Beat 1's rating trend, channel gap and stat row
and Beat 2's peer context can then show numbers with the tag they deserve.
Second, the generalisation Phase 2 deliberately skipped: a source declares its
own parser and cache root, so the second platform costs a declaration, not a
branch, and a source we may not fetch is declared as plainly as one we may.
Third, the first real review rows: the two app stores refuse us (one in its
robots file, one in its terms), but Opinion Assurances has given the developer
written authorization to read its pages (A1), so its profile pages become the
first review source, through the unchanged Phase 1 guard. Fourth, five BACKLOG
rows fall due here and each is closed or re-deferred. Phase 3b checks
Trustpilot.

**Teaching notes (become code comments / README lines at build — CLAUDE.md →
Teaching rule).**
- *A snapshot is a photograph of a public page's headline numbers.* A review
  platform shows, on each insurer's page, an average rating and a review count
  (and sometimes the share of one-star reviews and how fast the company
  answers). We do not compute those; we record them as they stood at a moment,
  with the page address and the time. Repeated, the photographs become a time
  series. The brief's §6 figures are earlier photographs taken by hand at
  scoping, so they are loaded first and marked as seeded.
- *Machine-readable blocks on ordinary web pages.* Many store and review pages
  carry, inside the page, a small block written for search engines
  (`<script type="application/ld+json">`, in the schema.org vocabulary) that
  states the rating and count as plain data. Reading that block is the boring,
  standard way: it is meant to be read by machines, it has a declared shape,
  and it does not depend on how the page looks.
- *A page we may read, and a page we may not.* A site tells crawlers what
  they may fetch in two places: its `robots.txt`, which a program reads, and
  its terms of use, which a person reads. We obey both. Where the terms say
  no, a person reads the number off the page and writes it down with the
  address and the date, and the study shows it as our own capture — because
  it is one, made by hand.
- *One declaration per source.* Each thing we read from is declared once, in
  one file: which platform, which address, which parser, which cache
  directory, which segment and channel it belongs to, and whether its site
  lets us fetch it. Every other module reads those facts from the declaration
  and none knows a platform by name.

## The central constraint

**Phase 1's review shape and Phase 2's load path, manners and run-twice
property do not move: `raw_reviews` keeps its ten columns and `load_reviews`
its guard; every new row of every new table carries the four provenance
columns; the anchors seed the same nine rows in every rebuild input but
`none`; a rebuild reads no clock and no network; the test suite opens no
socket; every live fetch is run by the developer; no site whose robots file
or terms refuse us is fetched, by any means.** Segment attribution joins on
`source_url` by exact value or on a column written in Python, never a pattern
in SQL. No parser reads a reviewer's name. `check-backing` stays clean: four
marts land, four rows flip, zero orphans.

## DONE command

```
make rebuild && make idempotency-check ROWS=captured
```

- `make rebuild` — `ROWS` defaults to `captured`: the anchors seed
  `raw_platform_snapshots` (9 rows, Documented); the hand-entered rows in
  `data/snapshots/manual_snapshots.csv` load (Measured); every capture under
  `data/cache/` is parsed by its source's declared parser (Measured); staging
  and the four marts are built; the per-table counts print, followed by
  reviews per month for the Opinion Assurances rows (A1). Precondition: the
  developer has run `make scrape CONFIRM=yes` once, which fetches the two
  fetchable sources (the Google Play listing; the Opinion Assurances profile
  pages, reviews and aggregate alike) — the first time `make scrape` runs
  green against a live host since the robots gate was rebuilt (Phase 2's A1,
  A6) — and has entered the one hand-read row the checks produced (the App
  Store listing, 2026-09-02).
- `make idempotency-check ROWS=captured` — rebuilds the corpus twice into a
  throwaway database and diffs every table's count.
- Also green: `make rebuild ROWS=samples && make idempotency-check
  ROWS=samples` (CI: every frozen sample through its real parser, offline,
  pinned in `tests/pins.py`); `make rebuild ROWS=synthetic && make
  idempotency-check` (Phase 1's line: raw 40 / staging 39, now with
  `raw_platform_snapshots` 9); `make rebuild ROWS=none` (zero rows, every
  table present); `make test`; `make check-backing` (19 rows, 4 marts, 0
  orphans); `make check-docs`.

## Done-when

1. **`platform_snapshots` lands, seeded from the anchors and marked as such.**
   `raw_platform_snapshots` (append-only, natural key `(source, profile,
   origin, source_url, captured_at)` + content hash of the measures, A2) and
   `stg_platform_snapshots` exist; the nine anchor rows load from the
   re-frozen `fixtures/anchors/` with `origin = anchor` and read back as
   `Documented`; a hand-entered row (`origin = manual`) and a captured row
   (`origin = fetch`) read back as `Measured`; every row carries `source`,
   `source_url`, `captured_at`, `run_id`, `profile`, `segment`, `channel`; a
   re-seed, a re-entry and a second rebuild add no row. *Evidence: row 1.*
2. **Four marts land and four BACKING rows flip Pending → Documented.**
   `sql/marts/rating_trend.sql` (B1.2), `channel_gap.sql` (B1.3),
   `platform_stats.sql` (B1.4), `peer_ratings.sql` (B2.3) build from
   `stg_platform_snapshots`, each row carrying its point's tag; BACKING flips
   those rows with sources of the declared shape; SPEC.md's four panels say
   what they now show; `make check-backing` prints 19 rows, 4 marts, 0
   orphans. *Evidence: row 2.*
3. **Every source declares its parser, cache root, host, profile, segment,
   channel and terms position; nothing branches on a name.**
   `ingest/sources.py` holds the closed tuple — the Phase 2 feed source, the
   Google Play listing (fetchable), the Opinion Assurances profiles
   (fetchable under the written authorization, A1), the App Store listing
   (declared, not fetchable, its terms clause as the reason, hand-entered
   snapshots only); `pipeline/build.py` loads every
   fetchable source's captures through the declared parser and fills a
   hand-entered row's platform, address, segment and channel from the
   declaration; the cache root is bound once; a capture's meta is validated
   against its source's declared host; a review row's segment comes from
   `source_pages` (one row per declared page address, written in Python at
   rebuild) joined on exact `source_url`; the SQL lint refuses `like`,
   `similar to` and `regexp` alike. *Evidence: row 3.*
4. **The first real rows: reviews from Opinion Assurances, snapshots from
   two fetches and one hand entry (A1).** After the developer's `make scrape
   CONFIRM=yes` and the entry in `data/snapshots/manual_snapshots.csv`, the
   DONE command prints `raw_reviews` > 0 from the Opinion Assurances profile
   through the unchanged `load_reviews` guard, `raw_platform_snapshots` = 9 +
   the entered row + one snapshot per fetched profile and listing, the four
   marts populated, reviews per month for the new source, and every count
   unchanged on the second rebuild; a second `make scrape` of unchanged pages
   adds no raw review row and one snapshot row per profile, since
   `captured_at` is in its key — that row is the point on the trend (A2). The
   run is also the first live check of the rebuilt robots gate on hosts that
   allow us. *Evidence: row 4.*
5. **The rebuild input is named by what it is, and every frozen sample runs
   offline.** `ROWS` is the closed set `{captured, none, synthetic, samples}`
   (`captured` the default for `rebuild`, `synthetic` for
   `idempotency-check`); `samples` reads every frozen sample under
   `fixtures/<parser>/` through its real parser, in CI; the new samples
   `fixtures/listings/` and `fixtures/opinion-assurances/` (A1) are
   hand-written, fake and nameless with a MANIFEST;
   `fixtures/app-store/robots.txt` is re-frozen to the real rule and a test
   reads it through `ingest/robots.py`. *Evidence: row 5.*
6. **The matcher is linear, and no parser or file reads a name.** A robots
   pattern with thirty wildcards against a long non-matching path answers in
   milliseconds and the matching table stands; the listing parser reads the
   page's `AggregateRating` and nothing else (no `author`, `name`, `url` or
   review item); the Opinion Assurances parser never reads the `author`
   scope or any `Person` (A1); the manual file carries no address and no name (a source
   name, a date, five numbers and the word `page`); the health-details BACKLOG row is
   re-deferred with a trigger that names what it is about — review text in a
   tracked file — which this phase does not reach. *Evidence: row 6.*

(6 items. Each is a contract, not a narrative.)

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `tests/test_snapshots.py::test_anchors_seed_nine_documented_rows_with_provenance`, `::test_manual_and_fetched_rows_read_back_as_measured`, `::test_reseeding_reentering_and_rebuilding_add_no_snapshot_row`, `::test_anchor_row_outside_the_declared_shape_is_refused` (a rating `6.0`, a count `-1`, a segment outside the closed set, a missing column), `::test_manual_row_outside_the_declared_shape_is_refused` (an undeclared source name, a fetchable source's name, a date that is not a date, a share above 1); `tests/test_provenance.py::test_every_raw_table_has_four_provenance_columns` (extended over every `raw_*` table) |
| 2 | `tests/test_marts.py::test_rating_trend_matches_pins`, `::test_channel_gap_matches_pins`, `::test_platform_stats_matches_pins`, `::test_peer_ratings_matches_pins` (the anchors' rows, `tests/pins.py`), `::test_every_mart_row_carries_exactly_one_tag`, `::test_a_hand_read_and_a_fetched_point_reach_the_marts_as_measured`, `::test_a_later_reading_of_one_stat_keeps_the_others` (A2: one row per stat); `make check-backing` prints `check-backing OK: 19 rows, 4 marts`; `tests/test_sql_portable.py::test_every_sql_file_is_portable_and_clock_free` over the new files |
| 3 | `tests/test_ingest_layout.py::test_every_source_declares_parser_cache_host_and_attribution`, `::test_every_non_fetchable_source_states_its_reason` (extended: the reason names robots or a terms clause and a date), `::test_every_fetchable_sources_host_is_allowed`, `::test_no_module_branches_on_a_platform_name` (no comparison against a platform or source name outside `ingest/sources.py` and the parsers' own `SOURCE` constants), `::test_the_cache_root_is_bound_once`; `tests/test_ingest_rebuild.py::test_meta_is_validated_against_the_sources_declared_host`, `::test_every_captured_review_joins_exactly_one_declared_page` (on a capture the test writes under the feed source's shape); `tests/test_sql_portable.py::test_pattern_matching_is_refused_in_sql` (`like`, `similar to`, `regexp` planted) |
| 4 | The DONE command's output on the developer's machine, pasted into the Delivered paragraph (counts per table, reviews per month for the new source, `idempotency-check OK`); `make scrape CONFIRM=yes` run twice, the second adding no raw review row and one snapshot row per profile (A2); functionality-tester reruns the DONE command on that cache and file; `tests/test_fetch_sources.py::test_a_listing_source_fetches_robots_then_one_page_and_archives_both`, `::test_a_review_page_source_stops_at_the_first_page_with_no_review`, `::test_a_non_fetchable_source_is_refused_before_any_request_whatever_robots_says` pin the same path on `httpx.MockTransport`; `tests/test_opinion_assurances_parser.py::test_well_formed_page_maps_to_reviews_and_one_snapshot` |
| 5 | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set`, `::test_idempotency_check_variables_are_a_closed_set` (re-pinned to `ROWS` and the four names); `tests/test_cli.py::test_each_input_builds_its_own_database` (re-pinned); `tests/test_ingest_rebuild.py::test_samples_load_every_frozen_sample_through_its_parser` (pins per sample); `tests/test_fixtures_frozen.py::test_manifests_match` (extended to `fixtures/listings/` and `fixtures/opinion-assurances/`); `tests/test_listing_parser.py::test_sample_is_obviously_fake_and_nameless`, `tests/test_opinion_assurances_parser.py::test_sample_is_obviously_fake_and_nameless`; `tests/test_robots.py::test_the_frozen_app_store_robots_file_disallows_the_sample_feed`; `.github/workflows/ci.yml` runs `ROWS=samples` in place of `FIXTURE=app-store` |
| 6 | `tests/test_robots.py::test_a_pathological_pattern_matches_in_linear_time`, `::test_pattern_matching_and_precedence` (the table, unchanged); `tests/test_listing_parser.py::test_only_the_aggregate_rating_is_read`, `::test_two_aggregate_ratings_refuse_the_page`, `::test_no_aggregate_rating_refuses_the_page`; `tests/test_opinion_assurances_parser.py::test_author_scope_is_never_read`, `::test_missing_required_field_refuses_the_page`, `::test_refusal_names_page_item_and_field`; `tests/test_snapshots.py::test_manual_file_columns_are_exactly_the_declared_eight`; `tests/test_app_store_parser.py::test_author_fields_are_never_read` (unchanged); security-reviewer confirms no name or address in `data/snapshots/manual_snapshots.csv` and no review text in any tracked file |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For all snapshot rows, the four provenance columns are non-empty, `origin`, `profile`, `segment` and `channel` are values from their closed sets, and the row reads back `Documented` iff `origin = anchor` and `Measured` otherwise; a re-seed, a re-entry or a second rebuild changes no count; the key `(source, profile, origin, source_url, captured_at)` is unique in raw, and a row whose key is already there under other figures refuses the load rather than being tiebroken (A2). | `tests/test_snapshots.py::test_anchors_seed_nine_documented_rows_with_provenance`, `::test_manual_and_fetched_rows_read_back_as_measured`, `::test_reseeding_reentering_and_rebuilding_add_no_snapshot_row` — anchors, a manual row and a capture each loaded twice: nine plus one plus one, both times; `::test_a_corrected_figure_for_an_entered_day_refuses_the_load`, `::test_two_entries_for_one_day_in_one_file_refuse_naming_the_second_line`, `::test_a_hand_read_row_is_never_swallowed_by_an_anchor_with_its_numbers`, `::test_the_snapshot_key_is_unique_in_raw`; `tests/test_ingest_layout.py::test_no_two_hand_entered_sources_share_a_platform_and_listing` (A2) |
| 2. For all rebuild inputs but `none`, the anchors seed the same nine rows and the four marts are byte-identical across two rebuilds under different wall-clock times; a Pending row's mart does not exist. | `tests/test_marts.py::test_marts_are_byte_stable_across_rebuilds` (every clock the data path imports made to raise; every column compared, `run_id` included), `::test_rating_trend_matches_pins` and siblings; `make check-backing` (orphans) |
| 3. For all declared sources, the parser, cache directory, host, page addresses, attribution and terms position are read from the declaration; a source declared not fetchable is never requested whatever its robots file says — a plain run skips it with one line, naming it refuses; no module outside `ingest/sources.py` and the parsers' own constants compares a platform or source name; a capture's meta is accepted iff its `source_url` host is the declaring source's host. | `tests/test_ingest_layout.py::test_no_module_branches_on_a_platform_name`, `::test_the_cache_root_is_bound_once`; `tests/test_fetch_sources.py::test_a_non_fetchable_source_is_refused_before_any_request_whatever_robots_says` — a permissive robots body and a non-fetchable source: only no request at all; `tests/test_ingest_rebuild.py::test_meta_is_validated_against_the_sources_declared_host` — a meta on another allowed host refuses; the allowlist shrunk in a test does not unload a declared source's capture |
| 4. For all captured review rows, `(source, source_url)` joins exactly one `source_pages` row, and for all files under `sql/`, no `like`, `similar to` or regex function appears: attribution is exact-value or Python-written, never a pattern in SQL. | `tests/test_ingest_rebuild.py::test_every_captured_review_joins_exactly_one_declared_page` — a capture under a declared source joins; a page address outside the declaration is an unattributed row and the test fails; `tests/test_sql_portable.py::test_pattern_matching_is_refused_in_sql` |
| 5. For all requests the fetcher makes to any host, the host's robots file was read first and allowed the path under both our group and `*`, the identifying User-Agent is set, the previous request to that host was ≥ 2 s earlier (more if asked), and there is no retry, proxy or rotation; matching a pattern takes time linear in its length times the path's. | `tests/test_app_store_fetch.py` (unchanged, now over a source parameter), `tests/test_fetch_sources.py::test_a_listing_source_fetches_robots_then_one_page_and_archives_both`, `::test_two_sources_on_two_hosts_keep_two_clocks`; `tests/test_robots.py::test_a_pathological_pattern_matches_in_linear_time` — thirty `*` against a 300-character non-matching path under 50 ms |
| 6. For all parsers and hand-entered files, no author, pseudonym, name or brand-carrying address is read or stored: the listing parser accepts exactly one `AggregateRating` per page and reads nothing else from the block; the Opinion Assurances parser reads each `review` scope's rating, date and body, derives its identifier from that content and never from its `author` scope, and refuses the whole page on a review outside the declared shape, naming page, item and field; the manual file has exactly the eight declared columns, none an address or free text; every frozen sample is fake, nameless and hashes to its MANIFEST. | `tests/test_listing_parser.py::test_only_the_aggregate_rating_is_read`, `::test_two_aggregate_ratings_refuse_the_page`, `::test_no_aggregate_rating_refuses_the_page`, `::test_refusal_names_page_and_field`; `tests/test_opinion_assurances_parser.py::test_author_scope_is_never_read`, `::test_missing_required_field_refuses_the_page`, `::test_refusal_names_page_item_and_field`; `tests/test_snapshots.py::test_manual_file_columns_are_exactly_the_declared_eight`; `tests/test_fixtures_frozen.py::test_manifests_match` |
| 7. For all `ROWS` values, the set is closed and each input builds its own database file; under `samples`, every declared parser's frozen sample loads through that parser and matches its pins. | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set`, `tests/test_cli.py::test_each_input_builds_its_own_database`, `tests/test_ingest_rebuild.py::test_samples_load_every_frozen_sample_through_its_parser` — a parser with no sample directory is a test failure, not a skip |

## Pinned decisions (do not re-litigate)

- **The snapshot shape, seeded from the re-frozen anchors (D2, D3).**
  `raw_platform_snapshots`: `source` (the platform slug, as `raw_reviews`),
  `profile` (the declared source name — `fr-digital-first` for the studied
  insurer, `peer-<segment>-<n>` for the anchors' anonymous peers), `segment`
  (closed set `digital-first | traditional | digital-challenger`), `channel`
  (`invited | unsolicited`), `origin` (`anchor | manual | fetch`), `rating`
  (`decimal(4,3)`, 0–5; a page's longer value is rounded half-even to three
  places in Python at parse, stated in the parser), `review_count` (integer ≥
  0), `one_star_share` (`decimal(4,3)`, 0–1, null when the page does not show
  it), `response_rate` (same), `response_delay_days` (`decimal(5,1)`, null
  when not shown), `source_url`, `captured_at` (text: the anchors' and manual
  rows' `YYYY-MM-DD`, or the fetch stamp), `run_id`, `seeded_from`
  (`PROJECT_BRIEF §6` for an anchor, empty otherwise), `content_hash` (over
  the five measures). Natural key `(source, profile, origin, source_url,
  captured_at)` + hash (A2), the Phase 1 guard shape; a row whose key is
  already in raw under another hash refuses the load, so
  `stg_platform_snapshots` keeps every raw row and derives `tag` (`case when
  origin = 'anchor' then 'Documented' else 'Measured' end` — an exact
  comparison, portable) and `month` (`substr(captured_at, 1, 7)`). The anchors
  CSV is parsed strictly in Python (`csv`, closed sets, numeric ranges; a bad
  row refuses the seed); `fixtures/anchors/` is re-frozen with `profile`,
  `channel`, the three B1.4 columns (filled where brief §6 gives them: the
  platform's 23.1 % one-star, 82 % and 1.5 days; the early-2025 18 % one-star;
  empty elsewhere) and `digital-first` on the two app rows (`Freeze:
  fixtures/anchors/`, MANIFEST in the diff, DECISIONS entry) — the frozen
  shape has no profile, so two traditional peers collide on every key, and the
  app rows carry a channel where a segment belongs. For a fetched or
  hand-entered row, `profile`, `segment`, `channel`, `source` and `source_url`
  are written in Python from the source declaration. The anchors seed in every
  input but `none`. Satisfies invariants 1 and 2. Rejected: repairing the
  seed's meaning in staging (a fixture fixed in SQL); Measured for anchors (a
  person's reading at scoping, without a capture time of ours, is a documented
  public figure); a Python-side dedup (the guard is the warehouse's, as in
  Phase 1); keeping the page's full-precision rating as text (a mart cannot
  average text; three places keep every platform's displayed value exactly).
- **Four marts, four flips to Documented.** `rating_trend` (B1.2): one row
  per `(channel, segment, source, profile, month)`, the latest snapshot in
  that month with `rating`, `review_count`, `captured_at`, `tag` — the panel
  shows the unsolicited channel and states the sampling bias beside it.
  `channel_gap` (B1.3): one row per `(segment, channel, source, profile)`,
  the latest snapshot, with its tag — invited beside unsolicited for one
  segment. `platform_stats` (B1.4): one row per `(segment, source, profile,
  stat)` over the closed set `{review_count, one_star_share, response_rate,
  response_delay_days}`, each the latest reading of that stat with its own
  tag, address and day (A2). `peer_ratings`
  (B2.3): one row per `(segment, source, profile)` over the unsolicited
  channel, the latest snapshot, with its tag and date. All four are
  window-function selects over `stg_platform_snapshots` in the `stg_reviews`
  shape (no `order by` at the top level, no clock, no pattern). BACKING:
  B1.2, B1.3, B1.4, B2.3 flip Pending → **Documented**, source cell
  `` `fixtures/anchors/platform_snapshots_seed.csv` `` plus the platform
  roots the seed names; the flip to Measured is Phase 4's, when scheduled
  captures make the series ours and every seeded point is marked in the
  chart (SPEC.md's Beat 1 already says "marked as seeded"). SPEC.md's four
  panels drop "(Pending until…)" and say "Documented for the seeded points;
  each point carries its own tag in the mart"; the header sentence "Today
  every row is Pending" goes. Satisfies invariant 2 and the central
  constraint. Rejected: one shared `platform_latest` mart under four rows
  (the names are Phase 0b's chart list; four small files read as four
  charts); flipping to Measured on the strength of a few 2026-09-02 points (a
  chart is as strong as its weakest displayed point until the seeded points
  are the minority and marked — Phase 4's condition); leaving B1.4 Pending
  now that its numbers are in the shape.
- **A source is a declaration; a parser and a terms position are declared
  beside it (BACKLOG rows "capture path hardwired" and "`DEFAULT_CACHE` /
  `ALLOWED_HOSTS`"; D1).** `ingest/sources.py::Source` (frozen dataclass):
  `name`, `platform`, `host`, `parser` (`app_store` — the feed; `listing` — a
  page's `AggregateRating` only; `opinion_assurances` — a profile page's
  microdata: its `review` scopes to review rows and its `AggregateRating` to
  one snapshot row, A1; or none, for a source whose snapshots are hand-entered
  only), `page_url(n)`, `pages` (≤ `politeness.MAX_PAGES`, 60 — A1),
  `profile`, `segment`, `channel`, `listing` (the address the figure is read
  from — the one place a brand-carrying address may appear, D1),
  `fetchable`, `terms` (the reason when not fetchable: the robots rule or
  the terms clause, with the date it was read), `declared_on`. Each parser
  exposes `parse(body, page_url, captured_at, source) -> Parsed(reviews,
  snapshots)` and names the body's file extension (`json` or
  `html`) and its sample directory (`fixtures/<parser-slug>/`). The cache
  root is bound once (`ingest/sources.py::CACHE_ROOT`, `data/cache/`); a
  source's cache directory is `CACHE_ROOT / platform / name`;
  `pipeline/build.py` and `pipeline/cli.py` import it and iterate `SOURCES`,
  dispatching to `source.parser`; `run_id` for a fetched row is the capture's
  path relative to the cache root, for a manual row the file's path.
  `read_meta` validates `source_url`'s host against the declaring source's
  `host`, not the live `ALLOWED_HOSTS` (which stays the fetch-time allowlist
  in `politeness.py`, now `("itunes.apple.com", "play.google.com",
  "www.opinion-assurances.fr")`; a test pins every fetchable source's host is
  in it). Attribution for reviews:
  `source_pages` (`sql/raw/raw_source_pages.sql`, one row per declared source
  × page address: `source`, `source_url`, `profile`, `segment`, `channel`,
  `captured_at` = `declared_on`, `run_id`), written in Python at every
  rebuild through the same guard — the closed set of `source_url` values a
  source can produce, so `stg_reviews join raw_source_pages using (source,
  source_url)` is exact-value and a test pins that every captured review row
  joins exactly one (on captures the tests write; no live review exists
  yet). `pipeline/sql_lint.py` gains `like` and `similar to` (a declared
  widening, recorded). Satisfies invariants 3 and 4. Rejected: a `segment`
  column on `raw_reviews` (Phase 1's shape); a pattern over `source_url` in
  SQL (the Portability contract); deriving `ALLOWED_HOSTS` from the
  declarations (a circular import, and the allowlist is a fetch-time knob by
  design); attribution through `run_id` (in no mart, by decision); leaving
  `source_pages` for the phase that charts it (Phase 2 promised the table
  here, and the join property is only cheap to pin now).
- **The sources, with their positions as checked on 2026-09-02, and the
  hand-entry path.** Four declared sources for the studied insurer:
  (a) the App Store review feed (Phase 2's): `fetchable=False`, robots
  disallows `/*/rss/*` for every crawler — unchanged.
  (b) the Google Play listing: `parser=listing`, host `play.google.com`,
  `pages=1`, the details address by package id with `hl=fr&gl=FR`,
  `fetchable=True`. Checked: the catch-all group disallows `/_`,
  `/store/getreviews` and `/store/xhr` and does not disallow
  `/store/apps/details` (our matcher: allowed); Google's terms forbid
  automated access only where it breaches robots.txt; the page answers 200
  without a redirect, about 1.3 MB, and carries one JSON-LD block of type
  `SoftwareApplication` whose `aggregateRating` holds `ratingValue` and
  `ratingCount` as digit strings. Reviews on this platform load through the
  disallowed `/_` call and are not fetched, ever — recorded as the platform's
  review position. The package id spells the brand: D1.
  (c) the App Store listing: `parser=None`, host `apps.apple.com`,
  `fetchable=False`, `terms` = Apple's website terms of use, "Your Use of the
  Site": no robot, spider, page-scrape or automated means to access or copy
  the site (read 2026-09-02); robots allows `/fr/app/…`, so the terms alone
  decide; the by-id address also answers 301 to a slug address. Snapshots
  hand-entered.
  (d) the Opinion Assurances profile (A1): `parser=opinion_assurances`, host
  `www.opinion-assurances.fr`, `pages=14` for the studied insurer (the
  profile's own page count on 2026-09-02; a later page past the last is an
  empty page and the end), `fetchable=True`, `terms` = the site's written
  authorization held by the developer (its conditions générales V.3 forbid
  automated extraction *without* prior written authorization; V.1 governs
  reproduction — the study publishes aggregates and paraphrases only, brief
  §2.5), recorded with the date it was granted. Robots allows the profile and
  its path-based pages `…-page<n>.html` and disallows every address with a
  query string, so the declared `page_url(n)` is the path form and page 1 is
  the profile itself. The parser: schema.org microdata, strictly — each
  `itemscope` of type `review` yields one review row (`rating` = its
  `reviewRating`'s `ratingValue`, an integer 1–5 checked against `bestRating`
  5; `review_date` = the review's own date as `YYYY-MM-DD`; `body` = the
  review text; `title` = the page's title-like field if the structure has one,
  else empty; `external_id` = the content hash of (publication date,
  experience date, rating, body) — the page marks no stable identifier,
  decided at build, A2);
  the page's one `AggregateRating` (`ratingValue`, `ratingCount`) and its
  one-star share, response rate and response delay, if the structure carries
  them as data, yield the snapshot row; the `author` scope and every `Person`
  are never read; a review missing a required field, a rating outside 1–5, a
  date that does not parse, or a page with no `review` scope and no
  end-of-list marker refuses the whole page, naming page, item and field.
  Where the date, body and identifier sit, and which stats are data rather
  than layout, are read off the redacted structure dump in the first hour
  and written into `ingest/opinion_assurances.py`'s header — the spec
  declares the fields, the build declares their addresses in the page;
  **no stable identifier in the markup was a STOP-and-decide**, decided at
  build (A2): the page marks none, `external_id` is the content hash of
  (publication date, experience date, rating, body), an edited review is a
  new review, and the BACKLOG row carries the trigger for keying on the dates
  and rating instead. Peers on that platform may be declared the same way at
  the developer's choice within the letter's scope (a traditional or
  digital-challenger segment, capped by `MAX_PAGES`); each is a declaration,
  not a branch.
  The hand-entry path: `data/snapshots/manual_snapshots.csv`, tracked (the
  subtree `.gitignore` already reserves for public aggregates), hand-edited,
  exactly eight columns: `source` (a declared source name whose `fetchable`
  is False), `captured_at` (`YYYY-MM-DD`, the day the figure was read),
  `rating`, `review_count`, `one_star_share`, `response_rate`,
  `response_delay_days` (the last three empty when the page does not show
  them) and `read_from`, always the word `page` (the figure was read off the
  declared address) — no address, no name, no free text. `make rebuild`
  parses it strictly (an undeclared or fetchable source name, a bad number, a
  share outside 0–1, a date that is not one, a
  wrong column set: one-line refusal naming the line and field); platform,
  address, profile, segment and channel come from the declaration; the row
  loads with `origin = manual`; a row entered twice loads once. No make
  target: a person's reading is a person's edit, and the loader is the
  guard. The 2026-09-02 App Store reading (4.9, about 13,000 ratings) is the
  first row — the developer confirms it against the page before entering;
  the Opinion Assurances aggregate comes from the fetch (A1).
  Satisfies invariants 3, 5 and 6. Rejected: fetching a page whose terms say
  no because its robots file says yes (both bind us); a `make snapshot`
  target with eight variables (eight threat-model rows for a CSV edit);
  storing the address in the file (D1 confines it to the declaration); a
  clock stamp for a manual row (the reader states the day; the only clock
  stays the fetcher's).
- **`ROWS` names the rebuild input; `samples` runs every frozen sample (D4,
  BACKLOG rows "`FIXTURE=cache` naming" and "frozen `robots.txt` read by
  nothing").** `make rebuild [ROWS=captured|none|synthetic|samples]` and
  `make idempotency-check [ROWS=…]` replace `FIXTURE`, same closed-set shape
  (validated in Python, never a path), defaults unchanged in meaning
  (`captured` for `rebuild`, `synthetic` for `idempotency-check`);
  `warehouse.database_for` names the files `friction_ledger.duckdb`
  (captured) and `friction_ledger.<input>.duckdb`; `reset` drops that set.
  `captured` loads the anchors, the manual file and every capture; `samples`
  loads the anchors and, for every parser a declared source names,
  `fixtures/<parser-slug>/` as one capture of a sample declaration whose
  `profile`, `segment` and `channel` are the literal `sample` — labels that
  exist only in the samples database. Three sample directories: the existing
  `fixtures/app-store/` (its `robots.txt` re-frozen to the real rule,
  `User-agent: *` / `Disallow: /*/rss/*`, so the frozen capture documents
  why its source is not fetched; `tests/test_robots.py` reads it through
  `Robots.parse` and asserts the sample's page address is disallowed), and
  two new hand-written, fake, nameless ones: `fixtures/listings/` (one page
  in the JSON-LD shape with fake values and a placeholder author, with its
  meta) and `fixtures/opinion-assurances/` (A1: two profile pages in the
  microdata shape with fictional reviews and placeholder pseudonyms, one
  review shared across the two pages, an aggregate, and a third page with no
  review scope — the end of the list). Each has a `MANIFEST.sha256`; `Freeze:`
  lines below; malformed variants are
  built in tests by mutation. Every doc, the Makefile, CI and the tests move
  from `FIXTURE` to `ROWS` in one commit; DECISIONS marks Phase 2's `FIXTURE`
  decision superseded. Satisfies invariant 7. Rejected: keeping `FIXTURE`
  and recording why (the name calls the real corpus a fixture, which the
  study-editor found and the writing rule forbids); one `ROWS` value per
  sample (the set would grow with every parser).
- **The robots matcher matches directly, in linear time (BACKLOG row
  "wildcard backtracking bound").** `ingest/robots.py::_matches` becomes a
  two-pointer glob match (`*` any run, trailing `$` anchors, everything else
  literal; anchored at the path's start) with no regex, so time is bounded by
  pattern length × path length and a pathological file cannot stall `make
  scrape`. The matching table (`$`, inner `*`, longest match, Allow on a tie)
  is unchanged and its test stands; the three real robots files read on
  2026-09-02 give the same verdicts as before the rewrite (a test carries
  their rules, not their files). A new pin: thirty wildcards against a
  300-character non-matching path under 50 ms. Satisfies invariant 5.
  Rejected: a cap on the number of `*` per pattern (a denylist on the input;
  the kind change is the fix); `fnmatch` (translates to the same regex).

(6 pinned decisions.)

## Scope (files)

New code:
- `ingest/sources.py` — `Source`, `CACHE_ROOT`, `SEGMENTS`, `CHANNELS`,
  `ORIGINS`, the parser closed set, `SOURCES` (the four declarations above,
  D1), `sample_source(parser)`.
- `ingest/listing.py` — the JSON-LD `AggregateRating` parser (exactly one
  per page, strict; `Parsed(snapshots=[one row])`; `ratingValue` and
  `ratingCount` or `reviewCount` as digit strings or numbers, nothing else
  read). `ingest/opinion_assurances.py` (A1) — the microdata parser: stdlib
  `html.parser` walking `itemscope`/`itemprop`, `Parsed(reviews, snapshots)`,
  the `author` scope skipped, the field addresses declared in its header.
  `ingest/app_store.py` — `parse_page` returns `Parsed`;
  `read_captures`, `read_meta`, `capture_pages` move to a parser-neutral
  `ingest/captures.py` (one reader for every parser, the extension from the
  parser).
- `ingest/fetch.py` — `scrape(source, …)` reads host, robots address, page
  addresses, cap and parser from the declaration; a `fetchable=False` source
  is refused before any request (unchanged); a review-page source stops at
  the first page with no review scope. `ingest/robots.py` — `_matches`
  rewritten (pinned decision 6). `ingest/politeness.py` — `ALLOWED_HOSTS =
  ("itunes.apple.com", "play.google.com", "www.opinion-assurances.fr")`;
  `MAX_PAGES = 60` (A1).
- `pipeline/build.py` — `INPUTS = ("captured", "none", "synthetic",
  "samples")`; `seed_anchors` and `load_manual_snapshots` (strict CSV →
  `raw_platform_snapshots`), `load_snapshots`, `write_source_pages`; capture
  loading iterates `SOURCES`. `pipeline/cli.py` — `--rows`; the no-captures
  hint names the cache root; reviews per month per source; `scrape` lists the fetchable
  sources' hosts in its prompt. `pipeline/warehouse.py` — `database_for(rows)`.
  `pipeline/sql_lint.py` — `like`, `similar to`.
- `sql/raw/raw_platform_snapshots.sql`, `sql/raw/raw_source_pages.sql`,
  `sql/staging/stg_platform_snapshots.sql`, `sql/marts/rating_trend.sql`,
  `sql/marts/channel_gap.sql`, `sql/marts/platform_stats.sql`,
  `sql/marts/peer_ratings.sql`.
- `data/snapshots/manual_snapshots.csv` — the header row and the 2026-09-02
  App Store reading, entered by the developer.
- `Makefile` — `ROWS` replaces `FIXTURE` (`unexport`, help lines, the two
  recipes). `.github/workflows/ci.yml` — `ROWS=synthetic`, `ROWS=samples`.

Fixtures (frozen this phase; see the `Freeze:` lines):
- `fixtures/anchors/platform_snapshots_seed.csv` re-frozen with `profile`,
  `channel` and the three B1.4 columns (D2); `fixtures/app-store/robots.txt`
  re-frozen to the real rule; `fixtures/listings/` and
  `fixtures/opinion-assurances/` new; each with `MANIFEST.sha256`.

New and extended tests:
- `tests/test_snapshots.py`, `tests/test_marts.py`,
  `tests/test_listing_parser.py`, `tests/test_opinion_assurances_parser.py`,
  `tests/test_fetch_sources.py` new;
  `tests/test_robots.py`, `tests/test_ingest_layout.py`,
  `tests/test_ingest_rebuild.py`, `tests/test_provenance.py`,
  `tests/test_sql_portable.py`, `tests/test_makefile.py`, `tests/test_cli.py`,
  `tests/test_fixtures_frozen.py`, `tests/conftest.py` (`ROWS` scrubbed in
  place of `FIXTURE`), `tests/pins.py` (anchor rows per mart; the listing
  sample's row) extended.

Records (see Record updates): `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`,
`BACKING.md`, `SPEC.md`, `PROJECT_BRIEF.md`, `docs/PLAN.md`, this spec.

Freeze: fixtures/anchors/
Freeze: fixtures/app-store/
Freeze: fixtures/listings/
Freeze: fixtures/opinion-assurances/

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 3a entry: the snapshot shape, the anchors
      re-freeze (D2) and tag (D3); the four marts and the Documented flip;
      the source declaration and parser dispatch; under "Scrape politely",
      the position of each source as checked on 2026-09-02 (Google Play
      listing allowed by robots and terms, its reviews disallowed; App Store
      listing forbidden by Apple's site terms; Opinion Assurances: CGU V.3
      forbids automated extraction without written authorization, and the
      developer holds that authorization — A1, with its date) and the
      hand-entry path; D1 as
      a standing neutrality decision; the `ROWS` rename with a supersede
      pointer on Phase 2's `FIXTURE` decision; the linear matcher; the
      `like` widening of the lint; Gotchas from the checks (the by-id App
      Store address redirects; the checks ran from the session, not by hand)
      and from the first live run
- [ ] `BACKLOG.md` — five rows closed (struck + "DONE Phase 3a"): the
      wildcard bound, the `DEFAULT_CACHE` / `ALLOWED_HOSTS` binding, the
      `FIXTURE=cache` naming, the hardwired capture path, the permissive
      frozen `robots.txt`; the health-details row re-deferred with the
      trigger "the first tracked file or published panel carrying review
      text" (this phase's tracked file carries numbers only); rows opened:
      the App Store listing's JSON-LD shape is unverified (trigger:
      any future permission to fetch it); the weekly run's re-fetch stops at
      the first page with no unseen row (trigger Phase 4)
- [ ] `CLAUDE.md` — Current status; Commands (`ROWS`; `scrape`'s hosts; the
      manual file); Repo map (`ingest/captures.py`, `listing.py`, the four
      marts, `fixtures/listings/`, `data/snapshots/manual_snapshots.csv`,
      `sql/marts/` no longer empty); BACKLOG count
- [ ] `BACKING.md` — B1.2, B1.3, B1.4, B2.3 Pending → Documented with sources
      of the declared shape
- [ ] `SPEC.md` — the four panels' tag sentences and the header's "Today
      every row is Pending" (a tag change, not a chart change — flagged here,
      approved with the spec)
- [ ] `PROJECT_BRIEF.md` — §6: anchors "appear in the study with Documented
      tags, marked as seeded" (D3); §9 Phase 3 unchanged in meaning
- [ ] `docs/PLAN.md` — §5 row 3a: the DONE command and the sources as built
- [ ] README — none (Phase 9)
- [ ] `specs/phase-3a-snapshots.md` — this spec; the "Delivered" paragraph at
      exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

No new target. Three existing targets change shape: `scrape` reaches one more
host; `rebuild` and `idempotency-check` take `ROWS` in place of `FIXTURE` and
`rebuild` reads one more input file; `reset`'s closed set of files follows the
new input names. Settled shape unchanged: one Python process validates each
value against a closed set, derives every path from the validated name,
prompts on a tty, then acts; every recipe is one line; every user variable
reaches Python unexpanded and single-quoted via `$(call _Q,$(value VAR))` and
is `unexport`ed.

**What `scrape` reaches and costs.** Hosts: exactly `ALLOWED_HOSTS` —
`itunes.apple.com` (declared, refused before any request), `play.google.com`
and `www.opinion-assurances.fr` (A1); a source on any other host is refused
before a request, and the non-fetchable sources are refused on their
declaration before the allowlist is consulted. Per run: one `robots.txt` plus
one listing page on Play (two requests, about 1.3 MB); one `robots.txt` plus
up to `pages` profile pages on Opinion Assurances (15 requests and about 5 MB
for the studied insurer; a peer up to 61), every request ≥ 2 s apart per host
or the host's Crawl-delay up to 60 s — under a minute for the studied
insurer, two for a capped peer. Run twice: the same again into a second
capture directory (public pages, no cost, no key); the second rebuild then
adds zero raw rows if nothing changed (invariant 1; Phase 2's invariant 3).
No credentials: none needed, none read (`ingest/` never opens `.env`; the
test stands). Refused (robots disallow, a non-robots body, non-200, timeout):
one line naming host, status and address, no retry, exit 2. Personal data:
the listing page carries a few reviews with display names and the profile
pages carry pseudonyms and free text; every page is archived as served under
gitignored `data/`; the listing parser reads the `AggregateRating` and
nothing else, the profile parser skips the `author` scope; nothing under
`data/cache/` is tracked or excerpted.

**What `rebuild` reads from the hand-entry file.** A tracked CSV the developer
edits; no variable names it. Eight declared columns, closed sets and numeric
ranges, a one-line refusal naming line and field on any deviation; a source
name that is not declared, or is declared fetchable, refuses (a fetched
source's figures come from its capture, never from a hand entry); the file
holds no address, no name, no free text (`read_from` is the word `page`).

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `scrape` | `SOURCE` empty → every declared source (non-fetchable ones report one line each; each fetchable one fetches — two today, on two hosts, at most 60 pages each); `CONFIRM` empty → prompt on a tty, refuse non-interactively, no request | `SOURCE` refused — a declared name, never a path; the capture directory is derived from the declaration | one literal arg; not a declared name → refused | `unexport`ed; validated in Python; `CONFIRM=yes` from the environment → `$(origin)` = `environment` → refused, no request | `CONFIRM=yes` counts only from the command line | `tests/test_makefile.py::test_scrape_requires_command_line_confirm`, `::test_scrape_source_is_a_closed_set`, `::test_scrape_variables_reach_python_as_one_literal`; `tests/test_cli.py::test_cli_scrape_skips_a_source_declared_not_fetchable_and_exits_0`, `::test_cli_scrape_exits_2_only_on_a_refusal_met_during_the_run`, `::test_cli_scrape_naming_a_source_declared_not_fetchable_is_a_refusal` (round 1: a plain run skips such a source with one line; naming it, or a refusal met during the run, is exit 2) |
| `rebuild` | `ROWS` → `captured` (zero captures → the anchors and the manual file, with a one-line hint) | refused (closed set of four names) | one literal arg; refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set` (re-pinned to `ROWS`), `tests/test_cli.py::test_cli_refuses_bad_rows_with_exit_2` |
| `idempotency-check` | `ROWS` → `synthetic` | refused | refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_idempotency_check_variables_are_a_closed_set` (re-pinned) |
| `reset` | unchanged: prompt or refuse | n/a (no path taken) | n/a | `CONFIRM=yes` from the environment does not confirm | command line only | `tests/test_makefile.py::test_reset_requires_command_line_confirm`, `tests/test_cli.py::test_reset_removes_only_the_db_and_wal` (the file set re-pinned to the `ROWS` names) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").
The range touches Code (`ingest/**`, `pipeline/**`, `sql/**`, `Makefile`,
`tests/`), Sensitive (`ingest/**`, `.github/workflows/ci.yml`, the network
target) and Prose (`SPEC.md`, `BACKING.md`, `CLAUDE.md`). The union runs:
code-reviewer, functionality-tester, **security-reviewer (mandatory — a new
host, a new parser of a page written by strangers, a tracked file under
`data/`)**, study-editor (`SPEC.md`'s panel sentences, `BACKING.md`'s claims,
`CLAUDE.md`), and coherence-auditor at exit.

- **code-reviewer** (triggered): `raw_reviews` and `load_reviews` untouched;
  every new raw table carries the four provenance columns; no clock and no
  pattern in `sql/`; the four marts are window selects with no `order by`;
  nothing branches on a platform name; the cache root is bound once; `ROWS`
  a closed set; the matcher regex-free; the manual loader strict; the
  samples frozen; scope (every file maps to a snapshot row, a source, a
  BACKLOG row or a record).
- **security-reviewer** (mandatory): scrape conduct on the one fetchable host
  — robots read first, both groups consulted, the interval, the User-Agent,
  no retry, proxy or rotation; the non-fetchable sources refused before any
  request with their terms recorded; D1 honoured (a brand-carrying address
  appears in `ingest/sources.py` only — not in the manual file, a test name,
  a fixture, a comment or a commit); no name or review text in any tracked
  file (the sample is fake by construction; the manual file is numbers); the
  rest of `data/` still gitignored; CI still `contents: read` and offline;
  `.env` never read by `ingest/`.
- **functionality-tester** (triggered): the DONE command on the developer's
  cache and file; Phase 1's line still green; `ROWS=samples` and `ROWS=none`
  green; the anchors seeded identically under every input but `none`; the
  listing parser's negatives; a manual row for a fetchable source refused; a
  shrunk allowlist does not unload a declared source's capture;
  hand-mutations: read the block's `author`, let a second `AggregateRating`
  through, branch on a platform name, put `like` in a mart, restore the
  regex matcher, fetch a `fetchable=False` source when robots allows.
- **study-editor** (triggered): `SPEC.md`'s four panel sentences and the
  header in the two-layer voice; `BACKING.md`'s four flipped claims; the
  sampling-bias sentence still beside B1.2; no insurer named in any prose the
  phase touches.
- **coherence-auditor** at exit: `SPEC` ↔ `BACKING` ↔ `sql/marts` reconcile
  (4 marts, 4 Documented, 15 Pending); no "Today every row is Pending"; the
  Repo map names the new modules and marks `sql/marts/` as populated; every
  `FIXTURE` mention is gone from every doc, the Makefile and CI; DECISIONS
  carries each source's position; brief §6 says Documented; the five BACKLOG
  rows are struck with the right phase, the health row re-deferred, and the
  count matches.
- **Stack risk — the candidate checks, done 2026-09-02 before approval** (from
  the build session at the developer's request; `curl` and the stdlib client
  with the project's User-Agent, one request per page, ≥ 2 s per host, saved
  outside the repo; the three robots files were run through
  `ingest/robots.py`; two pages were read through a text summary because the
  session's download permission was withdrawn midway, so their script blocks
  were not seen):
  1. `www.opinion-assurances.fr/robots.txt` — catch-all group: `Disallow:
     /*?*`, `/api/*`, a few site paths; no Crawl-delay; ~190 named bots
     disallowed entirely, none ours. The profile and its `…-page2.html` pages
     are allowed; any query-string address is not. **Terms: conditions
     générales V.3 forbids automated data extraction without prior written
     authorization; V.1 forbids reproduction without written agreement.**
     Page: ~40 reviews a page; stars, pseudonym, publication and experience
     dates, body, insurer reply; header 3.8 / 534 / 23.1 % one-star / 82 %
     answered / 1.5 days — the brief's §6 anchor to the decimal. No JSON-LD
     seen in the text summary (unverified either way; moot, not fetched).
  2. `play.google.com/robots.txt` — catch-all disallows `/_`,
     `/store/getreviews`, `/store/xhr`, `/store/search` and more; the details
     path is allowed. Google's terms: automated access is forbidden only
     where it breaches robots.txt. The details page (with `hl=fr&gl=FR`):
     200, no redirect, ~1.3 MB, one JSON-LD `SoftwareApplication` block with
     `aggregateRating.ratingValue` "4.766…" and `ratingCount` "6584" as
     strings — in the source itself.
  3. `apps.apple.com/robots.txt` — disallows `/WebObjects/*`, `/api/*`,
     `/includes/*`, `/v1/*`, `*/search?*`; `/fr/app/…` allowed. **Apple's
     website terms of use, "Your Use of the Site", forbid robots, spiders,
     page-scraping and automated copying, with no robots.txt carve-out.** The
     by-id address answers 301 to a slug address; the listing shows 4.9 and
     about 13,000 ratings; its JSON-LD is unverified (download withdrawn).
  4. No challenge page was met on any host.
  **Disposition, taken:** re-scope to snapshots (this revision), then A1 at
  approval: the authorization arrived and Opinion Assurances is a review
  source again. **To verify in the first hour of the build:** (1) the Opinion
  Assurances page structure, from the redacted dump the developer runs
  (`inspect_oa_structure.py` in the session scratchpad, via `!` — the
  session's own analysis of the saved page is blocked): where the review date
  and body sit and in what format the date is written; whether each `review`
  scope carries a stable identifier (an `id`, a `data-*` attribute or a
  permalink) — none is a STOP-and-decide; whether the one-star share, response
  rate and response delay are data (`content`/`itemprop`) or layout text; what
  the page past the last (`-page15.html`) returns — unanswered offline (round
  1): the first live run answers it; until then the fetcher's rule stands — it
  never asks for a page past the declaration, stops at the first page with no
  review, and a non-200 refuses the run keeping the pages already written. (2)
  The Play block's field types hold on a second day (strings, not numbers —
  the parser accepts both, strictly). (3) A second `make scrape` an hour later
  adds no raw row when nothing changed. Anything else surprising is a STOP;
  findings go to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- Trustpilot, its bot handling and any automated path for a refusing host —
  Phase 3b (PLAN §5).
- Review rows from the two app stores: Google Play reviews are behind a
  disallowed call and are not fetched; the App Store feed is disallowed.
  Opinion Assurances is the one review source (A1).
- The App Store listing's machine-readable block — unverified, not needed
  (hand-entered); BACKLOG row.
- The weekly schedule and the `data/snapshots/` commit of captures — Phase
  4; the stop-at-first-known-row re-fetch — BACKLOG row, trigger Phase 4.
- Per-review theme charts that consume `source_pages` (B2.2, B2.5) — Phases
  5b–7; the join is landed and pinned here, the charts are not.
- The health-details rule for excerpts — BACKLOG row re-deferred; the tracked
  file this phase adds carries numbers only.
- Classification, the cost model, the study — Phases 5–9.
