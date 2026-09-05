-- theme_share_by_month — the share of each complaint theme, month by month and
-- by segment, from the gated classifier (B2.2, SPEC.md Beat 2).
-- Grain: one row per (month, segment, label) — the labels of the closed set
--   present in the cell (five §5 themes + positive + unclassified). unclassified
--   is a row, not a gap: it is the gray "not yet classified" band, largest when
--   no key ran.
-- Counts at the review x theme grain SPEC.md settled: a two-theme review is one
--   review in `reviews` and one row in each of its two theme bars, so shares
--   across labels can sum past 1.
-- month is substr of the review's own date (never a clock); segment is the
--   review's own `segment` column, stamped onto the review at load from its
--   source (Phase 7a A1) — no join, so a review is counted under exactly one
--   segment on every input. Portable: substr + string-concat distinct count, no
--   regex, no like, no clock, no reader.
-- Provenance: the Measured tag. A computed share has no single address, capture
--   instant or run; its inputs (reviews, theme_rows) are stored so the share can
--   be redone by hand, and run_id lives one hop upstream on
--   stg_classified_reviews.
-- Tag: Measured (the classifier's own output, counted).
-- Feeds: B2.2. Built by the classify step after stg_classified_reviews is
--   filled (excluded from the generic marts pass, which runs before classify).
create or replace table theme_share_by_month as
with labeled as (
    select
        substr(r.review_date, 1, 7) as month,
        r.segment                   as segment,
        c.theme                     as label,
        r.source                    as source,
        r.external_id               as external_id
    from stg_classified_reviews c
    join stg_reviews r
        on c.source = r.source and c.external_id = r.external_id
),
totals as (
    select
        month,
        segment,
        count(distinct source || '|' || external_id) as reviews
    from labeled
    group by month, segment
)
select
    labeled.month,
    labeled.segment,
    labeled.label,
    totals.reviews,
    count(*)                        as theme_rows,
    count(*) * 1.0 / totals.reviews as share,
    'Measured'                      as tag
from labeled
join totals
    on labeled.month = totals.month and labeled.segment = totals.segment
group by labeled.month, labeled.segment, labeled.label, totals.reviews;
