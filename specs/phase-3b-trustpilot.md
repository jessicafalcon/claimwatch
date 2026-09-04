# Phase 3b — Trustpilot (APPROVED)

Contract for the `phase-3b-trustpilot` branch. Source: PROJECT_BRIEF.md §6
(the Trustpilot figures) and §9's "remaining sources" step, plus the Phase 0a
default #2 (DECISIONS → Phase 0a: "Trustpilot terms — polite fetch; on
refusal, the manual snapshot path; no evasion") and the Phase 3a Gotcha
(DECISIONS: "the rule for 3b's Trustpilot: freeze the sample from one
permitted real page, names replaced, before the parser is written"). Depends
on Phase 3a merged (PR #5, 2026-09-03).

**Status: APPROVED 2026-09-03 — in progress.** No new dependencies. (A1: the
robots check found Trustpilot not fetchable, so no parser is built at all — the
phase is a source declaration, one hand-read row, and records. The
JSON-LD/`httpx` notes below are pre-A1 and stand only as the plan for a future
authorization.)

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED`
→ `APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR
open` when the Delivered paragraph is appended.

## Amendment A1 — the terms check found Trustpilot not fetchable (2026-09-03)

The developer's robots check (Phase 0a default #2) settled pinned decision 3's
fork. `www.trustpilot.com/robots.txt` (where the profile lives) and
`fr.trustpilot.com`'s both end with
`User-agent: *` / `Disallow: /`, and our crawler's User-Agent matches none of
the named groups, so under RFC 9309 the catch-all group governs and every path
is disallowed. There is no page we may fetch, so none we may freeze — so the
hand-read branch is taken, mirroring the App Store listing:

- Done-when **1** (the JSON-LD parser) and **4** (the frozen sample) are
  **dropped**; `ingest/trustpilot.py` and `fixtures/trustpilot/` are not built,
  and the `Freeze:` line is removed.
- Trustpilot is declared as a not-fetchable source (`platform=trustpilot`,
  `parser=None`, `fetchable=False`, `host=www.trustpilot.com`), its `terms`
  naming fr's robots rule with the date read; refused before any request,
  whatever the file says on a later day.
- Its rating and review count are read by hand off the profile page (robots
  governs a crawler, not a person reading) and loaded as one **Measured** row
  in `data/snapshots/manual_snapshots.csv`, on profile `fr-digital-first` — the
  same series as the Documented Trustpilot anchors already seeded.
- The DONE command becomes `make rebuild && make idempotency-check
  ROWS=captured` (the hand-read row loads under `captured`, as the App Store
  listing's does), not `ROWS=samples` (no sample exists).
- Done-when **6** (the no-`SPEC` gate fix) is kept only if `make review-gate`
  without `SPEC=` is red on this branch; with no fixture change it may be
  green, and is then re-deferred with its existing trigger.

The parser and sample are re-deferred (BACKLOG): their trigger is a future
written authorization from Trustpilot, as Opinion Assurances granted. The
surviving done-when are **2** (declared source), **3** (a hand-read row reuses
its anchor's profile), and **5** (no-key run green, idempotent), renumbered
1–3 below, plus the two hand-read specifics A1 adds (the source is
not-fetchable and refused before any request; one Measured row loads beside
the anchor).

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

*(A1, 2026-09-03: the robots check found no page we may fetch, so neither the
parser nor the sample is built this phase — the two paragraphs above are the
pre-A1 plan, kept as the design for a future authorization. What 3b delivers
is the hand-read path: a not-fetchable source declaration and one Measured
row beside the anchors. See the A1 section above.)*

## The central constraint

**The anchors do not move, and no Trustpilot address reaches any file but
`ingest/sources.py`.** The Documented Trustpilot points in
`fixtures/anchors/platform_snapshots_seed.csv` are frozen (Phase 1, re-frozen
3a); a measured Trustpilot point lands *beside* an anchor, on the same
profile, never replacing it and never forking it into a second series. The
Trustpilot profile address spells the brand (D1): it lives in the source
declaration and nowhere else — no prose, comment, commit, test name or
fixture repeats it. The no-key run stays green and the pipeline stays
idempotent throughout (under A1 Trustpilot adds one hand-read snapshot row,
append-only on its content hash).

## DONE command (A1)

```
make rebuild && make idempotency-check ROWS=captured
```

- `make rebuild` (default `ROWS=captured`) loads the anchors, the hand-read
  rows in `data/snapshots/manual_snapshots.csv` — now including the Trustpilot
  row — and any capture under `data/cache/`: proves the Measured Trustpilot
  row loads beside its Documented anchor on the same profile.
- `make idempotency-check ROWS=captured` rebuilds twice and diffs per-table row
  counts: proves the hand-read row is append-only on its content hash — a
  second load inserts nothing. Offline, DuckDB, no key, no fetch.

(A1 replaced the pre-amendment `ROWS=samples` DONE: no sample fixture is built,
because no Trustpilot page may be fetched or frozen.)

## Done-when

1. ~~**The Trustpilot parser reads a profile page.**~~ **DROPPED by A1** —
   Trustpilot is not fetchable, so there is no page to parse. Replaced by A1's
   hand-read row (done-when 2 below). *(re-deferred to a future authorization,
   BACKLOG.)*
2. **Trustpilot is one declared not-fetchable source (A1).** A `Source` for the
   studied insurer's Trustpilot profile is in `SOURCES`: `platform=trustpilot`,
   `parser=None`, `fetchable=False`, `host=www.trustpilot.com`, `unsolicited`
   channel, its `terms` naming fr's robots rule (`User-agent: *` → `Disallow:
   /`, read 2026-09-03) — recorded beside it and in DECISIONS → Phase 3b. It is
   refused before any request; its profile address is the only new
   brand-carrying string, added to `BRAND_TOKENS` if it is a new form.
   *Evidence: rows 2, 3.*
3. **One Measured Trustpilot row loads beside its anchor, on the same series
   (A1).** A row in `data/snapshots/manual_snapshots.csv` for the Trustpilot
   source carries its rating and review count read by hand (tagged Measured);
   the source's `profile` equals the anchor seed's Trustpilot profile for the
   studied insurer (`fr-digital-first`), pinned by a test that the declaration
   and the seed agree — so the Measured point and its Documented anchor are one
   series in `rating_trend` / `peer_ratings`, never two. The same rule binds
   any future Trustpilot peer. *Evidence: rows 3, 4.* (Closes BACKLOG "A
   fetched peer may not join its anchor's series".)
4. ~~**A frozen Trustpilot sample runs through the real parser.**~~ **DROPPED
   by A1** — no page may be fetched, so none may be frozen. No
   `fixtures/trustpilot/`, no `Freeze:` line.
5. **The no-key run stays green and the rebuild stays idempotent.** With the
   API key unset the pipeline runs end to end; a second rebuild on the same
   input leaves every table's row count unchanged. *Evidence: row 5.*
6. **`make review-gate` without `SPEC=` is green on this branch, and its two
   summary lines count the same thing (A1: kept only if red).** With no fixture
   change the no-`SPEC` gate may already be green; if it is red, the no-`SPEC`
   form reads the branch's spec (or skips the freeze check) and the FAIL line
   counts the same quantity the OK line does. If green, re-deferred with its
   existing BACKLOG trigger. *Evidence: row 6.*

(A1: done-when 1 and 4 dropped; the surviving contract is 2, 3, 5, and 6 if
red.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | DROPPED by A1 (no parser). |
| 2 | `tests/test_fetch_sources.py::test_trustpilot_source_declared_not_fetchable`, `tests/test_fetch_sources.py::test_a_non_fetchable_source_is_refused_before_any_request_whatever_robots_says`, `tests/test_ingest_layout.py::test_brand_carrying_strings_appear_only_in_the_declarations`, `tests/test_ingest_layout.py::test_every_brand_form_in_the_declarations_is_a_declared_token` |
| 3 | `tests/test_snapshots.py::test_trustpilot_hand_read_row_matches_its_anchor_seed`, `tests/test_snapshots.py::test_the_tracked_manual_file_loads_and_names_no_address` |
| 4 | DROPPED by A1 (no sample). |
| 5 | `tests/test_idempotency.py::test_second_rebuild_adds_no_rows`, `make idempotency-check ROWS=captured` prints "every row count unchanged"; the no-key run is inherently green (no API call on the pipeline path before Phase 6, whose test is the durable guard — CLAUDE.md) |
| 6 | Re-deferred by A1: `make review-gate` without `SPEC=` is already green (5/5) on this branch — no fixture change, so the freeze check does not bite; the BACKLOG trigger stands for the first branch that re-freezes a fixture |

## Invariants (REQUIRED)

(A1: the JSON-LD-parse and frozen-sample invariants are dropped with done-when
1 and 4. The surviving invariants:)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all declared sources, no request is made to a source not recorded fetchable. | `tests/test_fetch_sources.py::test_trustpilot_source_declared_not_fetchable` — `scrape` on the not-fetchable Trustpilot declaration raises `FetchRefused` before any request; the request log is empty. |
| For all snapshot rows, the row's profile equals the anchor seed's profile for that platform and profile, so one profile is one series. | `tests/test_snapshots.py::test_trustpilot_hand_read_row_matches_its_anchor_seed` — a declaration whose profile is not the seed's is caught. |
| For all hand-read rows, a second rebuild on the same input changes no row count. | `tests/test_idempotency.py` — a second load of `manual_snapshots.csv` inserts nothing (append-only on the content hash). |
| For all Trustpilot addresses in the tree, the string appears only in `ingest/sources.py`. | `tests/test_ingest_layout.py::test_brand_carrying_strings_appear_only_in_the_declarations` — a brand token in any other tracked file fails. |

## Pinned decisions (do not re-litigate)

- ~~**The parser reads JSON-LD, not layout.**~~ **SUPERSEDED by A1** — no page
  may be fetched, so no parser is written. (The JSON-LD shape stands as a note
  for a future authorization; not built now.)
- ~~**The sample is frozen from one permitted real page.**~~ **SUPERSEDED by
  A1** — no permitted page exists, so none is frozen.
- **The terms position is the developer's recorded check, and the refusal
  takes the hand-read path (settled by A1).** Following Phase 0a default #2:
  the developer's check found `www.trustpilot.com`'s and `fr.trustpilot.com`'s
  robots.txt both end with `User-agent: *` / `Disallow: /` and our User-Agent
  matches no named group (RFC 9309: the catch-all group governs), so the source
  is declared on `www.trustpilot.com` (where the profile lives), `fetchable=False`
  with `terms` naming that rule and the date, and its figures are hand-read
  into `data/snapshots/manual_snapshots.csv` (Measured), as the App Store
  listing is. The position is recorded beside the source and in DECISIONS →
  Phase 3b; the not-fetchable source is refused before any request. Satisfies
  the surviving no-request invariant.
- **A Measured Trustpilot point reuses its anchor's profile.** The
  declaration's `profile` is `fr-digital-first`, exactly the seed's Trustpilot
  profile, so `rating_trend` / `peer_ratings` keyed on `(source, profile)`
  read one series, not two. Rejected: a new profile name for the hand-read
  point. Satisfies the one-series invariant.
- **The response-rate and response-delay figures stay Documented, or wait.**
  Trustpilot's "replied to X% of negative reviews" and "typically replies in
  N" are layout text, not JSON-LD (as Opinion Assurances' were — BACKLOG),
  so the parser reads rating and count only. B1.4's response comparison stays
  as SPEC.md already states it — waiting for a second platform's *measured*
  figures — and BACKLOG "The §6 response figures are not seeded" is re-
  deferred with a Phase 9 trigger, not seeded from layout. Satisfies the
  central constraint (no invented number).
- **The no-`SPEC` gate is fixed only if red on this branch (A1).** The freeze
  check needs a `Freeze:` line, which lives in a spec; the no-`SPEC` gate has
  none to read. Under A1 this branch adds no fixture, so the gate may already
  be green — checked during implementation. If red, `scripts/review_gate.py`
  resolves the branch's spec or skips that one check and both summary lines
  count the same quantity; if green, re-deferred with its BACKLOG trigger.
  Satisfies done-when 6.

## Scope (files) — A1

A1 dropped `ingest/trustpilot.py`, `fixtures/trustpilot/`, and the parser/
sample tests. The phase touches:

- `ingest/sources.py` — the Trustpilot `Source` in `SOURCES`
  (`platform=trustpilot`, `parser=None`, `fetchable=False`,
  `host=www.trustpilot.com`, the profile `listing` address, `terms`); its brand
  form in `BRAND_TOKENS` if the profile domain is a new form.
- `data/snapshots/manual_snapshots.csv` — one hand-read Measured Trustpilot
  row (rating + count).
- `scripts/review_gate.py` — the no-`SPEC` gate fix, only if the gate is red on
  this branch (done-when 6).
- `tests/test_fetch_sources.py`, `tests/test_snapshots.py`,
  `tests/test_ingest_layout.py`, `tests/test_makefile.py`, `tests/pins.py` —
  the declaration, the hand-read row, the brand walk, the not-fetchable
  refusal, the pinned counts. `tests/test_review_gate.py` (new) only if the
  gate fix lands.
- Records: `DECISIONS.md`, `BACKLOG.md`, `CLAUDE.md`, `SPEC.md`, `README.md`,
  this spec.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 3b entry: the Trustpilot robots position as
  checked (`www.trustpilot.com` and `fr.trustpilot.com` both `User-agent: *` →
  `Disallow: /`, our UA in no named group, 2026-09-03 → not fetchable →
  hand-read), amendment A1, the
  re-defer of the §6 response figures and of the parser/sample; the D1
  brand-token note if the profile domain is a new form.
- [ ] `BACKLOG.md` — closed: "A fetched peer may not join its anchor's series"
  (the hand-read row reuses its anchor's profile, pinned). Re-deferred:
  "`make review-gate` without `SPEC=` is red" (A1: fixed only if red this
  branch, else its trigger stands), "The §6 response figures are not seeded"
  (→ Phase 9), "Round 5's fix classes were applied at their finding sites
  only" (no new parser built — trigger stands). Opened: the Trustpilot parser
  + sample, re-deferred to a future written authorization from Trustpilot.
  Open-row count updated.
- [ ] `CLAUDE.md` — Current status; Repo map (the Trustpilot hand-read source
  in `ingest/sources.py`, the `manual_snapshots.csv` note); BACKLOG count; the
  line-count row (the audit reports growth against the ~400 cap).
- [ ] BACKING — none (B1.2, B1.3, B1.4, B2.3 already name
  `https://www.trustpilot.com/` and `data/snapshots/manual_snapshots.csv`; the
  row tag stays Documented until measured points make the series).
- [ ] SPEC — none (no panel changes). Beat 1's "under the hood" already names
  Trustpilot and the hand-read path.
- [ ] README — none (no README file exists yet; the study's README lands with
  Phase 9).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new `make` target takes a variable, deletes, calls a paid API, or
touches the network, and A1 adds no network code. Trustpilot is declared
`fetchable=False` (fr's robots `User-agent: *` → `Disallow: /`), so `make
scrape` has no Trustpilot path at all: a source not recorded fetchable is
refused (exit 2) before any request, whatever its robots file says on a later
day. The one new input is a hand-read row in `manual_snapshots.csv` (numbers a
person read; no address, no name). The security-reviewer checks that the
not-fetchable declaration is refused before any request and that no brand
string reaches any file but `ingest/sources.py`.

## Review & stack risk

- **code-reviewer** (triggered — `ingest/sources.py`, `scripts/` if the gate
  fix lands, `tests/`): the declaration's not-fetchable refusal, the hand-read
  row's profile reuse, the brand walk, no clock, no pattern in SQL.
- **security-reviewer** (mandatory — `ingest/**`, and `scripts/review_gate.py`
  if it changes): the not-fetchable source refused before any request, no
  brand string outside `sources.py`, no personal data in the hand-read row
  (numbers only, no name, no address).
- **functionality-tester** (triggered): the DONE command
  (`make rebuild && make idempotency-check ROWS=captured`), the hand-read row
  loading beside its anchor, idempotency, the no-key run.
- **study-editor** (triggered — SPEC/README/CLAUDE/DECISIONS prose): no
  editorial sentence about one insurer, Trustpilot named only as a sourced
  data point, the response-figures wording honest.
- **coherence-auditor** at exit (mandatory): the stale sentences it must find
  gone — the closed BACKLOG row struck, the Trustpilot hand-read source
  reflected in the Repo map, no "Phase 3b next" left dangling; the anchors ↔
  seed ↔ declaration profile agreement.
- Stack risk: minimal under A1 — no parsing, no network code. The one care is
  that the hand-read row's `(source, profile, platform)` matches the anchor
  seed exactly so the Measured point and the Documented anchor read as one
  series; a mismatch is caught by the profile-agreement test.

## Out of scope (deferred, recorded)

- **The Trustpilot JSON-LD parser and a frozen sample (A1).** Not built —
  Trustpilot disallows our crawler on every path, so no page may be fetched or
  frozen. Re-deferred to a future written authorization from Trustpilot (as
  Opinion Assurances granted); recorded in BACKLOG.
- **Trustpilot peers as measured sources.** Peer profiles stay Documented
  anchors; if one is ever hand-read or fetched, done-when 3's profile-reuse
  rule binds it (BACKLOG).
- **Response rate and delay as measured figures.** Layout text, and Trustpilot
  is not fetched anyway; re-deferred to Phase 9's B1.4 panel (BACKLOG).
- **A weekly Trustpilot re-fetch and the edit-id question.** Phase 4's
  workflow, with the Opinion Assurances re-fetch/edit-id rows (BACKLOG).
- **The App Store listing's JSON-LD block.** Unverified; its trigger is a
  future permission to fetch that listing, not this phase (BACKLOG).
