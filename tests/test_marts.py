"""The four snapshot marts (spec Phase 3a, invariant 2; done-when 2): built from
`stg_platform_snapshots`, each row carrying exactly one tag, pinned on the
anchors, byte-stable across rebuilds under a moving clock."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pipeline.build import rebuild
from pipeline.warehouse import connect, database_for
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
    root = tmp_path_factory.mktemp("marts")
    rebuild("duckdb", "synthetic", root=root)
    return database_for("synthetic", root)


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


STATS = ("review_count", "one_star_share", "response_rate", "response_delay_days")


def test_platform_stats_matches_pins(anchors_db):
    """One row per (segment, source, profile, stat) — A2 — so each stat is its
    own latest point; the profile's four stats read back as pinned."""
    rows = _query(
        anchors_db,
        "select source, profile, stat, value from platform_stats order by 1, 2, 3",
    )
    assert len(rows) == pins.PLATFORM_STATS_ANCHOR_ROWS
    assert {r[2] for r in rows} <= set(STATS)
    oa = {
        stat: str(value)
        for source, profile, stat, value in rows
        if (source, profile) == ("opinion-assurances", "fr-digital-first")
    }
    assert oa == pins.PLATFORM_STATS_OPINION_ASSURANCES


def test_a_later_reading_of_one_stat_keeps_the_others(tmp_path):
    """A2 (round 1, finding 21): a second hand entry that reads only the count
    becomes the count's latest point; the three stats read the day before keep
    their own point, tag and day — nothing is blanked."""
    from pipeline.build import MANUAL_COLUMNS
    from tests.test_snapshots import _write_csv

    def row(day: str, **stats: str) -> dict[str, str]:
        base = {
            "source": "fr-digital-first-app-store-listing",
            "captured_at": day,
            "rating": "4.9",
            "review_count": "13000",
            "one_star_share": "",
            "response_rate": "",
            "response_delay_days": "",
            "read_from": "page",
        }
        base.update(stats)
        return base

    manual = _write_csv(
        tmp_path / "m.csv",
        MANUAL_COLUMNS,
        [
            row(
                "2026-09-01",
                one_star_share="0.05",
                response_rate="0.5",
                response_delay_days="3",
            ),
            row("2026-09-02", review_count="13100"),
        ],
    )
    db = database_for("captured", tmp_path)
    rebuild(
        "duckdb",
        "captured",
        root=tmp_path,
        cache_dir=tmp_path / "no",
        manual_file=manual,
    )
    rows = _query(
        db,
        "select stat, value, captured_at, tag from platform_stats "
        "where source = 'app-store' and profile = 'fr-digital-first' order by stat",
    )
    assert rows == [
        ("one_star_share", Decimal("0.050"), "2026-09-01", "Measured"),
        ("response_delay_days", Decimal("3.000"), "2026-09-01", "Measured"),
        ("response_rate", Decimal("0.500"), "2026-09-01", "Measured"),
        ("review_count", Decimal("13100.000"), "2026-09-02", "Measured"),
    ]


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
    peers = _query(
        anchors_db,
        "select profile, rating, review_count from peer_ratings "
        "where profile <> 'fr-digital-first'",
    )
    assert {p: (str(r), c) for p, r, c in peers} == pins.PEER_RATINGS_ANCHOR_VALUES


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
    db = database_for("captured", tmp_path)
    rebuild("duckdb", "captured", root=tmp_path, cache_dir=cache, manual_file=manual)
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
        "select stat, value, tag, captured_at from platform_stats "
        "where source = 'app-store' and profile = 'fr-digital-first' order by stat",
    )
    assert stats == [
        ("one_star_share", Decimal("0.050"), "Measured", "2026-09-02"),
        ("response_delay_days", Decimal("3.000"), "Measured", "2026-09-02"),
        ("response_rate", Decimal("0.500"), "Measured", "2026-09-02"),
        ("review_count", Decimal("13000.000"), "Measured", "2026-09-02"),
    ]
    assert _query(
        db,
        "select distinct tag from platform_stats where source <> 'app-store' "
        "and source <> 'google-play'",
    ) == [("Documented",)]
    assert _query(db, "select distinct tag from peer_ratings") == [("Documented",)]
    tags = {t for m in MARTS for (t,) in _query(db, f"select distinct tag from {m}")}
    assert tags == {"Documented", "Measured"}


def test_the_tracked_trustpilot_hand_read_row_reaches_the_marts_in_its_anchor_series(
    tmp_path,
):
    """Phase 3b: the delivered `data/snapshots/manual_snapshots.csv` Trustpilot
    row, carried end to end through `ROWS=captured` (the tracked file, an empty
    cache — deterministic, no machine cache), lands in the same (source,
    profile) group as the Documented Trustpilot anchors: one series, mixed tags,
    the Measured 2026-09 point the latest in rating_trend, channel_gap and
    peer_ratings."""
    from pipeline.build import MANUAL_SNAPSHOTS

    cache = tmp_path / "cache"
    cache.mkdir()
    db = database_for("captured", tmp_path)
    rebuild(
        "duckdb",
        "captured",
        root=tmp_path,
        cache_dir=cache,
        manual_file=MANUAL_SNAPSHOTS,
    )
    key = "source = 'trustpilot' and profile = 'fr-digital-first'"
    trend = _query(
        db, f"select month, rating, tag from rating_trend where {key} order by month"
    )
    assert trend == [
        ("2025-01", Decimal("4.200"), "Documented"),
        ("2025-09", Decimal("3.800"), "Documented"),
        ("2026-06", Decimal("3.900"), "Documented"),
        ("2026-09", Decimal("3.900"), "Measured"),  # the hand-read point, one group
    ]
    assert _query(
        db, f"select rating, review_count, tag from peer_ratings where {key}"
    ) == [(Decimal("3.900"), 1072, "Measured")]
    assert _query(
        db, f"select channel, rating, review_count, tag from channel_gap where {key}"
    ) == [("unsolicited", Decimal("3.900"), 1072, "Measured")]


def test_review_tables_have_no_personal_columns(anchors_db):
    """Phase 3c done-when 3 / §2.5: the review tables hold no reviewer identity
    — the parser can write a name, avatar or country into no column because
    none exists. The column set is exactly the raw-review fields."""
    from pipeline import warehouse

    expected = {
        "source",
        "external_id",
        "source_url",
        "captured_at",
        "run_id",
        "review_date",
        "rating",
        "title",
        "body",
        "content_hash",
    }
    personal = {
        "name",
        "name2",
        "reviewer",
        "avatar",
        "image",
        "addresscountry",
        "country",
    }
    conn = connect("duckdb", database=anchors_db)
    try:
        for table in ("raw_reviews", "stg_reviews"):
            cols = {
                r[0]
                for r in conn.execute(
                    "select column_name from information_schema.columns "
                    "where table_schema = ? and table_name = ?",
                    [warehouse.default_schema(conn), table],
                ).fetchall()
            }
            assert cols == expected, table
            assert not (cols & personal), table
    finally:
        conn.close()


def _trustpilot_capture(cache, source, reviews, captured_at="2026-09-04T12:00:00"):
    """Write an authorized-export capture (`page-1.csv` + meta) for `source`
    into `cache`, addressed to the source's declared page — read from the
    declaration, never a brand literal in this file (D1). `reviews` is
    (title, body, stars, 'Month D, YYYY') tuples."""
    import csv
    import io
    import json

    from ingest.trustpilot import COLUMNS

    capdir = cache / source.platform / source.name / captured_at.replace(":", "-")
    capdir.mkdir(parents=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    for i, (title, body, stars, day) in enumerate(reviews, 1):
        row = {c: "" for c in COLUMNS}
        row.update(
            web_scraper_order=f"c{i}",
            web_scraper_start_url=source.pages[0],
            headline=title,
            reviewbody=body,
            data3=day,
            rating=f"https://cdn.trustpilot.net/brand-assets/4.1.0/stars/stars-{stars}.svg",
        )
        w.writerow(row)
    (capdir / "page-1.csv").write_text("﻿" + buf.getvalue(), encoding="utf-8")
    (capdir / "page-1.meta.json").write_text(
        json.dumps(
            {"source_url": source.pages[0], "captured_at": captured_at, "status": 200}
        ),
        encoding="utf-8",
    )


def test_trustpilot_rating_point_unchanged_by_corpus(tmp_path):
    """Central constraint / done-when 4: loading the authorized review corpus
    does not move the hand-read 3.9/1,072 rating point. The reviews are a
    separate source with no snapshot, so rating_trend/peer_ratings/channel_gap
    read the same figures as `test_the_tracked_trustpilot_hand_read_row…` pins
    with an empty cache — here the corpus is present and they are identical."""
    from ingest.sources import by_name
    from pipeline.build import MANUAL_SNAPSHOTS

    src = by_name("fr-digital-first-trustpilot-reviews")
    cache = tmp_path / "cache"
    _trustpilot_capture(
        cache,
        src,
        [
            ("Bien", "Corps un.", 5, "August 1, 2026"),
            ("Mal", "Corps deux.", 1, "July 2, 2026"),
        ],
    )
    db = database_for("captured", tmp_path)
    rebuild(
        "duckdb",
        "captured",
        root=tmp_path,
        cache_dir=cache,
        manual_file=MANUAL_SNAPSHOTS,
    )
    # the corpus loaded …
    assert _query(
        db, "select count(*) from stg_reviews where source = 'trustpilot'"
    ) == [(2,)]
    # … and the rating series is exactly the hand-read-only pins, unmoved.
    key = "source = 'trustpilot' and profile = 'fr-digital-first'"
    assert _query(
        db, f"select month, rating, tag from rating_trend where {key} order by month"
    ) == [
        ("2025-01", Decimal("4.200"), "Documented"),
        ("2025-09", Decimal("3.800"), "Documented"),
        ("2026-06", Decimal("3.900"), "Documented"),
        ("2026-09", Decimal("3.900"), "Measured"),
    ]
    assert _query(
        db, f"select rating, review_count, tag from peer_ratings where {key}"
    ) == [(Decimal("3.900"), 1072, "Measured")]


def test_a_same_day_measured_point_stands_in_front_of_an_anchor_in_every_mart(
    tmp_path,
):
    """A2 (b): when two points share a day, `precedence` puts the figure we
    measured in front of the anchor — in every mart, not only channel_gap.
    The measured row's address sorts AFTER the anchor's root, so without
    `precedence` the anchor would win on the address alone (round 2,
    functionality-tester F2)."""
    from pipeline.build import build_derived, load_snapshots

    db = database_for("synthetic", tmp_path)
    rebuild("duckdb", "synthetic", root=tmp_path)
    conn = connect("duckdb", database=db)
    try:
        # the unsolicited studied-insurer anchor of 2026-06-15, re-read by hand
        # the same day under an address that sorts after the platform root
        load_snapshots(
            conn,
            [
                {
                    "source": "trustpilot",
                    "profile": "fr-digital-first",
                    "segment": "digital-first",
                    "channel": "unsolicited",
                    "origin": "manual",
                    "rating": Decimal("3.9"),
                    "review_count": 975,
                    "one_star_share": None,
                    "response_rate": None,
                    "response_delay_days": None,
                    "source_url": "https://www.trustpilot.com/review/x",
                    "captured_at": "2026-06-15",
                    "seeded_from": "",
                }
            ],
            "test",
            "captured",
        )
        build_derived(conn)
        where = "source = 'trustpilot' and profile = 'fr-digital-first'"
        for mart, extra in (
            ("rating_trend", " and month = '2026-06'"),
            ("channel_gap", ""),
            ("peer_ratings", ""),
            ("platform_stats", " and stat = 'review_count'"),
        ):
            rows = conn.execute(
                f"select tag, source_url from {mart} where {where}{extra}"
            ).fetchall()
            assert rows == [("Measured", "https://www.trustpilot.com/review/x")], mart
    finally:
        conn.close()


def _measured(origin: str, day: str, url: str, rating: str) -> dict[str, object]:
    """A Measured point on the studied insurer's unsolicited Trustpilot key —
    the key the synthetic anchors carry for 2026-06-15."""
    return {
        "source": "trustpilot",
        "profile": "fr-digital-first",
        "segment": "digital-first",
        "channel": "unsolicited",
        "origin": origin,
        "rating": Decimal(rating),
        "review_count": 975,
        "one_star_share": None,
        "response_rate": None,
        "response_delay_days": None,
        "source_url": url,
        "captured_at": day,
        "seeded_from": "",
    }


def test_the_latest_day_in_a_month_is_the_months_point_in_rating_trend(tmp_path):
    """B1.2's grain, "the latest snapshot in that month": of two readings of
    one key in one month, the later day's rating and address reach the mart.
    The earlier day's address sorts FIRST and both have the same precedence,
    so only `captured_at desc` can pick the later one (round 3,
    functionality-tester F4)."""
    from pipeline.build import build_derived, load_snapshots

    db = database_for("synthetic", tmp_path)
    rebuild("duckdb", "synthetic", root=tmp_path)
    conn = connect("duckdb", database=db)
    try:
        load_snapshots(
            conn,
            [
                _measured(
                    "manual", "2026-06-10", "https://www.trustpilot.com/a", "3.1"
                ),
                _measured(
                    "manual", "2026-06-20", "https://www.trustpilot.com/z", "3.7"
                ),
            ],
            "test",
            "captured",
        )
        build_derived(conn)
        rows = conn.execute(
            "select rating, source_url, captured_at from rating_trend where source"
            " = 'trustpilot' and profile = 'fr-digital-first' and month = '2026-06'"
        ).fetchall()
        assert rows == [
            (Decimal("3.700"), "https://www.trustpilot.com/z", "2026-06-20")
        ]
    finally:
        conn.close()


def test_a_same_day_capture_stands_in_front_of_a_hand_entry_in_every_mart(
    tmp_path,
):
    """The declared precedence, a capture (fetch) before a hand entry
    (manual) before an anchor: a fetched and a hand-read point on one key and
    one day, the hand-read address sorting FIRST, and the fetched row reaches
    all four marts — only `precedence` can put it there (round 3,
    functionality-tester F5)."""
    from pipeline.build import build_derived, load_snapshots

    db = database_for("synthetic", tmp_path)
    rebuild("duckdb", "synthetic", root=tmp_path)
    conn = connect("duckdb", database=db)
    try:
        load_snapshots(
            conn,
            [
                _measured(
                    "manual", "2026-06-15", "https://www.trustpilot.com/a", "3.1"
                ),
                _measured("fetch", "2026-06-15", "https://www.trustpilot.com/b", "3.7"),
            ],
            "test",
            "captured",
        )
        build_derived(conn)
        where = "source = 'trustpilot' and profile = 'fr-digital-first'"
        for mart, extra in (
            ("rating_trend", " and month = '2026-06'"),
            ("channel_gap", ""),
            ("peer_ratings", ""),
            ("platform_stats", " and stat = 'review_count'"),
        ):
            rows = conn.execute(
                f"select tag, source_url from {mart} where {where}{extra}"
            ).fetchall()
            assert rows == [("Measured", "https://www.trustpilot.com/b")], mart
    finally:
        conn.close()


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
        db = database_for(rows, tmp_path / name)
        rebuild("duckdb", rows, root=tmp_path / name)
        seen.append(
            {m: sorted(map(str, _query(db, f"select * from {m}"))) for m in MARTS}
        )
    assert seen[0] == seen[1]
    assert all(seen[0][m] for m in MARTS)  # each mart holds rows to compare


def test_reimport_inserts_nothing(tmp_path):
    """Phase 3c done-when 6: re-importing the same authorized export inserts
    nothing — content_hash idempotency over the review corpus, per-table counts
    stable across two rebuilds."""
    from ingest.sources import by_name
    from pipeline.build import MANUAL_SNAPSHOTS, idempotency_check

    src = by_name("fr-digital-first-trustpilot-reviews")
    cache = tmp_path / "cache"
    _trustpilot_capture(
        cache,
        src,
        [
            ("Bien", "Corps.", 5, "August 1, 2026"),
            ("Mal", "Corps deux.", 1, "July 2, 2026"),
        ],
    )
    ok, first, second = idempotency_check(
        "duckdb", "captured", cache_dir=cache, manual_file=MANUAL_SNAPSHOTS
    )
    assert ok and first == second
    assert first["stg_reviews"] == 2  # both reviews loaded once, unchanged on re-run
