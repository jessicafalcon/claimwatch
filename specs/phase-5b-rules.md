# Phase 5b — The rules layer (PROPOSED)

Contract for the `phase-5b-rules` branch. Source: PROJECT_BRIEF.md §9 Phase 5
("Hand labels + rules layer"), split into 5a/5b per `docs/PLAN.md` §5 ("5b —
Rules layer": `rules.yaml` + `classify/rules.py`; per-theme precision on the
tuning folds; share decided by rules reported; no model). Depends on Phase 5a
merged (PR #10).

**Status: APPROVED 2026-09-04 — in progress.** One dependency moves from
transitive to direct: `pyyaml` — pre-approved for Phase 2 in CLAUDE.md →
Conventions ("pyyaml, httpx (2)"), first actually used here to read `rules.yaml`.
No other new dependency; no `anthropic` (the model is Phase 6). The allowlist is
in CLAUDE.md → Conventions.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

## Why

Beat 2 shows the share of negative reviews in each of five themes (SPEC.md
B2.2, B2.4, B2.5). 5a built the trust foundation — the closed seven-label set, a
stable `review_id`, the held-out split, and the wall around the hand-labeled
answer key — but wrote no rule and read no review. 5b is the first thing that
*reads a review and decides what it is about*: a layer of hand-written patterns
that catches the clear cases, so that when the model arrives in Phase 6 it sees
only what the rules could not decide (CLAUDE.md → Deterministic first;
architecture diagram, "rules.yaml decides the clear cases → the model sees only
the rest").

This is 5b and not 6 because the rules are deterministic and cost nothing to
run: plain pattern-matching in `rules.yaml` and Python, gradable today against
the fixture's own ground truth, with no API key and no model reply to distrust.
Splitting keeps each phase under six done-when items and lets the rules be
tuned and measured before a single model call is written.

*What precision is, and why the tuning folds only.* Precision for a theme is:
of the reviews the rules labeled with that theme, what fraction the hand labels
agree with — how often the rule is right when it fires. We measure it only on
the four **tuning folds** (`sha256(review_id) % 5 ≠ 4`), the reviews 5b is
allowed to look at while the patterns are written. The fifth fold is held out,
untouched, for Phase 6's gate: if the rules were tuned against it, its later
score would be a lie (the same reason a teacher grades on questions the student
never saw — 5a, `docs/PLAN.md` §4 decision 4). Recall — how many true cases each
theme catches — is Phase 6's `classifier_quality` (B2.4), measured on the held-
out fold; 5b reports precision and the share the rules could decide, not recall.

## The central constraint

**The rules decide from the review and the pattern file alone, never from the
answer key, and the held-out fold stays untouched.** `classify/rules.py` reads a
review's text and `classify/rules.yaml`; it never reads `classify/eval/labels.csv`
— that read stays inside `classify/eval/` (the 5a wall, now covering `rules*`).
Every label a rule emits is one of the seven closed labels; a review no theme
rule matches becomes exactly one `unclassified` row, never an eighth label.
Running the rules twice on the same corpus yields byte-identical rows (no clock,
no random). Precision is measured on the four tuning folds only; the held-out
fold's labels are never read by `make classify-eval`. Pattern-matching lives in
`rules.yaml` and Python and nowhere in SQL — the portability contract.

## DONE command

```
make classify-eval
```

- `make classify-eval` — builds the synthetic corpus, runs the rules over its
  `stg_reviews`, and prints per-theme precision on the four tuning folds plus the
  share of reviews the rules decided (vs. left `unclassified`). `make test` pins
  those numbers and the invariants below: the closed set holds at load, the
  rules are deterministic and review×theme-grained, the held-out fold is never
  read, and no module outside `classify/eval/` reads the answer key.

## Done-when

1. **`classify/rules.yaml` + `classify/rules.py`: labels come only from the
   closed seven, checked at load.** One pattern group per emitting label (the
   five §5 themes and `positive`); a group keyed by a label outside
   `classify.labels.LABEL_SET` refuses the load, naming it — never an eighth
   label. *Evidence: row 1.*
2. **The rules are deterministic, idempotent and review×theme-grained.** For one
   corpus the rules emit identical `(review_id, theme)` rows in identical
   (`review_id`, `theme`) order on every run (no clock, no random, no dict-order
   leak); a review matching K theme groups is K rows; a review matching none is
   exactly one `unclassified` row. *Evidence: row 2.*
3. **`make classify-eval` prints per-theme precision on the tuning folds and the
   decided share, matching pins.** Precision per theme = |rules said T ∧ hand
   says T| / |rules said T| over tuning-fold reviews; the decided share is the
   fraction of reviews the rules put in any theme or `positive`. Both are pinned
   in `tests/pins.py`. *Evidence: row 3.*
4. **The held-out fold is untouched.** `classify-eval` computes precision over
   `fold(review_id) ≠ HELDOUT_FOLD` only; changing or removing the held-out
   fold's rows in `labels.csv` does not change any printed number. *Evidence: row 4.*
5. **The wall still holds: the rules never read the answer key.** No module
   outside `classify/eval/` reads `labels.csv` — `classify/rules.py` reads
   reviews and `rules.yaml` only; the isolation grep now also covers
   `classify/rules*`. *Evidence: row 5.*
6. **Pattern-matching stays out of SQL; the answer key holds the synthetic
   ground truth.** 5b adds no `sql/marts/` file and no clause the SQL lint
   rejects; `classify/eval/labels.csv` is populated with the fabricated corpus's
   hand labels (`review_id, theme`, review×theme grain, text-free), so
   `classify-eval` has something to grade — the real 300–500 labels stay offline
   (BACKLOG). *Evidence: row 6.*

(6 items. Each is a contract the code can falsify.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_rules.py::test_labels_are_the_closed_seven`, `::test_out_of_set_rule_key_refuses_load` |
| 2 | `tests/test_rules.py::test_rules_are_idempotent`, `::test_review_times_theme_grain`, `::test_no_match_is_one_unclassified_row` |
| 3 | `tests/test_classify_eval.py::test_per_theme_precision_matches_pins`, `::test_decided_share_matches_pins` / `make classify-eval` prints "precision" per theme |
| 4 | `tests/test_classify_eval.py::test_heldout_fold_never_read`, `::test_precision_is_tuning_folds_only` |
| 5 | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval` (now covering `classify/rules*`) |
| 6 | `tests/test_rules.py::test_no_new_mart_and_sql_lint_clean`, `tests/test_classify_eval.py::test_labels_csv_covers_the_synthetic_corpus`, `tests/test_labels.py::test_labels_csv_rows_are_closed_set_and_text_free` |

## Invariants (REQUIRED)

Properties, not mechanisms — written before any pinned decision names how the
code works.

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all labels a rule emits, the label is one of the seven closed labels; a rules.yaml group keyed by anything else refuses the load. | `tests/test_rules.py::test_out_of_set_rule_key_refuses_load` — a `rules.yaml` with a group keyed `document-loop-ish`; the loader refuses rather than admitting an eighth label. |
| For all corpora, the rules emit identical rows in identical order on re-run — a pure function of the reviews and `rules.yaml`. | `tests/test_rules.py::test_rules_are_idempotent` — the classifier run twice over one corpus yields byte-equal `(review_id, theme)` rows; a dict-order or clock leak would drift. |
| For all reviews, a review matching K theme groups produces K theme rows and a review matching none produces exactly one `unclassified` row. | `tests/test_rules.py::test_review_times_theme_grain` — a review written to match two themes yields two rows; one written to match none yields one `unclassified` row. |
| For all review ids in the held-out fold, `classify-eval`'s printed numbers do not depend on their labels. | `tests/test_classify_eval.py::test_heldout_fold_never_read` — mutating the held-out fold's rows in a temp `labels.csv` leaves every printed number unchanged. |
| For all modules outside `classify/eval/` (sql, pipeline, `classify/rules*`, and — when they exist — `classify/llm*`, models), none reads `labels.csv`. | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval` — a grep of those surfaces (now including `classify/rules*`) for the answer-key path returns nothing. |
| For all classification logic, the pattern-matching lives in `rules.yaml` and Python, never in SQL; 5b adds no mart. | `tests/test_rules.py::test_no_new_mart_and_sql_lint_clean` — `sql/marts/` gains no file and the SQL lint denylist finds nothing new. |

## Pinned decisions (do not re-litigate)

- **`classify/rules.yaml` is the only pattern home; one group per emitting label,
  membership checked at load.** The file maps each of the five §5 themes and
  `positive` to a list of case-insensitive patterns; `classify/rules.py` loads it
  with `yaml.safe_load`, refuses a group keyed by a label outside
  `LABEL_SET`, compiles the patterns once, and applies them. *Rejected: patterns
  in Python literals (a rule change becomes a code change) or in SQL (breaks the
  portability contract — pattern-matching must stay out of SQL).* Satisfies the
  closed-set and pattern-not-in-SQL invariants.
- **Grain is one row per review × theme; `unclassified` is the single fallback.**
  A review is scored against every theme group; each match is one
  `(review_id, theme)` row. A review no theme matches becomes exactly one
  `unclassified` row (the model decides it in Phase 6); a `positive` match is a
  row like any theme. *Rejected: a packed multi-label cell (does not mirror the
  Beat 2 mart grain SPEC.md settled) and defaulting no-match to `positive` (that
  asserts praise where there is only silence).* Satisfies the grain invariant.
- **The classifier is a pure function of the reviews and `rules.yaml`; output is
  sorted.** Patterns are applied in file order; the emitted rows are sorted by
  `(review_id, theme)` before use; no clock, no `random`, no reliance on dict or
  set iteration order. *Rejected: emitting in scan order (drifts with corpus
  order) or caching to disk (state the run does not need).* Satisfies the
  determinism invariant.
- **`make classify-eval` reads `stg_reviews` from the synthetic warehouse and
  grades on the tuning folds only.** The recipe rebuilds the synthetic corpus,
  then the `classify-eval` subcommand reads `stg_reviews`, runs the rules, and
  scores against `classify/eval/labels.csv` for reviews with
  `fold(review_id) ≠ HELDOUT_FOLD`. It takes no user variable (synthetic is
  fixed for 5b; real rows are Phase 7). *Rejected: reading `fixtures/synthetic/
  reviews.csv` directly (skips the staging dedup, 40 → 39) and exposing `ROWS=`
  now (real-row eval needs real labels, which are offline).* Satisfies the
  held-out and precision invariants.
- **The synthetic corpus's ground truth is committed to `classify/eval/labels.csv`.**
  The fabricated reviews were hand-written to cover all seven labels; their hand
  labels are the answer key `classify-eval` grades against — fake reviews, no
  personal data, no brand, `review_id, theme`, text-free, review×theme grain. The
  real 300–500 labels stay offline human work (BACKLOG, opened in 5a); their ids
  differ from the synthetic ones, so the two never collide. *Rejected: a separate
  synthetic key file under `fixtures/` (two answer keys, one reader forked, and a
  fixture re-freeze) — the one answer key already has this exact shape.* Satisfies
  the "build on the synthetic fixture first" rule and keeps one reader.
- **5b populates no BACKING row; B2.2/B2.4/B2.5 stay Pending.** The per-theme
  precision and decided share are developer-facing tuning numbers a person reads
  at the command line, not a displayed study panel, and 5b writes no mart. B2.4
  (`classifier_quality`) is the held-out precision *and recall* the Phase 6 gate
  writes as a mart; B2.2/B2.5 are the Phase 7 theme-share marts. *Rejected:
  flipping B2.4 to Measured now — that is the held-out gate's number, and showing
  a tuning-fold precision as the study's quality figure would overstate it.*
  Satisfies the evidence contract (work maps to a row or is out of scope; a
  number a reader sees wears a tag — 5b's printout is neither a study number nor
  tagged).

## Scope (files)

- `classify/rules.yaml` — new; one pattern group per emitting label (5 themes + `positive`).
- `classify/rules.py` — new; load + closed-set check + compile + apply → `(review_id, theme)` rows.
- `classify/eval/precision.py` — new; per-theme precision + decided share on the tuning folds, reading labels through `classify/eval/labels_io.py`.
- `classify/eval/labels.csv` — populated with the synthetic corpus ground truth (was header-only from 5a).
- `pipeline/cli.py`, `pipeline/__main__.py` — the `classify-eval` subcommand (no user variable; reads the synthetic warehouse, prints the report).
- `Makefile` — the `classify-eval` target (rebuild synthetic, then eval) and `make help`.
- `tests/test_rules.py`, `tests/test_classify_eval.py` — new (closed set + load refusal, determinism, grain, precision/decided-share vs pins, held-out untouched).
- `tests/test_labels_isolation.py` — extend the grep to cover `classify/rules*`.
- `tests/test_labels.py` — a row-level check that `labels.csv` rows are closed-set and text-free (the file is no longer header-only).
- `tests/pins.py` — per-theme precision, the decided share, the tuning/held-out review counts used by the eval.
- `pyproject.toml`, `uv.lock` — `pyyaml` moved to `[project] dependencies` (pre-approved, allowlist).
- `DECISIONS.md` — Phase 5b entry.
- `BACKLOG.md` — the review×theme code-invariant row (row 20) closed; the real-labels row left open; rows opened.
- `CLAUDE.md` — Current status; Commands (`classify-eval`); Repo map (`rules.yaml`, `rules.py`, the eval scorer); BACKLOG count.
- this spec — the "Delivered" paragraph appended at exit.

Freeze: none

(`fixtures/` bytes do not change — the synthetic labels live in
`classify/eval/labels.csv`, not under `fixtures/`.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 5b entry: rules-only classifier; grain and `unclassified` fallback; synthetic ground truth committed to `labels.csv`; precision on tuning folds only; no BACKING row (B2.4 is Phase 6's held-out gate); `pyyaml` made a direct dependency
- [ ] `BACKLOG.md` — closed: row 20 (the review×theme code invariant lands in 5b); left open: the real 300–500 hand labels; opened: any tuning finding deferred
- [ ] `CLAUDE.md` — Current status; Commands (`classify-eval`); Repo map (`classify/rules.yaml`, `classify/rules.py`, `classify/eval/precision.py`); BACKLOG count
- [ ] BACKING — none (5b populates no BACKING row; per-theme precision is a tuning number, not a displayed study figure; B2.2/B2.4/B2.5 stay Pending)
- [ ] SPEC — none (no chart or beat changes; the Beat 2 grain was settled in Phase 0b)
- [ ] README — none (the README is a Phase 9 deliverable; it does not exist yet)
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new target takes a variable, deletes, calls a paid API, or touches the
network. `make classify-eval` takes no user variable (the corpus is the fixed
synthetic input for 5b); it reads the local synthetic warehouse and prints a
report, deleting nothing, fetching nothing, calling no API. The `rebuild
--rows=synthetic` it invokes is a fixed, code-authored argument, not a value from
the environment or the command line, and rebuild carries its own Phase 1/3a
guards. `classify/rules.py` is a guard at a foreign input (scraped review text):
its accepted output is the closed seven labels, and any review it cannot place in
a theme becomes `unclassified` (CLAUDE.md → Before reporting DONE, item 8) —
pinned by `tests/test_rules.py::test_no_match_is_one_unclassified_row`.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| (none — `classify-eval` takes no variable) | — | — | — | — | — | — |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `classify/**` incl. `rules.yaml`, `pipeline/**`,
  `Makefile`, `tests/`): the label set is checked at load, not coerced; the rules
  are a pure function (no clock, no random, sorted output); the grain is one row
  per review × theme with an `unclassified` fallback; pattern-matching is in
  `rules.yaml`/Python, never SQL; the wall holds (`rules.py` reads no answer key).
- **security-reviewer** (not triggered — no CI, `.env`, scraper, model call
  (`classify/llm.py` is Phase 6), Snowflake, weekly commit, `.claude/hooks/`,
  settings, or destructive target is touched; `classify-eval` reads locally and
  writes nothing tracked). `yaml.safe_load`, never `load`, is a code-reviewer
  check here.
- **functionality-tester** (triggered — same surface): the DONE command
  (`make classify-eval`), the precision/decided-share pins, the determinism and
  grain pins, the held-out-untouched pins, the load refusal on an out-of-set
  group, and the isolation grep.
- **study-editor** (triggered — `CLAUDE.md` prose changes): neutrality of the
  Current-status and Repo-map sentences; no company named; the rules described as
  "a rule reads each review and tags what it's about", not a banned word.
- **coherence-auditor** at exit: no stale sentence implying the rules read their
  own answer key; the 5a wall still described as holding (now over `rules*`);
  B2.2/B2.4/B2.5 still read Pending; the architecture diagram's "rules.yaml
  decides the clear cases" now matches built code.
- Stack risk (first hour; STOP and report before any workaround; findings →
  DECISIONS → Gotchas): that `yaml.safe_load` gives the same structure on macOS
  and Linux (it must); that regex/keyword matching over UTF-8 French text
  (accents) is deterministic and case-insensitive as intended; that the tuning-
  fold filter uses the same `sha256(review_id) % 5` as 5a (import `classify.split`,
  do not re-derive); that per-theme precision is reproducible byte-for-byte
  across machines.

## Out of scope (deferred, recorded)

- **The model call, the cache, the held-out gate, and the `classifier_quality`
  mart (B2.4)** — Phase 6 (`docs/PLAN.md`:241). 5b writes the rules the model
  falls back from; it does not call the model or grade on the held-out fold.
- **The `theme_share_by_month` / `theme_share_by_segment` marts (B2.2, B2.5) and
  a `classified_reviews` mart** — Phase 7 (`docs/PLAN.md`:242), when the classified
  rows feed a displayed number. 5b keeps the rules output in Python; it writes no
  mart.
- **Rules run on real scraped rows** — Phase 7 needs the real hand labels to
  grade them; 5b proves the rules on the synthetic corpus (CLAUDE.md → "Build on
  the synthetic fixture first").
- **The real 300–500 hand labels** — human offline work (BACKLOG, opened in 5a).
  5b grades on the synthetic ground truth committed here.
- **Paraphrased public seed examples for the taxonomy (B2.1)** — Documented prose
  for a later phase (9); 5b defines patterns, not the examples.
