"""Build the study's panels from the marts (PLAN §4.6). One layer above
`study/model.py` (the types and the contract) and one below `study/export.py`
(the renderers): a reader per Beat 1 chart turns mart rows into `Panel`s, every
number read straight from its mart and never recomputed here, every query
carrying its own `order by` so the bytes are stable.

Beat 1 is the proving ground; 9b/9c add the Beat 2/3 readers on the same
pattern."""

from __future__ import annotations

from study.model import Panel, Point, RenderRefused, Series, _require


# --- Reading the marts (every query carries its own order by) ------------------
def _rows(conn, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


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
    rows = _rows(
        conn,
        "select profile, month, rating, tag, source_url from rating_trend "
        "where channel = 'unsolicited' and segment = 'digital-first' "
        "order by profile, month, source",
    )
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
    rows = _rows(
        conn,
        "select stat, value, tag, source_url from platform_stats "
        "where segment = 'digital-first' and profile = 'fr-digital-first' "
        "and source = 'opinion-assurances' order by stat",
    )
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
            note=(
                "Stated here: invited channels (the app stores) are positively "
                "self-selected and unsolicited platforms negatively, so part of "
                "the gap is who gets asked, not only how the service performs."
            ),
            domain=(0.0, 5.0),
            axis_unit="stars",
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
            note=(
                "Stated here: today the answer rate and time come from one profile "
                "on one platform, so the comparison across platforms waits for a "
                "second platform’s figures."
            ),
        ),
    ]
