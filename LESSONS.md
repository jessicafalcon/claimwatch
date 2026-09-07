# LESSONS.md — what reached a review round, and what now carries it

One row per class of correctness finding a review round reported and a fix
commit closed. A wording or record finding is not a lesson; a wrong output,
an unpinned rule, an unshaped input, a mechanism in the wrong place is. The
fix commit appends the class's row or extends its Where cell (CLAUDE.md →
Workflow rules, "Fix commits"). The row is read before code is written, not
after: `/phase-start` prints the `open` rows, `/preflight` asks each one of
every changed symbol, and `code-craft` points here.

**Promotion.** A class hit twice becomes a mechanism — a ruff rule, a test, a
guard script, or one sentence in a standard — and its Status says which:
`promoted → <mechanism>`. A promoted class that recurs reopens its row: the
mechanism failed, so the mechanism is reworked, not the row. A row `open` for
two phases with no second hit is closed as `expired <date>`. Without this rule
the file grows into a list nobody reads.

The classes are a closed set, checked by `make check-docs` (a ninth is added
here and in `scripts/check_docs.py` in one commit):

```
unpinned unshaped-input traceback-at-boundary suppression site-fix
caller-sourced partial-write name-drift
```

Status is `open`, `promoted → <mechanism>` or `expired <YYYY-MM-DD>`. Commits
are cited by short hash from `main`; a round is the `/review-round` number.

| Class | Where | The mistake | The invariant restored | The pin | Status |
|---|---|---|---|---|---|
| `unpinned` | Phase 0a (9 fix commits); 1 `6794489`; 2 round 2 (`af3c898`, `e7c0df8`, `6208c54`, `04de832`); 6b `29e3a93`; 7b `3f6ef62`; 8a `d4275d7`; 8b rounds 1–3 (`717874a`, `bc9666c`, `337935d`) | A rule, a key, a boundary, a pairing or a tiebreak was written and worked, and no test failed when it moved: the hold-rule boundaries, the claim-draw memo's cache key, the `make simulate` rule/value pairing, the staging `content_hash` tiebreak. The most frequent finding class since Phase 0a. | Every rule and key has one test that fails when it moves, written with the rule, not after the round. | `scripts/check_pins.py` (the gate's `pins` line, `make check-pins`); the "Pinning test" column of `/preflight` | promoted → `scripts/check_pins.py` (2026-09-07) |
| `unshaped-input` | 0a `f9cf6a0`; 2 `f2790a0`; 3a `1be2c0c`, `0ea4e12`, `81e4794`, `0f89f43`; 5a `46d6694`; 7b `b38d871` | A foreign value was accepted by a loose test — `str.isdigit`, an unanchored pattern, whatever `json.loads` calls a number — and coerced or passed through: `N`, a DAMIR amount, a rating, a Crawl-delay, a hook event. | A foreign input is parsed to one declared shape with bounds and refused by name; the shape is written whole (`\A…\Z`). | code-craft → Guards; secure-by-construction → What we do not own; Before reporting DONE #8 | promoted → code-craft → Guards (2026-09-05) |
| `traceback-at-boundary` | 0a `ba407ce`; 1 `0f7b76c`; 2 `abe5a0b`; 3a `1bcd7d0`, `34d9631`, `9e36936` | A refusal surfaced as a traceback: a bad `TARGET`, an existing capture directory, a missing executable, a regex that hung, a declaration the engine could not run. | At a process boundary every refusal is one line naming the input and an exit code; exceptions stay inside the library. | code-craft → Error policy; `tests/test_review_tools.py::test_cli_refusals_are_one_line_exit_2` and its siblings per script | promoted → code-craft → Error policy (2026-09-05) |
| `suppression` | tooling `527425a`, `ff6d89a` (2026-09-05) | A function-shape signal was silenced with a `noqa` — three on `scrape` — instead of a split, and a `noqa` that suppressed nothing stayed. | Past a signal a function is split or carries a one-line reason; a suppression that suppresses nothing is deleted. | RUF100 (pyproject); `tests/test_noqa_reasons.py` | promoted → RUF100 + `tests/test_noqa_reasons.py` (2026-09-05) |
| `site-fix` | 2 round 4 `20240c8` (missed in round 3); 3a exit (BACKLOG row "Round 5's fix classes were applied at their finding sites only") | A fix landed on the finding's line while sibling sites kept the flaw: the driver-error relay around `create` but not `_columns`; one of six shapes anchored. | A fix changes the mechanism's kind everywhere the class occurs — the class, not the case. | CLAUDE.md → Workflow rules "Fix the class, not the case"; code-craft → Guards, last bullet | promoted → code-craft → Guards (2026-09-05) |
| `caller-sourced` | 3a `b5ba7f3`, `057eac5`, `6d0627f`; 8b round 2 `28da07a` | A value the data determines was a parameter or a default a caller could pass differently: the feed parser's platform as a module default, a rebuild's `root` rebound mid-loop, a claim draw handed in beside the fit it derives from. | A value the data determines is derived where it is used, never a caller's argument or a module default. | code-craft → Function shape (the sentence added 2026-09-07); code-reviewer Pass 2 | promoted → code-craft → Function shape (2026-09-07) |
| `partial-write` | 3a `0198fed`, `30d9fdd`; 6b `29e3a93` | A loader wrote the rows before the refused one and stopped, leaving half a batch; a re-populate's delete and insert were not one transaction. | A load writes its batch or nothing: one transaction per load, and a refused row refuses the batch. | code-craft → Error policy (the sentence added 2026-09-07); the two-rebuilds tests per mart | promoted → code-craft → Error policy (2026-09-07) |
| `name-drift` | 6a `6310b66`; 8b round 2 `dfd299b` | One quantity carried two or three names across the mart header, CLAUDE.md, the spec and the code (the hold-length threshold); test names drifted from the spec's Evidence ids. | One concept, one name, in code, mart headers, SPEC.md, BACKING.md and the spec; the mart's name is canonical. | `/preflight`, column "Same concept, other names"; code-craft → Naming (the sentence added 2026-09-07) | promoted → `/preflight` + code-craft → Naming (2026-09-07) |
