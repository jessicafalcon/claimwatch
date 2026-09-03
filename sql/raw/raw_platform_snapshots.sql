-- raw_platform_snapshots — a platform page's headline numbers as they stood
-- at a moment, append-only (spec Phase 3a, pinned decision 1).
-- Grain: one row per snapshot; natural key (source, profile, origin,
--   source_url, captured_at) — what produced the row and when (A2) — plus
--   content_hash over the five measures. A re-seed of the anchors, a re-entry
--   of a hand-read row or a re-capture of unchanged figures inserts nothing;
--   a same-key row with other figures is refused by the loader, so the key
--   is unique here.
-- Provenance: source, source_url, captured_at, run_id. captured_at is the
--   anchor's or the reader's day (YYYY-MM-DD) or the fetch stamp — no clock in
--   SQL; run_id is stamped by the loader in Python.
-- Attribution (written in Python from fixtures/anchors/ or the source
--   declaration, never a pattern in SQL): profile (whose figures), segment
--   (digital-first, traditional, digital-challenger), channel (invited,
--   unsolicited), origin (anchor, manual, fetch) — origin decides the tag
--   downstream: anchor -> Documented, otherwise Measured.
-- Measures: rating 0–5 to three places (null when the source gives none),
--   review_count, and three the stat row needs when a page shows them:
--   one_star_share and response_rate (0–1), response_delay_days.
-- Feeds: stg_platform_snapshots, then rating_trend (B1.2), channel_gap (B1.3),
--   platform_stats (B1.4), peer_ratings (B2.3).
create table if not exists raw_platform_snapshots (
    source               text          not null,
    profile              text          not null,
    segment              text          not null,
    channel              text          not null,
    origin               text          not null,
    rating               decimal(4, 3),
    review_count         integer       not null,
    one_star_share       decimal(4, 3),
    response_rate        decimal(4, 3),
    response_delay_days  decimal(5, 1),
    source_url           text          not null,
    captured_at          text          not null,
    run_id               text          not null,
    seeded_from          text          not null,
    content_hash         text          not null
);
