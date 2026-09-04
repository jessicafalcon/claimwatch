-- raw_reviews — public reviews exactly as captured, append-only.
-- Grain: one row per capture; natural key (source, external_id, content_hash).
--   A re-capture of an unchanged review inserts nothing; an edited review has a
--   new content_hash and appends a new row, so history is kept.
-- rating: a half-step 1 to 5 (ingest/parsed.py::REVIEW_RATINGS, checked at the
--   load); the profile site rates in half stars, the app feed in digits (A6).
-- Provenance: source, source_url, captured_at, run_id. captured_at is the
--   capture time carried in from the fixture/scraper, run_id is stamped by the
--   loader in Python — no clock in SQL.
-- segment: the market segment of the source the review was loaded from
--   (ingest/sources.py; the synthetic fixture's is looked up by platform),
--   stamped in Python at load — attribution, so it is outside content_hash
--   (like run_id) and a re-spelling of it is not a corrected review. It is how
--   the theme marts split by segment without a query-time join (Phase 7a, A1).
-- Feeds: stg_reviews, and downstream the theme marts theme_share_by_month
--   (B2.2) and theme_share_by_segment (B2.5) via stg_classified_reviews.
create table if not exists raw_reviews (
    source        text    not null,
    external_id   text    not null,
    source_url    text    not null,
    segment       text    not null,
    captured_at   text    not null,
    run_id        text    not null,
    review_date   text    not null,
    rating        decimal(2, 1) not null,
    title         text    not null,
    body          text    not null,
    content_hash  text    not null
);
