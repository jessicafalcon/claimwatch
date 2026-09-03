# The Friction Ledger — one command per stage. `make help` lists them.
# Pipeline targets land with their phases (CLAUDE.md → Commands):
# rebuild, idempotency-check, reset (Phase 1); scrape (Phase 2); label-sample,
# classify-eval (5); model (8); study (9).

.PHONY: help setup test lint check-docs check-backing review-gate \
        rebuild idempotency-check confirm reset scrape

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
# (spec Phase 3a, A4 (d); pinned by tests/test_makefile.py).
unexport SPEC BASE TARGET ROWS SOURCE
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
	@uv run python -m pipeline confirm --make-pid=$$PPID

reset: ## DESTRUCTIVE drop every DuckDB file this repo built (the corpus and one per rebuild input, past or present) — needs `make confirm reset`
	uv run python -m pipeline reset --target=$(call _Q,$(value TARGET)) --make-pid=$$PPID

scrape: ## NETWORK fetch the declared source(s) into data/cache [SOURCE=<name>] — needs `make confirm scrape`; developer-run
	uv run python -m pipeline scrape --source=$(call _Q,$(value SOURCE)) --make-pid=$$PPID
