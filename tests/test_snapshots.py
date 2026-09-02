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


def test_anchors_seed_eight_documented_rows_with_provenance(tmp_path):
    """Nine, since the re-freeze (the brief's Opinion Assurances anchor was
    missing from the Phase 1 file); the spec's 'eight' is corrected in the
    Delivered paragraph."""
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


def test_the_tracked_manual_file_loads_and_names_no_address():
    rows = read_manual_snapshots()
    assert rows and all(r["origin"] == "manual" for r in rows)
    text = MANUAL_SNAPSHOTS.read_text(encoding="utf-8")
    assert "http" not in text and "alan" not in text.lower()
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
