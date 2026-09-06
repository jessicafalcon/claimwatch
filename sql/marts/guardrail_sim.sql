-- guardrail_sim — how long each synthetic claim is held, per simulator scenario,
--   before and after the three fixes (B4.1, B4.3; SPEC.md Beat 4).
-- Grain: one row per (scenario, claim_rank) — the four simulator scenarios over
--   the 1,000-point quantile grid. 4 x 1000 = 4000 rows. The per-claim grain
--   exists for the timer's per-claim decision (which claims it releases, and at
--   what amount), not for a hold distribution: a hold takes two values per
--   scenario (the loop, or the timer). Phase 9 lays these beside the cost curves
--   on the curves_scenario join.
-- A Python-fed mart: this file is DDL only (the fixed shape);
--   pipeline/build.py::write_sim_marts fills it from models/guardrail_sim.py — no
--   arithmetic in SQL, which keeps the SQL portable and the rules one copy.
-- Columns: scenario is the simulator scenario (no_fix, ask_once, hold_timer,
--   both_fixes); curves_scenario is the cost-curve scenario it pairs with;
--   quantile and amount_eur are the fit read at the claim's rank (synthetic
--   claims, real distribution); loop_days is the document loop; hold_days is the
--   loop or the timer; outcome is one of three names (loop_released,
--   timer_released, timer_escalated). claim_rank/loop_days/hold_days are whole
--   days/counts, named integer so rebuild's catalog check and Snowflake see one
--   type (the cost_curves.is_default precedent).
-- Provenance: run_id names the build; no source_url, no captured_at, no clock.
-- Tag: Modeled (the deterministic simulator's own output).
-- Feeds: B4.1, B4.3.
create or replace table guardrail_sim (
    scenario varchar,
    curves_scenario varchar,
    claim_rank integer,
    quantile double,
    amount_eur double,
    loop_days integer,
    hold_days integer,
    outcome varchar,
    run_id varchar,
    tag varchar
);
