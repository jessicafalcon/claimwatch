-- platform_stats — the stat row: review counts, one-star share, how often and
-- how fast companies answer reviews (B1.4, SPEC.md Beat 1).
-- Grain: one row per (segment, source, profile, stat), stat from the closed
--   set review_count, one_star_share, response_rate, response_delay_days —
--   the latest snapshot carrying THAT stat, so a capture that reads one
--   figure never blanks another (spec Phase 3a, A2). value is decimal(12, 3)
--   for every stat. Four selects stacked with union all, one per stat: ANSI,
--   no dialect.
-- Provenance: source_url, captured_at, run_id carried through; tag per row.
-- Feeds: B1.4.
create or replace table platform_stats as
select
    segment,
    source,
    profile,
    stat,
    value,
    tag,
    source_url,
    captured_at,
    run_id
from (
    select
        segment,
        source,
        profile,
        stat,
        value,
        tag,
        source_url,
        captured_at,
        run_id,
        row_number() over (
            partition by segment, source, profile, stat
            order by captured_at desc, precedence, source_url
        ) as row_in_key
    from (
        select
            segment, source, profile, 'review_count' as stat,
            cast(review_count as decimal(12, 3)) as value,
            tag, precedence, source_url, captured_at, run_id
        from stg_platform_snapshots
        union all
        select
            segment, source, profile, 'one_star_share' as stat,
            cast(one_star_share as decimal(12, 3)) as value,
            tag, precedence, source_url, captured_at, run_id
        from stg_platform_snapshots
        where one_star_share is not null
        union all
        select
            segment, source, profile, 'response_rate' as stat,
            cast(response_rate as decimal(12, 3)) as value,
            tag, precedence, source_url, captured_at, run_id
        from stg_platform_snapshots
        where response_rate is not null
        union all
        select
            segment, source, profile, 'response_delay_days' as stat,
            cast(response_delay_days as decimal(12, 3)) as value,
            tag, precedence, source_url, captured_at, run_id
        from stg_platform_snapshots
        where response_delay_days is not null
    ) stats
) ranked
where row_in_key = 1;
