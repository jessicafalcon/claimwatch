# The Friction Ledger — one command per stage. `make help` lists them.
# Pipeline targets land with their phases (CLAUDE.md → Commands):
# rebuild, idempotency-check, reset (Phase 1); scrape (Phase 2); label-sample,
# classify-eval (5); model (8); study (9).

.PHONY: help setup test lint check-docs check-backing review-gate \
        rebuild idempotency-check confirm reset scrape record-snapshots \
        label-sample classify-eval fetch-damir sample-damir fit-damir

# User variables reach recipes ONLY as make values via `$(call _Q,$(value VAR))`
# — UNEXPANDED and single-quoted — so a value like `SPEC='$(shell …)'` or
# `"; rm x; "` from EITHER origin reaches Python as one literal argument and no
# shell or make function runs on it; Python validates. `unexport` is hygiene
# only (keeps the value out of the child's environment) — an environment-set
# variable still reaches the recipe. No variable can prove a command line:
# `$(origin VAR)` reports `command line` for a definition that arrived through
# MAKEFLAGS in the environment. A GOAL can — MAKEFLAGS carries flags and
# definitions, never goals — so the destructive `reset` and the network
# `scrape` are confirmed by the `confirm` goal in the SAME invocation:
# `make confirm reset`. The `confirm` recipe stamps its make process's id
# (`$$PPID`, the recipe shell's parent); `reset`/`scrape` pass their own and
# Python confirms only when the two are one process, consuming the stamp
# (spec Phase 3a, A4 (d); pinned by tests/test_makefile.py). The stamp is
# created exclusively, so a planted file makes `confirm` itself refuse
# (A8 (d)); `confirm` arms only when the goal after it is `reset` or
# `scrape`, and only from a goal list whose origin is make's own
# (`$(origin MAKECMDGOALS)` is `default` — a definition from the environment,
# MAKEFLAGS or the command line is refused), so no ordinary command leaves an
# armed stamp behind (A9 (a); goals run in order under -j, .NOTPARALLEL
# below). What the gate holds against is a variable definition, an
# environment value, MAKEFLAGS, a stale invocation and a typo; not an
# environment that chooses what make reads or runs (MAKEFILES, PATH), not a
# same-user process writing data/ while make runs — the spec's Threat model
# states both.
# Goals run in order even under -j: `reset` must not start before `confirm`
# has stamped (exit pass, security-reviewer #1; pinned by a -j2 probe).
.NOTPARALLEL:
unexport SPEC BASE TARGET ROWS SOURCE N MONTH
_Q = '$(subst ','\'',$(1))'

help: ## list the targets
	@grep -hE '^[a-z][a-z0-9-]*:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: ## uv sync + pre-commit install
	uv sync
	uv run pre-commit install

test: ## pytest — offline, no services, no network
	uv run pytest

lint: ## ruff via pre-commit (REWRITES files — never run inside a gate)
	uv run pre-commit run --all-files

check-docs: ## links, named make targets, banned words, glossary size, BACKLOG count
	uv run python scripts/check_docs.py

check-backing: ## BACKING rows ↔ sql/marts files ↔ tags ↔ sources ↔ SPEC citations
	uv run python scripts/check_backing.py

review-gate: ## offline gate [SPEC=specs/<f>.md] [BASE=main]; /review-round runs it first
	uv run python scripts/review_gate.py $(if $(value SPEC),--spec=$(call _Q,$(value SPEC)),) --base=$(call _Q,$(if $(value BASE),$(value BASE),main))

rebuild: ## build the warehouse from raw [TARGET=duckdb] [ROWS=captured|none|synthetic|samples]
	uv run python -m pipeline rebuild --target=$(call _Q,$(value TARGET)) --rows=$(call _Q,$(value ROWS))

idempotency-check: ## rebuild twice, diff per-table row counts (run-twice property) [ROWS=synthetic]
	uv run python -m pipeline idempotency-check --target=$(call _Q,$(value TARGET)) --rows=$(call _Q,$(value ROWS))

confirm: ## arm reset or scrape for THIS invocation only: `make confirm reset`, `make confirm scrape`
	@uv run python -m pipeline confirm --make-pid=$$PPID --goals=$(call _Q,$(MAKECMDGOALS)) --goals-origin=$(call _Q,$(origin MAKECMDGOALS))

reset: ## DESTRUCTIVE drop every DuckDB file this repo built (the corpus and one per rebuild input, past or present) — needs `make confirm reset`
	uv run python -m pipeline reset --target=$(call _Q,$(value TARGET)) --make-pid=$$PPID

scrape: ## NETWORK fetch the declared source(s) into data/cache [SOURCE=<name>] — needs `make confirm scrape`; developer-run
	uv run python -m pipeline scrape --source=$(call _Q,$(value SOURCE)) --make-pid=$$PPID

record-snapshots: ## read the captures on disk, append this week's fetched figures to data/snapshots/fetched_snapshots.csv (offline; no confirm gate)
	uv run python -m pipeline record-snapshots

label-sample: ## draw N reviews from the corpus to hand-label into data/label_sample.csv (offline, gitignored; N required)
	uv run python -m pipeline label-sample --n=$(call _Q,$(value N))

classify-eval: ## rules classifier: per-theme precision on the tuning folds vs the synthetic answer key (offline, no variable)
	uv run python -m pipeline rebuild --rows=synthetic >/dev/null
	uv run python -m pipeline classify-eval

fetch-damir: ## NETWORK download one month of Open DAMIR into data/cache/damir [MONTH=YYYY-MM] — needs `make confirm fetch-damir`; developer-run
	uv run python -m pipeline fetch-damir --month=$(call _Q,$(value MONTH)) --make-pid=$$PPID

sample-damir: ## draw a representative fixture from a cached DAMIR month into fixtures/damir [MONTH=YYYY-MM] [N=1000] (offline, developer-run)
	uv run python -m pipeline sample-damir --month=$(call _Q,$(value MONTH)) --n=$(call _Q,$(value N))

fit-damir: ## fit the lognormal to fixtures/damir and write data/damir/claim_cost_fit.csv (offline, deterministic)
	uv run python -m pipeline fit-damir
