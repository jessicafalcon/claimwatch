-- raw_source_pages — every page address a declared source can produce, with
-- the attribution its rows inherit (spec Phase 3a, pinned decision 3).
-- Grain: one row per (source, source_url): a platform slug and one exact page
--   address, written in Python from ingest/sources.py at every rebuild. It is
--   the declared-page registry: a captured page's address is checked against it
--   by exact value, so a review from an address outside the declaration is
--   caught (spec Phase 3a, invariant 4). Never a pattern over the address (the
--   Portability contract keeps pattern-matching out of SQL).
-- Provenance: source, source_url, captured_at (the day the source was
--   declared), run_id. content_hash covers profile, segment, channel; a
--   re-declaration with a changed attribution refuses the rebuild (spec
--   Phase 3a, A3), so one address has one row.
-- Note: it is NOT how a review gets its segment. A review's segment is stamped
--   onto the review at load time (raw_reviews.segment, Phase 7a A1), because the
--   source_url the review carries is a host root on the synthetic corpus and a
--   platform is declared under two segments on the samples input — neither an
--   exact review→page join could resolve. The theme marts group by
--   stg_reviews.segment, not this table.
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
