"""The CLI behind `make` (pipeline/cli.py, pipeline/build.py::reset). Every
refused value is exit 2 and one line, never a traceback; `reset` handles only
the DuckDB file and deletes only it. Offline, temp file."""

from __future__ import annotations

import pytest

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


# --- Phase 2 ---


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    """The CLI's working database and capture cache, redirected to a temp dir so
    a test never touches data/."""
    import pipeline.build as build
    import pipeline.cli as cli
    import pipeline.warehouse as warehouse

    monkeypatch.setattr(warehouse, "DEFAULT_DB", tmp_path / "w.duckdb")
    cache = tmp_path / "data" / "cache" / "app-store"
    monkeypatch.setattr(build, "DEFAULT_CACHE", cache)
    monkeypatch.setattr(cli, "DEFAULT_CACHE", cache)
    return cache


def test_rebuild_defaults_to_the_cache_and_says_when_it_is_empty(
    isolated_paths, capsys
):
    """`make rebuild` with no FIXTURE is the real run: zero captures -> zero rows
    and a one-line hint, never an error (a fresh clone)."""
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "no captures under data/cache/app-store" in out
    assert "make scrape CONFIRM=yes" in out
    assert f"{'raw_reviews':24} 0" in out
    assert "(none)" in out


def test_rebuild_from_the_sample_prints_the_metric(isolated_paths, capsys):
    from tests import pins

    assert main(["rebuild", "--fixture=app-store"]) == 0
    out = capsys.readouterr().out
    assert f"{'raw_reviews':24} {pins.APP_STORE_SAMPLE_RAW_ROWS}" in out
    assert "reviews per month" in out
    for source, month, n in pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH:
        assert f"{source:14} {month}  {n}" in out


def test_rebuild_from_captures_under_the_cache(isolated_paths, capsys):
    import shutil
    from pathlib import Path

    from tests import pins

    sample = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
    shutil.copytree(sample, isolated_paths / "src" / "2026-09-01T08-00-00")
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "no captures" not in out
    assert f"{'stg_reviews':24} {pins.APP_STORE_SAMPLE_STG_ROWS}" in out


def test_cli_scrape_refuses_without_command_line_confirm(capsys, monkeypatch):
    """Non-interactive and unconfirmed: one line, exit 2, no fetch attempted
    (conftest would raise on a socket; nothing is imported from the fetcher)."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    code = main(["scrape", "--confirm=yes", "--confirm-origin=environment"])
    assert code == 2
    out = capsys.readouterr().out
    assert "pass CONFIRM=yes on the command line" in out
    assert "nothing fetched" in out


def test_cli_scrape_refuses_a_bad_source_with_exit_2(capsys):
    code = main(
        ["scrape", "--source=../x", "--confirm=yes", "--confirm-origin=command line"]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("refusing:") and err.count("\n") <= 1


def test_cli_scrape_refuses_an_unfilled_source_before_any_request(capsys, monkeypatch):
    """Confirmed on the command line but the source has no app id: the fetcher
    refuses before a request (a socket would raise here). The unfilled source
    is patched in, so the test holds whatever id the developer has declared."""
    from ingest.sources import AppStoreSource
    from pipeline import cli

    blank = AppStoreSource(name="blank", app_id=0, country="fr")
    monkeypatch.setattr(cli, "SOURCES", (blank,))
    code = main(["scrape", "--confirm=yes", "--confirm-origin=command line"])
    assert code == 2
    err = capsys.readouterr().err
    assert "has no app_id" in err


def test_cli_scrape_keeps_the_host_interval_across_sources(
    capsys, monkeypatch, isolated_paths
):
    """Two declared sources on one host in one run: the first request of the
    second source waits the full two seconds after the last of the first. One
    client, one per-host clock, for the whole `make scrape`."""
    import ingest.fetch as fetch
    from ingest.sources import AppStoreSource
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    two = (
        AppStoreSource(name="one", app_id=1, country="fr"),
        AppStoreSource(name="two", app_id=2, country="fr"),
    )
    monkeypatch.setattr(cli, "SOURCES", two)
    code = main(["scrape", "--confirm=yes", "--confirm-origin=command line"])
    assert code == 0
    n = len(server.requests)
    assert n == 2 * (1 + 3)  # robots + three sample pages, per source
    assert clock.sleeps == [2.0] * (n - 1)  # including the gap between sources
    assert capsys.readouterr().out.count("scrape: ") == 2


def _count(out: str, table: str) -> int:
    (line,) = [ln for ln in out.splitlines() if ln.startswith(table + " ")]
    return int(line.split()[-1])


def test_each_input_builds_its_own_database(capsys, isolated_paths):
    """Fix amendment A2: the counts `rebuild FIXTURE=X` prints are X's own. The
    sample builds beside the corpus, never into it; `synthetic` leaves the
    corpus file absent; `reset` names every file it removed."""
    import pipeline.warehouse as warehouse

    corpus = warehouse.DEFAULT_DB
    assert main(["rebuild", "--fixture=synthetic"]) == 0
    assert _count(capsys.readouterr().out, "raw_reviews") == 40
    assert not corpus.exists()
    assert main(["rebuild", "--fixture=app-store"]) == 0
    assert _count(capsys.readouterr().out, "raw_reviews") == 8
    assert main(["rebuild"]) == 0  # the cache, empty here
    assert _count(capsys.readouterr().out, "raw_reviews") == 0
    files = {corpus.with_name(f"w.{f}.duckdb") for f in ("synthetic", "app-store")}
    assert corpus.exists() and all(f.exists() for f in files)
    assert main(["rebuild", "--fixture=app-store"]) == 0  # again: still 8, not 16
    assert _count(capsys.readouterr().out, "raw_reviews") == 8
    assert main(["reset", "--confirm=yes", "--confirm-origin=command line"]) == 0
    out = capsys.readouterr().out
    assert not corpus.exists() and not any(f.exists() for f in files)
    assert all(str(f) in out for f in files | {corpus})
