-- stg_platform_snapshots — one row per snapshot, with its tag and month.
-- Grain: one row per raw row. The raw key (source, profile, origin,
--   source_url, captured_at) is unique — a same-key row with other figures is
--   refused at load (spec Phase 3a, A2) — so nothing is deduplicated or
--   tiebroken here.
-- Provenance: carries source, source_url, captured_at, run_id from raw.
-- Derived: tag — Documented for an anchor (a public figure read at scoping),
--   Measured for a hand-read or fetched row (a capture of ours, with its
--   address and day); month — substr of the row's own date; precedence — when
--   two points share a day in a mart, a figure we measured stands in front of
--   one read at scoping, and a capture in front of a hand entry (0, 1, 2);
--   the address orders what is left. Exact comparisons only: no pattern, no
--   clock.
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
    case when origin = 'fetch' then 0 when origin = 'manual' then 1 else 2 end
        as precedence,
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
from raw_platform_snapshots;
