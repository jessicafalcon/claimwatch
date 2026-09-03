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

from ingest.captures import capture_pages, read_captures
from ingest.parsed import PageShapeError
from ingest.sources import SOURCES, by_name, sample_source
from pipeline.build import idempotency_check, rebuild
from pipeline.metrics import reviews_per_month
from pipeline.warehouse import connect
from tests import pins

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
FEED = by_name("fr-digital-first")  # the declared feed source; captures live under it
FEED_DIR = Path(FEED.platform) / FEED.name
SAMPLE_SRC = sample_source("app_store")


def _capture(root: Path, capture_id: str, captured_at: str, edit=None) -> Path:
    """Copy the sample into `root/<platform>/<source>/<capture_id>` with its meta
    re-stamped; `edit` may mutate page 1's document before it is written."""
    d = root / FEED_DIR / capture_id
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
    counts = rebuild("duckdb", "samples", database=tmp_path / "w.duckdb")
    assert counts["raw_reviews"] == pins.SAMPLES_RAW_REVIEWS
    assert (
        counts["stg_reviews"]
        == pins.APP_STORE_SAMPLE_STG_ROWS + pins.OA_SAMPLE_STG_ROWS
    )
    rows = _query(
        tmp_path / "w.duckdb",
        "select distinct source, run_id, captured_at from raw_reviews order by source",
    )
    assert rows == [
        ("app-store", "sample:app-store", pins.APP_STORE_SAMPLE_CAPTURED_AT),
        ("opinion-assurances", "sample:opinion-assurances", pins.OA_SAMPLE_CAPTURED_AT),
    ]


def test_samples_load_every_frozen_sample_through_its_parser(tmp_path):
    """Phase 3a, invariant 7: every declared parser has a frozen sample and it
    loads under the sample declaration — a parser with no sample is a failure,
    not a skip; the counts are pinned."""
    from ingest.captures import parser_module
    from ingest.sources import PARSERS

    for parser in PARSERS:
        mod = parser_module(parser)
        assert mod.SAMPLE_DIR.is_dir(), parser
        ((capture_id, parsed),) = read_captures(mod.SAMPLE_DIR, sample_source(parser))
        assert capture_id == mod.SAMPLE_DIR.name
        assert parsed.reviews or parsed.snapshots, parser
    counts = rebuild("duckdb", "samples", database=tmp_path / "w.duckdb")
    assert counts["raw_reviews"] == pins.SAMPLES_RAW_REVIEWS
    assert counts["raw_platform_snapshots"] == pins.SAMPLES_RAW_SNAPSHOTS
    months = _query(
        tmp_path / "w.duckdb",
        "select source, substr(review_date, 1, 7), count(*) from stg_reviews "
        "group by 1, 2 order by 1, 2",
    )
    assert tuple(months) == (
        pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH + pins.OA_SAMPLE_REVIEWS_PER_MONTH
    )


def test_every_row_carries_its_declarations_attribution_not_the_modules():
    """Invariant 3: a parser writes `source`, `profile`, `segment` and
    `channel` from the declaration it is handed, never from its own
    `SAMPLE_*` constants — each frozen sample is read under a twin
    declaration whose every attribution value differs from the module's, and
    every row carries the twin's (round 3, functionality-tester F3)."""
    from ingest.captures import parser_module
    from ingest.sources import PARSERS, SAMPLE, Source

    for parser in PARSERS:
        mod = parser_module(parser)
        twin = Source(
            name=SAMPLE,
            platform="twin-platform",
            host=mod.SAMPLE_HOST,
            parser=parser,
            pages=(),
            profile="twin-profile",
            segment="traditional",
            channel="unsolicited",
            listing="",
            fetchable=False,
            declared_on="2026-09-01",
            terms="a frozen sample read under a twin declaration",
        )
        assert twin.platform != mod.SAMPLE_PLATFORM
        ((_, parsed),) = read_captures(mod.SAMPLE_DIR, twin)
        assert parsed.reviews or parsed.snapshots, parser
        for row in parsed.reviews:
            assert row["source"] == "twin-platform", parser
        for row in parsed.snapshots:
            assert row["source"] == "twin-platform", parser
            assert row["profile"] == "twin-profile", parser
            assert row["segment"] == "traditional", parser
            assert row["channel"] == "unsolicited", parser


def test_reviews_per_month_matches_pins(tmp_path):
    db = tmp_path / "w.duckdb"
    rebuild("duckdb", "samples", database=db)
    conn = connect("duckdb", database=db)
    try:
        assert tuple(reviews_per_month(conn)) == (
            pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH + pins.OA_SAMPLE_REVIEWS_PER_MONTH
        )
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
    assert [p.name for p in capture_pages(d, "json")] == expected
    ((_, parsed),) = read_captures(d, SAMPLE_SRC)
    rows = parsed.reviews
    seen = [int(r["source_url"].rsplit("page=", 1)[1].split("/")[0]) for r in rows]
    assert seen == sorted(seen) and seen[-1] == 10


def test_read_captures_orders_captures_then_pages_then_items():
    ((capture_id, parsed),) = read_captures(SAMPLE, SAMPLE_SRC)
    rows = parsed.reviews
    assert capture_id == "app-store" and parsed.snapshots == []
    assert len(rows) == sum(pins.APP_STORE_SAMPLE_ITEMS_ON_PAGES)  # before dedup
    assert rows[0]["external_id"] == pins.APP_STORE_SAMPLE_FIRST_ROW["external_id"]
    assert [r["source_url"][-6] for r in rows] == ["1"] * 6 + ["2"] * 3
    assert read_captures(Path("/nonexistent/cache"), SAMPLE_SRC) == []


def test_second_rebuild_from_captures_adds_no_rows():
    ok, first, second = idempotency_check("duckdb", "samples")
    assert ok and first == second
    assert first["raw_reviews"] == pins.SAMPLES_RAW_REVIEWS


def test_second_capture_of_unchanged_pages_adds_no_rows(tmp_path):
    """A re-scrape a week later, nothing edited: raw keeps the first capture's
    rows and gains none; staging is unchanged."""
    cache = tmp_path / "cache"
    _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    _capture(cache, "2026-09-08T08-00-00", "2026-09-08T08:00:00")
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "captured", database=db, cache_dir=cache)
    assert counts["raw_reviews"] == pins.APP_STORE_SAMPLE_RAW_ROWS
    assert counts["stg_reviews"] == pins.APP_STORE_SAMPLE_STG_ROWS
    assert _query(db, "select distinct captured_at from raw_reviews") == [
        ("2026-09-01T08:00:00",)
    ]
    assert _query(db, "select distinct run_id from raw_reviews") == [
        (f"{FEED.platform}/{FEED.name}/2026-09-01T08-00-00",)
    ]


def test_edited_review_in_a_later_capture_appends_one_row(tmp_path):
    cache = tmp_path / "cache"
    _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")

    def edit(doc):
        doc["feed"]["entry"][0]["im:rating"]["label"] = "5"

    _capture(cache, "2026-09-08T08-00-00", "2026-09-08T08:00:00", edit=edit)
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "captured", database=db, cache_dir=cache)
    assert counts["raw_reviews"] == pins.APP_STORE_SAMPLE_RAW_ROWS + 1
    assert counts["stg_reviews"] == pins.APP_STORE_SAMPLE_STG_ROWS
    ext = pins.APP_STORE_SAMPLE_FIRST_ROW["external_id"]
    assert _query(
        db, f"select rating, captured_at from stg_reviews where external_id = '{ext}'"
    ) == [(5, "2026-09-08T08:00:00")]


def test_reviews_per_month_is_stable_across_rebuilds(tmp_path):
    db = tmp_path / "w.duckdb"
    seen = []
    for run_id in ("run-a", "run-b", "run-c"):
        rebuild("duckdb", "samples", database=db, run_id=run_id)
        conn = connect("duckdb", database=db)
        try:
            seen.append(reviews_per_month(conn))
        finally:
            conn.close()
    assert seen[0] == seen[1] == seen[2]
    assert tuple(seen[0]) == (
        pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH + pins.OA_SAMPLE_REVIEWS_PER_MONTH
    )


def test_rebuild_from_captures_is_byte_stable_under_a_moving_clock(
    tmp_path, monkeypatch
):
    """Two fresh rebuilds from the same captures, with every clock the parser
    could reach poisoned, produce identical raw rows — provenance included."""
    import ingest.app_store as parser
    import ingest.captures as captures

    class NoClock(parser.datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - reaching here is the failure
            raise AssertionError("a clock was read on the data path")

        utcnow = today = now

    monkeypatch.setattr(parser, "datetime", NoClock)
    monkeypatch.setattr(captures, "datetime", NoClock)
    rows = []
    for name in ("a", "b"):
        db = tmp_path / f"{name}.duckdb"
        rebuild("duckdb", "samples", database=db)
        rows.append(
            _query(db, "select * from raw_reviews order by external_id, content_hash")
        )
    assert rows[0] == rows[1]
    assert len(rows[0]) == pins.SAMPLES_RAW_REVIEWS


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
    with pytest.raises(PageShapeError, match="'im:rating' is missing") as exc:
        rebuild("duckdb", "captured", database=db, cache_dir=cache)
    assert str(exc.value).startswith("capture ") and "2026-09-0" in str(exc.value)
    assert "\n" not in str(exc.value)
    assert _query(db, "select count(*) from raw_reviews") == [(0,)]


def test_missing_or_malformed_meta_is_refused(tmp_path):
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    (d / "page-1.meta.json").write_text('{"source_url": "x"}')
    with pytest.raises(PageShapeError, match="meta must have exactly"):
        read_captures(cache / FEED_DIR, FEED)
    (d / "page-1.meta.json").unlink()
    with pytest.raises(PageShapeError, match="meta is missing"):
        read_captures(cache / FEED_DIR, FEED)


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
    with pytest.raises(PageShapeError, match=f"field '{field}'"):
        read_captures(cache / FEED_DIR, FEED)
    db = tmp_path / "w.duckdb"
    with pytest.raises(PageShapeError):
        rebuild("duckdb", "captured", database=db, cache_dir=cache)
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
    with pytest.raises(PageShapeError, match="meta must have exactly"):
        read_captures(cache / FEED_DIR, FEED)


def test_zero_captures_is_zero_rows_not_an_error(tmp_path):
    counts = rebuild(
        "duckdb", "captured", database=tmp_path / "w.duckdb", cache_dir=tmp_path / "no"
    )
    assert counts["raw_reviews"] == 0 and counts["stg_reviews"] == 0


def test_meta_is_validated_against_the_sources_declared_host(tmp_path, monkeypatch):
    """Phase 3a, invariant 3: the host check is the declaration's, not the
    fetch-time allowlist. A meta on another allowed host refuses; shrinking the
    allowlist to nothing does not unload the declared source's capture."""
    import ingest.politeness as politeness

    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    meta_path = d / "page-1.meta.json"
    meta = json.loads(meta_path.read_text())
    meta["source_url"] = (
        "https://play.google.com/fr/rss/x/page=1/json"  # allowed, not ours
    )
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(PageShapeError, match="field 'source_url'.*itunes.apple.com"):
        read_captures(cache / FEED_DIR, FEED)
    meta["source_url"] = FEED.page_url(1)
    meta_path.write_text(json.dumps(meta))
    monkeypatch.setattr(politeness, "ALLOWED_HOSTS", ())
    ((_, parsed),) = read_captures(cache / FEED_DIR, FEED)
    assert len(parsed.reviews) == sum(pins.APP_STORE_SAMPLE_ITEMS_ON_PAGES)


def test_every_captured_review_joins_exactly_one_declared_page(tmp_path):
    """Phase 3a, invariant 4: `raw_source_pages` holds every address a declared
    source can produce, so each captured review joins exactly one row by exact
    `source_url`; a review from an address outside the declaration is
    unattributed, and this test would count it."""
    cache = tmp_path / "cache"
    d = _capture(cache, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    for n in (1, 2, 3):  # the sample's addresses (id=0) -> the declared ones
        meta_path = d / f"page-{n}.meta.json"
        meta = json.loads(meta_path.read_text())
        meta["source_url"] = FEED.page_url(n)
        meta_path.write_text(json.dumps(meta))
    db = tmp_path / "w.duckdb"
    counts = rebuild("duckdb", "captured", database=db, cache_dir=cache)
    assert counts["raw_reviews"] == pins.APP_STORE_SAMPLE_RAW_ROWS
    assert counts["raw_source_pages"] == sum(len(s.pages) for s in SOURCES)
    joined = _query(
        db,
        "select r.external_id, count(p.source_url), min(p.profile), min(p.segment) "
        "from stg_reviews r left join raw_source_pages p "
        "on r.source = p.source and r.source_url = p.source_url "
        "group by r.external_id",
    )
    assert len(joined) == pins.APP_STORE_SAMPLE_STG_ROWS
    assert all(n == 1 for _, n, _, _ in joined), joined
    assert {(p, s) for _, _, p, s in joined} == {(FEED.profile, FEED.segment)}
    # every declared page carries the real day its declaration was recorded —
    # never an empty provenance column (round 1, code-reviewer #6)
    from datetime import date

    days = _query(db, "select distinct captured_at from raw_source_pages")
    assert days and all(date.fromisoformat(d) for (d,) in days)
    # a second rebuild re-declares the same pages and adds nothing
    again = rebuild("duckdb", "captured", database=db, cache_dir=cache, run_id="again")
    assert again["raw_source_pages"] == counts["raw_source_pages"]
