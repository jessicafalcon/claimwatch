-- stg_reviews — cleaned, deduplicated reviews, one per review.
-- Grain: one row per (source, external_id) — the latest capture (newest
--   captured_at; content_hash breaks a tie deterministically, so equal sort
--   keys resolve the same way every run).
-- Provenance: carries source, source_url, captured_at, run_id from raw_reviews.
-- Feeds: theme_share_by_month (B2.2), theme_share_by_segment (B2.5) via
--   classified_reviews (Phase 5b+).
-- Portable: window function + subquery filter (no qualify, no regex, no clock).
create or replace table stg_reviews as
select
    source,
    external_id,
    source_url,
    captured_at,
    run_id,
    review_date,
    rating,
    title,
    body,
    content_hash
from (
    select
        raw_reviews.*,
        row_number() over (
            partition by source, external_id
            order by captured_at desc, content_hash desc
        ) as row_in_review
    from raw_reviews
) ranked
where row_in_review = 1;
