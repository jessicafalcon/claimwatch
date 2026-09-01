---
description: Review round N on a phase branch. Step 1 finds the spec and the range (always main...HEAD; N is a label — for N > 1 the previous round's table is pasted into every agent prompt so findings on already-reviewed code carry "missed in round N−1"); step 2 runs make review-gate (red → no agents); step 3 prints the spec's Invariants; step 4 classifies the diff surface and spawns code-reviewer + functionality-tester (+ security-reviewer, + study-editor, or coherence-auditor alone for docs-only) scoped to the range; step 5 prints the consolidated table and STOPs. Read-only, report-only.
---

Run review round **$ARGUMENTS** (an integer N ≥ 1) on the current phase branch.
Read-only and report-only, like every agent this command invokes: no edits, no
fixes, no commits, no push. Findings are relayed verbatim and the session STOPS
(CLAUDE.md → Git workflow, "STOP-on-findings"). The working tree is never
written; the only writes are the throwaway worktrees the functionality-tester
registers and removes for hand-mutation.

## 1. Locate the spec and the range

- Scope: phase branches only. If the branch is not `phase-*` (a `fix/*`,
  `docs/*` branch) print ONE line and STOP:
  `no phase spec for <branch> — fix/docs branches run the agents directly`.
- Spec: the one `specs/phase-*.md` whose slug matches the branch name
  (`phase-0a-machinery` → `specs/phase-0a-machinery.md`). If none matches,
  ask for `SPEC=` and stop.
- Range: `RANGE=main...HEAD` (three-dot: the branch since its merge-base).
  There are no round tags. For N > 1, ask the developer to paste round N−1's
  consolidated table if it is not already in the conversation; it becomes part
  of every agent prompt in step 4.

Print first:

```
Review round N — spec: <SPEC> — range: main...HEAD
git log --oneline main...HEAD
git diff --stat main...HEAD
```

## 2. The deterministic gate first — no agents on a state known broken

```
make review-gate SPEC=<SPEC>
```

Print every line it emits. If it exits non-zero: print its lines under
**"GATE RED — no agents spawned"** and STOP.

## 3. Print the invariant list

Print the spec's **Invariants** section verbatim — the table and every fix
amendment appended to it. A spec with no Invariants section is a BLOCKER
finding; record it and continue with the range alone.

## 4. Select the agents by diff surface, then spawn them scoped

Run `git diff --name-only main...HEAD` and classify with the table in
CLAUDE.md → "Which review agents run" (a lookup, not a judgment). Print the
classification and the agent list BEFORE spawning:

```
Surface: code | sensitive | prose | docs-only | mixed (<the surfaces>)
Agents:  <list>
```

- **Code touched** (`*.py`, `sql/**`, `classify/**` incl. `rules.yaml`,
  `models/**`, `Makefile`, `scripts/`, `tests/`, `dags/**`, `study/*.py`):
  spawn **code-reviewer** and **functionality-tester** (that order).
- **Sensitive touched** (`.github/`, `ingest/**`, `classify/llm.py`,
  `pipeline/warehouse.py`, `.env*`, `.claude/hooks/`,
  `.claude/settings*.json`, a target that deletes, calls a paid API or
  fetches): also **security-reviewer**.
- **Prose touched** (`README.md`, `SPEC.md`, `BACKING.md`, `study/**/*.md`,
  `study/**/*.html`, `CLAUDE.md`): also **study-editor**.
- **Docs-only** (every changed path is `*.md`): spawn **coherence-auditor**
  ONLY, scoped to the changed files, plus **study-editor** if a prose file
  above is in the range. No code-reviewer or functionality-tester — there is
  no code to review or run; the gate already checked links, targets, banned
  words, BACKING rows.
- **Mixed**: the union.

All agents are report-only — no Write/Edit, do not grant more. Each prompt
contains:

- the range: "review `git diff main...HEAD`; read every changed file in full";
- the invariant list from step 3, verbatim;
- for N > 1, round N−1's table, and the labelling rule: "a finding on code an
  earlier round already reviewed is still reported, labelled **`missed in
  round N−1`**; a finding on code changed since carries no label";
- for the functionality-tester: "the Evidence-row check and the hand-mutation
  step are mandatory for every write path, rule and formula in the range;
  never run a target that fetches, calls the model API or touches Snowflake";
- for the code-reviewer: "the Invariants check is mandatory; flag every
  mechanism whose value comes from the caller or the clock rather than the
  data; a SQL file and `rules.yaml` are code — read them".

## 5. Consolidate, STOP

Wait for EVERY agent spawned in step 4 to finish before printing anything from
any of them — no per-agent relay as results arrive. Then print one table over
every finding from every agent:

| # | Finding (one sentence) | Raised by | file:line | Class | In range / missed in round N−1 |
|---|---|---|---|---|---|

Below the table, one verdict line per agent that ran (`code-reviewer: pass |
N findings`, `functionality-tester: works | partially | doesn't`,
`security-reviewer: pass | N findings`, `study-editor: pass | N findings`,
`coherence-auditor: pass | N findings`) and one line naming the agents NOT
run and the surface reason. Class is exactly one of **correctness** (wrong
output, an invariant with no pin, a caller/clock-sourced mechanism, an
untagged number), **security**, **voice** (a §2.3/§2.5 finding), **record**
(a stale or missing record sentence), **wording** (names, comments).

Then print, verbatim:

```
Cap is the architect's call: compare this table to round N−1's.
```

The two-round rule (CLAUDE.md → Workflow rules, "Review cap") is applied by a
human reading two tables, never by this command. When it fires, the
disposition replaces the mechanism's KIND (a denylist → a closed set or a
strict parse), never a longer list; correctness fixes land one per commit.

Close with the one line the developer decides on per finding: **fix
(wording/test-only)**, **fix amendment (design change → spec paragraph first,
stop for approval)**, or **accept (BACKLOG row with a trigger)**. Then STOP.

This is an explicit, on-request review. Do not treat its presence as a cue to
run it automatically — it runs only when invoked.
