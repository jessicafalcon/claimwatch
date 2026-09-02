"""The CLI behind `make` (pipeline/cli.py, pipeline/build.py::reset). Every
refused value is exit 2 and one line, never a traceback; `reset` handles only
the DuckDB file and deletes only it. Offline, temp file."""

from __future__ import annotations

from pipeline.cli import main


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
