-- channel_gap — the latest rating on each channel a company invites and each
-- it does not, side by side (B1.3, SPEC.md Beat 1).
-- Grain: one row per (segment, channel, source, profile): the latest snapshot
--   carrying a rating.
-- Provenance: source_url, captured_at, run_id carried through; tag per row.
-- Feeds: B1.3.
create or replace table channel_gap as
select
    segment,
    channel,
    source,
    profile,
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
            partition by segment, channel, source, profile
            order by captured_at desc, content_hash desc
        ) as row_in_key
    from stg_platform_snapshots
    where rating is not null
) ranked
where row_in_key = 1;
