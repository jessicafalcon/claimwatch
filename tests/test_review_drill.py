"""Phase 9g: the review-level drill (review_drill, B2.1) and its SQLite export.

Offline, no key, DuckDB temp files. The CLI classify path is replicated here
(rebuild -> classify_all rules-only -> write_classified_reviews ->
build_post_classify_marts), so review_drill is exercised without the CLI's
printing or fixed db paths. The central constraint: the drill exposes the
non-text allowlist only, its sole text is study/paraphrases.yaml, and no review
body ever appears."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from classify.combined import classify_all
from classify.labels import POSITIVE, THEMES, UNCLASSIFIED, review_id
from classify.rules import load_rules
from pipeline.build import build_post_classify_marts, rebuild, write_classified_reviews
from pipeline.warehouse import connect, database_for
from study.metabase import export
from study.metabase.export import ExportError, _cell, build_sqlite
from tests import pins

pytestmark = pytest.mark.slow  # slow: a full rebuild, kept out of the fast hook

PARAPHRASES = Path(__file__).resolve().parent.parent / "study" / "paraphrases.yaml"
FORBIDDEN = ("body", "title", "source_url")


def _classify_and_build(db, run_id: str = "t") -> None:
    """Fill stg_classified_reviews and build the post-classify marts (rules-only,
    no key) — the CLI classify step's work."""
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
        build_post_classify_marts(conn)
    finally:
        conn.close()


def _built(tmp_path, rows: str = "synthetic"):
    db = database_for(rows, tmp_path)
    rebuild("duckdb", rows, root=tmp_path, run_id="t")
    _classify_and_build(db)
    return db


def _drill_columns(db) -> tuple[str, ...]:
    conn = connect("duckdb", database=db)
    try:
        cur = conn.execute("select * from review_drill limit 0")
        return tuple(d[0] for d in cur.description)
    finally:
        conn.close()


def test_drill_projects_only_the_non_text_allowlist_across_the_join(tmp_path):
    """Invariant: review_drill projects exactly the non-text allowlist, even
    though the join reaches stg_reviews, which carries body/title/source_url."""
    db = _built(tmp_path)
    assert _drill_columns(db) == pins.REVIEW_DRILL_COLUMNS
    conn = connect("duckdb", database=db)
    try:
        joined = [
            d[0]
            for d in conn.execute("select * from stg_reviews limit 0").description
        ]
    finally:
        conn.close()
    # the join really does reach the text/brand columns — the projection is the guard
    assert set(FORBIDDEN) <= set(joined)
    assert not set(FORBIDDEN) & set(pins.REVIEW_DRILL_COLUMNS)


def test_review_id_expression_matches_labels_review_id(tmp_path):
    """Invariant: the drill's review_id equals classify/labels.py::review_id for
    every classified review — one definition of identity, not two."""
    db = _built(tmp_path)
    conn = connect("duckdb", database=db)
    try:
        pairs = conn.execute(
            "select distinct r.source, r.external_id "
            "from stg_classified_reviews c join stg_reviews r "
            "on c.source = r.source and c.external_id = r.external_id"
        ).fetchall()
        drill_ids = {
            r[0]
            for r in conn.execute("select distinct review_id from review_drill").fetchall()
        }
    finally:
        conn.close()
    assert drill_ids == {review_id(s, e) for s, e in pairs}


def test_drill_builds_and_bands_unclassified_with_no_key(tmp_path):
    """Done-when 4: the rules-only (no-key) path builds the drill, and ambiguous
    reviews appear under the 'unclassified' band — a real row, never dropped."""
    db = _built(tmp_path)  # _classify_and_build passes decide=None: no key
    conn = connect("duckdb", database=db)
    try:
        unclassified = conn.execute(
            "select count(*) from review_drill where theme = ?", [UNCLASSIFIED]
        ).fetchone()[0]
        total = conn.execute("select count(*) from review_drill").fetchone()[0]
    finally:
        conn.close()
    assert unclassified > 0
    assert total == pins.CLASSIFIED_REVIEWS_ROWS


def test_a_review_body_never_appears_in_any_drill_column(tmp_path):
    """Invariant: a review's own body is never shown — a synthetic review with a
    distinctive body renders no text, and the body string is in no drill cell."""
    db = _built(tmp_path)
    conn = connect("duckdb", database=db)
    try:
        body = conn.execute(
            "select body from stg_reviews where body <> '' order by source, external_id limit 1"
        ).fetchone()[0]
        cells = conn.execute("select * from review_drill").fetchall()
    finally:
        conn.close()
    assert body  # the fixture review carries a real body
    haystack = "\n".join(str(v) for row in cells for v in row)
    assert body not in haystack


def test_drilled_theme_paraphrase_resolves_to_a_sourced_entry(tmp_path):
    """Done-when 3: every one of the five themes has a Documented, sourced
    paraphrase in study/paraphrases.yaml, and every theme the drill shows (bar
    positive/unclassified, which carry no theme) has one."""
    data = yaml.safe_load(PARAPHRASES.read_text(encoding="utf-8"))
    assert set(data) == set(THEMES)
    for theme, entry in data.items():
        assert entry["paraphrase"].strip(), theme
        assert entry["source"].strip(), theme
        assert entry["title"].strip(), theme
    db = _built(tmp_path)
    conn = connect("duckdb", database=db)
    try:
        drill_themes = {
            r[0]
            for r in conn.execute("select distinct theme from review_drill").fetchall()
        }
    finally:
        conn.close()
    themed = drill_themes - {POSITIVE, UNCLASSIFIED}
    assert themed <= set(data)  # every complaint theme shown has a paraphrase


def test_sqlite_export_carries_only_the_allowlist_no_body_title_source_url(tmp_path):
    """Invariant: the SQLite export carries review_drill's allowlist and no more,
    and no exported table carries body/title/source_url."""
    db = _built(tmp_path)
    out = tmp_path / "metabase.sqlite"
    build_sqlite(duck_db=db, sqlite_path=out)
    conn = sqlite3.connect(out)
    try:
        drill_cols = tuple(r[1] for r in conn.execute("pragma table_info(review_drill)"))
        tables = [r[0] for r in conn.execute("select name from sqlite_master where type='table'")]
        for table in tables:
            cols = {r[1] for r in conn.execute(f'pragma table_info("{table}")')}
            assert not cols & set(FORBIDDEN), (table, cols)
    finally:
        conn.close()
    assert drill_cols == pins.REVIEW_DRILL_COLUMNS


def test_a_forbidden_mart_column_is_refused_by_name(tmp_path):
    """The export's second guard: a mart carrying a body/title/source_url column
    is refused by name, so a future mart change cannot leak review text."""
    db = _built(tmp_path)
    conn = connect("duckdb", database=db)
    try:
        conn.execute("create or replace table review_drill as select 'x' as body")
    finally:
        conn.close()
    with pytest.raises(ExportError, match="body"):
        build_sqlite(duck_db=db, sqlite_path=tmp_path / "leak.sqlite")


def test_sqlite_export_rating_is_exact_and_row_order_is_stable(tmp_path):
    """Invariant: the export preserves rating exactly (a rounded one-decimal
    string, no float drift) and is byte-identical on a rerun."""
    assert _cell(Decimal("4.3")) == "4.3"  # the exact-string rule, no 4.2999...
    db = _built(tmp_path)
    # a review whose rating is a fraction: it must read back exactly, not as a float
    conn = connect("duckdb", database=db)
    try:
        first = conn.execute(
            "select source, external_id from stg_reviews order by source, external_id limit 1"
        ).fetchone()
        conn.execute(
            "update stg_reviews set rating = 4.3 where source = ? and external_id = ?",
            [first[0], first[1]],
        )
        build_post_classify_marts(conn)
        rid = conn.execute(
            "select review_id from review_drill where rating = 4.3 limit 1"
        ).fetchone()
    finally:
        conn.close()
    assert rid is not None
    a = build_sqlite(duck_db=db, sqlite_path=tmp_path / "a.sqlite")
    b = build_sqlite(duck_db=db, sqlite_path=tmp_path / "b.sqlite")
    conn = sqlite3.connect(a)
    try:
        got = conn.execute(
            "select rating, typeof(rating) from review_drill where review_id = ?", [rid[0]]
        ).fetchone()
    finally:
        conn.close()
    assert got == ("4.3", "text")
    assert Path(a).read_bytes() == Path(b).read_bytes()  # byte-identical rerun
