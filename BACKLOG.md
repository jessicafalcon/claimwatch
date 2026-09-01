# BACKLOG.md — deferred findings and revisits

Items accepted "for now" with a concrete revisit trigger. Reviewed at every
phase exit (alongside the coherence audit); an item whose trigger has arrived
is either done in that phase or re-deferred here with a new trigger — never
silently dropped. Cite rows by TITLE (bold text); line numbers shift. A closed
row is struck through with "DONE Phase N" (or the fix branch), never deleted.
CLAUDE.md states the open-row count; `make check-docs` keeps it honest.

| Item | Source | Trigger |
|---|---|---|
| **No mutation sweep** — the reference project's `mutate.py` (delete-call, constant-return, invert-guard, swap-sort-key over Python; arm operators over SQL `case`) is not adopted. Load-bearing logic here (rules classifier, cost formulas) is pinned by goldens and the Phase 8 "code formulas equal displayed numbers" test; the functionality-tester hand-mutates in a worktree per review. | Phase 0a (`docs/PLAN.md` §2) | A bug in `classify/` or `models/` that a green suite missed, or a hand-mutation survivor class the tester reports twice: adopt the sweep for that class only |
| **CI green on the Phase 0a PR is unverified until first push** — Done-when 6 / Evidence row 6; the workflow has never run (branch unpushed). | Phase 0a spec | First push of `phase-0a-machinery`: confirm `ci / lint-test` green, then strike |
| **Naming-the-target check is agent-only** — the studied company must never be named as the target in prose, code, comments or commits (PROJECT_BRIEF §2.5); today only `study-editor` and `code-reviewer` check it. A deterministic grep would put the name in the repo; a hashed denylist (sha256 of lowercased tokens over `*.py`, `*.sql`, `*.md`, commit messages; seed CSVs and URL columns excluded) is the mechanical alternative. | Phase 0a (`docs/PLAN.md` §6.10, default taken) | The name reaches a tracked file or commit once: build the hashed check in `scripts/` and add it to `make check-docs` |
