# Phase 5a — Label sample + the labels wall (PROPOSED)

Contract for the `phase-5a-label-sample` branch. Source: PROJECT_BRIEF.md §9
Phase 5 ("Hand labels + rules layer"), split into 5a/5b per `docs/PLAN.md` §5
(the split was named there before this spec: "5a — Label sample + wall", "5b —
Rules layer"). Depends on Phase 4 merged (PR #8) and the Phase 4 docs hotfix
merged (PR #9).

**Status: PROPOSED — do not start until approved.** No new dependencies (uses
DuckDB via `pipeline/warehouse.py`, stdlib `csv`/`hashlib`; no `pyyaml`, no
`anthropic` — `rules.yaml` and the model are 5b and 6). The allowlist is in
CLAUDE.md → Conventions.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

## Why

Beat 2 shows the share of negative reviews in each of five themes (SPEC.md
B2.2, B2.4, B2.5). A machine can only be trusted to read those themes if it is
graded against reviews a person read first — the hand-labeled eval set the
brief calls for (§5, §4.1). Before any rule or any model is written, two things
must exist and be trustworthy: a **sample of real reviews for a human to
label**, and a **wall** between those hand labels and every part of the
pipeline that will later be scored against them. If the classifier could see
the answer key, its scores would be a lie.

This is 5a because it is the whole trust foundation and nothing else: the label
set as a closed list, a stable id for every review, a command that draws the
sample, the answer-key file's text-free shape, the deterministic held-out
split, and the grep that proves the wall holds. The rules that read reviews and
the precision they earn are 5b; the model is 6. Splitting keeps each under six
done-when items (CLAUDE.md → Workflow rules) and lets the human labeling happen
offline between the two — hours of a person's time, not a session's (`docs/PLAN.md`
§5, risk 6).

*What a held-out eval split is, and why here.* To check whether a classifier
can be trusted, you hide some hand-labeled examples from it while it is built
and tuned, then grade it only on those hidden ones — the way a teacher grades a
test with questions the student never saw. We split by a hash of the review id
(`sha256(review_id) % 5`): four fifths are the tuning folds 5b may look at, one
fifth is held out for Phase 6's gate. A hash, not a coin toss, so the same
review lands in the same fold on every machine, every run.

## The central constraint

**The hand labels are the answer key, and nothing that is graded against them
may read them.** `classify/eval/labels.csv` is read only by `classify/eval/`;
no rule file, no model call, no SQL, no mart, no other pipeline module touches
it. The file carries no review text — an id and a theme, nothing a body or a
brand could ride in on. The held-out fold is a pure function of the review id,
identical on every run, chosen by no clock and no coin. A review is labeled
with one of exactly seven themes or it is not labeled at all — an eighth label
cannot be written.

## DONE command

```
make test
```

- `make test` — the pins below: the seven-label set is closed (an unknown theme
  is refused, not coerced); `review_id` is `{source}:{external_id}`, stable and
  distinct per staged review; `make label-sample N=` draws a byte-identical
  sheet on re-run and caps N at the corpus size; the sheet carries review text
  and lives only under gitignored `data/` while the tracked `labels.csv` carries
  none; the held-out fold is `sha256(review_id) % 5`, identical across runs; the
  labels-isolation grep finds no reader of `labels.csv` outside `classify/eval/`;
  and an absent or header-only `labels.csv` reads as zero eval rows, never an
  error. (5a has no `classify-eval` yet — that command and per-theme precision
  are 5b; 5a's DONE is the suite, matching `docs/PLAN.md` §5.)

## Done-when

1. **The theme set is a closed list of seven.** The five §5 themes plus
   `positive` and `unclassified`, defined once as data; a theme outside the set
   is refused by the labels reader, never coerced to an eighth. *Evidence: row 1.*
2. **Every review has a stable, deterministic id.** `review_id =
   "{source}:{external_id}"`, identical across runs and distinct per staged
   review (39 in the synthetic corpus). *Evidence: row 2.*
3. **`make label-sample N=<n>` draws a deterministic, text-carrying sheet under
   gitignored `data/` only.** Same corpus and N → a byte-identical
   `data/label_sample.csv` (`review_id, source_url, text`), N capped at the
   corpus size, reviews chosen by `sha256(review_id)` order — no clock, no
   random; a missing warehouse writes a header-only sheet and says so.
   *Evidence: row 3.*
4. **The tracked answer key carries no review text.** `classify/eval/labels.csv`
   is `review_id, theme` — one row per review × theme (K themes → K rows, none →
   one `positive` or `unclassified` row), no `text`/`title`/`body` column; it
   ships header-only (no fabricated labels land before a human labels). *Evidence:
   row 4.*
5. **The held-out split is `sha256(review_id) % 5`, never random.** A pure
   function of the id; the same review lands in the same fold on every run; one
   pinned fold is held out for Phase 6, four are the tuning folds. *Evidence:
   row 5.*
6. **The answer key is read only by `classify/eval/`, and reads sanely when
   small or absent.** No module outside `classify/eval/` reads `labels.csv`; the
   reader refuses an out-of-set theme; an absent or header-only file is zero eval
   rows, never a raise. *Evidence: row 6.*

(6 items. Each is a contract the code can falsify.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_labels.py::test_theme_set_is_the_seven`, `::test_out_of_set_theme_is_refused` |
| 2 | `tests/test_labels.py::test_review_id_is_source_and_external_id`, `::test_review_id_stable_and_distinct_over_corpus` |
| 3 | `tests/test_label_sample.py::test_sheet_is_byte_identical_on_rerun`, `::test_n_caps_at_corpus_size`, `::test_missing_warehouse_writes_header_only` / `make label-sample N=5` |
| 4 | `tests/test_label_sample.py::test_labels_csv_has_no_text_column`, `tests/test_labels.py::test_labels_csv_ships_header_only` |
| 5 | `tests/test_split.py::test_fold_is_sha256_mod_5`, `::test_fold_stable_across_runs`, `::test_heldout_fold_is_pinned` |
| 6 | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval`, `tests/test_labels.py::test_absent_labels_is_zero_rows`, `::test_small_labels_scores_what_exists` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all themes the labels reader accepts, the theme is one of the seven closed labels — an eighth is impossible. | `tests/test_labels.py::test_out_of_set_theme_is_refused` — a `labels.csv` row whose theme is `document-loop-ish`; the reader refuses it rather than admitting an eighth label. |
| For all reviews, `review_id` is `{source}:{external_id}`, identical across runs and distinct per staged review. | `tests/test_labels.py::test_review_id_stable_and_distinct_over_corpus` — two runs over the synthetic corpus yield the same 39 ids with no collision. |
| For all corpora and all N, `make label-sample` writes a byte-identical sheet on re-run. | `tests/test_label_sample.py::test_sheet_is_byte_identical_on_rerun` — the sampler run twice on one warehouse; the two `data/label_sample.csv` files are byte-equal. |
| For all sheets the sampler writes, the review text lives only under gitignored `data/`, and the tracked `labels.csv` carries none. | `tests/test_label_sample.py::test_labels_csv_has_no_text_column` — the tracked answer key has columns `review_id, theme` and no text; the text sheet's path matches the gitignored `data/*` rule. |
| For all review ids, the held-out fold is `sha256(review_id) % 5`, identical across runs. | `tests/test_split.py::test_fold_stable_across_runs` — the fold computed twice for a set of ids is identical; a random split would drift. |
| For all modules outside `classify/eval/` (sql, pipeline, and — when they exist — `classify/rules*`, `classify/llm*`, models), none reads `labels.csv`. | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval` — a grep of those surfaces for the answer-key path returns nothing. |
| For all label files, an absent or header-only `labels.csv` yields zero eval rows and never raises. | `tests/test_labels.py::test_absent_labels_is_zero_rows` — the reader on a missing file and on a header-only file returns an empty set, no exception. |

## Pinned decisions (do not re-litigate)

- **The seven-label set is defined once, as data, and membership is a check —
  never a coercion.** `classify/labels.py` holds the exact seven canonical
  strings (the five §5 themes, `positive`, `unclassified`); the labels reader
  refuses a row whose theme is not in the set. *Rejected: a free-text theme
  column, or coercing an unknown value to a default — either admits an eighth
  label through the back door (CLAUDE.md, "a value outside the set is impossible
  by construction, not coerced").* Satisfies the closed-set invariant.
- **`review_id = "{source}:{external_id}"`, derived in Python — no SQL change.**
  `stg_reviews` keys on `(source, external_id)` and has no id column; `classify`
  derives the stable id string from that pair. *Rejected: adding a `review_id`
  column to `stg_reviews`, which is a Phase 1 SQL change and therefore its own
  fix PR (CLAUDE.md → Git workflow), not 5a's to make.* Satisfies the
  stable-id invariant and keeps the eval split a pure function of the id.
- **`make label-sample N=<n>` writes a text-carrying sheet to gitignored
  `data/`; the tracked answer key carries no text.** The sheet is
  `review_id, source_url, text` at `data/label_sample.csv` (matched by the
  gitignored `data/*` rule); `classify/eval/labels.csv` is `review_id, theme`,
  tracked, text-free, and ships header-only. Reviews are drawn by
  `sha256(review_id)` order, capped at the corpus size; the text is read from
  `stg_reviews` in the built warehouse, so a missing warehouse writes a
  header-only sheet and says so. *Rejected: committing the text sheet, which
  would track review bodies and force the unwritten personal-data excerpt rule
  now (BACKLOG "Health details arrive in review bodies").* Satisfies the
  text-free-answer-key and sheet-determinism invariants.
- **The answer key's grain is one row per review × theme.** A review carrying K
  hand-assigned themes is K rows; a review with none is one `positive` or
  `unclassified` row — the grain SPEC.md settled at Beat 2 and the shape the 5b
  scorer joins to `classified_reviews`. *Rejected: one packed multi-value labels
  cell, which would need parsing on every read and would not mirror the mart
  grain.* Satisfies the closed-set invariant at the file level.
- **The held-out split is `sha256(review_id) % 5`, one pinned fold held out,
  never random.** `classify/split.py::fold(review_id)` is a pure function; the
  held-out fold index is a pinned constant (four folds tune in 5b, one gates in
  6). *Rejected: `random.shuffle` or a stored split file — either breaks
  reproducibility across machines and runs.* Satisfies the deterministic-split
  invariant (labels-isolation adaptation, `docs/PLAN.md`:64).
- **`classify/eval/labels.csv` is read only by `classify/eval/`.** One reader
  (`classify/eval/labels_io.py`) validates each row against the closed set and
  returns an empty result for an absent or header-only file; a grep pins that no
  other surface reads the path. *Rejected: letting `rules.py` or `llm.py` read
  the labels to "help decide" — that is the exact leakage the wall exists to
  stop.* Satisfies the labels-isolation and graceful-small/absent invariants.

## Scope (files)

- `classify/__init__.py` — new package.
- `classify/labels.py` — the seven-label closed set; `review_id(source, external_id)`.
- `classify/split.py` — `fold(review_id)` = `sha256(review_id) % 5`; the pinned held-out fold.
- `classify/eval/__init__.py` — new package.
- `classify/eval/labels_io.py` — the one reader of `labels.csv`; closed-set validation; empty on absent/header-only.
- `classify/eval/labels.csv` — new tracked file, header row only (`review_id,theme`) at first (no fabricated labels before a human labels).
- `pipeline/label_sample.py` — the sampler: reads `stg_reviews`, writes the gitignored sheet.
- `pipeline/cli.py`, `pipeline/__main__.py` — the `label-sample` subcommand (validates N, derives the fixed output path).
- `Makefile` — the `label-sample` target (and `make help`).
- `tests/test_labels.py`, `tests/test_split.py`, `tests/test_label_sample.py`, `tests/test_labels_isolation.py` — new (closed set + reader, split determinism, sampler determinism + text-free wall + N validation, the isolation grep).
- `tests/pins.py` — the held-out fold index, the fold of a pinned id, the sample-order first ids, the corpus review-id count.
- `DECISIONS.md` — Phase 5a entry.
- `BACKLOG.md` — the real-labels-are-offline row opened; the 5b review×theme code-invariant row noted (already deferred from row 20).
- `CLAUDE.md` — Current status; Commands (`label-sample`); Repo map (`classify/`); BACKLOG count.
- this spec — the "Delivered" paragraph appended at exit.

Freeze: none

(The synthetic fixture is read, not re-frozen; no `fixtures/` bytes change.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 5a entry: the 5a/5b split realized; `review_id` derived in Python (not an `stg_reviews` column); labels.csv ships header-only
- [ ] `BACKLOG.md` — opened: "The real 300–500 eval labels are human offline work, not yet in `labels.csv`" (trigger: 5b/6 needs a graded set); noted: the review×theme code invariant lands in 5b (BACKLOG row 20 already carries this)
- [ ] `CLAUDE.md` — Current status; Commands (`label-sample`); Repo map (`classify/`, the wall); BACKLOG count
- [ ] BACKING — none (5a populates no BACKING row; it is the wall the Phase 6 eval gate writes B2.4 from, and the labels B2.2/B2.5 rest on — those rows stay Pending)
- [ ] SPEC — none (no chart or beat changes; the Beat 2 grain was settled in Phase 0b)
- [ ] README — none (the README is a Phase 9 deliverable; it does not exist yet)
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

The one new target, `make label-sample N=<n>`, takes a variable (`N`); it
deletes nothing, calls no paid API and touches no network (it reads
`stg_reviews` from the built DuckDB file and writes one gitignored sheet), so it
needs no `confirm` gate. `N` reaches Python single-quoted and unexported
(`$(call _Q,$(value N))`, the settled shape); Python validates it is a positive
integer and refuses otherwise. The output path is the fixed
`data/label_sample.csv`, derived in code — never built from `N` — so `N` cannot
escape a directory or inject a path.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `label-sample N=` | refuses — `N` is not a positive integer | refuses — not an integer; and the path is fixed, not built from `N` | refuses — not an integer; the value reaches Python single-quoted, never a shell | the value is read but still validated as a positive integer in Python; a non-integer env value refuses | n/a — `label-sample` is not goal-gated (no delete, no network); `N` is a variable, validated in Python | `tests/test_label_sample.py::test_n_rejects_empty_path_and_metachar_and_env` |

- **No secret, no network, no delete.** The sampler reads the local warehouse
  and writes one gitignored file; there is no key, no fetch, and nothing is
  removed. Run twice on one warehouse, the sheet is byte-identical (no clock, no
  random); run against a missing warehouse, it writes a header-only sheet and
  says so — never a fabricated row.
- **No review text on a tracked path.** The sheet with text is gitignored by the
  `data/*` rule; the tracked `labels.csv` is `review_id, theme` with no text
  column, pinned by `test_labels_csv_has_no_text_column`. The brand never enters
  either: `review_id` is a source slug plus an external id, not an address.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `classify/**`, `pipeline/**`, `Makefile`,
  `tests/`): the label set is a closed list checked, not coerced; `review_id`
  needs no SQL change; the sampler and split are pure functions of the id (no
  clock, no random); the answer key carries no text; the wall holds.
- **security-reviewer** (not triggered — no CI, `.env`, scraper, model call,
  Snowflake, weekly commit, `.claude/hooks/`, settings, or destructive target
  is touched; `label-sample` reads locally and writes a gitignored file. If the
  reviewer disagrees on the `N`-variable surface, run it — the range is the
  architect's call).
- **functionality-tester** (triggered — same surface as code-reviewer): the
  DONE command (`make test`), the sheet-determinism and N-validation pins, the
  text-free wall, the split-stability pins, the absent/small-labels path, and
  the isolation grep.
- **study-editor** (triggered — `CLAUDE.md` prose changes): neutrality of the
  Current-status and Repo-map sentences; no company named.
- **coherence-auditor** at exit: no stale sentence implying the classifier
  reads its own answer key; the 5a/5b split reads as realized, not promised; the
  Beat 2 grain in SPEC still matches the labels.csv grain; B2.2/B2.4/B2.5 still
  read Pending.
- Stack risk (first hour; STOP and report before any workaround; findings →
  DECISIONS → Gotchas): whether `hashlib.sha256` over a UTF-8 `review_id` gives
  the same fold on macOS and Linux (it must — pin the fold of a known id); that
  `make`'s `$(value N)` quoting matches the Phase 3a `_Q` shape exactly; that
  reading `stg_reviews` when the warehouse is absent degrades to a header-only
  sheet rather than raising.

## Out of scope (deferred, recorded)

- **`rules.yaml` + `classify/rules.py` and per-theme precision** — Phase 5b
  (`docs/PLAN.md`:240). 5a writes no rule and reports no precision; there is no
  `make classify-eval` yet.
- **The model call, the cache, the held-out gate, and the `classifier_quality`
  mart (B2.4)** — Phase 6 (`docs/PLAN.md`:241). 5a builds the split the gate
  will use; it does not score.
- **The `classified_reviews` mart and the review×theme code invariant** — Phase
  5b (BACKLOG row 20; the grain is settled in SPEC, the code lands in 5b).
- **The real 300–500 hand labels** — human offline work between 5a and 5b
  (BACKLOG, opened here). 5a ships `labels.csv` header-only and behaves sanely
  until a person fills it.
- **Paraphrased seed examples for the taxonomy (B2.1)** — Documented prose for a
  later phase (5b or 9); 5a defines the theme set as code, not the examples.
