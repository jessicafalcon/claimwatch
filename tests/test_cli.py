"""The CLI behind `make` (pipeline/cli.py, pipeline/build.py::reset). Every
refused value is exit 2 and one line, never a traceback; `reset` handles only
the DuckDB file and deletes only it. Offline, temp file."""

from __future__ import annotations

from pipeline.build import reset
from pipeline.cli import main


def test_cli_refuses_bad_fixture_with_exit_2(capsys):
    """A refused value goes all the way through main(): exit 2, one line on
    stderr, nothing built."""
    code = main(["rebuild", "--fixture=../x"])
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("refusing:") and err.count("\n") <= 1


def test_reset_removes_only_the_db_and_wal(tmp_path):
    """reset() deletes exactly the DuckDB file and its .wal, touches no neighbour,
    and returns what it removed."""
    db = tmp_path / "friction_ledger.duckdb"
    wal = tmp_path / "friction_ledger.duckdb.wal"
    neighbour = tmp_path / "keep.txt"
    for p in (db, wal, neighbour):
        p.write_text("x")
    removed = reset("duckdb", database=db)
    assert not db.exists() and not wal.exists()
    assert neighbour.exists()
    assert set(removed) == {db, wal}


def test_cli_reset_refuses_non_duckdb_target(capsys):
    """TARGET=snowflake is refused with one line at the CLI, not a traceback from
    reset() downstream."""
    code = main(
        [
            "reset",
            "--target=snowflake",
            "--confirm=yes",
            "--confirm-origin=command line",
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("refusing:") and err.count("\n") <= 1
