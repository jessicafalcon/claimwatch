-- theme_share_by_segment — the share of each complaint theme by segment, from
-- the gated classifier; the study's hypothesis, held-claim (document-loop)
-- complaints digital-first versus traditional (B2.5, SPEC.md Beat 2).
-- Grain: one row per (segment, label) — the labels of the closed set present in
--   the segment. unclassified is a row, the gray "not yet classified" band.
-- Counts at the review x theme grain SPEC.md settled: a two-theme review is one
--   review in `reviews` and one row in each of its theme bars, so shares across
--   labels can sum past 1. The document-loop share the panel highlights is one
--   of these rows.
-- segment is the review's own `segment` column, stamped onto the review at load
--   from its source (Phase 7a A1) — no join, so a review is counted under
--   exactly one segment on every input. Portable: string-concat distinct count,
--   no regex, no like, no clock, no reader.
-- Provenance: the Measured tag and run_id. A computed share has no single
--   address or capture instant; its inputs (reviews, theme_rows) are stored so
--   the share can be redone by hand, and run_id — one value per build, a
--   build-level constant, not a grain key — is carried through min() from
--   stg_classified_reviews so the study can tell which input the counted rows
--   came from (the render-time corpus gate, Phase 9b).
-- Tag: Measured (the classifier's own output, counted).
-- Feeds: B2.5. Built by the classify step after stg_classified_reviews is
--   filled (excluded from the generic marts pass, which runs before classify).
create or replace table theme_share_by_segment as
with labeled as (
    select
        r.segment     as segment,
        c.theme       as label,
        r.source      as source,
        r.external_id as external_id,
        c.run_id      as run_id
    from stg_classified_reviews c
    join stg_reviews r
        on c.source = r.source and c.external_id = r.external_id
),
totals as (
    select
        segment,
        count(distinct source || '|' || external_id) as reviews
    from labeled
    group by segment
)
select
    labeled.segment,
    labeled.label,
    totals.reviews,
    count(*)                        as theme_rows,
    count(*) * 1.0 / totals.reviews as share,
    min(labeled.run_id)             as run_id,
    'Measured'                      as tag
from labeled
join totals
    on labeled.segment = totals.segment
group by labeled.segment, labeled.label, totals.reviews;
