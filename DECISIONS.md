# DECISIONS.md — why-not-X log

One entry per non-obvious choice. **"Decisions still in force"** (first) is the
binding set — ≤ 15 entries, by component, each linking to the phase entry that
argued it. **"Process"** records how the phases are run. **"Gotchas"** records
stack surprises found live. **"Appendix — by phase"** is the full log, oldest
first; an entry a later phase reverses is annotated **Superseded by …** in
place and never deleted.

## Decisions still in force

**Method**

- **Deterministic first; a language model decides in exactly one place.**
  Rules, SQL and arithmetic decide everything that can be decided that way;
  the model reads only the reviews the rules could not label, its output
  passes an eval gate before any chart uses it, and with no API key the
  pipeline still runs and shows a gray "unclassified" band. ([Brief §2.1](PROJECT_BRIEF.md); [Phase 0a](#phase-0a))
- **Every number carries one of four evidence tags**, and every model default
  is either sourced or visibly declared unsourced. `BACKING.md` is the
  contract; `make check-backing` enforces the mechanical half. ([Brief §2.4](PROJECT_BRIEF.md); [Phase 0a](#phase-0a))
- **No dbt, no ORM, no vector store, no cloud VMs.** At ~8 SQL files plain
  SQL is clearer than a framework; knowing when not to use a tool is part of
  the study. ([Brief §2.2](PROJECT_BRIEF.md))

**Data**

- **Publish aggregates and code, never the raw review corpus.** The corpus
  is gitignored; hand labels are stored as ids plus labels, no text; CI and
  tests run on a hand-written synthetic fixture; a fresh clone scrapes before
  real charts appear. ([Phase 0a](#phase-0a), PLAN §6.1)
- **Scrape politely, never evade.** Low rate, identifying User-Agent,
  robots.txt honoured, pages cached. If a platform blocks, the fallback is a
  manually captured snapshot tagged Measured — not circumvention. Each
  source's terms position is recorded here when its scraper lands.
  ([Phase 0a](#phase-0a), PLAN §6.2)

**Process**

- See the Process section below.

## Process

- **Workflow machinery established before any pipeline code (2026-09-01).**
  Adapted from the sibling project `ontime-rate-recovery-pipeline`
  (`docs/PLAN.md` §2 has the piece-by-piece verdicts). Three load-bearing
  mechanisms: a spec layer (`specs/TEMPLATE.md`: Invariants / Evidence /
  Record updates / Threat model, one DONE command); phase = branch = PR =
  review gate (`/review-round`, STOP-on-findings, the two-round cap, the
  developer merges); pins and a frozen synthetic fixture so "did it work" is
  a command. The offline guards (`review_gate.py`, `check_docs.py`,
  `check_backing.py`, `review_common.py`) carry their hardening from day one
  (spec-path validation, unexpanded `$(value)` + `_Q` quoting, one-line
  refusals) rather than earning it incident by incident.
- **Phase 0 split into 0a (machinery) and 0b (contracts); Phase 5 into 5a
  (label sample + wall) and 5b (rules).** The brief's rule "done-when is a
  test or make target" needs the gate to exist before the contracts it checks;
  hand-labeling is human hours, not a session. Numbering otherwise follows
  PROJECT_BRIEF.md §9; each phase's contract is its spec in `specs/`, and the
  "Delivered" paragraph is appended to the spec, never to the brief.
- **No mutation sweep, no round tags.** The reference's `mutate.py` and
  `round_tag.py` (~26 KB plus tests) earned their keep on multi-branch SQL and
  a write-back contract; nothing here has that shape yet. BACKLOG row with a
  trigger. `/review-round N` ranges over `main...HEAD`; N is a label.
- **Review agents are selected by diff surface, not run wholesale.** Table in
  CLAUDE.md; `/review-round` classifies `git diff --name-only` and prints the
  list before spawning. A fifth agent, `study-editor`, exists because this
  project's deliverable is prose with rules (brief §2.3, §2.5) that no code
  reviewer checks.
- **The run-tests hook is wired locally, not committed.** A committed
  `settings.json` would auto-execute an inbound branch's hook for anyone
  opening the repo in Claude Code; `tests/test_claude_config.py` pins that
  only agent/command prose and hook scripts are tracked.
- **Naming.** Package and project name `friction_ledger` / "The Friction
  Ledger"; the directory `claimwatch` is left alone (a rename buys nothing
  and breaks the remote).

## Gotchas (stack surprises found live)

None yet. Each entry: the surprise, the official-docs check, what we did.

## Appendix — by phase

### Phase 0a

Branch `phase-0a-machinery`, spec `specs/phase-0a-machinery.md`. The ten
defaults from `docs/PLAN.md` §6, approved 2026-09-01:

1. **Corpus vs. clone-and-run** — labels as ids + labels, corpus gitignored,
   synthetic fixture for CI; a fresh clone scrapes first.
2. **Trustpilot terms** — polite fetch; on refusal, the manual snapshot path;
   no evasion.
3. **Metabase open-source has no dashboards-as-code** — Phase 9 drives it
   through the HTTP API from a small YAML, idempotently; the static HTML
   export is the permanent artifact.
4. **A bot committing to `main`** — one written exception: the weekly
   workflow's identity commits only under `data/snapshots/`; a CI check
   refuses any other path from that author (Phase 4).
5. **Model API** — the Anthropic API via the `anthropic` package (Phase 6);
   key in `.env` only; prompt and model id versioned in `classified_reviews`.
6. **Naming** — `friction_ledger`; directory unchanged.
7. **Phase 0 split** — 0a machinery, 0b contracts.
8. **Hand labeling** — human hours between 5a and 5b; planned on the
   calendar, not in a session.
9. **Open DAMIR is large** — Phase 7 fetches one or two months, filters,
   caches under `data/`, records file names and hashes in BACKING; nothing
   large is committed.
10. **Naming-the-target check** — agent-only for now (BACKLOG row).

Also decided in this phase: Python 3.12 via `uv`, dev dependencies only
(`pytest`, `ruff`, `pre-commit`); `duckdb` lands in Phase 1. `check_backing.py`
lets a **Pending** row name a SQL file not built yet — the brief writes BACKING
before code, so every row starts Pending and flips when its mart lands;
requiring the file for Pending rows would make Phase 0b un-passable. The
hook's matcher is widened to `.sql` and `.yaml`: SQL files and `rules.yaml`
are code in this repo.
