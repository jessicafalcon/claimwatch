-- cost_model_outputs — each cost-model formula printed next to the value it
--   produces, per scenario (B3.1, SPEC.md Beat 3).
-- Grain: one row per (scenario, formula) — the twelve point formulas and the two
--   curve crossovers, over the four §7 scenarios (baseline, contacts_once,
--   churn_halved, both). 4 x 14 = 56 rows.
-- A Python-fed mart: this file is DDL only (the fixed shape);
--   pipeline/build.py::write_model_marts fills it from models/cost_model.py, the
--   one place the formulas are written — the printed `expression` and the
--   computed `value` are one entry there, so they cannot drift. No arithmetic in
--   SQL — that keeps the SQL portable.
-- Columns: expression is the formula as text (what the study prints); value is
--   it evaluated at the defaults for that scenario, rounded at the one site. A
--   curve formula whose crossover never happens stores value NULL.
-- Provenance: run_id names the build; no source_url, no captured_at, no clock.
-- Tag: Modeled (the deterministic model's own output).
-- Reader rule: B3.1 prints every point row (the model formulas and the three
--   hold-timer formulas loop_days, friction_per_day, timer_amount_eur); B4.2
--   reads only those three hold-timer rows, at the baseline scenario.
-- Feeds: B3.1; and B4.2 indirectly — its three hold-timer rows here are read at
--   baseline into sla_threshold, B4.2's mart of record.
create or replace table cost_model_outputs (
    scenario varchar,
    name varchar,
    expression varchar,
    value double,
    run_id varchar,
    tag varchar
);
