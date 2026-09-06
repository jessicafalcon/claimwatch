-- cost_model_outputs — each cost-model formula printed next to the value it
--   produces, per scenario (B3.1, SPEC.md Beat 3).
-- Grain: one row per (scenario, formula) — the nine point formulas and the two
--   curve crossovers, over the four §7 scenarios (baseline, contacts_once,
--   churn_halved, both). 4 x 11 = 44 rows.
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
-- Feeds: B3.1.
create or replace table cost_model_outputs (
    scenario varchar,
    name varchar,
    expression varchar,
    value double,
    run_id varchar,
    tag varchar
);
