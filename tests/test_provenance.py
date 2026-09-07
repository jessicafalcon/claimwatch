"""Every raw row carries the four provenance columns (spec Phase 1, done-when 3).
Offline, temp file via the synthetic_conn fixture."""

from __future__ import annotations

import pytest

from pipeline.warehouse import database_for

pytestmark = pytest.mark.slow  # slow: kept out of the fast edit-loop hook

PROVENANCE = ("source", "source_url", "captured_at", "run_id")


def test_raw_reviews_has_four_provenance_columns(synthetic_conn):
    columns = {
        row[0]
        for row in synthetic_conn.execute(
            "select column_name from information_schema.columns "
            "where table_name = 'raw_reviews'"
        ).fetchall()
    }
    assert set(PROVENANCE) <= columns

    predicate = " or ".join(f"{c} is null" for c in PROVENANCE)
    nulls = synthetic_conn.execute(
        f"select count(*) from raw_reviews where {predicate}"
    ).fetchone()[0]
    assert nulls == 0

    blank_run = synthetic_conn.execute(
        "select count(*) from raw_reviews where run_id = ''"
    ).fetchone()[0]
    assert blank_run == 0


@pytest.mark.parametrize("rows", ["synthetic", "samples"])
def test_every_raw_table_has_four_provenance_columns(tmp_path, rows):
    """Phase 3a, invariant 1: every `raw_*` table, not only reviews, carries the
    four provenance columns and no row leaves one empty — under the samples
    input too, where every parser writes (A4 (b))."""
    from pipeline.build import rebuild
    from pipeline.warehouse import connect

    db = database_for(rows, tmp_path)
    rebuild("duckdb", rows, root=tmp_path, run_id="test")
    conn = connect("duckdb", database=db)
    try:
        _check_tables(conn)
    finally:
        conn.close()


def _check_tables(synthetic_conn) -> None:
    tables = [
        row[0]
        for row in synthetic_conn.execute(
            "select table_name from information_schema.tables "
            "where table_schema = 'main' and table_name like 'raw_%' "
            "order by table_name"
        ).fetchall()
    ]
    assert "raw_reviews" in tables and "raw_platform_snapshots" in tables
    for table in tables:
        columns = {
            row[0]
            for row in synthetic_conn.execute(
                "select column_name from information_schema.columns "
                f"where table_name = '{table}'"
            ).fetchall()
        }
        assert set(PROVENANCE) <= columns, table
        predicate = " or ".join(f"{c} is null or {c} = ''" for c in PROVENANCE)
        bad = synthetic_conn.execute(
            f"select count(*) from {table} where {predicate}"
        ).fetchone()[0]
        assert bad == 0, table
