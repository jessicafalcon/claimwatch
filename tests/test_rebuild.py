"""rebuild runs end to end on zero rows and on the synthetic fixture, and staging
keeps the latest capture (spec Phase 1, done-when 2 and 3). Offline, temp file."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decimal import Decimal  # noqa: E402

import pins  # noqa: E402
import pytest  # noqa: E402

from ingest.parsed import PageShapeError  # noqa: E402
from pipeline.build import (  # noqa: E402
    _columns,
    build_derived,
    check_raw_declaration,
    content_hash,
    create_raw,
    load_reviews,
    rebuild,
    table_counts,
)
from pipeline.warehouse import connect, database_for, default_schema  # noqa: E402

_INSERT_RAW = (
    "insert into raw_reviews (source, external_id, source_url, captured_at, "
    "run_id, review_date, rating, title, body, content_hash) "
    "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def test_zero_row_rebuild(tmp_path):
    """`none`: every table exists and every count is zero — the anchors seed
    every other input, not this one."""
    counts = rebuild("duckdb", "none", root=tmp_path)
    assert set(counts) >= {"raw_reviews", "stg_reviews", "raw_platform_snapshots"}
    assert all(n == 0 for n in counts.values()), counts


def test_synthetic_stage_counts_match_pins(tmp_path):
    counts = rebuild("duckdb", "synthetic", root=tmp_path, run_id="test")
    assert counts["raw_reviews"] == pins.RAW_REVIEWS_ROWS
    assert counts["stg_reviews"] == pins.STG_REVIEWS_ROWS


def test_staging_keeps_latest_capture(synthetic_conn):
    source, external_id = pins.EDITED_REVIEW
    rows = synthetic_conn.execute(
        "select captured_at, rating from stg_reviews "
        "where source = ? and external_id = ?",
        [source, external_id],
    ).fetchall()
    assert len(rows) == 1
    captured_at, rating = rows[0]
    assert captured_at == pins.EDITED_REVIEW_LATEST_CAPTURED_AT
    assert rating == pins.EDITED_REVIEW_LATEST_RATING


def test_fixture_spans_the_rating_range(synthetic_conn):
    """The synthetic bodies cover every outcome from one-star to five-star; the
    ratings span the whole pinned scale (uses tests/pins.py::RATING_RANGE)."""
    lo, hi = synthetic_conn.execute(
        "select min(rating), max(rating) from raw_reviews"
    ).fetchone()
    assert (lo, hi) == pins.RATING_RANGE


def test_staging_tiebreak_is_deterministic_on_equal_captured_at():
    """Invariant 3's tiebreak: two captures of one key sharing a captured_at
    deduplicate to the higher content_hash, whatever the insertion order — so
    the survivor is a function of the data, not of the physical row order. Drop
    `content_hash desc` from the dedup and one insertion order changes."""
    lo = ("00aa", 3, "lower-hash")
    hi = ("ff99", 4, "higher-hash")
    for order in ([lo, hi], [hi, lo]):
        conn = connect("duckdb", database=":memory:")
        try:
            create_raw(conn)
            for content_hash, rating, body in order:
                conn.execute(
                    _INSERT_RAW,
                    [
                        "oa",
                        "DUP",
                        "https://x/",
                        "2026-05-01T00:00:00",
                        "t",
                        "2026-05-01",
                        rating,
                        "t",
                        body,
                        content_hash,
                    ],
                )
            build_derived(conn)
            row = conn.execute(
                "select content_hash, body from stg_reviews "
                "where source = 'oa' and external_id = 'DUP'"
            ).fetchone()
            assert row == ("ff99", "higher-hash"), order
        finally:
            conn.close()


def _review(rating) -> dict:
    return {
        "source": "oa",
        "external_id": "R1",
        "source_url": "https://x/",
        "captured_at": "2026-05-01T00:00:00",
        "review_date": "2026-05-01",
        "rating": rating,
        "title": "t",
        "body": "b",
    }


@pytest.mark.parametrize("rating", ["4.25", "4.0", "0.5", "6", "", "x", True, None])
def test_loader_refuses_a_rating_outside_the_half_steps(rating):
    """A6: the loader checks the closed set (`parsed.REVIEW_RATINGS`) on every
    row it is handed, whatever handed it; a refusal names the field and the
    value and nothing is inserted."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        with pytest.raises(PageShapeError, match="field 'rating' is not a half-step"):
            load_reviews(conn, [_review(rating)], run_id="t")
        assert conn.execute("select count(*) from raw_reviews").fetchone() == (0,)
    finally:
        conn.close()


def test_a_refused_review_batch_loads_nothing():
    """A8 (b): the review loader loads a batch or nothing — four good rows
    and a fifth outside the half-steps leave zero rows in raw, where a
    row-by-row load committed the first four (round 4, code-reviewer #1)."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        rows = [
            {**_review("4"), "external_id": f"r{k}", "body": f"b{k}"} for k in range(4)
        ] + [{**_review("4.25"), "external_id": "r4"}]
        with pytest.raises(PageShapeError, match="field 'rating' is not a half-step"):
            load_reviews(conn, rows, run_id="t")
        assert conn.execute("select count(*) from raw_reviews").fetchone() == (0,)
        load_reviews(conn, rows[:4], run_id="t")  # the same good rows, alone: all four
        assert conn.execute("select count(*) from raw_reviews").fetchone() == (4,)
    finally:
        conn.close()


@pytest.mark.parametrize("rating", ["4.5", Decimal("4.5"), 4, "4", Decimal("4.0")])
def test_loader_stores_a_half_step_as_the_column_spells_it(rating):
    """A6: a member of the set, however spelled by its source, lands as one
    decimal(2, 1) value."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        load_reviews(conn, [_review(rating)], run_id="t")
        (stored,) = conn.execute("select rating from raw_reviews").fetchone()
        assert stored == Decimal(str(rating))
    finally:
        conn.close()


def test_content_hash_spells_a_rating_one_way():
    """A6: `1`, `"1"` and `Decimal("1.0")` are one figure and one fingerprint,
    so the synthetic corpus's hashes (strings) and a parser's Decimals agree
    and a re-run inserts nothing."""
    hashes = {content_hash(_review(r)) for r in (1, "1", Decimal("1"), Decimal("1.0"))}
    assert len(hashes) == 1
    assert content_hash(_review("1.5")) == content_hash(_review(Decimal("1.5")))
    assert content_hash(_review("1.5")) != content_hash(_review("1"))


RAW_REVIEWS_SQL = (
    Path(__file__).resolve().parents[1] / "sql" / "raw" / "raw_reviews.sql"
)


def _previous_declaration() -> str:
    """raw_reviews as declared before A6: `rating integer`."""
    sql = RAW_REVIEWS_SQL.read_text(encoding="utf-8")
    assert "rating        decimal(2, 1) not null" in sql
    return sql.replace(
        "rating        decimal(2, 1) not null", "rating        integer not null"
    )


def test_a_raw_table_built_under_a_previous_declaration_refuses_the_rebuild():
    """A7: the corpus file keeps the column it was built with; the engine
    would cast into it. The rebuild refuses naming table, column and both
    types, and inserts nothing."""
    conn = connect("duckdb", database=":memory:")
    try:
        conn.execute(_previous_declaration())
        with pytest.raises(PageShapeError) as exc:
            create_raw(conn)
        message = str(exc.value)
        assert "raw_reviews" in message and "'rating'" in message
        assert (
            "INTEGER not null in the database" in message
            and "DECIMAL(2,1) not null in the file" in message
        )
        assert "`make confirm reset`" in message and "\n" not in message
        assert conn.execute("select count(*) from raw_reviews").fetchone() == (0,)
        assert conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name like 'declared_%'"
        ).fetchone() == (0,)
    finally:
        conn.close()


def test_a_raw_table_with_an_extra_column_refuses_the_rebuild():
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        conn.execute("alter table raw_reviews add column extra text")
        with pytest.raises(
            PageShapeError, match="column 'extra' is in the database only"
        ):
            create_raw(conn)
    finally:
        conn.close()


def test_a_nullability_drift_refuses_with_one_line():
    """A8 (a): the comparison is the whole declaration. A4 (e) made
    `review_count` nullable; a corpus built before it passed A7's name-and-type
    check and then died in a driver ConstraintException at the load. Now the
    nullability difference refuses like a type, naming the column, both
    sides and the fix, before anything is loaded."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        conn.execute(
            "alter table raw_platform_snapshots alter column review_count set not null"
        )
        with pytest.raises(PageShapeError) as exc:
            create_raw(conn)
        message = str(exc.value)
        assert "'review_count' INTEGER not null in the database" in message
        assert "'review_count' INTEGER nullable in the file" in message
        assert "`make confirm reset`" in message and "\n" not in message
    finally:
        conn.close()


def test_columns_in_another_order_refuse_naming_the_position():
    """A8 (a): the comparison is by position — the file's order is the
    table's — so a column moved to the end refuses at the first position
    that differs, naming both columns."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        conn.execute("alter table raw_reviews drop column body")
        conn.execute("alter table raw_reviews add column body text")
        with pytest.raises(PageShapeError) as exc:
            create_raw(conn)
        message = str(exc.value)
        assert "column 9 is 'content_hash'" in message and "'body'" in message
    finally:
        conn.close()


def test_a_stray_scratch_named_table_refuses_naming_itself():
    """A8 (a): a table already sitting under the scratch name is not the
    declaration and not the corpus; the check refuses naming it and does not
    point at `make confirm reset`, and leaves it in place."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        conn.execute("create table declared_raw_reviews (a integer)")
        with pytest.raises(PageShapeError) as exc:
            create_raw(conn)
        message = str(exc.value)
        assert (
            "'declared_raw_reviews'" in message
            and "not one this repo builds" in message
        )
        assert "make confirm reset" not in message
        assert conn.execute("select count(*) from declared_raw_reviews").fetchone() == (
            0,
        )
    finally:
        conn.close()


def test_a_raw_file_with_two_statements_refuses_before_any_runs(tmp_path):
    """A8 (a): a raw file is exactly one `create table if not exists`; a
    second statement would run against the corpus during the check, so the
    file refuses first, and a header comment quoting the phrase is not a
    statement."""
    conn = connect("duckdb", database=":memory:")
    try:
        two = tmp_path / "raw_two.sql"
        two.write_text(
            "create table if not exists raw_x (a integer);\n"
            "create table if not exists raw_y (b integer);\n",
            encoding="utf-8",
        )
        with pytest.raises(PageShapeError, match="holds 2 statements, not one"):
            check_raw_declaration(conn, two)
        assert conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name in ('raw_x', 'raw_y')"
        ).fetchone() == (0,)
        other = tmp_path / "raw_other.sql"
        other.write_text("insert into raw_reviews select 1;\n", encoding="utf-8")
        with pytest.raises(PageShapeError, match="is not one `create table"):
            check_raw_declaration(conn, other)
        commented = tmp_path / "raw_commented.sql"
        commented.write_text(
            "-- create table if not exists nothing_here (x integer);\n"
            "create table if not exists raw_z (\n"
            "  a integer -- create table if not exists\n);\n",
            encoding="utf-8",
        )
        check_raw_declaration(conn, commented)  # raw_z does not exist yet: passes
        conn.execute("create table raw_z (a integer)")
        check_raw_declaration(conn, commented)  # matches: the comments were ignored
    finally:
        conn.close()


def test_the_scratch_declaration_is_listed_in_the_engines_default_schema():
    """A8 (a) asserts, rather than assumes, that the engine lists a temporary
    table under the schema it names as its default, which is where `_columns`
    reads the scratch declaration from."""
    conn = connect("duckdb", database=":memory:")
    try:
        conn.execute("create temporary table t_scratch (a integer, b text not null)")
        assert _columns(conn, "t_scratch") == [
            ("a", "INTEGER", "YES"),
            ("b", "VARCHAR", "NO"),
        ]
    finally:
        conn.close()


class _ReversedRows:
    """A connection that hands every result set back in reverse — the order an
    engine returns catalog rows in is not a promise, and this stands in for
    one that keeps none."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, *args, **kwargs):
        return _ReversedCursor(self._conn.execute(*args, **kwargs))


class _ReversedCursor:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def fetchall(self):
        return list(reversed(self._cursor.fetchall()))

    def fetchone(self):
        return self._cursor.fetchone()


def test_column_positions_are_the_catalogs_ordinals_not_the_row_order():
    """A8 (a)'s positional comparison rests on `ordinal_position` as a value
    read from the catalog and sorted on, not on the order the engine returns
    rows in: through a connection that reverses every result set, the columns
    still come back in the declaration's order (round 5, functionality-tester
    #1 — the `order by` alone survived removal on DuckDB, which happens to
    list columns in order)."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        straight = _columns(conn, "raw_reviews")
        assert [name for name, _, _ in straight][:2] == ["source", "external_id"]
        assert _columns(_ReversedRows(conn), "raw_reviews") == straight
        create_raw(_ReversedRows(conn))  # the check passes through it too
    finally:
        conn.close()


def test_a_matching_raw_table_passes_and_leaves_no_scratch_table():
    """A7's happy path: a second create_raw on a database the files built is
    a no-op that leaves nothing behind, so a rebuild on the corpus file is
    unchanged when nothing changed."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        before = conn.execute(
            "select table_name from information_schema.tables order by 1"
        ).fetchall()
        create_raw(conn)
        check_raw_declaration(conn, RAW_REVIEWS_SQL)
        after = conn.execute(
            "select table_name from information_schema.tables order by 1"
        ).fetchall()
        assert after == before and not any(n.startswith("declared_") for (n,) in after)
    finally:
        conn.close()


def test_table_counts_reads_the_default_schema_from_the_engine():
    """The counts `idempotency-check` diffs are the default schema's tables,
    the schema named by the engine (`warehouse.default_schema`), not a
    literal: a table in another schema is not counted, one in the default
    schema is (round 4, code-reviewer #3)."""
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        conn.execute("create schema elsewhere")
        conn.execute("create table elsewhere.stray (x integer)")
        conn.execute("insert into elsewhere.stray values (1)")
        counts = table_counts(conn)
        assert "stray" not in counts and counts["raw_reviews"] == 0
        assert default_schema(conn) == "main"  # DuckDB's answer, read, not spelled
    finally:
        conn.close()


def test_the_database_file_is_derived_from_the_input_never_named(tmp_path):
    """A8 (e): `rebuild` takes a root directory and the file is always
    `database_for(rows, root)` — there is no way to name the file an input
    lands in, so the literal `sample` exists only in the samples file wherever
    the root is (round 4, code-reviewer #4)."""
    import inspect

    from pipeline.build import load_snapshots

    assert "database" not in inspect.signature(rebuild).parameters
    assert "root" in inspect.signature(rebuild).parameters
    rebuild("duckdb", "samples", root=tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "friction_ledger.samples.duckdb"
    ]
    samples = tmp_path / "friction_ledger.samples.duckdb"
    assert database_for("samples", tmp_path) == samples
    assert database_for("captured", tmp_path) == tmp_path / "friction_ledger.duckdb"
    with pytest.raises(ValueError, match="not in"):
        rebuild("duckdb", "corpus", root=tmp_path)  # not an input: no file at all
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "friction_ledger.samples.duckdb"
    ]
    # the label set the loader applies is the input, never a signature's default
    rows_input = inspect.signature(load_snapshots).parameters["rows_input"]
    assert rows_input.default is inspect.Parameter.empty
    conn = connect("duckdb", database=":memory:")
    try:
        create_raw(conn)
        with pytest.raises(TypeError):
            load_snapshots(conn, [], "t")  # rows_input is required
    finally:
        conn.close()
