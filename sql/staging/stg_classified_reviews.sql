-- stg_classified_reviews — the gated classifier's decision for every review,
-- one row per theme it carries, persisted so SQL can count it (feeds B2.2/B2.5).
-- Grain: one row per (source, external_id, theme) at the review x theme grain
--   classify_all returns — a K-theme review is K rows; a review no rule and no
--   model placed is one `unclassified` row; a clean review is one `positive`.
-- Python-fed, not the staging SQL pass: this file is DDL only (the shape). The
--   classify step (pipeline/cli.py) runs the combined classifier over
--   stg_reviews and delete+inserts here, so with no key the rows are rules-only
--   and the `unclassified` band is honest. `create table if not exists` so the
--   staging pass makes it empty and re-running the DDL never drops the rows.
-- Provenance: run_id (the rebuild input). theme is a label of the closed set,
--   never free text — the classifier can only answer from the seven labels.
-- Portable: DDL only, no reader, no pattern, no clock.
-- Feeds: theme_share_by_month (B2.2), theme_share_by_segment (B2.5).
create table if not exists stg_classified_reviews (
    source       varchar not null,
    external_id  varchar not null,
    theme        varchar not null,
    run_id       varchar not null
);
