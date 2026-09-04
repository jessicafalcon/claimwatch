# Phase 7a — Findings marts: theme share (PROPOSED)

Contract for the `phase-7a-findings-marts` branch. Source: PROJECT_BRIEF.md §9
Phase 7 ("Findings marts + open data"), cut to its deterministic first half —
the classifier-fed theme-share marts, no network. Depends on Phase 6b (the
held-out gate + `classifier_quality`) merged.

**Status: APPROVED — in progress. Amendment A1 (2026-09-04): segment is a
load-time column on the review, not a query-time join.** No new dependencies
(the allowlist is in CLAUDE.md → Conventions; this phase is DuckDB + stdlib SQL).

## Amendment A1 — segment stamped at load, not joined at query time

The pinned "segment by `source` slug" decision (below) does not survive the
`samples` input: `raw_source_pages.source` is the *platform* slug, and a review's
`source` is also the platform, but `samples` declares two sources per platform —
the real one (`digital-first`) and the per-parser sample one (`segment=sample`,
same `SAMPLE_PLATFORM`) — so a platform maps to two segments and no query-time
join on `source` can tell a sample review from a real one. A review's segment is
in fact a fact of the source it was loaded from, known in Python at load time.
So: `raw_reviews` gains a `segment` column, stamped from the loading source's
`segment` (the platform→segment map for the synthetic fixture, which carries no
segment of its own); `stg_reviews` carries it through; the theme-share marts
group by `stg_reviews.segment` with no `raw_source_pages` join, so segment is
unambiguous on every input (synthetic, captured, samples) and the multi-segment
guard is unneeded. `segment` is attribution, so it is outside the review content
hash (like `run_id`); an existing pre-7a database refuses the rebuild until
`make confirm reset` (the A8 column-check), which CI does not hit (it builds
fresh). Restores the invariant "every review is counted under exactly one
segment, its source's." (Decided with the developer before this amendment was
implemented; committed alone.)

Phase 7's open-data half — the DAMIR slice fetch and the fitted cost
distributions — is Phase 7b (Out of scope, below). This spec carries 6
done-when items.

## Why

Beat 2 promises two charts the pipeline cannot yet draw: **B2.2** the share of
each complaint theme month by month, and **B2.5** the held-claim complaint
share by segment. Both are the gated classifier's own output, counted. Phase 6
made the classifier and graded it (B2.4); its per-review decisions live only in
memory during a rebuild and in the gitignored decision cache — nothing persists
them where SQL can count them. This phase persists the review × theme
classification to a table and aggregates it into the two marts, so B2.2 and B2.5
flip Pending → Measured.

A review carries no segment. `raw_source_pages` was built (Phase 3a) to supply
one, but its documented review→segment join is by `source_url`, and on the
synthetic corpus that matches **0 of 39** reviews: the synthetic reviews carry
brand-free host roots (`https://www.opinion-assurances.fr/`) while
`raw_source_pages` carries the brand-bearing page addresses seeded from
`ingest/sources.py`. Segment is in fact a property of the *source* (one
declaration = one segment/channel), so this phase attaches segment by the
`source` slug and corrects the `raw_source_pages` header. (Decided with the
developer before this spec; a fix, not a silent repair.)

## The central constraint

**The no-key run stays green and the `unclassified` band stays visible.** With
`ANTHROPIC_API_KEY` unset the classifier is rules-only, more reviews are
`unclassified`, and the two new marts must show that as an honest `unclassified`
share — never drop those reviews, never leave a mart empty by hiding them. The
frozen `fixtures/synthetic/` is not touched (that is the point of attaching
segment by source, not by re-freezing the reviews to carry page addresses).

## DONE command

```
make rebuild ROWS=synthetic && make idempotency-check ROWS=synthetic && make check-backing && make test
```

- `make rebuild ROWS=synthetic` — builds `stg_classified_reviews` and both
  theme-share marts on the synthetic corpus; prints the classification summary
  (unchanged) and leaves the marts populated (reproduces the pins in
  `tests/pins.py`).
- `make idempotency-check ROWS=synthetic` — rebuilds twice, diffs per-table row
  counts: proves the new table and marts are stable run to run.
- `make check-backing` — B2.2 and B2.5 are Measured with an existing SQL file
  and a declared-shape source; no orphan mart.
- `make test` — the new pins and invariant tests, and the extended no-key test,
  all pass with the key unset.

## Done-when

1. **The classification persists.** For every staged review the classify step
   writes its `(source, external_id, theme)` rows to `stg_classified_reviews`
   at the review × theme grain `classify_all` returns (a K-theme review is K
   rows; a review with none is one `positive` or `unclassified` row), sorted so
   a re-run is byte-identical. *Evidence: rows 1, 5.*
2. **Theme share by month.** `theme_share_by_month` has one row per
   `(month, segment, label)` with `reviews`, `theme_rows`, `share`, built by
   portable SQL over `stg_classified_reviews` ⋈ `stg_reviews` (month from the
   review's own date) ⋈ the source-grain segment; the synthetic counts are
   pinned. *Evidence: row 2.*
3. **Theme share by segment.** `theme_share_by_segment` has one row per
   `(segment, label)` with the same columns; the synthetic counts are pinned,
   and the `document-loop` share B2.5 highlights is among them. *Evidence: row 3.*
4. **One segment per review (amendment A1).** Every review carries the segment
   of the source it was loaded from, on `stg_reviews`; the marts group by it, so
   a review is never counted under two segments, on any input. *Evidence: row 4.*
5. **The no-key run is green and the band shows.** With the key unset,
   `make rebuild` exits 0 and each mart's `unclassified` share equals the
   rules-`unclassified` share of that cell — the gray "not yet classified" band,
   not an empty mart. *Evidence: row 5.*
6. **B2.2 and B2.5 are Measured.** BACKING flips both Pending → Measured with
   their SQL files and a declared-shape upstream source; `make check-backing`
   is green and SPEC's Pending notes are gone. *Evidence: row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_theme_share.py::test_classified_reviews_grain_and_sorted` / `make idempotency-check ROWS=synthetic` diff is empty |
| 2 | `tests/test_theme_share.py::test_by_month_pins` (reproduces `THEME_SHARE_BY_MONTH_*` in `tests/pins.py`) |
| 3 | `tests/test_theme_share.py::test_by_segment_pins` (reproduces `THEME_SHARE_BY_SEGMENT_*`) |
| 4 | `tests/test_theme_share.py::test_review_segment_is_its_source_segment` |
| 5 | `tests/test_no_key.py::test_theme_share_shows_unclassified_band` (key unset, rebuild green, band non-empty) |
| 6 | `make check-backing` prints PASS; BACKING B2.2/B2.5 show Measured in the diff |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all staged reviews, a second rebuild leaves `stg_classified_reviews` and both theme-share marts with byte-identical rows. | `tests/test_theme_share.py::test_rebuild_twice_stable` — rebuild synthetic twice, diff every new table. |
| For all reviews, the review carries exactly one segment — its loading source's — so no review is counted under two segments (amendment A1). | `tests/test_theme_share.py::test_review_segment_is_its_source_segment` — a synthetic review's `stg_reviews.segment` is its platform's declared segment; a sample review's is `sample`. |
| For all `(month, segment)` [and each `segment`], every review contributes at least one row and the label rows partition the review's `classify_all` output — no review is dropped from a mart. | `tests/test_theme_share.py::test_no_review_dropped` — sum of `theme_rows` over labels equals the cell's `classify_all` rows. |
| For all runs with no key, `make rebuild` exits 0 and each cell's `unclassified` share equals its rules-`unclassified` share. | `tests/test_no_key.py::test_theme_share_shows_unclassified_band`. |

## Pinned decisions (do not re-litigate)

- **Segment is stamped onto the review at load time (amendment A1).** A review
  is loaded from exactly one source, whose `segment` is known in Python then, so
  `raw_reviews` carries a `segment` column and the marts group by
  `stg_reviews.segment` — no join, unambiguous on synthetic, captured and
  samples alike. Rejected: the `source_url` join `raw_source_pages` documents
  (0/39 on synthetic); rejected: joining by the `source`/platform slug (two
  segments per platform on `samples`). `segment` is outside the content hash
  (attribution, like `run_id`). Satisfies invariant 2.
- **`stg_classified_reviews` lives in `sql/staging/`, DDL-only, Python-fed.**
  It maps to no BACKING claim of its own, and `check-backing` orphan-checks
  `sql/marts/`; a marts file with no row would FAIL. `create table if not
  exists` in the staging pass creates it empty; the classify step
  `delete`+`insert`s it (like `classifier_quality`). Rejected: `sql/marts/`
  (orphan). Satisfies done-when 1.
- **The classify step runs the two theme-share marts, after
  `stg_classified_reviews` is filled; `build_derived`'s marts loop excludes
  them.** They read the classification, which Python fills between staging and
  the rest of the marts. Rejected: reordering `build_derived` into
  staging→classify→marts (a wider refactor that also forces `classifier_quality`
  DDL to become non-destructive); rejected: running them empty in the marts loop
  then again after (pointless double build). Satisfies done-when 2, 3.
- **Share is at the theme-row grain: numerator `theme_rows`, denominator the
  distinct reviews in the cell.** A two-theme review counts once in the
  denominator and in two theme bars, so shares may sum past 1 — the grain
  SPEC.md Beat 2 settled ("a review may appear in two theme bars"). Rejected:
  one label per review (hides multi-theme reviews). Satisfies done-when 2, 3.
- **All seven labels are rows, including `positive` and `unclassified`.** The
  `unclassified` share is the gray "not yet classified" band the study shows;
  omitting it would hide the no-key degradation. Rejected: negative themes only.
  Satisfies the central constraint and done-when 5.
- **Both marts are tagged Measured; provenance is `run_id` only — no
  `source_url`, no `captured_at`, no clock.** A computed share has no address
  and no capture instant (as `classifier_quality` established); `month` is
  `substr(review_date, 1, 7)`, the review's own date, never `now()`. Rejected:
  a `captured_at` column. Satisfies the Provenance and no-clock contracts and
  done-when 6.

## Scope (files)

- `sql/staging/stg_classified_reviews.sql` — new; DDL-only, the persisted
  review × theme classification.
- `sql/marts/theme_share_by_month.sql` — new; B2.2.
- `sql/marts/theme_share_by_segment.sql` — new; B2.5.
- `sql/raw/raw_reviews.sql` — new `segment` column (amendment A1); it remains
  the declared-page registry, no longer the review→segment source.
- `sql/raw/raw_source_pages.sql` — header correction: no longer the
  review→segment source (segment is stamped at load).
- `sql/staging/stg_reviews.sql` — carry `segment`; header: it feeds the marts via
  `stg_classified_reviews` by `(source, external_id)`, grouped by its `segment`.
- `pipeline/build.py` — `segment` on the review load path (fixture + captures);
  `segment_by_platform`; `write_classified_reviews`; `build_theme_share_marts`;
  exclude the two theme-share marts from the generic marts loop.
- `pipeline/cli.py` — the classify step fills `stg_classified_reviews` and runs
  the two theme-share mart SQL files after it.
- `tests/pins.py` — `THEME_SHARE_BY_MONTH_*`, `THEME_SHARE_BY_SEGMENT_*`,
  `CLASSIFIED_REVIEWS_ROWS`.
- `tests/test_theme_share.py` — new; the grain, pins, segment invariant, no-drop.
- `tests/test_no_key.py` — extend: the band shows with the key unset.
- `BACKING.md`, `SPEC.md`, `README.md`, `CLAUDE.md`, `DECISIONS.md`,
  `BACKLOG.md`, this spec — records (see Record updates).

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 7a: segment-by-source (with the `raw_source_pages`
  header correction), the classify-step-runs-the-theme-marts ordering, the
  B1.1/B2.1 deferral.
- [ ] `BACKLOG.md` — open: no traditional-mutuelle corpus, so B2.2/B2.5's "vs
  traditional" half is empty until such a source is added (revisit trigger).
- [ ] `CLAUDE.md` — Current status; Repo map (`stg_classified_reviews`, the two
  theme-share marts, the classify step running them); Commands (`rebuild` now
  writes the theme-share marts); BACKLOG count.
- [ ] `BACKING.md` — B2.2, B2.5 Pending → Measured; fill their upstream source.
- [ ] `SPEC.md` — B2.2/B2.5 panels: drop the "(Pending until its mart lands)"
  notes (status, not a chart change).
- [ ] README — none (no README.md yet; it is a Phase 9 output).
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target. `make rebuild` already exists and takes `ROWS` (pinned in
Phase 3a); this phase adds SQL and a Python write path inside it, no new target,
no new variable, no delete, no paid call, no fetch. The classification the marts
count still calls the model only from `classify/llm.py`, only for
rules-`unclassified` reviews, only with a key — unchanged from Phase 6.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `sql/**`, `pipeline/**`, `tests/`): portable
  SQL (no clock, no regex, the `substr` month), provenance columns and the
  Measured tag, the review×theme grain, deterministic write path, scope (every
  change feeds B2.2/B2.5).
- **security-reviewer** (not triggered — no CI, `.env`, scraper, `classify/llm.py`,
  `pipeline/warehouse.py`, or destructive/paid/network target in the diff).
- **functionality-tester** (triggered): the DONE command; the pins; idempotency;
  the no-key band; a two-segment source.
- **study-editor** (triggered — `SPEC.md`, `README.md`, `BACKING.md`, `CLAUDE.md`
  change): the Beat 2 panels stay two-layer and name no insurer; the
  `unclassified` band is described as such.
- **coherence-auditor** at exit: SPEC B2.2/B2.5 ↔ BACKING (now Measured) ↔ the
  two marts ↔ README Beat 2 reconcile; no stale "Pending until its mart lands"
  sentence remains; the `raw_source_pages` header no longer documents a join the
  code does not use.
- Stack risk: the build ordering — the theme-share marts must see a filled
  `stg_classified_reviews`. Verify in the first hour that a plain `make rebuild
  ROWS=synthetic` (no key) populates both marts, and that the marts loop does
  not build them empty first. STOP and report before any workaround; findings go
  to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- **Open DAMIR slice + fitted cost distributions** — Phase 7b (its own spec;
  network + large files, a security-reviewer surface).
- **B1.1 hero case, B2.1 taxonomy examples** — Documented rows with no mart;
  they flip when their prose is curated with links (Phase 9 study). Recorded in
  DECISIONS Phase 7a.
- **The "vs traditional" comparison** — no traditional-mutuelle source exists;
  the marts split by whatever segments the data has (all `digital-first` today).
  BACKLOG row.
