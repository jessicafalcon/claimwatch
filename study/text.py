"""The study's display texts, as data (Phase 9c): the words a panel shows beside
its numbers — note texts, fixture-state labels, display names and the templates
a note is filled from. One layer below `study/panels.py` (the readers) and two
below `study/export.py` (the renderers): `text.py` ← `panels.py` ← `export.py`.
This module imports nothing from either, reads no database and emits no HTML.

The words are the study-editor's; the mechanism is the closed map: a display
name is looked up by the mart's own identifier and an unknown identifier refuses
by name, so a new formula or parameter cannot render its identifier as prose."""

from __future__ import annotations

# --- Beat 2: the corpus gate's fixture state and the theme-share notes ---------
# The fixture-state text carries no digit, so a fixture panel's body shows no
# number (Phase 9b, the brief's "never faked" applied at render time).
FIXTURE_NOTE = (
    "Built from hand-written example reviews: a check that the study’s machinery "
    "works, not a result. The counted figures appear when the study is built "
    "over captured reviews."
)
# The denominator every theme share divides by — every classified review,
# positive included — stated beside the chart so `positive`'s exclusion from
# the bars is not read as a shrunk denominator (Phase 9b, pinned decision 4).
# One note per chart shape: B2.2's lines (shares across themes in one month),
# B2.5's bars (one theme's share in one segment) — round 2, study-editor #1.
DENOMINATOR_NOTE = (
    "The share of each theme is theme rows over every classified review "
    "(positive reviews included in the total, but not drawn as a theme bar — a "
    "theme chart counts complaints). A review carrying two themes counts in two "
    "bars, so the shares across themes can sum past one. The gray “not yet "
    "classified” band is the reviews a language model would sort; when that "
    "model is switched off it is largest, shown, never hidden."
)
SEGMENT_DENOMINATOR_NOTE = (
    "The bar is the document-loop share among every classified review in that "
    "segment (positive reviews included in the total, never a bar); a review "
    "carrying document-loop beside another theme counts once here. The gray "
    "“not yet classified” band is the reviews a language model would sort; "
    "when that model is switched off it is largest, shown, never hidden."
)


# The negative-self-selection caveat, the theme-share panels' own note beside the
# counting method (brief §2.5; B1.2 carries the same caveat beside the rating
# trend). A theme SHARE from unsolicited platforms is a mix among the
# dissatisfied, not a census — stated where the chart shows it, naming what
# that chart shows (round 2, study-editor #2).
def _self_selection_note(shown: str) -> str:
    return (
        "Sampling bias, stated here: these reviews come from platforms customers "
        "were not invited to (unsolicited), which are negatively self-selected — "
        f"so {shown} is what dissatisfied customers chose to write about, not a "
        "census of every claim."
    )


SELF_SELECTION_NOTE = _self_selection_note("the theme mix")
SEGMENT_SELF_SELECTION_NOTE = _self_selection_note("the held-claim complaint share")
# The corpus is one segment today — B2.2 and B2.5's own note, before the caveat:
# B2.2's query filters on it and B2.5 draws it (BACKLOG "vs traditional").
TRADITIONAL_CAVEAT = (
    "The corpus is digital-first only for now, so the traditional comparison "
    "awaits a traditional-mutuelle source; the chart shows the segment the data "
    "has."
)


# --- Beat 3: the cost model's display names, marker labels and note templates --
# Each formula's display name, keyed by its `FORMULAS` name and in `FORMULAS`
# order (a test pins the key sequence equal), so the page reads line for line
# with `make model`. A name the map does not know refuses by name in the reader
# — a formula added without a study name fails the render rather than
# rendering its identifier as prose (Phase 9c, pinned decision 6).
FORMULA_NAMES = {
    "customer_value": "Revenue per member per year",
    "mean_claim": "The mean claim, from the fit",
    "median_cell": "The median reimbursement cell",
    "claims": "Claims per year",
    "claims_at_mean_cell": "Claims per year at the mean cell",
    "flagged": "Claims flagged",
    "false_pos": "Claims wrongly held",
    "fraud_saved": "Fraud saved",
    "friction_cost": "Friction cost",
    "net": "Net: saved minus friction",
    "loop_days": "Length of the document loop",
    "friction_per_day": "Friction per day of hold",
    "timer_amount_eur": "Hold-timer threshold amount",
    "crossover_flag_rate": "Where the curves cross",
    "marginal_crossover_flag_rate": "Where the next flag stops paying",
}
# Each parameter's display name and the display unit its default is read in
# (`study.model.Unit`), keyed by its mart name and in `parameters()` order (a
# test pins the key sequence equal). One closed choice per parameter beside its
# name — never a second map (challenge round 1, #4).
PARAMETER_NAMES = {
    "arr_eur": ("Yearly revenue", "eur"),
    "members": ("Members", "count"),
    "fraud_pool_eur": ("Fraud pool per year", "eur"),
    "refunded_eur": ("Refunds paid per year", "eur"),
    "mu": ("Log-mean of the claim cost, from the fit", "logeur"),
    "sigma": ("Log-spread of the claim cost, from the fit", "logeur"),
    "emp_p50": ("Median reimbursement cell", "eur"),
    "emp_mean": ("Mean reimbursement cell", "eur"),
    "flag_rate": ("Flag rate", "pct"),
    "fp_share": ("Share of flags that are wrong", "pct"),
    "contacts": ("Contacts per stuck claim", "count"),
    "cost_per_contact": ("Cost per contact", "eur"),
    "churn_prob": ("Chance a stuck customer leaves", "pct"),
    "k": ("How fast extra flags stop catching fraud", ""),
    "days_per_round": ("Days per document round trip", "days"),
    "timer_days": ("Days a hold may run before the clock", "days"),
}
# The derived headline figures B3.3 shows above its parameter rows (BACKING
# B3.3: revenue per member, the mean claim, the claim volume) and, from 9h, the
# claim count at the sample's own mean cell — the contrast beside the claim
# volume, a fourth row through this one map — read from the outputs mart at the
# baseline, never retyped.
HEADLINE_FORMULAS = ("customer_value", "mean_claim", "claims", "claims_at_mean_cell")
# What B3.3 says about the two claim counts: only what its cells show — the
# mean cell sits above the fitted mean, so the count at the mean cell is the
# lower one. No maximum cell, no percentage, no decile: the page holds none of
# those as a cell (9h, challenge round 1, #8).
MEAN_CELL_NOTE = (
    "Two claim counts are shown, one division each: refunds paid over the mean "
    "claim from the fit, and refunds paid over the mean reimbursement cell of "
    "the sample itself — the plain average of the cells, no fit involved. The "
    "mean cell sits above the fitted mean, so the lognormal puts less weight on "
    "the largest cells than the sample carries, and the count at the mean cell "
    "is the lower of the two. Every later formula uses the fitted count; the "
    "second is the contrast a reader recomputing from the data would find."
)

# The labels of a curve panel's three markers, in the order they are drawn:
# the default flag rate, then the two crossovers. Two markers at one x stack
# their labels by draw index, neither hidden (pinned decision 3).
MARKER_DEFAULT = "you are here"
MARKER_CROSSOVER = "the curves cross"
MARKER_MARGINAL = "the next flag stops paying"
# The declared absences: a crossover the grid never reaches (the mart stores
# NULL), and a parameter whose range is one point (`low == default == high`).
NEVER_CROSSES = "never crosses on this grid"
FIXED_RANGE = "fixed — read from the fit"
# What an unsourced parameter row says instead of a citation: a declared guess
# to explore, never a fact (brief §7).
UNSOURCED_LABEL = "declared unsourced — explore the range"


# The B3.2 note that names the crossovers: a reading of the chart filled from
# the outputs mart's rows, never a typed figure (pinned decision 4). Each half
# has its present and its absent sentence, so a null crossover says so.
def crossover_note(crossover: str | None, marginal: str | None, default: str) -> str:
    """The note beneath the curve chart, from the three displayed rates (or
    `None` where the mart stores NULL): where the next flag stops paying (and
    whether that is where the default sits), then where the curves cross. The
    earlier point reads first, so a non-technical reader meets the default
    before the whole-curve crossover (round 1, study-editor #3)."""
    if marginal is None:
        marginal_sentence = (
            "No point of the grid has the next flag costing more than it recovers."
        )
    else:
        where = ", where the default sits" if marginal == default else ""
        marginal_sentence = (
            f"The next flag stops paying for itself at {marginal}{where}."
        )
    if crossover is None:
        crossover_sentence = (
            "On this grid the two curves never cross: at every flag rate drawn, "
            "the flags as a whole recover more than they cost."
        )
    else:
        crossover_sentence = (
            f"At these defaults the two curves cross at a flag rate of {crossover}: "
            "past it, the flags as a whole cost more than they recover."
        )
    return f"{marginal_sentence} {crossover_sentence}"


# --- Beat 4 (Phase 9d): the three fixes, drawn beside the Beat 3 curves --------
# B4.1's four net curves, keyed by the cost-model scenario each draws
# (`models.cost_model.SCENARIOS`) and in that draw order — baseline first, the
# reference. `churn_halved` is the cost-curve effect the hold timer is modelled
# as (fewer customers lost), which is why its display name names the clock.
# A test pins these keys equal to `SCENARIOS` (the B4.1 palette is ≤ 5 series).
SCENARIO_NAMES = {
    "baseline": "Today, no fix",
    "contacts_once": "Ask once",
    "churn_halved": "A clock on every hold",
    "both": "Both fixes",
}
# B4.3's bars, one per simulator scenario (`models.guardrail_sim.SIM_SCENARIOS`,
# in that order): the no-fix hold is the "before", each fix's hold the "after"
# beside it — the spec's "scenario × hold days", the before shown once, not
# repeated per fix. The display names match B4.1's for the paired scenarios. A
# test pins these keys equal to the simulator scenario set.
SIM_HOLD_NAMES = {
    "no_fix": "Today, no fix",
    "ask_once": "Ask once",
    "hold_timer": "A clock on every hold",
    "both_fixes": "Both fixes",
}
# B4.2's three stat labels, in the order of `sla_threshold`'s cells
# (`timer_days`, `timer_amount_eur`, `share_under`), each with its display unit
# — the closed display text as data, not literals in `panels.py`. "Claims small
# enough to auto-release" names the share as what it is (the small claims the
# clock releases), so B4.2's 49% reads as the same quantity B4.3 reports
# released, not a second coincidental figure.
THRESHOLD_STATS = (
    ("Clock fires after", "days"),
    ("Not worth holding below", "eur"),
    ("Claims small enough to auto-release", "pct"),
)


# The B4.2 note: the clock's arithmetic, filled from the `sla_threshold`
# is_default row's three cells (a reading of the mart, never a typed figure) —
# the timer day, the claim amount below which a hold that long is net-negative,
# and the share of synthetic claims under it.
def threshold_note(timer_days: str, amount: str, share: str) -> str:
    """The sentence beneath B4.2, from the three displayed cells of the default
    threshold row: a hold beyond the timer day on a claim under the amount costs
    more in friction than the fraud it could still catch, so it auto-releases;
    the share names how many claims fall under that amount."""
    return (
        f"Holds beyond {timer_days} on claims under {amount} are net-negative in "
        f"expectation — the friction they add outweighs the fraud they still "
        f"catch — so past {timer_days} a small claim auto-releases and a large "
        f"one goes to a person. {share} of synthetic claims fall under that "
        "amount."
    )


# The B4.3 note figure: where the released share renders (a note figure, not a
# bar — the bars are one mean hold per scenario). Only the clock releases claims;
# once the document loop is already one round, the timer has nothing left to
# release, so ask-once and both-fixes release none (SPEC Beat 4). The "same hold
# as ask-once" claim is prose; the ask_once == both_fixes equality it rests on is
# pinned in tests/test_beat4.py, so a parameter change that broke it fails there.
def released_note(clock_share: str) -> str:
    """The sentence naming the clock's released share, from the `hold_timer`
    scenario's aggregate cell — the same "synthetic claims" population B4.2's
    threshold note counts, so the shared figure reads as one quantity."""
    return (
        f"The clock alone releases {clock_share} of synthetic claims early. With "
        "the document loop already cut to one round, ask-once and both-fixes "
        "leave the timer nothing to release — the same hold as ask-once."
    )


# B4.4 is Pending: a design panel with no number, because the outcome log a
# false-positive rate needs does not exist yet (SPEC B4.4).
BEAT4_PENDING = (
    "No number yet: a false-positive rate per flag rule needs an outcome log — "
    "each hold recorded as fraud-confirmed or released-clean — that the system "
    "does not keep. The same event stream would also trigger a status "
    "notification against silent rejections, from the events already recorded."
)


# --- Beat 5: the facts you can check, and reproducibility ----------------------
# B5.1's three facts, in render order: the display label and unit for each
# `determinism_facts` key (a count). A key outside this closed map refuses by name
# in the reader — the mart and the page name the same three facts.
DETERMINISM_FACTS = {
    "model_call_sites": ("Places a language model makes a decision", "count"),
    "formulas_shown": ("Cost-model formulas shown beside their output", "count"),
    "evidence_tags": ("Evidence tags in the study's closed set", "count"),
}
# B5.1's note, second layer: what each fact means and how a reader checks it.
DETERMINISM_NOTE = (
    "One place a model decides: every other tag comes from rules, SQL or "
    "arithmetic. The formulas are the cost-model ones printed next to their "
    'output in "What a wrongly held claim costs" above — redo any by hand. Every '
    "number on this page carries one of three tags — Measured, Documented or "
    "Modeled — and a panel with no number yet is marked Pending, so nothing "
    "stands unsourced."
)
# B5.2's stage display names, in flow order: the `pipeline_row_counts` stage key
# (a table name) → what it is in plain words. A key outside this closed map
# refuses by name.
ROW_COUNT_STAGES = {
    "raw_reviews": "Reviews as scraped",
    "stg_reviews": "After removing duplicates",
    "stg_classified_reviews": "Tagged by theme (one row per review × theme)",
}
# B5.2's note: the eval scores live in the classifier-quality panel above (B2.4,
# not copied here), and the one command that rebuilds everything from raw data.
# `make rebuild` is named as text, never a live counter.
ROW_COUNTS_NOTE = (
    "How good the tagging is — precision and recall on reviews the classifier "
    "never saw — is the classifier-quality table above. One command rebuilds "
    "every number in this study from the raw reviews: `make rebuild`. Run it "
    "twice and the counts do not move."
)
