"""The study's panel model and its render-time contract, as data (PLAN §4.6).

One layer below the renderers: the frozen types a panel is made of, the four
evidence tags, the closed chart-kind and unit sets, and `check_panel` — the
render-time guard that refuses a panel breaking the contract. `study/panels.py`
builds these from the marts; `study/export.py` renders them. Nothing here reads
a database or emits HTML.

The contract, checked here, not by editorial trust:

- A panel is data — `Panel(id, backing_row, tag, kind, series, notes)`. Its `tag`
  is the one BACKING evidence tag; a panel whose tag is not exactly one of
  `TAGS` is refused (no tag, or two).
- A **Pending** panel carries no value; a Pending panel handed a value is
  refused (brief §2.4; the render-time no-number guard).
- Every rendered number carries exactly one tag (its point's own `tag`, in
  `TAGS`), so a chart that mixes anchor (Documented) and captured (Measured)
  points marks each point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The four evidence tags (brief §2.4). A panel's tag, and every point's tag, is
# exactly one of these; anything else is refused (the runtime guard is `TAGS`).
TAGS = ("Measured", "Documented", "Modeled", "Pending")
# Closed sets a static checker can read too (round 1, code-reviewer #7): the
# chart kind and the display unit. Their runtime guards are `_render_body`
# (unknown kind refuses) and `display` (unknown unit refuses). Phase 9c adds
# the three Beat 3 kinds — `formulas` (a list of expression / value rows),
# `curve` (series over one numeric x axis with labelled markers), `parameters`
# (range marks) — and the two units a cost-model figure is read in.
Kind = Literal[
    "hero",
    "line",
    "grouped_bar",
    "stat_row",
    "table",
    "formulas",
    "curve",
    "parameters",
]
Unit = Literal["stars", "pct", "days", "count", "eur", "logeur", ""]

# The `unclassified` band's colour: the palette's neutral token, not a sixth
# categorical hue (the five-slot order is the CVD-safety mechanism; Phase 9b,
# pinned decision 4). A `Series.colour` is a slot `0..4` or exactly this token.
NEUTRAL = "neutral"


class RenderRefused(Exception):
    """A one-line render refusal: printed as-is, non-zero exit, never a
    traceback (the same boundary policy as pipeline/cli.py's `Refused`)."""


@dataclass(frozen=True)
class Point:
    """One marked number in a panel: its label (a month, a channel, a stat), its
    value in the mart's own units, its evidence tag, and the platform-root
    address it opens to (`""` when the panel cites its sources at the panel
    level, e.g. a computed share). `value is None` marks a Pending placeholder
    or a metric cell with no value — never rendered as a number. `absent`, when
    set, is the labelled reason a metric cell has no value (a zero-denominator
    score, a crossover the grid never reaches); a cell carries a value xor an
    `absent` (`check_panel`). `detail` is an optional inline note — the raw
    counts behind a share (Phase 9b), or a parameter's prose unit with its
    citation or unsourced label (Phase 9c), shown so the figure can be redone
    by hand."""

    label: str
    value: float | None
    tag: str
    source_url: str
    unit: Unit = ""
    absent: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Series:
    """One line, one group of bars, or one table row, coloured by categorical
    slot `0..4` or the `NEUTRAL` token (the `unclassified` band). The colour is
    a closed choice on the type — the renderer refuses anything else by name
    (Phase 9b, pinned decision 4). `key` is the mart's own identifier for a
    formula or parameter row, shown beside the display name so a reader matches
    `make model` line for line; `sourcing` is a parameter row's mart word
    (`sourced` | `unsourced`), the closed key the range mark's style is looked
    up by (Phase 9c)."""

    name: str
    colour: int | str
    points: tuple[Point, ...]
    key: str = ""
    sourcing: str = ""


@dataclass(frozen=True)
class Panel:
    """A study panel as data. `tag` is the BACKING-declared evidence tag; `kind`
    is one of hero | line | grouped_bar | stat_row | table. `fixture`, when set,
    is the labelled fixture-state text a corpus panel shows over a fixture input
    (no number) — distinct from Pending and from "no data yet" (Phase 9b).
    `columns` names a metric table's headers; `sources` are panel-level drill
    addresses for a computed number whose points carry no per-row address.
    `markers` are a curve panel's labelled vertical rules, `(label, x)` pairs
    read from a mart row and drawn at a grid x the panel's points carry;
    `headline` is the derived figures a parameters panel shows above its rows
    (B3.3's three), each a formula row (Phase 9c)."""

    id: str
    backing_row: str
    title: str
    blurb: str
    tag: str
    kind: Kind
    series: tuple[Series, ...] = ()
    notes: tuple[str, ...] = ()  # second-layer commentary, one <p> per note (§2.3)
    placeholder: str = ""  # the Pending panel's labelled gray text
    fixture: str = ""  # the corpus panel's fixture-state text over a fixture input
    columns: tuple[str, ...] = ()  # a metric table's column headers (table kind)
    sources: tuple[str, ...] = ()  # panel-level drill addresses (computed numbers)
    domain: tuple[float, float] = (0.0, 5.0)
    markers: tuple[tuple[str, float], ...] = ()  # a curve's labelled rules (label, x)
    headline: tuple[Series, ...] = ()  # a parameters panel's derived figures above


def _points(panel: Panel) -> list[Point]:
    return [p for s in panel.headline + panel.series for p in s.points]


# A curve point's label is its grid x at this many places — the flag-rate grid
# steps by 0.005, so three places name each grid point exactly; a marker is
# matched to a point by this key, never by float equality (Phase 9c).
_X_PLACES = 3


def x_key(x: float) -> str:
    """The label a curve point carries for its grid x, and the key a marker's x
    is matched against (`check_panel`)."""
    return f"{x:.{_X_PLACES}f}"


def display(value: float, unit: str) -> str:
    """One number formatted for the page in its display unit — the `Unit` set's
    runtime guard: a unit outside it refuses by name. Byte-stable and
    locale-independent (`format` uses `.` and `,` in every locale)."""
    if unit == "stars":
        return f"{value:.1f}★"
    if unit == "pct":
        # A fraction stored in the mart (0.231) shown as a percent (23.1%) — a
        # unit conversion for display, not a recomputed study number; the mart
        # value on the Point stays mart-equal (round 1, code-reviewer #10).
        return f"{value * 100:.1f}%"
    if unit == "days":
        return f"{value:.1f} days"
    if unit == "count":
        return f"{int(round(value)):,}"
    if unit == "eur":
        return f"€{value:,.2f}"  # the mart rounds euros to two places (8a)
    if unit == "logeur":
        return f"{value:.6f} log-euros"  # the fit's six places (8a)
    if unit == "":
        return f"{value:.2f}"
    raise RenderRefused(f"unknown display unit {unit!r} (not in {Unit})")


def has_values(panel: Panel) -> bool:
    """True if any point carries a number — the test for a Pending panel that
    must carry none, and for the empty-mart "no data yet" state."""
    return any(p.value is not None for p in _points(panel))


def has_content(panel: Panel) -> bool:
    """True if any cell carries a value or a declared absence — the test the
    `table` kind dispatches on, so a table of all-absent cells still renders as
    a table, not "no data yet" (Phase 9b)."""
    return any(p.value is not None or p.absent for p in _points(panel))


# --- The render-time contract -------------------------------------------------
def check_panel(panel: Panel) -> None:
    """Refuse, in one line, a panel that breaks the contract: a tag that is not
    exactly one of `TAGS` (no tag, or two); a point whose tag is not in `TAGS`;
    a metric cell with both a value and a declared absence, or with neither (a
    null cell no absence explains); a Pending panel carrying any value; a
    fixture-state panel carrying any value or declared absence."""
    if panel.tag not in TAGS:
        raise RenderRefused(
            f"{panel.id}: tag {panel.tag!r} is not exactly one of {TAGS}"
        )
    for p in _points(panel):
        if p.tag not in TAGS:
            raise RenderRefused(
                f"{panel.id}: point {p.label!r} tag {p.tag!r} is not one of {TAGS}"
            )
        _check_cell(panel, p)
    if panel.tag == "Pending" and has_values(panel):
        raise RenderRefused(
            f"{panel.id}: a Pending panel shows no number — it carries a value "
            "(brief §2.4; never fake or fill a number)"
        )
    # A fixture state carries no value and no absence: the "no number" over a
    # fixture input is the contract, not the builder's construction (Phase 9b,
    # challenge round 2 amendment — the shape 9a closed for Pending).
    if panel.fixture and has_content(panel):
        raise RenderRefused(
            f"{panel.id}: a fixture-state panel shows no number — it carries "
            "content beside its fixture text (brief §2.4; never faked)"
        )
    _check_markers(panel)


def _check_markers(panel: Panel) -> None:
    """A marker is a rule at a grid x the mart holds: only a `curve` panel
    carries one, and its x must be the label of a point the panel draws — a
    marker placed between grid points would be a computed position, not a
    mart row (Phase 9c, invariant 5)."""
    if not panel.markers:
        return
    if panel.kind != "curve":
        raise RenderRefused(
            f"{panel.id}: a {panel.kind!r} panel carries markers — only a curve does"
        )
    on_grid = {p.label for p in _points(panel)}
    for label, x in panel.markers:
        if x_key(x) not in on_grid:
            raise RenderRefused(
                f"{panel.id}: marker {label!r} at x {x!r} is not a grid point the "
                "panel draws"
            )


def _check_cell(panel: Panel, point: Point) -> None:
    """A metric cell is a value xor a declared absence: both set is a
    contradiction; neither set is a null cell no absence explains (Phase 9b's
    extension of 9a's null-cell refusal). A value-less point with no absence is
    allowed only under a Pending panel (its no-number placeholder)."""
    has_value = point.value is not None
    has_absence = bool(point.absent)
    if has_value and has_absence:
        raise RenderRefused(
            f"{panel.id}: cell {point.label!r} carries both a value "
            f"({point.value!r}) and an absence ({point.absent!r}) — exactly one"
        )
    if not has_value and not has_absence and panel.tag != "Pending":
        raise RenderRefused(
            f"{panel.id}: cell {point.label!r} carries neither a value nor a "
            "declared absence (a null cell must name why it is absent)"
        )


def _require(value: float | str | None, column: str, panel_id: str) -> float | str:
    """A displayed number needs its value and provenance: a null mart cell is
    refused by name at the boundary, never coerced into an uncaught traceback
    (`float(None)`, `None.startswith`) that escapes `render` (round 2, SR#5)."""
    if value is None:
        raise RenderRefused(f"{panel_id}: mart column {column!r} is null")
    return value
