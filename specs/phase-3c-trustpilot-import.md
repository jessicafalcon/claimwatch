# Phase 3c — Trustpilot, authorized import (APPROVED)

Contract for the `phase-3c-trustpilot-import` branch. Source: PROJECT_BRIEF.md
§6 (the Trustpilot figures) and the Phase 3b amendment A1's deferral — "the
parser and sample are re-deferred (BACKLOG): their trigger is a future written
authorization from Trustpilot, as Opinion Assurances granted." That trigger is
now met: the developer holds written authorization (2026-09-04) and the
studied insurer's Trustpilot reviews are in hand as an authorized export.
Depends on Phase 3b merged.

**Status: APPROVED 2026-09-04 — DELIVERED 2026-09-04, PR pending.** No new
dependencies (stdlib `csv`; the export is a CSV, read like every other captured
input).

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

> **Phase number is the developer's call** (docs/PLAN.md owns the phase cut).
> "3c" is a proposal — this reverses A1, so it is a new phase, not a fix PR.

## Amendment A1 — reviews are a second source, not a parser on the snapshot source (2026-09-04)

`read_manual_snapshots` (pipeline/build.py) refuses a source that has a parser
("a parsed source's figures come from its capture"). The
`fr-digital-first-trustpilot` source owns the hand-read 3.9/1,072 row in
`data/snapshots/manual_snapshots.csv`, so giving it a parser (done-when 1 as
written) would make `make rebuild` refuse that row and erase the rating point —
the exact thing the central constraint forbids. Instead, mirror the App Store
feed/listing split:

- `fr-digital-first-trustpilot` is **untouched** — `parser=None`,
  `fetchable=False`, its hand-read 3.9/1,072 Measured point kept.
- A **new** source `fr-digital-first-trustpilot-reviews` reads the corpus:
  `platform="trustpilot"`, `parser="trustpilot"`, `fetchable=False`,
  `host="ca.trustpilot.com"` (the export's start_url host, not `www`), the one
  authorized profile page (its address lives only in `ingest/sources.py`, D1),
  its authorized-export capture under `data/cache/trustpilot/`.

This strengthens the central constraint: the rating series is unchanged **by
construction**, because its source never changes. Done-when **1** and Scope
update accordingly; done-when **4**'s invariant is satisfied structurally.
`"ca"` joins the brand-token allowlist in `tests/test_ingest_layout.py`. The
capture is authored from the authorized export (one `page-1.csv` + `meta.json`,
`status:200` for the authorized fetch that produced it) — a DECISIONS Gotcha
records that it is not a live `fetch.py` capture.

## Why

A1 declared Trustpilot not fetchable — its `robots.txt` ends `User-agent: *` /
`Disallow: /` for our crawler, and its terms forbid automated collection — and
read one aggregate rating point by hand (3.9 on 1,072 reviews, Measured). It
re-deferred the reviews themselves to "a future written authorization." That
authorization now exists (recorded minimally, exactly as Opinion Assurances is:
one `terms=` line, evidence held by the developer, not committed). The studied
insurer's 1,050 Trustpilot reviews are in hand as an authorized third-party
export. This phase ingests them as a Measured **review corpus** — the raw
material Beat 2's theme shares (B2.2, B2.5) will classify in Phase 5 — closing
BACKLOG #41. It is not a fix PR: it reverses a pinned decision (A1) and adds a
parser and a write path.

## The central constraint

**The Trustpilot rating series does not move.** The hand-read TrustScore point
(3.9 on 1,072, `data/snapshots/manual_snapshots.csv`) stays exactly as it is —
Trustpilot's TrustScore is a weighted score, not the mean of the review rows
(~4.0), and the displayed count (1,072) is not the export's row count (1,050).
The corpus feeds the theme marts only; recomputing the rating from it would
fabricate a number. `rating_trend` / `peer_ratings` / `channel_gap` read the
same figures after this phase as before it.

## DONE command

```
make rebuild && make idempotency-check ROWS=captured
```

- `make rebuild ROWS=captured` — the authorized export loads as a capture and
  the corpus reaches `stg_reviews` (1,050 rows), the rating series unchanged.
- `make idempotency-check ROWS=captured` — a second rebuild diffs zero rows;
  re-importing the same export inserts nothing (content_hash idempotency).
- CI additionally runs `ROWS=samples`, proving the parser on the frozen
  synthetic sample.

## Done-when

1. **The export parses into `raw_reviews` as an authorized offline import.** A
   new source `fr-digital-first-trustpilot-reviews` (`parser="trustpilot"`,
   `fetchable=False` — our crawler never runs against it) reads its authorized
   export as a capture under `data/cache/trustpilot/`; the existing
   `fr-digital-first-trustpilot` snapshot source is untouched (A1). `make
   rebuild ROWS=captured` loads the 1,050 review rows. *Evidence: row 1.*
2. **The parser accepts only the export's declared shape and refuses the rest.**
   A rating comes only from a `stars-N.svg` URL with N a member of
   `REVIEW_RATINGS`; an unknown rating URL or an unparseable date raises
   `PageShapeError`, never a silent default (§8, fix-the-class). *Evidence:
   row 2.*
3. **No personal data crosses into any table.** The parser keeps only
   headline→title, reviewbody→body, data3→review_date, rating→rating,
   web_scraper_order→external_id; `name`, `name2`, avatar `image`,
   `addresscountry` and the relative time are dropped and appear in no raw or
   staging column. *Evidence: row 3.*
4. **The rating series is unchanged.** `platform_snapshots`, `rating_trend` and
   `peer_ratings` show the same hand-read 3.9 / 1,072 point after the corpus
   loads as before. *Evidence: row 4.*
5. **The frozen synthetic sample runs through the real parser.** A hand-written,
   nameless, brand-free capture in the export's exact column shape lives in
   `fixtures/trustpilot/` with its `MANIFEST.sha256`; `make idempotency-check
   ROWS=samples` parses it and is row-count-stable. *Evidence: row 5.*
6. **Re-import is idempotent.** `make idempotency-check ROWS=captured` diffs
   zero; a re-import of the unchanged export inserts nothing (content_hash over
   rating, review_date, title, body). *Evidence: row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `make rebuild ROWS=captured` loads the 1,050 Trustpilot rows into `stg_reviews` (developer-run: the real export is gitignored, so the tracked proofs are the declaration test and the frozen sample below); `tests/test_fetch_sources.py::test_trustpilot_reviews_is_authorized_offline_import` |
| 2 | `tests/test_ingest_trustpilot.py::test_maps_rating_date_title_body_and_only_those`, `::test_a_rating_that_is_not_a_known_star_url_refuses`, `::test_a_date_that_is_not_month_day_year_refuses`, `::test_a_header_that_is_not_the_export_refuses` |
| 3 | `tests/test_ingest_trustpilot.py::test_dropped_columns_reach_no_field`; `tests/test_marts.py::test_review_tables_have_no_personal_columns` |
| 4 | `tests/test_marts.py::test_trustpilot_rating_point_unchanged_by_corpus` |
| 5 | `make idempotency-check ROWS=samples` prints "OK"; `tests/test_fixtures_frozen.py::test_manifests_match` checks `fixtures/trustpilot/` against its MANIFEST |
| 6 | `make idempotency-check ROWS=captured` prints "OK"; `tests/test_marts.py::test_reimport_inserts_nothing` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all imported review rows, the rating is a member of `REVIEW_RATINGS`, or the parse refuses. | `tests/test_ingest_trustpilot.py::test_a_rating_that_is_not_a_known_star_url_refuses` — a `stars-7.svg` (and `stars-0`, non-svg, non-host, digit, empty) row raises `PageShapeError`, loads nothing. |
| For all imported reviews, no reviewer name, avatar or country appears in any raw or staging column. | `tests/test_marts.py::test_review_tables_have_no_personal_columns` — the column set of `raw_reviews`/`stg_reviews` excludes them. |
| For all rebuilds, the Trustpilot rating series equals the hand-read snapshot, whatever the corpus holds. | `tests/test_marts.py::test_trustpilot_rating_point_unchanged_by_corpus` — corpus mean ≠ 3.9, and the snapshot point wins. |
| For all re-imports of an unchanged export, per-table row counts are unchanged. | `tests/test_marts.py::test_reimport_inserts_nothing`. |
| For all `fetchable=False` sources, `make scrape` never fetches them, parser or not. | `tests/test_fetch_sources.py::test_trustpilot_reviews_is_authorized_offline_import` — the parsered, not-fetchable reviews source: `scrape` refuses before any request. |

## Pinned decisions (do not re-litigate)

- **Authorized offline import, not a live fetch.** The data is an authorized
  export already in hand; re-fetching with our crawler is redundant and we
  represent it honestly — `fetchable=False` (the crawler never runs; A1's
  robots ruling stands for the crawler), `parser="trustpilot"` set, the capture
  authored from the export. Rejected: `fetchable=True` + a live re-scrape (a
  needless hit on a `Disallow: /` host). Satisfies inv "scrape never fetches
  an unfetchable source."
- **The TrustScore stays hand-read; the corpus is themes only.** 3.9 is
  Trustpilot's weighted score, not the mean of the rows (~4.0), and 1,072 ≠
  1,050; recomputing would fabricate. Rejected: derive the rating point from
  the corpus. Satisfies "rating series unchanged."
- **A strict, closed parse (§8).** The column set and the star-URL spellings
  are a declaration; an unrecognized rating URL or date refuses, never
  defaults. Satisfies "rating member or refuse."
- **The synthetic sample is shaped, not real.** A frozen slice of real reviews
  would commit personal data and the brand; the sample is a hand-written,
  nameless capture in the export's column shape, like
  `fixtures/opinion-assurances/`. Satisfies §2.5 / D1.
- **Minimal authorization record.** One `terms=` line ("written authorization
  from the site, granted 2026-09-04 …") plus a DECISIONS entry, mirroring
  Opinion Assurances; the evidence is held by the developer, never committed.

## Scope (files)

- `ingest/sources.py` — ADD `fr-digital-first-trustpilot-reviews`
  (`parser="trustpilot"`, `fetchable=False`, `host="ca.trustpilot.com"`, the
  authorized profile page, the authorization `terms=` line); the existing
  `fr-digital-first-trustpilot` snapshot source is left as-is (A1).
- `ingest/trustpilot.py` — new parser: the authorized export CSV → review rows
  + refusal; the `_CONTENT` fingerprint columns only.
- `ingest/captures.py` — register `trustpilot` in `PARSERS`.
- `pipeline/build.py` — confirm a `fetchable=False` source WITH a parser reads
  its captures (the new offline-import mode); the smallest change that admits
  it, or none if already admitted.
- `fixtures/trustpilot/` — the synthetic sample capture + `MANIFEST.sha256`.
- `tests/test_ingest_trustpilot.py` (new); `tests/test_fetch_sources.py`,
  `tests/test_marts.py`, `tests/test_ingest_layout.py` (extend).
- `data/cache/trustpilot/…` — the capture authored from the export (gitignored;
  never committed).

Freeze: fixtures/trustpilot/

(A new set, not a re-freeze; the covering line lets `make review-gate` admit
its first `MANIFEST.sha256`. The DECISIONS entry records the new set.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 3c entry; supersede A1's "not fetchable / no
  parser" with the authorization that lifts it (a pointer, A1 not rewritten).
- [ ] `BACKLOG.md` — #41 struck ("DONE Phase 3c"); BACKLOG count updated.
- [ ] `CLAUDE.md` — Current status; Repo map (Trustpilot now has a parser and a
  fixture set); BACKLOG count.
- [ ] BACKING — none: the review corpus feeds B2.2 / B2.5, but they stay
  **Pending** until Phase 5 classifies — no displayed number, so no tag or
  source change this phase.
- [ ] SPEC — none: no chart or beat changes (a chart change would be a design
  change — STOP first).
- [ ] README — none: no command or beat description changed (the DONE command
  is unchanged from Phase 3b).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new `make` target takes a variable, deletes, calls a paid API, or
touches the network. The parser reads a fixed capture path under `data/cache/`,
exactly as the existing parsers do; `make scrape` is unchanged and still skips
`fetchable=False` sources. `ingest/**` is a **sensitive** surface, so
security-reviewer is mandatory: it must confirm the authorization is recorded
(not evasion), no personal data reaches a tracked file, and the sample fixture
carries no real name or brand address.

## Review & stack risk

- **code-reviewer** (triggered — `ingest/**`, `pipeline/build.py`, `tests/`):
  closed-set parse, provenance columns, no clock, deterministic content_hash,
  the dropped-column discipline, scope (the corpus feeds a Beat 2 row).
- **security-reviewer** (mandatory — `ingest/**` touched, and the
  authorization/robots question): no evasion (the crawler still never runs), the
  authorization line present and truthful, no personal data or brand address in
  a tracked file, no secrets.
- **functionality-tester** (after code-reviewer): the DONE command,
  `ROWS=samples`, idempotency, the refusal tests (`stars-7.svg`, bad date), the
  rating-unchanged test. (No model call; the no-key run is unaffected.)
- **study-editor** (triggered only if `BACKING.md`/`README.md` prose changed):
  the corpus note carries no editorial sentence about the insurer.
- **coherence-auditor** at exit (mandatory): A1's "not fetchable / `parser=None`"
  sentences in CLAUDE.md, DECISIONS and the repo map are superseded, not left
  stale; BACKLOG #41 struck; the rating point still reads 3.9 everywhere.
- **Stack risk (verify in the first hour; STOP before any workaround):**
  (a) the `fetchable=False` + parser-set mode may trip a test or a build path
  that assumes "no parser ⟺ hand-read" or "unfetchable ⟹ `parser is None`" —
  find every such assumption before changing it; (b) the export's date spelling
  (`"September 3, 2026"`) must parse deterministically without a locale
  dependency (`%B %d, %Y`, refuse otherwise) — no clock, no `now()`. Findings
  → DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- **Classifying the corpus** — the reviews land Measured; theme shares (B2.2,
  B2.5) come in Phase 5 (BACKING rows stay Pending until then).
- **The §6 response-rate / delay figures** — layout text, not in the export;
  still B1.4's open BACKLOG row, waiting on a second platform's measured
  figures.
- **A live Trustpilot crawler** — A1's robots ruling stands for our crawler;
  this import is offline. A future authorized live fetch is a separate phase
  (BACKLOG).
- **Refreshing the export on a schedule** — a one-time import now; a periodic
  refresh is later work if wanted (BACKLOG).

## Delivered (2026-09-04)

The studied insurer's 1,050 Trustpilot reviews are ingested as a Measured
corpus, the raw material Phase 5 will classify for Beat 2's theme shares (B2.2,
B2.5, still Pending). Written authorization lifted Phase 3b's A1 for an OFFLINE
import only: the robots ban still governs our crawler, so a SECOND source
`fr-digital-first-trustpilot-reviews` (`parser=trustpilot`, `fetchable=False`,
host `ca.trustpilot.com`) reads the authorized export — saved as a capture and
read from disk, never fetched — while the hand-read snapshot source is left
untouched, so the 3.9/1,072 rating point is unchanged by construction (A1, the
App Store feed/listing split). The `trustpilot` parser reads the rating from
the star-image URL and the date from a locale-independent `Month D, YYYY`,
drops every personal and layout column, and refuses anything outside the
export's declared shape (§8). A synthetic, nameless sample in
`fixtures/trustpilot/` runs the real parser under `ROWS=samples`. BACKLOG #41
closed; a residual row (a live fetch and a scheduled refresh) opened. DONE
(`make rebuild && make idempotency-check ROWS=captured`) passes: the 1,050 rows
reach `stg_reviews`, idempotent, the rating series unchanged; 588 tests pass;
`review-gate` 7/7.

Review round: security-reviewer, study-editor, functionality-tester — no
findings / WORKS. code-reviewer — one should-fix (the no-clock byte-stable
guard now patches the `trustpilot` parser, CR1) and one suggestion (`_rating`
gains `-> Decimal`, CR2). coherence-auditor — no blocker; four low items fixed
(the in-place supersede tag on Phase 3b's A1, the re-deferred line-cap row, the
test count, the spec title). Decisions the spec did not cover: content-derived
`external_id` (the export has no stable public review id, so a re-import is one
fingerprint; mirrors `opinion_assurances`); the offline capture is authored
from the export with `status:200` standing for the authorized fetch (a
DECISIONS Gotcha), not a live `fetch.py` capture.
