-- rating_trend — the public rating over time, one point per platform, profile
-- and month (B1.2, SPEC.md Beat 1).
-- Grain: one row per (channel, segment, source, profile, month): the latest
--   snapshot in that month carrying a rating. The panel shows the unsolicited
--   channel and states the sampling bias beside it.
-- Provenance: source_url, captured_at, run_id carried through; tag per point
--   (Documented for a seeded anchor, Measured for our own capture).
-- Feeds: B1.2.
create or replace table rating_trend as
select
    channel,
    segment,
    source,
    profile,
    month,
    rating,
    review_count,
    tag,
    source_url,
    captured_at,
    run_id
from (
    select
        stg_platform_snapshots.*,
        row_number() over (
            partition by channel, segment, source, profile, month
            order by captured_at desc, precedence, source_url
        ) as row_in_month
    from stg_platform_snapshots
    where rating is not null
) ranked
where row_in_month = 1;
