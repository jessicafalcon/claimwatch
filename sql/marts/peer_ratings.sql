-- peer_ratings — public ratings across the market segment on unsolicited
-- platforms, so no one insurer is read in isolation (B2.3, SPEC.md Beat 2).
-- Grain: one row per (segment, source, profile) over the unsolicited channel:
--   the latest snapshot carrying a rating, with its date.
-- Provenance: source_url, captured_at, run_id carried through; tag per row.
-- Feeds: B2.3.
create or replace table peer_ratings as
select
    segment,
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
            partition by segment, source, profile
            order by captured_at desc, precedence, source_url
        ) as row_in_key
    from stg_platform_snapshots
    where channel = 'unsolicited'
      and rating is not null
) ranked
where row_in_key = 1;
