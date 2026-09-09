"""Build the study's panels from the marts (PLAN §4.6). One layer above
`study/model.py` (the types and the contract) and one below `study/export.py`
(the renderers): a reader per chart turns mart rows into `Panel`s, every number
read straight from its mart and never recomputed here, every query carrying its
own `order by` so the bytes are stable.

Two Phase 9b mechanisms live here:

- **The column allowlist.** Every study query goes through `_rows`, which reads
  the cursor's own description and refuses a projected column outside the closed
  `ALLOWED_COLUMNS` — so review text (`title`, `body`) can never reach the page
  and `select *` fails by name. `STUDY_QUERIES` is every query the export runs,
  linted for portability and the clock by a test.
- **The corpus gate.** A panel whose numbers derive from the review corpus
  reads the mart's own `run_id`: `captured` renders the counted numbers, a
  fixture input renders a labelled fixture state and no number (the brief's
  "never faked" applied at render time), an empty mart renders 9a's "no data
  yet". Two run_ids, or one outside `INPUTS`, refuse in one line."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from classify.labels import POSITIVE, THEMES, UNCLASSIFIED
from pipeline.build import INPUTS
from pipeline.warehouse import default_schema
from study.model import NEUTRAL, Panel, Point, RenderRefused, Series, _require

# The only columns any study query may project — a closed allowlist checked on
# every cursor's description, so review text (`title`, `body`) can never reach
# the page and `select *` fails by name (Phase 9b, pinned decision 3; the
# personal-data guarantee is structural, not a denylist on query text).
ALLOWED_COLUMNS = frozenset(
    {
        # Beat 1: rating_trend, channel_gap, platform_stats
        "profile",
        "month",
        "rating",
        "tag",
        "source_url",
        "channel",
        "source",
        "segment",
        "stat",
        "value",
        # Beat 2: peer_ratings, the two theme marts, classifier_quality
        "review_count",
        "label",
        "reviews",
        "theme_rows",
        "share",
        "run_id",
        "hits",
        "predicted",
        "actual",
        "precision",
        "recall",
    }
)

# Every query the export runs, in one tuple, so a test lints each for portability
# and the clock (the pipeline/metrics.py pattern; Phase 9b, pinned decision 3).
_Q_RATING_TREND = (
    "select profile, month, rating, tag, source_url from rating_trend "
    "where channel = 'unsolicited' and segment = 'digital-first' "
    "order by profile, month, source"
)
_Q_CHANNEL_GAP = (
    "select channel, source, rating, tag, source_url from channel_gap "
    "where segment = 'digital-first' and profile = 'fr-digital-first' "
    "order by channel, source"
)
_Q_PLATFORM_STATS = (
    "select stat, value, tag, source_url from platform_stats "
    "where segment = 'digital-first' and profile = 'fr-digital-first' "
    "and source = 'opinion-assurances' order by stat"
)
_Q_PEER_RATINGS = (
    "select segment, source, profile, rating, review_count, tag, source_url "
    "from peer_ratings order by profile, source"
)
_Q_THEME_BY_MONTH = (
    "select month, label, reviews, theme_rows, share, tag "
    "from theme_share_by_month where segment = 'digital-first' "
    "order by label, month"
)
_Q_THEME_BY_SEGMENT = (
    "select segment, label, reviews, theme_rows, share, tag "
    "from theme_share_by_segment order by label, segment"
)
_Q_CLASSIFIER_QUALITY = (
    "select label, hits, predicted, actual, precision, recall, tag "
    "from classifier_quality order by label"
)

# The marts a corpus panel gates on: it reads their `run_id` to decide numbers
# vs the fixture state (Phase 9b, the corpus gate).
_CORPUS_MARTS = (
    "theme_share_by_month",
    "theme_share_by_segment",
    "classifier_quality",
)


def _run_id_sql(mart: str) -> str:
    return f"select distinct run_id from {mart} order by run_id"


# The catalog probe `_mart_exists` runs — with the engine's schema read, one of
# the two catalog reads the export runs outside STUDY_QUERIES (no data column,
# so no review text can leak); a test records every query a render runs and
# refuses one that is neither (challenge round 2).
_MART_PROBE = (
    "select 1 from information_schema.tables where table_schema = ? and table_name = ?"
)


def _mart_exists(conn, mart: str) -> bool:
    # A catalog probe, not a data read (no review text, so it stays outside the
    # column allowlist): a Python-fed mart the classify step never built under
    # ROWS=none is absent, not empty, and its panel renders "no data yet".
    # information_schema.tables is portable across DuckDB and Snowflake; the
    # schema is the engine's own (`warehouse.default_schema`, as the rebuild's
    # catalog reads do), so a same-named table elsewhere never matches.
    return (
        conn.execute(_MART_PROBE, [default_schema(conn), mart]).fetchone() is not None
    )


STUDY_QUERIES = (
    _Q_RATING_TREND,
    _Q_CHANNEL_GAP,
    _Q_PLATFORM_STATS,
    _Q_PEER_RATINGS,
    _Q_THEME_BY_MONTH,
    _Q_THEME_BY_SEGMENT,
    _Q_CLASSIFIER_QUALITY,
) + tuple(_run_id_sql(mart) for mart in _CORPUS_MARTS)


# --- Reading the marts (every query carries its own order by) ------------------
def _rows(conn, sql: str) -> list[tuple]:
    """Run a study query and return its rows, refusing by name any column
    outside `ALLOWED_COLUMNS` — the structural no-text guarantee, read off the
    cursor's own description so a `select *` cannot slip a body column through
    (Phase 9b). The projected columns are checked once, before any row is read."""
    cur = conn.execute(sql)
    projected = [column[0] for column in cur.description]
    blocked = [column for column in projected if column not in ALLOWED_COLUMNS]
    if blocked:
        raise RenderRefused(
            f"study query projects non-allowlisted column(s) {blocked} — the "
            "export reads only the closed set (no review text)"
        )
    return cur.fetchall()


# --- Beat 1 readers -----------------------------------------------------------
def _rating_trend(conn) -> tuple[Series, ...]:
    """B1.2: the studied segment's unsolicited rating over time, one line per
    profile (a brand-free role slug). Anchors only under `synthetic`."""
    # Segment-wide BY DESIGN (SPEC B1.2 is "the studied segment's rating"): no
    # profile filter, unlike _channel_gap/_platform_stats which are the studied
    # insurer's profile. The anchors carry one digital-first unsolicited profile
    # today, so it renders one line; a second lands as a second line, no change.
    # The grain is (source, profile, month), so `source` closes the order-by:
    # two unsolicited sources with a rating in one profile+month append in a
    # fixed order, not the engine's, and the bytes stay stable (round 2, CR#16).
    rows = _rows(conn, _Q_RATING_TREND)
    by_profile: dict[str, list[Point]] = {}
    for profile, month, rating, tag, url in rows:
        by_profile.setdefault(profile, []).append(
            Point(
                str(month),
                float(_require(rating, "rating", "B1.2")),
                tag,
                _require(url, "source_url", "B1.2"),
                "stars",
            )
        )
    return tuple(
        Series(_PROFILE_NAMES.get(profile, profile), slot, tuple(pts))
        for slot, (profile, pts) in enumerate(sorted(by_profile.items()))
    )


def _channel_gap(conn) -> tuple[Series, ...]:
    """B1.3: the studied insurer's rating on each invited channel and each
    unsolicited one, one bar per (channel, source), coloured by channel."""
    rows = _rows(conn, _Q_CHANNEL_GAP)
    channels = sorted({channel for channel, *_ in rows})
    slot_of = {channel: i for i, channel in enumerate(channels)}
    by_channel: dict[str, list[Point]] = {}
    for channel, source, rating, tag, url in rows:
        by_channel.setdefault(channel, []).append(
            Point(
                source,
                float(_require(rating, "rating", "B1.3")),
                tag,
                _require(url, "source_url", "B1.3"),
                "stars",
            )
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
    rows = _rows(conn, _Q_PLATFORM_STATS)
    order = list(_STAT_LABELS)
    for stat, *_ in rows:
        if stat not in _STAT_LABELS:  # a stat outside the closed set: refuse by name
            raise RenderRefused(
                f"B1.4: unknown platform stat {stat!r} (not in {tuple(_STAT_LABELS)})"
            )
    points = [
        Point(
            _STAT_LABELS[stat][0],
            float(_require(value, "value", "B1.4")),
            tag,
            _require(url, "source_url", "B1.4"),
            _STAT_LABELS[stat][1],
        )
        for stat, value, tag, url in sorted(rows, key=lambda r: order.index(r[0]))
    ]
    return (Series("stats", 0, tuple(points)),) if points else ()


# Brand-free display names for the role slugs the marts carry (D1: no brand
# token leaves ingest/sources.py; these are roles, not names). The four anchor
# profiles; an unknown profile refuses by name (Phase 9b, B2.3).
_PROFILE_NAMES = {
    "fr-digital-first": "Studied digital-first insurer",
    "peer-digital-challenger-1": "Digital challenger (peer)",
    "peer-traditional-1": "Traditional mutuelle 1 (peer)",
    "peer-traditional-2": "Traditional mutuelle 2 (peer)",
}


def _profile_name(profile: str) -> str:
    if profile not in _PROFILE_NAMES:
        raise RenderRefused(
            f"unknown profile {profile!r} (not in {tuple(_PROFILE_NAMES)})"
        )
    return _PROFILE_NAMES[profile]


# Short axis labels for the peer bars (the full role names overflow a 4-bar band
# and overlap — B1.3 uses short labels too); the full name sits in the tooltip.
_PROFILE_SHORT = {
    "fr-digital-first": "Studied",
    "peer-digital-challenger-1": "Challenger",
    "peer-traditional-1": "Mutuelle 1",
    "peer-traditional-2": "Mutuelle 2",
}


def _profile_short(profile: str) -> str:
    return _PROFILE_SHORT.get(profile, _profile_name(profile))


def beat1_panels(conn) -> list[Panel]:
    """The four Beat 1 panels, built from the marts. B1.1 is Pending (the hero
    case is not yet curated); B1.2–B1.4 are Documented under the anchors."""
    return [
        Panel(
            id="B1.1",
            backing_row="B1.1",
            title="One refund, held for months",
            blurb=(
                "When a public case is curated here it will show the pattern in "
                "one story: a refund put on hold pending extra documents, "
                "followed for as long as it stays unresolved. The day count "
                "will be frozen at the last publicly confirmed date, never a "
                "live ticker we cannot verify."
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
                "Customers rate this segment’s digital-first insurers on platforms "
                "they were not invited to — one line per insurer, not a segment "
                "average. This is that rating, month by month, on the unsolicited "
                "channel."
            ),
            tag="Documented",
            kind="line",
            series=_rating_trend(conn),
            notes=(
                "Sampling bias, stated here: unsolicited review platforms are "
                "negatively self-selected — a company that stops inviting reviews "
                "drifts down — so part of any decline is a sampling choice, not "
                "only a service change.",
            ),
            domain=(1.0, 5.0),
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
            notes=(
                "Stated here: invited channels (the app stores) are positively "
                "self-selected and unsolicited platforms negatively, so part of "
                "the gap is who gets asked, not only how the service performs.",
            ),
            domain=(0.0, 5.0),
        ),
        Panel(
            id="B1.4",
            backing_row="B1.4",
            title="The ratings in context",
            blurb=(
                "A few numbers that place the ratings in context: how many reviews, "
                "how many one-star, how often and how fast the company answers."
            ),
            tag="Documented",
            kind="stat_row",
            series=_platform_stats(conn),
            notes=(
                "Stated here: today the answer rate and time come from one profile "
                "on one platform, so the comparison across platforms waits for a "
                "second platform’s figures.",
            ),
        ),
    ]


# --- Beat 2: the corpus gate, the theme shares, the classifier score -----------
# The theme labels, coloured in the closed five-slot categorical order; the
# `unclassified` band is the neutral token, `positive` is excluded from a theme
# chart (a theme chart counts complaints). A label outside the closed set is
# refused by name (classify/labels.py is the source of the set).
_THEME_SLOTS = {theme: slot for slot, theme in enumerate(THEMES)}
# The study's hypothesis theme (brief §5.1, B2.5): the one theme B2.5 draws per
# segment, beside the band. Named from the closed label set, never retyped.
HELD_CLAIM = THEMES[0]  # "document-loop"; a test pins the name
# Segment display names, a closed lookup over ingest's SEGMENTS (refused by name
# outside it — a segment is a role, never a brand).
_SEGMENT_NAMES = {
    "digital-first": "Digital-first",
    "traditional": "Traditional mutuelle",
    "digital-challenger": "Digital challenger",
}  # a test pins the key set equal to SEGMENTS
_LABEL_NAMES = {
    "document-loop": "Document loop",
    "silent-rejection": "Silent rejection",
    "second-payer": "Second-payer failure",
    "support-traction": "Support without traction",
    "coverage-price": "Coverage and price",
    POSITIVE: "Positive",
    UNCLASSIFIED: "Not yet classified",
}

# The corpus gate's states and the platform roots a computed share cites (no
# per-review address leaves ingest — D1). The fixture-state text carries no
# digit, so a fixture panel's body shows no number (Phase 9b, the brief's
# "never faked" applied at render time).
# The gate's state per rebuild input, one closed mapping over `INPUTS` (a test
# pins the key sets equal): counted numbers over the real corpus, the labelled
# fixture state over a fixture input, "no data yet" over `none`. A run_id
# outside it refuses by name in `_corpus_input`; a fifth input cannot fall into
# a default arm (challenge round 2, #8).
COUNTED, FIXTURE, NO_DATA = "counted", "fixture", "no-data"
_STATE_OF_INPUT = {
    "captured": COUNTED,
    "synthetic": FIXTURE,
    "samples": FIXTURE,
    "none": NO_DATA,
}
_FIXTURE_NOTE = (
    "Built from hand-written example reviews: a check that the study’s machinery "
    "works, not a result. The counted figures appear when the study is built "
    "over captured reviews."
)
# B2.4's source (BACKING): the hand-labelled answer key, a repository file the
# footer names in plain text; the export never reads it (classify/eval does).
ANSWER_KEY_FILE = "classify/eval/labels.csv"
PLATFORM_ROOTS = (
    "https://apps.apple.com/",
    "https://play.google.com/",
    "https://www.opinion-assurances.fr/",
    "https://www.trustpilot.com/",
)
# The denominator every theme share divides by — every classified review,
# positive included — stated beside the chart so `positive`'s exclusion from
# the bars is not read as a shrunk denominator (Phase 9b, pinned decision 4).
# One note per chart shape: B2.2's lines (shares across themes in one month),
# B2.5's bars (one theme's share in one segment) — round 2, study-editor #1.
_DENOMINATOR_NOTE = (
    "The share of each theme is theme rows over every classified review "
    "(positive reviews included in the total, but not drawn as a theme bar — a "
    "theme chart counts complaints). A review carrying two themes counts in two "
    "bars, so the shares across themes can sum past one. The gray “not yet "
    "classified” band is the reviews a language model would sort; when that "
    "model is switched off it is largest, shown, never hidden."
)
_SEGMENT_DENOMINATOR_NOTE = (
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


_SELF_SELECTION_NOTE = _self_selection_note("the theme mix")
_SEGMENT_SELF_SELECTION_NOTE = _self_selection_note("the held-claim complaint share")
# The corpus is one segment today — B2.2 and B2.5's own note, before the caveat:
# B2.2's query filters on it and B2.5 draws it (BACKLOG "vs traditional").
_TRADITIONAL_CAVEAT = (
    "The corpus is digital-first only for now, so the traditional comparison "
    "awaits a traditional-mutuelle source; the chart shows the segment the data "
    "has."
)


def _label_display(label: str) -> str:
    if label not in _LABEL_NAMES:
        raise RenderRefused(
            f"classified label {label!r} is not one of {tuple(_LABEL_NAMES)}"
        )
    return _LABEL_NAMES[label]


def _theme_colour(label: str) -> int | str:
    """A theme's categorical slot, or the neutral token for the `unclassified`
    band. `positive` is excluded upstream; any other label refuses by name."""
    if label in _THEME_SLOTS:
        return _THEME_SLOTS[label]
    if label == UNCLASSIFIED:
        return NEUTRAL
    raise RenderRefused(
        f"theme series label {label!r} is not a theme or {UNCLASSIFIED!r}"
    )


def _label_order(label: str) -> int:
    """The five themes in slot order, then the `unclassified` band last — a
    deterministic series order independent of the row order."""
    return _THEME_SLOTS.get(label, len(THEMES))


def _corpus_input(conn, mart: str, panel_id: str) -> str | None:
    """The single `run_id` the mart's rows carry, or `None` for an empty mart.
    Exactly one value of the closed `INPUTS` set is accepted; two values, or one
    outside the set, refuse in one line naming the panel (Phase 9b, the corpus
    gate). The input is read from the mart's own rows, never from a filename or
    a caller flag."""
    if not _mart_exists(conn, mart):
        return None  # the classify step never ran (e.g. ROWS=none) — no data yet
    run_ids = [row[0] for row in _rows(conn, _run_id_sql(mart))]
    if not run_ids:
        return None
    if len(run_ids) != 1:
        raise RenderRefused(
            f"{panel_id}: {mart} carries {len(run_ids)} run_ids {run_ids} — a "
            "corpus panel counts rows from exactly one input"
        )
    run_id = run_ids[0]
    if run_id not in _STATE_OF_INPUT:
        raise RenderRefused(
            f"{panel_id}: run_id {run_id!r} in {mart} is not one of {INPUTS}"
        )
    return run_id


def _theme_series(
    rows: list[tuple],
    panel_id: str,
    label_by: Literal["period", "segment"],
    themes: frozenset[str] = frozenset(THEMES),
) -> tuple[Series, ...]:
    """One series per label from `(x, label, reviews, theme_rows, share, tag)` rows:
    each drawn theme a coloured line/bar, the `unclassified` band the neutral
    token, `positive` excluded (a theme chart counts complaints). `themes` is the
    closed set of themes drawn — every theme for B2.2, the held-claim theme alone
    for B2.5 (SPEC B2.5: the document-loop share per segment). `label_by` names
    each point by its period (a month) or by its segment (x = segment, theme =
    series, so a second segment is a second bar per series — BACKLOG "vs
    traditional"). The raw counts ride on each point as the trail behind the
    share, redone by hand.

    The `unclassified` band is always emitted, even with no rows, and its legend
    name carries its total count — so a small or empty band reads as zero, never
    as hidden (Phase 9b, invariant 3)."""
    by_label: dict[str, list[Point]] = {}
    # The tag is the mart row's own, as every Beat 1 reader reads it — never a
    # literal in the reader (round 2, code-reviewer #1, the caller-sourced class).
    for x_key, label, reviews, theme_rows, share, tag in rows:
        if label == POSITIVE or (label in _THEME_SLOTS and label not in themes):
            continue
        point_label = str(x_key) if label_by == "period" else _segment_name(x_key)
        by_label.setdefault(label, []).append(
            Point(
                point_label,
                float(_require(share, "share", panel_id)),
                _require(tag, "tag", panel_id),
                "",
                "pct",
                detail=f"{int(theme_rows)} of {int(reviews)} reviews",
            )
        )
    # A deterministic legend count summed from the mart's own `unclassified` rows
    # — the band's legend total, not a recomputed study number: the shares
    # themselves are each read from a mart cell (round 1, code-reviewer).
    band_total = sum(
        int(theme_rows)
        for _, label, _, theme_rows, _, _ in rows
        if label == UNCLASSIFIED
    )
    labels = sorted(set(by_label) | {UNCLASSIFIED}, key=_label_order)
    return tuple(
        Series(
            _series_name(label, band_total),
            _theme_colour(label),
            tuple(by_label.get(label, ())),
        )
        for label in labels
    )


def _segment_name(segment: str) -> str:
    if segment not in _SEGMENT_NAMES:
        raise RenderRefused(
            f"unknown segment {segment!r} (not in {tuple(_SEGMENT_NAMES)})"
        )
    return _SEGMENT_NAMES[segment]


def _series_name(label: str, band_total: int) -> str:
    """A theme's display name, or the `unclassified` band named with its total
    count so an empty band still reads as zero in the legend (invariant 3)."""
    if label == UNCLASSIFIED:
        return f"{_label_display(UNCLASSIFIED)} ({band_total})"
    return _label_display(label)


def _peer_ratings(conn) -> tuple[Series, ...]:
    """B2.3: public ratings across the segment on the unsolicited channel, one
    bar per profile, each point labelled by platform in its tooltip. Documented
    anchors — not corpus-gated. A profile on two platforms is two points, never
    an average (SPEC B2.3)."""
    rows = _rows(conn, _Q_PEER_RATINGS)
    points = []
    for _segment, source, profile, rating, review_count, tag, url in rows:
        detail = f"{_profile_name(profile)} · on {source}"  # full name + platform
        if review_count is not None:
            detail += f", {int(review_count):,} reviews"
        points.append(
            Point(
                _profile_short(profile),  # short axis label; full name in the tooltip
                float(_require(rating, "rating", "B2.3")),
                tag,
                _require(url, "source_url", "B2.3"),
                "stars",
                detail=detail,
            )
        )
    return (Series("Public rating", 0, tuple(points)),) if points else ()


def _score_cell(
    name: str,
    value: float | None,
    hits: int,
    denominator: int,
    denominator_name: str,
    *,
    tag: str,
) -> Point:
    """One classifier-quality cell: a percentage with its raw counts, or — when
    the held-out denominator is zero — a labelled absence carrying that count
    (value xor absence; Phase 9b, pinned decision 5). `tag` is the mart row's
    own, never a literal here."""
    if denominator == 0:
        return Point(
            name,
            None,
            _require(tag, "tag", "B2.4"),
            "",
            "pct",
            absent="no held-out case",
            detail=f"{int(denominator)} {denominator_name}",
        )
    return Point(
        name,
        float(_require(value, name.lower(), "B2.4")),
        _require(tag, "tag", "B2.4"),
        "",
        "pct",
        detail=f"{int(hits)}/{int(denominator)}",
    )


def _classifier_table(conn) -> tuple[Series, ...]:
    """B2.4: one table row per scored label (the five themes + positive), each
    with its precision and recall cell against the held-out fold. The colour is
    unused for a table — slot 0 keeps the type happy."""
    rows = _rows(conn, _Q_CLASSIFIER_QUALITY)
    return tuple(
        Series(
            _label_display(label),
            0,
            (
                _score_cell(
                    "Precision", precision, hits, predicted, "predicted", tag=tag
                ),
                _score_cell("Recall", recall, hits, actual, "actual", tag=tag),
            ),
        )
        for label, hits, predicted, actual, precision, recall, tag in rows
    )


def _corpus_series(
    conn,
    mart: str,
    panel_id: str,
    build: Callable[[], tuple[Series, ...]],
) -> tuple[tuple[Series, ...], str]:
    """The (series, fixture-state) pair a corpus panel renders: the built series
    over a captured input, else empty series and the labelled fixture-state text
    over a fixture input (an empty mart leaves both empty — 9a's "no data yet")."""
    run_id = _corpus_input(conn, mart, panel_id)
    if run_id is None:
        return (), ""
    state = _STATE_OF_INPUT[run_id]  # closed: `_corpus_input` refused the rest
    if state == COUNTED:
        return build(), ""
    return (), (_FIXTURE_NOTE if state == FIXTURE else "")


def beat2_panels(conn) -> list[Panel]:
    """The five Beat 2 panels. B2.1 is Pending; B2.3 is Documented (the peer
    anchors); B2.2, B2.4 and B2.5 are Measured behind the corpus gate — counted
    over a captured input, the fixture state over the frozen synthetic input."""
    month_series, month_fixture = _corpus_series(
        conn,
        "theme_share_by_month",
        "B2.2",
        lambda: _theme_series(_rows(conn, _Q_THEME_BY_MONTH), "B2.2", "period"),
    )
    quality_series, quality_fixture = _corpus_series(
        conn, "classifier_quality", "B2.4", lambda: _classifier_table(conn)
    )
    segment_series, segment_fixture = _corpus_series(
        conn,
        "theme_share_by_segment",
        "B2.5",
        lambda: _theme_series(
            _rows(conn, _Q_THEME_BY_SEGMENT),
            "B2.5",
            "segment",
            themes=frozenset({HELD_CLAIM}),
        ),
    )
    return [
        Panel(
            id="B2.1",
            backing_row="B2.1",
            title="The five kinds of complaint",
            blurb=(
                "The complaints are not random: they fall into five recurring "
                "kinds — the document loop, silent rejections, second-payer "
                "failures, support without traction, and coverage-and-price "
                "frustration. Each will be shown here with paraphrased examples "
                "from public reviews and their links."
            ),
            tag="Pending",
            kind="hero",
            placeholder=(
                "Awaiting the five themes, each with a short paraphrased example "
                "and a link to its public source. Paraphrased, never quoted — a "
                "review is about a real person."
            ),
        ),
        Panel(
            id="B2.2",
            backing_row="B2.2",
            title="Theme share over time",
            blurb=(
                "How the mix of complaints moves month by month. Each line is one "
                "theme’s share of the reviews that month; the gray band is the "
                "reviews not yet sorted into a theme."
            ),
            tag="Measured",
            kind="line",
            series=month_series,
            fixture=month_fixture,
            sources=PLATFORM_ROOTS,
            notes=(_TRADITIONAL_CAVEAT, _SELF_SELECTION_NOTE, _DENOMINATOR_NOTE),
            domain=(0.0, 1.0),
        ),
        Panel(
            id="B2.3",
            backing_row="B2.3",
            title="Peer context",
            blurb=(
                "So no one insurer is read in isolation: public ratings across the "
                "segment on platforms customers were not invited to. Each bar is "
                "one profile’s rating; a profile rated on two platforms is two "
                "bars, never one average."
            ),
            tag="Documented",
            kind="grouped_bar",
            series=_peer_ratings(conn),
            notes=(
                "Placed points, stated here: where the brief gives a range, the "
                "point is its midpoint, not a reading; a review count the brief "
                "does not give is left blank. Each point is labelled by its "
                "platform in the tooltip.",
            ),
            domain=(0.0, 5.0),
        ),
        Panel(
            id="B2.4",
            backing_row="B2.4",
            title="Classifier quality",
            blurb=(
                "How good the classifier is, graded only on reviews it never saw "
                "while it was built (the held-out fold), so the scores are not "
                "flattered. Precision is how often a label is right; recall is how "
                "many true cases it catches."
            ),
            tag="Measured",
            kind="table",
            series=quality_series,
            fixture=quality_fixture,
            sources=(ANSWER_KEY_FILE,),  # BACKING B2.4's source: the answer key
            columns=("Theme", "Precision", "Recall"),
            notes=(
                "“No held-out case” means the held-out fold carried no review of "
                "that theme to score — an empty denominator, not a zero score. "
                "The counts beside each figure are the cases it was graded on.",
            ),
        ),
        Panel(
            id="B2.5",
            backing_row="B2.5",
            title="Held-claim complaints, digital-first versus traditional",
            blurb=(
                "The study’s hypothesis, not its verdict: the share of "
                "document-loop complaints at digital-first insurers beside the "
                "same share at traditional mutuelles. If the data shows no gap, "
                "the chart says so and is published as-is."
            ),
            tag="Measured",
            kind="grouped_bar",
            series=segment_series,
            fixture=segment_fixture,
            sources=PLATFORM_ROOTS,
            notes=(
                _TRADITIONAL_CAVEAT,
                _SEGMENT_SELF_SELECTION_NOTE,
                _SEGMENT_DENOMINATOR_NOTE,
            ),
            domain=(0.0, 1.0),
        ),
    ]
