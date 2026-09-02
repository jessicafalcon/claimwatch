"""Every pinned number in one place (docs/PLAN.md §4, "tests/pins.py"). A test
compares a computed value against a pin here; a change to a pin is a deliberate,
reviewed edit. Phase 1 pins the synthetic stage counts and the edited-review
pair; the §6 anchors and the cost-model outputs are pinned in Phases 3 and 8."""

from __future__ import annotations

# fixtures/synthetic/reviews.csv: 40 captured rows, of which one (source,
# external_id) is captured twice (an edited review), so 39 distinct reviews.
RAW_REVIEWS_ROWS = 40
STG_REVIEWS_ROWS = 39

# The one review captured twice: raw keeps both captures (append-only), staging
# keeps the later one (2026-03-15, rating 1).
EDITED_REVIEW = ("opinion-assurances", "OA-201")
EDITED_REVIEW_RAW_ROWS = 2
EDITED_REVIEW_LATEST_CAPTURED_AT = "2026-03-15T09:00:00"
EDITED_REVIEW_LATEST_RATING = 1

# Ratings span the whole 1..5 scale (every outcome from one-star to five-star is
# represented in the fixture bodies).
RATING_RANGE = (1, 5)
