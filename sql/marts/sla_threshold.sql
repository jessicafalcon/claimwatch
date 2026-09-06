-- sla_threshold — the computed hold-timer threshold: for each candidate timer
--   day, the claim amount below which a hold that long is net-negative in
--   expectation, and the share of synthetic claims under it (B4.2, SPEC.md Beat 4).
-- Grain: one row per timer day of the fixed grid 1..60, at the baseline
--   parameters. 60 rows. No scenario column — the recommendation is made once,
--   before any fix. Exactly one row (the default timer day) has is_default = true.
-- A Python-fed mart: this file is DDL only (the fixed shape);
--   pipeline/build.py::write_sim_marts fills it from models/guardrail_sim.py and
--   the cost model's timer_amount_eur formula — no arithmetic in SQL, which keeps
--   the SQL portable and the formula one copy in cost_model.py::FORMULAS.
-- Columns: timer_amount_eur is the cost model's threshold at that timer day (it
--   rises with the day up to the loop's length, then holds, because friction
--   stops accruing when the loop ends); share_under is the fraction of synthetic
--   claims below it. timer_days whole (named integer) and is_default boolean, so
--   rebuild's catalog check and Snowflake see one type (the cost_curves precedent).
-- Provenance: run_id names the build; no source_url, no captured_at, no clock.
-- Tag: Modeled (the deterministic model's own output).
-- Feeds: B4.2.
create or replace table sla_threshold (
    timer_days integer,
    timer_amount_eur double,
    share_under double,
    is_default boolean,
    run_id varchar,
    tag varchar
);
