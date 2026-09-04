# Phase 6b — Held-out eval gate + the classifier_quality mart

Contract for the `phase-6b-eval-gate` branch. Source: PROJECT_BRIEF.md §9 Phase 6
("Model fallback + gate"), split into 6a/6b (the architect's call, prior
session): 6a shipped the model call site, the decision cache and the no-key
guarantee; 6b is the held-out eval gate and the `classifier_quality` mart (B2.4).
Depends on Phase 6a merged (PR #12).

**Status: APPROVED 2026-09-04 — DELIVERED 2026-09-04, PR open.** No new dependency:
`anthropic` already landed in 6a; the gate itself is offline (it scores
predictions against the hand answer key, no model call). The allowlist is in
CLAUDE.md → Conventions.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

## Why

Beat 2 shows the share of negative reviews in each of five themes. 5b built the
rules layer; 6a added the one model call site that reads what the rules could not
decide, and combined the two into a classification held in Python. But a
classifier the study leans on has to earn trust with a number of its own: how
often is each theme label right (precision), and how many of the true cases does
it catch (recall)? 6b measures exactly that — on reviews the classifier never saw
while it was built — and writes the one number this phase is allowed to show, the
`classifier_quality` mart (B2.4).

*What "held-out" means, and why the gate may only read one fold.* Some
hand-labeled reviews are hidden from the classifier while it is built and tuned,
then it is graded only on those hidden ones — a test with questions the student
never saw (`classify/split.py`, `sha256(review_id) % 5`). Four folds tune the
rules (5b); one, `HELDOUT_FOLD = 4`, is reserved for this gate. If the gate scored
any tuning fold, the score would flatter a classifier that had already seen those
answers. So the gate reads fold 4 alone, and fold 4 is never tuned against.

*What precision and recall are here (a first-appearance concept).* For one label
T on the held-out fold: `predicted` is the set of reviews the classifier gave T,
`actual` is the set the answer key marks T, and `hits` is their overlap.
Precision = `hits / predicted` (when the classifier says T, how often it is
right); recall = `hits / actual` (of the reviews that truly are T, how many it
caught). The overlap is the shared numerator of both. A denominator of zero means
the ratio is undefined, not zero — shown as blank, never faked.

*Why the mart is honest with no key.* With no `ANTHROPIC_API_KEY` the classifier
is rules-only, so it decides fewer reviews and recall is lower. The gate scores
that classifier truthfully — the mart reflects whatever ran, and the no-key run
still populates it (lower recall, some labels blank), rather than hiding the
number or inventing a with-key one. CI (no key) pins the rules-only figures; the
with-key figures vary with the model and are not pinned.

## The central constraint

**The gate scores the classifier on the held-out fold alone, never tunes against
it, and the `classifier_quality` mart is the one number this phase shows — tagged
Measured, reflecting truthfully whatever classifier ran.** Every review the gate
counts satisfies `is_heldout(review_id)`; the four tuning folds and 5b's tuning
report are never consulted by the gate. The answer key is read only inside
`classify/eval/` (now including the gate) — the classifier is never shown the
answers it is graded against. The mart's per-label figures are a deterministic
function of the classifier's predictions and the answer key: two rebuilds with no
key yield byte-identical mart rows, and no clock, no `source_url` and no
`captured_at` stand in for provenance a computed metric does not have. B2.2/B2.5
stay Pending (Phase 7); B2.4 is the only tag this phase flips.

## DONE command

```
make rebuild ROWS=synthetic && make idempotency-check ROWS=synthetic && make check-backing && make test
```

- `make rebuild ROWS=synthetic` (no key): builds the warehouse, runs the classify
  step rules-only, scores the held-out fold and populates `classifier_quality`,
  prints the classify summary and a one-line gate summary, exits 0. The mart's
  rules-only fold-4 figures are pinned (`tests/pins.py`).
- `make idempotency-check ROWS=synthetic`: rebuild twice, per-table counts
  identical (`classifier_quality`'s row count is constant — one row per scored
  label); green. The byte-identical *values* are pinned by a dedicated test (the
  count-diff alone cannot see value drift).
- `make check-backing`: B2.4 now reads **Measured**, names
  `sql/marts/classifier_quality.sql` (which now exists) and upstream source
  `` `classify/eval/labels.csv` ``, and is still cited by SPEC.md — every check ok.
- `make test`: pins the fold-4 per-label precision/recall/counts (rules-only), the
  null-when-denominator-zero semantics, the mart shape/tag/provenance, the
  value-idempotency across two rebuilds, the no-key honest population, and the
  wall (only `classify/eval/` reads the answer key, now including the gate).

## Done-when

1. **The held-out eval gate scores precision and recall per label on fold 4
   alone.** `classify/eval/gate.py` takes the classifier's `(review_id, label)`
   predictions and grades them against the hand answer key on `HELDOUT_FOLD`
   only: per label, `hits = |predicted ∩ actual|`, `precision = hits / predicted`,
   `recall = hits / actual`, each `None` when its denominator is 0. No tuning fold
   is consulted. *Evidence: row 1.*
2. **`classifier_quality` is a DDL-only mart populated by Python, one row per
   scored label, every figure tagged Measured; B2.4 flips Pending → Measured.**
   Its `.sql` creates the empty fixed-shape table in `build_derived`; the CLI
   classify step inserts the fold-4 scores. `make rebuild` writes it; B2.4 in
   BACKING reads Measured with source `` `classify/eval/labels.csv` ``. *Evidence:
   row 2.*
3. **The mart carries a computed metric's provenance, not a scraped row's, and no
   clock.** Columns `label, hits, predicted, actual, precision, recall,
   heldout_fold, answer_key, run_id, tag` — no `source_url`, no `captured_at`,
   no `now()`/`current_date`; the integer components are stored so `precision =
   hits / predicted` can be redone by hand. *Evidence: row 3.*
4. **The mart is deterministic and idempotent.** Two rebuilds with no key yield
   byte-identical `classifier_quality` rows (sorted by label); the row count is
   constant, so `idempotency-check`'s count-diff is stable. *Evidence: row 4.*
5. **The no-key run stays green and populates the mart truthfully.** With the key
   unset the classifier is rules-only, the gate scores those predictions (lower
   recall, some labels blank), the mart populates with the pinned rules-only
   figures, and no model is called to grade. *Evidence: row 5.*
6. **The wall holds: only `classify/eval/` reads the answer key, now including the
   gate.** `gate.py` reads `labels.csv` (via `labels_io`) inside the wall; the CLI
   passes predictions to the gate and gets scores back, reading no answer key. The
   classifier is never shown the answers it is graded against. *Evidence: row 6.*

(6 items. Each is a contract the code can falsify.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_gate.py::test_scores_heldout_fold_only`, `::test_precision_and_recall_formula`, `::test_null_when_denominator_is_zero`, `::test_a_crafted_disagreement_scores_below_one` |
| 2 | `tests/test_classifier_quality.py::test_mart_exists_empty_after_rebuild`, `::test_one_row_per_scored_label_all_measured`, `::test_rules_only_heldout_values_are_pinned` / `make check-backing` prints "ok" with B2.4 Measured / `make rebuild ROWS=synthetic` prints the gate summary |
| 3 | `tests/test_classifier_quality.py::test_mart_columns_are_the_computed_metric_shape`, `::test_components_reproduce_the_ratio`; `tests/test_sql_lint.py` (no clock in `sql/`) |
| 4 | `tests/test_classifier_quality.py::test_two_rebuilds_identical_mart_rows` / `make idempotency-check ROWS=synthetic` green |
| 5 | `tests/test_no_key.py::test_no_key_mart_is_rules_only_and_populated`, `::test_no_key_scores_call_no_model` |
| 6 | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval`, `::test_the_gate_is_inside_the_wall`; `tests/test_gate.py::test_gate_takes_predictions_not_the_corpus` |

## Invariants (REQUIRED)

Properties, not mechanisms — written before any pinned decision names how the
code works.

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all gate scoring, only the held-out fold is read: every counted review satisfies `is_heldout(review_id)`, and no tuning-fold review or 5b tuning report is consulted. | `tests/test_gate.py::test_scores_heldout_fold_only` — predictions spanning all folds are scored; the denominators equal the fold-4-only counts, tuning-fold rows are ignored. |
| For all labels, `hits = |predicted ∩ actual|` on fold 4, `precision = hits/predicted`, `recall = hits/actual`, each `None` exactly when its denominator is 0. | `tests/test_gate.py::test_precision_and_recall_formula`, `::test_null_when_denominator_is_zero` — a crafted disagreement gives precision < 1 and recall < 1; a label with `predicted = 0` gives `None`, not `0`. |
| For all figures in `classifier_quality`, the tag is Measured and the provenance is a computed metric's (`answer_key`, `heldout_fold`, `run_id`) — never a `source_url`/`captured_at` it does not have, never a build clock. | `tests/test_classifier_quality.py::test_one_row_per_scored_label_all_measured`, `::test_mart_columns_are_the_computed_metric_shape` (asserts no `source_url`/`captured_at`); `tests/test_sql_lint.py` — the mart carries no address, no instant, no `now()`. |
| For all rebuilds, `classifier_quality` exists and its rows are a deterministic function of the classifier's predictions and the answer key — two rebuilds with no key are byte-identical. | `tests/test_classifier_quality.py::test_two_rebuilds_identical_mart_rows` — rebuild-then-classify twice with no key; the mart rows are equal. |
| For all runs with no API key, the mart populates truthfully from the rules-only classifier and no model is called to grade; the run is green. | `tests/test_no_key.py::test_no_key_mart_is_rules_only_and_populated`, `::test_no_key_scores_call_no_model` — with the key unset the mart holds the pinned rules-only figures and the Anthropic client is never constructed. |
| For all modules outside `classify/eval/`, none reads the answer key; the gate (inside `eval/`) reads it, and the CLI hands the gate predictions, not labels. | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval`, `::test_the_gate_is_inside_the_wall`; `tests/test_gate.py::test_gate_takes_predictions_not_the_corpus`. |

## Pinned decisions (do not re-litigate)

- **The gate scores the held-out fold alone (`HELDOUT_FOLD = 4`), precision and
  recall per label, in `classify/eval/gate.py`.** It reuses `split.is_heldout`,
  reads the answer key through `labels_io.read_labels`, and takes the classifier's
  predictions as input (a pure function of predictions and labels, like 5b's
  `precision.evaluate`). `hits = |predicted ∩ actual|` is the shared numerator;
  `precision = hits/predicted`, `recall = hits/actual`, `None` on a zero
  denominator. *Rejected: scoring every fold (leaks the tuning folds into the
  study number and lets the gate be tuned against — the split's whole purpose);
  a separate recall-only pass (two scorers drift).* Satisfies the held-out and
  formula invariants.
- **`classifier_quality` is a DDL-only mart populated by Python — the first
  Python-fed mart.** Its `.sql` is `create or replace table classifier_quality
  (<columns>)` — the fixed shape, no `select` — run in `build_derived` like every
  mart, so the table always exists after a rebuild (portability: no pattern/model
  logic in SQL). The CLI classify step (6a's placement, where the model and cache
  already live) scores fold 4 and inserts the per-label rows. *Rejected: a
  `create … as select` mart (there is no SQL source table — the metric is computed
  in Python against the answer key, which SQL may not read); populating inside
  `rebuild()` (forces a return-type change across ~50 callers and adds no
  idempotency signal, since the mart's row count is constant either way).*
  Satisfies the portability contract and the deterministic-mart invariant.
- **The mart carries a computed metric's provenance, not a scraped row's.**
  Columns: `label, hits, predicted, actual, precision, recall, heldout_fold (= 4),
  answer_key (= 'classify/eval/labels.csv'), run_id, tag (= 'Measured')`. No
  `source_url`, no `captured_at` — a computed quality metric has no address and no
  capture instant, and a build timestamp would be a clock on the data path
  (CLAUDE.md → Deterministic first). `hits`, `predicted`, `actual` are stored so a
  reader can redo `precision = hits / predicted` by hand (brief §2.1); `precision`
  and `recall` are `double`, `None` when undefined. *Rejected: faking
  `source_url`/`captured_at` (dishonest provenance) or a `now()`/`current_date`
  stamp (the banned clock).* Satisfies the provenance and no-clock invariants.
- **Every `classifier_quality` figure is Measured; B2.4 flips Pending → Measured,
  upstream source `` `classify/eval/labels.csv` ``.** The numbers are a direct
  measurement of the real classifier against the real hand labels. B2.2/B2.5 stay
  Pending (Phase 7 — theme-share marts). *Rejected: Pending (a number is now
  shown; it must wear a real tag), or Modeled (there is no model or assumption —
  it is a measurement against hand labels).* Satisfies the evidence contract (work
  maps to a row) and the Measured-tag invariant.
- **The mart reflects whatever classifier ran; the no-key run populates it
  rules-only and stays green.** With no key `classify_all` is rules-only, so recall
  is lower and some labels are blank; the gate scores those predictions and never
  calls the model to grade (grading is offline — it compares stored predictions to
  the answer key). *Rejected: skipping the mart with no key (hides the honest
  degraded number) or a fabricated with-key figure (never fake).* Satisfies the
  no-key invariant.
- **The wall holds, now including the gate; the CLI passes predictions, not
  labels.** `gate.py` lives in `classify/eval/` and reads the answer key there; the
  CLI calls `score_heldout(predictions)` and gets per-label scores back, reading no
  `labels.csv`. `build.py`'s inserter takes the scored rows and a connection — it
  imports no answer-key reader. *Rejected: the CLI or `build.py` reading
  `labels.csv` (breaks the wall — a classifier that can see its own answers makes
  its scores a lie).* Satisfies the wall invariant.

## Scope (files)

- `sql/marts/classifier_quality.sql` — new; DDL only (`create or replace table
  classifier_quality (label, hits, predicted, actual, precision, recall,
  heldout_fold, answer_key, run_id, tag)`). Header comment names the grain, the
  provenance columns and B2.4 (SQL conventions).
- `classify/eval/gate.py` — new; `score_heldout(predictions, *, labels=None) ->
  tuple[LabelScore, …]` — per scored label, `hits/predicted/actual` and
  `precision/recall` (`None` on a zero denominator) on `HELDOUT_FOLD` only. Reads
  the answer key via `labels_io` (inside the wall). `SCORED_LABELS` reused from /
  aligned with `precision.py` (the five themes + `positive`).
- `pipeline/build.py` — add `write_classifier_quality(conn, scored_rows, run_id)`:
  a plain parameterized insert into the table its `.sql` created (no `classify`
  import, no answer-key reader — it takes scored rows in). No change to
  `rebuild()`'s signature or return.
- `pipeline/cli.py` — the 6a classify step (`_classify_and_print`) also scores
  fold 4 via `classify.eval.gate.score_heldout` and calls
  `build.write_classifier_quality`, then prints a one-line gate summary. It passes
  the gate the classifier's predictions, never the answer key; `run_id` for the
  mart is the rebuild input name (byte-stable across reruns of the same input).
- `tests/test_gate.py` — new; fold-4-only scoring, the precision/recall formula,
  null-on-zero-denominator, a crafted disagreement scoring below one, the gate
  takes predictions not the corpus.
- `tests/test_classifier_quality.py` — new; mart exists after rebuild, one row per
  scored label, every figure Measured, the computed-metric column shape (no
  `source_url`/`captured_at`), the components reproduce the ratio, two rebuilds
  identical.
- `tests/test_no_key.py` — add `test_no_key_mart_is_rules_only_and_populated`,
  `test_no_key_scores_call_no_model`.
- `tests/test_labels_isolation.py` — add `test_the_gate_is_inside_the_wall` (the
  gate is excluded from the sweep and carries a reader token, mirroring
  `test_the_one_reader_actually_reads_it`).
- `tests/pins.py` — the synthetic fold-4 per-label rules-only scores
  (`hits/predicted/actual`, precision/recall), the mart column set, `heldout_fold
  = 4`, the `answer_key` path, the tag.
- `BACKING.md` — B2.4 Pending → Measured; upstream source
  `` `classify/eval/labels.csv` ``.
- `SPEC.md` — B2.4 panel: drop the "(Pending until the eval gate writes its mart)"
  parenthetical now that the mart lands (a living-doc update reflecting reality —
  no chart or beat design changes; the panel, its tag intent and its B2.4 id are
  unchanged).
- `DECISIONS.md` — Phase 6b entry.
- `BACKLOG.md` — rows closed / opened; count refreshed.
- `CLAUDE.md` — Current status; Repo map (`classify/eval/gate.py`, the
  `classifier_quality` mart, `build.write_classifier_quality`); Commands (`rebuild`
  now writes the mart and prints the gate summary); the marts list gains
  `classifier_quality`; BACKLOG count.
- this spec — the "Delivered" paragraph appended at exit.

Freeze: none

(`fixtures/` bytes do not change; the synthetic answer key stays in
`classify/eval/labels.csv`.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 6b entry: the held-out gate (precision + recall on
  fold 4 only, in `classify/eval/gate.py`); `classifier_quality` as the first
  Python-fed, DDL-only mart populated by the CLI classify step (not `rebuild()`,
  to avoid a return-type change and because the row count gives no idempotency
  signal); the computed-metric provenance (no `source_url`/`captured_at`, no
  clock); B2.4 Pending → Measured with the answer key as upstream source
- [ ] `BACKLOG.md` — closed: the held-out gate / B2.4 row from 6a's "opened";
  opened: the with-key eval numbers and real-corpus grading (Phase 7); count
  refreshed
- [ ] `CLAUDE.md` — Current status; Repo map (`classify/eval/gate.py`,
  `classifier_quality`, `write_classifier_quality`); Commands (`rebuild` writes the
  mart + gate summary); marts list; BACKLOG count
- [ ] `BACKING.md` — B2.4 Pending → Measured, source `` `classify/eval/labels.csv` ``
- [ ] `SPEC.md` — B2.4 panel parenthetical dropped (living-doc, not a design
  change)
- [ ] README — none (the README is a Phase 9 deliverable; it does not exist yet)
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

None — no new `make` target takes a variable, deletes, calls a paid API, or
touches the network. The gate is **offline**: it grades stored predictions against
the hand answer key with no model call. The model-call path is unchanged from 6a
(`make rebuild`'s classify step calls the paid API only when a key is present,
only for rules-`unclassified` reviews not already cached, from `classify/llm.py`
alone — developer-run, never an agent's). `rebuild`'s `TARGET`/`ROWS` remain the
Phase 3a closed-set guards. The mart insert is a parameterized insert of computed
scores — no user input reaches it.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| (no new target/variable; `rebuild`'s `TARGET`/`ROWS` are the Phase 3a closed-set guards) | resolve_choice → default | refused | refused | refused (not in set) | n/a (no confirm goal) | `tests/test_cli.py` (Phase 3a) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `classify/**`, `sql/**`, `pipeline/**`,
  `tests/`): the gate scores fold 4 only and is a pure function of predictions and
  labels; the formula is right and null-on-zero-denominator is honest; the mart is
  DDL fed by Python (no pattern/model logic in SQL); the provenance is a computed
  metric's (no faked address/instant, no clock); every figure is Measured; the
  mart is deterministic and sorted; the wall holds.
- **security-reviewer** (not triggered — no sensitive surface in the range:
  `classify/llm.py`, `pipeline/warehouse.py`, `ingest/**`, `.github/`, `.env*`,
  `.claude/`, and every destructive/paid/fetch target are untouched. The gate is
  offline; the 6a model path is not modified).
- **functionality-tester** (triggered — same surface as code-reviewer): the DONE
  chain (rebuild + idempotency-check + check-backing + test, no key), the fold-4
  scoring and formula pins, the crafted-disagreement pin, the mart shape/tag pins,
  the value-idempotency across two rebuilds, and the no-key honest population with
  no model call.
- **study-editor** (triggered — `BACKING.md`, `SPEC.md`, `CLAUDE.md` prose
  changes): the B2.4 flip reads Measured and neutral; no company named; precision
  and recall described in plain words next to the number; the dropped SPEC
  parenthetical does not change the panel's meaning.
- **coherence-auditor** at exit: no stale sentence saying B2.4 is Pending or the
  gate is unbuilt; the five-contracts "the gate scores it on the eval set … and
  writes the scores to the `classifier_quality` mart, which the study displays"
  now matches built code; SPEC ↔ BACKING ↔ the new mart ↔ CLAUDE.md marts list
  reconcile; B2.2/B2.5 still read Pending.
- Stack risk (first hour; STOP and report before any workaround; findings →
  DECISIONS → Gotchas): that a DDL-only mart `.sql` runs cleanly through
  `build_derived`'s `run_sql_file` on DuckDB (a `create or replace table (…)` with
  no `select`); that `double` precision/recall values are byte-stable across
  reruns (identical integer operands → identical float, so the value-idempotency
  test holds); that on the synthetic corpus fold 4 (only 5 reviews) leaves several
  labels with a zero denominator — the pins record whatever is actually computed,
  including the `None`s, not a hoped-for shape.

## Out of scope (deferred, recorded)

- **The `theme_share_by_month` / `theme_share_by_segment` marts (B2.2, B2.5) and
  materializing `classified_reviews` as a mart** — Phase 7 (`docs/PLAN.md` row 7),
  when the classified rows feed a displayed share. 6b writes only
  `classifier_quality`.
- **Grading the classifier on the real scraped corpus** — Phase 7 needs the real
  300–500 hand labels; 6b grades the synthetic corpus (CLAUDE.md → "Build on the
  synthetic fixture first").
- **The with-key eval figures as pinned numbers** — the model varies, so the
  with-key run is developer-run and its figures are not pinned; only the rules-only
  (no-key) figures are pinned (BACKLOG, opened in 6a).
- **A read-only `make classify-gate` diagnostic** — rejected as surface the five
  parts do not need: the held-out grade is a real build output (it rides `make
  rebuild` and lands in the mart), unlike 5b's `make classify-eval`, which is a
  tuning-fold dev diagnostic. Reconsider only if a developer needs the held-out
  report without a full rebuild (BACKLOG if it comes up).

## Amendment A1 — grade over the reviews both classified and labeled (2026-09-04)

Round 1 (code-reviewer, functionality-tester) found that the gate graded the
classifier's predictions against the answer key for **every** rebuild input, but
the answer key covers only the synthetic corpus. So `make rebuild
ROWS=captured|samples` wrote a **Measured** `classifier_quality` mart grading a
real (or empty) corpus's predictions against synthetic labels — real and synthetic
review-ids never intersect, so every figure was a garbage `0.0`/`None` tagged
Measured. The invariant this restores:

**For all gate scoring, precision and recall are computed only over reviews that
are both classified and present in the answer key (on the held-out fold); a review
labeled but not classified — or classified but not labeled — is not graded, and an
input whose corpus the answer key does not cover writes no mart.**

Mechanism (a coherence precondition on the measurement, not a per-input case
check): `score_heldout` restricts both sides to `graded = {held-out review ids
present in the predictions AND in the answer key}`. On the synthetic corpus every
review is classified and labeled, so `graded` is the full held-out set and the
pinned `RULES_HELDOUT` figures are unchanged. On a captured/real corpus with only
synthetic labels, `graded` is empty, so every label scores `predicted = actual =
0 → None`; the CLI then writes **no** mart (it populates only when at least one
review was graded), leaving the empty shell `build_derived` created. When Phase 7
appends real labels, those ids are classified and grade normally, while synthetic
labels a real run did not classify are ignored — so a mixed answer key grades each
corpus against its own labels. This tightens invariant 2 (the `predicted`/`actual`
sets are over `graded`, not over all held-out predictions/labels) and adds the
"no mart when nothing is graded" clause; the three crafted `test_gate.py` unit
cases are updated so a "miss" is a review classified with the wrong label (in the
predictions), not a label present only in the gold. *Rejected: guarding the write
by `ROWS == "synthetic"` (a per-input case, and it would wrongly skip Phase 7's
real captured grading under a mixed answer key).*

## Delivered

2026-09-04. The held-out eval gate ships: `classify/eval/gate.py::score_heldout`
grades the full classifier's predictions on the held-out fold (fold 4) alone —
`hits = |predicted ∩ actual|` (the shared numerator), `precision = hits/predicted`,
`recall = hits/actual`, each `None` on a zero denominator — reading the answer key
inside the wall and taking predictions in (a pure function, like 5b's
`precision.evaluate`). `sql/marts/classifier_quality.sql` is the first Python-fed
mart: DDL only (the fixed shape) run in `build_derived`, filled by
`pipeline/build.py::write_classifier_quality` from the CLI classify step — one row
per scored label (five themes + `positive`), tagged **Measured**, carrying a
computed metric's provenance (`answer_key`, `heldout_fold`, `run_id`) and no
`source_url`/`captured_at`/clock. B2.4 flips Pending → Measured (upstream source
`classify/eval/labels.csv`); B2.2/B2.5 stay Pending (Phase 7). `make rebuild` writes
the mart and prints a one-line gate summary. No new dependency.

Per **amendment A1**, the gate grades only reviews both classified and present in
the answer key, and the CLI writes no mart when nothing is graded — so `make
rebuild ROWS=captured` (the real corpus, whose ids the synthetic answer key does
not cover) leaves `classifier_quality` empty and says so, rather than a garbage
`0.0` tagged Measured. On the synthetic corpus fold 4 is five clear reviews the
rules classify correctly, so every present label scores 1.00/1.00 and two labels
are `n/a`, pinned in `tests/pins.py` (`RULES_HELDOUT`); the formula (a disagreement
scores below 1) is proven by crafted unit tests. The no-key run stays green and
populates the mart rules-only, truthfully. `make test` passes (722 tests, 18 new);
`make rebuild ROWS=synthetic`, `make idempotency-check ROWS=synthetic` and `make
check-backing` (B2.4 Measured) are green with no key.

Review round 1 (code-reviewer, functionality-tester, study-editor, coherence-
auditor; security-reviewer not triggered — no sensitive surface): no blockers.
Applied — **amendment A1** (grade over classified ∩ labeled; no mart when nothing
graded), fixing the code-reviewer's should-fix that `ROWS=captured|samples` wrote a
garbage Measured mart; **two pinning tests** for the functionality-tester's
surviving mutations (the mart's precision/recall column mapping under asymmetry,
and the re-populate `delete`); and the **branch/spec-file renamed** to the single
form `phase-6b-eval-gate` (coherence-auditor: `/phase-start` had doubled the slug).
Accepted to BACKLOG: the mart write is not warehouse-aware (Snowflake, Phase 10).

Decisions the spec did not spell out: grading over the intersection (not a
per-input `ROWS == "synthetic"` guard) is what lets a *mixed* answer key in Phase 7
grade a real captured corpus against its real labels while ignoring synthetic
labels the real run did not classify; the mart's `run_id` deliberately carries the
input name (byte-stable provenance), not a per-run id, so a reader must not read
raw-row `run_id` semantics into it.
