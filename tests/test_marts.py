"""The four snapshot marts (spec Phase 3a, invariant 2; done-when 2): built from
`stg_platform_snapshots`, each row carrying exactly one tag, pinned on the
anchors, byte-stable across rebuilds under a moving clock."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pipeline.build import rebuild
from pipeline.warehouse import connect
from tests import pins

MARTS = ("rating_trend", "channel_gap", "platform_stats", "peer_ratings")


def _query(db: Path, sql: str):
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def anchors_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("marts") / "w.duckdb"
    rebuild("duckdb", "synthetic", database=db)
    return db


def test_every_mart_row_carries_exactly_one_tag(anchors_db):
    names = {
        r[0]
        for r in _query(anchors_db, "select table_name from information_schema.tables")
    }
    assert set(MARTS) <= names
    for mart in MARTS:
        tags = _query(anchors_db, f"select distinct tag from {mart}")
        assert tags == [("Documented",)], mart  # anchors only: every point seeded
        cols = {
            r[0]
            for r in _query(
                anchors_db,
                f"select column_name from information_schema.columns where table_name "
                f"= '{mart}'",
            )
        }
        assert {"tag", "source_url", "captured_at", "run_id"} <= cols, mart


def test_rating_trend_matches_pins(anchors_db):
    rows = _query(
        anchors_db,
        "select channel, segment, source, profile, month, rating from rating_trend "
        "order by 1, 2, 3, 4, 5",
    )
    assert len(rows) == pins.RATING_TREND_ANCHOR_ROWS
    digital_first = [
        r for r in rows if r[1] == "digital-first" and r[0] == "unsolicited"
    ]
    assert [(r[4], r[5]) for r in digital_first] == [
        ("2025-01", Decimal("4.200")),
        ("2025-09", Decimal("3.800")),
        ("2026-06", Decimal("3.900")),
    ]
    assert all(r[5] is not None for r in rows)


def test_channel_gap_matches_pins(anchors_db):
    rows = _query(
        anchors_db,
        "select channel, source, rating, review_count, captured_at from channel_gap "
        "where segment = 'digital-first' and profile = 'fr-digital-first'",
    )
    got = {(c, s): (str(r), n, at) for c, s, r, n, at in rows}
    assert got == pins.CHANNEL_GAP_DIGITAL_FIRST
    assert _query(anchors_db, "select count(*) from channel_gap") == [
        (pins.CHANNEL_GAP_ANCHOR_ROWS,)
    ]


def test_platform_stats_matches_pins(anchors_db):
    rows = _query(
        anchors_db,
        "select source, one_star_share, response_rate, response_delay_days, "
        "review_count from platform_stats order by source",
    )
    assert len(rows) == pins.PLATFORM_STATS_ANCHOR_ROWS
    (oa,) = [r for r in rows if r[0] == "opinion-assurances"]
    assert (
        str(oa[1]),
        str(oa[2]),
        str(oa[3]),
        oa[4],
    ) == pins.PLATFORM_STATS_OPINION_ASSURANCES


def test_peer_ratings_matches_pins(anchors_db):
    rows = _query(
        anchors_db,
        "select segment, source, profile, rating from peer_ratings order by segment, "
        "profile",
    )
    assert len(rows) == pins.PEER_RATINGS_ANCHOR_ROWS
    assert {r[0] for r in rows} == {
        "digital-first",
        "traditional",
        "digital-challenger",
    }
    assert all(
        r[1] == "trustpilot" for r in rows
    )  # the unsolicited anchors with a rating


def test_a_hand_read_and_a_fetched_point_reach_the_marts_as_measured(tmp_path):
    """Done-when 2 on a Measured row, not only on the anchors: a fetched
    listing (google-play, invited) and a hand-read stat row (app-store,
    invited), both dated after every anchor, become the latest point of their
    key in rating_trend, channel_gap and platform_stats, tagged Measured, with
    their own address and day; the anchors stay Documented beside them; the
    unsolicited-only peer_ratings mart is untouched by either (round 1,
    code-reviewer #8, functionality-tester Done-when 2)."""
    from pipeline.build import MANUAL_COLUMNS
    from tests.test_snapshots import PLAY, _play_capture, _write_csv

    store = "fr-digital-first-app-store-listing"
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-02T10:00:00")
    manual = _write_csv(
        tmp_path / "manual.csv",
        MANUAL_COLUMNS,
        [
            {
                "source": store,
                "captured_at": "2026-09-02",
                "rating": "4.9",
                "review_count": "13000",
                "one_star_share": "0.05",
                "response_rate": "0.5",
                "response_delay_days": "3",
                "read_from": "page",
            }
        ],
    )
    db = tmp_path / "w.duckdb"
    rebuild("duckdb", "captured", database=db, cache_dir=cache, manual_file=manual)
    from ingest.sources import by_name

    store_url = by_name(store).listing
    trend = _query(
        db,
        "select source, month, rating, tag, source_url, captured_at from rating_trend "
        "where channel = 'invited' and profile = 'fr-digital-first' "
        "order by source, month",
    )
    assert trend == [
        (
            "app-store",
            "2024-09",
            Decimal("4.900"),
            "Documented",
            "https://apps.apple.com/",
            "2024-09-15",
        ),
        ("app-store", "2026-09", Decimal("4.900"), "Measured", store_url, "2026-09-02"),
        (
            "google-play",
            "2024-09",
            Decimal("4.500"),
            "Documented",
            "https://play.google.com/",
            "2024-09-15",
        ),
        (
            "google-play",
            "2026-09",
            Decimal("4.123"),
            "Measured",
            PLAY.page_url(1),
            "2026-09-02T10:00:00",
        ),
    ]
    gap = _query(
        db,
        "select source, rating, review_count, tag, captured_at from channel_gap "
        "where channel = 'invited' and profile = 'fr-digital-first' order by source",
    )
    assert gap == [
        ("app-store", Decimal("4.900"), 13000, "Measured", "2026-09-02"),
        ("google-play", Decimal("4.123"), 1234, "Measured", "2026-09-02T10:00:00"),
    ]
    stats = _query(
        db,
        "select source, one_star_share, response_rate, response_delay_days, tag "
        "from platform_stats order by source",
    )
    assert stats == [
        ("app-store", Decimal("0.050"), Decimal("0.500"), Decimal("3.0"), "Measured"),
        (
            "opinion-assurances",
            Decimal("0.231"),
            Decimal("0.820"),
            Decimal("1.5"),
            "Documented",
        ),
        ("trustpilot", Decimal("0.180"), None, None, "Documented"),
    ]
    assert _query(db, "select distinct tag from peer_ratings") == [("Documented",)]
    tags = {t for m in MARTS for (t,) in _query(db, f"select distinct tag from {m}")}
    assert tags == {"Documented", "Measured"}


def _no_clock(cls: type) -> type:
    """A date/datetime class whose `today()` and `now()` raise: reaching either
    on the data path is the failure. Parsing (`fromisoformat`, `strptime`)
    still works, which is all the data path may do with a date."""

    class NoClock(cls):  # type: ignore[misc,valid-type]
        @classmethod
        def today(cls):  # pragma: no cover - reaching here is the failure
            raise AssertionError("a clock was read on the data path")

        @classmethod
        def now(cls, tz=None):  # pragma: no cover - reaching here is the failure
            raise AssertionError("a clock was read on the data path")

    return NoClock


@pytest.mark.parametrize("rows", ["synthetic", "samples"])
def test_marts_are_byte_stable_across_rebuilds(tmp_path, monkeypatch, rows):
    """Two rebuilds of one input, with every clock the data path imports made
    to raise, produce marts equal in EVERY column, `run_id` included: for a
    fixture input `run_id` is the input's name, so a rebuild is byte-stable,
    not merely count-stable. `samples` runs every parser, so the parsers'
    date imports are covered too (round 1, code-reviewer #7)."""
    import ingest.app_store as app_store
    import ingest.captures as captures
    import ingest.opinion_assurances as opinion_assurances
    import pipeline.build as build

    for module, name in (
        (build, "date"),
        (captures, "datetime"),
        (app_store, "datetime"),
        (opinion_assurances, "date"),
    ):
        monkeypatch.setattr(module, name, _no_clock(getattr(module, name)))
    seen = []
    for name in ("a", "b"):
        db = tmp_path / f"{name}.duckdb"
        rebuild("duckdb", rows, database=db)
        seen.append(
            {m: sorted(map(str, _query(db, f"select * from {m}"))) for m in MARTS}
        )
    assert seen[0] == seen[1]
    assert all(seen[0][m] for m in MARTS)  # each mart holds rows to compare
