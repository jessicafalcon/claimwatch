-- pipeline_row_counts — how many rows the review pipeline holds at each stage
-- (B5.2, SPEC.md Beat 5): the reproducibility signal a reader reruns and checks.
-- Grain: one row per pipeline stage (a closed set of stage tables, single grain
--   — the per-source-month review breakdown is a printed query, not this mart;
--   BACKLOG Phase 2 row, Phase 9e challenge #6).
-- A Python-fed mart, DDL only here (the fixed shape); the CLI classify step
--   (pipeline/cli.py, after stg_classified_reviews is filled) counts each stage
--   table and inserts one row — so the classified stage is counted too. No
--   pattern or model logic in SQL — the counts are plain count(*) in Python.
-- Corpus-gated (the Phase 9b gate, like classifier_quality): real counts over a
--   captured input, the fixture-state note over the frozen synthetic input, and
--   "no data yet" over none — the committed synthetic page shows the note.
-- Not filled by `make idempotency-check` (which runs rebuild() only, before
--   classify): its rebuild-stability is proven by a named rebuild-then-classify
--   twice test, not the target (BACKLOG line 52).
-- Provenance (a computed count, not a scraped row): run_id names the build. No
--   source_url and no captured_at — a stage count has no address and no capture
--   instant, and a build clock is forbidden on the data path.
-- Tag: Measured (a direct count of each stage table).
-- Feeds: B5.2.
create or replace table pipeline_row_counts (
    stage varchar,
    value integer,
    run_id varchar,
    tag varchar
);
