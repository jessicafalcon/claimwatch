-- classifier_quality — how good the classifier is, graded on the held-out fold
-- against the hand answer key (B2.4, SPEC.md Beat 2).
-- Grain: one row per scored label (the five §5 themes + positive). unclassified
--   is the absence of a decision, not a label to score.
-- The first Python-fed mart: this file is DDL only (the fixed shape); the CLI
--   classify step scores fold 4 (classify/eval/gate.py) and inserts the rows.
--   No pattern or model logic in SQL — that keeps the SQL portable, and the
--   answer key is read only inside classify/eval/ (the wall).
-- Columns: precision = hits / predicted, recall = hits / actual, each null when
--   its denominator is 0; hits/predicted/actual are stored so the ratio can be
--   redone by hand.
-- Provenance (a computed metric, not a scraped row): answer_key names the ground
--   truth it was scored against, heldout_fold which fold, run_id the build. No
--   source_url and no captured_at — a quality metric has no address and no
--   capture instant, and a build clock is forbidden on the data path.
-- Tag: Measured (a direct measurement of the classifier against hand labels).
-- Feeds: B2.4.
create or replace table classifier_quality (
    label varchar,
    hits integer,
    predicted integer,
    actual integer,
    precision double,
    recall double,
    heldout_fold integer,
    answer_key varchar,
    run_id varchar,
    tag varchar
);
