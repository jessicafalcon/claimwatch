# Phase 4 — The weekly cron (PROPOSED)

Contract for the `phase-4-weekly-cron` branch. Source: PROJECT_BRIEF.md §9
Phase 4 — a scheduled scrape that commits new snapshots so the rating
time-series accrues while the rest of the study is built. Depends on Phase 3c
merged (PR #7, 2026-09-04).

**Status: PROPOSED — do not start until approved.** No new dependencies (uses
the Phase 2 fetcher, DuckDB, stdlib csv; GitHub Actions is configuration, not a
package). The allowlist is in CLAUDE.md → Conventions.

Four sections marked REQUIRED are mandatory. The status line moves `PROPOSED` →
`APPROVED <date> — in progress` → `APPROVED <date> — DELIVERED <date>, PR open`
when the Delivered paragraph is appended.

## Why

The rating time-series (B1.2, B1.3, B1.4) needs points at different weeks to be
a *series* and not a single dot. Today every fetched point lives only in a
capture under `data/cache/`, which is gitignored, so nothing a scrape reads
survives the machine it ran on. Phase 4 gives the fetched rating figures a
tracked home and a hand that writes to it every week: a GitHub Actions cron
runs the polite scrape and commits the new figures. This is a phase, not a fix
PR, because it is the first workflow that writes to the repo — the one
sanctioned exception to "never commit to `main`" — and its write path, its
commit scope and its unattended network conduct are new contracts that need
invariants, not a patch.

*What GitHub Actions is, and why here.* GitHub Actions runs a workflow file on
GitHub's servers on a schedule (a cron line), the same way a nightly job runs
on a server you own — no machine of ours stays on. A workflow is granted a
token scoped to what it may do; ours may write to the repo, and we hold it to
one subtree by what it commits. We use it because the accrual must happen on a
clock nobody watches, every week, for months.

## The central constraint

**The weekly bot writes numbers, under `data/snapshots/` only, and nothing
else moves.** The rating series accrues as tracked figures; the hand-read
`data/snapshots/manual_snapshots.csv` point (3.9/1,072 and 4.9/13,000) is
untouched; no review body, no personal datum and no brand token enters a
tracked file or a commit message; the no-network offline rebuild stays green;
and the row tags for B1.2–B1.4 stay **Documented** (a single fetched point is
Measured, but the series is not yet ours to call Measured — BACKING's note).

## DONE command

```
make test && make idempotency-check ROWS=captured
```

- `make test` — the pins below: the harvest is idempotent and numbers-only,
  `read_fetched_snapshots` maps the tracked file to `origin=fetch` rows (absent
  file → zero rows), the workflow scrapes exactly the fetchable set, and
  `weekly.yml` has the scheduled trigger, the scoped write permission and the
  data/snapshots-only commit.
- `make idempotency-check ROWS=captured` — the tracked fetched-snapshots path
  loads twice into one fresh database with identical per-table counts, offline,
  no key, no fetch: the persisted series is deterministic. (The brief's own
  Done-when — "two scheduled runs visible in Actions history" — is observed
  over weeks, so it is a post-merge ops check, recorded in BACKLOG, not a CI
  gate.)

## Done-when

1. **The fetched series has a tracked, offline home.** A capture's snapshot
   figures persist as numbers in the tracked `data/snapshots/fetched_snapshots.csv`
   with `origin = fetch`; `make rebuild ROWS=captured` loads them with no
   network, and a missing file is zero rows (a fresh clone before the first
   run). *Evidence: row 1.*
2. **The harvest is deterministic and numbers-only.** Recording twice from the
   same capture appends no new row (key = `source`, `captured_at`); every
   written cell is a source slug, a day or one of the five snapshot figures —
   never a review body, an address or a brand token. *Evidence: row 2.*
3. **The weekly commit touches only `data/snapshots/`.** The workflow stages
   paths under `data/snapshots/` and nothing else, under `permissions: contents:
   write`, with a fixed, brand-free commit message. *Evidence: row 3.*
4. **Only fetchable sources are fetched, politely.** The weekly run scrapes
   exactly `fetchable_sources()` — skipping the App Store feed, the App Store
   listing and both Trustpilot sources — through `make confirm scrape`: robots
   first, ≥ 2 s per host, identifying User-Agent, ≤ 60 pages per source, no
   proxy, no retry. *Evidence: row 4.*
5. **The workflow runs on a clock, on no untrusted input.** `weekly.yml`
   triggers on `schedule` (cron) and `workflow_dispatch` only — never
   `pull_request` — so its runner environment (`MAKEFILES`, `PATH`) is the
   repo's own, which closes the Phase 3a residual about an environment that
   chooses what `make` reads. *Evidence: row 5.*
6. **The series stays Documented and the offline series is stable.** `make
   idempotency-check ROWS=captured` gives identical counts across two rebuilds;
   B1.2–B1.4 keep their **Documented** tag (a fetched point is Measured, the
   series is not yet). *Evidence: row 6.*

(6 items. Each is a contract the code can falsify.)

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `tests/test_harvest.py::test_fetched_snapshots_load_as_fetch_origin`, `::test_absent_fetched_file_is_zero_rows` / `make rebuild ROWS=captured` |
| 2 | `tests/test_harvest.py::test_recording_twice_adds_no_row`, `::test_recorded_cells_are_numbers_and_slugs_only` |
| 3 | `tests/test_weekly.py::test_workflow_commits_only_data_snapshots`, `::test_workflow_has_scoped_write_permission`, `::test_commit_message_is_fixed_and_brand_free` |
| 4 | `tests/test_weekly.py::test_workflow_scrapes_exactly_the_fetchable_set` |
| 5 | `tests/test_weekly.py::test_workflow_triggers_on_schedule_and_dispatch_only` |
| 6 | `make idempotency-check ROWS=captured` prints "idempotent"; `tests/test_backing.py::test_rating_rows_stay_documented` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all captures the weekly run records, the tracked file carries only source slugs, days and the five snapshot numbers — no review body, no address, no brand token. | `tests/test_harvest.py::test_recorded_cells_are_numbers_and_slugs_only` — a capture whose review body names a condition and whose address spells the brand; the recorded rows contain neither. |
| For all fetched snapshot keys already in the tracked file, recording again changes nothing. | `tests/test_harvest.py::test_recording_twice_adds_no_row` — the same capture harvested twice; the file's row set is unchanged. |
| For all sources the weekly run fetches, the source is declared `fetchable=True`. | `tests/test_weekly.py::test_workflow_scrapes_exactly_the_fetchable_set` — the not-fetchable App Store and Trustpilot sources appear in no fetched row and no scrape line. |
| For all runs of the weekly workflow, every path it commits is under `data/snapshots/`. | `tests/test_weekly.py::test_workflow_commits_only_data_snapshots` — the workflow's staging step names `data/snapshots/` and no other path. |
| For all rebuilds, an absent or header-only fetched file yields zero fetch-from-file rows and a count stable across two runs, with no network and no key. | `tests/test_harvest.py::test_absent_fetched_file_is_zero_rows`; `make idempotency-check ROWS=captured`. |
| For all fetched points, the point loads as Measured but the B1.2–B1.4 row tag stays Documented. | `tests/test_backing.py::test_rating_rows_stay_documented` — the BACKING rows for the series still read `Documented`. |

## Pinned decisions (do not re-litigate)

- **The tracked path is a numbers-only file, not a tracked capture root.**
  `data/snapshots/fetched_snapshots.csv` holds the fetched snapshot figures in
  the shape of `manual_snapshots.csv` — a source slug, a day and the five
  figures; the loader derives the address, profile, segment and channel from
  the declaration in `ingest/sources.py` (D1), so the brand never enters the
  file. *Rejected: a tracked capture root under `data/snapshots/`, which would
  commit review bodies and force the unwritten personal-data excerpt rule
  (BACKLOG "Health details arrive in review bodies") now.* Satisfies the
  numbers-only and no-personal-data invariants. Closes BACKLOG "Phase 4 has no
  tracked path into `platform_snapshots`".
- **A new non-network command harvests captures to the tracked file.** `make
  record-snapshots` (subcommand `python -m pipeline record-snapshots`) reads
  the freshest capture per fetchable, parsed source via `read_captures` (the
  one parser path — no duplicated extraction), and appends each unseen
  `(source, captured_at)` snapshot as numbers. It takes no variable, deletes
  nothing, calls no paid API and touches no network, so it needs no `confirm`
  gate. *Rejected: folding the write into `rebuild`, which would give a rebuild
  a tracked-write side effect.* Satisfies the idempotent-harvest invariant.
- **`rebuild ROWS=captured` also reads the tracked fetched file.** A new
  `read_fetched_snapshots()` maps it to `origin=fetch` rows, loaded through the
  existing `load_snapshots` guard; live captures under `data/cache/` are still
  read too, and the snapshot natural key + hash makes the overlap a no-op.
  *Rejected: reading the tracked file instead of the cache, which would hide a
  freshly fetched point until the next commit.* Satisfies the offline-stable
  invariant.
- **The workflow is `schedule` + `workflow_dispatch`, never `pull_request`.**
  It runs on the repo's own trusted runner on a weekly cron (manual dispatch
  for a first proof), so `MAKEFILES`/`PATH` are the repo's, not an attacker's;
  it runs `make confirm scrape` as one command (the `confirm` and `scrape`
  goals in one invocation), then `make record-snapshots`, then commits. This
  closes the Phase 3a residual "the confirm gate does not hold against an
  environment that chooses what make reads": in this context the environment is
  the runner's own. Satisfies the untrusted-input invariant.
- **The commit is one bot identity, one fixed message, `data/snapshots/`
  only.** The message is a brand-free template (`data: weekly snapshot
  <YYYY-MM-DD>`); the workflow `git add data/snapshots/` and commits only if
  that path changed. The D1 brand-token walk is extended over the commit
  message it writes. Satisfies the commit-scope invariant. Closes BACKLOG "The
  D1 walk covers tracked files, not commit messages" for the weekly commit.
- **B1.2–B1.4 stay Documented; only the source cells gain the tracked file.**
  A handful of weekly points do not make the series ours to call Measured
  (BACKING's rating-row note); the BACKING source cells for B1.2–B1.4 add
  `data/snapshots/fetched_snapshots.csv` as the Measured points' tracked home.
  *Rejected: flipping the row tag to Measured now.* Satisfies the tag
  invariant.

## Scope (files)

- `.github/workflows/weekly.yml` — new: the scheduled scrape + harvest + commit.
- `pipeline/cli.py`, `pipeline/__main__.py` — the `record-snapshots` subcommand.
- `pipeline/build.py` — `read_fetched_snapshots()`; `rebuild ROWS=captured`
  reads it; the harvest reader/writer for the tracked file.
- `Makefile` — the `record-snapshots` target (and `make help`).
- `data/snapshots/fetched_snapshots.csv` — new tracked file, header row only at
  first (no fabricated Measured numbers land before the first real run).
- `tests/test_harvest.py`, `tests/test_weekly.py` — new; `tests/test_backing.py`
  (or the existing BACKING test file) for the tag check; `tests/pins.py`.
- `BACKING.md` — B1.2–B1.4 source cells gain the tracked file.
- `DECISIONS.md` — Phase 4 entry; supersede pointer on the Phase 3a
  environment-residual note.
- `BACKLOG.md` — rows closed and re-deferred (see Record updates).
- `CLAUDE.md` — Current status, Commands (`record-snapshots`), Repo map
  (`weekly.yml`, the tracked file), BACKLOG count, the one-exception note.
- `README.md` — the weekly command and what accrues.
- this spec — the "Delivered" paragraph at exit.

Freeze: none

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 4 entry; supersede the Phase 3a "environment that
  chooses what make reads" residual (trusted runner, schedule-only)
- [ ] `BACKLOG.md` — closed: "Phase 4 has no tracked path into
  `platform_snapshots`", "The D1 walk covers tracked files, not commit
  messages" (weekly commit); re-deferred with new triggers: "Health details
  arrive in review bodies" (numbers-only path carries none — trigger moves to
  Phase 9 excerpts), "A re-fetch reads every page of a review profile"
  (stop-at-known-page), "An Opinion Assurances review's id is a content hash"
  (edit counting on two real captures), "read_captures parses every capture
  into memory", the hashed naming-check row
- [ ] `CLAUDE.md` — Current status; Commands (`record-snapshots`); Repo map;
  BACKLOG count; the `main`-commit exception now realized
- [ ] `BACKING.md` — B1.2, B1.3, B1.4 source cells gain
  `data/snapshots/fetched_snapshots.csv` (tag stays Documented)
- [ ] `SPEC.md` — none (no chart or beat changes)
- [ ] `README.md` — the weekly command and the accrual sentence
- [ ] this spec — the "Delivered" paragraph appended at exit

## Threat model (REQUIRED)

The new target `record-snapshots` takes no variable, deletes nothing, calls no
paid API and touches no network — it reads captures from disk and appends
numbers to one tracked file. The network target the workflow invokes, `make
confirm scrape`, is unchanged from Phase 2 / 3a; its threat model (the
`confirm` goal gate, `$(origin)`, the empty / `../x` / `"; ` / env-exported
`SOURCE`) holds unchanged and `record-snapshots` adds no `SOURCE` surface. The
new residuals are the unattended run and the write token:

| Target / context | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `record-snapshots` (no variable) | n/a — takes no variable; reads all fetchable captures | n/a | n/a | n/a | n/a | `tests/test_harvest.py` (path is derived, not passed) |
| `confirm scrape` in the workflow | — | — | — | goals come from the workflow's own command line, origin `command line`, arms | `command line` | `tests/test_makefile.py` (unchanged) |

- **Write token.** `permissions: contents: write`, no other scope; the token
  cannot be scoped to a path, so the subtree limit is enforced by what the
  workflow commits (`git add data/snapshots/`) and by branch protection's one
  written exception. Pinned by `tests/test_weekly.py`.
- **No secret in the workflow.** The scrape needs no API key (no model on this
  path); no `.env`, no key echoed; `persist-credentials` handled as in `ci.yml`.
- **Run twice.** A second run in the same week fetches again (polite, ≤ 60
  pages/source) and harvests; the `(source, captured_at)` key makes a same-day
  re-run a no-op in the tracked file, and an empty diff commits nothing.
- **No credentials.** With no scrape possible (a source refuses, or robots
  disallows), the run fetches nothing, harvests nothing, and the commit step
  sees an empty diff and exits clean — never a fake row.

## Review & stack risk

Agents are selected by diff surface (CLAUDE.md → "Which review agents run").

- **code-reviewer** (triggered — `Makefile`, `pipeline/**`, `tests/`): the
  harvest reuses the one parser path, no duplicated extraction; the loader
  keys on the snapshot natural key; no clock on the data path (the day is
  `captured_at`, stamped at fetch); the tracked file is numbers-only.
- **security-reviewer** (mandatory — `.github/**`, a network run, a write
  token): the token scope, no secret, scrape conduct unchanged, the commit
  scope, schedule-only trigger, the D1 walk over the commit message.
- **functionality-tester** (triggered): the DONE command, the harvest idempotency
  and numbers-only pins, the absent-file zero-rows path, the fetchable-only set,
  the no-key/no-network rebuild.
- **study-editor** (triggered — `CLAUDE.md`, `README.md`, `BACKING.md` claims
  change): neutrality of the accrual sentence and the tag note.
- **coherence-auditor** at exit: no stale sentence claiming captures reach only
  the gitignored cache; the `main`-commit exception now reads as realized, not
  promised; BACKING's rating-row note still matches the code.
- Stack risk (first hour, STOP and report before any workaround; findings →
  DECISIONS → Gotchas): GitHub Actions cron drift and the default-branch push
  permission model; that `make confirm scrape`'s goal-origin reads `command
  line` inside a workflow `run:` step; that a scheduled workflow on a fork or a
  quiet repo is disabled by GitHub after 60 days of inactivity (a manual
  dispatch keeps it live).

## Out of scope (deferred, recorded)

- **A live/scheduled Trustpilot fetch or review-corpus accrual** — BACKLOG "A
  live Trustpilot fetch and a scheduled refresh are not built" and the
  reviews-corpus accrual stay deferred; Phase 4 accrues snapshot figures only.
- **Stop-at-first-known-page** — BACKLOG "A re-fetch reads every page of a
  review profile"; the weekly run re-reads all pages politely for now.
- **Edit-counting across captures** — BACKLOG "An Opinion Assurances review's
  id is a content hash"; needs two real weekly captures to measure.
- **A per-capture generator for `read_captures`** — BACKLOG row; today's cache
  is small.
- **The hashed brand-name check** — BACKLOG "Naming-the-target check is
  agent-only"; the weekly commit is a fixed brand-free template, so the name
  cannot leak through it by construction; the D1 walk is extended to the
  message.
