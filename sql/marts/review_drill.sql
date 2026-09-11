-- review_drill — the review-level audit trail behind each theme bar: one row per
--   classified review x theme, for the Metabase demonstration's drill (9g,
--   PROJECT_BRIEF.md §90, SPEC.md Beat 2). Read by study/metabase/export.py into
--   the SQLite file Metabase reads; never rendered in the byte-checked HTML page.
-- Grain: one row per (source, external_id, theme) — the same review x theme grain
--   as theme_share_by_month, one row per theme a review carries (a two-theme
--   review is two rows; a positive or unclassified review is one row on that
--   label). A reader drilling a theme bar sees exactly these rows.
-- Columns — the non-text, non-brand allowlist (9g central constraint): review_id
--   (the review's stable identity, `source || ':' || external_id`, the same
--   string classify/labels.py::review_id builds, so the drill and the classifier
--   name a review identically), theme (one of the seven closed labels),
--   rating, review_date, segment, source (the platform slug). NEVER body/title
--   (personal data — brief §5 bodies name conditions) and NEVER source_url (the
--   brand-carrying page address — DECISIONS D1); the join to stg_reviews reaches
--   the table that carries those, so the projection here is the guard, checked on
--   the cursor's own description (study/metabase/export.py, test_review_drill).
-- No text a reader sees comes from here: the theme's paraphrase is
--   study/paraphrases.yaml (B2.1, Documented, sourced), joined by theme in the
--   Metabase config, never a review body.
-- segment/rating are the review's own columns (never a clock); source and
--   segment are carried from stg_reviews. Portable: string-concat only, no regex,
--   no reader function, no clock.
-- Provenance: the rows carry no tag/run_id column — the drill is the audit trail
--   of counted rows, not a displayed number; its honesty is the input it was
--   built over (only fake reviews under ROWS=synthetic) plus the caption on the
--   demonstration, not a render-time corpus gate, which lives in the HTML render
--   (study/panels.py), not in this mart (9g challenge round 2).
-- Feeds: the Metabase review-level drill (B2.1's paraphrases are shown beside it).
--   Built by the classify step after stg_classified_reviews is filled (excluded
--   from the generic marts pass, which runs before classify).
create or replace view review_drill as
select
    r.source || ':' || r.external_id as review_id,
    c.theme                          as theme,
    r.rating                         as rating,
    r.review_date                    as review_date,
    r.segment                        as segment,
    r.source                         as source
from stg_classified_reviews c
join stg_reviews r
    on c.source = r.source and c.external_id = r.external_id;
