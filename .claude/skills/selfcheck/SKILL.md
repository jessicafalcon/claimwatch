---
name: selfcheck
description: Post-commit self-check — verify the last commit against its spec and this repo's rules (deterministic first, tags, fixtures, divergence), then STOP.
# On request only: the developer types /selfcheck; the model never invokes it.
disable-model-invocation: true
---

Verify the current branch's most recent commit. Execute the checks, report,
then **STOP — no push, no agents, no fixes.**

Report each, concisely, with concrete evidence (counts, pass/fail output,
file:line):

- **(a) Suite** — run `make test`; report pass/fail counts.
- **(b) DONE command** — if the commit implements a spec in `specs/`, run that
  spec's DONE command and paste its real result. The DONE command is the only
  definition of done; "tests pass" alone does not substitute. Exception: if
  the DONE command fetches from a live platform, calls the paid model API,
  touches Snowflake, or needs the `confirm` goal, report that it needs explicit
  user go-ahead instead of running it.
- **(c) Deterministic first** — name any decision this commit adds that a
  model makes outside `classify/llm.py`; any `now()` / `current_date` /
  `current_timestamp` in `sql/`; any unseeded randomness (a random split, an
  unordered output, a tie-break with no named key); any number in README /
  study text without a Measured / Documented / Modeled / Pending tag; any
  formula written outside `models/cost_model.py::FORMULAS`. Confirm each is
  justified in DECISIONS.md, or flag it.
- **(d) Fixtures and corpus** — on a branch check `git diff main...HEAD --stat
  -- fixtures/` (must be empty unless the spec has a `Freeze:` line); `git
  ls-files data/` shows only `data/snapshots/`. Also confirm no test was
  weakened to get green.
- **(e) Divergence** — any spec-vs-brief-vs-BACKING-vs-reality gap hit during
  the work: name it and confirm it was reported to the user, not silently
  adapted.
- **(f) Eyeball** — the ONE file you'd most want a human to read
  line-by-line, and why.
