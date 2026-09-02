# Phase 0b — Contracts (PROPOSED)

Contract for the `phase-0b-contracts` branch. Source: PROJECT_BRIEF.md §9
Phase 0 (the contracts half), split per `docs/PLAN.md` §5 (approved
2026-09-01): 0a built the gate, 0b writes the contracts the gate then checks.
Depends on `phase-0a-machinery` merged.

**Status: PROPOSED — do not start until approved.** One dependency change: none
(stdlib only). This phase adds one small guard to `scripts/check_backing.py` and
its test; no runtime package. The allowlist is in CLAUDE.md → Conventions.

## Why

Phase 0a proved a gate on an empty project. Nothing yet says what the study
claims, which chart shows it, or where its number comes from — the brief's §8
promise ("if a claim has no row here, it is not in the study") has no content to
enforce. Phase 0b writes the two contract files that every later phase is
scoped by: `SPEC.md` (the five parts and the exact chart list, each panel citing
its evidence) and the full `BACKING.md` table (every claim → mart → SQL → source
→ tag). Until they exist and agree with the brief and each other, Phase 1's
schema has nothing to build toward. This is documents and one guard, not
pipeline code.

## The central constraint

**Every BACKING row is Pending and carries no number; no chart is faked, and no
`sql/`, `fixtures/` or pipeline file is written.** 0b writes the scope, not the
data. A Pending row may name a `sql/marts/` file not built yet (the tag says
so); a SPEC.md panel shows its tag and its BACKING row id, never a value and
never a `make` target that does not exist. The seven-label set and the
deterministic-first architecture are described here, not changed.

## DONE command

```
make review-gate SPEC=specs/phase-0b-contracts.md
```

- `make test` — the guard pins green, including the new
  `tests/test_check_backing.py::test_spec_citations`; offline, no services.
- `ruff check` + `ruff format --check` — read-only lint green.
- `make check-docs` — links/anchors, named `make` targets, banned words and
  glossary size (≤ 10) green over the living docs now that `SPEC.md` exists;
  BACKLOG count green (6 → 5).
- `make check-backing` — the full table passes: every row has an id, a tag in
  the four, a source of the declared shape, and its SPEC citations reconcile.
- Evidence rows — every test id and target below exists; Record updates — every
  listed file is in `git diff main...HEAD`.

## Done-when

1. **`SPEC.md` is the five parts and the exact chart list.** Every panel names
   its tag and its BACKING row id (`B<beat>.<n>`), states the classification
   grain where a theme-share chart depends on it, and names the sampling bias
   beside the rating-trend panel; SPEC.md names no `make` target absent from the
   Makefile. *Evidence: row 1.*
2. **`BACKING.md` is the full table, every row Pending.** Each row: a claim
   opening with `B<beat>.<n> `, a tag in {Measured, Documented, Modeled,
   Pending} (all Pending in 0b), a source of the declared shape, and a
   `sql/marts/` path that may be unbuilt. `make check-backing` green. *Evidence:
   row 2.*
3. **SPEC ↔ BACKING citations reconcile both ways.** Every `B<beat>.<n>` cited
   in SPEC.md is a row in BACKING.md, and every BACKING row is cited by at least
   one SPEC.md panel or prose sentence — a new check in `check_backing.py`,
   pinned by a test. *Evidence: row 3.*
4. **Classification grain is pinned before any chart is frozen:** one row per
   review × theme (a review carrying K themes writes K theme rows; a review with
   none writes one `unclassified` or `positive` row) — stated identically in
   SPEC.md's theme-share definitions and CLAUDE.md's Classification contract.
   *Evidence: row 4.*
5. **The glossary is ≤ 10 terms, one everyday example each.** ≤ 10 is
   mechanical (`make check-docs` glossary); the everyday example on each term is
   editorial (study-editor). *Evidence: row 5.*
6. **CLAUDE.md is final and the records reconcile.** BACKLOG row 18 (label
   arity) struck "DONE Phase 0b" and the count moved 6 → 5; a DECISIONS Phase 0b
   entry; the phase-exit coherence audit finds no SPEC ↔ BACKING ↔ CLAUDE drift.
   *Evidence: row 6.*

(6 items. Each is a contract, not a narrative.)

## Evidence (REQUIRED)

| Done-when | Proof |
|---|---|
| 1 | `make check-docs` prints `check-docs OK` (make-targets check green over SPEC.md, pinned by `tests/test_check_docs.py::test_every_named_make_target_exists_today`); study-editor confirms every panel wears one tag and one `B<beat>.<n>` id and the rating-trend panel names its sampling bias |
| 2 | `make check-backing` prints `check-backing OK: <N> rows, 0 marts` with every row Pending; the tag, source-shape and row-id checks are pinned by `tests/test_check_backing.py::test_tag_outside_the_four_fails`, `::test_measured_without_source_fails`, `::test_claim_without_row_id_fails`, `::test_pending_row_is_ok_without_source` |
| 3 | `tests/test_check_backing.py::test_spec_citations` — a SPEC citation with no BACKING row fails, a BACKING row cited nowhere in SPEC fails, matched sets pass, an absent SPEC.md passes; `make check-backing` green on the delivered pair |
| 4 | coherence-auditor confirms SPEC.md and CLAUDE.md state the same grain (one row per review × theme); the falsifying code test lands with `classified_reviews` in Phase 5b (`tests/test_classify_grain.py::test_k_themes_yield_k_rows`, deferred — documentary here) |
| 5 | `make check-docs` glossary check green (≤ 10 terms), pinned by `tests/test_check_docs.py::test_check_glossary_reports_an_eleventh_term`; study-editor confirms each term carries an everyday example |
| 6 | `make check-docs` BACKLOG-count check green (5), pinned by `tests/test_check_docs.py::test_check_backlog_count_reports_a_mismatch`; coherence-auditor at exit reports no stale SPEC/BACKING/CLAUDE sentence |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all `B<beat>.<n>` ids cited in SPEC.md, the id is a row in BACKING.md; and for all BACKING rows, the id appears in SPEC.md (cited by a panel or a prose sentence). An absent SPEC.md (Phase 0a) is OK. | `tests/test_check_backing.py::test_spec_citations` — a dangling SPEC citation fails; an uncited BACKING row fails; matched sets pass; no SPEC.md passes |
| For all BACKING rows, the tag is one of exactly four, a Measured or Documented row names a source of the declared shape, the claim opens with `B<beat>.<n> `, and every SQL path resolves under `sql/` (a Pending row may name a file not built yet). | `tests/test_check_backing.py::test_tag_outside_the_four_fails`, `::test_measured_without_source_fails`, `::test_claim_without_row_id_fails`, `::test_pending_row_is_ok_without_source`, `::test_sql_path_traversal_is_refused` (0a invariant, now exercised on a full table) |
| For all glossary sections in a LIVING doc, there are ≤ 10 `- **term**` bullets. | `tests/test_check_docs.py::test_check_glossary_reports_an_eleventh_term` |
| For all `make` targets a LIVING doc names, the target exists as an exact token in the Makefile (SPEC.md is LIVING, so a chart may name a mart by its BACKING row id but never a `make` target that is not built). | `tests/test_check_docs.py::test_every_named_make_target_exists_today`, `::test_partial_rename_is_a_failure` |
| For all classified reviews, a review carrying K themes yields exactly K theme rows and a review with none yields one `unclassified` (or `positive`) row — pinned now in SPEC.md and CLAUDE.md; the mechanism and its falsifying test land with `classified_reviews` in Phase 5b. In 0b the check is editorial: coherence-auditor confirms SPEC.md and CLAUDE.md agree. | Phase 5b `tests/test_classify_grain.py::test_k_themes_yield_k_rows` (deferred); 0b: coherence-auditor cross-reads SPEC.md ↔ CLAUDE.md |

## Pinned decisions (do not re-litigate)

- **The citation guard is one addition to `check_backing.py`, not a new
  target.** It reads `SPEC.md` (when present) for `B<beat>.<n>` tokens and
  reconciles them against the parsed BACKING row ids in both directions; the
  DONE command and CI already run `make check-backing`, so no `make` target is
  added and SPEC.md cites none. Satisfies invariant 1. Rejected: a separate
  `check-spec` target (SPEC ↔ BACKING is the evidence contract, which is
  `check_backing`'s job) and a check in `check_docs` (it does not parse the
  BACKING table).
- **A prose claim cites its id inline in SPEC.md.** "Cited by a panel or a prose
  claim" (brief §8, invariant 1) is enforced as: the row's `B<beat>.<n>` id
  appears in SPEC.md, whether beside a chart or inside a narrative sentence. So
  parity is symmetric and mechanical. Rejected: a "prose-only" marker column in
  BACKING (a second place to keep in step; the id in SPEC is the single source).
- **Classification grain: one row per review × theme.** Brief §5 lets a review
  carry several themes; a theme-share chart counts theme rows, so the grain is
  `(review_id, theme)` — one row each, `unclassified`/`positive` as a single
  row when no theme applies. Closes BACKLOG row 18. Stated in SPEC.md and
  CLAUDE.md's Classification contract before any chart is frozen. Satisfies the
  arity invariant. Rejected: one `theme` column per review (a multi-theme review
  could not be counted per theme without a second table).
- **Tag presence and tag-match on a panel are editorial, not mechanical.** The
  guard checks id parity only; that each panel wears exactly one of the four
  tags, and that the tag matches its BACKING row, is study-editor's and
  coherence-auditor's read this phase. Rejected: parsing panel → tag → id
  association in the guard (more than one small addition; the brief's render-time
  refusal, Phase 9, is where a Pending panel's value is caught mechanically —
  already a BACKLOG row).
- **All rows start Pending; the flip is a later phase's Record update.** Per
  BACKING.md's rules and the 0a decision: BACKING is written before code, so
  every 0b row is Pending and flips to Measured/Documented/Modeled in the phase
  that lands its mart. No number appears in 0b. Rejected: tagging a row Measured
  before its mart exists (the guard would demand the SQL file).

## Scope (files)

- `SPEC.md` — new: the five parts (beats), the exact chart list with each
  panel's tag and `B<beat>.<n>` id, the classification-grain note, the
  sampling-bias note beside the rating-trend panel, the glossary (≤ 10 terms).
- `BACKING.md` — the full table appended under the existing header; every row
  Pending.
- `CLAUDE.md` — Current status; Classification contract (the grain); the
  `check-backing` one-liner (now "↔ SPEC citations"); Repo map (`SPEC.md`
  exists); BACKLOG count 6 → 5.
- `DECISIONS.md` — Phase 0b entry (the grain, the citation guard, the SPEC/
  BACKING structure choices).
- `BACKLOG.md` — row 18 (label arity) struck "DONE Phase 0b".
- `scripts/check_backing.py` — the citation check (check 7); its docstring.
- `tests/test_check_backing.py` — `test_spec_citations`.
- `Makefile` — the `check-backing` help line, if its wording changes.
- `specs/phase-0b-contracts.md` — this spec; the "Delivered" paragraph appended
  at exit.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 0b entry: classification grain, the citation
      guard, the SPEC/BACKING structure choices; no supersede pointers
- [ ] `BACKLOG.md` — row 18 (label arity) struck + "DONE Phase 0b"
- [ ] `CLAUDE.md` — Current status; Classification contract (grain); Repo map;
      `check-backing` one-liner; BACKLOG count 6 → 5
- [ ] `BACKING.md` — the full table (all rows Pending)
- [ ] `SPEC.md` — new file: the five parts, chart list, grain note, glossary
- [ ] README — none (Phase 9; PROJECT_BRIEF.md is the front door until then)
- [ ] `specs/phase-0b-contracts.md` — this spec; the "Delivered" paragraph at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches
the network. The citation check runs inside the existing `make check-backing`,
which reads `SPEC.md` and `BACKING.md` from the working tree and takes no
variable.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").
**`docs/PLAN.md` §5 lists only coherence-auditor and study-editor for 0b — that
assumed a docs-only diff. This spec adds a guard to `scripts/check_backing.py`
and a test to `tests/`, so the code surface is touched and the union runs:
code-reviewer + functionality-tester join. security-reviewer stays untriggered
— the guard only reads two tracked files; no CI, `.env`, network, paid API or
destructive/variable target is in the range.**

- **code-reviewer** (triggered — `scripts/check_backing.py`, `tests/`): the
  citation check is stdlib-only, guards an absent `SPEC.md`, has no clock and no
  network, and is a closed parse (a `B<beat>.<n>` token set compared both ways);
  no formula, no model, no SQL.
- **security-reviewer** (not triggered — no CI, `.env`, credentials, network,
  paid API or destructive/variable target; the guard reads files only).
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  command; `test_spec_citations` on planted trees — a dangling SPEC citation, an
  uncited BACKING row, matched sets, and no `SPEC.md` — each showing the one-line
  result.
- **study-editor** (triggered — `SPEC.md`, `BACKING.md` claims, `CLAUDE.md`
  prose): every one of the five parts opens two-layer (plain first, technical
  signposted); names are by meaning, not mechanism; every panel wears exactly
  one tag and one id; the trend chart is framed as a hypothesis, not a verdict,
  and the rating-trend panel names the negative self-selection of unsolicited
  platforms; no sentence is editorial about a single insurer; the glossary stays
  ≤ 10 terms, each with an everyday example.
- **coherence-auditor** at exit (mandatory): SPEC charts ↔ BACKING rows ↔ tags
  reconcile; SPEC.md and CLAUDE.md state the same classification grain; SPEC.md
  names no unbuilt `make` target; the BACKLOG count is 5; the Repo map marks
  what exists.
- Stack risk: the citation regex must not treat a `B<beat>.<n>` token inside a
  SPEC.md code fence or an illustrative example as a real citation, nor miss one
  in a table cell. Verify against the delivered SPEC.md in the first hour; if it
  bites, record the edge in BACKLOG rather than widening the regex silently.
  STOP and report before any workaround; findings go to DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- Actual mart SQL, `fixtures/`, `pipeline/` — Phase 1.
- The render-time "a Pending panel shows no number" refusal — BACKLOG row
  (Phase 9 export), unchanged by this phase.
- Mechanical tag-on-panel and tag-match checks — editorial now (study-editor,
  coherence-auditor); may become a guard when the export lands.
- The `classified_reviews` grain test — Phase 5b (named in Evidence row 4).
