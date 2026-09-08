"""The study's panel model and its render-time contract, as data (PLAN §4.6).

One layer below the renderers: the frozen types a panel is made of, the four
evidence tags, the closed chart-kind and unit sets, and `check_panel` — the
render-time guard that refuses a panel breaking the contract. `study/panels.py`
builds these from the marts; `study/export.py` renders them. Nothing here reads
a database or emits HTML.

The contract, checked here, not by editorial trust:

- A panel is data — `Panel(id, backing_row, tag, kind, series, note)`. Its `tag`
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
# (unknown kind refuses) and `_display` (unknown unit refuses).
Kind = Literal["hero", "line", "grouped_bar", "stat_row"]
Unit = Literal["stars", "pct", "days", "count", ""]


class RenderRefused(Exception):
    """A one-line render refusal: printed as-is, non-zero exit, never a
    traceback (the same boundary policy as pipeline/cli.py's `Refused`)."""


@dataclass(frozen=True)
class Point:
    """One marked number in a panel: its label (a month, a channel, a stat), its
    value in the mart's own units, its evidence tag, and the platform-root
    address it opens to. `value is None` marks a Pending placeholder — never
    rendered as a number."""

    label: str
    value: float | None
    tag: str
    source_url: str
    unit: Unit = ""


@dataclass(frozen=True)
class Series:
    """One line or one group of bars, coloured by categorical slot."""

    name: str
    slot: int
    points: tuple[Point, ...]


@dataclass(frozen=True)
class Panel:
    """A study panel as data. `tag` is the BACKING-declared evidence tag; `kind`
    is one of hero | line | grouped_bar | stat_row."""

    id: str
    backing_row: str
    title: str
    blurb: str
    tag: str
    kind: Kind
    series: tuple[Series, ...] = ()
    note: str = ""
    placeholder: str = ""  # the Pending panel's labelled gray text
    domain: tuple[float, float] = (0.0, 5.0)
    axis_unit: str = "stars"


def _points(panel: Panel) -> list[Point]:
    return [p for s in panel.series for p in s.points]


def has_values(panel: Panel) -> bool:
    """True if any point carries a number — the test for a Pending panel that
    must carry none."""
    return any(p.value is not None for p in _points(panel))


# --- The render-time contract -------------------------------------------------
def check_panel(panel: Panel) -> None:
    """Refuse, in one line, a panel that breaks the contract: a tag that is not
    exactly one of `TAGS` (no tag, or two); a point whose tag is not in `TAGS`;
    a Pending panel carrying any value."""
    if panel.tag not in TAGS:
        raise RenderRefused(
            f"{panel.id}: tag {panel.tag!r} is not exactly one of {TAGS}"
        )
    for p in _points(panel):
        if p.tag not in TAGS:
            raise RenderRefused(
                f"{panel.id}: point {p.label!r} tag {p.tag!r} is not one of {TAGS}"
            )
    if panel.tag == "Pending" and has_values(panel):
        raise RenderRefused(
            f"{panel.id}: a Pending panel shows no number — it carries a value "
            "(brief §2.4; never fake or fill a number)"
        )


def _require(value: float | str | None, column: str, panel_id: str) -> float | str:
    """A displayed number needs its value and provenance: a null mart cell is
    refused by name at the boundary, never coerced into an uncaught traceback
    (`float(None)`, `None.startswith`) that escapes `render` (round 2, SR#5)."""
    if value is None:
        raise RenderRefused(f"{panel_id}: mart column {column!r} is null")
    return value
