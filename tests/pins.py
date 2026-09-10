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
# B1.2 as the study export renders it: the studied digital-first insurer's
# unsolicited rating series, (month, rating) per point (the anchor values).
RATING_TREND_DIGITAL_FIRST = (
    ("2025-01", "4.2"),
    ("2025-09", "3.8"),
    ("2026-06", "3.9"),
)
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

# --- Phase 7a: the theme-share marts (B2.2, B2.5) over stg_classified_reviews ---

# The classification persisted at the (source, external_id, theme) grain: one row
# per theme a review carries — the same 39 rows the no-key combiner produces (25
# theme + 7 positive + 7 unclassified). run_id is provenance; no clock, no address.
CLASSIFIED_REVIEWS_ROWS = STG_REVIEWS_ROWS  # 39
CLASSIFIED_REVIEWS_COLUMNS = ("source", "external_id", "theme", "run_id")

# The theme-share marts count those rows. share = theme_rows / reviews, at the
# review x theme grain (a review counts once in `reviews`, once per theme bar).
# unclassified is a row, not a gap — the gray "not yet classified" band, and with
# no key it is largest. Tag Measured; provenance is the tag plus run_id (a computed
# share has no address or capture instant; run_id — a build-level constant, not a
# grain key — is carried through min() from stg_classified_reviews so the study
# can tell which input the rows came from). Columns end run_id, tag, matching the
# other computed marts (classifier_quality, the cost-model and simulator marts).
THEME_SHARE_TAG = "Measured"
THEME_SHARE_BY_SEGMENT_COLUMNS = (
    "segment",
    "label",
    "reviews",
    "theme_rows",
    "share",
    "run_id",
    "tag",
)
THEME_SHARE_BY_MONTH_COLUMNS = ("month",) + THEME_SHARE_BY_SEGMENT_COLUMNS

# Every synthetic review is digital-first (all four platforms are), so by-segment
# has one segment. theme_rows per label over the 39 reviews (no key): the five
# themes, positive and unclassified. `document-loop` (held-claim, B2.5's subject)
# is the largest theme; `unclassified` is the band a key would shrink.
THEME_SHARE_SEGMENT = "digital-first"
THEME_SHARE_BY_SEGMENT_REVIEWS = STG_REVIEWS_ROWS  # 39 (the denominator)
THEME_SHARE_BY_SEGMENT_NOKEY = {
    "document-loop": 9,
    "silent-rejection": 4,
    "second-payer": 4,
    "support-traction": 4,
    "coverage-price": 4,
    "positive": 7,
    "unclassified": 7,
}

# The month split (by the review's own date). Reviews per (month, digital-first);
# every month carries at least one document-loop row, and every month a review
# the rules left unclassified carries an unclassified band row.
THEME_SHARE_BY_MONTH_REVIEWS = {"2026-01": 36, "2026-02": 2, "2026-03": 1}

# --- Phase 7b: the DAMIR lognormal claim-cost fit over fixtures/damir/ ---------
# The fit computed by `make fit-damir` over the frozen fixture: a systematic
# N=5000 draw of positive legal-type (PRS_REM_TYP in {0,1}, Amendment A1)
# PRS_REM_MNT amounts from Open DAMIR July 2025 (A202507). mu = mean(ln x),
# sigma = population-std(ln x), n = the kept amounts. Rounded to 6 decimals, the
# grain fit_lognormal is pinned at. Byte-stable and reproducible from the fixture.
DAMIR_MU = 3.809814
DAMIR_SIGMA = 2.187981
DAMIR_N = 5000
# The median DAMIR cell (emp_p50), read back by opendata.fit.read_fit and the
# contrast printed beside mean_claim in the cost model.
DAMIR_EMP_P50 = 49.76

# --- Phase 8a: the cost model (Beat 3) ---------------------------------------
# Every number below is typed from the built output of models/cost_model.py over
# the tracked fit (mu/sigma/emp_p50 above), never guessed: the defaults are not
# tuned to tell a story. The formulas themselves live in one place,
# models/cost_model.py::FORMULAS (the study prints them). Euros round to 2
# places, counts to whole (the one rounding site). Only friction_cost and net
# move with a scenario; every other point output is scenario-invariant.
COST_MODELED_TAG = "Modeled"
COST_PARAM_ROWS = 15  # 4 scale + 3 fit + 6 knobs + 2 timer knobs (8b)
COST_SCENARIOS = ("baseline", "contacts_once", "churn_halved", "both")
FLAG_RATE_GRID_POINTS = 41  # 0.000..0.200 step 0.005
COST_OUTPUT_ROWS = len(COST_SCENARIOS) * 14  # 12 point + 2 curve per scenario = 56
# The unit each formula's value is rounded and displayed in — a field of the
# Formula entry (fix/cost-outputs-unit), stored in cost_model_outputs.unit so the
# page, `make model` and the dashboard format one number one way. Every key is
# a rounding unit of models.cost_model._ROUNDING; a curve's value is a flag rate.
COST_FORMULA_UNITS = {
    "customer_value": "eur",
    "mean_claim": "eur",
    "median_cell": "eur",
    "claims": "count",
    "flagged": "count",
    "false_pos": "count",
    "fraud_saved": "eur",
    "friction_cost": "eur",
    "net": "eur",
    "loop_days": "days",  # a day count, quoted in days (two places), not a tally
    "friction_per_day": "eur",
    "timer_amount_eur": "eur",
    "crossover_flag_rate": "rate",
    "marginal_crossover_flag_rate": "rate",
}
COST_CURVE_ROWS = len(COST_SCENARIOS) * FLAG_RATE_GRID_POINTS  # 164

# mu/sigma sliders: the fit ± 2 standard errors (se_mu = sigma/√n, se_sigma =
# sigma/√(2n)) over n = 5000, rounded to 6 places.
DAMIR_MU_RANGE = (3.747929, 3.871699)
DAMIR_SIGMA_RANGE = (2.144221, 2.231741)

COST_OUTPUTS = {
    "baseline": {
        "customer_value": 800.0,
        "mean_claim": 494.45,
        "median_cell": 49.76,
        "claims": 707858,
        "flagged": 35393,
        "false_pos": 17696,
        "fraud_saved": 1318719.82,
        "friction_cost": 1132573.36,
        "net": 186146.45,
        "loop_days": 21.0,  # days: two places, so the printed value is 21.0
        "friction_per_day": 3.05,
        "timer_amount_eur": 42.67,
    },
    "contacts_once": {
        "customer_value": 800.0,
        "mean_claim": 494.45,
        "median_cell": 49.76,
        "claims": 707858,
        "flagged": 35393,
        "false_pos": 17696,
        "fraud_saved": 1318719.82,
        "friction_cost": 849430.02,
        "net": 469289.79,
        "loop_days": 7.0,
        "friction_per_day": 6.86,
        "timer_amount_eur": 48.0,
    },
    "churn_halved": {
        "customer_value": 800.0,
        "mean_claim": 494.45,
        "median_cell": 49.76,
        "claims": 707858,
        "flagged": 35393,
        "false_pos": 17696,
        "fraud_saved": 1318719.82,
        "friction_cost": 778644.19,
        "net": 540075.63,
        "loop_days": 21.0,  # days: two places, so the printed value is 21.0
        "friction_per_day": 2.1,
        "timer_amount_eur": 29.33,
    },
    "both": {
        "customer_value": 800.0,
        "mean_claim": 494.45,
        "median_cell": 49.76,
        "claims": 707858,
        "flagged": 35393,
        "false_pos": 17696,
        "fraud_saved": 1318719.82,
        "friction_cost": 495500.85,
        "net": 823218.97,
        "loop_days": 7.0,
        "friction_per_day": 4.0,
        "timer_amount_eur": 28.0,
    },
}
# (crossover_flag_rate, marginal_crossover_flag_rate) per scenario. A fix that
# lifts net above zero across the whole grid has no crossover (None); the
# marginal crossover always exists here. The baseline crosses at 0.095 with the
# 0.05 "you are here" marker left of it.
COST_CROSSOVERS = {
    "baseline": {"crossover_flag_rate": 0.095, "marginal_crossover_flag_rate": 0.05},
    "contacts_once": {
        "crossover_flag_rate": 0.18,
        "marginal_crossover_flag_rate": 0.085,
    },
    "churn_halved": {
        "crossover_flag_rate": None,
        "marginal_crossover_flag_rate": 0.095,
    },
    "both": {"crossover_flag_rate": None, "marginal_crossover_flag_rate": 0.15},
}

# --- Phase 8b: the guardrail simulator (Beat 4) ------------------------------
# Every number below is typed from the built output of models/guardrail_sim.py
# over the tracked fit, never guessed. The claims are the lognormal read at 1,000
# fixed quantile midpoints (i - 0.5)/n — a real distribution, synthetic claims —
# and the hold timer is a rule, not a draw; two runs are byte-identical.
QUANTILE_N = 1000
GUARDRAIL_SIM_ROWS = 4 * QUANTILE_N  # 4 scenarios x 1000 claims = 4000
SLA_THRESHOLD_ROWS = 60  # timer days 1..60
TIMER_DEFAULT_DAY = 14  # the default timer_days; exactly one is_default row

# The simulator scenarios and the cost-curve scenario each pairs with (decision 4).
SIM_SCENARIO_MAP = {
    "no_fix": "baseline",
    "ask_once": "contacts_once",
    "hold_timer": "churn_halved",
    "both_fixes": "both",
}

# The first, middle and last synthetic amounts (ranks 1, 500, 1000), rounded eur:
# exp(mu + sigma * z((rank - 0.5)/n)) over the pinned fit.
SYNTHETIC_AMOUNTS = {1: 0.03, 500: 45.02, 1000: 60441.06}

# The SLA threshold at three grid days (amount below which a hold that long is
# net-negative in expectation; share of claims under it). Linear in the day up to
# the baseline loop (21 days), then constant (day 21 == day 60), share
# non-decreasing. The default day (14) is inside the body of the distribution.
SLA_THRESHOLD_SAMPLE = {
    7: {"timer_amount_eur": 21.33, "share_under": 0.366},
    14: {"timer_amount_eur": 42.67, "share_under": 0.49},
    21: {"timer_amount_eur": 64.0, "share_under": 0.563},
}
SLA_DEFAULT_SHARE = 0.49  # share_under at the default day; equals hold_timer's
#                           timer_released_share (decision 6)

# The hold-day summary per fix (mean hold days, share the timer released). Each
# fix shortens the mean hold; both_fixes equals ask_once (a one-round loop ends
# before the default timer, so the clock never fires) — the expected identical bars.
SIM_SUMMARY = {
    "no_fix": {"mean_hold_days": 21.0, "timer_released_share": 0.0},
    "ask_once": {"mean_hold_days": 7.0, "timer_released_share": 0.0},
    "hold_timer": {"mean_hold_days": 17.57, "timer_released_share": 0.49},
    "both_fixes": {"mean_hold_days": 7.0, "timer_released_share": 0.0},
}

# --- Phase 9b: Beat 2 as the study export renders it (over a captured run_id) ---
# The corpus panels (B2.2, B2.4, B2.5) render a number only over a captured input;
# a test relabels a copy of the synthetic marts' run_id to `captured`. The values
# are the no-key synthetic marts above (only run_id changed), read here as the
# export plots them.

# B2.5 (theme_share_by_segment): each theme bar's share is theme_rows / reviews,
# the mart's own; positive is excluded from the bars (still in the denominator),
# unclassified is the neutral band. document-loop is the hypothesis subject.
BEAT2_SEGMENT_BARS = {  # the two drawn series (held-claim + the band) → theme_rows
    "document-loop": 9,
    "unclassified": 7,
}
BEAT2_SEGMENT_LABEL = "Digital-first"  # the one segment's bar label (x = segment)
BEAT2_POSITIVE_EXCLUDED = "positive"  # in the denominator, never a theme bar

# B2.2 (theme_share_by_month): document-loop's share each month = theme_rows /
# THEME_SHARE_BY_MONTH_REVIEWS[month]. 2026-03 is a single review, one theme —
# a share of exactly 1.0, plotted at the axis top, never stacked.
BEAT2_MONTH_DOCUMENT_LOOP = {"2026-01": 7, "2026-02": 1, "2026-03": 1}

# B2.4 (classifier_quality) as the table renders each scored label: precision and
# recall shown as a percent with the held-out counts, or "no held-out case" with
# the empty denominator's count (RULES_HELDOUT above is the source).
BEAT2_QUALITY_CELLS = {
    "document-loop": ("100.0%", "2/2", "100.0%", "2/2"),
    "silent-rejection": ("100.0%", "1/1", "100.0%", "1/1"),
    "second-payer": ("100.0%", "1/1", "100.0%", "1/1"),
    "support-traction": (
        "no held-out case",
        "0 predicted",
        "no held-out case",
        "0 actual",
    ),
    "coverage-price": (
        "no held-out case",
        "0 predicted",
        "no held-out case",
        "0 actual",
    ),
    "positive": ("100.0%", "1/1", "100.0%", "1/1"),
}

# B2.3 (peer_ratings): the four anchor profiles the export draws, each a bar
# labelled by its role, rated on trustpilot. rating as the mart carries it; a
# count the brief does not give is blank (None) and no count renders.
BEAT2_PEER_RATINGS = {
    "fr-digital-first": (3.9, 975),
    "peer-digital-challenger-1": (3.1, None),
    "peer-traditional-1": (4.5, 3000),
    "peer-traditional-2": (3.25, None),
}

# --- Phase 9c: Beat 3 rendered — the first Modeled panels ---------------------
# The rendered fragments are typed from `make study` over the synthetic marts
# (whose Beat 3 figures are COST_OUTPUTS / COST_CROSSOVERS above, reused, not
# retyped). The display names live in study/text.py; their counts are pinned.
BEAT3_PANELS = ("B3.1", "B3.2", "B3.3", "B3.4")
BEAT3_FORMULA_ROWS = 14  # twelve point + two curve formulas, the baseline scenario
BEAT3_PARAMETER_ROWS = COST_PARAM_ROWS  # 15: 7 sourced + 8 unsourced
BEAT3_SOURCED_ROWS = 7  # the four scale anchors + the three fit rows
BEAT3_UNSOURCED_ROWS = 8  # the six knobs + the two hold-timer knobs
BEAT3_HEADLINES = ("customer_value", "mean_claim", "claims")  # B3.3, BACKING
# The outputs-mart rounding unit → display unit is `panels._DISPLAY_UNIT`; the
# test asserts against that one map, never a copy of it (round 1, code-reviewer
# #5), so the pin cannot drift from the code it checks.
# The curve chart's three rules at the baseline, in draw order: the default and
# the marginal crossover both at 0.05 — two labels stacked at one x.
BEAT3_MARKERS = (
    ("you are here", 0.05),
    ("the curves cross", 0.095),
    ("the next flag stops paying", 0.05),
)
# The y-domain rule over two inputs: the synthetic maximum (friction cost at a
# 20% flag rate) rounds up to one significant figure; one cent past the bound
# crosses to the next.
BEAT3_CURVE_DOMAIN = {4_530_293.45: 5_000_000.0, 5_000_000.01: 6_000_000.0}
BEAT3_FIXED_PARAMETER = "emp_p50"  # low == default == high: the fixed mark
BEAT3_FRAGMENTS = {
    "formula value (fraud_saved, eur)": ">€1,318,719.82<",
    "curve euro tick": ">€1,250,000.00<",
    "marker label": ">you are here (5.0%)<",
    "sourced default (arr_eur, eur)": ">€800,000,000.00<",
    "fit default (mu, logeur)": ">3.809814 log-euros<",
    "unsourced default (flag_rate, pct)": ">5.0%<",
    "crossover row (rate as pct)": ">9.5%<",
}

# --- Phase 9d: Beat 4 rendered — the three fixes beside the Beat 3 curves ------
# Every Beat 4 number is a mart cell filled on every rebuild input (SIM_SUMMARY,
# SLA_THRESHOLD_SAMPLE, TIMER_DEFAULT_DAY above are its source, reused not
# retyped). The committed page shows these; the tests prove the readers.
BEAT4_PANELS = ("B4.1", "B4.2", "B4.3", "B4.4")
BEAT4_NET_SERIES = 4  # baseline + the three toggled scenarios, ≤ 5-slot palette
# B4.1's net curves span all four scenarios: the min (baseline, deep negative)
# and max (both) each round outward to one significant figure. A signed domain,
# unlike curve_domain's 0-floor (net dips below zero — the crossover).
BEAT4_NET_DOMAIN = (-2_000_000.0, 2_000_000.0)
# B4.3 draws one bar per simulator scenario in SIM_SCENARIOS order — the no-fix
# baseline (the "before") shown once, each fix beside it; the clock is the only
# scenario that releases claims early (SIM_SUMMARY).
BEAT4_SIM_SCENARIOS = ("no_fix", "ask_once", "hold_timer", "both_fixes")
BEAT4_FRAGMENTS = {
    "threshold day (stat, days)": ">14.0 days<",
    "threshold amount (stat, eur)": ">€42.67<",
    "threshold share (stat, pct)": ">49.0%<",
    "released share (note, pct)": "releases 49.0% of synthetic claims",
}

# --- Phase 9e: Beat 5 rendered — the facts you can check, and reproducibility --
# B5.1's three repo facts are counted from the code, so the tests assert each
# rendered value equals its source (len(model_call_sites()), len(FORMULAS),
# len(TAGS)); these pins are the regression fragments, updated deliberately when
# the code changes the count.
BEAT5_PANELS = ("B5.1", "B5.2")
# determinism_facts fills by construction in rebuild() (three facts, on every
# input including none); pipeline_row_counts fills in the classify path, so it is
# empty over a rebuild()-only `none` build.
DETERMINISM_FACT_ROWS = 3
BEAT5_MODEL_SITES = 1  # one place a model decides: classify/llm.py (== len(sites))
BEAT5_EVIDENCE_TAGS = 4  # Measured, Documented, Modeled, Pending (== len(TAGS))
BEAT5_FRAGMENTS = {
    "model sites (stat, count)": ">1<",
    "formulas shown (stat, count)": ">14<",  # == len(cost_model.FORMULAS)
    "evidence tags (stat, count)": ">4<",
}
# The per-stage row counts over the synthetic corpus (pipeline_row_counts): as
# scraped, after dedup, after tagging (one theme row per review). B5.2 is
# corpus-gated, so these render only over a captured input; the mart holds them
# on the synthetic build and a direct count(*) must equal each.
BEAT5_STAGE_COUNTS = {
    "raw_reviews": 40,
    "stg_reviews": 39,
    "stg_classified_reviews": 39,
}
