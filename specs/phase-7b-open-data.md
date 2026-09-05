# Phase 7b — Open data: DAMIR slice + fitted claim-cost distribution (PROPOSED)

Contract for the `phase-7b-open-data` branch. Source: PROJECT_BRIEF.md §7 and
§9 Phase 7 ("Findings marts + open-data calibration"), the open-data half of
the Phase 7 split (7a, the theme-share marts, merged as PR #14). Depends on
Phase 7a merged.

**Status: APPROVED 2026-09-04 — in progress.** No new dependency: the
DAMIR fetch is a plain bulk file download over stdlib `urllib.request` (so
`ingest/fetch.py` stays the only `httpx` import); the fit is stdlib `statistics`
+ `math`.

## Why

Beat 3 puts a euro figure on a wrongly held claim, and Beat 4's simulator draws
synthetic claims from "cost distributions fitted to real public reimbursement
data, with the fit shown" (PROJECT_BRIEF.md §7). Those distributions need a real,
sourced anchor and a fit anyone can redo by hand. This phase lands that anchor —
a frozen slice of Open DAMIR and the lognormal fit computed from it — so Phase 8
(the cost model and the guardrail simulator) has sourced numbers to consume. It
is not a fix PR: it is the second half of the planned Phase 7 open-data work,
scoped out of 7a to keep that phase's cap (7a spec, "Out of scope").

The cost model and the simulator themselves are Phase 8. This phase lands **no
mart** and **flips no BACKING row**: B3.3 (`cost_model_params`) and B4.3
(`guardrail_sim`) stay Pending because their marts are Phase 8. 7b makes their
already-named `open-damir` upstream real.

*Teaching note (lands in code/README at build).* Open DAMIR is France's public
open dataset of **aggregated** health-insurance reimbursements — monthly CSVs
since 2009, no individual people in them. We take one month's reimbursement-
**amount** column and fit a lognormal curve: two numbers, the average and spread
of the **logarithms** of the amounts (health costs are lognormal — a few big
claims sit far above many small ones). `mu = mean(ln x)`, `sigma = std(ln x)` is
plain arithmetic anyone can redo in a spreadsheet, and it is exactly the best
lognormal fit — no solver, no black box. Boring on purpose: a closed-form formula
you can check by hand is trustworthy in a way an optimizer's output is not.

## The central constraint

**The DONE command is fully offline and reproduces the sourced fit from the
frozen fixture alone.** The real DAMIR download is developer-run, never in CI,
never by an agent; the committed fit and every pinned number are computed from
`fixtures/damir/` (a small, real, brand-free DAMIR slice), so anyone re-running
`make fit-damir` gets byte-identical output with no network and no key.

## DONE command

```
make fit-damir && make idempotency-check ROWS=synthetic && make check-backing && make test
```

- `make fit-damir` — recompute the lognormal fit over `fixtures/damir/`, write
  `data/damir/claim_cost_fit.csv`, print `mu`, `sigma`, `n` and the
  goodness-of-fit decile table; a second run writes byte-identical output.
- `make idempotency-check ROWS=synthetic` — proves 7b touched no rebuild path
  (no mart, no new raw table): row counts unchanged, as before.
- `make check-backing` — B3.3/B4.3 still Pending; no new mart to name.
- `make test` — pins `mu`, `sigma`, the GoF deciles, the committed-artifact ==
  recompute equality, the domain guard, and the fetch target's gate/variable
  refusals. Green with the key unset (no model on this path).

## Done-when

1. **The fit is computed by plain arithmetic over the fixture.** `make fit-damir`
   reads `fixtures/damir/`, computes `mu = mean(ln x)` and `sigma =
   population-std(ln x)` over strictly-positive amounts, and prints `mu`,
   `sigma`, `n`. *Evidence: row 1.*
2. **The fit is reproducible by hand and pinned.** A test reproduces `mu` and
   `sigma` from the fixture with stdlib `statistics` and asserts the pinned
   values. *Evidence: row 2.*
3. **The tracked artifact equals the recomputed fixture fit.** The committed
   `data/damir/claim_cost_fit.csv` equals what `fit-damir` recomputes — no drift,
   byte-identical on re-run. *Evidence: row 3.*
4. **The fit is shown.** `fit-damir` and the artifact carry a goodness-of-fit
   table: each decile's empirical amount boundary vs the lognormal-predicted
   boundary `exp(mu + sigma·z_p)` with the `z_p` constants printed. *Evidence:
   row 4.*
5. **The amount column is guarded as a foreign shape.** The slice reader accepts
   only numeric amounts `> 0`; every other row is dropped and counted, and the
   count is printed — never silently absorbed. *Evidence: row 5.*
6. **The fetch is confirm-gated, developer-run, and validates its variable.**
   `make fetch-damir` refuses without `make confirm fetch-damir` (exit 2) and
   refuses an empty / path-escaping / metacharacter / env-exported `MONTH`;
   `MONTH` is validated in Python against a closed `YYYY-MM` shape. *Evidence:
   row 6.*

## Evidence (REQUIRED)

| Done-when | Proof (test id / `make` target / output line) |
|---|---|
| 1 | `make fit-damir` prints the fit; `tests/test_damir.py::test_fit_reproducible_by_hand`, `::test_fit_is_the_lognormal_mle`, `::test_fit_params_over_fixture` (skips until the fixture exists) |
| 2 | `tests/test_damir.py::test_fit_reproducible_by_hand` (recomputes `mu`/`sigma` the hand way) |
| 3 | `tests/test_damir.py::test_artifact_equals_recompute` (skips until fixture) and `::test_write_fit_is_byte_identical_on_rerun` |
| 4 | `tests/test_damir.py::test_goodness_of_fit_deciles`; `make fit-damir` prints the decile table |
| 5 | `tests/test_damir.py::test_amount_domain_guard_drops_and_counts`, `::test_parse_amount_keeps_only_positive_numbers`, `::test_read_amounts_refuses_a_file_without_the_column` |
| 6 | `tests/test_damir.py::test_fetch_damir_refuses_without_the_confirm_goal`, `::test_confirm_arms_fetch_damir_and_the_armed_path_proceeds`, `::test_fetch_damir_month_validation_refuses_before_any_network` |

## Invariants (REQUIRED)

| Invariant ("for all …, … holds") | Falsified by (scenario test) |
|---|---|
| For all runs of `fit-damir` on the same slice, the output numbers are identical (no clock, no RNG, closed-form). | `tests/test_damir.py::test_fit_is_deterministic`, `::test_write_fit_is_byte_identical_on_rerun`. |
| For all amounts fed to the fit, `mu`/`sigma` equal `mean`/`population-std` of their natural logs — the arithmetic anyone can redo. | `tests/test_damir.py::test_fit_reproducible_by_hand` — recompute independently. |
| For all rows in the slice, only a numeric amount `> 0` reaches the fit; every other row is dropped and counted. | `tests/test_damir.py::test_amount_domain_guard_drops_and_counts` — a slice with a blank, text, `0`, `-5`. |
| For all committed states, `data/damir/claim_cost_fit.csv` equals the fit recomputed from `fixtures/damir/`. | `tests/test_damir.py::test_artifact_equals_recompute` (skips until the fixture exists). |
| For all invocations, the DAMIR fetch runs only when `confirm` armed it in the same make process and `MONTH` matches `YYYY-MM`. | `tests/test_damir.py::test_fetch_damir_refuses_without_the_confirm_goal`, `::test_fetch_damir_month_validation_refuses_before_any_network`. |
| For all of 7b, no `sql/marts/*.sql` is added and no BACKING tag flips (marts are Phase 8). | `make check-backing`; `tests/test_damir.py::test_no_new_mart_files_and_marts_are_phase_8`. |

## Pinned decisions (do not re-litigate)

- **Lognormal by log-moments.** `mu = mean(ln x)`, `sigma = population-std(ln x)`
  over strictly-positive reimbursement amounts — closed-form, hand-checkable, and
  identical to the lognormal MLE; no optimizer, no fitted predictive model
  (brief §2.1). Rejected: gamma method-of-moments (less standard for claim cost),
  empirical deciles only (no `mu`/`sigma` to show). Satisfies invariants 1–2.
- **The frozen fixture is the sourced sample; the fit is pinned over it.**
  `fixtures/damir/` holds a small, hand-trimmed, real DAMIR slice — the amount
  column only, numbers-only, brand-free (DAMIR names no insurer) — with a
  `MANIFEST.sha256`, read-only after 7b. CI reproduces the sourced fit offline
  from it. Rejected: pinning over the gitignored real slice (not reproducible in
  CI). Satisfies the central constraint.
- **The fit artifact is tracked, derived, numbers-only.**
  `data/damir/claim_cost_fit.csv` (a new `!data/damir/` gitignore negation, the
  `data/snapshots/` precedent) holds `mu`, `sigma`, `n` and the GoF decile rows;
  written by `make fit-damir`; a test asserts it equals the recompute. Phase 8
  reads this file. Rejected: recompute-only with nothing tracked (Phase 8 would
  have no committed anchor). Satisfies invariant 4.
- **The DAMIR fetch is a new confirm-gated network target.** `make confirm
  fetch-damir [MONTH=YYYY-MM]`, developer-run, never by an agent; writes the
  gitignored `data/cache/damir/`. `GATED` in `pipeline/cli.py` extends to
  `("reset", "scrape", "fetch-damir")` — the same closed-set gate. `MONTH`
  validated in Python (closed `YYYY-MM`), path derived in Python, single-quoted
  and `unexport`ed. Rejected: folding into `make scrape` (mixes review-platform
  robots/source logic with a plain bulk download). Satisfies invariant 5.
- **stdlib `urllib` for the download; no clock on the fit path.** The fetch is a
  plain bulk GET with an identifying User-Agent (no proxy, no evasion, no retry),
  so `ingest/fetch.py` stays the only `httpx` import and no dependency is added.
  The fit reads amounts as-is: no `now()`/`current_date` anywhere. Rejected: a
  second `httpx` site (distorts the stated single-import convention). Satisfies
  invariant 1 and brief §2.1.
- **No mart, no BACKING flip in 7b.** 7b lands upstream data + the fit only.
  B3.3 (`cost_model_params`) and B4.3 (`guardrail_sim`) stay Pending; their marts
  are Phase 8. BACKING's `open-damir` upstream cell for those rows is annotated to
  resolve to `fixtures/damir/` + the fit artifact; tags do not move. Satisfies
  invariant 6.

## Scope (files)

- `opendata/__init__.py` — new package (open-data ingest + fit; distinct from
  `ingest/` review scrapers and Phase 8 `models/`).
- `opendata/sources.py` — the DAMIR dataset declaration: the monthly-file URL
  template, the amount column name, the slice spec. One place; brand-free.
- `opendata/fetch.py` — stdlib-`urllib` bulk download of `MONTH` into
  `data/cache/damir/` (developer-run, confirm-gated via the CLI).
- `opendata/slice.py` — read a fetched CSV or the fixture, apply the positive-
  numeric amount guard (drop-and-count), return the amounts.
- `opendata/fit.py` — the log-moments lognormal fit + GoF deciles; writes
  `data/damir/claim_cost_fit.csv`.
- `pipeline/cli.py` — wire `fetch-damir` (confirm-gated) and `fit-damir`
  (offline); extend `GATED`.
- `Makefile` — `fetch-damir`, `fit-damir` targets; `.PHONY`; help lines.
- `fixtures/damir/` — the frozen real DAMIR slice + `MANIFEST.sha256`.
- `data/damir/claim_cost_fit.csv` — the tracked fit artifact.
- `.gitignore` — add `!data/damir/`.
- `tests/test_damir.py`, `tests/pins.py` — the pins.

Freeze: none

(`fixtures/damir/` is created new in this phase — it is not a re-freeze, so no
`Freeze:` grant is needed; it becomes read-only after 7b.)

## Record updates (REQUIRED)

- [ ] `DECISIONS.md` — Phase 7b entry: the four settled choices (fixture+fit,
  lognormal log-moments, tracked artifact, confirm-gated `fetch-damir`); the
  `GATED` extension; `urllib`-not-`httpx` gotcha if any.
- [ ] `BACKLOG.md` — rows closed/opened (the real-slice periodic refresh, if
  deferred, is a new row); count updated.
- [ ] `CLAUDE.md` — Current status; Commands (`fetch-damir`, `fit-damir`, the
  `confirm` allowlist now `{reset, scrape, fetch-damir}`); Repo map (`opendata/`,
  `fixtures/damir/`, `data/damir/`); BACKLOG count.
- [ ] `BACKING.md` — B3.3 and B4.3 `open-damir` upstream cell annotated to
  resolve to `fixtures/damir/` + `data/damir/claim_cost_fit.csv`; **tags stay
  Pending** (marts are Phase 8).
- [ ] SPEC.md — none (no chart or beat changes; Beat 3/4 already describe the
  fit "with the fit shown").
- [ ] README — none (no README.md exists yet; it lands in Phase 9). The
  teaching sentence on why the boring closed-form fit lives in
  `opendata/fit.py`'s module docstring until then.
- [ ] this spec — the "Delivered" paragraph appended at exit.

## Threat model (REQUIRED)

`make fetch-damir` is the one new target that touches the network and takes a
variable (`MONTH`). It is developer-run, never by an agent (CLAUDE.md → Paid or
network commands). Settled shape (Phase 3a): one Python process validates
`MONTH`, derives the cache path from it, and acts; the recipe is one line;
`MONTH` reaches Python single-quoted (`$(call _Q,$(value MONTH))`) and
`unexport`ed. `fit-damir` takes no variable, touches no network, deletes
nothing — no gate.

| Target | empty | `../x` | `"; ` | env-exported | `$(origin)` | Pinned by |
|---|---|---|---|---|---|---|
| `fetch-damir` | refuse (no default month; exit 2) | refuse (`YYYY-MM` shape rejects `/`) | refuse (shape rejects `;` and space) | refuse (needs `confirm` goal in the same process; a `MONTH`/goal from the environment cannot arm it) | `confirm` trusts the goal list only when `origin == default` (make's own) | `test_fetch_damir_month_validation_refuses_before_any_network`, `test_fetch_damir_refuses_without_the_confirm_goal`, `test_valid_month_refuses_bad_shapes` |

Run twice: `fetch-damir` re-downloads the month into the cache, overwriting the
same path (no duplicate rows anywhere; the cache is gitignored). No credentials
needed — DAMIR is open data, no key, no account; the fit path never touches the
network or a key, so the no-key run is green by construction.

## Review & stack risk

- **code-reviewer** (triggered — `*.py`, `Makefile`, `tests/`): deterministic
  fit (closed-form, no RNG, no clock), the domain guard as a closed shape, the
  tracked-artifact == recompute pin, scope (feeds B3.3/B4.3 upstream, no mart).
- **security-reviewer** (mandatory — a network target and the `confirm`-gate
  change): fetch conduct (identifying UA, no proxy/evasion/retry), the `GATED`
  extension keeps the closed-set gate intact, no secret, `data/cache/damir/`
  stays gitignored, the tracked slice/fit carry no brand and no personal data
  (DAMIR is aggregate).
- **functionality-tester** (after code-reviewer): the DONE command, the
  fit-by-hand and idempotency proofs, the gate/variable refusals, the no-key run.
- **study-editor** (triggered — README + this spec + BACKING claim wording):
  two-layer voice on the DAMIR/fit explanation; no banned words; DAMIR named as
  aggregate public data, no insurer as subject.
- **coherence-auditor** at exit: SPEC Beat 3/4 "with the fit shown" now has a
  landed fixture + fit; B3.3/B4.3 still Pending and consistent; no stale "Phase
  7b deferred" line left in 7a's spec or CLAUDE.md status.
- Stack risk (verify in the first hour): confirm the DAMIR file URL/format and
  the exact amount column against the official open-data portal BEFORE trimming
  the fixture (the column name and units drive the fit); the frozen fixture must
  be a faithful, representative real slice, not invented numbers. STOP and report
  before any workaround; findings → DECISIONS.md → Gotchas.

## Out of scope (deferred, recorded)

- **`cost_model_params` and `guardrail_sim` marts (B3.3, B4.3)** — Phase 8; 7b
  lands only the upstream fixture + fit they consume.
- **A scheduled / periodic DAMIR refresh** — the weekly cron is review snapshots
  only; a recurring open-data refresh is a BACKLOG row if wanted.
- **data.ameli practitioner-fee distributions** (brief §7) — a second open-data
  source; not needed for the claim-cost fit. BACKLOG.
- **Multiple distribution families / a chosen best-fit contest** — one lognormal,
  shown; alternatives are not part of the deterministic anchor.
