-- platform_stats — the stat row: one-star share, review count, how fast and
-- how often companies answer (B1.4, SPEC.md Beat 1).
-- Grain: one row per (segment, source, profile): the latest snapshot carrying
--   at least one of the three stats a platform page shows.
-- Provenance: source_url, captured_at, run_id carried through; tag per row.
-- Feeds: B1.4.
create or replace table platform_stats as
select
    segment,
    source,
    profile,
    review_count,
    one_star_share,
    response_rate,
    response_delay_days,
    tag,
    source_url,
    captured_at,
    run_id
from (
    select
        stg_platform_snapshots.*,
        row_number() over (
            partition by segment, source, profile
            order by captured_at desc, precedence, source_url
        ) as row_in_key
    from stg_platform_snapshots
    where one_star_share is not null
       or response_rate is not null
       or response_delay_days is not null
) ranked
where row_in_key = 1;
