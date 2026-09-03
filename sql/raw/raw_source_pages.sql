-- raw_source_pages — every page address a declared source can produce, with
-- the attribution its rows inherit (spec Phase 3a, pinned decision 3).
-- Grain: one row per (source, source_url): a platform slug and one exact page
--   address, written in Python from ingest/sources.py at every rebuild, so a
--   review row joins its profile, segment and channel by exact value:
--     stg_reviews r join raw_source_pages p
--       on r.source = p.source and r.source_url = p.source_url
--   Never a pattern over the address (the Portability contract keeps
--   pattern-matching out of SQL).
-- Provenance: source, source_url, captured_at (the day the source was
--   declared), run_id. content_hash covers profile, segment, channel; a
--   re-declaration with a changed attribution refuses the rebuild (spec
--   Phase 3a, A3), so one address has one row.
-- Feeds: theme_share_by_month (B2.2) and theme_share_by_segment (B2.5) via
--   classified_reviews (Phase 5b+); nothing charts it yet.
create table if not exists raw_source_pages (
    source        text not null,
    source_url    text not null,
    profile       text not null,
    segment       text not null,
    channel       text not null,
    captured_at   text not null,
    run_id        text not null,
    content_hash  text not null
);
