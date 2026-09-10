-- determinism_facts — the checkable facts about the repository itself (B5.1,
-- SPEC.md Beat 5): the facts a reader can verify without trusting the study.
-- Grain: one row per checkable fact (a closed set, filled by the writer).
-- A Python-fed mart, DDL only here (the fixed shape); rebuild() computes each
--   fact from the code it describes and inserts the rows — the model-decision
--   count from the one-call-site walk (Classification contract: classify/llm.py),
--   the formula count from models/cost_model.py::FORMULAS (the formulas B3.1
--   displays beside their output), the evidence-tag count from study/model.py::TAGS.
--   No pattern or model logic in SQL — the counts are computed in Python and
--   passed in, which keeps the SQL portable.
-- Not corpus-gated: a repo fact is constant on any input and with no key, so it
--   fills on every rebuild input (including none) and shows on the committed page.
-- Provenance (a computed fact, not a scraped row): run_id names the build. No
--   source_url and no captured_at — a repo fact has no address and no capture
--   instant, and a build clock is forbidden on the data path.
-- Tag: Measured (a direct count of the repository).
-- Feeds: B5.1.
create or replace table determinism_facts (
    fact varchar,
    value integer,
    run_id varchar,
    tag varchar
);
