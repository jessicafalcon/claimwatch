"""No file under sql/ uses a DuckDB-only form, a regex, or a clock (spec Phase 1,
done-when 4). The denylist is `pipeline.sql_lint`; here it runs over every real
sql/ file and over planted strings that must be rejected."""

from __future__ import annotations

from pathlib import Path

from pipeline.sql_lint import find_clock, find_nonportable

SQL_FILES = sorted((Path(__file__).resolve().parent.parent / "sql").rglob("*.sql"))


def test_repo_sql_is_portable_and_clock_free():
    assert SQL_FILES, "no sql files found"
    for path in SQL_FILES:
        text = path.read_text(encoding="utf-8")
        assert find_nonportable(text) == [], path
        assert find_clock(text) == [], path


def test_denylisted_form_is_rejected():
    assert find_nonportable("select * from read_csv('x.csv')")
    assert find_nonportable("select regexp_matches(body, 'x') from t")
    assert find_nonportable("select count(*) from t group by all")
    # a comment mentioning a form in prose is not a hit (comments are stripped)
    assert find_nonportable("-- we never use read_csv here\nselect 1") == []


def test_clock_in_sql_is_rejected():
    assert find_clock("select now()")
    assert find_clock("select current_date")
    assert find_clock("insert into t values (current_timestamp)")
    assert find_clock("-- captured_at, not now()\nselect 1") == []


def test_metric_query_is_portable_and_clock_free():
    """The Phase 2 metric is a query in Python, not a `sql/` file, so the lint
    is applied to its text here (spec Phase 2, invariant 4)."""
    from pipeline.metrics import REVIEWS_PER_MONTH

    assert find_nonportable(REVIEWS_PER_MONTH) == []
    assert find_clock(REVIEWS_PER_MONTH) == []
    assert "substr(review_date, 1, 7)" in REVIEWS_PER_MONTH


def test_pattern_matching_is_refused_in_sql():
    """Phase 3a, invariant 4: attribution joins on exact values; `like`,
    `similar to` and any regex function are refused alike."""
    assert find_nonportable("select 1 from t where source_url like '%id=1%'")
    assert find_nonportable("select 1 from t where url similar to 'a.*'")
    assert find_nonportable("select 1 from t where regexp_matches(url, 'x')")
    assert find_nonportable("select 1 from t where source_url = 'https://x/'") == []
    assert find_nonportable("-- never like this\nselect 1") == []
