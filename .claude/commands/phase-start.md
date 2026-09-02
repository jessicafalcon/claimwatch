---
description: Start a phase — checkout main, pull, create phase-<slug>, print the spec's Done-when, DONE command and the BACKING rows in scope; refuse if the spec is missing or not approved. Then STOP for the developer to say "build".
---

Start phase **$ARGUMENTS** (a slug such as `0a-machinery`, `1-schema`).

1. **Clean tree.** `git status --porcelain` must be empty; otherwise print
   the lines and STOP (a phase starts from a clean main).
2. **Branch.** `git checkout main && git pull && git checkout -b
   phase-$ARGUMENTS`. If the branch exists, check it out instead and say so.
3. **Spec.** `specs/phase-$ARGUMENTS.md` must exist. If it does not: STOP and
   say the spec is written first, from `specs/TEMPLATE.md`, and approved
   before any code (CLAUDE.md → Workflow rules). If its status line still says
   `PROPOSED — do not start`, STOP and ask for approval.
4. **Restate the contract.** Print, verbatim from the spec: the central
   constraint, the DONE command, the Done-when list, and the Scope (files).
5. **Scope from the evidence contract.** Print the BACKING.md rows this phase
   populates (the rows the spec's Record updates name, or the rows whose SQL
   file is under the spec's Scope). Work that maps to no row is out of scope
   (PROJECT_BRIEF §8).
6. **Guardrails inherited.** Run `make review-gate` (no SPEC) and print its
   lines — the branch starts green or the previous phase left a problem.
7. Print one line: `Phase $ARGUMENTS ready — say "build" to start.` Then
   STOP. Do not write code until told.

This is an explicit, on-request command. It runs only when invoked.
