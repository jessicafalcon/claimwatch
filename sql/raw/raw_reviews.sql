-- raw_reviews — public reviews exactly as captured, append-only.
-- Grain: one row per capture; natural key (source, external_id, content_hash).
--   A re-capture of an unchanged review inserts nothing; an edited review has a
--   new content_hash and appends a new row, so history is kept.
-- Provenance: source, source_url, captured_at, run_id. captured_at is the
--   capture time carried in from the fixture/scraper, run_id is stamped by the
--   loader in Python — no clock in SQL.
-- Feeds: stg_reviews, and downstream the theme marts theme_share_by_month
--   (B2.2) and theme_share_by_segment (B2.5) via classified_reviews (Phase 5b+).
create table if not exists raw_reviews (
    source        text    not null,
    external_id   text    not null,
    source_url    text    not null,
    captured_at   text    not null,
    run_id        text    not null,
    review_date   text    not null,
    rating        integer not null,
    title         text    not null,
    body          text    not null,
    content_hash  text    not null
);
