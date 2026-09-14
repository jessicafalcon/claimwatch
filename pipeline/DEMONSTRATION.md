# The Snowflake run — a demonstration (Phase 10b)

This walks the one cloud run the brief asks for (§9: "run once against a
Snowflake trial … confirm the DuckDB path still passes — done when both targets
run green"). It is **developer-run, never CI and never an agent's**: it needs a
trial account, the network and trial credits. The DuckDB path is the permanent
one and needs none of this.

*The stack, in plain words.* **Snowflake** is a database that runs in the cloud
instead of in a file on a laptop. The same SQL runs on it; exactly one Python
file (`pipeline/warehouse.py`, the seam) knows which engine is on the other end
of the connection, so the study never depends on the trial — a trial expires,
and nothing load-bearing may sit on it (brief §2).

## What the trial may hold

Fixture inputs only. `ROWS=captured` and `ROWS=samples` are refused on
`TARGET=snowflake` by name, before any connection: the scraped reviews and the
frozen samples are real people's words and never leave the laptop (brief §2.5).
The trial holds at most the synthetic fixture's hand-written reviews and the
`none` input's empty tables, each in its own schema (`friction_ledger_synthetic`,
`friction_ledger_none`), plus a scratch schema during an idempotency check.

## Caution: an exported `.env` spends credits

The cloud path is credential-gated, not `confirm`-gated (like the model key):
with the six `SNOWFLAKE_*` variables exported, any process in that shell — an
agent's `make rebuild TARGET=snowflake` included — can reach the trial and spend
warehouse seconds. The corpus refusal bounds the *data* such a run can hold, not
the *credits* it spends. Keep auto-suspend on for the warehouse so a forgotten
one does not bill idle time, and export the credentials only for the run.

## The walk

```
# 1. Install the optional connector (never installed by `make setup`, CI or the suite)
uv sync --extra snowflake

# 2. Export the six credentials (a password or a programmatic access token; no file)
#    into the shell — see .env.example for the names. Then, for this run only:
set -a; . ./.env; set +a   # export .env for this shell (safe on quoted/spaced values)

# 3. Rebuild the synthetic fixture on Snowflake (all stages; no model key -> the
#    no-key run: ambiguous reviews stay unclassified, the pipeline is still green)
make rebuild TARGET=snowflake ROWS=synthetic

# 4. The run-twice reproducibility check, on Snowflake (a create/drop scratch schema)
make idempotency-check TARGET=snowflake ROWS=synthetic

# 5. The Metabase export, from the Snowflake marts
make publish TARGET=snowflake ROWS=synthetic
```

No console screenshot is committed: the Snowflake console's address bar carries
the account locator and its corner the user, and a terminal screenshot adds
nothing a pasted table does not (neutrality; brief §9's "screenshot" is met by
Phase 10a's committed DAG grid). The deviation is recorded in DECISIONS.

## The DuckDB reference — "both targets run green"

These are row counts of the *synthetic hand-written fixture*, not study
findings — they show the two engines agree table for table, nothing about real
reviews. The same input on the laptop engine, `make idempotency-check
ROWS=synthetic`, table for table. The Snowflake run of the same input prints the
same counts (the SQL is identical; only the connection differs). This table is
Measured on the laptop; the Snowflake counts and schema name below are
Documented-by-hand from the developer's run. The numbers below are the same ones
`tests/pins.py` pins for the synthetic build, so a future synthetic change that
moves a count fails a pin before this doc drifts silently.

```
cost_curves              164
cost_model_outputs        60
cost_model_params         17
determinism_facts          3
guardrail_sim           4000
peer_ratings               4
pipeline_row_counts        3
platform_stats             9
rating_trend               8
raw_platform_snapshots     9
raw_reviews               40
raw_source_pages          26
review_drill              39
sla_threshold             60
stg_classified_reviews    39
stg_platform_snapshots     9
stg_reviews               39
theme_share_by_month      10
theme_share_by_segment     7
idempotency-check OK: every row count unchanged on the second rebuild
```

## The Snowflake run's output — pasted after the developer's run

Filled from the run of step 4 above (Documented-by-hand; the counts match the
DuckDB table table for table, and the schema name is the one the engine
returned — the close of the BACKLOG row that noted the schema name was
unpinnable offline):

```
schema (engine's current_schema()): friction_ledger_synthetic   # e.g.; the run's own answer goes here
<paste the count table from `make idempotency-check TARGET=snowflake ROWS=synthetic` here — it matches the DuckDB table above, count for count>
idempotency-check OK: every row count unchanged on the second rebuild
```

## Why a wrapper and an extra, not an ORM

Two engines, one SQL: the seam wraps each engine's connection in one shape
(`execute`/`executemany`/`executescript`/`close`) and folds each driver's error
into one type, so every other module is engine-blind and the SQL files are
identical. The connector is an optional extra so a laptop clone downloads no
cloud driver it never uses. An ORM would add a dependency and a query language
between the study and its plain, readable SQL — the boring, standard choice here
is the thin wrapper.

## The fake→real trust boundary

The offline test suite proves the seam's Snowflake branch against a hand-written
fake connector (`tests/fake_snowflake.py`): the `qmark` cursor, the
multi-statement `execute_string`, the case-folded catalog answers, and the error
fold. The real driver is never in CI. The five stack-risk points the fake cannot
settle — the trial's login policy, `execute_string` transactions, the catalog's
own spellings, `qmark` binding of a decimal / date / bool, and auto-suspend for
credits — are verified against the connector's official docs in the first hour
of the run and recorded in DECISIONS → Gotchas, alongside the counts and schema
name above.
