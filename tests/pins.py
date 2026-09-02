"""Every pinned number in one place (docs/PLAN.md §4, "tests/pins.py"). A test
compares a computed value against a pin here; a change to a pin is a deliberate,
reviewed edit. Phase 1 pins the synthetic stage counts and the edited-review
pair; Phase 2 pins the frozen App Store sample (`fixtures/app-store/`) through
the real parser; the §6 anchors and the cost-model outputs are pinned in Phases
3 and 8."""

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

# fixtures/app-store/: one hand-written capture of three feed pages — six items
# on page 1, three on page 2 of which one repeats page 1's last item (paging
# overlap: same id, same content, so the raw guard skips it), and page 3 with
# no `entry` (the end of the feed). 8 distinct reviews over three months.
APP_STORE_SAMPLE_PAGES = 3
APP_STORE_SAMPLE_ITEMS_ON_PAGES = (6, 3, 0)
APP_STORE_SAMPLE_RAW_ROWS = 8
APP_STORE_SAMPLE_STG_ROWS = 8
APP_STORE_SAMPLE_DUPLICATE_ID = "900000006"
APP_STORE_SAMPLE_CAPTURED_AT = "2026-09-01T08:00:00"
APP_STORE_SAMPLE_REVIEWS_PER_MONTH = (
    ("app-store", "2026-01", 3),
    ("app-store", "2026-02", 3),
    ("app-store", "2026-03", 2),
)
# Page 1's first item, as the parser must map it (the eight raw columns).
APP_STORE_SAMPLE_FIRST_ROW = {
    "source": "app-store",
    "external_id": "900000001",
    "source_url": "https://itunes.apple.com/fr/rss/customerreviews/id=0/"
    "sortBy=mostRecent/page=1/json",
    "captured_at": APP_STORE_SAMPLE_CAPTURED_AT,
    "review_date": "2026-03-20",
    "rating": 1,
    "title": "Exemple: encore un document",
}

# fixtures/listings/: one hand-written listing page whose JSON-LD block carries
# an aggregateRating; read under the sample declaration (Phase 3a).
LISTING_SAMPLE_CAPTURED_AT = "2026-09-01T09:00:00"
LISTING_SAMPLE_ROW = {
    "source": "google-play",
    "profile": "sample",
    "segment": "sample",
    "channel": "sample",
    "origin": "fetch",
    "rating": "4.123",  # the page's 4.123456789, kept to three places
    "review_count": 1234,
    "source_url": "https://play.google.com/store/apps/details"
    "?id=example.fictional.app&hl=fr&gl=FR",
    "captured_at": LISTING_SAMPLE_CAPTURED_AT,
}
