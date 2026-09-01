# Phase N — <name> (PROPOSED)

Contract for the `phase-N-<slug>` branch. Source: PROJECT_BRIEF.md §9 Phase N
(or "post-plan extension" + the finding that originated it). Depends on
<predecessor> merged.

**Status: PROPOSED — do not start until approved.** <"No new dependencies", or
the package and why — the allowlist is in CLAUDE.md → Conventions.>

Four sections marked REQUIRED are mandatory; a spec without them is not
approvable (CLAUDE.md → Workflow rules). A spec carries at most ~6 done-when
items — split larger scope into sub-phases (5a/5b), each from this template.

## Why

<The problem in the reader's words, then why this phase and not a fix PR.>

## The central constraint

**<One bolded sentence.>** <What must not move while the phase moves everything
else — a frozen fixture, a BACKING row set, a pinned number, the no-key run.>

## DONE command

```
<one command line>
```

- <One bullet per command segment: what it proves and which pin it reproduces.>

## Done-when

1. **<Item.>** <A behavioural clause the code can falsify.> *Evidence: row 1.*
2. …

(≤ ~6 items. An item is a contract, not a narrative.)

## Evidence (REQUIRED)

Every done-when item names the test or command output that proves it. An item
without evidence is not a done-when item. `make review-gate SPEC=…` checks that
every `tests/….py::test_x` id and every `make <target>` named here exists; the
functionality-tester confirms each exercises its claim.

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_<x>.py::test_<y>` / `make <target>` prints "<…>" |

## Invariants (REQUIRED)

Properties, not mechanisms — written BEFORE any pinned decision names how the
code works. Each is a universally quantified sentence ("for all X, Y holds")
paired with the scenario test that would falsify it. A mechanism ("a status
column marks…") is not an invariant; the invariant is the property the
mechanism must keep ("for every review already classified, a re-run changes
nothing"). Pinned decisions may name a mechanism only by reference to the
invariant it satisfies.

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all <X>, <Y>. | `tests/test_<x>.py::test_<scenario>` — <the scenario in one clause> |

## Pinned decisions (do not re-litigate)

- **<Decision.>** <Why; the alternative rejected in one clause; "satisfies
  invariant N".> (≤ ~6)

## Scope (files)

- <Every file the phase touches, code and record alike.>

## Record updates (REQUIRED)

`make review-gate SPEC=…` diffs this list against `git diff main...HEAD`: a
listed file absent from the diff is a FAIL; a record file in the diff but off
the list is a WARN. A row that applies to no file is written WITHOUT backticks
("- [ ] README — none").

- [ ] `DECISIONS.md` — Phase N entry; supersede pointers on reversed entries
- [ ] `BACKLOG.md` — rows closed (struck + "DONE Phase N") and rows opened
- [ ] `CLAUDE.md` — Current status; Commands; Repo map; allowlist; BACKLOG count
- [ ] `BACKING.md` — rows this phase populates (tag changes Pending → Measured/Modeled)
- [ ] `SPEC.md` — only if a chart or beat changed (a design change: STOP first)
- [ ] `README.md` — commands / beats touched
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED when the phase adds a `make` target that takes a variable, deletes anything, calls a paid API, or touches the network)

For each such target: behaviour and the test pinning it for an **empty value**,
a **path-escaping value** (`../x`), a **shell-metacharacter value** (`"; `), the
**variable exported from the environment** instead of the command line, and
for any confirmation knob, **`$(origin)` gating** (`CONFIRM=yes` counts only
from the command line). For a paid-API or network target: what it costs or
fetches if run twice, and what it does with no credentials.

Settled shape: one Python process validates the value, derives every path from
it, prompts on a tty, then acts; every recipe is one line; every user variable
reaches Python unexpanded and single-quoted (`$(call _Q,$(value VAR))`) and is
`unexport`ed.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|

(If none: keep the heading and write "None — no new target takes a variable,
deletes, calls a paid API, or touches the network.")

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (<triggered / not triggered — reason>): <what it checks here>.
- **security-reviewer** (<mandatory if CI, `.env`, credentials, network, a paid
  API, or a destructive target is touched; else "not triggered — reason">).
- **functionality-tester** (<same trigger as code-reviewer>): DONE command + <the
  phase's negative tests>.
- **study-editor** (<triggered if README / SPEC / study prose changed>).
- **coherence-auditor** at exit: <the stale sentences it must find gone>.
- Stack risk: <features to verify in the first hour; STOP and report before any
  workaround; findings go to DECISIONS.md → Gotchas>.

## Out of scope (deferred, recorded)

- <Each item with where it is recorded — BACKLOG row, a later phase's spec.>
