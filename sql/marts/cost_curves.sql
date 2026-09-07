-- cost_curves — fraud saved, friction cost and net over the flag-rate grid, per
--   scenario, with the default flag rate marked (B3.2, SPEC.md Beat 3).
-- Grain: one row per (scenario, flag_rate) — the 41-point grid (0.000..0.200
--   step 0.005) over the four §7 scenarios. 4 x 41 = 164 rows. Exactly one row
--   per scenario is the default flag rate (is_default = true), the "you are
--   here" marker.
-- A Python-fed mart: this file is DDL only (the fixed shape);
--   pipeline/build.py::write_model_marts fills it from models/cost_model.py — no
--   arithmetic in SQL, which keeps the SQL portable and the formulas one copy.
-- Columns: fraud_saved, friction_cost, net are the two curves and their
--   difference at each grid flag rate, rounded at the one site; the crossover
--   the study names is the first row whose net < 0, read straight off this
--   column. is_default marks the default flag rate.
-- Provenance: run_id names the build; no source_url, no captured_at, no clock.
-- Tag: Modeled (the deterministic model's own output).
-- Feeds: B3.2; B4.1 (the contacts_once rows — the document loop one round
--   shorter, "the curves move").
create or replace table cost_curves (
    scenario varchar,
    flag_rate double,
    fraud_saved double,
    friction_cost double,
    net double,
    is_default boolean,
    run_id varchar,
    tag varchar
);
