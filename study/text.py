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
