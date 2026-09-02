"""Every raw row carries the four provenance columns (spec Phase 1, done-when 3).
Offline, temp file via the synthetic_conn fixture."""

from __future__ import annotations

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
