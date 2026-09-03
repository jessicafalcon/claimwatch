# Phase 3b — Trustpilot (PROPOSED)

Contract for the `phase-3b-trustpilot` branch. Source: PROJECT_BRIEF.md §6
(the Trustpilot figures) and §9's "remaining sources" step, plus the Phase 0a
default #2 (DECISIONS → Phase 0a: "Trustpilot terms — polite fetch; on
refusal, the manual snapshot path; no evasion") and the Phase 3a Gotcha
(DECISIONS: "the rule for 3b's Trustpilot: freeze the sample from one
permitted real page, names replaced, before the parser is written"). Depends
on Phase 3a merged (PR #5, 2026-09-03).

**Status: PROPOSED — do not start until approved.** No new dependencies:
`httpx` (fetch) and `pyyaml` are the Phase 2 allowlist; the parser uses the
stdlib `json` decoder already in `ingest/parsed.py`. Trustpilot marks its
data as JSON-LD, so no HTML-microdata code is added beyond what exists.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED`
→ `APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR
open` when the Delivered paragraph is appended.

## Why

Trustpilot is the segment's most-cited independent review platform: it is the
source of the peer anchors and of the studied insurer's Documented rating
series already seeded in `fixtures/anchors/platform_snapshots_seed.csv`
(Documented, from PROJECT_BRIEF.md §6). Today those points are Documented
placements; nothing we measure sits beside them. Phase 3a built the machinery
for a second review-profile platform — every source is one declaration, a
parser reads its pages, `ROWS` names what a rebuild loads — so adding
Trustpilot is a new source and a new parser, not new machinery. This is a
phase, not a fix PR: it adds a parser (a foreign-input guard), a source
declaration with a recorded terms position, and a frozen sample — the same
three deliverables Opinion Assurances took in 3a.

Trustpilot's pages carry their aggregate and their reviews as JSON-LD, a
different shape from Opinion Assurances' inline microdata; the 3a Gotcha (a
guessed nesting is a shape the tests cannot see) is why the sample is frozen
from one permitted real page, names replaced, **before** the parser is
written.

## The central constraint

**The anchors do not move, and no Trustpilot address reaches any file but
`ingest/sources.py`.** The Documented Trustpilot points in
`fixtures/anchors/platform_snapshots_seed.csv` are frozen (Phase 1, re-frozen
3a); a measured Trustpilot point lands *beside* an anchor, on the same
profile, never replacing it and never forking it into a second series. The
Trustpilot profile address spells the brand (D1): it lives in the source
declaration and nowhere else — no prose, comment, commit, test name or
fixture repeats it. The no-key run stays green and the pipeline stays
idempotent throughout (Trustpilot adds review rows and one snapshot row, both
append-only on a content hash).

## DONE command

```
make rebuild ROWS=samples && make idempotency-check ROWS=samples
```

- `make rebuild ROWS=samples` runs every frozen sample — now including
  `fixtures/trustpilot/` — through its real parser and loads it into the
  samples database: proves the Trustpilot parser turns its frozen page into
  review rows and one aggregate snapshot row (the count CI reproduces).
- `make idempotency-check ROWS=samples` rebuilds twice and diffs per-table row
  counts: proves the Trustpilot rows are append-only on their content hash — a
  second load of the same sample inserts nothing. Offline, DuckDB, no key, no
  fetch, exactly what CI runs.

## Done-when

1. **The Trustpilot parser reads a profile page.** `ingest/trustpilot.py`
   turns one Trustpilot profile page (JSON-LD) into review rows — each rating
   a member of `REVIEW_RATINGS` (Trustpilot rates in whole stars 1–5, which
   are members) — and exactly one aggregate snapshot row (rating 0–5, review
   count); a page outside the declared JSON-LD shape raises `PageShapeError`
   naming page, item and field, and the whole page loads nothing. *Evidence:
   rows 1, 5.*
2. **Trustpilot is one declared source with its recorded terms position.**
   `trustpilot` is in `PARSERS`; a `Source` for the studied insurer's
   Trustpilot profile is in `SOURCES`, `unsolicited` channel, its `fetchable`
   and `terms` set from the developer's checked robots.txt + terms position
   (recorded beside it and in DECISIONS → Phase 3b). A source not recorded
   fetchable is refused before any request; its profile address is the only
   new brand-carrying string, added to `BRAND_TOKENS` if it is a new form.
   *Evidence: rows 2, 3.*
3. **A fetched Trustpilot row joins its anchor's series, not a new one.** The
   Trustpilot source's `profile` equals the anchor seed's Trustpilot profile
   for the studied insurer (`fr-digital-first`), pinned by a test that the
   declaration and the seed agree — so a measured point and its Documented
   anchor are one series in `rating_trend` / `peer_ratings`. The same rule
   binds any future Trustpilot peer. *Evidence: row 4.* (Closes BACKLOG "A
   fetched peer may not join its anchor's series".)
4. **A frozen Trustpilot sample runs through the real parser under
   `ROWS=samples`.** `fixtures/trustpilot/` holds a real profile page with the
   insurer's name replaced (a fake, nameless profile), its meta files and a
   `MANIFEST.sha256`; it is read-only after this phase and its rows land in
   the samples database, joining `raw_source_pages` like any capture's.
   *Evidence: rows 4, 5.*
5. **The no-key run stays green and the rebuild stays idempotent.** With the
   API key unset the pipeline runs end to end; a second rebuild on the same
   input leaves every table's row count unchanged. *Evidence: row 5.*
6. **`make review-gate` without `SPEC=` is green on a phase branch, and its
   two summary lines count the same thing.** The no-`SPEC` form reads the
   branch's spec (or skips the freeze check) so a new or re-frozen fixture
   does not fail it, and the FAIL line counts the same quantity the OK line
   does. *Evidence: row 6.* (Closes BACKLOG "`make review-gate` without
   `SPEC=` is red on a phase branch".)

(6 items — at the cap.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_trustpilot_parser.py::test_parses_reviews_and_aggregate`, `::test_off_shape_page_refuses_naming_field`, `::test_review_rating_outside_the_half_steps_refuses` |
| 2 | `tests/test_fetch_sources.py::test_trustpilot_source_declared`, `tests/test_makefile.py::test_scrape_refuses_a_source_not_fetchable` (if not fetchable), `tests/test_ingest_layout.py::test_brand_carrying_strings_appear_only_in_the_declarations` |
| 3 | `tests/test_snapshots.py::test_fetched_trustpilot_profile_matches_its_anchor_seed` |
| 4 | `tests/test_fixtures_frozen.py::test_trustpilot_sample_manifest`, `make rebuild ROWS=samples` prints the Trustpilot review + snapshot counts |
| 5 | `tests/test_rebuild.py::test_no_key_run_is_green` (existing, extended), `make idempotency-check ROWS=samples` prints "row counts unchanged" |
| 6 | `tests/test_review_gate.py::test_no_spec_gate_green_with_a_frozen_fixture` and `::test_both_summary_lines_count_the_same`; `make review-gate` prints an OK line on this branch |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all Trustpilot profile pages the parser reads, every review row's rating is a member of `REVIEW_RATINGS` and the aggregate rating is in [0, 5]; a page outside the declared JSON-LD shape loads nothing from it. | `tests/test_trustpilot_parser.py::test_off_shape_page_refuses_naming_field` — a page with a rating of `6`, a missing aggregate, or malformed JSON-LD loads zero rows and names the field. |
| For all declared sources, no request is made to a source not recorded fetchable; a fetchable source names a parser. | `tests/test_makefile.py::test_scrape_refuses_a_source_not_fetchable` — `make scrape SOURCE=<trustpilot>` on a not-fetchable declaration exits 2 before any fetch. |
| For all fetched snapshot rows, the row's profile equals the anchor seed's profile for that platform and profile, so one profile is one series. | `tests/test_snapshots.py::test_fetched_trustpilot_profile_matches_its_anchor_seed` — a declaration whose profile is not the seed's is caught. |
| For all frozen samples, the bytes match `MANIFEST.sha256` and a rebuild reads them read-only; a second rebuild changes no row count. | `tests/test_fixtures_frozen.py::test_trustpilot_sample_manifest` (a mutated byte fails) and `tests/test_idempotency.py` (a second load inserts nothing). |
| For all Trustpilot addresses in the tree, the string appears only in `ingest/sources.py`. | `tests/test_ingest_layout.py::test_brand_carrying_strings_appear_only_in_the_declarations` — a brand token in any other tracked file fails. |

## Pinned decisions (do not re-litigate)

- **The parser reads JSON-LD, not layout.** Trustpilot marks its aggregate
  (`aggregateRating`: `ratingValue`, `reviewCount`) and each review
  (`reviewRating.ratingValue`, an integer 1–5) as JSON-LD in a
  `<script type="application/ld+json">` block, decoded by
  `parsed.decode_json`; everything else on the page is layout and is never
  read. Rejected: parsing the visible HTML — brittle and a second shape.
  Satisfies invariant 1.
- **The sample is frozen from one permitted real page, names replaced,
  before the parser.** A hand-guessed JSON-LD shape is a shape the tests
  cannot see (the 3a Gotcha). The developer fetches one profile page once
  under Trustpilot's own terms, replaces the insurer's name with a nameless
  placeholder, and freezes it; the parser is written against it. Satisfies
  invariant 4.
- **The terms position is the developer's recorded check, and a refusal takes
  the hand-read path.** Following Phase 0a default #2: the developer checks
  Trustpilot's robots.txt and terms; if they permit an identifying, rate-
  limited fetch the source is `fetchable=True` with a `parser`; if they
  forbid it the source is `fetchable=False` with `terms` and its figures are
  hand-read into `data/snapshots/manual_snapshots.csv` (Measured), as the App
  Store listing is. Either way the position is recorded beside the source and
  in DECISIONS → Phase 3b, and a not-fetchable source is refused before any
  request. Satisfies invariant 2.
- **A measured Trustpilot point reuses its anchor's profile.** The
  declaration's `profile` is `fr-digital-first`, exactly the seed's Trustpilot
  profile, so `rating_trend` / `peer_ratings` keyed on `(source, profile)`
  read one series, not two. Rejected: a new profile name for the fetched
  point. Satisfies invariant 3.
- **The response-rate and response-delay figures stay Documented, or wait.**
  Trustpilot's "replied to X% of negative reviews" and "typically replies in
  N" are layout text, not JSON-LD (as Opinion Assurances' were — BACKLOG),
  so the parser reads rating and count only. B1.4's response comparison stays
  as SPEC.md already states it — waiting for a second platform's *measured*
  figures — and BACKLOG "The §6 response figures are not seeded" is re-
  deferred with a Phase 9 trigger, not seeded from layout. Satisfies the
  central constraint (no invented number).
- **The no-`SPEC` gate reads the branch's spec or skips the freeze check.**
  The freeze check needs a `Freeze:` line, which lives in a spec; the no-
  `SPEC` gate has none to read, so it must resolve the branch's spec or skip
  that one check, and both summary lines must count the same quantity. This
  is a `scripts/review_gate.py` change, in scope because 3b's `Freeze:` line
  is what exposes it. Satisfies done-when 6.

## Scope (files)

- `ingest/trustpilot.py` — the new parser (JSON-LD → reviews + one snapshot),
  exposing `parse()`, `EXTENSION`, `SAMPLE_PLATFORM`, `SAMPLE_HOST`,
  `SAMPLE_DIR`, `SAMPLE_PAGES` (the contract in `ingest/parsed.py` and the
  `PARSERS`/`sample_source` closed set in `ingest/sources.py`).
- `ingest/sources.py` — `trustpilot` added to `PARSERS`; the Trustpilot
  `Source` in `SOURCES`; its brand form in `BRAND_TOKENS` if new.
- `ingest/captures.py` — `parser_module` gains `trustpilot` in its closed-set
  lookup (if it enumerates modules).
- `fixtures/trustpilot/` — the frozen sample: real page (names replaced), meta
  files, `MANIFEST.sha256`.
- `scripts/review_gate.py` — the no-`SPEC` freeze-check fix (done-when 6).
- `data/snapshots/manual_snapshots.csv` — only if the terms check makes
  Trustpilot not fetchable (the hand-read path).
- `tests/test_trustpilot_parser.py` (new), `tests/test_fetch_sources.py`,
  `tests/test_snapshots.py`, `tests/test_fixtures_frozen.py`,
  `tests/test_ingest_layout.py`, `tests/test_makefile.py`,
  `tests/test_review_gate.py` (new), `tests/pins.py` — the pinned counts.
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `SPEC.md`, `README.md`,
  this spec.

Freeze: fixtures/trustpilot/

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 3b entry: the Trustpilot terms/robots position as
  checked (fetchable or hand-read), the JSON-LD shape from the structure dump,
  the re-defer of the §6 response figures; the D1 brand-token note if a new
  form.
- [ ] `BACKLOG.md` — closed: "A fetched peer may not join its anchor's series",
  "`make review-gate` without `SPEC=` is red". Re-deferred with new triggers:
  "The §6 response figures are not seeded" (→ Phase 9), "Round 5's fix classes
  were applied at their finding sites only" (apply each class in the new
  parser). Opened if any: a Trustpilot re-fetch / edit-id row like Opinion
  Assurances'. Open-row count updated.
- [ ] `CLAUDE.md` — Current status; Repo map (`ingest/trustpilot.py`, the
  Trustpilot source, `fixtures/trustpilot/`); `PARSERS`; BACKLOG count; the
  line-count row (the audit reports growth against the ~400 cap).
- [ ] `BACKING.md` — none (B1.2, B1.3, B1.4, B2.3 already name
  `https://www.trustpilot.com/`; the row tag stays Documented until measured
  points make the series).
- [ ] `SPEC.md` — none unless the terms check changes a panel (a design
  change: STOP first). Beat 1's "under the hood" already names Trustpilot.
- [ ] `README.md` — the Trustpilot source in the sources list; `make scrape`
  gains a green Trustpilot path only if fetchable.
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new `make` target takes a variable, deletes, calls a paid API, or
touches the network. `make scrape` (network, Phase 2/3a) gains one fetchable
source but no new variable or code path: it fetches Trustpilot's declared page
addresses under the same gate (`make confirm scrape`, Phase 3a A4/A9),
robots.txt first, ≥ 2 s apart per host, identifying User-Agent, no proxy, no
retry, ≤ 60 pages — and is developer-run, never by an agent. A source not
recorded fetchable is refused (exit 2) before any request, whatever its robots
file says on a later day. If the developer's terms check makes Trustpilot not
fetchable, no fetch path exists at all and the figures are hand-read. The
security-reviewer checks the fetch conduct of the new source and the JSON-LD
parser's refusal on a hostile page.

## Review & stack risk

- **code-reviewer** (triggered — `ingest/**`, `scripts/`, `tests/`): the
  parser is a closed-shape JSON-LD parse (round 5's fix class at every site —
  `\A…\Z`, a strict decode, no `.get(default)` that invents a value); the
  measured point reuses its anchor's profile; no clock, no pattern in SQL.
- **security-reviewer** (mandatory — `ingest/**` incl. a network source, and
  `scripts/review_gate.py`): scrape conduct (rate limit, robots, no evasion),
  no brand string outside `sources.py`, no personal data in the frozen sample
  (names replaced), the parser refuses a hostile page without a traceback.
- **functionality-tester** (triggered): the DONE command, the parser against
  `fixtures/trustpilot/`, idempotency, the no-key run, a hand-mutation of the
  frozen sample.
- **study-editor** (triggered — SPEC/README/CLAUDE/DECISIONS prose): no
  editorial sentence about one insurer, Trustpilot named only as a sourced
  data point, the response-figures wording honest.
- **coherence-auditor** at exit (mandatory): the stale sentences it must find
  gone — the two closed BACKLOG rows struck, the Trustpilot source reflected
  in the Repo map, no "Phase 3b next" left dangling; the anchors ↔ seed ↔
  declaration profile agreement.
- Stack risk: verify Trustpilot's real JSON-LD shape from the frozen page in
  the first hour (the `@type`, the `aggregateRating` keys, whether reviews are
  one array or paginated as separate JSON-LD blocks); a guessed key is the 3a
  Gotcha again. STOP and report before any workaround; findings → DECISIONS →
  Gotchas.

## Out of scope (deferred, recorded)

- **Trustpilot peers as fetched sources.** 3b fetches the studied insurer's
  profile only; peer profiles stay Documented anchors. If a peer is fetched
  later, done-when 3's profile-reuse rule binds it (BACKLOG).
- **Response rate and delay as measured figures.** Layout text, not JSON-LD;
  re-deferred to Phase 9's B1.4 panel (BACKLOG).
- **A weekly Trustpilot re-fetch and the edit-id question.** Phase 4's
  workflow, with the Opinion Assurances re-fetch/edit-id rows (BACKLOG).
- **The App Store listing's JSON-LD block.** Unverified; its trigger is a
  future permission to fetch that listing, not this phase (BACKLOG).
