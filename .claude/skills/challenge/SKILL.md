---
name: challenge
description: Challenge a plan, phase spec, amendment, DECISIONS entry or design — steel-manned strengths first, then severity-tagged findings each with a concrete alternative, then a verdict. Use when the developer asks to challenge, critique, stress-test, pressure-test, red-team or poke holes in a plan, design, architecture decision or proposal, before it is implemented.
argument-hint: [specs/phase-N-slug.md | DECISIONS.md#anchor | "the plan above"]
allowed-tools: Read, Grep, Glob, Bash(git *), Bash(make review-gate*), Agent
effort: high
---

Run a devil's-advocate round on **$ARGUMENTS**. Read-only and report-only: no
edits, no fixes, no spec amendment, no commit. The verdict is advisory; the
developer decides the disposition, then the main session acts.

## 1. Resolve the target

- A path under `specs/` → read the whole file (status line, Invariants,
  Evidence, Threat model, any amendment paragraphs).
- `DECISIONS.md#<anchor>` → that entry and the "still in force" bullet it
  backs.
- No argument, or "the plan above" → the most recent plan in this
  conversation (a plan-mode plan, a proposed amendment, a design sketch).
  Quote its first line so the developer can confirm it is the right one.
- Anything else (a URL, a value with `"; `, a path outside the repo) → print
  one line and STOP: `challenge: target must be a spec path, a DECISIONS
  anchor, or the plan in the conversation`.

Print: `Challenge — target: <what> — standard: brief §2/§8/§9, CLAUDE.md
contracts, BACKING rows <ids>, predecessor <spec>`.

## 2. Gather the standard (so the challenger argues from the record, not memory)

Read and pass along, verbatim where short:
- `PROJECT_BRIEF.md` §2, §8, §9; `CLAUDE.md` → The five contracts, Workflow
  rules, Conventions.
- The BACKING rows the plan names (their current tag) and `SPEC.md`'s
  mention of them.
- The predecessor spec's Delivered paragraph and the `docs/PLAN.md` §2
  verdict rows that touch the same piece.
- `DECISIONS.md` "still in force" + Gotchas; `BACKLOG.md` rows whose trigger
  the plan could fire.
- `git log --oneline -15` and `git status --porcelain` (what state the repo
  is in).

## 3. Spawn the challenger

Spawn **senior-architect** once, in this turn, with: the plan text (or path),
the standard from step 2, and the instruction "apply every lens to the whole
plan; report verbatim in your format; the verdict is advisory". Wait for it.

## 4. Print the report verbatim, then the disposition line

Print the challenger's report unchanged. Below it, one line per BLOCKER and
should-fix for the developer to answer:

- **amend** — a one-paragraph spec amendment naming the invariant it
  restores (a fix amendment: written alone, STOP for approval);
- **accept** — a BACKLOG row with a trigger;
- **reject** — one sentence why, recorded in DECISIONS if the challenger's
  alternative was a real option.

When the developer has answered, the main session stamps the spec under its
status line — `Challenged: <date>, round <k> — <verdict>` — so the
`challenge-gate` hook and `/phase-start` can see it. Not before.

## 5. STOP

Print `Cap and disposition are the architect's call.` and stop. Do not amend,
do not start building, do not re-run the challenger on its own findings.

This is an explicit, on-request skill. Its presence is not a cue to run it;
it runs when invoked or when the developer asks to challenge a plan.
