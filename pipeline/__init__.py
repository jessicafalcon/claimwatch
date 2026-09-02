"""The Friction Ledger pipeline — the code that fills the warehouse.

`warehouse` is the one seam that knows DuckDB from Snowflake; `build` runs the
raw -> staging -> marts stages; `sql_lint` is the portability/clock guard used by
the tests. Nothing here calls a model or touches the network (Phase 1)."""
