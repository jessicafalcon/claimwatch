"""Render the static HTML study from the marts and `FORMULAS` (PLAN §4.6, §4.7).

The renderers, the palette and the page. The panel model and its render-time
contract live in `study/model.py`; the readers that build panels from the marts
live in `study/panels.py`; this file turns a built `Panel` into byte-stable
inline-SVG HTML. The direction is one way: `model.py` ← `panels.py` ← this file.

The contract is enforced in `study/model.py::check_panel`, called here before a
panel renders:

- A **Pending** panel renders a labelled gray placeholder and carries no value.
- A **Documented/Measured** panel whose mart is empty renders a distinct
  "no data yet" state — never a blank, a dropped panel, or a fabricated number.
- Every rendered number carries exactly one tag, so a chart that mixes anchor
  (Documented) and captured (Measured) points marks each point.
- The output loads no CDN and no external asset (charts are hand-written inline
  SVG) and carries no render timestamp, so two renders are byte-identical.

Beat 1 is the proving ground; 9b/9c extend the contract (the counted
`unclassified` series, `FORMULAS` `expression_text`, text drill-through). The
palette is the dataviz reference default ("Ledger"), validated for both modes.

Determinism: every SVG coordinate is formatted at fixed precision through `_n`
(locale-independent), every query carries its own `order by`, and no value is
recomputed here — each number is read from its mart."""

from __future__ import annotations

import html
from pathlib import Path

from pipeline.warehouse import ROOT, connect, database_for
from study.model import (
    NEUTRAL,
    TAGS,
    Panel,
    RenderRefused,
    Unit,
    _points,
    check_panel,
    has_content,
    has_values,
)
from study.panels import beat1_panels, beat2_panels

# The render input is the frozen synthetic database: Beat 1's Documented points
# are the anchors only (no manual/fetched snapshot — those are `captured`-only),
# so the committed baseline cannot drift with the weekly cron (spec pinned
# decision). `make study` reads this file; a caller (a test) may name another.
DEFAULT_DB = database_for("synthetic")
OUTPUT = ROOT / "study" / "friction_ledger.html"


# --- The palette: the dataviz reference default "Ledger", light + dark. -------
# Series slots are the validated categorical order (worst adjacent CVD ΔE 9.1
# light / 8.4 dark); the chrome/ink and the Pending gray are the reference
# chart-surface tokens. Emitted once as CSS custom properties; the SVG reads the
# series hexes by slot. Never reordered — the order is the CVD-safety mechanism.
# One hex per theme slot: `len(SERIES_*)` must cover `THEMES` (a sixth theme
# maps to slot 5, which `_series_var` refuses loudly — fail-safe, not silent).
SERIES_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
SERIES_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181")
# The `unclassified` band's neutral series colour (`var(--sN)`): a mid gray,
# low-chroma by construction so it reads apart from all five hues without being
# a sixth categorical slot (Phase 9b, pinned decision 4; dataviz: a neutral band
# is not a series). Distinct from the recessive grid/baseline chrome.
NEUTRAL_LIGHT = "#9a988f"
NEUTRAL_DARK = "#7a7975"
_LIGHT = {
    "surface": "#fcfcfb",
    "page": "#f9f9f7",
    "ink": "#0b0b0b",
    "ink2": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    "pending": "#e1e0d9",
}
_DARK = {
    "surface": "#1a1a19",
    "page": "#0d0d0d",
    "ink": "#ffffff",
    "ink2": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "baseline": "#383835",
    "pending": "#2c2c2a",
}

# One chart geometry for every plot, so coordinates are byte-stable constants.
_W, _H = 680, 280
_ML, _MR, _MT, _MB = 48, 16, 16, 40


# --- Number formatting (byte-stable, locale-independent) ----------------------
def _n(x: float) -> str:
    """A coordinate at fixed precision — `format` uses '.' in every locale, so
    the bytes do not shift with LANG."""
    return f"{x:.2f}"


def _display(value: float, unit: str) -> str:
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
    if unit == "":
        return f"{value:.2f}"
    raise RenderRefused(f"unknown display unit {unit!r} (not in {Unit})")


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _series_var(colour: int | str) -> str:
    """The CSS colour for a series: a categorical slot `0..4` or the neutral
    band token. Anything else is refused by name — never a sentinel integer
    reaching an undefined `var(--sN)` slot (Phase 9b, pinned decision 4)."""
    if colour == NEUTRAL:
        return "var(--sN)"
    if isinstance(colour, int) and 0 <= colour <= 4:
        return f"var(--s{colour})"
    raise RenderRefused(
        f"series colour {colour!r} is not a slot 0..4 or the {NEUTRAL!r} token"
    )


def _detail(point) -> str:
    """The tooltip suffix carrying a point's raw counts (the trail behind a
    share), or empty when the point has none — so Beat 1 tooltips are unchanged."""
    return f" · {_esc(point.detail)}" if point.detail else ""


# --- SVG chart rendering ------------------------------------------------------
_AXIS_TICKS = 4  # one grid step count for every plot; a byte-stable constant


def _axis(domain: tuple[float, float]) -> list[tuple[float, str]]:
    lo, hi = domain
    ticks: list[tuple[float, str]] = []
    for i in range(_AXIS_TICKS + 1):
        value = lo + (hi - lo) * i / _AXIS_TICKS
        ticks.append((value, f"{value:g}"))
    return ticks


def _y_of(value: float, domain: tuple[float, float]) -> float:
    lo, hi = domain
    span = hi - lo or 1.0
    return _H - _MB - (value - lo) / span * (_H - _MT - _MB)


def _svg_open() -> list[str]:
    return [
        f'<svg viewBox="0 0 {_W} {_H}" role="img" '
        'preserveAspectRatio="xMidYMid meet" class="chart">'
    ]


def _grid_and_axis(domain: tuple[float, float]) -> list[str]:
    out: list[str] = []
    for value, label in _axis(domain):
        y = _y_of(value, domain)
        out.append(
            f'<line x1="{_n(_ML)}" y1="{_n(y)}" x2="{_n(_W - _MR)}" y2="{_n(y)}" '
            'class="grid"/>'
        )
        out.append(
            f'<text x="{_n(_ML - 6)}" y="{_n(y + 3)}" class="tick" '
            f'text-anchor="end">{_esc(label)}</text>'
        )
    return out


def _render_line(panel: Panel) -> list[str]:
    months = sorted({p.label for s in panel.series for p in s.points})
    step = (_W - _ML - _MR) / (max(len(months) - 1, 1))
    x_of = {m: _ML + i * step for i, m in enumerate(months)}
    out = _svg_open()
    out += _grid_and_axis(panel.domain)
    for s in panel.series:
        colour_var = _series_var(s.colour)
        coords = [
            (x_of[p.label], _y_of(p.value, panel.domain), p)
            for p in s.points
            if p.value is not None
        ]
        if len(coords) > 1:
            pts = " ".join(f"{_n(x)},{_n(y)}" for x, y, _ in coords)
            out.append(
                f'<polyline points="{pts}" fill="none" stroke="{colour_var}" '
                'stroke-width="2"/>'
            )
        for x, y, p in coords:
            out.append(
                f'<circle cx="{_n(x)}" cy="{_n(y)}" r="4" fill="{colour_var}">'
                f"<title>{_esc(s.name)} · {_esc(p.label)}: "
                f"{_esc(_display(p.value, p.unit))}{_detail(p)}"
                f" ({_esc(p.tag)})</title></circle>"
            )
    for m in months:
        out.append(
            f'<text x="{_n(x_of[m])}" y="{_n(_H - _MB + 16)}" class="tick" '
            f'text-anchor="middle">{_esc(m)}</text>'
        )
    out.append("</svg>")
    return out


def _render_grouped_bar(panel: Panel) -> list[str]:
    bars = [(s, p) for s in panel.series for p in s.points if p.value is not None]
    n = len(bars) or 1
    band = (_W - _ML - _MR) / n
    width = band * 0.6
    out = _svg_open()
    out += _grid_and_axis(panel.domain)
    for i, (s, p) in enumerate(bars):
        x = _ML + i * band + (band - width) / 2
        y = _y_of(p.value, panel.domain)
        base = _y_of(panel.domain[0], panel.domain)
        out.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(width)}" '
            f'height="{_n(base - y)}" rx="4" fill="{_series_var(s.colour)}">'
            f"<title>{_esc(s.name)} · {_esc(p.label)}: "
            f"{_esc(_display(p.value, p.unit))}{_detail(p)} "
            f"({_esc(p.tag)})</title></rect>"
        )
        out.append(
            f'<text x="{_n(x + width / 2)}" y="{_n(base + 16)}" class="tick" '
            f'text-anchor="middle">{_esc(p.label)}</text>'
        )
        out.append(
            f'<text x="{_n(x + width / 2)}" y="{_n(y - 6)}" class="barval" '
            f'text-anchor="middle">{_esc(_display(p.value, p.unit))}</text>'
        )
    out.append("</svg>")
    return out


def _render_legend(panel: Panel) -> list[str]:
    """The legend: drawn when a panel has more than one series, and always when
    it carries the neutral `unclassified` band — a corpus the rules sort into
    positive/unclassified alone leaves one series, and the band's count must
    still read in the legend (invariant 3; round 2, code-reviewer #2)."""
    has_band = any(s.colour == NEUTRAL for s in panel.series)
    if len(panel.series) < 2 and not has_band:
        return []
    out = ['<ul class="legend">']
    for s in panel.series:
        out.append(
            f'<li><span class="swatch" style="background:{_series_var(s.colour)}">'
            f"</span>{_esc(s.name)}</li>"
        )
    out.append("</ul>")
    return out


def _render_stat_row(panel: Panel) -> list[str]:
    # Reached only with values: _render_body returns the empty-mart state before
    # dispatching here, and every stat point carries a value (_platform_stats).
    out = ['<div class="stat-row">']
    for p in _points(panel):
        out.append(
            '<div class="stat">'
            f'<div class="stat-value">{_esc(_display(p.value, p.unit))}</div>'
            f'<div class="stat-label">{_esc(p.label)}</div>'
            f"{_render_chip(p.tag)}</div>"
        )
    out.append("</div>")
    return out


def _metric_cell(point) -> str:
    """One table cell: a value with its raw counts, or a labelled absence with
    its counts — never both, never blank (`check_panel` guarantees the xor)."""
    if point.absent:
        absence = f'<span class="absent">{_esc(point.absent)}</span>'
        return f"{absence} ({_esc(point.detail)})"
    return (
        f"{_esc(_display(point.value, point.unit))} "
        f'<span class="cnt">({_esc(point.detail)})</span>'
    )


def _render_table(panel: Panel) -> list[str]:
    # Reached only with content: _render_body returns "no data yet" first when a
    # table has no present cell. One row per series (a label), its cells in the
    # column order the panel declares.
    out = ['<table class="metric"><thead><tr>']
    out += [f"<th>{_esc(col)}</th>" for col in panel.columns]
    out.append("</tr></thead><tbody>")
    for s in panel.series:
        out.append(f'<tr><th scope="row">{_esc(s.name)}</th>')
        out += [f"<td>{_metric_cell(p)}</td>" for p in s.points]
        out.append("</tr>")
    out.append("</tbody></table>")
    return out


# The chip's CSS class is a closed lookup keyed on the four tags, so the class
# attribute is safe by construction — not a raw tag string interpolated on the
# trust that `check_panel` validated it first on this path (round 2, SR#4).
_CHIP_CLASS = {
    "Measured": "measured",
    "Documented": "documented",
    "Modeled": "modeled",
    "Pending": "pending",
}


def _render_chip(tag: str) -> str:
    if tag not in _CHIP_CLASS:
        raise RenderRefused(f"chip tag {tag!r} is not one of {tuple(_CHIP_CLASS)}")
    return f'<span class="chip chip-{_CHIP_CLASS[tag]}">{_esc(tag)}</span>'


def _panel_tags(panel: Panel) -> list[str]:
    """The distinct evidence tags the panel's points carry, in `TAGS` order, so a
    mixed panel shows a chip per tag and a Pending panel shows its own tag."""
    present = {p.tag for p in _points(panel)} or {panel.tag}
    return [t for t in TAGS if t in present]


def _render_body(panel: Panel) -> list[str]:
    # A Pending panel shows its placeholder by its authoritative `tag`, never by
    # a `kind` coincidence: the "distinct from Pending" state rests on the tag,
    # not on B1.1 happening to be a hero (round 1, code-reviewer, caller-sourced).
    if panel.tag == "Pending":
        return [f'<div class="pending">{_esc(panel.placeholder)}</div>']
    # A corpus panel over a fixture input renders a labelled state and no number
    # — distinct from Pending and from "no data yet" (Phase 9b, the corpus gate).
    if panel.fixture:
        return [f'<div class="fixture">{_esc(panel.fixture)}</div>']
    # A table dispatches on "any cell present" (value or absence), so a table of
    # absences still renders as a table, not "no data yet" (pinned decision 5).
    if panel.kind == "table":
        if not has_content(panel):
            return _nodata()
        return _render_table(panel)
    if not has_values(panel):
        return _nodata()
    if panel.kind == "line":
        return _render_line(panel) + _render_legend(panel)
    if panel.kind == "grouped_bar":
        return _render_grouped_bar(panel) + _render_legend(panel)
    if panel.kind == "stat_row":
        return _render_stat_row(panel)
    raise RenderRefused(f"{panel.id}: unknown panel kind {panel.kind!r}")


def _nodata() -> list[str]:
    return ['<p class="nodata">No data yet — this panel’s mart is empty.</p>']


def _render_panel(panel: Panel) -> list[str]:
    check_panel(panel)
    chips = "".join(_render_chip(t) for t in _panel_tags(panel))
    out = [
        '<section class="panel">',
        f"<h3>{_esc(panel.id)} · {_esc(panel.title)} {chips}</h3>",
        f'<p class="blurb">{_esc(panel.blurb)}</p>',
    ]
    out += _render_body(panel)
    for note in panel.notes:  # one <p> per note, so the second layer stays scannable
        out.append(f'<p class="note">{_esc(note)}</p>')
    # The footer's tag is DERIVED from the points actually shown (the same
    # `_panel_tags` the header chips use), not the authored `panel.tag`, so the
    # two can never disagree and a mixed Documented+Measured panel names both
    # (round 1, code-reviewer, caller-sourced). A Pending panel with no points
    # falls back to its declared tag.
    tags = ", ".join(_panel_tags(panel))
    out.append(
        f'<p class="evidence">Evidence: {_esc(panel.backing_row)} · '
        f"{_esc(tags)} · " + _drill(panel) + "</p>"
    )
    out.append("</section>")
    return out


def _drill(panel: Panel) -> str:
    # Only an http(s) address becomes a clickable href: escaping neutralises
    # HTML metacharacters but not the URL scheme, so a `javascript:`/`data:`
    # source is dropped, not rendered as a live link (round 1, security #16).
    # A computed number (a theme share) carries no per-row address; the panel
    # cites its platform roots at the panel level (`sources`) instead.
    addresses = [p.source_url for p in _points(panel)] + list(panel.sources)
    urls = sorted({u for u in addresses if _is_http(u)})
    if not urls:
        return "source pending"
    links = ", ".join(f'<a href="{_esc(u)}" rel="noopener">{_esc(u)}</a>' for u in urls)
    return f"opens to {links} and PROJECT_BRIEF §6"


def _is_http(url: str) -> bool:
    return url.startswith(("http://", "https://"))


# --- The page -----------------------------------------------------------------
def _css() -> str:
    def tokens(scope: dict[str, str]) -> str:
        pairs = [f"--{k}:{v};" for k, v in sorted(scope.items())]
        series = [f"--s{i}:{hex_};" for i, hex_ in enumerate(SERIES_LIGHT)]
        return "".join(pairs + series) + f"--sN:{NEUTRAL_LIGHT};"

    def dark_series() -> str:
        slots = "".join(f"--s{i}:{hex_};" for i, hex_ in enumerate(SERIES_DARK))
        return slots + f"--sN:{NEUTRAL_DARK};"

    light = tokens(_LIGHT)
    dark = "".join(f"--{k}:{v};" for k, v in sorted(_DARK.items())) + dark_series()
    return _CSS_TEMPLATE.format(light=light, dark=dark)


def _beat_header(title: str) -> str:
    return f'<h2 class="beat">{_esc(title)}</h2>'


# The beats in render order, each a (header, builder) pair. A new beat adds one
# row; the render loop and the page do not change (9c–9e).
_BEATS = (
    ("Beat 1 — People are telling us what’s wrong, in public", beat1_panels),
    ("Beat 2 — The complaints have a shape", beat2_panels),
)


def render(conn) -> str:
    """The full study HTML as one string, from the panels the marts fill."""
    body: list[str] = []
    for header, builder in _BEATS:
        body.append(_beat_header(header))
        for panel in builder(conn):
            body += _render_panel(panel)
    return _PAGE.format(css=_css(), body="\n".join(body))


def write(db: Path | None = None, out: Path | None = None) -> Path:
    """Render from `db` and write `out`; returns the path written. The defaults
    are read at call time (the module's `DEFAULT_DB` and `OUTPUT`), so `make
    study` renders over the frozen synthetic database and a test can redirect
    both. CI diffs the committed bytes."""
    db = DEFAULT_DB if db is None else db
    out = OUTPUT if out is None else out
    conn = connect("duckdb", database=db)
    try:
        page = render(conn)
    finally:
        conn.close()
    out.write_text(page, encoding="utf-8")
    return out


_CSS_TEMPLATE = (
    ":root{{color-scheme:light;{light}}}"
    "@media (prefers-color-scheme:dark){{:root:where(:not([data-theme=light]))"
    "{{color-scheme:dark;{dark}}}}}"
    ":root[data-theme=dark]{{color-scheme:dark;{dark}}}"
    "*{{box-sizing:border-box}}"
    "body{{margin:0;background:var(--page);color:var(--ink);"
    'font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}'
    ".wrap{{max-width:860px;margin:0 auto;padding:32px 20px}}"
    "h1{{font-size:26px;margin:0 0 4px}}"
    ".lede{{color:var(--ink2);margin:0 0 28px}}"
    ".beat{{font-size:20px;margin:24px 0 12px}}"
    ".panel{{background:var(--surface);border:1px solid var(--grid);"
    "border-radius:10px;padding:20px 22px;margin:0 0 20px}}"
    "h3{{font-size:17px;margin:0 0 8px}}"
    ".blurb{{color:var(--ink2);margin:0 0 14px}}"
    ".note{{color:var(--muted);font-size:13px;margin:12px 0 0}}"
    ".evidence{{color:var(--muted);font-size:12px;margin:12px 0 0;"
    "border-top:1px solid var(--grid);padding-top:8px;word-break:break-word}}"
    ".evidence a{{color:var(--s0)}}"
    ".chart{{width:100%;height:auto;display:block}}"
    ".grid{{stroke:var(--grid);stroke-width:1}}"
    ".tick{{fill:var(--muted);font-size:11px}}"
    ".barval{{fill:var(--ink2);font-size:12px;font-weight:600}}"
    ".legend{{list-style:none;display:flex;flex-wrap:wrap;gap:14px;"
    "padding:10px 0 0;margin:0;font-size:13px;color:var(--ink2)}}"
    ".legend li{{display:flex;align-items:center;gap:6px}}"
    ".swatch{{width:12px;height:12px;border-radius:3px;display:inline-block}}"
    ".stat-row{{display:flex;flex-wrap:wrap;gap:16px}}"
    ".stat{{flex:1;min-width:120px;background:var(--page);border:1px solid "
    "var(--grid);border-radius:8px;padding:14px}}"
    ".stat-value{{font-size:24px;font-weight:700}}"
    ".stat-label{{color:var(--ink2);font-size:13px;margin:2px 0 8px}}"
    ".pending{{background:repeating-linear-gradient(45deg,"
    "var(--pending),var(--pending) 8px,transparent 8px,transparent 16px);"
    "border:1px dashed var(--baseline);border-radius:8px;padding:18px;"
    "color:var(--ink2);font-size:14px}}"
    ".nodata{{background:var(--page);border:1px solid var(--grid);"
    "border-radius:8px;padding:18px;color:var(--muted);font-style:italic;"
    "font-size:14px}}"
    ".fixture{{background:var(--page);border:1px solid var(--baseline);"
    "border-left:3px solid var(--sN);border-radius:8px;padding:16px 18px;"
    "color:var(--ink2);font-size:14px}}"
    ".metric{{width:100%;border-collapse:collapse;font-size:13px;margin:4px 0 0}}"
    ".metric th,.metric td{{text-align:left;padding:8px 10px;"
    "border-bottom:1px solid var(--grid)}}"
    ".metric thead th{{color:var(--muted);font-weight:600;font-size:12px}}"
    ".metric tbody th{{font-weight:600;color:var(--ink)}}"
    ".metric .cnt{{color:var(--muted)}}"
    ".metric .absent{{color:var(--muted);font-style:italic}}"
    ".chip{{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;"
    "border-radius:99px;border:1px solid var(--baseline);color:var(--ink2);"
    "vertical-align:middle}}"
    ".chip-pending{{background:var(--pending)}}"
    ".stat .chip{{margin-top:2px}}"
)

_PAGE = (
    "<!doctype html>\n"
    '<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>The Friction Ledger</title>"
    '<style>{css}</style></head><body><main class="wrap">'
    "<h1>The Friction Ledger</h1>"
    '<p class="lede">Why health-insurance refunds get stuck — read from the '
    "customer’s chair, every number tagged for where it came from.</p>\n"
    "{body}\n"
    "</main></body></html>\n"
)
