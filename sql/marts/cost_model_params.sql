-- cost_model_params — the cost model's parameters, each on a slider (B3.3 the
--   sourced defaults, B3.4 the declared-unsourced sliders; SPEC.md Beat 3).
-- Grain: one row per parameter (models.cost_model.parameters): the four scale
--   anchors, the four DAMIR-fit rows (mu, sigma, emp_p50, emp_mean), the eight
--   unsourced knobs (incl. the two hold-timer knobs days_per_round and
--   timer_days). 16 rows.
-- The third family of Python-fed marts: this file is DDL only (the fixed
--   shape); pipeline/build.py::write_model_marts fills it from
--   models/cost_model.py, the one place the formulas and parameters are
--   written. No arithmetic in SQL — that keeps the SQL portable, and the
--   formulas stay one copy.
-- Columns: default_value, low, high are the slider's value and span. sourcing is
--   'sourced' or 'unsourced'; a sourced row names its citation, an unsourced one
--   leaves citation empty (a declared guess to explore, never a fact).
-- Provenance (a computed parameter set, not a scraped row): run_id names the
--   build; no source_url, no captured_at, no clock on the data path.
-- Tag: Modeled (a parameter of the deterministic model).
-- Feeds: B3.3, B3.4.
create or replace table cost_model_params (
    name varchar,
    default_value double,
    unit varchar,
    sourcing varchar,
    citation varchar,
    low double,
    high double,
    run_id varchar,
    tag varchar
);
