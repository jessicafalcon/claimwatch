-- stg_platform_snapshots — one row per snapshot, with its tag and month.
-- Grain: one row per (source, profile, captured_at) — the latest content_hash
--   when two raw rows share a key (a deterministic tiebreak, as stg_reviews).
-- Provenance: carries source, source_url, captured_at, run_id from raw.
-- Derived: tag — Documented for an anchor (a public figure read at scoping),
--   Measured for a hand-read or fetched row (a capture of ours, with its
--   address and day); month — substr of the row's own date. Exact
--   comparisons only: no pattern, no clock.
-- Feeds: rating_trend (B1.2), channel_gap (B1.3), platform_stats (B1.4),
--   peer_ratings (B2.3).
create or replace table stg_platform_snapshots as
select
    source,
    profile,
    segment,
    channel,
    origin,
    case when origin = 'anchor' then 'Documented' else 'Measured' end as tag,
    rating,
    review_count,
    one_star_share,
    response_rate,
    response_delay_days,
    source_url,
    captured_at,
    substr(captured_at, 1, 7) as month,
    run_id,
    seeded_from,
    content_hash
from (
    select
        raw_platform_snapshots.*,
        row_number() over (
            partition by source, profile, captured_at
            order by content_hash desc
        ) as row_in_key
    from raw_platform_snapshots
) ranked
where row_in_key = 1;
