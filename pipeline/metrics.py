"""The one Phase 2 metric — reviews per month — as a query, not a mart (spec
Phase 2, pinned decision 5). It is a pipeline-health number, not a study claim:
no SPEC.md panel shows it, so a `sql/marts/` file for it would be an orphan
under BACKING.md's rule. It surfaces in Beat 5 through B5.2
`pipeline_row_counts`, whose mart folds this query in (BACKLOG row).

Plain ANSI: `substr` on the review's own ISO date, `group by`, `count(*)`. No
clock (time is `review_date`), no dialect (the portability lint checks this
text in a test). `order by` is fine here — this is a query, not a table."""

from __future__ import annotations

REVIEWS_PER_MONTH = """
select
    source,
    substr(review_date, 1, 7) as month,
    count(*) as n
from stg_reviews
group by source, substr(review_date, 1, 7)
order by source, month
"""


def reviews_per_month(conn) -> list[tuple[str, str, int]]:
    """(source, 'YYYY-MM', reviews) per month over the deduplicated reviews."""
    return [
        (str(s), str(m), int(n))
        for s, m, n in conn.execute(REVIEWS_PER_MONTH).fetchall()
    ]
