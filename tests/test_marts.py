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


def test_marts_are_byte_stable_across_rebuilds(tmp_path, monkeypatch):
    import ingest.captures as captures
    import pipeline.build as build

    class NoClock(build.date):
        @classmethod
        def today(cls):  # pragma: no cover - reaching here is the failure
            raise AssertionError("a clock was read on the data path")

    monkeypatch.setattr(build, "date", NoClock)
    seen = []
    for name in ("a", "b"):
        db = tmp_path / f"{name}.duckdb"
        rebuild("duckdb", "synthetic", database=db, run_id=name)
        seen.append(
            {
                m: sorted(map(str, _query(db, f"select * exclude (run_id) from {m}")))
                for m in MARTS
            }
        )
    assert seen[0] == seen[1]
    assert captures  # the reader stays clock-free too (its datetime is only a parser)
