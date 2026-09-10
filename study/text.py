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
# — a fifteenth formula added without a study name fails the render rather than
# rendering its identifier as prose (Phase 9c, pinned decision 6).
FORMULA_NAMES = {
    "customer_value": "Revenue per member per year",
    "mean_claim": "The mean claim, from the fit",
    "median_cell": "The median reimbursement cell",
    "claims": "Claims per year",
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
    "flag_rate": ("Flag rate", "pct"),
    "fp_share": ("Share of flags that are wrong", "pct"),
    "contacts": ("Contacts per stuck claim", "count"),
    "cost_per_contact": ("Cost per contact", "eur"),
    "churn_prob": ("Chance a stuck customer leaves", "pct"),
    "k": ("How fast extra flags stop catching fraud", ""),
    "days_per_round": ("Days per document round trip", "days"),
    "timer_days": ("Days a hold may run before the clock", "days"),
}
# The three derived headline figures B3.3 shows above its parameter rows
# (BACKING B3.3: revenue per member, the mean claim, the claim volume) — read
# from the outputs mart at the baseline, never retyped.
HEADLINE_FORMULAS = ("customer_value", "mean_claim", "claims")

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
