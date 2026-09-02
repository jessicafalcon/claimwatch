"""Captures -> raw -> staging -> the metric, through Phase 1's unchanged load
guard (spec Phase 2, invariants 3 and 4; done-when 3, 4 and 5). Every test
builds into a temp database from the frozen sample or from captures assembled
in a temp directory; `data/` is never touched."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from ingest.app_store import FeedShapeError, capture_pages, read_captures
from pipeline.build import idempotency_check, rebuild
from pipeline.metrics import reviews_per_month
from pipeline.warehouse import connect
from tests import pins

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"


def _capture(root: Path, capture_id: str, captured_at: str, edit=None) -> Path:
    """Copy the sample into `root/<capture_id>` with its meta re-stamped; `edit`
    may mutate page 1's document before it is written."""
    d = root / capture_id
    shutil.copytree(SAMPLE, d)
    for meta in d.glob("page-*.meta.json"):
        m = json.loads(meta.read_text())
        m["captured_at"] = captured_at
        meta.write_text(json.dumps(m))
    if edit is not None:
        page = d / "page-1.json"
        doc = json.loads(page.read_text(encoding="utf-8"))
        edit(doc)
        page.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return d


def _query(db: Path, sql: str):
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_rebuild_from_sample_matches_pins(tmp_path):
    counts = rebuild("duckdb", "app-store", database=tmp_path / "w.duckdb")
    assert counts == {
        "raw_reviews": pins.APP_STORE_SAMPLE_RAW_ROWS,
        "stg_reviews": pins.APP_STORE_SAMPLE_STG_ROWS,
    }
    rows = _query(
        tmp_path / "w.duckdb",
        "select distinct source, run_id, captured_at from raw_reviews",
    )
    assert rows == [
        ("app-store", "app-store:app-store", pins.APP_STORE_SAMPLE_CAPTURED_AT)
    ]


def test_reviews_per_month_matches_pins(tmp_path):
    db = tmp_path / "w.duckdb"
    rebuild("duckdb", "app-store", database=db)
    conn = connect("duckdb", database=db)
    try:
        assert tuple(reviews_per_month(conn)) == pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH
    finally:
        conn.close()


def test_pages_beyond_nine_are_read_in_numeric_order(tmp_path):
    """A ten-page capture is read page-1 .. page-10, not page-1, page-10,
    page-2 (string order); the row's `source_url` follows the same order."""
    d = tmp_path / "ten"
    d.mkdir()
    page = (SAMPLE / "page-2.json").read_bytes()  # three well-formed items
    for n in range(1, 11):
        (d / f"page-{n}.json").write_bytes(page)
        meta = {
            "source_url": f"https://itunes.apple.com/fr/rss/x/page={n}/json",
            "captured_at": pins.APP_STORE_SAMPLE_CAPTURED_AT,
            "status": 200,
        }
        (d / f"page-{n}.meta.json").write_text(json.dumps(meta))
    expected = [f"page-{n}.json" for n in range(1, 11)]
    assert [p.name for p in capture_pages(d)] == expected
    ((_, rows),) = read_captures(d)
    seen = [int(r["source_url"].rsplit("page=", 1)[1].split("/")[0]) for r in rows]
    assert seen == sorted(seen) and seen[-1] == 10


def test_read_captures_orders_captures_then_pages_then_items():
    ((capture_id, rows),) = read_captures(SAMPLE)
    assert capture_id == "app-store"
    assert len(rows) == sum(pins.APP_STORE_SAMPLE_ITEMS_ON_PAGES)  # before dedup
    assert rows[0]["external_id"] == pins.APP_STORE_SAMPLE_FIRST_ROW["external_id"]
    assert [r["source_url"][-6] for r in rows] == ["1"] * 6 + ["2"] * 3
    assert read_captures(Path("/nonexistent/cache")) == []


def test_second_rebuild_from_captures_adds_no_rows():
    ok, first, second = idempotency_check("duckdb", "app-store")
    assert ok and first == second
    assert first["raw_reviews"] == pins.APP_STORE_SAMPLE_RAW_ROWS


def test_second_capture_of_unchanged_pages_adds_no_rows(tmp_path):
    """A re-scrape a week later, nothing edited: raw keeps the first capture's
    rows and gains none; staging is unchanged."""
    cache = tmp_path / "cache"
    _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    _capture(cache, "2026-09-08T08-00-00", "2026-09-08T08:00:00")
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "cache", database=db, cache_dir=cache)
    assert counts == {
        "raw_reviews": pins.APP_STORE_SAMPLE_RAW_ROWS,
        "stg_reviews": pins.APP_STORE_SAMPLE_STG_ROWS,
    }
    assert _query(db, "select distinct captured_at from raw_reviews") == [
        ("2026-09-01T08:00:00",)
    ]
    assert _query(db, "select distinct run_id from raw_reviews") == [
        ("app-store:2026-09-01T08-00-00",)
    ]


def test_edited_review_in_a_later_capture_appends_one_row(tmp_path):
    cache = tmp_path / "cache"
    _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")

    def edit(doc):
        doc["feed"]["entry"][0]["im:rating"]["label"] = "5"

    _capture(cache, "2026-09-08T08-00-00", "2026-09-08T08:00:00", edit=edit)
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "cache", database=db, cache_dir=cache)
    assert counts == {
        "raw_reviews": pins.APP_STORE_SAMPLE_RAW_ROWS + 1,
        "stg_reviews": pins.APP_STORE_SAMPLE_STG_ROWS,
    }
    ext = pins.APP_STORE_SAMPLE_FIRST_ROW["external_id"]
    assert _query(
        db, f"select rating, captured_at from stg_reviews where external_id = '{ext}'"
    ) == [(5, "2026-09-08T08:00:00")]


def test_reviews_per_month_is_stable_across_rebuilds(tmp_path):
    db = tmp_path / "w.duckdb"
    seen = []
    for run_id in ("run-a", "run-b", "run-c"):
        rebuild("duckdb", "app-store", database=db, run_id=run_id)
        conn = connect("duckdb", database=db)
        try:
            seen.append(reviews_per_month(conn))
        finally:
            conn.close()
    assert seen[0] == seen[1] == seen[2]
    assert tuple(seen[0]) == pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH


def test_rebuild_from_captures_is_byte_stable_under_a_moving_clock(
    tmp_path, monkeypatch
):
    """Two fresh rebuilds from the same captures, with every clock the parser
    could reach poisoned, produce identical raw rows — provenance included."""
    import ingest.app_store as parser

    class NoClock(parser.datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - reaching here is the failure
            raise AssertionError("a clock was read on the data path")

        utcnow = today = now

    monkeypatch.setattr(parser, "datetime", NoClock)
    rows = []
    for name in ("a", "b"):
        db = tmp_path / f"{name}.duckdb"
        rebuild("duckdb", "app-store", database=db)
        rows.append(
            _query(db, "select * from raw_reviews order by external_id, content_hash")
        )
    assert rows[0] == rows[1]
    assert len(rows[0]) == pins.APP_STORE_SAMPLE_RAW_ROWS


def test_refused_page_loads_nothing_from_the_capture(tmp_path):
    """The page is the unit and the capture is parsed before it is loaded: one
    bad item on page 2 means zero rows from that capture, not page 1's rows."""
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    page2 = d / "page-2.json"
    doc = json.loads(page2.read_text(encoding="utf-8"))
    bad = copy.deepcopy(doc)
    del bad["feed"]["entry"][1]["im:rating"]
    page2.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    db = tmp_path / "w.duckdb"
    with pytest.raises(FeedShapeError, match="'im:rating' is missing") as exc:
        rebuild("duckdb", "cache", database=db, cache_dir=cache)
    assert str(exc.value).startswith("capture ") and "2026-09-0" in str(exc.value)
    assert "\n" not in str(exc.value)
    assert _query(db, "select count(*) from raw_reviews") == [(0,)]


def test_missing_or_malformed_meta_is_refused(tmp_path):
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    (d / "page-1.meta.json").write_text('{"source_url": "x"}')
    with pytest.raises(FeedShapeError, match="meta must have exactly"):
        read_captures(cache)
    (d / "page-1.meta.json").unlink()
    with pytest.raises(FeedShapeError, match="meta is missing"):
        read_captures(cache)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("captured_at", ""),
        ("captured_at", "yesterday"),
        ("captured_at", "2026-09-01 08:00:00"),
        (
            "captured_at",
            "2026-9-1T8:0:0",
        ),  # parses, but not the canonical form we write
        ("captured_at", "2025-13-40T00:00:00"),
        ("captured_at", 20260901),
        ("source_url", ""),
        ("source_url", "http://itunes.apple.com/fr/rss/x/page=1/json"),
        ("source_url", "https://example.com/fr/rss/x/page=1/json"),
        ("source_url", 5),
        ("status", 500),
        ("status", "200"),
        ("status", True),
    ],
)
def test_meta_value_outside_the_declared_shape_refuses_the_capture(
    tmp_path, field, value
):
    """Fix amendment A4: the row's own provenance is parsed as strictly as the
    review's date; nothing loads with an empty or nonsense `captured_at`."""
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    meta_path = d / "page-1.meta.json"
    meta = json.loads(meta_path.read_text())
    meta[field] = value
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(FeedShapeError, match=f"field '{field}'"):
        read_captures(cache)
    db = tmp_path / "w.duckdb"
    with pytest.raises(FeedShapeError):
        rebuild("duckdb", "cache", database=db, cache_dir=cache)
    assert _query(db, "select count(*) from raw_reviews") == [(0,)]


def test_meta_with_an_extra_key_is_refused(tmp_path):
    """Exactly the three fields: a fourth refuses the capture (a superset check
    would let an unknown field ride along unexamined)."""
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    meta_path = d / "page-1.meta.json"
    meta = json.loads(meta_path.read_text())
    meta["extra"] = 1
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(FeedShapeError, match="meta must have exactly"):
        read_captures(cache)


def test_zero_captures_is_zero_rows_not_an_error(tmp_path):
    counts = rebuild(
        "duckdb", "cache", database=tmp_path / "w.duckdb", cache_dir=tmp_path / "no"
    )
    assert counts == {"raw_reviews": 0, "stg_reviews": 0}
