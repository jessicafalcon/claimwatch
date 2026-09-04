"""The fetched rating series' tracked path (spec Phase 4, done-when 1, 2, 6).

`make record-snapshots` harvests a capture's snapshot figures into the tracked
`data/snapshots/fetched_snapshots.csv` — numbers only, idempotently — and
`rebuild ROWS=captured` loads them as `origin=fetch` Measured points. A fetched
row and its live-cache twin share the snapshot key, so the two are one row and
never double-count; the file is the durable, offline record the weekly cron
appends to."""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

import pytest

from ingest.opinion_assurances import SAMPLE_DIR as OA_SAMPLE
from ingest.parsed import PageShapeError
from ingest.sources import BRAND_TOKENS, SOURCES, by_name
from pipeline.build import (
    FETCHED_COLUMNS,
    idempotency_check,
    read_fetched_snapshots,
    rebuild,
    record_snapshots,
)
from pipeline.warehouse import ROOT, database_for
from tests.test_snapshots import PLAY, _play_capture, _query, _write_csv

OA = by_name("fr-digital-first-opinion-assurances")
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\Z")
_NUMBER = re.compile(r"\A[0-9]*\.?[0-9]*\Z")  # a figure or empty; no letters


def _row(source: str, stamp: str, **figs: str) -> dict[str, str]:
    row = {c: "" for c in FETCHED_COLUMNS}
    row["source"] = source
    row["captured_at"] = stamp
    row.update(figs)
    return row


def _oa_capture(cache: Path, stamp: str) -> None:
    """An Opinion Assurances capture — reviews with bodies and a brand-carrying
    page address, so a harvest that carried either would show it."""
    d = cache / OA.platform / OA.name / stamp.replace(":", "-")
    shutil.copytree(OA_SAMPLE, d)
    (d / "MANIFEST.sha256").unlink()
    for n in (1, 2, 3):
        (d / f"page-{n}.meta.json").write_text(
            json.dumps(
                {"source_url": OA.page_url(n), "captured_at": stamp, "status": 200}
            )
        )


def test_absent_fetched_file_is_zero_rows(tmp_path):
    assert read_fetched_snapshots(tmp_path / "nope.csv") == []


def test_fetched_snapshots_load_as_fetch_origin(tmp_path):
    fetched = _write_csv(
        tmp_path / "f.csv",
        FETCHED_COLUMNS,
        [_row(PLAY.name, "2026-09-10T03:00:00", rating="4.5", review_count="800")],
    )
    db = database_for("captured", tmp_path)
    rebuild(
        "duckdb",
        "captured",
        root=tmp_path,
        cache_dir=tmp_path / "nocache",
        manual_file=tmp_path / "nomanual.csv",
        fetched_file=fetched,
    )
    rows = _query(
        db,
        "select origin, tag, source, source_url, captured_at "
        "from stg_platform_snapshots where origin = 'fetch'",
    )
    assert rows == [
        ("fetch", "Measured", PLAY.platform, PLAY.pages[0], "2026-09-10T03:00:00")
    ]


def test_recording_twice_adds_no_row(tmp_path):
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-10T03:00:00")
    fetched = tmp_path / "f.csv"
    assert record_snapshots(fetched, cache_root=cache) == 1
    body = fetched.read_text(encoding="utf-8")
    assert record_snapshots(fetched, cache_root=cache) == 0
    assert fetched.read_text(encoding="utf-8") == body  # byte-identical, empty diff


def test_recorded_cells_are_numbers_and_slugs_only(tmp_path):
    """Invariant: the tracked file carries only source slugs, capture instants
    and the five figures — never a review body, an address or a brand token."""
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-10T03:00:00")
    _oa_capture(cache, "2026-09-10T04:00:00")
    fetched = tmp_path / "f.csv"
    record_snapshots(fetched, cache_root=cache)
    text = fetched.read_text(encoding="utf-8")
    assert "http" not in text  # no address
    assert not any(tok in text for tok in BRAND_TOKENS)  # no brand
    assert read_fetched_snapshots(fetched)  # and it loads cleanly
    declared = {s.name for s in SOURCES}
    with fetched.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            assert r["source"] in declared
            assert _INSTANT.fullmatch(r["captured_at"])
            for f in FETCHED_COLUMNS[2:]:
                assert _NUMBER.fullmatch(r[f]), (f, r[f])


def test_a_fetched_row_and_its_cache_twin_are_one_row(tmp_path):
    """The double read is a no-op: a rebuild that reads BOTH the live capture
    and the tracked file it was harvested into holds the same snapshot count as
    one that reads the cache alone (pinned decision 3)."""
    cache = tmp_path / "cache"
    _play_capture(cache, "2026-09-10T03:00:00")
    fetched = tmp_path / "f.csv"
    record_snapshots(fetched, cache_root=cache)
    empty = _write_csv(tmp_path / "empty.csv", FETCHED_COLUMNS, [])
    manual = tmp_path / "m.csv"
    both_root, only_root = tmp_path / "both", tmp_path / "only"
    both_root.mkdir()
    only_root.mkdir()
    both = rebuild(
        "duckdb",
        "captured",
        root=both_root,
        cache_dir=cache,
        manual_file=manual,
        fetched_file=fetched,
    )
    only = rebuild(
        "duckdb",
        "captured",
        root=only_root,
        cache_dir=cache,
        manual_file=manual,
        fetched_file=empty,
    )
    assert both["raw_platform_snapshots"] == only["raw_platform_snapshots"]


def test_an_opinion_assurances_row_and_its_cache_twin_are_one_row(tmp_path):
    """The twin collapse over the multi-page profile source, not only the
    single-page listing: page 1 carries the aggregate, so `pages[0]` is the
    snapshot's address and the fetched row and its live-cache twin are one row
    for a 14-page source too (the coupling code-reviewer flagged)."""
    cache = tmp_path / "cache"
    _oa_capture(cache, "2026-09-10T05:00:00")
    fetched = tmp_path / "f.csv"
    record_snapshots(fetched, cache_root=cache)
    empty = _write_csv(tmp_path / "empty.csv", FETCHED_COLUMNS, [])
    manual = tmp_path / "m.csv"
    both_root, only_root = tmp_path / "both", tmp_path / "only"
    both_root.mkdir()
    only_root.mkdir()
    both = rebuild(
        "duckdb",
        "captured",
        root=both_root,
        cache_dir=cache,
        manual_file=manual,
        fetched_file=fetched,
    )
    only = rebuild(
        "duckdb",
        "captured",
        root=only_root,
        cache_dir=cache,
        manual_file=manual,
        fetched_file=empty,
    )
    assert both["raw_platform_snapshots"] == only["raw_platform_snapshots"]


def test_the_tracked_fetched_series_rebuilds_identically(tmp_path):
    fetched = _write_csv(
        tmp_path / "f.csv",
        FETCHED_COLUMNS,
        [_row(PLAY.name, "2026-09-10T03:00:00", rating="4.5", review_count="800")],
    )
    ok, first, second = idempotency_check(
        "duckdb",
        "captured",
        cache_dir=tmp_path / "nocache",
        manual_file=tmp_path / "m.csv",
        fetched_file=fetched,
    )
    assert ok
    assert first["raw_platform_snapshots"] == second["raw_platform_snapshots"]


@pytest.mark.parametrize(
    "bad",
    [
        "fr-digital-first-app-store-listing",  # no parser
        "fr-digital-first-trustpilot-reviews",  # a parser, but not fetchable
        "not-a-source",
    ],
)
def test_a_fetched_row_names_a_fetchable_parsed_source(tmp_path, bad):
    f = _write_csv(
        tmp_path / "f.csv",
        FETCHED_COLUMNS,
        [_row(bad, "2026-09-10T03:00:00", rating="4.5", review_count="800")],
    )
    with pytest.raises(PageShapeError):
        read_fetched_snapshots(f)


def test_the_tracked_fetched_file_loads_and_names_no_address():
    """The committed data/snapshots/fetched_snapshots.csv always parses and
    carries no address, no brand and no review body — whatever the cron has
    appended. Reads the real path (the suite isolates the default elsewhere)."""
    real = ROOT / "data" / "snapshots" / "fetched_snapshots.csv"
    text = real.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(FETCHED_COLUMNS)
    assert "http" not in text
    assert not any(tok in text for tok in BRAND_TOKENS)
    read_fetched_snapshots(real)  # loads with no refusal, whatever its rows


def test_a_fetched_captured_at_must_be_an_instant(tmp_path):
    f = _write_csv(
        tmp_path / "f.csv",
        FETCHED_COLUMNS,
        [_row(PLAY.name, "2026-09-10", rating="4.5", review_count="800")],
    )
    with pytest.raises(PageShapeError):
        read_fetched_snapshots(f)


@pytest.mark.parametrize(
    "bad_instant",
    [
        "2026-9-10T3:0:0",  # not zero-padded — strptime accepts it, the regex must not
        "2026-09-10T03:00:00Z",  # a trailing zone
        "2026-09-10T03:00:00+00:00",  # an offset
        "2026-09-10 03:00:00",  # a space, not a T
    ],
)
def test_a_non_canonical_instant_is_refused(tmp_path, bad_instant):
    """The fetched `captured_at` must be byte-equal to the live-cache meta stamp
    for the snapshot key to match and the double read to stay a no-op, so the
    canonical zero-padded `YYYY-MM-DDTHH:MM:SS` is enforced by the `_INSTANT`
    regex — not left to `strptime`, which accepts `2026-9-10T3:0:0`."""
    f = _write_csv(
        tmp_path / "f.csv",
        FETCHED_COLUMNS,
        [_row(PLAY.name, bad_instant, rating="4.5", review_count="800")],
    )
    with pytest.raises(PageShapeError):
        read_fetched_snapshots(f)
