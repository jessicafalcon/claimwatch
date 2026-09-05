"""Phase 7a: the persisted classification (stg_classified_reviews) and the two
theme-share marts (theme_share_by_month B2.2, theme_share_by_segment B2.5).

Offline, no key, DuckDB temp files. The classification path the CLI runs after a
rebuild is replicated here (rebuild -> classify_all rules-only ->
write_classified_reviews -> build_theme_share_marts), so the marts are exercised
without the CLI's printing or fixed db paths."""

from __future__ import annotations

import pytest

from classify.combined import classify_all
from classify.labels import review_id
from classify.rules import load_rules
from pipeline.build import (
    build_theme_share_marts,
    rebuild,
    write_classified_reviews,
)
from pipeline.warehouse import connect, database_for
from tests import pins


def _classify_and_build(db, run_id: str = "t") -> None:
    """Fill stg_classified_reviews and build the theme-share marts over the
    warehouse at `db` — the CLI classify step's work, rules-only (no key)."""
    conn = connect("duckdb", database=db)
    try:
        staged = conn.execute(
            "select source, external_id, title, body from stg_reviews"
        ).fetchall()
    finally:
        conn.close()
    identity = {review_id(s, e): (s, e) for s, e, _, _ in staged}
    reviews = [
        (review_id(s, e), "\n".join(p for p in (t, b) if p).strip())
        for s, e, t, b in staged
    ]
    rows, _ = classify_all(reviews, rules=load_rules())  # decide=None -> rules only
    classified = sorted(
        (identity[rid][0], identity[rid][1], theme) for rid, theme in rows
    )
    conn = connect("duckdb", database=db)
    try:
        write_classified_reviews(conn, classified, run_id=run_id)
        build_theme_share_marts(conn)
    finally:
        conn.close()


def _built(tmp_path, rows: str = "synthetic"):
    db = database_for(rows, tmp_path)
    rebuild("duckdb", rows, root=tmp_path, run_id="t")
    _classify_and_build(db)
    return db


def _rows(db, sql: str):
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_classified_reviews_grain_and_sorted(tmp_path):
    """Done-when 1: one row per (source, external_id, theme), the columns and
    count pinned, and stored in sorted order so a re-run is byte-identical."""
    db = _built(tmp_path)
    conn = connect("duckdb", database=db)
    try:
        cols = [
            r[0]
            for r in conn.execute(
                "select column_name from information_schema.columns "
                "where table_name = 'stg_classified_reviews' order by ordinal_position"
            ).fetchall()
        ]
        rows = conn.execute(
            "select source, external_id, theme from stg_classified_reviews"
        ).fetchall()
    finally:
        conn.close()
    assert tuple(cols) == pins.CLASSIFIED_REVIEWS_COLUMNS
    assert len(rows) == pins.CLASSIFIED_REVIEWS_ROWS
    assert rows == sorted(rows)
    assert len(set(rows)) == len(rows)  # (source, external_id, theme) is unique


def test_by_segment_pins(tmp_path):
    """Done-when 3: one row per (segment, label); theme_rows pinned, reviews the
    denominator, tag Measured, share = theme_rows / reviews. document-loop
    (B2.5's held-claim subject) is present."""
    db = _built(tmp_path)
    rows = _rows(
        db,
        "select segment, label, reviews, theme_rows, share, tag "
        "from theme_share_by_segment",
    )
    by_label = {
        label: (seg, reviews, tr, share, tag)
        for seg, label, reviews, tr, share, tag in rows
    }
    assert set(by_label) == set(pins.THEME_SHARE_BY_SEGMENT_NOKEY)
    for label, theme_rows in pins.THEME_SHARE_BY_SEGMENT_NOKEY.items():
        seg, reviews, tr, share, tag = by_label[label]
        assert seg == pins.THEME_SHARE_SEGMENT
        assert reviews == pins.THEME_SHARE_BY_SEGMENT_REVIEWS
        assert tr == theme_rows
        assert tag == pins.THEME_SHARE_TAG
        assert share == pytest.approx(theme_rows / reviews)
    assert "document-loop" in by_label


def test_by_month_pins(tmp_path):
    """Done-when 2: reviews per (month, digital-first) pinned; every month carries
    a document-loop row and every month a review the rules could not place carries
    an unclassified band row; share = theme_rows / reviews; tag Measured."""
    db = _built(tmp_path)
    rows = _rows(
        db,
        "select month, segment, label, reviews, theme_rows, share, tag "
        "from theme_share_by_month",
    )
    reviews_by_month = {m: reviews for m, _, _, reviews, _, _, _ in rows}
    assert reviews_by_month == pins.THEME_SHARE_BY_MONTH_REVIEWS
    for _month, _seg, _label, reviews, theme_rows, share, tag in rows:
        assert tag == pins.THEME_SHARE_TAG
        assert share == pytest.approx(theme_rows / reviews)
    months = pins.THEME_SHARE_BY_MONTH_REVIEWS
    doc_months = {m for m, _, label, *_ in rows if label == "document-loop"}
    assert doc_months == set(months)  # the held-claim theme in every month


def test_review_segment_is_its_source_segment(tmp_path):
    """Done-when 4 / invariant 2 (A1): a review carries the segment of the source
    it was loaded from. Every synthetic review is digital-first; a sample review
    (ROWS=samples) is `sample`."""
    syn = _rows(_built(tmp_path), "select distinct segment from stg_reviews")
    assert syn == [("digital-first",)]

    sample_dir = tmp_path / "samples-root"
    sample_dir.mkdir()
    db = database_for("samples", sample_dir)
    rebuild("duckdb", "samples", root=sample_dir, run_id="s")
    assert _rows(db, "select distinct segment from stg_reviews") == [("sample",)]


def test_rebuild_twice_stable(tmp_path):
    """Invariant 1: the classification and both theme marts are byte-identical on
    a second build — sorted rows, delete+insert, deterministic SQL."""
    db = _built(tmp_path)
    tables = (
        "stg_classified_reviews",
        "theme_share_by_month",
        "theme_share_by_segment",
    )
    first = {t: _rows(db, f"select * from {t} order by 1, 2, 3") for t in tables}
    _classify_and_build(db, run_id="t")  # run the classify path again on the same db
    second = {t: _rows(db, f"select * from {t} order by 1, 2, 3") for t in first}
    assert first == second


def test_no_review_dropped(tmp_path):
    """Invariant 3: no review is dropped — the theme_rows across labels in each
    (month, segment) cell sum to that cell's classified rows, which equals the
    reviews' total classification output (39 rows over the synthetic corpus)."""
    db = _built(tmp_path)
    total = _rows(db, "select sum(theme_rows) from theme_share_by_month")[0][0]
    assert total == pins.CLASSIFIED_REVIEWS_ROWS
    total_seg = _rows(db, "select sum(theme_rows) from theme_share_by_segment")[0][0]
    assert total_seg == pins.CLASSIFIED_REVIEWS_ROWS


def test_marts_on_samples_count_each_review_once(tmp_path):
    """Invariant 2 (A1) on the input where a source-slug join fails: `samples`
    declares two segments per platform (real `digital-first` + the parser
    `sample`), so grouping by a raw_source_pages join would count every review
    twice. Grouping by the review's own `segment` counts it once, under
    `sample`; `sum(theme_rows)` equals the classified rows, never double."""
    db = _built(tmp_path, "samples")
    classified = _rows(db, "select count(*) from stg_classified_reviews")[0][0]
    assert classified > 0
    assert _rows(db, "select distinct segment from theme_share_by_segment") == [
        ("sample",)
    ]
    for mart in ("theme_share_by_month", "theme_share_by_segment"):
        total = _rows(db, f"select sum(theme_rows) from {mart}")[0][0]
        assert total == classified, mart  # not 2 * classified


def test_distinct_denominator_counts_a_multi_theme_review_once(tmp_path):
    """The pinned grain: a two-theme review is one review in `reviews` (distinct)
    but a row in each theme bar, so shares can sum past 1. Exercises the
    `distinct` in the denominator — dropping it would count the review twice.
    (The synthetic corpus has no multi-theme review, so this crafts one.)"""
    db = _built(tmp_path)
    seg = pins.THEME_SHARE_SEGMENT
    before_reviews = _rows(
        db, f"select distinct reviews from theme_share_by_segment where segment='{seg}'"
    )
    before_total = _rows(db, "select sum(theme_rows) from theme_share_by_segment")[0][0]

    conn = connect("duckdb", database=db)
    try:
        src, ext, theme = conn.execute(
            "select source, external_id, theme from stg_classified_reviews "
            "order by source, external_id limit 1"
        ).fetchone()
        other = "coverage-price" if theme != "coverage-price" else "second-payer"
        conn.execute(
            "insert into stg_classified_reviews (source, external_id, theme, run_id) "
            "values (?, ?, ?, ?)",
            [src, ext, other, "t"],
        )
        build_theme_share_marts(conn)
    finally:
        conn.close()

    after_reviews = _rows(
        db, f"select distinct reviews from theme_share_by_segment where segment='{seg}'"
    )
    after_total = _rows(db, "select sum(theme_rows) from theme_share_by_segment")[0][0]
    assert after_reviews == before_reviews  # distinct: the review still counts once
    assert after_total == before_total + 1  # but it contributes a second theme row
