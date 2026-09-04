# Phase 6a — Model fallback + graceful degradation

Contract for the `phase-6a-model-fallback` branch. Source: PROJECT_BRIEF.md §9
Phase 6 ("Model fallback + gate"), split into 6a/6b (this session, the architect's
call): 6a is the model call site, the decision cache and the no-key guarantee;
6b is the held-out eval gate and the `classifier_quality` mart (B2.4). Depends on
Phase 5b merged (PR #11).

**Status: APPROVED 2026-09-04 — in progress.** One new dependency:
`anthropic` — pre-approved for Phase 6 in CLAUDE.md → Conventions ("anthropic
(6)"), the client the one model call site uses. No other new dependency. The
allowlist is in CLAUDE.md → Conventions.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

## Why

Beat 2 shows the share of negative reviews in each of five themes. 5b built the
rules layer — hand-written patterns that decide the clear cases and leave the
rest `unclassified`. 6a is the one place a language model reads the reviews the
rules could not decide and tags what they are about, so that no review is left
unread when a key is present — while the pipeline still runs end to end, and
honestly, when no key is present.

This is 6a and not 6b because the model call, its key handling and the cache are
one security-sensitive, paid unit that deserves its own review and its own merge
before the deterministic eval gate is built on top of it. 6a writes no mart and
shows no study number: it produces the combined rules+model classification as a
Python value, proves the no-key run is green and the cache makes re-runs
deterministic, and hands that value to 6b's gate.

*What a language model is doing here, and why it is fenced.* A language model
reads each review the rules left unclassified and answers with a label from a
fixed list. It is fenced three ways: it is called from exactly one module
(`classify/llm.py`), it sees only what the rules could not decide, and its reply
is parsed strictly against the seven closed labels — a reply outside the set
becomes `unclassified`, never an eighth label (CLAUDE.md → The five contracts,
Classification). It is never trusted on its own: 6b grades it on hand labels the
model never saw. And it is never required: delete the key and every ambiguous
review stays `unclassified`, shown in the study as a gray "not yet classified"
band (SPEC.md, *How to read a panel*).

*Why a cache, and why deterministic despite a model.* A language model can give
two answers to the same review on two calls. The cache is what makes the
pipeline deterministic anyway: a decision is stored once, keyed by the review,
the prompt version and the model, and every later run reads the cache instead of
calling the model again. So "run the pipeline twice and every number is the
same" holds *given the cache* (CLAUDE.md → Deterministic first); a re-run calls
the model only for reviews it has never decided.

## The central constraint

**The no-key run is green, and the model is called from exactly one module and
never trusted to invent a label.** With `ANTHROPIC_API_KEY` unset,
`make rebuild ROWS=synthetic` runs end to end, constructs no Anthropic client,
touches no network, and every review the rules left `unclassified` stays
`unclassified` — no crash, no fake label. A language model is called from
`classify/llm.py` and nowhere else; it sees only the rules-`unclassified`
reviews; its reply is parsed to a subset of the seven closed labels, and anything
outside becomes `unclassified`, never an eighth label. Decisions are cached by
`(review_id, prompt_version, model)`; a re-run calls the model only for uncached
rows, so the combined classification is a deterministic function of the reviews,
`rules.yaml`, the prompt version, the model and the cache. No clock touches the
data path or the cache key. 6a adds no `sql/marts` file and populates no BACKING
row — the combined classification stays a Python value for 6b.

## DONE command

```
make rebuild ROWS=synthetic                              # green, no key (offline; CI runs this)
ANTHROPIC_API_KEY=<key> make rebuild ROWS=synthetic      # green, with a key (developer-run, paid)
```

- Line 1 is the no-key proof: `make rebuild ROWS=synthetic` exits 0 with the key
  unset, classifies the synthetic corpus (rules only, since no model runs),
  prints the classify summary, and leaves every rules-`unclassified` review
  `unclassified`. The functionality-tester runs this; `make test` pins it
  (`test_no_key.py`).
- Line 2 is the paid path: with a key set, the same command classifies the
  reviews the rules could not decide via one model call each (cached after), and
  exits 0. It is developer-run — an agent never runs it (no key, and the paid
  call is the developer's). Its exact labels are not pinned (the model varies);
  what is pinned is that the run is green and the strict parse admits only the
  seven labels.
- `make test` also pins the cache (a warm re-run makes zero model calls),
  determinism (rebuild twice yields identical classified rows), the strict parse
  (a foreign reply → `unclassified`), and the one-call-site / lazy-import wall.

## Done-when

1. **One model call site; the model sees only rules-`unclassified` reviews; a
   reply outside the seven labels becomes `unclassified`.** A language model is
   called from `classify/llm.py` alone (the only `import anthropic`, imported
   lazily inside the real-call function); its input is exactly the reviews the
   rules left `unclassified`; `parse_reply` returns a subset of
   `classify.labels.LABEL_SET`, and any token outside — or an empty/uncertain
   reply — yields `unclassified`, never an eighth label. *Evidence: row 1.*
2. **The no-key run is green (the durable guarantee, every phase from 6a on).**
   With `ANTHROPIC_API_KEY` unset, the classify step and `make rebuild
   ROWS=synthetic` complete without error, construct no Anthropic client and make
   no network call, and every rules-`unclassified` review stays `unclassified` —
   the combined output equals the rules-only output. *Evidence: row 2.*
3. **Decisions are cached by `(review_id, prompt_version, model)`; a re-run calls
   the model only for uncached rows.** The cache is a gitignored, text-free file
   under `data/` (`review_id, prompt_version, model, theme`); a warm re-run over
   the same reviews makes zero model calls and yields byte-identical rows; a
   changed `prompt_version` or `model` is a new key, not a stale hit. *Evidence:
   row 3.*
4. **`classified_reviews` = rules + model combined, one row per review × theme,
   `unclassified` the single fallback; it stays Python (no mart, no BACKING
   row).** The combined output is deterministic and sorted by
   `(review_id, theme)`; a review the rules and model both leave undecided is
   exactly one `unclassified` row; 6a adds no `sql/marts/` file and flips no
   BACKING tag. *Evidence: row 4.*
5. **Rebuild is deterministic given the cache; no clock on the data path.**
   `make rebuild ROWS=synthetic` run twice (no key, or with a warm cache) yields
   identical classified rows; `classify/llm.py`, `classify/cache.py` and the
   combiner carry no `now()`/clock on the data path or in the cache key. The wall
   still holds: none of them reads `classify/eval/labels.csv`. *Evidence: row 5.*

(5 items. Each is a contract the code can falsify.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_llm.py::test_only_llm_imports_anthropic`, `::test_anthropic_import_is_lazy`, `::test_model_input_is_only_rules_unclassified`, `::test_reply_outside_the_set_becomes_unclassified`, `::test_valid_reply_maps_to_closed_labels` |
| 2 | `tests/test_no_key.py::test_no_key_classify_stays_unclassified`, `::test_no_key_constructs_no_client_and_no_network`, `::test_no_key_combined_equals_rules_only` / `make rebuild ROWS=synthetic` exits 0 with the key unset |
| 3 | `tests/test_cache.py::test_warm_rerun_makes_zero_model_calls`, `::test_cache_round_trip_is_text_free`, `::test_prompt_version_or_model_change_is_a_new_key` |
| 4 | `tests/test_combined.py::test_review_times_theme_grain`, `::test_undecided_is_one_unclassified_row`, `::test_combined_is_sorted_and_deterministic`, `tests/test_combined.py::test_no_new_mart` |
| 5 | `tests/test_combined.py::test_rebuild_twice_identical_classified_rows`, `tests/test_llm.py::test_no_clock_on_the_data_path`, `tests/test_labels_isolation.py::test_the_model_call_site_is_covered_by_the_wall` |

## Invariants (REQUIRED)

Properties, not mechanisms — written before any pinned decision names how the
code works.

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all classification, a language model is called from `classify/llm.py` and nowhere else, and it sees only the reviews the rules left `unclassified`. | `tests/test_llm.py::test_only_llm_imports_anthropic` — a grep of the repo finds `import anthropic` only in `classify/llm.py`; `::test_model_input_is_only_rules_unclassified` — the decide function is handed exactly the rules-`unclassified` ids, never a decided one. |
| For all model replies, the parsed result is a subset of the seven closed labels; a reply outside the set — or empty/uncertain — becomes `unclassified`, never an eighth label. | `tests/test_llm.py::test_reply_outside_the_set_becomes_unclassified` — a fake model returns `"document-loop-ish"` / free text; the review is `unclassified`, no new label appears. |
| For all runs with no API key, the pipeline completes and every rules-`unclassified` review stays `unclassified` — no client constructed, no network, no crash, no fake label. | `tests/test_no_key.py::test_no_key_constructs_no_client_and_no_network` — with the key unset, the Anthropic client is never constructed and the combined output equals the rules-only output. |
| For all reviews already in the cache under `(review_id, prompt_version, model)`, a re-run makes no model call for them and yields identical rows. | `tests/test_cache.py::test_warm_rerun_makes_zero_model_calls` — a counting fake model, run twice over one cache: the second run's call count is 0 and the rows are byte-equal. |
| For all classification, no clock is on the data path or in the cache key; the combined output is a pure function of the reviews, `rules.yaml`, the prompt version, the model and the cache. | `tests/test_combined.py::test_rebuild_twice_identical_classified_rows`, `tests/test_llm.py::test_no_clock_on_the_data_path` — two rebuilds agree; the cache key holds no timestamp and the data path calls no clock. |
| For all modules outside `classify/eval/` (now including `classify/llm*`, `classify/cache*`, the combiner), none reads `labels.csv`; and 6a adds no mart. | `tests/test_labels_isolation.py::test_no_reader_of_labels_outside_eval`, `::test_the_model_call_site_is_covered_by_the_wall`; `tests/test_combined.py::test_no_new_mart` — the model never sees its own answer key, and the pattern/model logic never becomes SQL. |

## Pinned decisions (do not re-litigate)

- **One model call site, `classify/llm.py`, key-gated and lazy-imported.** The
  Anthropic client and `import anthropic` live only inside the real-call
  function; `model_available()` reads the key from the environment; no key → the
  decide function returns no decision, so every unresolved review stays
  `unclassified`. The prompt asks for a label from the seven and nothing else.
  *Rejected: importing `anthropic` at module top (an offline/no-key run then
  loads a paid SDK on the data path, and a fresh clone without the dep installed
  could not even import the module) or a second call site (breaks the
  one-place contract).* Satisfies the one-call-site and no-key invariants.
- **Strict closed-set parse of the reply → the seven labels or `unclassified`.**
  `parse_reply` reads the reply, keeps only tokens in `LABEL_SET`, and returns
  them; an empty result, or a reply the model uses to say it cannot decide, is
  `unclassified`. The reply is never trusted as written and never becomes a new
  label. *Rejected: passing the reply through as a label (breaks the
  Classification contract) or a fuzzy match to the nearest label (invents a
  decision the model did not make).* Satisfies the closed-set invariant.
- **The cache is a gitignored, text-free file under `data/`, keyed
  `(review_id, prompt_version, model)`, review×theme rows.**
  `data/classify/decisions.csv`, columns `review_id, prompt_version, model,
  theme` (a review the model gave two themes is two rows; a review the model
  could not place is one `unclassified` row). A run reads it and calls the model
  only for `(review_id, prompt_version, model)` keys absent from it, then appends
  the new decisions. *Rejected: committing the cache (it is corpus-derived —
  brief §2.5 keeps the corpus out of git — and a committed synthetic cache would
  smuggle model decisions into the no-key CI run, hiding the very gray band the
  no-key guarantee is meant to show); keying without `prompt_version`/`model` (a
  prompt or model change would silently reuse stale decisions).* Satisfies the
  determinism and no-key invariants.
- **`prompt_version` and `MODEL` are pinned constants in `classify/llm.py`.**
  Both are part of the cache key, so bumping either invalidates the cache by
  construction (the next run re-decides). `MODEL` is one current Claude id, a
  fast model apt for a high-volume classifier. *Rejected: a runtime- or
  environment-chosen model (non-reproducible, and the cache key would drift
  without anyone bumping a version).* Satisfies the determinism invariant.
- **`classified_reviews` stays a Python value; 6a writes no mart and populates no
  BACKING row.** The combined rules+model output is produced by a function
  (`classify/combined.py::classify_all`), used by 6b's gate and Phase 7's
  theme-share marts; it is not a displayed study number in 6a. B2.4
  (`classifier_quality`) is 6b's held-out gate; B2.2/B2.5 are Phase 7.
  *Rejected: materializing a mart now (no Beat panel consumes it until 6b/7, and
  a number a reader sees must wear a tag — this value is not yet shown).*
  Satisfies the evidence contract (work maps to a row or is out of scope).
- **`make rebuild` runs the classify step; the paid model call is the
  developer's, never an agent's.** Rebuild invokes `classify_all` after staging
  and prints a one-line summary, so the no-key path is proven end to end through
  the DONE command; with a key the developer's run populates the cache. *Rejected:
  a separate `make classify` target the DONE does not exercise (the no-key
  guarantee would then live outside `rebuild`, the command the study is built
  from).* Satisfies the no-key invariant (the guarantee rides the real build).

## Scope (files)

- `classify/llm.py` — new; the one model call site: `MODEL`, `PROMPT_VERSION`,
  `model_available()`, `decide(reviews) -> dict[review_id, tuple[label, …]]`
  (real call, `anthropic` imported lazily inside), `parse_reply` (strict
  closed-set). No key → no decision.
- `classify/cache.py` — new; read/write the gitignored decision cache under
  `data/`, keyed `(review_id, prompt_version, model)`, text-free.
- `classify/combined.py` — new; `classify_all(reviews, *, rules, decide, cache…)`
  → sorted `(review_id, theme)` rows combining rules with the cached/model
  decisions for the rules-`unclassified` reviews; `unclassified` the single
  fallback.
- `pipeline/build.py`, `pipeline/cli.py` — `rebuild` runs `classify_all` over
  `stg_reviews` after staging and prints a classify summary (counts by outcome);
  no mart, no user variable added.
- `tests/test_llm.py` — new; one call site, lazy import, model input is only
  rules-`unclassified`, strict parse (foreign reply → `unclassified`, valid reply
  → closed labels), no clock.
- `tests/test_cache.py` — new; round-trip text-free, warm re-run zero model
  calls, prompt/model change is a new key.
- `tests/test_combined.py` — new; review×theme grain, `unclassified` fallback,
  sorted/deterministic, rebuild-twice identical, no new mart.
- `tests/test_no_key.py` — new; the durable no-key guarantee (green, no client,
  no network, combined == rules-only).
- `tests/test_labels_isolation.py` — add `test_the_model_call_site_is_covered_by_the_wall`
  (assert `classify/llm.py` is in the swept set; the whole `classify/` tree
  outside `eval/` is already swept).
- `tests/pins.py` — the synthetic no-key outcome counts (decided / `unclassified`
  reviews, combined == rules-only), the cache-key fields.
- `pyproject.toml`, `uv.lock` — `anthropic` added to `[project] dependencies`
  (pre-approved, Phase 6 allowlist).
- `.gitignore` — confirm `data/classify/` is covered by the existing `data/`
  rule (add a line only if it is not).
- `DECISIONS.md` — Phase 6a entry.
- `BACKLOG.md` — rows closed / opened.
- `CLAUDE.md` — Current status; Commands (`rebuild` now classifies); Repo map
  (`classify/llm.py`, `classify/cache.py`, `classify/combined.py`); allowlist
  (`anthropic` direct); BACKLOG count.
- this spec — the "Delivered" paragraph appended at exit.

Freeze: none

(`fixtures/` bytes do not change; the synthetic labels stay in
`classify/eval/labels.csv`.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 6a entry: one lazy-imported model call site; strict
  closed-set parse (foreign reply → `unclassified`); the gitignored, text-free
  decision cache keyed `(review_id, prompt_version, model)`; `classified_reviews`
  stays Python (no mart; B2.4 is 6b's gate); `rebuild` runs the classify step;
  `anthropic` made a direct dependency
- [ ] `BACKLOG.md` — closed: any 5b-deferred row 6a lands; opened: the with-key
  eval numbers / real-corpus classification (Phase 6b / 7); BACKLOG count refreshed
- [ ] `CLAUDE.md` — Current status; Commands (`rebuild` classifies); Repo map
  (the three new `classify/` modules); allowlist (`anthropic`); BACKLOG count
- [ ] BACKING — none (6a populates no BACKING row; `classified_reviews` is a
  Python value, not a displayed number; B2.2/B2.4/B2.5 stay Pending, B2.4 for 6b)
- [ ] SPEC — none (the grain and the gray "not yet classified" band were settled
  in Phase 0b; no chart or beat changes)
- [ ] README — none (the README is a Phase 9 deliverable; it does not exist yet)
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

6a adds no new `make` target and no new target variable: `make rebuild` keeps its
`TARGET`/`ROWS` variables, both validated against closed sets by
`pipeline.cli.resolve_choice` (Phase 3a). What is new is that `rebuild` now calls
a **paid API** when a key is present, through `classify/llm.py`. That path:

- **No credentials.** `model_available()` is false, `decide` returns no decision,
  every unresolved review stays `unclassified`, and `make rebuild` exits 0. The
  Anthropic client is never constructed and `anthropic` is never imported (lazy
  import inside the real-call function). Pinned by
  `tests/test_no_key.py::test_no_key_constructs_no_client_and_no_network`.
- **Cost / run twice.** The first keyed run calls the model once per
  rules-`unclassified` `(review_id, prompt_version, model)` not already cached,
  then caches it; a second run over the same reviews calls the model zero times
  (warm cache). Cost is bounded by the count of never-decided unresolved reviews,
  once. Pinned by `tests/test_cache.py::test_warm_rerun_makes_zero_model_calls`.
  The DONE proof uses `ROWS=synthetic` (a small corpus); the default
  `ROWS=captured` classifies the real corpus and is the developer's paid choice.
- **The key.** Lives in `.env` only — never in a tracked file, never in Actions,
  never echoed; a refusal or log prints names, never the value (CLAUDE.md →
  Conventions, Secrets). The key is read from the environment inside
  `classify/llm.py`, nowhere else.
- **`classify/llm.py` is a guard at a foreign input (the model reply):** its
  accepted output is the seven closed labels, and any reply it cannot place in a
  label becomes `unclassified` (CLAUDE.md → Before reporting DONE, item 8) —
  pinned by `tests/test_llm.py::test_reply_outside_the_set_becomes_unclassified`.
- **The agent never runs the paid path.** The model API is developer-run
  (CLAUDE.md → Workflow rules). The agent builds and proves the no-key and
  fake-model paths offline; the with-key DONE line is the developer's.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| (no new target/variable; `rebuild`'s `TARGET`/`ROWS` are the Phase 3a closed-set guards) | resolve_choice → default | refused | refused | refused (not in set) | n/a (no confirm goal) | `tests/test_cli.py` (Phase 3a) |

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `classify/**`, `pipeline/**`, `tests/`): one
  model call site, lazy `anthropic` import; the reply is parsed to the closed
  set, never coerced or trusted; the cache is keyed by
  `(review_id, prompt_version, model)` and text-free; the combiner is a pure
  function (no clock, no random, sorted); the grain is one row per review × theme
  with an `unclassified` fallback; no mart, no pattern/model logic in SQL; the
  wall holds (`llm.py`/`cache.py`/`combined.py` read no answer key).
- **security-reviewer** (MANDATORY — the model API / key path is touched,
  `classify/llm.py`): the key is read from `.env`/environment only, never
  committed, never echoed, never in Actions; `anthropic` is imported lazily so a
  no-key run loads no paid SDK; the cache carries ids and labels only, no review
  text, no brand; the paid call is developer-run, never an agent's; the model
  reply is a foreign input parsed to a closed set.
- **functionality-tester** (triggered — same surface): the no-key DONE line
  (`make rebuild ROWS=synthetic`, key unset), the strict-parse pins, the
  warm-cache zero-call pin, the rebuild-twice determinism pin, the review×theme
  grain and `unclassified` fallback, the one-call-site grep, and the combined ==
  rules-only equality under no key. Exercises a fake `decide` for the model path
  (no key, no network).
- **study-editor** (triggered — `CLAUDE.md` prose changes): neutrality of the
  Current-status and Repo-map sentences; no company named; the model described as
  "a language model reads each review and tags what it's about", not a banned
  word.
- **coherence-auditor** at exit: no stale sentence implying the model reads its
  own answer key or runs without a key being optional; the five-contracts
  "one model call site" and "no-key run is green" now match built code; B2.4
  still reads Pending (it is 6b's); the architecture diagram's "a language model
  only for what rules could not decide" now matches `classify/llm.py`.
- Stack risk (first hour; STOP and report before any workaround; findings →
  DECISIONS → Gotchas): that the `anthropic` SDK version pinned in `uv.lock`
  imports cleanly on Python 3.12 macOS/Linux and exposes the message API shape
  the one call uses (check the official docs before coding the call — the
  `claude-api` skill); that a fake `decide` seam lets every model-path test run
  with no key and no network (the durable no-key test must not need a key to
  pass); that the cache file's `(review_id, prompt_version, model)` order is
  stable so a re-record is a byte-identical file and an empty git diff (it is
  gitignored, but a stable order still matters for the warm-cache pin).

## Out of scope (deferred, recorded)

- **The held-out eval gate (precision + recall on fold 4) and the
  `classifier_quality` mart (B2.4 Pending → Measured)** — Phase 6b
  (`docs/PLAN.md` row 6, the second half of the split). 6a produces the combined
  classification the gate grades; it does not grade on the held-out fold or write
  a mart.
- **The `theme_share_by_month` / `theme_share_by_segment` marts (B2.2, B2.5) and
  materializing `classified_reviews` as a mart** — Phase 7 (`docs/PLAN.md` row 7),
  when the classified rows feed a displayed number. 6a keeps the combined output
  in Python.
- **Classification on real scraped rows** — Phase 7 needs the real hand labels to
  grade them; 6a proves the model fallback on the synthetic corpus (CLAUDE.md →
  "Build on the synthetic fixture first").
- **The real 300–500 hand labels** — human offline work (BACKLOG, opened in 5a).
- **A prompt-caching or batching optimization for the model call** — a later
  cost concern; 6a's cache already makes re-runs free, which is the correctness
  property that matters (BACKLOG if it becomes a cost problem).

## Delivered

<!-- appended at phase exit -->
