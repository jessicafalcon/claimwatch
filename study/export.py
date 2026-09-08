"""Render the static HTML study from the marts and `FORMULAS` (PLAN §4.6, §4.7).

The contract, checked at render time, not by editorial trust:

- A panel is data — `Panel(id, backing_row, tag, kind, series, note)`. Its `tag`
  is the one BACKING evidence tag; a panel whose tag is not exactly one of
  `TAGS` is refused (no tag, or two).
- A **Pending** panel renders a labelled gray placeholder and carries no value;
  a Pending panel handed a value is refused (brief §2.4; the render-time
  no-number guard).
- A **Documented/Measured** panel whose mart is empty renders a distinct
  "no data yet" state — never a blank, a dropped panel, or a fabricated number.
- Every rendered number carries exactly one tag (its point's own `tag`, in
  `TAGS`), so a chart that mixes anchor (Documented) and captured (Measured)
  points marks each point.
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
from dataclasses import dataclass
from pathlib import Path

from pipeline.warehouse import ROOT, connect, database_for

# The render input is the frozen synthetic database: Beat 1's Documented points
# are the anchors only (no manual/fetched snapshot — those are `captured`-only),
# so the committed baseline cannot drift with the weekly cron (spec pinned
# decision). `make study` reads this file; a caller (a test) may name another.
DEFAULT_DB = database_for("synthetic")
OUTPUT = ROOT / "study" / "friction_ledger.html"

# The four evidence tags (brief §2.4). A panel's tag, and every point's tag, is
# exactly one of these; anything else is refused.
TAGS = ("Measured", "Documented", "Modeled", "Pending")


class RenderRefused(Exception):
    """A one-line render refusal: printed as-is, non-zero exit, never a
    traceback (the same boundary policy as pipeline/cli.py's `Refused`)."""


# --- The palette: the dataviz reference default "Ledger", light + dark. -------
# Series slots are the validated categorical order (worst adjacent CVD ΔE 9.1
# light / 8.4 dark); the chrome/ink and the Pending gray are the reference
# chart-surface tokens. Emitted once as CSS custom properties; the SVG reads the
# series hexes by slot. Never reordered — the order is the CVD-safety mechanism.
SERIES_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
SERIES_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181")
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


# --- The panel model ----------------------------------------------------------
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
    unit: str = ""  # "stars" | "pct" | "days" | "count" | ""


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
    kind: str
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


# --- Reading the Beat 1 marts (every query carries its own order by) ----------
def _rows(conn, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


def _rating_trend(conn) -> tuple[Series, ...]:
    """B1.2: the studied segment's unsolicited rating over time, one line per
    profile (a brand-free role slug). Anchors only under `synthetic`."""
    rows = _rows(
        conn,
        "select profile, month, rating, tag, source_url from rating_trend "
        "where channel = 'unsolicited' and segment = 'digital-first' "
        "order by profile, month",
    )
    by_profile: dict[str, list[Point]] = {}
    for profile, month, rating, tag, url in rows:
        by_profile.setdefault(profile, []).append(
            Point(str(month), float(rating), tag, url, "stars")
        )
    return tuple(
        Series(_PROFILE_NAMES.get(profile, profile), slot, tuple(pts))
        for slot, (profile, pts) in enumerate(sorted(by_profile.items()))
    )


def _channel_gap(conn) -> tuple[Series, ...]:
    """B1.3: the studied insurer's rating on each invited channel and each
    unsolicited one, one bar per (channel, source), coloured by channel."""
    rows = _rows(
        conn,
        "select channel, source, rating, tag, source_url from channel_gap "
        "where segment = 'digital-first' and profile = 'fr-digital-first' "
        "order by channel, source",
    )
    channels = sorted({channel for channel, *_ in rows})
    slot_of = {channel: i for i, channel in enumerate(channels)}
    by_channel: dict[str, list[Point]] = {}
    for channel, source, rating, tag, url in rows:
        by_channel.setdefault(channel, []).append(
            Point(source, float(rating), tag, url, "stars")
        )
    return tuple(
        Series(channel, slot_of[channel], tuple(by_channel[channel]))
        for channel in channels
    )


_STAT_LABELS = {
    "review_count": ("Reviews", "count"),
    "one_star_share": ("One-star share", "pct"),
    "response_rate": ("Reviews answered", "pct"),
    "response_delay_days": ("Typical answer time", "days"),
}


def _platform_stats(conn) -> tuple[Series, ...]:
    """B1.4: the studied insurer's stat row, one tile per stat, from the one
    platform that carries the full set (the comparison across platforms waits —
    SPEC B1.4)."""
    rows = _rows(
        conn,
        "select stat, value, tag, source_url from platform_stats "
        "where segment = 'digital-first' and profile = 'fr-digital-first' "
        "and source = 'opinion-assurances' order by stat",
    )
    order = list(_STAT_LABELS)
    points = [
        Point(_STAT_LABELS[stat][0], float(value), tag, url, _STAT_LABELS[stat][1])
        for stat, value, tag, url in sorted(rows, key=lambda r: order.index(r[0]))
    ]
    return (Series("stats", 0, tuple(points)),) if points else ()


# Brand-free display names for the role slugs the marts carry (D1: no brand
# token leaves ingest/sources.py; these are roles, not names).
_PROFILE_NAMES = {
    "fr-digital-first": "Studied digital-first insurer",
    "peer-digital-challenger-1": "Digital challenger (peer)",
}


def beat1_panels(conn) -> list[Panel]:
    """The four Beat 1 panels, built from the marts. B1.1 is Pending (the hero
    case is not yet curated); B1.2–B1.4 are Documented under the anchors."""
    return [
        Panel(
            id="B1.1",
            backing_row="B1.1",
            title="One refund, held for months",
            blurb=(
                "One documented case shows the whole pattern: a roughly €340 "
                "emergency-room refund put on hold pending extra documents, "
                "reported unresolved for months. The day count is frozen at the "
                "last publicly confirmed date — never a live ticker we cannot "
                "verify."
            ),
            tag="Pending",
            kind="hero",
            placeholder=(
                "Awaiting the curated public case and its link. A “Day N — claim "
                "on hold” figure, frozen at the last confirmed date, lands here "
                "with its source."
            ),
        ),
        Panel(
            id="B1.2",
            backing_row="B1.2",
            title="The public rating over time",
            blurb=(
                "Customers rate the segment’s insurers on platforms they were not "
                "invited to. This is that rating month by month, on the unsolicited "
                "channel."
            ),
            tag="Documented",
            kind="line",
            series=_rating_trend(conn),
            note=(
                "Sampling bias, stated here: unsolicited review platforms are "
                "negatively self-selected — a company that stops inviting reviews "
                "drifts down — so part of any decline is a sampling choice, not "
                "only a service change."
            ),
            domain=(1.0, 5.0),
            axis_unit="stars",
        ),
        Panel(
            id="B1.3",
            backing_row="B1.3",
            title="The channel gap",
            blurb=(
                "The same insurer looks very different on channels it invites and "
                "channels it does not. Each bar is the latest rating on one "
                "platform."
            ),
            tag="Documented",
            kind="grouped_bar",
            series=_channel_gap(conn),
            domain=(0.0, 5.0),
            axis_unit="stars",
        ),
        Panel(
            id="B1.4",
            backing_row="B1.4",
            title="The stat row",
            blurb=(
                "A few numbers that place the ratings in context: how many reviews, "
                "how many one-star, how often and how fast the company answers."
            ),
            tag="Documented",
            kind="stat_row",
            series=_platform_stats(conn),
            note=(
                "Stated here: today the answer rate and time are measured for one "
                "profile on one platform, so the comparison across platforms waits "
                "for a second platform’s figures."
            ),
        ),
    ]


# --- Number formatting (byte-stable, locale-independent) ----------------------
def _n(x: float) -> str:
    """A coordinate at fixed precision — `format` uses '.' in every locale, so
    the bytes do not shift with LANG."""
    return f"{x:.2f}"


def _display(value: float, unit: str) -> str:
    if unit == "stars":
        return f"{value:.1f}★"
    if unit == "pct":
        return f"{value * 100:.1f}%"
    if unit == "days":
        return f"{value:.1f} days"
    if unit == "count":
        return f"{int(round(value)):,}"
    return f"{value:.2f}"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


# --- SVG chart rendering ------------------------------------------------------
def _axis(domain: tuple[float, float], ticks: int) -> list[tuple[float, str]]:
    lo, hi = domain
    return [
        (lo + (hi - lo) * i / ticks, f"{lo + (hi - lo) * i / ticks:g}")
        for i in range(ticks + 1)
    ]


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
    for value, label in _axis(domain, 4):
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
        colour_var = f"var(--s{s.slot})"
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
                f"<title>{_esc(s.name)} · {p.label}: {_esc(_display(p.value, p.unit))}"
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
            f'height="{_n(base - y)}" rx="4" fill="var(--s{s.slot})">'
            f"<title>{_esc(s.name)} · {_esc(p.label)}: "
            f"{_esc(_display(p.value, p.unit))} ({_esc(p.tag)})</title></rect>"
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
    if len(panel.series) < 2:
        return []
    out = ['<ul class="legend">']
    for s in panel.series:
        out.append(
            f'<li><span class="swatch" style="background:var(--s{s.slot})"></span>'
            f"{_esc(s.name)}</li>"
        )
    out.append("</ul>")
    return out


def _render_stat_row(panel: Panel) -> list[str]:
    points = _points(panel)
    if not points:
        return ['<p class="nodata">No data yet.</p>']
    out = ['<div class="stat-row">']
    for p in points:
        assert p.value is not None  # a stat tile with no value is caught upstream
        out.append(
            '<div class="stat">'
            f'<div class="stat-value">{_esc(_display(p.value, p.unit))}</div>'
            f'<div class="stat-label">{_esc(p.label)}</div>'
            f"{_render_chip(p.tag)}</div>"
        )
    out.append("</div>")
    return out


def _render_chip(tag: str) -> str:
    slug = tag.lower()
    return f'<span class="chip chip-{slug}">{_esc(tag)}</span>'


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
    if not has_values(panel):
        return ['<p class="nodata">No data yet — this panel’s mart is empty.</p>']
    if panel.kind == "line":
        return _render_line(panel) + _render_legend(panel)
    if panel.kind == "grouped_bar":
        return _render_grouped_bar(panel) + _render_legend(panel)
    if panel.kind == "stat_row":
        return _render_stat_row(panel)
    raise RenderRefused(f"{panel.id}: unknown panel kind {panel.kind!r}")


def _render_panel(panel: Panel) -> list[str]:
    check_panel(panel)
    chips = "".join(_render_chip(t) for t in _panel_tags(panel))
    out = [
        '<section class="panel">',
        f"<h3>{_esc(panel.id)} · {_esc(panel.title)} {chips}</h3>",
        f'<p class="blurb">{_esc(panel.blurb)}</p>',
    ]
    out += _render_body(panel)
    if panel.note:
        out.append(f'<p class="note">{_esc(panel.note)}</p>')
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
    urls = sorted({p.source_url for p in _points(panel) if p.source_url})
    if not urls:
        return "source pending"
    links = ", ".join(f'<a href="{_esc(u)}" rel="noopener">{_esc(u)}</a>' for u in urls)
    return f"opens to {links} and PROJECT_BRIEF §6"


# --- The page -----------------------------------------------------------------
def _css() -> str:
    def tokens(scope: dict[str, str]) -> str:
        pairs = [f"--{k}:{v};" for k, v in sorted(scope.items())]
        series = [f"--s{i}:{hex_};" for i, hex_ in enumerate(SERIES_LIGHT)]
        return "".join(pairs + series)

    def dark_series() -> str:
        return "".join(f"--s{i}:{hex_};" for i, hex_ in enumerate(SERIES_DARK))

    light = tokens(_LIGHT)
    dark = "".join(f"--{k}:{v};" for k, v in sorted(_DARK.items())) + dark_series()
    return _CSS_TEMPLATE.format(light=light, dark=dark)


def render(conn) -> str:
    """The full study HTML as one string, from the panels the marts fill."""
    panels = beat1_panels(conn)
    body: list[str] = []
    for panel in panels:
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
    ".pending,.nodata{{background:repeating-linear-gradient(45deg,"
    "var(--pending),var(--pending) 8px,transparent 8px,transparent 16px);"
    "border:1px dashed var(--baseline);border-radius:8px;padding:18px;"
    "color:var(--ink2);font-size:14px}}"
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
    "customer’s chair, every number tagged for where it came from.</p>"
    '<h2 style="font-size:20px;margin:24px 0 12px">Beat 1 — People are telling '
    "us what’s wrong, in public</h2>\n"
    "{body}\n"
    "</main></body></html>\n"
)
