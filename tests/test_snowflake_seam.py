"""The Snowflake branch of the warehouse seam, proved offline against the
recording fake (`tests/fake_snowflake.py`) — no socket, no real driver (Phase
10b). The fake→real trust boundary: this pins the seam's shape against a
hand-written connector; the five stack-risk unknowns and the run's counts and
schema name are verified live and recorded Documented-by-hand in DECISIONS →
Gotchas (spec done-when 6).

The DuckDB branch is exercised for real (in-memory / temp file) wherever a
property is "on both branches"."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import build, warehouse
from pipeline.warehouse import CLOUD, LOCAL, connect
from tests import fake_snowflake
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # a rebuild-backed test is here; off the edit loop


# --- Done-when 1: one connection shape, one error type, lazy import -----------
def test_the_snowflake_branch_wraps_a_qmark_cursor_in_the_seams_shape(monkeypatch):
    fake = fake_snowflake.install(monkeypatch)
    conn = connect(CLOUD, database="friction_ledger_synthetic")
    assert fake.paramstyle == "qmark"  # set before connect (the module-level knob)
    result = conn.execute("select 1")
    assert hasattr(result, "fetchone") and hasattr(result, "fetchall")
    assert hasattr(result, "description")
    conn.executemany("insert into t (x) values (?)", [[1], [2]])
    conn.close()
    ops = [op for op, _, _ in fake.CALLS]
    assert "connect" in ops and "executemany" in ops
    assert ops.count("cursor.close") == 1 and ops.count("conn.close") == 1


def test_run_sql_file_runs_every_statement_of_a_file_on_both_branches(
    tmp_path, monkeypatch
):
    sql = tmp_path / "three.sql"
    sql.write_text(
        "create table a (x integer);\n"
        "create table b (x integer);\n"
        "create table c (x integer);\n",
        encoding="utf-8",
    )
    duck = connect(LOCAL, database=":memory:")
    try:
        warehouse.run_sql_file(duck, sql)
        assert {"a", "b", "c"} <= set(warehouse.tables(duck))  # three effects
    finally:
        duck.close()

    fake = fake_snowflake.install(monkeypatch)
    conn = connect(CLOUD, database=None)  # no schema create; the file's call is alone
    try:
        warehouse.run_sql_file(conn, sql)
    finally:
        conn.close()
    scripts = [text for op, text, _ in fake.CALLS if op == "execute_string"]
    assert len(scripts) == 1
    assert all(f"create table {t}" in scripts[0] for t in ("a", "b", "c"))


def test_each_branch_folds_its_drivers_error_into_the_seams_one_type(monkeypatch):
    duck = connect(LOCAL, database=":memory:")
    try:
        with pytest.raises(warehouse.DriverError):
            duck.execute("select not valid sql !!!")
    finally:
        duck.close()

    fake_snowflake.install(monkeypatch, execute_error="the fake driver refused")
    conn = connect(CLOUD, database=None)
    with pytest.raises(warehouse.DriverError):
        conn.execute("select 1")
    with pytest.raises(warehouse.DriverError):
        conn.executescript("create table t (x int);")


def test_a_missing_extra_is_one_refusal_line_naming_the_sync_command(monkeypatch):
    # No connector installed: import fails -> one DriverError naming the sync
    # command, never an ImportError traceback.
    import sys

    monkeypatch.setitem(sys.modules, "snowflake", None)
    fake_snowflake.set_credentials(monkeypatch)
    with pytest.raises(warehouse.DriverError, match=r"uv sync --extra snowflake"):
        connect(CLOUD, database="friction_ledger_synthetic")


def test_a_missing_extra_is_one_refusal_line_through_the_cli(monkeypatch, capsys):
    """The missing-extra refusal reaches the process boundary as one line, exit
    2 (invariant 4's 'missing extra' arm at the CLI, not only at `connect()` —
    round 1 code-reviewer #12): no connector installed, credentials set."""
    import sys

    from pipeline.cli import main

    monkeypatch.setitem(sys.modules, "snowflake", None)
    fake_snowflake.set_credentials(monkeypatch)
    code = main(["rebuild", "--target=snowflake", "--rows=synthetic"])
    assert code == 2
    err = capsys.readouterr().err
    assert "uv sync --extra snowflake" in err and err.count("\n") <= 1


# --- Done-when 2: catalog reads are the seam's and case-folded ----------------
def test_catalog_answers_are_case_folded_on_both_branches(monkeypatch):
    # The fake answers UPPER (Snowflake's unquoted folding); the seam folds to
    # lower, so an equality holds the same way as on DuckDB's own lower answers.
    fake_snowflake.install(
        monkeypatch,
        schema="FRICTION_LEDGER_SYNTHETIC",
        tables=("STG_REVIEWS", "RAW_REVIEWS"),
        columns={
            "STG_REVIEWS": [(1, "RATING", "NUMBER", "YES"), (2, "BODY", "TEXT", "YES")]
        },
    )
    cloud = connect(CLOUD, database="friction_ledger_synthetic")
    try:
        assert warehouse.tables(cloud) == ["raw_reviews", "stg_reviews"]
        assert warehouse.table_exists(cloud, "stg_reviews")
        assert warehouse.table_exists(cloud, "STG_REVIEWS")  # the arg is folded too
        assert warehouse.columns(cloud, "stg_reviews") == [
            ("rating", "NUMBER", "YES"),
            ("body", "TEXT", "YES"),
        ]
    finally:
        cloud.close()

    duck = connect(LOCAL, database=":memory:")
    try:
        duck.execute("create table stg_reviews (rating integer, body text)")
        assert warehouse.tables(duck) == ["stg_reviews"]
        assert warehouse.table_exists(duck, "STG_REVIEWS")  # case-insensitive on both
        assert [name for name, _, _ in warehouse.columns(duck, "stg_reviews")] == [
            "rating",
            "body",
        ]
    finally:
        duck.close()


# --- Done-when 3: a location per (input, target); a corpus input has none -----
def test_location_for_is_a_file_per_input_on_duckdb_and_a_schema_per_input_on_snowflake(
    tmp_path,
):
    for rows in build.INPUTS:
        assert warehouse.location_for(LOCAL, rows, tmp_path) == warehouse.database_for(
            rows, tmp_path
        )
    assert warehouse.location_for(CLOUD, "synthetic") == "friction_ledger_synthetic"
    assert warehouse.location_for(CLOUD, "none") == "friction_ledger_none"
    for rows in warehouse.CLOUD_FORBIDDEN_INPUTS:
        with pytest.raises(ValueError, match=rf"{rows}.*snowflake|snowflake.*{rows}"):
            warehouse.location_for(CLOUD, rows)


def test_scratch_creates_and_drops_a_schema_that_is_no_inputs_own(monkeypatch):
    # DuckDB: a temp file under a temp dir, gone after the block, never an input's own.
    with warehouse.scratch(LOCAL, "synthetic") as loc:
        assert Path(loc).parent.is_dir()
        assert loc != warehouse.database_for("synthetic")
    assert not Path(loc).parent.exists()

    # Snowflake: connecting into the scratch creates it; the block's exit drops
    # it, even after an error, and the name is no input's own.
    fake = fake_snowflake.install(monkeypatch)
    with pytest.raises(RuntimeError), warehouse.scratch(CLOUD, "synthetic") as name:
        assert name != warehouse.location_for(CLOUD, "synthetic")
        connect(CLOUD, database=name).close()  # triggers create schema
        raise RuntimeError("boom inside the block")
    creates = [t for op, t, _ in fake.CALLS if op == "execute" and "create schema" in t]
    drops = [t for op, t, _ in fake.CALLS if op == "execute" and "drop schema" in t]
    assert any(name in c for c in creates) and any(name in d for d in drops)


def test_scratch_refuses_a_corpus_input_on_the_cloud_target(monkeypatch):
    """The corpus-refusal guard lives at every location source, not only the CLI
    and `location_for`: `scratch(CLOUD, corpus)` refuses before yielding, so the
    trial cannot hold a real review through the idempotency scratch path either
    (invariant 2 by construction — round 1 #1). DuckDB scratch takes any input."""
    fake = fake_snowflake.install(monkeypatch)
    for rows in warehouse.CLOUD_FORBIDDEN_INPUTS:
        with (
            pytest.raises(ValueError, match="never reach the cloud"),
            warehouse.scratch(CLOUD, rows),
        ):
            pass
        assert not any(op == "connect" for op, _, _ in fake.CALLS)  # nothing connected
    with warehouse.scratch(LOCAL, "captured"):  # the laptop takes any input
        pass


# --- Done-when 4: the classify step writes land on the target -----------------
def test_the_classify_step_writes_land_on_the_target(tmp_path, monkeypatch):
    # Build the synthetic warehouse on DuckDB, read its staged reviews, then run
    # the classify step over the fake with those very rows: every write is
    # recorded on the fake and no DuckDB file is opened at the schema name.
    db = build_study_db(tmp_path, "synthetic")
    duck = connect(LOCAL, database=db)
    try:
        staged = duck.execute(
            "select source, external_id, title, body from stg_reviews"
        ).fetchall()
    finally:
        duck.close()
    assert staged  # the synthetic corpus has staged reviews

    fake = fake_snowflake.install(
        monkeypatch, tables=("STG_REVIEWS",), reviews=tuple(staged)
    )
    outcome = build.classify_step(
        "friction_ledger_synthetic",
        "synthetic",
        target=CLOUD,
        cache_path=tmp_path / "decisions.csv",
    )
    assert outcome is not None and outcome.graded  # held-out fold is gradeable
    writes = " ".join(t for op, t, _ in fake.CALLS if op == "execute" and t)
    classify_tables = (
        "stg_classified_reviews",
        "pipeline_row_counts",
        "classifier_quality",
    )
    for table in classify_tables:
        assert f"insert into {table}" in writes, table
    scripts = " ".join(t for op, t, _ in fake.CALLS if op == "execute_string")
    for mart in ("theme_share_by_month", "theme_share_by_segment", "review_drill"):
        assert mart in scripts, mart
    assert not Path("friction_ledger_synthetic").exists()  # no DuckDB file


# --- Done-when 5: credentials are strings, read by name, refused by name ------
def test_a_missing_credential_is_refused_by_name_and_no_value_is_printed(
    monkeypatch, capsys
):
    from pipeline.cli import main

    fake_snowflake.install(monkeypatch)  # connector present, credentials set
    required = warehouse.SNOWFLAKE_ENV[:-1]  # every name but the optional role
    for name in required:
        monkeypatch.setenv(name, "a-real-value")
    for missing in required:
        monkeypatch.delenv(missing, raising=False)
        result = main(["rebuild", "--target=snowflake", "--rows=synthetic"])
        assert result == 2
        captured = capsys.readouterr()
        assert missing in captured.err and captured.err.count("\n") <= 1
        assert "a-real-value" not in captured.err + captured.out  # no value shown
        monkeypatch.setenv(missing, "a-real-value")  # restore for the next turn
    # SNOWFLAKE_ROLE absent is not a refusal: the credentials read returns "".
    monkeypatch.delenv("SNOWFLAKE_ROLE", raising=False)
    assert warehouse._snowflake_credentials()["SNOWFLAKE_ROLE"] == ""


def test_a_driver_refusal_is_one_line_naming_the_class_and_the_variables_not_the_message(  # noqa: E501 -- the spec's Evidence table cites this exact test name
    monkeypatch, capsys
):
    planted = "secret-locator.snowflakecomputing.com"
    fake_snowflake.install(monkeypatch, connect_error=f"login failed ACCOUNT={planted}")
    from pipeline.cli import main

    code = main(["rebuild", "--target=snowflake", "--rows=synthetic"])
    assert code == 2
    err = capsys.readouterr().err
    assert "snowflake.connector.Error" in err
    assert "SNOWFLAKE_ACCOUNT" in err
    assert planted not in err and "snowflakecomputing.com" not in err
    assert err.count("\n") <= 1


# --- Invariant 5: the DuckDB path loads no connector --------------------------
def test_the_duckdb_branch_never_imports_the_connector(tmp_path):
    import sys

    sys.modules.pop("snowflake", None)
    sys.modules.pop("snowflake.connector", None)
    build.rebuild(LOCAL, "synthetic", root=tmp_path, run_id="probe")
    assert "snowflake" not in sys.modules
    assert "snowflake.connector" not in sys.modules


# --- Done-when 6: the demonstration is committed text, no account or host -----
def test_demonstration_doc_exists_and_names_no_account_or_host():
    doc = warehouse.ROOT / "pipeline" / "DEMONSTRATION.md"
    text = doc.read_text(encoding="utf-8")
    assert "idempotency-check" in text  # the walk is present
    assert ".snowflakecomputing.com" not in text  # no account locator
    assert "SNOWFLAKE_ACCOUNT=" not in text  # no credential value
    assert "https://" not in text  # no console link (its address bar has the account)
