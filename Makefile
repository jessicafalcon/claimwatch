# The Friction Ledger — one command per stage. `make help` lists them.
# Pipeline targets land with their phases (CLAUDE.md → Commands):
# rebuild, idempotency-check, reset (Phase 1); scrape (2); label-sample,
# classify-eval (5); model (8); study (9).

.PHONY: help setup test lint check-docs check-backing review-gate \
        rebuild idempotency-check reset

# User variables reach recipes ONLY as make values via `$(call _Q,$(value VAR))`
# — UNEXPANDED and single-quoted — so a value like `SPEC='$(shell …)'` or
# `"; rm x; "` from EITHER origin reaches Python as one literal argument and no
# shell or make function runs on it; Python validates. `unexport` is hygiene
# only (keeps the value out of the child's environment) — an environment-set
# variable still reaches the recipe. The only way to tell command line from
# environment is `$(origin VAR)`; the destructive `reset` passes
# `$(origin CONFIRM)` to Python, which confirms only on `command line`
# (specs/TEMPLATE.md → Threat model; pinned by tests/test_makefile.py).
unexport SPEC BASE TARGET FIXTURE CONFIRM
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

rebuild: ## build the warehouse from raw [TARGET=duckdb] [FIXTURE=empty|synthetic]
	uv run python -m pipeline rebuild --target=$(call _Q,$(value TARGET)) --fixture=$(call _Q,$(value FIXTURE))

idempotency-check: ## rebuild twice, diff per-table row counts (run-twice property)
	uv run python -m pipeline idempotency-check --target=$(call _Q,$(value TARGET)) --fixture=$(call _Q,$(value FIXTURE))

reset: ## DESTRUCTIVE drop the DuckDB file — needs CONFIRM=yes on the command line
	uv run python -m pipeline reset --target=$(call _Q,$(value TARGET)) --confirm=$(call _Q,$(value CONFIRM)) --confirm-origin=$(call _Q,$(origin CONFIRM))
