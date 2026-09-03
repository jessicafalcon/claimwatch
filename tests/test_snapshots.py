"""`platform_snapshots` (spec Phase 3a, invariants 1 and 2; done-when 1): the
anchors seed with `origin = anchor` and read back Documented; hand-read and
fetched rows read back Measured; every row carries the four provenance columns
and the closed-set attribution; a re-seed, a re-entry and a second rebuild add
no row; a row outside either declared shape refuses, naming line and field."""

from __future__ import annotations

import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from ingest.listing import SAMPLE_DIR as LISTING_SAMPLE
from ingest.parsed import PageShapeError
from ingest.sources import CHANNELS, ORIGINS, SEGMENTS, by_name
from pipeline.build import (
    ANCHOR_COLUMNS,
    ANCHORS,
    MANUAL_COLUMNS,
    MANUAL_SNAPSHOTS,
    idempotency_check,
    read_anchors,
    read_manual_snapshots,
    rebuild,
)
from pipeline.warehouse import connect
from tests import pins

PLAY = by_name("fr-digital-first-google-play-listing")


def _query(db: Path, sql: str):
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _anchor_rows() -> list[dict[str, str]]:
    with ANCHORS.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns))
        w.writeheader()
        w.writerows(rows)
    return path


def _play_capture(cache: Path, stamp: str) -> None:
    d = cache / PLAY.platform / PLAY.name / stamp.replace(":", "-")
    shutil.copytree(LISTING_SAMPLE, d)
    meta = d / "page-1.meta.json"
    meta.write_text(
        json.dumps(
            {"source_url": PLAY.page_url(1), "captured_at": stamp, "status": 200}
        )
    )
    (d / "MANIFEST.sha256").unlink()


def test_anchors_seed_nine_documented_rows_with_provenance(tmp_path):
    """Nine since the re-freeze: the brief's Opinion Assurances anchor was
    missing from the Phase 1 file (round 1: the spec says nine everywhere)."""
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "synthetic", database=db)
    assert counts["raw_platform_snapshots"] == pins.ANCHOR_ROWS
    assert counts["stg_platform_snapshots"] == pins.ANCHOR_ROWS
    rows = _query(
        db,
        "select origin, tag, profile, segment, channel, source, source_url, "
        "captured_at, run_id, seeded_from from stg_platform_snapshots",
    )
    assert len(rows) == pins.ANCHOR_ROWS
    for (
        origin,
        tag,
        _profile,
        segment,
        channel,
        source,
        url,
        at,
        run_id,
        seeded,
    ) in rows:
        assert (origin, tag) == ("anchor", "Documented")
        assert segment in SEGMENTS and channel in CHANNELS and origin in ORIGINS
        assert source and url.startswith("https://") and len(at) == 10 and run_id
        assert seeded == "PROJECT_BRIEF §6"
    profiles = {p: 0 for p in pins.ANCHOR_PROFILES}
    for (profile,) in _query(db, "select profile from stg_platform_snapshots"):
        profiles[profile] += 1
    assert profiles == pins.ANCHOR_PROFILES
    # the one anchor with no rating (the brief gives none) loads with a null
    assert _query(
        db, "select review_count from stg_platform_snapshots where rating is null"
    ) == [(534,)]


def test_anchors_seed_identically_in_every_input_but_none(tmp_path):
    seen = {}
    for rows in ("captured", "synthetic", "samples", "none"):
        db = tmp_path / f"{rows}.duckdb"
        rebuild(
            "duckdb",
            rows,
            database=db,
            cache_dir=tmp_path / "no",
            manual_file=tmp_path / "no.csv",
        )
        seen[rows] = _query(
            db,
            "select source, profile, captured_at, content_hash from "
            "raw_platform_snapshots "
            "where origin = 'anchor' order by 1, 2, 3",
        )
    assert seen["none"] == []
    assert len(seen["captured"]) == pins.ANCHOR_ROWS
    assert seen["captured"] == seen["synthetic"] == seen["samples"]


def test_manual_and_fetched_rows_read_back_as_measured(tmp_path):
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-02T10:00:00")
    manual = _write_csv(
        tmp_path / "manual.csv",
        MANUAL_COLUMNS,
        [
            {
                "source": "fr-digital-first-app-store-listing",
                "captured_at": "2026-09-02",
                "rating": "4.9",
                "review_count": "13000",
                "one_star_share": "",
                "response_rate": "",
                "response_delay_days": "",
                "read_from": "page",
            }
        ],
    )
    db = tmp_path / "w.duckdb"
    counts = rebuild(
        "duckdb", "captured", database=db, cache_dir=cache, manual_file=manual
    )
    assert counts["raw_platform_snapshots"] == pins.ANCHOR_ROWS + 2
    rows = _query(
        db,
        "select origin, tag, source, profile, segment, channel, rating, review_count, "
        "source_url, captured_at, run_id from stg_platform_snapshots "
        "where origin <> 'anchor' order by origin",
    )
    assert len(rows) == 2
    fetched, manual_row = rows
    assert fetched[:6] == (
        "fetch",
        "Measured",
        "google-play",
        "fr-digital-first",
        "digital-first",
        "invited",
    )
    assert fetched[6] == Decimal("4.123") and fetched[7] == 1234
    assert fetched[8] == PLAY.page_url(1) and fetched[9] == "2026-09-02T10:00:00"
    assert fetched[10] == f"{PLAY.platform}/{PLAY.name}/2026-09-02T10-00-00"
    assert manual_row[:6] == (
        "manual",
        "Measured",
        "app-store",
        "fr-digital-first",
        "digital-first",
        "invited",
    )
    assert manual_row[6] == Decimal("4.900") and manual_row[7] == 13000
    assert manual_row[8] == by_name("fr-digital-first-app-store-listing").listing
    assert manual_row[9] == "2026-09-02" and manual_row[10] == "manual"


def test_a_profile_capture_yields_one_snapshot_row_from_its_first_page(tmp_path):
    """The aggregate repeats on every page of a profile; if the live figure
    moves between page 1 and page 2 of one run, the capture still yields ONE
    snapshot row — page 1's, under the capture's instant — never two rows for
    one `captured_at` left to a hash tiebreak (round 1, code-reviewer)."""
    from ingest.opinion_assurances import SAMPLE_DIR as OA_SAMPLE

    oa = by_name("fr-digital-first-opinion-assurances")
    stamp = "2026-09-02T11:00:00"
    d = tmp_path / "cache" / oa.platform / oa.name / stamp.replace(":", "-")
    shutil.copytree(OA_SAMPLE, d)
    (d / "MANIFEST.sha256").unlink()
    for n in (1, 2, 3):
        (d / f"page-{n}.meta.json").write_text(
            json.dumps(
                {"source_url": oa.page_url(n), "captured_at": stamp, "status": 200}
            )
        )
    page2 = d / "page-2.html"
    moved = page2.read_text(encoding="utf-8").replace(
        '<meta itemprop="ratingValue" content="3.6">',
        '<meta itemprop="ratingValue" content="3.7">',
        1,
    )
    assert moved != page2.read_text(encoding="utf-8")
    page2.write_text(moved, encoding="utf-8")
    db = tmp_path / "w.duckdb"
    rebuild(
        "duckdb",
        "captured",
        database=db,
        cache_dir=tmp_path / "cache",
        manual_file=tmp_path / "none.csv",
    )
    rows = _query(
        db,
        "select rating, review_count, source_url from raw_platform_snapshots "
        "where origin = 'fetch'",
    )
    assert rows == [(Decimal("3.600"), 512, oa.page_url(1))]


def _manual(tmp_path: Path, name: str, rows: list[dict[str, str]]) -> Path:
    return _write_csv(tmp_path / name, MANUAL_COLUMNS, rows)


def _store_row(**over: str) -> dict[str, str]:
    row = {
        "source": "fr-digital-first-app-store-listing",
        "captured_at": "2026-09-02",
        "rating": "4.9",
        "review_count": "13000",
        "one_star_share": "",
        "response_rate": "",
        "response_delay_days": "",
        "read_from": "page",
    }
    row.update(over)
    return row


@pytest.mark.parametrize(
    ("field", "corrected"),
    [
        ("rating", "4.8"),
        ("review_count", "13001"),
        ("one_star_share", "0.1"),
        ("response_rate", "0.5"),
        ("response_delay_days", "2"),
    ],
)
def test_a_corrected_figure_for_an_entered_day_refuses_the_load(
    tmp_path, field, corrected
):
    """A2 (round 1, finding 1): a hand-read row whose key is already in the
    corpus under other figures — any of the five measures (round 2,
    functionality-tester F4) — is refused with one line naming its line and
    the fix, never tiebroken by hash order. The same figures again add
    nothing; a corrected figure on a NEW day is a new point."""
    db = tmp_path / "w.duckdb"
    first = _manual(tmp_path, "m1.csv", [_store_row()])
    rebuild(
        "duckdb", "captured", database=db, cache_dir=tmp_path / "no", manual_file=first
    )
    changed = _manual(tmp_path, "m2.csv", [_store_row(**{field: corrected})])
    with pytest.raises(
        PageShapeError, match=r"line 2: a snapshot for .*make reset"
    ) as exc:
        rebuild(
            "duckdb",
            "captured",
            database=db,
            cache_dir=tmp_path / "no",
            manual_file=changed,
        )
    assert "\n" not in str(exc.value)
    again = rebuild(
        "duckdb", "captured", database=db, cache_dir=tmp_path / "no", manual_file=first
    )
    assert again["raw_platform_snapshots"] == pins.ANCHOR_ROWS + 1
    new_day = _manual(
        tmp_path, "m3.csv", [_store_row(**{field: corrected}, captured_at="2026-09-03")]
    )
    later = rebuild(
        "duckdb",
        "captured",
        database=db,
        cache_dir=tmp_path / "no",
        manual_file=new_day,
    )
    assert later["raw_platform_snapshots"] == pins.ANCHOR_ROWS + 2


@pytest.mark.parametrize(
    ("field", "corrected"),
    [("segment", "traditional"), ("channel", "unsolicited"), ("seeded_from", "x")],
)
def test_a_corrected_attribution_for_an_entered_key_refuses_the_load(
    tmp_path, field, corrected
):
    """A3 (a): `segment`, `channel` and `seeded_from` are outside the key, so
    they are in the fingerprint — a row on an existing key with another
    attribution is a same-key pair and refuses like a corrected figure, never
    dropped by the not-exists guard (round 2, code-reviewer #4)."""
    from pipeline.build import build_derived, load_snapshots

    db = tmp_path / "w.duckdb"
    rebuild("duckdb", "synthetic", database=db)
    conn = connect("duckdb", database=db)
    try:
        row = {
            "source": "app-store",
            "profile": "fr-digital-first",
            "segment": "digital-first",
            "channel": "invited",
            "origin": "manual",
            "rating": Decimal("4.9"),
            "review_count": 13000,
            "one_star_share": None,
            "response_rate": None,
            "response_delay_days": None,
            "source_url": "https://apps.apple.com/x",
            "captured_at": "2026-09-02",
            "seeded_from": "",
        }
        load_snapshots(conn, [row], "first")
        load_snapshots(conn, [dict(row)], "again")  # the same row: nothing
        with pytest.raises(PageShapeError, match="another attribution"):
            load_snapshots(conn, [{**row, field: corrected}], "corrected")
        build_derived(conn)
        stored = conn.execute(
            "select segment, channel, seeded_from from raw_platform_snapshots "
            "where source_url = 'https://apps.apple.com/x'"
        ).fetchall()
        assert stored == [("digital-first", "invited", "")]
    finally:
        conn.close()


def test_a_respelled_figure_is_the_same_figure_not_a_correction(tmp_path):
    """`4.90` for `4.9`, `13000.0` is outside the shape but `4.900` is not:
    one figure hashes alike however it is spelled, so re-formatting the
    tracked file never refuses a rebuild; a different figure still does
    (round 2, code-reviewer #12)."""
    from pipeline.build import snapshot_hash

    first = _manual(tmp_path, "m1.csv", [_store_row(rating="4.9")])
    db = tmp_path / "w.duckdb"
    rebuild(
        "duckdb", "captured", database=db, cache_dir=tmp_path / "no", manual_file=first
    )
    respelled = _manual(
        tmp_path, "m2.csv", [_store_row(rating="4.900", response_rate="")]
    )
    counts = rebuild(
        "duckdb",
        "captured",
        database=db,
        cache_dir=tmp_path / "no",
        manual_file=respelled,
    )
    assert counts["raw_platform_snapshots"] == pins.ANCHOR_ROWS + 1
    rows = read_manual_snapshots(respelled)
    assert snapshot_hash(rows[0]) == snapshot_hash(read_manual_snapshots(first)[0])
    assert snapshot_hash(
        read_manual_snapshots(_manual(tmp_path, "m3.csv", [_store_row(rating="4.91")]))[
            0
        ]
    ) != snapshot_hash(rows[0])
    big = {
        "rating": Decimal("13000"),
        "review_count": 13000,
        "one_star_share": None,
        "response_rate": None,
        "response_delay_days": Decimal("1.50"),
    }
    assert snapshot_hash(big) == snapshot_hash(
        {**big, "rating": Decimal("13000.000"), "response_delay_days": Decimal("1.5")}
    )


def test_two_entries_for_one_day_in_one_file_refuse_naming_the_second_line(tmp_path):
    db = tmp_path / "w.duckdb"
    both = _manual(tmp_path, "m.csv", [_store_row(), _store_row(rating="4.8")])
    with pytest.raises(PageShapeError, match="line 3: a snapshot for"):
        rebuild(
            "duckdb",
            "captured",
            database=db,
            cache_dir=tmp_path / "no",
            manual_file=both,
        )


def test_a_hand_read_row_is_never_swallowed_by_an_anchor_with_its_numbers(tmp_path):
    """A2 (round 1, finding 2): a hand-read row with the same platform,
    profile, day and figures as an anchor is a row of its own — the key names
    how it came to be and where it was read — and, sharing the day, it stands
    in front of the anchor in the marts as the Measured point."""
    db = tmp_path / "w.duckdb"
    same = _manual(
        tmp_path, "m.csv", [_store_row(captured_at="2024-09-15", review_count="5000")]
    )
    counts = rebuild(
        "duckdb", "captured", database=db, cache_dir=tmp_path / "no", manual_file=same
    )
    assert counts["raw_platform_snapshots"] == pins.ANCHOR_ROWS + 1
    assert counts["stg_platform_snapshots"] == pins.ANCHOR_ROWS + 1
    rows = _query(
        db,
        "select origin, tag, source_url from stg_platform_snapshots "
        "where source = 'app-store' and captured_at = '2024-09-15' order by origin",
    )
    store = by_name("fr-digital-first-app-store-listing")
    assert rows == [
        ("anchor", "Documented", "https://apps.apple.com/"),
        ("manual", "Measured", store.listing),
    ]
    gap = _query(
        db,
        "select tag, source_url, captured_at from channel_gap "
        "where source = 'app-store' and profile = 'fr-digital-first'",
    )
    assert gap == [("Measured", store.listing, "2024-09-15")]


def test_the_snapshot_key_names_its_declaration(tmp_path):
    """A2 (a), pinned literally: the key is these five names, and two rows
    that differ in `origin` alone — an anchor and a hand entry sharing
    platform, profile, day AND address — are two rows (round 2,
    functionality-tester F3)."""
    from pipeline.build import SNAPSHOT_KEY, load_snapshots

    assert SNAPSHOT_KEY == ("source", "profile", "origin", "source_url", "captured_at")
    db = tmp_path / "w.duckdb"
    rebuild("duckdb", "synthetic", database=db)
    conn = connect("duckdb", database=db)
    try:
        (anchor,) = conn.execute(
            "select source, profile, segment, channel, rating, review_count, "
            "source_url, captured_at from raw_platform_snapshots "
            "where source = 'app-store' and origin = 'anchor'"
        ).fetchall()
        twin = {
            "source": anchor[0],
            "profile": anchor[1],
            "segment": anchor[2],
            "channel": anchor[3],
            "origin": "manual",
            "rating": anchor[4],
            "review_count": anchor[5],
            "one_star_share": None,
            "response_rate": None,
            "response_delay_days": None,
            "source_url": anchor[6],  # the very same address
            "captured_at": anchor[7],  # and the very same day
            "seeded_from": "",
        }
        load_snapshots(conn, [twin], "test")
        rows = conn.execute(
            "select origin from raw_platform_snapshots where source = 'app-store' "
            "and source_url = ? and captured_at = ? order by origin",
            [anchor[6], anchor[7]],
        ).fetchall()
        assert rows == [("anchor",), ("manual",)]
    finally:
        conn.close()


def test_the_snapshot_key_is_unique_in_raw(tmp_path):
    """A2: with anchors, a capture and a hand entry loaded twice, no two raw
    rows share (source, profile, origin, source_url, captured_at) — staging
    and the marts have nothing to tiebreak."""
    from pipeline.build import SNAPSHOT_KEY

    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-02T10:00:00")
    manual = _manual(tmp_path, "m.csv", [_store_row()])
    db = tmp_path / "w.duckdb"
    for _ in range(2):
        rebuild("duckdb", "captured", database=db, cache_dir=cache, manual_file=manual)
    cols = ", ".join(SNAPSHOT_KEY)
    dupes = _query(
        db,
        f"select {cols}, count(*) from raw_platform_snapshots "
        f"group by {cols} having count(*) > 1",
    )
    assert dupes == []
    assert _query(db, "select count(*) from stg_platform_snapshots") == _query(
        db, "select count(*) from raw_platform_snapshots"
    )


def test_reseeding_reentering_and_rebuilding_add_no_snapshot_row(tmp_path):
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-02T10:00:00")
    manual = MANUAL_SNAPSHOTS if MANUAL_SNAPSHOTS.is_file() else tmp_path / "none.csv"
    ok, first, second = idempotency_check(
        "duckdb", "captured", cache_dir=cache, manual_file=manual
    )
    assert ok and first == second
    expected = pins.ANCHOR_ROWS + 1 + len(read_manual_snapshots(manual))
    assert first["raw_platform_snapshots"] == expected
    # a second capture of the unchanged listing at a later time IS a new point
    # (captured_at is in the key); a second load of the same capture is not
    _play_capture(cache, "2026-09-09T10:00:00")
    db = tmp_path / "w.duckdb"
    for _ in range(2):
        counts = rebuild(
            "duckdb", "captured", database=db, cache_dir=cache, manual_file=manual
        )
    assert counts["raw_platform_snapshots"] == expected + 1


def test_the_only_tracked_files_under_data_are_hand_read_snapshot_csvs():
    """`data/` is gitignored but `data/snapshots/` is re-included whole, and
    Phase 4's weekly commit will `git add` it: every tracked path under
    `data/` must be a `data/snapshots/*.csv` that parses under the declared
    eight columns — never a capture, a corpus extract or a file carrying
    reviewer text (round 2, security-reviewer #5)."""
    import subprocess

    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "data"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8", errors="replace")
    paths = [p for p in tracked.split("\0") if p]
    assert paths, "the hand-read file is tracked"
    for rel in paths:
        parts = Path(rel).parts
        assert parts[:2] == ("data", "snapshots") and len(parts) == 3, rel
        assert rel.endswith(".csv"), rel
        rows = read_manual_snapshots(root / rel)  # the declared shape, or a refusal
        assert all(r["origin"] == "manual" for r in rows), rel


def test_the_tracked_manual_file_loads_and_names_no_address():
    rows = read_manual_snapshots()
    assert rows and all(r["origin"] == "manual" for r in rows)
    from ingest.sources import BRAND_TOKENS

    text = MANUAL_SNAPSHOTS.read_text(encoding="utf-8")
    assert "http" not in text
    assert not any(token in text.lower() for token in BRAND_TOKENS)
    assert text.splitlines()[0] == ",".join(MANUAL_COLUMNS)


def test_manual_file_columns_are_exactly_the_declared_eight(tmp_path):
    assert len(MANUAL_COLUMNS) == 8
    bad = _write_csv(tmp_path / "m.csv", MANUAL_COLUMNS + ("note",), [])
    with pytest.raises(PageShapeError, match="columns must be exactly"):
        read_manual_snapshots(bad)
    fewer = _write_csv(tmp_path / "f.csv", MANUAL_COLUMNS[:-1], [])
    with pytest.raises(PageShapeError, match="columns must be exactly"):
        read_manual_snapshots(fewer)
    assert read_manual_snapshots(tmp_path / "absent.csv") == []


@pytest.mark.parametrize(
    ("field", "value", "why"),
    [
        ("source", "nobody", "not a declared source"),
        ("source", "fr-digital-first-google-play-listing", "is fetchable"),
        ("captured_at", "yesterday", "not YYYY-MM-DD"),
        ("captured_at", "2026-02-30", "not a real day"),
        ("rating", "5.5", "outside the range"),
        ("rating", "four", "not a number"),
        ("review_count", "-1", "not a non-negative integer"),
        ("review_count", "", "not a non-negative integer"),
        ("review_count", "9" * 5000, "not a non-negative integer"),
        ("review_count", "2147483648", "not a non-negative integer"),  # column ceiling
        ("rating", "4." + "9" * 5000, "not a number"),
        ("one_star_share", "1.5", "outside the range"),
        ("response_rate", "82", "outside the range"),
        (
            "response_delay_days",
            "-1",
            "not a number",
        ),  # digits only: a sign is outside the shape
        ("read_from", "memory", "must be the word 'page'"),
    ],
)
def test_manual_row_outside_the_declared_shape_is_refused(tmp_path, field, value, why):
    row = {
        "source": "fr-digital-first-app-store-listing",
        "captured_at": "2026-09-02",
        "rating": "4.9",
        "review_count": "13000",
        "one_star_share": "",
        "response_rate": "",
        "response_delay_days": "",
        "read_from": "page",
    }
    row[field] = value
    path = _write_csv(tmp_path / "m.csv", MANUAL_COLUMNS, [row])
    with pytest.raises(PageShapeError, match=f"line 2: field '{field}'.*{why}"):
        read_manual_snapshots(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rating", "6.0"),
        ("review_count", "-1"),
        ("segment", "invited"),
        ("channel", "digital-first"),
        ("captured_at", "2025-01"),
        ("source_url", "trustpilot.com"),
        ("profile", "Peer One"),
        ("seeded_from", ""),
    ],
)
def test_anchor_row_outside_the_declared_shape_is_refused(tmp_path, field, value):
    rows = _anchor_rows()
    rows[0][field] = value
    path = _write_csv(tmp_path / "anchors.csv", ANCHOR_COLUMNS, rows)
    with pytest.raises(PageShapeError, match=f"line 2: field '{field}'"):
        read_anchors(path)
    missing = _write_csv(tmp_path / "short.csv", ANCHOR_COLUMNS[:-1], [])
    with pytest.raises(PageShapeError, match="columns must be exactly"):
        read_anchors(missing)
