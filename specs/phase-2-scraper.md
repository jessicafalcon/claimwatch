# Phase 2 — One scraper, end to end (APPROVED)

Contract for the `phase-2-scraper` branch. Source: PROJECT_BRIEF.md §9 Phase 2
(one scraper, end to end), scoped by `docs/PLAN.md` §5 row 2 (the App Store
review feed, recommended over Opinion Assurances) and §2's Boundary/Adapter row
(a scraped page is a foreign input: parse strictly to a declared shape). Depends
on `phase-1-schema` merged (PR #3).

**Status: APPROVED 2026-09-02 — in progress.** One dependency change:
`httpx` (pre-approved for Phase 2, CLAUDE.md → Conventions). `pyyaml` is also
pre-approved for Phase 2 but nothing here needs it — the source list and the
politeness knobs are Python constants — so it waits for `rules.yaml` (Phase 5b).
No pandas on any pipeline path; anything beyond `httpx` is a STOP-and-ask.

## Why

Phase 1 built the warehouse and proved it runs the same way twice, but every
row in it is hand-written. Phase 2 puts the first real reviews through the same
path: fetch one public review feed politely, parse it strictly into the exact
eight-column raw shape Phase 1 defined, load it with the same idempotent guard,
and read one metric out of staging — reviews per month. The point is the path,
not the volume: one source, one feed, one metric, and the proof that a re-scrape
of unchanged reviews adds nothing. Phase 3 adds the other sources; Phase 4 puts
this on a schedule. Nothing here classifies, models or publishes.

**Teaching notes (become code comments / README lines at build — CLAUDE.md →
Teaching rule).**
- *A public review feed, fetched politely.* App stores publish each app's
  customer reviews as a public feed — a plain web address that returns the
  most recent reviews as JSON, no account or key needed. We fetch it the way a
  considerate person would: we read the site's `robots.txt` first and stop if
  it says no, we send a User-Agent string that names this project so the site
  knows who is asking, we wait at least two seconds between requests, and we
  keep every page we fetched under `data/` so a rebuild never asks the site
  again. `httpx` is the small library that makes the request; the manners are
  ours, in one file.
- *Strict parsing of a foreign JSON shape.* A page we did not write can change
  under us. So the parser declares exactly which fields it expects and what type
  each must be, and refuses the whole page — naming the item and the field —
  the moment one is missing or malformed. It never guesses a rating, defaults a
  date, or drops a review quietly, because a silently skipped review would move
  a count with no trace. The list of accepted fields is the contract with the
  feed; widening it is a deliberate, tested change.

## The central constraint

**Phase 1's raw shape, load path, and run-twice property do not move: the
scraper writes the identical eight raw columns through the same `load_reviews`
guard, a re-scrape of unchanged reviews adds no raw row, and the data path stays
clock-free, network-free at rebuild time, and model-free.** Exactly one source
is added; `fixtures/synthetic/` and `fixtures/anchors/` stay byte-identical; no
mart lands (`check-backing` stays at 19 rows, 0 marts, 0 orphans); `make test`
and CI open no socket; the live fetch is run by the developer, never by an
agent.

## DONE command

```
make rebuild FIXTURE=app-store && make idempotency-check FIXTURE=app-store
```

Amended 2026-09-02 (fix amendment A1, approved). It was `make rebuild && make
idempotency-check FIXTURE=cache` over a live capture. The first live run showed
the host's `robots.txt` disallows the feed path for every crawler, so a capture
of this source cannot be the phase's proof; that capture and its database were
deleted. The DONE command is the real parser over the frozen capture, offline
— the same path CI runs. The real-rows proof moves to the first source whose
robots allows it (Phase 3a).

- `make rebuild FIXTURE=app-store` — the frozen capture is parsed strictly,
  loaded into `raw_reviews` through Phase 1's guard, `stg_reviews` is rebuilt,
  and the per-table counts are printed followed by the reviews-per-month
  table: raw 8 / staging 8, three months (`tests/pins.py`). Each input builds
  its own database file (A2), so the counts are the sample's own.
- `make idempotency-check FIXTURE=app-store` — rebuilds twice from the same
  capture into a throwaway database and diffs per-table counts.
- Also green: `make rebuild` (the default, `cache`: every capture under
  `data/cache/app-store/` through the same path; zero captures → zero rows
  with a one-line hint) and `make idempotency-check FIXTURE=cache`; `make
  rebuild FIXTURE=synthetic && make idempotency-check` (Phase 1's DONE
  command, unchanged: raw 40 / staging 39); `make rebuild FIXTURE=empty`;
  `make test`; `make check-backing` (19 rows, 0 marts); `make check-docs`
  (BACKLOG count 12).

## Done-when

1. **The fetcher is polite, and its manners live in one place.** Before the
   first feed request it fetches and obeys the host's `robots.txt` (a disallow
   is a one-line refusal, no feed request); every request carries the
   identifying User-Agent; consecutive requests to the host are ≥ 2 s apart;
   there is no proxy, rotation, or retry loop; every page is archived
   byte-exact under `data/cache/` with its `captured_at` and `source_url`
   beside it. `make scrape` is the only network target and is CONFIRM-gated
   like `reset`. *Evidence: row 1.*
2. **The parser is a strict parse of a declared shape.** A feed item missing a
   required field, carrying the wrong type, a rating outside 1–5, or a
   timestamp that is not ISO 8601 refuses the whole page, naming the page, the
   item and the field; nothing partial is loaded. A well-formed item maps to
   exactly the eight raw columns; the `author` fields are never read. *Evidence:
   row 2.*
3. **`make rebuild` produces real rows and the metric through Phase 1's path.**
   Cached captures (or the frozen sample under `FIXTURE=app-store`) reach
   `raw_reviews` via the unchanged `load_reviews` guard, `stg_reviews` dedups
   them, and `reviews_per_month` is printed and pinned; `sql/` gains no file.
   *Evidence: row 3.*
4. **Idempotency holds on real rows.** A second rebuild from the same captures,
   and a second capture of unchanged pages at a later `captured_at`, add no raw
   row; the metric is identical run to run. *Evidence: row 4.*
5. **No clock, no network on the data path.** `captured_at` is stamped in
   Python at fetch and read back from the capture at rebuild; `review_date` is
   the item's own date; the metric query passes the clock and portability
   lint; `httpx` is imported only by the fetcher; the test suite blocks every
   socket connection. *Evidence: row 5.*
6. **One source, one frozen sample, no personal data.** `ingest/sources.py`
   declares exactly one source; `fixtures/app-store/` is hand-written fake
   content in the feed's exact shape and matches its `MANIFEST.sha256`; no
   tracked file holds a reviewer name or a real review. *Evidence: row 6.*

(6 items. Each is a contract, not a narrative.)

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `tests/test_app_store_fetch.py::test_robots_disallow_refuses_before_any_feed_request`, `::test_every_request_carries_the_identifying_user_agent`, `::test_consecutive_requests_are_spaced_two_seconds`, `::test_pages_are_archived_byte_exact_with_meta`, `::test_non_200_is_a_one_line_refusal_with_no_retry`; `tests/test_makefile.py::test_scrape_requires_command_line_confirm`, `::test_scrape_source_is_a_closed_set`; `tests/test_ingest_layout.py::test_politeness_knobs_live_in_one_module` |
| 2 | `tests/test_app_store_parser.py::test_well_formed_item_maps_to_the_eight_raw_columns`, `::test_missing_required_field_refuses_the_page` (parametrized over every required field), `::test_mistyped_field_refuses_the_page`, `::test_rating_outside_1_to_5_is_refused`, `::test_malformed_timestamp_is_refused`, `::test_refusal_names_page_item_and_field`, `::test_author_fields_are_never_read` |
| 3 | `make rebuild` prints per-table counts and the `reviews_per_month` table; `tests/test_ingest_rebuild.py::test_rebuild_from_sample_matches_pins`, `::test_reviews_per_month_matches_pins`; code-reviewer confirms `load_reviews` is unchanged and `sql/` gains no file; functionality-tester runs the DONE command |
| 4 | `make idempotency-check FIXTURE=app-store` prints every count unchanged (and `FIXTURE=cache` on zero captures); `tests/test_ingest_rebuild.py::test_second_rebuild_from_captures_adds_no_rows`, `::test_second_capture_of_unchanged_pages_adds_no_rows`, `::test_edited_review_in_a_later_capture_appends_one_row`, `::test_reviews_per_month_is_stable_across_rebuilds` |
| 5 | `tests/test_ingest_rebuild.py::test_rebuild_from_captures_is_byte_stable_under_a_moving_clock`; `tests/test_sql_portable.py::test_metric_query_is_portable_and_clock_free`; `tests/test_ingest_layout.py::test_httpx_is_imported_only_by_the_fetcher`; `tests/test_offline.py::test_socket_connect_is_blocked_in_the_suite` |
| 6 | `tests/test_ingest_layout.py::test_exactly_one_source_is_declared`; `tests/test_fixtures_frozen.py::test_manifests_match` (extended to `fixtures/app-store/`); `tests/test_app_store_parser.py::test_sample_is_obviously_fake_and_nameless`; security-reviewer confirms no real review or name in a tracked file and `data/cache/` is gitignored |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| 1. For all feed items, either every required field is present with its declared type or the page is refused with the item id and field named, and nothing from that page is loaded. | `tests/test_app_store_parser.py::test_missing_required_field_refuses_the_page`, `::test_mistyped_field_refuses_the_page`, `::test_refusal_names_page_item_and_field` — one item on a two-item page loses `im:rating`; the page yields zero rows, not one |
| 2. For all feed items, `rating` is the integer 1–5 the feed's digit string denotes and `review_date` is the `YYYY-MM-DD` of the item's own ISO 8601 timestamp; any other value is refused, never defaulted. | `tests/test_app_store_parser.py::test_rating_outside_1_to_5_is_refused` (`"0"`, `"6"`, `"4.5"`, `""`, `4`), `::test_malformed_timestamp_is_refused` (`"2025-13-40T00:00:00Z"`, `"yesterday"`, `""`) — a refusal, not a default row |
| 3. For all captures, a second rebuild from the same captures, and a later capture of unchanged pages, leave every raw row count unchanged and the reviews-per-month table identical; an edited review appends exactly one raw row. | `tests/test_ingest_rebuild.py::test_second_rebuild_from_captures_adds_no_rows`, `::test_second_capture_of_unchanged_pages_adds_no_rows`, `::test_edited_review_in_a_later_capture_appends_one_row`, `::test_reviews_per_month_is_stable_across_rebuilds` |
| 4. For all raw rows written by the scraper path, `captured_at` is the value stamped at fetch and read back from the capture, and `review_date` is the item's own date: a rebuild reads no clock, so two rebuilds under different wall-clock times are byte-identical. | `tests/test_ingest_rebuild.py::test_rebuild_from_captures_is_byte_stable_under_a_moving_clock` — the clock is patched to two different instants; `raw_reviews` content is identical; `tests/test_sql_portable.py::test_metric_query_is_portable_and_clock_free` |
| 5. For all requests the fetcher makes, the host's `robots.txt` was read first and allowed the path, the identifying User-Agent is set, and the previous request to that host was ≥ 2 s earlier; a disallow, a non-200 or a timeout is a one-line refusal with no retry, no proxy, no rotation. | `tests/test_app_store_fetch.py::test_robots_disallow_refuses_before_any_feed_request`, `::test_every_request_carries_the_identifying_user_agent`, `::test_consecutive_requests_are_spaced_two_seconds`, `::test_non_200_is_a_one_line_refusal_with_no_retry` — all against `httpx.MockTransport` |
| 6. For all modules in the repo, `httpx` is imported only by `ingest/fetch.py`, and the politeness knobs are defined only in `ingest/politeness.py`; for all tests, no socket connection is opened. | `tests/test_ingest_layout.py::test_httpx_is_imported_only_by_the_fetcher`, `::test_politeness_knobs_live_in_one_module`, `tests/test_offline.py::test_socket_connect_is_blocked_in_the_suite` — a planted `socket.create_connection` raises |
| 7. For all sources, exactly one is declared in Phase 2, and for all tracked files, none holds a reviewer's name or a real review: `fixtures/app-store/` is hand-written and matches its MANIFEST. | `tests/test_ingest_layout.py::test_exactly_one_source_is_declared`, `tests/test_fixtures_frozen.py::test_manifests_match`, `tests/test_app_store_parser.py::test_sample_is_obviously_fake_and_nameless` |

### Fix amendments — review round 1 (2026-09-02)

Each paragraph names the invariant it restores and changes the KIND of a
mechanism, never its list. Committed alone; implemented only after approval.

**A1 — robots.txt is matched by our own RFC 9309 matcher, for every page,
and Crawl-delay is honoured** (security-reviewer #1 #2 #4, code-reviewer #1).
Restores invariant 5: "the host's `robots.txt` was read first and allowed the
path". The stdlib parser is the wrong kind: on Python 3.12 it matches prefixes
only and silently ignores wildcards, so the live host's rule `Disallow:
/*/rss/*` under `User-agent: *` was read and passed, and the 2026-09-02 capture
was fetched from a path the site disallows. New kind: a small matcher in
`ingest/robots.py` that parses the file into groups, picks the group whose
product token is a case-insensitive substring of ours (else `*`), matches
`Allow`/`Disallow` patterns with `*` and `$`, lets the longest match win and
`Allow` win a tie, and returns the group's `Crawl-delay` so the per-host
interval becomes `max(MIN_INTERVAL_S, delay)`. Every page URL is checked before
its own request. Pinned by: the archived real rule against the real feed path
refuses; `Allow: /fr/rss/$` beats `Disallow: /fr/rss/`; page 1 allowed and page
2 disallowed stops after page 1; a `Crawl-delay: 5` yields 5 s sleeps; the
matcher is the only robots code (`urllib.robotparser` is grepped absent).
*Consequence, for decision:* this source refuses under the corrected matcher,
so the DONE command's precondition (a capture of it) can no longer be met
honestly. The spec's own disposition (Review & stack risk, item 1) and PLAN
§6.2 apply: the fallback is a manually captured snapshot (rating, count, URL,
date) tagged Measured, which is Phase 3a's `platform_snapshots` path, never a
different User-Agent or a "syndication feeds don't count" reading. Proposed:
the DONE command becomes `make rebuild FIXTURE=app-store && make
idempotency-check FIXTURE=app-store` (the real parser on the frozen capture),
the real-rows proof moves to the first source whose robots allows it (Phase
3a), the 2026-09-02 capture and the working database built from it are
deleted, and DECISIONS records the disallow under the terms position. The app
id stays a sourced data point only if a source URL is recorded beside it
(code-reviewer #7); otherwise it returns to 0. *Decided 2026-09-02:* all of
the above; the id stays with its listing address beside it; study-editor's
`FIXTURE` → `ROWS` rename is deferred to a BACKLOG row (it touches the DONE
command and every doc).

**A2 — one database file per input; a fixture can never land in the real
corpus** (code-reviewer #3, functionality-tester #3). Restores invariant 3 as
the DONE command reads it: the counts `make rebuild FIXTURE=X` prints are the
counts of X. Today every input appends into `data/friction_ledger.duckdb`, so
CI's `FIXTURE=app-store` after `synthetic` prints 48, and the sample's eight
fake rows sit in the real database under the same `source` slug,
distinguishable only by `run_id`. New kind: `warehouse.py` derives the file
from the input — `friction_ledger.duckdb` for `cache`, `friction_ledger.
<fixture>.duckdb` for `empty|synthetic|app-store` — and `reset` drops that
closed set. Raw stays append-only within a file (a second `cache` rebuild
still adds no row). Pinned by: `main(["rebuild", "--fixture=app-store"])` then
`main(["rebuild"])` on a temp `data/` prints 8 and 0; a `synthetic` rebuild
leaves the `cache` file absent; `reset` names every file it removed.

**A3 — a page the strict parser refuses is archived under a name a rebuild
never loads; a malformed stored page is a one-line refusal** (code-reviewer
#4, functionality-tester #2). Restores invariant 1 ("nothing from that page is
loaded") together with the CLI's contract ("never a traceback"). Today the
fetcher writes `page-<n>.json` before parsing it, so one shape change leaves a
poison page that breaks every later `make rebuild` with a traceback until it is
deleted by hand. New kind: the fetcher parses first and writes a refused page
as `page-<n>.refused.json` beside its meta (evidence kept, never loaded);
the CLI's `main` turns a `FeedShapeError` from a stored capture into the same
one-line refusal as a `Refused` (naming capture, page, item and field, exit 2). Pinned by: a fetch
that meets a malformed page leaves `page-1.refused.json` and no `page-1.json`,
and a rebuild over that capture loads zero rows from it without refusing; a
hand-corrupted `page-1.json` makes `main(["rebuild"])` return 2 with one
stderr line and no traceback.

**A4 — capture meta is parsed strictly to its declared shape** (code-reviewer
#5, functionality-tester #1). Restores the Provenance contract for the row's
own columns: `read_meta` checks the key set and two `isinstance`s, so
`captured_at: ""`, `"yesterday"`, an empty `source_url` or `status: 500` load
silently, and `captured_at` is staging's dedup sort key. New kind: a strict
parse — `captured_at` must be exactly `YYYY-MM-DDTHH:MM:SS` (what the fetcher
writes), `source_url` an `https` URL whose host is in `ALLOWED_HOSTS`, `status`
the integer 200 — any other value refuses the capture with the file and field
named. `status` thereby becomes a guard rather than a decoration (code-reviewer
#11). Pinned by: one parametrized test over each bad value.

### Fix amendments — review round 2 (2026-09-02)

**A5 — a robots verdict is authoritative only from a recognised robots body;
a source can be declared not-fetchable; our group is matched by substring**
(security-reviewer #1 #2 #3, code-reviewer #1). Restores invariant 5 ("the
host's `robots.txt` was read first and allowed the path") against the round 1
failure class — a rule we cannot see becoming permission — and makes the
recorded terms position durable in code rather than a live-fetch outcome.
Three kind changes, one paragraph because they gate the same request:
(a) *What counts as a robots file.* Today a 200 whose body is not a robots
file (an HTML catch-all page) parses to zero groups and is read as "nothing
disallowed". New kind: a 200 is a robots file only if its `Content-Type` is
`text/plain` or its body carries at least one recognised directive line
(`user-agent:`, `allow:`, `disallow:`, `crawl-delay:`, `sitemap:`); anything
else is a one-line refusal like the 503 branch, never `permissive()`. Only a
404 is permissive. Pinned by: an HTML 200 body refuses before any feed
request; a `text/plain` body with an empty `Disallow:` allows.
(b) *A declared position, not an inferred one.* `AppStoreSource` gains
`fetchable: bool` and `terms: str` (the recorded position, a reason — never a
name); `scrape` refuses a non-fetchable source before any request, the way it
refuses `app_id == 0`, so a robots hiccup, a rewrite or a mis-parse cannot
silently re-enable a fetch the terms position records as disallowed. The
robots check stays as the second, independent gate. The declared source
becomes `fetchable=False, terms="robots.txt disallows /*/rss/* for every
crawler (2026-09-02)"`. Pinned by: the declared source is refused with no
request; a `fetchable=True` test source proceeds; the layout test pins that a
non-fetchable source states its terms.
(c) *Which group is ours.* Today group selection is exact token equality, so
`User-agent: friction-ledger/0.1` or `friction` falls through to `*`, and the
failure direction is permissive; A1 itself said substring. New kind: a group
applies to us when its non-empty User-agent value, lowercased, is a substring
of our full `USER_AGENT` lowercased; `*` stays the fallback. Pinned by:
`friction-ledger/0.1`, `friction` and `FRICTION-LEDGER` select the group,
`other-bot` does not, and the empty value selects nothing.

### Fix amendment — review round 3 (2026-09-02): the review cap

Rounds 2 and 3 each reported correctness findings only in the previous round's
fixes, so the cap (CLAUDE.md → Workflow rules) applies to the robots gate:
stop patching, state the invariant, re-implement once, one scoped re-review.

**A6 — the robots gate, re-implemented against its invariant** (round 3:
code-reviewer #1 #3 #4 #5 #6 #8, security-reviewer #1 #2, functionality-tester
F1–F5). Invariant 5, restated for the gate: *for every robots response with
status 200, a feed request is made only if the body reads as a robots file on
its own terms and the path is allowed by both the groups written for us and
the `*` group* (a 404 is a file with no rules; any other status refuses).
Three consequences, one mechanism:
(a) *What counts as a robots file is decided by the body alone.* The
content-type is recorded, never trusted: a 200 body is a robots file when
every non-blank, non-comment line is directive-shaped (`<key>: <value>` with a
letter-or-hyphen key; a leading byte-order mark is skipped), a non-empty body
carries a `User-agent:` line unless every line is a `Sitemap:`, and no
`Allow`/`Disallow` comes before the first `User-agent:`. An empty body and a
sitemap-only body are robots files with no rules. Anything else — an HTML or
JSON page under any content-type, a plain-text error even with colons in it
(`Error: 503`), a rule line before the first group — is a one-line refusal
like the 503 branch. The status and content-type are archived as
`robots.meta.json` beside `robots.txt`, so a capture shows why its run
proceeded.
(b) *Our group never displaces the catch-all group.* The groups written for us
are those whose non-empty User-agent value is a case-insensitive substring of
our product token (`friction-ledger`) at least three characters long, or has
the token as a substring (so `friction-ledger`, `friction-ledger/0.1`,
`FRICTION-LEDGER`, `friction` all select; `study`, `github`, `ai`, `f` and
`0.1` do not — a one- or two-letter value is noise, not a name); `*` applies
as well, always, and is never ours. A run of `User-agent:` lines ends at any
other line, so a `Sitemap:` between two of them cannot fuse two groups. A
path is allowed only if both verdicts allow it; the Crawl-delay is the longer
declared anywhere for either, within a group or across groups. An over-broad
selector can therefore only tighten.
(c) *No caller decides which rules bind us.* `Robots.parse(text)` reads the
product token from `politeness.USER_AGENT`; the parameter goes.
Pinned by: an HTML page with colons in it, a JSON error, a plain-text error
and a `Disallow:` line before any group are each refused before any feed
request under `text/plain`, `text/html` and no content-type alike; an empty
body allows; a `Sitemap:`-only body allows; `*` Disallow-all beside an empty
`study`, `ai`, `f` or `0.1` group refuses; `*` Disallow-all beside a
`friction-ledger` Allow-all group still refuses (both must allow); `*`
Crawl-delay 10 beside our group's 2 yields 10; each of the four required
forms of our token selects our group; the refusal tests assert that only
`/robots.txt` was requested; `robots.meta.json` carries status and
content-type; `urllib.robotparser` stays absent; the directive shape and the
`User-agent:` requirement are pinned by colon-bearing negatives (an HTML page
with attributes, `Error: 503`); a `Sitemap:` between two `User-agent:` lines
does not fuse their groups; `*` merged into ours would loosen our own
Disallow and is pinned absent; a BOM-led file is obeyed; the matching table
(`$`, inner `*`, longest match, Allow on a tie) stands on its own.
*Round 4 (2026-09-02), the one scoped re-review the cap prescribes, found
the parser edges above; each landed as a single fix with its pin, none
changed the invariant.*

*Not amended, disposed as fixes or accepted:* page order past page-9, the
literal 2 s pin, the whole-repo layout grep, no directory before robots
answers, one client per run (five fix commits, one finding each); `sleep`
as an injectable seam on `PoliteClient` is accepted — the constant is pinned
`>= 2.0` and the spacing test pins the literal; health details in review
bodies (security-reviewer #6) become a BACKLOG row triggered by Phase 4's
snapshot commit.

## Pinned decisions (do not re-litigate)

- **The one source is the App Store customer-reviews feed (public JSON), for
  the sources declared in `ingest/sources.py` — exactly one in Phase 2.** The
  feed is a public, keyless address per app and country
  (`https://itunes.apple.com/<country>/rss/customerreviews/id=<app>/sortBy=mostRecent/page=<n>/json`,
  pages 1–10, the feed's own cap), which is why PLAN §5 recommends it over
  Opinion Assurances (HTML, stricter terms) and why Trustpilot waits for 3b.
  Column mapping: `source` = `app-store` (the platform slug, matching
  `fixtures/anchors/`), `external_id` = the item's `id.label`, `source_url` =
  the feed page URL the item was read from, `captured_at` = stamped at fetch
  (UTC, `YYYY-MM-DDTHH:MM:SS`, the synthetic fixture's format), `review_date`
  = the date part of the item's `updated.label`, `rating` = `im:rating.label`
  as an int, `title` / `body` = `title.label` / `content.label`. The app id and
  country are values in the source declaration (a sourced data point, as the
  anchors fixture treats platform URLs), never in prose; the developer fills
  the app id at build. The source's terms position is recorded in DECISIONS
  when the scraper lands (the standing "Scrape politely" decision). Satisfies
  invariant 7. Rejected: a second source now (PLAN §5 row 3a); a per-app
  column in raw (the shape is Phase 1's; the app is recoverable from
  `source_url`, and segment attribution is Phase 3a's table).
- **The parser is a strict parse of a declared shape; the page is the unit of
  refusal.** `ingest/app_store.py::parse_page(body, source_url, captured_at)`
  declares the accepted shape: top-level `feed`; `feed.entry` absent → an
  empty page (the end of the feed); a list of items, each requiring `id.label`
  (a digit string), `title.label` and `content.label` (strings), `im:rating.label`
  (a digit string denoting 1–5), `updated.label` (an ISO 8601 timestamp with
  offset; `review_date` is its `YYYY-MM-DD`, no timezone arithmetic — the
  review's own date as the feed states it). Anything else — a missing field,
  a wrong type, `"4.5"`, an integer where a string is declared, a bad date —
  raises `FeedShapeError` naming page URL, item id and field, and the page
  loads nothing. `author`, `im:version`, `im:voteSum`, `link` are never read
  (no personal data enters the warehouse: the raw shape has no column for a
  name). Satisfies invariants 1 and 2. Rejected: skip-and-count (a chart could
  hide reviews); `.get(…, default)` coercion (CLAUDE.md "fix the class");
  accepting a single-item `entry` object — listed as a stack risk to verify,
  and added to the declared shape with a test only if the live feed does it.
- **Politeness knobs live in `ingest/politeness.py`; `ingest/fetch.py` is the
  only `httpx` import; every capture is archived byte-exact.** Constants:
  `MIN_INTERVAL_S = 2.0` per host, `USER_AGENT` naming the project and its
  repository, `TIMEOUT_S`, `MAX_PAGES = 10`, `ALLOWED_HOSTS = ("itunes.apple.com",)`.
  The fetcher reads `robots.txt` before the first feed request and checks
  every page's address against it with `ingest/robots.py` (RFC 9309: `*`, `$`,
  longest match wins, Crawl-delay honoured — fix amendment A1 replaced the
  stdlib parser, which matches prefixes only on 3.12); it sleeps to honour the
  interval;
  it makes at most one request per page with no retry (a non-200 or timeout is
  a one-line refusal, the developer re-runs); it never sets a proxy and never
  varies the User-Agent. Each run writes one capture:
  `data/cache/app-store/<source-name>/<capture-id>/page-<n>.json` (the body,
  byte-exact) beside `page-<n>.meta.json` (`source_url`, `captured_at`,
  `status`), the `robots.txt` it obeyed and, since A6, `robots.meta.json`
  (the status and content-type that answer came with; the frozen sample
  predates it and nothing reads it at rebuild, so no re-freeze); `<capture-id>` is the run's
  `captured_at`. `data/cache/` is under the gitignored `data/*` — the corpus is
  never tracked (brief §2.5, §10). Satisfies invariants 5 and 6. Rejected:
  overwriting one cache per source (loses capture history, which is what
  proves "re-scrape unchanged → no new row"); a retry/backoff loop (a polite
  client that is refused stops, PLAN §6.2).
- **`rebuild` reads captures; the `FIXTURE` closed set names the rebuild
  input: `{cache, empty, synthetic, app-store}`, default `cache`.** `cache` —
  every capture under `data/cache/app-store/`, parsed then loaded through the
  unchanged `load_reviews`; `empty` — the explicit zero-row run; `synthetic` —
  Phase 1's fixture; `app-store` — `fixtures/app-store/` read as if it were a
  capture directory (the offline proof of the parser + load path, run by CI).
  `idempotency-check` accepts the same set (default `synthetic`, so Phase 1's
  DONE line and the CI step are unchanged). `run_id` for a capture-fed rebuild
  is derived from the capture ids (`app-store:<capture-id>`), not a clock, so a
  rebuild from the same cache is byte-stable; the fixture modes keep the
  fixture name. `build.rebuild` takes a `cache_dir` so tests never touch
  `data/`. Satisfies invariants 3 and 4. Rejected: a second variable
  (`SOURCE=` on rebuild — two knobs for one closed choice); making `empty` the
  default and requiring `FIXTURE=cache` for the real run (brief §4.4: a clone
  runs `make rebuild` and gets data).
- **The metric is a query, not a mart: `pipeline/metrics.py::REVIEWS_PER_MONTH`
  over `stg_reviews`, printed by `rebuild`, pinned by a test; no
  `sql/marts/` file lands.** Reviews per month (`source`, `substr(review_date,
  1, 7)`, `count(*)`) is a pipeline-health number, not a study claim: no
  SPEC.md panel shows it, so a mart for it would be an orphan under BACKING's
  rule ("a mart no claim needs is out of scope") and `check-backing` would
  fail. It surfaces in Beat 5 through B5.2 `pipeline_row_counts`
  ("row counts at each pipeline stage"), whose mart lands with Beat 5; a
  BACKLOG row records the fold-in and deletes `metrics.py` then. The query
  text is ANSI (`substr`, `group by`), checked by the portability and clock
  lint in a test, and lives in Python because it is not a table — the
  `sql/` convention is one file per table. `check-backing` stays at 19 rows,
  0 marts, 0 orphans; BACKING and SPEC are untouched. **This narrows the
  brief's Phase 2 "one trivial mart (reviews per month)" to "one queryable
  metric" (the brief's own Done-when wording); whether PROJECT_BRIEF.md §9 is
  reworded to match is the developer's call, as in Phase 1.** Satisfies the
  central constraint. Rejected: a new BACKING row B5.3 (a new study claim
  needs a SPEC.md panel — a design change, and Beat 5 already owns the
  number); flipping B5.2 to Measured now with a partial mart (its eval-score
  columns do not exist until Phase 6).
- **The committed sample is a new frozen fixture set, `fixtures/app-store/`,
  hand-written in the feed's exact shape; `make scrape` is developer-run and
  CONFIRM-gated.** A real captured page holds real reviews and reviewer names
  — tracking one would publish raw corpus and personal data (brief §2.5,
  §10) — so the sample is fake by construction: two pages (`page-1.json`,
  `page-2.json` with their `.meta.json`) of obviously fake reviews with
  placeholder author labels, one review appearing on both pages (dedup across
  pages), a last page whose `entry` is absent (the end-of-feed shape), in the
  capture layout so `FIXTURE=app-store` reads it unchanged. Malformed variants
  are built in tests by mutating the sample in memory, never committed.
  `fixtures/` is read-only after Phase 1, so this is a deliberate freeze:
  `Freeze: fixtures/app-store/` below, `MANIFEST.sha256` in the diff, a
  DECISIONS entry (CLAUDE.md → Workflow rules). `make scrape [SOURCE=<name>]`
  prompts on a tty and otherwise requires `CONFIRM=yes` from the command line
  (`$(origin CONFIRM)`, the `reset` shape), so an agent's non-interactive call
  refuses; CI never calls it. Satisfies invariant 7 and the threat model.
  Rejected: a sample under `ingest/` or `tests/` (a fixture outside the
  MANIFEST discipline — the freeze gate exists for exactly this file); a
  scrubbed real page (still a real review, paraphrase is not a scrub).

(6 pinned decisions.)

## Scope (files)

New code:
- `ingest/__init__.py`; `ingest/sources.py` — the closed tuple of declared
  sources (`AppStoreSource(name, app_id, country, listing)`), one entry;
  `ingest/politeness.py` — the knobs, one place; `ingest/robots.py` — the
  robots.txt matcher (RFC 9309; amendment A1); `ingest/fetch.py` — the only `httpx` import:
  robots check, spaced requests, byte-exact capture with meta; `ingest/app_store.py`
  — `parse_page` (strict, `FeedShapeError`) and `read_captures(cache_dir)`
  (captures → raw-shape dicts, in capture then page then item order).
- `pipeline/metrics.py` — `REVIEWS_PER_MONTH` and `reviews_per_month(conn)`.
- `pipeline/warehouse.py` — `database_for(fixture)`: one file per rebuild input
  (amendment A2).
- `pipeline/build.py` — `FIXTURES` widened to the four inputs; `rebuild` gains
  `cache_dir` and the capture-fed branch (calls `read_captures`, then the
  unchanged `load_reviews`); `run_id` from capture ids. `pipeline/cli.py` —
  `rebuild` default `cache`, the `scrape` subcommand (SOURCE closed set,
  CONFIRM + origin), prints the metric after the counts.
- `Makefile` — `scrape` target; `unexport SOURCE`; help line; `.PHONY`.
- `.github/workflows/ci.yml` — one added step: `make rebuild FIXTURE=app-store`
  (offline, the sample through the real parser). No token change.

New fixture (frozen this phase):
- `fixtures/app-store/page-1.json`, `page-1.meta.json`, `page-2.json`,
  `page-2.meta.json`, `page-3.json`, `page-3.meta.json` (entry absent),
  `robots.txt` (a permissive sample), `MANIFEST.sha256`.

New tests:
- `tests/test_robots.py` (amendment A1); `tests/test_app_store_parser.py`,
  `tests/test_app_store_fetch.py`,
  `tests/test_ingest_rebuild.py`, `tests/test_ingest_layout.py`,
  `tests/test_offline.py`; `tests/conftest.py` gains the autouse `_no_network`
  fixture (every `socket` connect raises) and scrubs `SOURCE`; `tests/pins.py`
  gains the sample's raw / staging counts and its reviews-per-month rows;
  `tests/test_fixtures_frozen.py`, `tests/test_makefile.py`, `tests/test_cli.py`,
  `tests/test_sql_portable.py` extended.

Records (see Record updates):
- `pyproject.toml` + `uv.lock` (`httpx`), `CLAUDE.md`, `DECISIONS.md`,
  `BACKLOG.md`, `specs/phase-2-scraper.md`.

Freeze: fixtures/app-store/

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 2 entry: the App Store feed as the one source and
      its terms position (under "Scrape politely"), the strict parser and the
      page-as-unit refusal, the capture archive layout, the widened `FIXTURE`
      set with `cache` as default, the metric-as-query (with the brief-narrowing
      note), the `fixtures/app-store/` freeze; Gotchas from the first-hour
      checks; no supersede pointers
- [ ] `BACKLOG.md` — one row opened: "`reviews_per_month` is a query in
      `pipeline/metrics.py`, not a mart" — trigger: B5.2 `pipeline_row_counts`
      lands (Beat 5): fold the query into the mart, delete `metrics.py`, strike
- [ ] `CLAUDE.md` — Current status; Commands (`scrape`; `rebuild`'s `FIXTURE`
      set and default; `idempotency-check`'s set); Repo map (`ingest/` now
      exists — fetcher, parser, sources, politeness; `fixtures/app-store/`;
      `pipeline/metrics.py`); Conventions allowlist unchanged (`httpx` was
      pre-approved); BACKLOG count 6 → 12
- [ ] `pyproject.toml`, `uv.lock` — `httpx` pinned
- [ ] `specs/phase-2-scraper.md` — this spec; the "Delivered" paragraph at exit
- [ ] BACKING — none (no mart lands; every row stays Pending; 0 orphans)
- [ ] SPEC — none (no chart or beat changed)
- [ ] README — none (Phase 9; PROJECT_BRIEF.md is the front door until then)
- [ ] PROJECT_BRIEF — none unless the developer chooses to reword §9 Phase 2
      ("one trivial mart" → "one queryable metric"), as for Phase 1; then
      checked here

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

One new target touches the network: `scrape` (takes `SOURCE`, gated by
`CONFIRM`). Two existing targets take a widened variable: `rebuild` and
`idempotency-check` (`FIXTURE` gains `cache` and `app-store`). Settled shape
unchanged: one Python process validates each value against a closed set,
derives every path from the validated name (never from the value), prompts on a
tty, then acts; every recipe is one line; every user variable reaches Python
unexpanded and single-quoted via `$(call _Q,$(value VAR))` and is `unexport`ed.

**What `scrape` reaches and costs.** Host: `itunes.apple.com` only
(`ALLOWED_HOSTS`; any other host in a source declaration is refused before a
request). Requests per run per source: one `robots.txt` plus at most
`MAX_PAGES` (10) feed pages, ≥ 2 s apart — about 25 s, no cost, no key. Run
twice: the same again (a second capture directory; the pages are public and
free); the second rebuild then adds zero raw rows if nothing changed
(invariant 3). No credentials: none are needed and none are read — `ingest/`
never opens `.env` (a test greps for it); nothing is echoed. Refused
(`robots.txt` disallow, 403/429, non-200, timeout): one line naming the status
and the URL, no retry, exit 2; the fallback is Phase 3a's manual snapshot
path, never evasion (PLAN §6.2). Personal data: the cache holds the pages as
served (reviewer display names included) under gitignored `data/`; the parser
never reads the author fields, so no name reaches the warehouse or a tracked
file.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `scrape` | `SOURCE` empty → every declared source (one in Phase 2); `CONFIRM` empty → prompt on a tty, refuse non-interactively, no request made | `SOURCE` refused — validated against the declared names, never a path; the capture path is derived from the validated name | one literal arg; not a declared name → refused | `unexport`ed; validated identically in Python; `CONFIRM=yes` from the environment → `$(origin CONFIRM)` = `environment` → not confirmed → refused, no request | `CONFIRM=yes` counts only from the command line | `tests/test_makefile.py::test_scrape_requires_command_line_confirm`, `::test_scrape_source_is_a_closed_set`, `::test_pipeline_variables_reach_python_as_one_literal` (extended to `scrape`/`SOURCE`) |
| `rebuild` | `FIXTURE` → `cache` (the real run; zero captures → zero rows) | refused (closed set of four names) | one literal arg; refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_rebuild_variables_are_a_closed_set` (re-pinned to the four names and the `cache` default), `tests/test_cli.py` |
| `idempotency-check` | `FIXTURE` → `synthetic` (unchanged) | refused | refused | `unexport`ed; validated in Python | n/a | `tests/test_makefile.py::test_idempotency_check_variables_are_a_closed_set` (re-pinned to the four names) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").
The range touches Code (`ingest/**`, `pipeline/**`, `Makefile`, `tests/`),
Sensitive (`ingest/**`, `.github/workflows/ci.yml`, a target that fetches) and
Prose (`CLAUDE.md`'s Commands / Repo map / status). The union runs:
code-reviewer, functionality-tester, **security-reviewer (mandatory — a
scraper and a network target)**, study-editor (only because `CLAUDE.md` prose
changes; if the build leaves it untouched, not triggered), and
coherence-auditor at exit.

- **code-reviewer** (triggered): deterministic-first (no model import; the
  parser is rules, not guesses); the raw shape and `load_reviews` untouched;
  `content_hash` unchanged; no clock in `sql/` or in the rebuild path;
  `httpx` in one module; `FIXTURE` a closed set; the metric query portable
  and not a mart; the sample fixture frozen; scope (every file maps to the
  scraper path or a record).
- **security-reviewer** (mandatory): scrape conduct — robots.txt read first
  and obeyed, the interval, the identifying User-Agent, no proxy or rotation,
  no retry storm, `ALLOWED_HOSTS`; `make scrape` CONFIRM-gated by
  `$(origin)` and never called by CI; `data/cache/` gitignored and no real
  review or name in any tracked file (the sample is fake by construction);
  `.env` never read by `ingest/`; the CI step stays `contents: read` and
  offline.
- **functionality-tester** (triggered): the DONE command on the developer's
  cache (or the sample form if `data/cache/` is empty); Phase 1's DONE command
  still green; the strict-parse negatives (each required field removed,
  mistyped, out-of-range rating, bad timestamp) refuse the page; two captures
  of unchanged pages add no row; an edited review appends one; the no-network
  guard actually raises; hand-mutations: drop the robots check, shorten the
  interval, default a bad rating, read `author`.
- **study-editor** (triggered only by `CLAUDE.md` prose): the Commands / Repo
  map / status edits stay in the two-layer voice and add no banned word.
- **coherence-auditor** at exit: `SPEC` ↔ `BACKING` ↔ `sql/marts` still
  reconcile (0 marts, all Pending); the Repo map marks `ingest/` as existing
  and `classify/`, `models/`, `study/`, `dags/` as future; no stale "Phase 2
  will…" sentence; the brief-narrowing (metric, not mart) is recorded in
  DECISIONS, not silently applied; the BACKLOG count is 12; the "Scrape
  politely" decision now names this source's terms position.
- Stack risk — verified by the developer by hand in the first hour, in a
  browser, before any code (an agent runs no fetch): (1) `itunes.apple.com/robots.txt`
  allows the `/<country>/rss/customerreviews/…` path for a generic agent — a
  disallow is a STOP (the fallback source is a spec amendment, not a
  workaround); (2) the live feed's field names match the declared shape
  (`feed.entry[].id.label`, `title.label`, `content.label`, `im:rating.label`,
  `updated.label`) and whether a one-review page returns `entry` as an object
  rather than a list; (3) the page cap and what a page past the last returns
  (`entry` absent, or an error status); (4) `httpx`'s current release and its
  `MockTransport` API. Check official docs before any workaround; STOP and
  report; findings go to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- A second source — Google Play and Opinion Assurances (Phase 3a),
  Trustpilot (Phase 3b); `platform_snapshots` and its four marts (Phase 3a).
- Per-review segment attribution (which app, digital-first or traditional):
  Phase 3a's table, keyed on `source_url`; noted there, not a BACKLOG row.
- The weekly scheduled scrape (Phase 4) — it will call `make scrape
  CONFIRM=yes` from the workflow's command line.
- `reviews_per_month` as a mart — folded into B5.2 `pipeline_row_counts` when
  Beat 5 lands (BACKLOG row opened this phase).
- `pyyaml` — Phase 5b (`rules.yaml`); nothing here needs it.
- Classification, the cost model, the study — Phases 5–9.
