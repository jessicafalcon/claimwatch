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

# fixtures/anchors/platform_snapshots_seed.csv (re-frozen in Phase 3a, D2): the
# brief's §6 public figures — nine rows, every one Documented. Six are the
# studied insurer's (three Trustpilot points, one Opinion Assurances point with
# the stat-row figures and no rating, the two app-store ratings) and three are
# anonymous peers. Loaded in every rebuild input but `none`.
ANCHOR_ROWS = 9
ANCHOR_PROFILES = {
    "fr-digital-first": 6,
    "peer-traditional-1": 1,
    "peer-traditional-2": 1,
    "peer-digital-challenger-1": 1,
}
# The marts on the anchors alone (`ROWS=synthetic` or `none`+anchors):
RATING_TREND_ANCHOR_ROWS = 8  # every anchor with a rating, one per month
CHANNEL_GAP_ANCHOR_ROWS = 6  # latest rating per segment × channel × platform × profile
PLATFORM_STATS_ANCHOR_ROWS = (
    9  # one row per stat (A2): a count per key with one + 4 stats
)
PEER_RATINGS_ANCHOR_ROWS = 4  # unsolicited: the studied insurer + three peers
# The three peers as the brief states them (A4 (e)): a range is stored at its
# midpoint, rounded to the column; a count the brief does not give is empty.
PEER_RATINGS_ANCHOR_VALUES = {
    "peer-traditional-1": ("4.500", 3000),  # "~4.4–4.6 (1k–5k reviews)"
    "peer-traditional-2": ("3.250", None),  # "~2.7–3.8", no count
    "peer-digital-challenger-1": ("3.100", None),  # "~3.1", no count
}
# The studied insurer's latest unsolicited point and its invited ones.
CHANNEL_GAP_DIGITAL_FIRST = {
    ("unsolicited", "trustpilot"): ("3.900", 975, "2026-06-15"),
    ("invited", "app-store"): ("4.900", 5000, "2024-09-15"),
    ("invited", "google-play"): ("4.500", 765, "2024-09-15"),
}
PLATFORM_STATS_OPINION_ASSURANCES = {  # stat -> value, decimal(12, 3)
    "review_count": "534.000",
    "one_star_share": "0.231",
    "response_rate": "0.820",
    "response_delay_days": "1.500",
}

# fixtures/opinion-assurances/: a hand-written profile in the page's microdata
# shape — three reviews on page 1, two on page 2 of which one repeats page 1's
# third (paging overlap: same content, same hash, so the guard skips it), and
# page 3 with the aggregate and no review (the end of the list). Four distinct
# reviews; one snapshot (the aggregate repeats on pages 1 and 2, same key and
# hash). external_id is a content hash, so it is pinned by shape, not value.
OA_SAMPLE_PAGES = 3
OA_SAMPLE_REVIEWS_ON_PAGES = (3, 2, 0)
OA_SAMPLE_RAW_ROWS = 4
OA_SAMPLE_STG_ROWS = 4
OA_SAMPLE_CAPTURED_AT = "2026-09-01T10:00:00"
OA_SAMPLE_FIRST_ROW = {
    "source": "opinion-assurances",
    "source_url": "https://www.opinion-assurances.fr/assureur-exemple-fictif.html",
    "captured_at": OA_SAMPLE_CAPTURED_AT,
    "review_date": "2026-08-20",  # "publié le 20/08/2026": the first date
    "rating": 1,
    "title": "",
}
OA_SAMPLE_REVIEWS_PER_MONTH = (
    ("opinion-assurances", "2026-06", 1),
    ("opinion-assurances", "2026-07", 1),
    ("opinion-assurances", "2026-08", 2),
)
OA_SAMPLE_SNAPSHOT = ("3.600", 512)
# `ROWS=samples`: every frozen sample through its parser, plus the anchors.
SAMPLES_RAW_REVIEWS = APP_STORE_SAMPLE_RAW_ROWS + OA_SAMPLE_RAW_ROWS
SAMPLES_RAW_SNAPSHOTS = ANCHOR_ROWS + 1 + 1  # the listing's row and the profile's
