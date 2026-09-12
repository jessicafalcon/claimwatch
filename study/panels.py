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

from collections.abc import Callable, Iterable
from math import ceil, floor, log10
from typing import Literal, NamedTuple

from classify.eval.gate import ANSWER_KEY
from classify.labels import POSITIVE, THEMES, UNCLASSIFIED
from models.cost_model import FORMULAS, SCENARIOS, Formula, rounded
from models.guardrail_sim import SIM_SCENARIOS
from opendata.fee_split import ARTIFACT as FEE_SPLIT_ARTIFACT
from opendata.fit import ARTIFACT
from opendata.sources import AMELI_DATASET_URL, DATASET_API
from pipeline.build import INPUTS
from pipeline.warehouse import ROOT, default_schema
from study import text
from study.model import (
    NEUTRAL,
    Panel,
    Point,
    RenderRefused,
    Series,
    _require,
    display,
    x_key,
)
from study.text import (
    DENOMINATOR_NOTE,
    FIXTURE_NOTE,
    SEGMENT_DENOMINATOR_NOTE,
    SEGMENT_SELF_SELECTION_NOTE,
    SELF_SELECTION_NOTE,
    TRADITIONAL_CAVEAT,
)

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
        # Beat 3: the three cost-model marts (no review column among them)
        "scenario",
        "name",
        "expression",
        "unit",
        "default_value",
        "sourcing",
        "citation",
        "low",
        "high",
        "flag_rate",
        "fraud_saved",
        "friction_cost",
        "net",
        "is_default",
        # Beat 4 (9d): sla_threshold (B4.2) and the guardrail_sim aggregate
        # (B4.3). `mean_hold_days`/`released`/`claim_count` are the aggregate's
        # own aliases; the raw per-claim columns (hold_days, outcome, quantile,
        # amount_eur, loop_days, claim_rank, curves_scenario) are never
        # projected to the page — the reduction happens in the query.
        "timer_days",
        "timer_amount_eur",
        "share_under",
        "mean_hold_days",
        "released",
        "claim_count",
        # Beat 5 (9e): determinism_facts (B5.1) and pipeline_row_counts (B5.2).
        # `value` (a count) is already allowed; `fact` and `stage` are the keys.
        "fact",
        "stage",
    }
)

# Every query the export runs, in one tuple, so a test lints each for portability
# and the clock (the reviews-per-month query pattern in pipeline/build.py; Phase
# 9b, pinned decision 3).
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
# Beat 3 reads each model mart whole and picks the scenario in Python, so no
# filter value is a literal in the SQL (pinned decision 2); `name` is the
# tie-free read key and the rows are re-ordered by the imported tuples.
_Q_COST_OUTPUTS = (
    "select scenario, name, expression, value, unit, tag "
    "from cost_model_outputs order by scenario, name"
)
# `net` is read by no Beat 3 reader — B3.2's marker is the outputs mart's
# crossover row, never a scan of `net` (pinned decision 4), so a mutated `net`
# cell moves no Beat 3 number. Beat 4's B4.1 (9d) is the reader of `net`: the
# net curve per scenario. `tests/test_beat3.py` pins both (Beat 3 unmoved, Beat
# 4 moved); `tests/test_beat4.py` pins the curve.
_Q_COST_CURVES = (
    "select scenario, flag_rate, fraud_saved, friction_cost, net, is_default, tag "
    "from cost_curves order by scenario, flag_rate"
)
_Q_COST_PARAMS = (
    "select name, default_value, unit, sourcing, citation, low, high, tag "
    "from cost_model_params order by name"
)
# Beat 4 (9d). B4.3 reads guardrail_sim through one SQL aggregate — the mean
# hold and the timer-released share per scenario — the shape Phase 8b's BACKLOG
# row named and a test pins equal to `models.guardrail_sim.summarize` (pinned
# decision 4). The `case` idiom is the portable conditional count (Snowflake has
# no `filter`); no clock, no pattern, so `sql_lint` passes. The per-claim
# columns stay in the query — only the reduced aliases reach the page.
_Q_GUARDRAIL_AGG = (
    "select scenario, tag, avg(hold_days) as mean_hold_days, "
    "sum(case when outcome = 'timer_released' then 1 else 0 end) as released, "
    "count(*) as claim_count "
    "from guardrail_sim group by scenario, tag order by scenario, tag"
)
# B4.2 reads sla_threshold whole and picks the is_default row in Python (no
# filter literal in the SQL, the Beat 3 pattern); exactly one row is the default.
_Q_SLA_THRESHOLD = (
    "select timer_days, timer_amount_eur, share_under, is_default, tag "
    "from sla_threshold order by timer_days"
)
# Beat 5 (9e). B5.1 reads the repo facts whole and re-orders by the closed
# DETERMINISM_FACTS map (the FORMULAS pattern); B5.2 reads the per-stage counts
# and re-orders by the ROW_COUNT_STAGES map. `value` is a count in both.
_Q_DETERMINISM_FACTS = "select fact, value, tag from determinism_facts order by fact"
_Q_PIPELINE_ROW_COUNTS = (
    "select stage, value, tag from pipeline_row_counts order by stage"
)

# The marts a corpus panel gates on: it reads their `run_id` to decide numbers
# vs the fixture state (Phase 9b, the corpus gate). B5.2's pipeline_row_counts
# is corpus-gated too (9e); B5.1's determinism_facts is not (a repo fact is
# constant on any input, so it reads directly, no gate).
_CORPUS_MARTS = (
    "theme_share_by_month",
    "theme_share_by_segment",
    "classifier_quality",
    "pipeline_row_counts",
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
    _Q_COST_OUTPUTS,
    _Q_COST_CURVES,
    _Q_COST_PARAMS,
    _Q_GUARDRAIL_AGG,
    _Q_SLA_THRESHOLD,
    _Q_DETERMINISM_FACTS,
    _Q_PIPELINE_ROW_COUNTS,
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
# per-review address leaves ingest — D1); the fixture-state text itself lives in
# study/text.py. The gate's state per rebuild input, one closed mapping over
# `INPUTS` (a test pins the key sets equal): counted numbers over the real
# corpus, the labelled fixture state over a fixture input, "no data yet" over
# `none`. A run_id outside it refuses by name in `_corpus_input`; a fifth input
# cannot fall into a default arm (challenge round 2, #8).
COUNTED, FIXTURE, NO_DATA = "counted", "fixture", "no-data"
_STATE_OF_INPUT = {
    "captured": COUNTED,
    "synthetic": FIXTURE,
    "samples": FIXTURE,
    "none": NO_DATA,
}
# B2.4's source (BACKING): the hand-labelled answer key, a repository file the
# footer names in plain text. The export never reads it and never spells it —
# the path is the constant its one reader, classify/eval, exports (the labels
# wall, tests/test_labels_isolation.py), as pipeline/cli.py names it.
ANSWER_KEY_FILE = ANSWER_KEY
PLATFORM_ROOTS = (
    "https://apps.apple.com/",
    "https://play.google.com/",
    "https://www.opinion-assurances.fr/",
    "https://www.trustpilot.com/",
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
    for x_label, label, reviews, theme_rows, share, tag in rows:
        if label == POSITIVE or (label in _THEME_SLOTS and label not in themes):
            continue
        point_label = str(x_label) if label_by == "period" else _segment_name(x_label)
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
    return (), (FIXTURE_NOTE if state == FIXTURE else "")


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
            notes=(TRADITIONAL_CAVEAT, SELF_SELECTION_NOTE, DENOMINATOR_NOTE),
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
                TRADITIONAL_CAVEAT,
                SEGMENT_SELF_SELECTION_NOTE,
                SEGMENT_DENOMINATOR_NOTE,
            ),
            domain=(0.0, 1.0),
        ),
    ]


# --- Beat 3: the cost model, every number a cell of its three marts ------------
# The outputs mart's rounding unit (models/cost_model.py::_ROUNDING's keys) → the
# display unit the page formats it in; a unit outside the closed lookup refuses
# by name (pinned decision 5). A curve formula's value is a flag rate, read as a
# percentage.
_DISPLAY_UNIT = {"eur": "eur", "rate": "pct", "count": "count", "days": "days"}
# The sourcing words a parameter row may carry (`models.cost_model.SOURCING`,
# restated as the closed key of the render class): any other word refuses.
Sourcing = Literal["sourced", "unsourced"]
_SOURCINGS: tuple[Sourcing, ...] = ("sourced", "unsourced")
# The panel-level sources: B3.1–B3.3 name the tracked fit artifact (a repository
# file) and the Open DAMIR dataset it was fitted from (an address); B3.4 names
# the module that declares the guesses. The params mart's citation string is
# rendered as text, never passed as a source (its "… ← open-damir" shape is
# neither a file nor an address).
FIT_FILE = str(ARTIFACT.relative_to(ROOT))
MODEL_FILE = "models/cost_model.py"
_FIT_SOURCES = (FIT_FILE, DATASET_API)
# B3.3 alone also names the fee-split artifact and the data.ameli table it was
# read from (9i): the extra-billing row is its row, no other panel's.
FEE_SPLIT_FILE = str(FEE_SPLIT_ARTIFACT.relative_to(ROOT))
_B33_SOURCES = (*_FIT_SOURCES, FEE_SPLIT_FILE, AMELI_DATASET_URL)
# The scenario B3.1–B3.3 read; the three toggled scenarios are Beat 4's (9d).
BASELINE = "baseline"


def _scenario_rows(conn, sql: str, scenario: str, panel_id: str) -> list[tuple]:
    """The rows of one scenario from a scenario-keyed model mart, the scenario
    checked against the imported `SCENARIOS` and refused by name outside it —
    never a literal in the SQL, never a caller's free string."""
    if scenario not in SCENARIOS:
        raise RenderRefused(
            f"{panel_id}: scenario {scenario!r} is not one of {tuple(SCENARIOS)}"
        )
    return [row[1:] for row in _rows(conn, sql) if row[0] == scenario]


def _display_unit(unit: str | None, panel_id: str) -> str:
    unit = _require(unit, "unit", panel_id)
    if unit not in _DISPLAY_UNIT:
        raise RenderRefused(
            f"{panel_id}: outputs unit {unit!r} is not one of {tuple(_DISPLAY_UNIT)}"
        )
    return _DISPLAY_UNIT[unit]


def _formula_cell(
    formula: Formula, row: tuple, panel_id: str
) -> Point:  # one outputs row → one cell
    """One formula row's cell: the expression as its label, the mart's value in
    its display unit — or, for a curve formula whose crossover the grid never
    reaches (the mart stores NULL), the declared absence. A null value on a
    point formula, or a null expression, refuses by name."""
    expression, value, unit, tag = row
    label = str(_require(expression, "expression", panel_id))
    unit = _display_unit(unit, panel_id)
    tag = str(_require(tag, "tag", panel_id))
    if value is None and formula.kind == "curve":
        return Point(label, None, tag, "", unit, absent=text.NEVER_CROSSES)
    return Point(label, float(_require(value, "value", panel_id)), tag, "", unit)


def _formula_rows(conn, scenario: str, panel_id: str) -> tuple[Series, ...]:
    """B3.1 (and B3.3's headline, 9d's B4.1): one series per `FORMULAS` entry,
    in the tuple's order so the page reads line for line with `make model`,
    each the display name, the mart's own name as `key`, and one cell. Every
    mart row must be a `FORMULAS` name with a display name, and every
    `FORMULAS` name must have a row — the module ↔ mart ↔ page identity."""
    by_name = {
        name: row
        for name, *row in _scenario_rows(conn, _Q_COST_OUTPUTS, scenario, panel_id)
    }
    known = {f.name for f in FORMULAS}
    for name in by_name:
        if name not in known or name not in text.FORMULA_NAMES:
            raise RenderRefused(
                f"{panel_id}: formula {name!r} in cost_model_outputs has no "
                "display name (not in the closed map)"
            )
    series = []
    for f in FORMULAS:
        if f.name not in by_name:
            raise RenderRefused(
                f"{panel_id}: formula {f.name!r} has no {scenario} row in "
                "cost_model_outputs"
            )
        series.append(
            Series(
                text.FORMULA_NAMES[f.name],
                0,
                (_formula_cell(f, by_name[f.name], panel_id),),
                key=f.name,
            )
        )
    return tuple(series)


def _headline_rows(formula_rows: tuple[Series, ...]) -> tuple[Series, ...]:
    """B3.3's derived headline figures (BACKING: revenue per member, the mean
    claim, the claim volume; from 9h the claim count at the sample's mean cell
    beside the volume) — the baseline formula rows of those names.
    Filters the B3.1 rows the panel build already read, so the outputs mart is
    read once, not once more for the headline (round 1, code-reviewer #6)."""
    return tuple(s for s in formula_rows if s.key in text.HEADLINE_FORMULAS)


def _curve_series(conn, scenario: str, panel_id: str) -> tuple[Series, ...]:
    """B3.2 (and 9d's B4.1): the two curves over the flag-rate grid, one point
    per mart row, labelled by its grid x. Fraud saved takes slot 0 and friction
    cost slot 1 — the first slots in series order, never a semantic colour."""
    saved: list[Point] = []
    cost: list[Point] = []
    for row in _scenario_rows(conn, _Q_COST_CURVES, scenario, panel_id):
        flag_rate, fraud_saved, friction_cost, _net, _is_default, tag = row
        label = x_key(float(_require(flag_rate, "flag_rate", panel_id)))
        tag = str(_require(tag, "tag", panel_id))
        saved.append(
            Point(
                label,
                float(_require(fraud_saved, "fraud_saved", panel_id)),
                tag,
                "",
                "eur",
            )
        )
        cost.append(
            Point(
                label,
                float(_require(friction_cost, "friction_cost", panel_id)),
                tag,
                "",
                "eur",
            )
        )
    return (
        Series(text.FORMULA_NAMES["fraud_saved"], 0, tuple(saved)),
        Series(text.FORMULA_NAMES["friction_cost"], 1, tuple(cost)),
    )


def _one_default_rate(
    scenario_rows: list[tuple], scenario: str, panel_id: str
) -> float:
    """The single `is_default` flag rate among a scenario's already-read
    `cost_curves` rows (shape: flag_rate, fraud_saved, friction_cost, net,
    is_default, tag) — exactly one else refuse. The pure core shared by
    `_default_flag_rate` (which reads per scenario, B3.2) and `_net_marker`
    (which reads the whole mart once, B4.1)."""
    defaults = [
        float(_require(flag_rate, "flag_rate", panel_id))
        for flag_rate, *_rest, is_default, _tag in scenario_rows
        if is_default
    ]
    if len(defaults) != 1:
        raise RenderRefused(
            f"{panel_id}: cost_curves marks {len(defaults)} default rows for "
            f'{scenario} — exactly one is the "you are here" rule'
        )
    return defaults[0]


def _default_flag_rate(conn, scenario: str, panel_id: str) -> float:
    """The one `is_default` flag rate of a scenario's `cost_curves` rows — the
    "you are here" grid x, read from the mart (B3.2's `_curve_markers`)."""
    return _one_default_rate(
        _scenario_rows(conn, _Q_COST_CURVES, scenario, panel_id), scenario, panel_id
    )


def _curve_markers(conn, scenario: str, panel_id: str) -> tuple[tuple[str, float], ...]:
    """The curve chart's labelled rules, each read from a mart row and never
    found by scanning the curve (pinned decision 4): the `is_default` row's flag
    rate ("you are here"), then the two crossover rows of `cost_model_outputs`,
    each present only when the mart stores a value. Exactly one default row."""
    outputs = {
        name: value
        for name, _expression, value, _unit, _tag in _scenario_rows(
            conn, _Q_COST_OUTPUTS, scenario, panel_id
        )
    }
    markers = [(text.MARKER_DEFAULT, _default_flag_rate(conn, scenario, panel_id))]
    for label, name in (
        (text.MARKER_CROSSOVER, "crossover_flag_rate"),
        (text.MARKER_MARGINAL, "marginal_crossover_flag_rate"),
    ):
        if name not in outputs:
            raise RenderRefused(
                f"{panel_id}: formula {name!r} has no {scenario} row in "
                "cost_model_outputs"
            )
        if outputs[name] is not None:
            markers.append((label, float(outputs[name])))
    return tuple(markers)


def _crossover_note(markers: tuple[tuple[str, float], ...]) -> str:
    """The B3.2 note, filled from the markers (themselves mart rows): a rule that
    is absent reads as the grid never reaching it."""
    by_label = dict(markers)
    shown = {label: display(x, "pct") for label, x in markers}
    return text.crossover_note(
        shown.get(text.MARKER_CROSSOVER),
        shown.get(text.MARKER_MARGINAL),
        shown[text.MARKER_DEFAULT] if text.MARKER_DEFAULT in by_label else "",
    )


def _sig_ceil(value: float) -> float:
    """A positive value rounded up to one significant figure (4,530,293.45 →
    5,000,000) — the curve charts' domain-bound rule, shared by `curve_domain`
    (Beat 3) and `net_domain` (Beat 4, mirrored downward)."""
    magnitude = 10 ** floor(log10(value))
    return float(ceil(value / magnitude) * magnitude)


def curve_domain(values: Iterable[float]) -> tuple[float, float]:
    """The curve chart's y domain — a layout number by one fixed rule: lower
    bound 0, upper bound the largest value rounded up to one significant figure
    (4,530,293.45 → 5,000,000). The same cells give the same domain; no
    displayed figure derives from it (invariant 9)."""
    top = max(values, default=0.0)
    return (0.0, 1.0) if top <= 0 else (0.0, _sig_ceil(top))


def _parameter_rows(conn, sourcing: Sourcing, panel_id: str) -> tuple[Series, ...]:
    """B3.3 (sourced) and B3.4 (unsourced): one series per parameter whose mart
    `sourcing` is the given word — the split is that column, never an id list
    — in the display map's order (pinned equal to `parameters()` order), each
    three cells: low, default (its citation or the unsourced label in `detail`,
    beside the mart's prose unit), high, all in the parameter's display unit.
    A row whose word is neither, or whose name the map does not know, refuses."""
    if sourcing not in _SOURCINGS:
        raise RenderRefused(
            f"{panel_id}: sourcing {sourcing!r} is not one of {_SOURCINGS}"
        )
    by_name = {name: row for name, *row in _rows(conn, _Q_COST_PARAMS)}
    for name, (*_cells, word, _citation, _low, _high, _tag) in by_name.items():
        if name not in text.PARAMETER_NAMES:
            raise RenderRefused(
                f"{panel_id}: parameter {name!r} in cost_model_params has no display "
                "name (not in the closed map)"
            )
        if word not in _SOURCINGS:
            raise RenderRefused(
                f"{panel_id}: parameter {name!r} sourcing {word!r} is not one of "
                f"{_SOURCINGS}"
            )
    series = []
    for name, (display_name, unit) in text.PARAMETER_NAMES.items():
        if name not in by_name:
            raise RenderRefused(
                f"{panel_id}: parameter {name!r} has no row in cost_model_params"
            )
        default, prose_unit, word, citation, low, high, tag = by_name[name]
        if word != sourcing:
            continue
        tag = str(_require(tag, "tag", panel_id))
        told = citation if word == "sourced" else text.UNSOURCED_LABEL
        series.append(
            Series(
                display_name,
                0,
                (
                    Point("low", float(_require(low, "low", panel_id)), tag, "", unit),
                    Point(
                        "default",
                        float(_require(default, "default_value", panel_id)),
                        tag,
                        "",
                        unit,
                        detail=f"{_require(prose_unit, 'unit', panel_id)} · {told}",
                    ),
                    Point(
                        "high", float(_require(high, "high", panel_id)), tag, "", unit
                    ),
                ),
                key=name,
                sourcing=word,
            )
        )
    return tuple(series)


def beat3_panels(conn) -> list[Panel]:
    """The four Beat 3 panels, the study's first Modeled surface: every number a
    cell of the three cost-model marts, which fill on every rebuild input — so
    no corpus gate, and the committed page shows these numbers."""
    formulas = _formula_rows(conn, BASELINE, "B3.1")
    curves = _curve_series(conn, BASELINE, "B3.2")
    markers = _curve_markers(conn, BASELINE, "B3.2")
    return [
        Panel(
            id="B3.1",
            backing_row="B3.1",
            title="The formulas, next to their output",
            blurb=(
                "What a wrongly held claim costs, as arithmetic you can redo by "
                "hand: each row is one formula of the cost model, printed exactly "
                "as the code holds it, beside the number it gives at the "
                "defaults. Nothing here is measured — it is the model’s own "
                "output, and every input is listed in the two panels below."
            ),
            tag="Modeled",
            kind="formulas",
            series=formulas,
            sources=_FIT_SOURCES,
            notes=(
                "How to read a row: the quantity, the model’s own name for it, the "
                "formula as printed in the repository file models/cost_model.py, "
                "and its value at the defaults of the baseline scenario. The "
                "three fixes of Beat 4 rerun the same formulas with one or two "
                "inputs changed.",
                "The mean claim comes from a lognormal fitted to public "
                "reimbursement cells (Open DAMIR); a cell sums one or more "
                "claims, so the mean overstates a single claim and understates "
                "the claim count and the friction cost — the row says so, and "
                "the median cell is printed beside it as the contrast.",
            ),
        ),
        Panel(
            id="B3.2",
            backing_row="B3.2",
            title="The crossover chart",
            blurb=(
                "Flag more claims and you catch more fraud, with diminishing "
                "returns; you also hold more legitimate claims, and each of those "
                "costs staff time and lost customers. The two curves put both in "
                "euros over the share of claims flagged. Where they cross, "
                "flagging as a whole costs more than it recovers."
            ),
            tag="Modeled",
            kind="curve",
            series=curves,
            markers=markers,
            domain=curve_domain(p.value for s in curves for p in s.points),
            sources=_FIT_SOURCES,
            notes=(
                _crossover_note(markers),
                "The rules are read off the model’s own rows, not from the "
                "drawing: the default flag rate, the first grid point where the "
                "net turns negative, and the first where the next flag costs more "
                "than it recovers. A grid the curves never cross draws no rule "
                "and says so.",
                "One channel the curves do not show: for a company plan, one "
                "employee stuck in a document loop complains to their HR "
                "department, and it is HR that decides the renewal — so the "
                "customer lost can be a whole account.",
            ),
        ),
        Panel(
            id="B3.3",
            backing_row="B3.3",
            title="The sourced defaults",
            blurb=(
                "The inputs anchored to public figures — revenue, members, the "
                "fraud pool, refunds paid, and the typical size of a claim — each "
                "shown with the public figure behind it and, for the inputs the "
                "formulas read, the range the study explores. One row is context, "
                "not a formula input: the share of fees billed above the public "
                "tariff. The headline figures above the rows are derived from "
                "the inputs, at the defaults."
            ),
            tag="Modeled",
            kind="parameters",
            headline=_headline_rows(formulas),
            series=_parameter_rows(conn, "sourced", "B3.3"),
            sources=_B33_SOURCES,
            notes=(
                "Each range is shown as a fixed mark, not a slider you drag: low, "
                "default and high come from the model’s own table, so a reader "
                "redoes the arithmetic at any point of the range by hand with the "
                "printed formula. A published figure given as a floor spans the "
                "floor to twice it — the study’s stated exploration bound, not a "
                "fact.",
                "Stated here: the four scale anchors are public disclosures cited "
                "second-hand from the project brief, each a floor; the fit rows "
                "span the fit plus and minus two standard errors; the median and "
                "mean cells are read figures with no range of their own; the "
                "extra-billing row’s low and high are the lowest and highest "
                "profession family.",
                text.MEAN_CELL_NOTE,
                text.EXTRA_BILLING_NOTE,
            ),
        ),
        Panel(
            id="B3.4",
            backing_row="B3.4",
            title="The declared-unsourced parameters",
            blurb=(
                "The inputs with no public source — how many claims are flagged, "
                "how many of those are wrong, what a stuck claim costs in contacts "
                "and lost customers, and the two hold-timer settings. Each is a "
                "declared guess with the range worth exploring, styled apart from "
                "the sourced rows, never a settled fact."
            ),
            tag="Modeled",
            kind="parameters",
            series=_parameter_rows(conn, "unsourced", "B3.4"),
            sources=(MODEL_FILE,),
            notes=(
                "The low, default and high are static marks, nothing to drag: the "
                "printed formulas and these spans let a reader redo the arithmetic "
                "at any point of the range by hand. A control that recomputes on "
                "the page is a script, and this page carries none.",
                "Stated here: the cost per contact is a declared guess awaiting a "
                "public benchmark; if one is handed over, the row moves to the "
                "sourced panel with its citation and nothing else changes.",
            ),
        ),
    ]


# --- Beat 4 readers (Phase 9d): the three fixes, drawn beside the Beat 3 curves --
def net_domain(values: Iterable[float]) -> tuple[float, float]:
    """B4.1's y domain — the net curve dips below zero (the crossover), so unlike
    `curve_domain` the lower bound follows the data: each non-zero bound rounded
    outward to one significant figure (−1,337,879.52 → −2,000,000; 1,309,102.82
    → 2,000,000). A layout number by one fixed rule; no displayed figure derives
    from it (the `curve_domain` invariant, mirrored)."""
    vals = list(values)
    lo, hi = min(vals, default=0.0), max(vals, default=0.0)
    bottom = -_sig_ceil(-lo) if lo < 0 else 0.0
    top = _sig_ceil(hi) if hi > 0 else 0.0
    return (0.0, 1.0) if top == bottom else (bottom, top)


def _net_curves(curve_rows: list[tuple], panel_id: str) -> tuple[Series, ...]:
    """B4.1: one net (fraud − friction) curve per cost-model scenario, in
    `SCENARIOS` order — baseline the reference — four series within the
    five-slot palette, each a series of `cost_curves` `net` cells keyed on
    `scenario`. Reads the already-fetched `cost_curves` rows (grouped by
    `scenario` here, so the mart is read once for the whole panel). The display
    names are the closed `SCENARIO_NAMES` map, pinned equal to the scenario set."""
    if tuple(text.SCENARIO_NAMES) != tuple(SCENARIOS):
        raise RenderRefused(
            f"{panel_id}: SCENARIO_NAMES {tuple(text.SCENARIO_NAMES)} are not the "
            f"cost-model scenarios {tuple(SCENARIOS)}"
        )
    by_scenario = _rows_by_scenario(curve_rows)
    series = []
    for slot, scenario in enumerate(text.SCENARIO_NAMES):
        points = [
            Point(
                x_key(float(_require(flag_rate, "flag_rate", panel_id))),
                float(_require(net, "net", panel_id)),
                str(_require(tag, "tag", panel_id)),
                "",
                "eur",
            )
            for flag_rate, _fraud, _friction, net, _is_default, tag in by_scenario.get(
                scenario, []
            )
        ]
        if not points:
            raise RenderRefused(f"{panel_id}: cost_curves has no rows for {scenario!r}")
        series.append(Series(text.SCENARIO_NAMES[scenario], slot, tuple(points)))
    return tuple(series)


def _net_marker(
    curve_rows: list[tuple], panel_id: str
) -> tuple[tuple[str, float], ...]:
    """B4.1's single "you are here" rule: the baseline scenario's default flag
    rate (every scenario shares the grid and the default), on a grid x the curves
    draw. Reads the already-fetched rows, so the mart is read once for B4.1."""
    baseline = _rows_by_scenario(curve_rows).get(BASELINE, [])
    return ((text.MARKER_DEFAULT, _one_default_rate(baseline, BASELINE, panel_id)),)


def _rows_by_scenario(curve_rows: list[tuple]) -> dict[str, list[tuple]]:
    """The `cost_curves` rows grouped by their `scenario` (the first column),
    each value the rows with `scenario` stripped — so B4.1 reads the mart once
    and both readers filter in Python (the Beat 3 read-whole pattern)."""
    by_scenario: dict[str, list[tuple]] = {}
    for scenario, *rest in curve_rows:
        by_scenario.setdefault(scenario, []).append(tuple(rest))
    return by_scenario


def _hold_summary(conn, panel_id: str) -> dict[str, tuple[float, float, str]]:
    """B4.3: the mean hold days and the timer-released share per simulator
    scenario, from one SQL aggregate over `guardrail_sim`, rounded at the model's
    one site (`rounded`) — the reduction a test pins equal to
    `guardrail_sim.summarize` (pinned decision 4). The share is `released` /
    `claim_count`, exact. A scenario outside the closed `SIM_SCENARIOS` set, a
    scenario carrying two tags, or a missing one, refuses by name."""
    known = {s.name for s in SIM_SCENARIOS}
    summary: dict[str, tuple[float, float, str]] = {}
    for scenario, tag, mean_hold, released, claim_count in _rows(
        conn, _Q_GUARDRAIL_AGG
    ):
        if scenario not in known:
            raise RenderRefused(
                f"{panel_id}: guardrail_sim scenario {scenario!r} is not one of "
                f"{tuple(sorted(known))}"
            )
        if scenario in summary:
            raise RenderRefused(
                f"{panel_id}: guardrail_sim scenario {scenario!r} carries two tags"
            )
        n = int(_require(claim_count, "claim_count", panel_id))
        summary[scenario] = (
            rounded("days", float(_require(mean_hold, "mean_hold_days", panel_id))),
            rounded("rate", int(_require(released, "released", panel_id)) / n),
            str(_require(tag, "tag", panel_id)),
        )
    for name in known:
        if name not in summary:
            raise RenderRefused(
                f"{panel_id}: guardrail_sim has no rows for scenario {name!r}"
            )
    return summary


def _hold_bars(
    summary: dict[str, tuple[float, float, str]], panel_id: str
) -> tuple[Series, ...]:
    """B4.3: one bar per simulator scenario (the spec's "scenario × hold days"),
    in `SIM_SCENARIOS` order — the no-fix hold is the "before", each fix's hold
    the "after" beside it, the before shown once rather than repeated per fix.
    Each bar the scenario's mean hold, carrying the mart's own tag (from the
    aggregate), labelled by the closed `SIM_HOLD_NAMES` map."""
    names = tuple(s.name for s in SIM_SCENARIOS)
    if tuple(text.SIM_HOLD_NAMES) != names:
        raise RenderRefused(
            f"{panel_id}: SIM_HOLD_NAMES {tuple(text.SIM_HOLD_NAMES)} are not the "
            f"simulator scenarios {names}"
        )
    points = tuple(
        Point(text.SIM_HOLD_NAMES[name], summary[name][0], summary[name][2], "", "days")
        for name in text.SIM_HOLD_NAMES
    )
    return (Series("Mean hold", 0, points),)


class _Threshold(NamedTuple):
    """B4.2's default `sla_threshold` row, validated once: the timer day, the
    net-negative amount, the share of claims under it, and the row's tag — named
    fields so the stat row and the note read the same cells without re-checking."""

    timer_days: float
    amount: float
    share: float
    tag: str


def _threshold_row(conn, panel_id: str) -> _Threshold:
    """B4.2: the one `is_default` row of `sla_threshold`, validated into a
    `_Threshold`. Exactly one default row, else refuse."""
    rows = [
        (timer_days, amount, share, tag)
        for timer_days, amount, share, is_default, tag in _rows(conn, _Q_SLA_THRESHOLD)
        if is_default
    ]
    if len(rows) != 1:
        raise RenderRefused(
            f"{panel_id}: sla_threshold marks {len(rows)} default rows — exactly one"
        )
    timer_days, amount, share, tag = rows[0]
    return _Threshold(
        float(_require(timer_days, "timer_days", panel_id)),
        float(_require(amount, "timer_amount_eur", panel_id)),
        float(_require(share, "share_under", panel_id)),
        str(_require(tag, "tag", panel_id)),
    )


def _threshold_stats(threshold: _Threshold) -> tuple[Series, ...]:
    """B4.2's stat row: the three cells of the default threshold row, each in its
    display unit and carrying the row's own tag; the labels and units are the
    closed `text.THRESHOLD_STATS` map."""
    values = (threshold.timer_days, threshold.amount, threshold.share)
    points = tuple(
        Point(label, value, threshold.tag, "", unit)
        for (label, unit), value in zip(text.THRESHOLD_STATS, values, strict=True)
    )
    return (Series("threshold", 0, points),)


def beat4_panels(conn) -> list[Panel]:
    """The four Beat 4 panels: B4.1 the net curve across the four scenarios, B4.2
    the computed hold-length threshold, B4.3 the before/after holds per fix, B4.4
    the Pending outcome-log panel. Every number a `cost_curves`, `sla_threshold`
    or `guardrail_sim` cell, filled on every rebuild input — so no corpus gate,
    and the committed page shows these numbers."""
    curve_rows = _rows(conn, _Q_COST_CURVES)  # read once; B4.1 filters in Python
    net = _net_curves(curve_rows, "B4.1")
    marker = _net_marker(curve_rows, "B4.1")
    threshold = _threshold_row(conn, "B4.2")
    summary = _hold_summary(conn, "B4.3")
    bars = _hold_bars(summary, "B4.3")
    return [
        Panel(
            id="B4.1",
            backing_row="B4.1",
            title="The curves move",
            blurb=(
                "The first fix collapses the back-and-forth for documents: one "
                "request returns the whole list. Fewer stuck claims means less "
                "friction, "
                "so the net line — fraud saved minus friction cost — lifts. Each "
                "line is one scenario; the fraud caught is unchanged, so what "
                "moves is the cost."
            ),
            tag="Modeled",
            kind="curve",
            series=net,
            markers=marker,
            domain=net_domain(p.value for s in net for p in s.points),
            sources=_FIT_SOURCES,
            notes=(
                "Each line is the net at the same defaults with one or two inputs "
                "changed — ask-once sets contacts to one, the clock is modelled as "
                "halving the customers lost, both apply together. The fixes do not "
                "change the fraud caught, only the friction, so the fraud-saved "
                "curve of Beat 3 is the same under every scenario.",
                "The rule is the default flag rate, read from the model’s own "
                "row, not the drawing (the crossover of Beat 3 above). Where a net "
                "line stays above zero across the grid, that scenario never "
                "reaches a rate at which the flags cost more than they recover.",
            ),
        ),
        Panel(
            id="B4.2",
            backing_row="B4.2",
            title="A clock on every hold",
            blurb=(
                "The second fix puts a timer on each held claim: past a threshold, "
                "a small low-risk claim releases itself and a large one goes to a "
                "person. The threshold is computed from the Beat 3 model, not "
                "guessed — the day and amount below which a hold that long costs "
                "more than it saves."
            ),
            tag="Modeled",
            kind="stat_row",
            series=_threshold_stats(threshold),
            sources=_FIT_SOURCES,
            notes=(
                text.threshold_note(
                    display(threshold.timer_days, "days"),
                    display(threshold.amount, "eur"),
                    display(threshold.share, "pct"),
                ),
                "The threshold is the amount at which the friction of a hold that "
                "long equals the fraud it could still catch, read from the cost "
                "model’s own rows — the same arithmetic printed in Beat 3, at the "
                "baseline defaults.",
            ),
        ),
        Panel(
            id="B4.3",
            backing_row="B4.3",
            title="Before and after",
            blurb=(
                "What the fixes do to how long a claim waits: the average hold in "
                "days before any fix and after each one. Ask-once cuts the "
                "document loop to a single round; the clock releases the small "
                "low-risk claims early."
            ),
            tag="Modeled",
            kind="grouped_bar",
            series=bars,
            # the bar's y domain is the same 0-floor, one-significant-figure rule
            # the curves use (holds are non-negative days) — `curve_domain` names
            # the rule, reused here rather than a second copy of it.
            domain=curve_domain(p.value for s in bars for p in s.points),
            sources=_FIT_SOURCES,
            notes=(
                text.released_note(
                    display(summary["hold_timer"][1], "pct"),
                ),
                "Each bar is the mean over a thousand synthetic claims — the "
                "fitted distribution read at a thousand evenly spaced points, no "
                "individual claim, none is public. One hold per scenario, not a "
                "distribution: the no-fix bar is the hold before any fix, each fix "
                "beside it, the document loop or the timer, whichever ends the hold "
                "first.",
            ),
        ),
        Panel(
            id="B4.4",
            backing_row="B4.4",
            title="Count the mistakes",
            blurb=(
                "The third fix records how each hold ends — fraud confirmed, or "
                "released clean. That log would be the false-positive rate per "
                "flag rule the system otherwise never learns, and the same events "
                "would drive a status notification against silent rejections."
            ),
            tag="Pending",
            kind="hero",
            placeholder=text.BEAT4_PENDING,
        ),
    ]


# --- Beat 5: the facts you can check, and reproducibility ----------------------
# B5.1's sources are the repository files the facts are counted from; B5.2's is
# the pipeline that produces the counts — the same cells BACKING B5.1/B5.2 name.
_B5_1_SOURCES = ("classify/llm.py", "models/cost_model.py", "study/model.py")
_B5_2_SOURCES = ("pipeline/build.py",)


def _determinism_facts(conn) -> tuple[Series, ...]:
    """B5.1: the checkable repo facts as a stat row, in the display order of the
    closed `text.DETERMINISM_FACTS` map, each carrying the mart row's own tag.
    Every mart fact must be in the map and every map fact must have a row — the
    writer ↔ mart ↔ page identity (the `_formula_rows` pattern). Not corpus-gated:
    a repo fact is constant on any input, so this reads the mart directly."""
    by_fact = {
        fact: (value, tag) for fact, value, tag in _rows(conn, _Q_DETERMINISM_FACTS)
    }
    for fact in by_fact:
        if fact not in text.DETERMINISM_FACTS:
            raise RenderRefused(
                f"B5.1: determinism_facts row {fact!r} has no display label "
                "(not in the closed map)"
            )
    points = []
    for fact, (label, unit) in text.DETERMINISM_FACTS.items():
        if fact not in by_fact:
            raise RenderRefused(f"B5.1: determinism_facts has no {fact!r} row")
        value, tag = by_fact[fact]
        points.append(
            Point(
                label,
                float(_require(value, "value", "B5.1")),
                str(_require(tag, "tag", "B5.1")),
                "",
                unit,
            )
        )
    return (Series("facts", 0, tuple(points)),)


def _row_counts_table(conn) -> tuple[Series, ...]:
    """B5.2: one table row per pipeline stage, the count in its cell, in the flow
    order of the closed `text.ROW_COUNT_STAGES` map, each carrying the mart row's
    tag. Writer ↔ mart ↔ page identity, as B5.1. Built only over a captured input
    (the corpus gate calls this; a fixture input renders the fixture note)."""
    by_stage = {
        stage: (value, tag) for stage, value, tag in _rows(conn, _Q_PIPELINE_ROW_COUNTS)
    }
    for stage in by_stage:
        if stage not in text.ROW_COUNT_STAGES:
            raise RenderRefused(
                f"B5.2: pipeline_row_counts row {stage!r} has no display name "
                "(not in the closed map)"
            )
    series = []
    for stage, name in text.ROW_COUNT_STAGES.items():
        if stage not in by_stage:
            raise RenderRefused(f"B5.2: pipeline_row_counts has no {stage!r} row")
        value, tag = by_stage[stage]
        series.append(
            Series(
                name,
                0,
                (
                    Point(
                        "Rows",
                        float(_require(value, "value", "B5.2")),
                        str(_require(tag, "tag", "B5.2")),
                        "",
                        "count",
                    ),
                ),
            )
        )
    return tuple(series)


def beat5_panels(conn) -> list[Panel]:
    """The two Beat 5 panels. B5.1 is Measured and NOT corpus-gated — a repo fact
    is constant on any input, so the committed synthetic page shows the numbers.
    B5.2 is Measured behind the corpus gate (like Beat 2): counted over a captured
    input, the labelled fixture state over the frozen synthetic input."""
    counts_series, counts_fixture = _corpus_series(
        conn, "pipeline_row_counts", "B5.2", lambda: _row_counts_table(conn)
    )
    return [
        Panel(
            id="B5.1",
            backing_row="B5.1",
            title="The facts you can check",
            blurb=(
                "Three facts about how this study is built, each a count you can "
                "verify in the code. A language model makes a decision in exactly "
                "one place; the cost model's formulas are printed next to the "
                "numbers they give; and every number on the page carries a tag "
                "saying where it came from."
            ),
            tag="Measured",
            kind="stat_row",
            series=_determinism_facts(conn),
            sources=_B5_1_SOURCES,
            notes=(text.DETERMINISM_NOTE,),
        ),
        Panel(
            id="B5.2",
            backing_row="B5.2",
            title="Rerun it and the numbers hold",
            blurb=(
                "The same reviews always produce the same numbers. This is how "
                "many reviews the pipeline holds at each step — as scraped, after "
                "removing duplicates, and after tagging by theme — so anyone can "
                "rebuild the study from the raw data and check every count."
            ),
            tag="Measured",
            kind="table",
            series=counts_series,
            fixture=counts_fixture,
            sources=_B5_2_SOURCES,
            columns=("Pipeline stage", "Rows"),
            notes=(text.ROW_COUNTS_NOTE,),
        ),
    ]
