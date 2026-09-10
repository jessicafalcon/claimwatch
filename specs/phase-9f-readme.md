# Phase 9f — The README + the stranger acceptance test (PROPOSED)

Contract for the `phase-9f` branch. Source: PROJECT_BRIEF.md §9 Phase 9 (done
when: "a stranger goes from the README's first paragraph to any number's raw
evidence without asking a human anything") and §3 (the README is the third
delivery format, telling the same five beats in prose). Depends on Phase 9e
merged.

**Status: APPROVED 2026-09-10 — in progress.** No new dependencies (the
allowlist is in CLAUDE.md → Conventions). No new `make` target, no new chart
`Kind`, no new mart, no new BACKING row.
Challenged: 2026-09-10, round 1, spec 9d690e59 — approve with amendments (5 should-fix + 2 suggestions applied)

## Why

Beats 1–5 render as a permanent HTML artifact (9a–9e) and the marts back every
number, but a person arriving at the repo has no prose entry point and no
mechanical guarantee that a reader can walk from a claim to its evidence
unaided. The brief's Phase 9 done-when is exactly that walk. It is a new prose
surface (the README) plus a test that pins the walk — not a fix to any existing
file, so it is a phase, not a fix PR. It also settles two decisions the earlier
sub-phases deferred to 9f: whether the *published* study is a captured render
(BACKLOG "The published study's corpus render is not decided") and whether the
permanent page may carry a live slider script (BACKLOG "Live sliders need a
script the permanent page does not carry").

## The central constraint

**The committed `study/friction_ledger.html` does not change: the README is a
new prose surface over the existing byte-checked permanent artifact, which still
renders the frozen synthetic corpus and stays byte-identical on a re-render.**
The stranger test reads text; it renders nothing new and moves no pinned number.

## DONE command

```
make review-gate SPEC=specs/phase-9f-readme.md && make study && git diff --exit-code
```

- `make review-gate SPEC=specs/phase-9f-readme.md` — test + ruff (read-only) +
  check-docs + check-backing + fixtures + check-pins, and with `SPEC=`, the
  spec's own Evidence ids and Record-update files; `tests/test_readme.py` (the
  tag, per-figure citation and link invariants) runs in the suite, so the
  stranger walk is pinned here (review-gate ⊇ {test, check-docs}). The README
  enters the LIVING-doc set by existing on disk, so check-docs' banned words,
  links, glossary ≤ 10 and naming-the-target now scan it.
- `make study && git diff --exit-code` — the permanent artifact re-renders
  byte-identical and the tree is clean (README committed): proves the central
  constraint, that 9f added prose and changed no rendered byte.

## Done-when

1. **The README exists and tells the five beats in the two-layer voice.** Each
   beat opens with 2–3 plain sentences for a non-technical reader, then the
   under-the-hood layer; banned-words clean, glossary ≤ 10, no insurer named as
   the subject. *Evidence: row 1.*
2. **Every number a reader sees in the README prose wears exactly one tag**
   (Measured / Documented / Modeled / Pending). *Evidence: row 2.*
3. **The stranger walk is closed per number: every tagged figure sits in its
   own sentence or list-item that cites a specific `B<beat>.<n>`, and following
   *that figure's own* citation reaches *that figure's* backing row — not merely
   the beat's.** Every cited id resolves to a BACKING row, the first paragraph
   links onward into the evidence, and the README links to the permanent study
   page and to `BACKING.md` with every link resolving, so a reader reaches any
   one number's raw evidence using only the README's and BACKING's own links.
   *Evidence: row 3.*
4. **The permanent study page is unchanged — it renders the synthetic corpus,
   and the README states this and names the one command that rebuilds it over
   the real corpus** (`make rebuild ROWS=captured && make study`). *Evidence:
   row 4.*
5. **The live-slider decision is recorded and the permanent page carries no
   script.** *Evidence: row 5.*

(5 items.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `make check-docs` prints `ok banned words`, `ok glossary`, `ok naming the target`; study-editor confirms the two-layer opening per beat |
| 2 | `tests/test_readme.py::test_every_euro_or_percent_wears_a_tag` (a `€`/`%` figure with no tag word in its sentence fails), `::test_beat5_counts_and_day_n_use_the_tagged_template` |
| 3 | `tests/test_readme.py::test_every_tagged_figure_cites_a_resolving_row` (a figure whose sentence cites the wrong-but-real or no id fails), `::test_readme_cites_only_real_backing_rows`, `::test_first_paragraph_links_into_evidence`, `::test_readme_links_to_study_and_backing`; `make check-docs` prints `ok links` |
| 4 | `make study && git diff --exit-code`; `tests/test_readme.py::test_readme_names_the_captured_rebuild_command` |
| 5 | `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp` (already green); `DECISIONS.md` Phase 9f entry records the decision |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For every euro amount or percentage in the README's beat prose (outside code spans and links), the figure's sentence carries exactly one of the four tag words; Beat 5's three checkable counts and Beat 1's frozen "Day N on hold" are each written on a fixed, tested template line that carries its tag. | `tests/test_readme.py::test_every_euro_or_percent_wears_a_tag` (a `€`/`%` figure with no tag word fails), `::test_beat5_counts_and_day_n_use_the_tagged_template` |
| For every tagged figure in the README, the figure's own sentence or list-item cites a `B<beat>.<n>` that resolves to a row in `BACKING.md` — following *that* figure's citation reaches *that* figure's backing row; beat-granular reachability is not enough. | `tests/test_readme.py::test_every_tagged_figure_cites_a_resolving_row` (a figure whose sentence cites no id, or a `B9.9` with no row, fails), `::test_readme_cites_only_real_backing_rows` |
| For all links in the README, the link resolves; and the README links to `study/friction_ledger.html` and `BACKING.md`, and the first paragraph carries a link onward into the evidence. | `make check-docs` links check; `tests/test_readme.py::test_readme_links_to_study_and_backing`, `::test_first_paragraph_links_into_evidence` |
| For all re-renders, the committed `study/friction_ledger.html` is byte-identical (the permanent artifact is the synthetic render, unchanged by this phase). | `make study && git diff --exit-code` (CI), `tests/test_export.py` |
| For all renders of the permanent page, it carries no `<script>` and no external asset (no live slider). | `tests/test_export.py::test_export_has_no_cdn_no_external_asset_no_timestamp` |

## Pinned decisions (do not re-litigate)

- **The permanent artifact stays the synthetic render; a captured render is the
  reader's own `make rebuild ROWS=captured && make study`.** The committed page
  is deterministic and byte-checked (9a); a captured render would carry corpus
  state that drifts with the weekly cron and cannot be byte-checked in CI. This
  answers the brand-address question (the shipped page carries no per-review
  address; a captured render is run off the committed artifact) and the
  page-size question (moot — the shipped page is unchanged). *Rejected: shipping
  a captured render as the permanent artifact — breaks the byte-check and ships
  drifting corpus state. Satisfies invariant 4; closes the "corpus render"
  BACKLOG row.*
- **The permanent page carries no live slider; live exploration is the Metabase
  demonstration (9g).** *Rejected: an inline CDN-free script recomputing
  `FORMULAS` — a second copy of the formulas in a second language needs its own
  module↔script identity test and breaks the self-contained, byte-stable
  artifact (9a/9c). Satisfies invariant 5; the "live sliders" BACKLOG row closes
  at 9g per its own trigger.*
- **The stranger test is a pytest over the README text, not a new
  `scripts/check_docs.py` check.** `check_docs` is for structural docs guards
  (links, banned words, glossary, naming) and already covers the README; a
  content/pins assertion — a figure carries its tag and its own resolving
  citation — is a test, and belongs beside the README in `tests/test_readme.py`.
  The review surface follows from the test's nature (code → code-reviewer +
  functionality-tester), not the other way round. *Rejected: extending
  `scripts/check_docs.py` — it duplicates the link/naming coverage and puts a
  content pin inside a structural guard.*
- **The README cites BACKING row ids inline (`B<beat>.<n>`) as the drill
  anchors, not raw SQL.** The reader's hop is README → id → `BACKING.md`, which
  `make check-backing` already maps id → table → SQL → source. *Rejected:
  pasting SQL into the README — duplicates BACKING and drifts from it.*
- **The README's numbers are limited to Beat 5's checkable facts and figures
  already tagged in the study; it does not restate every chart value.** Avoids a
  second pin surface that drifts from the marts. *Rejected: a full numeric
  recap — every restated value becomes a pin that can disagree with the mart.*
- **The mechanical tag check matches only unambiguous figure shapes — `€`
  amounts and `%` percentages in beat prose (outside code spans and links) —
  with no date/version denylist** (the promoted `unshaped-input` class: a loose
  pattern plus an exclusion list false-negatives silently). Beat 5's three
  checkable counts and Beat 1's frozen "Day N on hold" are the only other
  bare-number figures; each is written on a fixed template line the test asserts
  by shape, so a bare count needs no digit-sniffing regex. A bare number outside
  these forms is a study-editor / `/selfcheck` (c) finding, as today. *Rejected:
  a "multi-digit count minus dates/versions/code" shape — the denylist is the
  trap. Rejected: a catch-all "any digit" check — false-positives on dates and
  versions make it unmaintainable.*

## Scope (files)

- `README.md` — new. The five beats in the two-layer voice; the first paragraph
  links into the evidence; each beat cites its BACKING rows and links to the
  study page; the fixture-state note and the `ROWS=captured` rebuild command;
  Beat 5's checkable facts, each tagged; the "why not dbt" sentence (brief §2.2,
  §9.3); a glossary ≤ 10 terms if one is added.
- `tests/test_readme.py` — new. The `€`/`%` tag test, the per-figure citation
  test (each tagged figure's own sentence cites a resolving `B<beat>.<n>`), the
  Beat 5 count / Beat 1 "Day N" template tests, the link, first-paragraph and
  rebuild-command tests; reads README/BACKING through `tests/repo_text.py`.
- `tests/repo_text.py` — extended only if the reader needs a README/BACKING
  accessor it does not already expose.
- `DECISIONS.md` — Phase 9f entry (the two decisions above; the README-as-prose
  surface rationale is already in the 9a entry).
- `BACKLOG.md` — close "The published study's corpus render is not decided"
  (struck + "DONE Phase 9f"); re-point the "Live sliders" row's trigger firmly
  at 9g; re-point the classify-path idempotency row's ("`make idempotency-check`
  skips the classify step") trigger off "Phase 9f's captured `make study`" to
  Phase 10's DAG — this spec keeps the committed page synthetic, so the classify
  step never runs inside a coverage target here; the `pipeline/build.py`
  accretion row carried in on this branch stays open; update the open count.
- `CLAUDE.md` — Current status → 9f; Repo map (README as a delivery surface,
  `tests/test_readme.py`); BACKLOG count.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 9f entry (captured-render decision; live-slider decision)
- [ ] `BACKLOG.md` — "corpus render" row struck + "DONE Phase 9f"; "live sliders" trigger re-pointed at 9g; classify-path idempotency row's trigger re-pointed to Phase 10's DAG; open count updated
- [ ] LESSONS.md — none until a review round reports a correctness finding; then backtick it and the fix commit writes the row
- [ ] `CLAUDE.md` — Current status; Repo map; BACKLOG count
- [ ] BACKING.md — none: the README cites existing rows and adds none; no tag changes
- [ ] SPEC.md — none: no chart or beat changed; the README is a new prose surface, not a new chart
- [ ] `README.md` — the phase's own subject (new file)
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches the
network. The phase adds a prose file and a read-only test; the DONE command's
`make study` is the existing offline, no-key, no-network render.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `tests/test_readme.py`): the tag/backing-id/link
  tests read repo text through the one reader; assertions on the smallest output
  that contains the mechanism's result (not the whole file); the figure-shape
  regex is anchored and its residual is declared.
- **security-reviewer** (not triggered — no `scripts/`, `.github/`, ingest,
  credentials, network, paid API or destructive target in the range; the stranger
  check is a test, not a `check_docs` change, by pinned decision).
- **functionality-tester** (triggered): the DONE command; that
  `test_every_euro_or_percent_wears_a_tag` fails on an untagged figure, that
  `test_every_tagged_figure_cites_a_resolving_row` fails when a figure's sentence
  cites the *wrong-but-real* B-id or none (the cheapest check of the "any number
  reaches its own evidence" claim), and `test_readme_cites_only_real_backing_rows`
  fails on a dangling id (hand-mutate the README in a worktree); that `make
  study` stays byte-identical.
- **study-editor** (triggered — README is new prose): two-layer opening per beat,
  name-by-meaning, no editorial sentence about one company, paraphrase not quote,
  glossary discipline, the sampling-bias note beside the rating trend; that
  Beat 1–2 prose clearly separates the shipped page's illustrative *synthetic*
  figures (under the fixture note) from the *measured* findings a reader gets on
  their own `ROWS=captured` rebuild (the honesty rests on this, not on note
  prominence alone); and whether the B2.2/B2.5 counts are legible to a reader
  without hover (the tooltip-count judgment, per Out of scope).
- **coherence-auditor** at exit (mandatory): the README's five beats match SPEC's
  five beats and BACKING's rows; no stale "no README yet" sentence remains in
  CLAUDE.md or DECISIONS; the two closed/​re-pointed BACKLOG rows are consistent
  with their triggers; the finished README supports 9g (the Metabase
  demonstration reads the same marts the README names).
- Stack risk: the `€`/`%` tag regex — verify in the first hour it flags an
  untagged euro amount and does not flag `ROWS=captured` or a link; and that
  `make check-pins BASE=origin/main` is green once `tests/test_readme.py` exists
  (the new test file's symbols do not choke the pin guard). Record any surprise
  under DECISIONS → Gotchas rather than widening the regex.

## Out of scope (deferred, recorded)

- The Metabase demonstration and the review-level drill (BACKLOG "A per-review
  drill…", "The published study's corpus render…" residual exploration) — Phase
  9g.
- A live, in-browser slider recomputing `FORMULAS` (BACKLOG "Live sliders…") —
  closes at 9g if the Metabase demonstration is the exploration.
- The B2.2/B2.5 tooltip-only counts becoming visible text (BACKLOG "The
  B2.2/B2.5 trail is tooltip-only") — the mechanical pytest cannot model reader
  perception, so this judgment is the study-editor's human read on this surface;
  if study-editor finds a reader misses the counts, a fix amendment follows, not
  this phase's prose.
- The claims sample-mean slider and data.ameli practitioner fees — the two
  pulled-out data phases (DECISIONS Phase 9a).
