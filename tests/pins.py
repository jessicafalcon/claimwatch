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
# Page 1's second review rates 4.5: the one half-step in the sample, so
# `ROWS=samples` carries a half star through the real parser and the real
# `decimal(2, 1)` column (A6). (review_date, rating as the column spells it.)
OA_SAMPLE_HALF_STEP = ("2026-08-18", "4.5")
# fixtures/trustpilot/: a hand-written export in webscraper.io's column shape —
# four reviews (5, 1, 4 and 3 stars; the 3-star is rating-only, empty body) on
# one page, no snapshot (the rating stays hand-read, Phase 3c). external_id is
# a content hash, so it is pinned by shape, not value.
TRUSTPILOT_SAMPLE_PAGES = 1
TRUSTPILOT_SAMPLE_RAW_ROWS = 4
TRUSTPILOT_SAMPLE_STG_ROWS = 4
TRUSTPILOT_SAMPLE_CAPTURED_AT = "2026-09-01T10:00:00"
TRUSTPILOT_SAMPLE_REVIEWS_PER_MONTH = (
    ("trustpilot", "2026-06", 1),
    ("trustpilot", "2026-07", 1),
    ("trustpilot", "2026-08", 1),
    ("trustpilot", "2026-09", 1),
)

# `ROWS=samples`: every frozen sample through its parser, plus the anchors.
SAMPLES_RAW_REVIEWS = (
    APP_STORE_SAMPLE_RAW_ROWS + OA_SAMPLE_RAW_ROWS + TRUSTPILOT_SAMPLE_RAW_ROWS
)
SAMPLES_RAW_SNAPSHOTS = ANCHOR_ROWS + 1 + 1  # the listing's row and the profile's
# (the trustpilot sample emits no snapshot: its rating stays hand-read)

# --- Phase 5a: the label set, the review id and the held-out split ---

# The closed label set (PROJECT_BRIEF §5 + positive + unclassified): exactly
# seven labels, of which five are complaint themes. An eighth is impossible.
LABEL_COUNT = 7
THEME_COUNT = 5

# The deterministic eval split, `sha256(review_id) % 5` (docs/PLAN §4.4). Four
# folds tune the rules in 5b; fold 4 is held out for Phase 6's gate.
SPLIT_FOLDS = 5
HELDOUT_FOLD = 4
# The fold of fixed ids — pins that `fold` is `sha256(review_id) % 5` over the
# id's UTF-8 bytes, the same number on every machine.
FOLD_OF = {
    "app-store:900000001": 0,
    "opinion-assurances:OA-101": 0,
}

# The synthetic corpus, addressed as review ids: one per distinct staged review,
# so the count equals STG_REVIEWS_ROWS (39). Over these ids the held-out fold
# (4) is non-empty and so are the tuning folds — a usable split.
SYNTHETIC_REVIEW_IDS = STG_REVIEWS_ROWS
SYNTHETIC_HELDOUT_REVIEW_IDS = 5  # ids in fold 4; the other 34 tune

# `make label-sample` draws reviews in `sha256(review_id)` order and takes the
# first N, so the sheet is deterministic and a larger N is a superset. The first
# three ids in that order over the synthetic corpus:
SAMPLE_ORDER_FIRST_3 = (
    "opinion-assurances:OA-107",
    "opinion-assurances:OA-108",
    "app-store:AS-302",
)
# The labeling sheet's columns (with the review text) and the tracked answer
# key's columns (text-free) — the wall stated as two shapes.
LABEL_SHEET_COLUMNS = ("review_id", "source_url", "text")
LABELS_CSV_COLUMNS = ("review_id", "theme")

# --- Phase 5b: the rules layer graded on the tuning folds ---

# Per-theme precision on the four tuning folds (`sha256(review_id) % 5 != 4`),
# each as (hits, predicted): of the reviews the rules gave the label, how many
# the synthetic answer key agrees with. The rules fire only at a clear word-start
# match, so on the clean hand-written corpus every firing is right — precision
# 1.0. The metric earns its keep on the decided share and the formula unit test
# (a crafted disagreement scores below 1.0). Held-out reviews (fold 4) are not
# counted here — they are Phase 6's to grade.
RULES_PRECISION = {
    "document-loop": (7, 7),
    "silent-rejection": (3, 3),
    "second-payer": (3, 3),
    "support-traction": (4, 4),
    "coverage-price": (4, 4),
    "positive": (6, 6),
}
# The tuning corpus: every staged review not in the held-out fold.
RULES_TUNING_REVIEWS = STG_REVIEWS_ROWS - SYNTHETIC_HELDOUT_REVIEW_IDS  # 39 - 5 = 34
# Reviews the rules placed in a theme or `positive` (vs left `unclassified` for
# the model), over the tuning folds. The rules decide the clear cases and leave
# the rest — a decided share below 1 is the point of the layer.
RULES_DECIDED = 27

# --- Phase 6a: the combined classification over the full synthetic corpus ---

# The rules + model combiner runs over every staged review (not just the tuning
# folds — the held-out fold is special only for 6b's grading). With NO key the
# model never runs, so these are the rules-only outcome at the review x theme
# grain: 39 reviews -> 25 theme rows + 7 positive + 7 unclassified. The 7
# unclassified are the reviews a model would decide with a key (the gray band).
CLASSIFY_NOKEY_REVIEWS = STG_REVIEWS_ROWS  # 39
CLASSIFY_NOKEY_THEME_ROWS = 25
CLASSIFY_NOKEY_POSITIVE = 7
CLASSIFY_NOKEY_UNCLASSIFIED = 7

# --- Phase 6b: the held-out eval gate + the classifier_quality mart (B2.4) ---

# The gate grades the FULL classifier on the held-out fold alone (fold 4). The
# classifier_quality mart is one row per scored label (the five themes + positive
# — `unclassified` is the absence of a decision, not scored), every figure
# Measured. Its columns are a computed metric's provenance: no source_url, no
# captured_at, no clock (precision = hits/predicted, recall = hits/actual).
CLASSIFIER_QUALITY_COLUMNS = (
    "label",
    "hits",
    "predicted",
    "actual",
    "precision",
    "recall",
    "heldout_fold",
    "answer_key",
    "run_id",
    "tag",
)
CLASSIFIER_QUALITY_ROWS = THEME_COUNT + 1  # five themes + positive = 6
CLASSIFIER_QUALITY_TAG = "Measured"
CLASSIFIER_QUALITY_ANSWER_KEY = "classify/eval/labels.csv"

# Rules-only (no key) held-out grades on the synthetic corpus, per scored label:
# (hits, predicted, actual, precision, recall). The five held-out reviews
# (SYNTHETIC_HELDOUT_REVIEW_IDS) are clear cases the rules classify correctly, so
# every label present in fold 4 scores 1.0/1.0 and the two labels absent from
# fold 4 are undefined (None, not 0). The formula — a disagreement scores below
# 1.0 — is proven by a crafted unit test (test_gate.py), not by this clean
# fixture; here the point is that the gate reads only fold 4 and populates the
# mart honestly with no key.
RULES_HELDOUT = {
    "document-loop": (2, 2, 2, 1.0, 1.0),
    "silent-rejection": (1, 1, 1, 1.0, 1.0),
    "second-payer": (1, 1, 1, 1.0, 1.0),
    "support-traction": (0, 0, 0, None, None),
    "coverage-price": (0, 0, 0, None, None),
    "positive": (1, 1, 1, 1.0, 1.0),
}
