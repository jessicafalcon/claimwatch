"""The CLI behind `make` (pipeline/cli.py, pipeline/build.py::reset). Every
refused value is exit 2 and one line, never a traceback; `reset` handles only
the DuckDB file and deletes only it. Offline, temp file."""

from __future__ import annotations

import pytest

from ingest.sources import app_store_source, by_name
from pipeline.build import reset
from pipeline.cli import main


def test_cli_refuses_bad_rows_with_exit_2(capsys):
    """A refused value goes all the way through main(): exit 2, one line on
    stderr, nothing built."""
    code = main(["rebuild", "--rows=../x"])
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
    import ingest.sources as sources
    import pipeline.warehouse as warehouse

    monkeypatch.setattr(warehouse, "DEFAULT_DB", tmp_path / "w.duckdb")
    cache = tmp_path / "data" / "cache"
    monkeypatch.setattr(sources, "CACHE_ROOT", cache)  # the one binding
    return cache


def test_rebuild_defaults_to_the_cache_and_says_when_it_is_empty(
    isolated_paths, capsys
):
    """`make rebuild` with no ROWS is the real run: zero captures -> zero rows
    and a one-line hint, never an error (a fresh clone)."""
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "no captures under data/cache" in out
    assert "make scrape CONFIRM=yes" in out
    assert f"{'raw_reviews':24} 0" in out
    assert "(none)" in out


def test_rebuild_from_the_sample_prints_the_metric(isolated_paths, capsys):
    from tests import pins

    assert main(["rebuild", "--rows=samples"]) == 0
    out = capsys.readouterr().out
    assert f"{'raw_reviews':24} {pins.SAMPLES_RAW_REVIEWS}" in out
    assert "reviews per month" in out
    months = pins.APP_STORE_SAMPLE_REVIEWS_PER_MONTH + pins.OA_SAMPLE_REVIEWS_PER_MONTH
    width = max(len(source) for source, _, _ in months)  # the month column lines up
    for source, month, n in months:
        assert f"  {source:{width}} {month}  {n}\n" in out


def test_rebuild_from_captures_under_the_cache(isolated_paths, capsys):
    import shutil
    from pathlib import Path

    from tests import pins

    sample = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
    feed = by_name("fr-digital-first")  # a capture lives under platform/name
    shutil.copytree(
        sample, isolated_paths / feed.platform / feed.name / "2026-09-01T08-00-00"
    )
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
    from pipeline import cli

    blank = app_store_source(
        name="blank",
        app_id=0,
        country="fr",
        listing="",
        fetchable=True,
        declared_on="2026-09-01",
    )
    monkeypatch.setattr(cli, "SOURCES", (blank,))
    code = main(["scrape", "--confirm=yes", "--confirm-origin=command line"])
    assert code == 2
    err = capsys.readouterr().err
    assert "has no page address" in err


def test_cli_scrape_keeps_the_host_interval_across_sources(
    capsys, monkeypatch, isolated_paths
):
    """Two declared sources on one host in one run: the first request of the
    second source waits the full two seconds after the last of the first. One
    client, one per-host clock, for the whole `make scrape`."""
    import ingest.fetch as fetch
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    two = (
        app_store_source(
            name="one",
            app_id=1,
            country="fr",
            listing="https://a/id1",
            fetchable=True,
            declared_on="2026-09-01",
        ),
        app_store_source(
            name="two",
            app_id=2,
            country="fr",
            listing="https://a/id2",
            fetchable=True,
            declared_on="2026-09-01",
        ),
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
    """Fix amendment A2: the counts `rebuild ROWS=X` prints are X's own. The
    sample builds beside the corpus, never into it; `synthetic` leaves the
    corpus file absent; `reset` names every file it removed."""
    import pipeline.warehouse as warehouse
    from tests import pins

    corpus = warehouse.DEFAULT_DB
    assert main(["rebuild", "--rows=synthetic"]) == 0
    assert _count(capsys.readouterr().out, "raw_reviews") == 40
    assert not corpus.exists()
    assert main(["rebuild", "--rows=samples"]) == 0
    assert _count(capsys.readouterr().out, "raw_reviews") == pins.SAMPLES_RAW_REVIEWS
    assert main(["rebuild"]) == 0  # the cache, empty here
    assert _count(capsys.readouterr().out, "raw_reviews") == 0
    files = {corpus.with_name(f"w.{f}.duckdb") for f in ("synthetic", "samples")}
    assert corpus.exists() and all(f.exists() for f in files)
    assert main(["rebuild", "--rows=samples"]) == 0  # again: the same, not double
    assert _count(capsys.readouterr().out, "raw_reviews") == pins.SAMPLES_RAW_REVIEWS
    assert main(["reset", "--confirm=yes", "--confirm-origin=command line"]) == 0
    out = capsys.readouterr().out
    assert not corpus.exists() and not any(f.exists() for f in files)
    assert all(str(f) in out for f in files | {corpus})


def test_reset_removes_every_database_this_repo_built_past_or_present(
    capsys, isolated_paths
):
    """`reset` drops the corpus and every `<stem>.<input>.duckdb` beside it —
    including files an earlier phase's input names left behind (`app-store`,
    `empty`), which a list drawn from today's INPUTS would keep — and their
    write-ahead logs; a neighbour that is not ours is untouched (round 1,
    functionality-tester F5)."""
    import pipeline.warehouse as warehouse

    corpus = warehouse.DEFAULT_DB
    ours = [corpus, corpus.with_name(corpus.name + ".wal")] + [
        corpus.with_name(f"{corpus.stem}.{name}{corpus.suffix}")
        for name in ("app-store", "empty", "synthetic", "samples")
    ]
    theirs = [corpus.with_name("other.duckdb"), corpus.with_name(f"{corpus.stem}.txt")]
    for p in ours + theirs:
        p.write_text("x")
    assert main(["reset", "--confirm=yes", "--confirm-origin=command line"]) == 0
    out = capsys.readouterr().out
    assert not any(p.exists() for p in ours)
    assert all(p.exists() for p in theirs)
    assert all(str(p) in out for p in ours)


def test_a_malformed_stored_page_is_a_one_line_refusal_from_rebuild(
    capsys, isolated_paths
):
    """Fix amendment A3: a hand-corrupted page-1.json under the cache makes
    `rebuild` and `idempotency-check` print one line naming the page and the
    field, exit 2, no traceback."""
    import shutil
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
    feed = by_name("fr-digital-first")
    d = isolated_paths / feed.platform / feed.name / "2026-09-01T08-00-00"
    shutil.copytree(sample, d)
    (d / "page-1.json").write_text('{"feed": {"entry": [{"id": "no label"}]}}')
    for argv in (["rebuild"], ["idempotency-check", "--rows=captured"]):
        assert main(argv) == 2
        err = capsys.readouterr().err
        assert err.startswith("refusing:") and err.count("\n") == 1
        assert "page=1/json" in err and "field" in err


def test_a_capture_holding_only_refused_pages_still_gets_the_no_captures_hint(
    capsys, isolated_paths
):
    """The hint and the reader share one rule for what a page is: a directory
    with only page-1.refused.json (a run refused at page 1) loads nothing and
    says so, rather than printing zero rows with no explanation."""
    feed = by_name("fr-digital-first")
    d = isolated_paths / feed.platform / feed.name / "2026-09-01T08-00-00"
    d.mkdir(parents=True)
    (d / "page-1.refused.json").write_text("{}")
    (d / "page-1.meta.json").write_text("{}")
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "no captures under" in out
    assert _count(out, "raw_reviews") == 0


def test_cli_scrape_on_the_declared_source_refuses_before_the_network(capsys):
    """`make scrape CONFIRM=yes SOURCE=<the feed>` today, on the real
    declaration: one line, exit 2, and no socket (the suite would raise on
    one). The terms position holds without a request."""
    code = main(
        [
            "scrape",
            "--source=fr-digital-first",
            "--confirm=yes",
            "--confirm-origin=command line",
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("refusing:") and "not fetchable" in err
    assert err.count("\n") == 1


def _two_sources():
    return (
        app_store_source(
            name="no",
            app_id=1,
            country="fr",
            listing="",
            fetchable=False,
            terms="asked",
            declared_on="2026-09-01",
        ),
        app_store_source(
            name="yes",
            app_id=2,
            country="fr",
            listing="",
            fetchable=True,
            declared_on="2026-09-01",
        ),
    )


def test_cli_scrape_skips_a_source_declared_not_fetchable_and_exits_0(
    capsys, monkeypatch, isolated_paths
):
    """A plain `make scrape CONFIRM=yes`: the source declared not fetchable is
    one stdout line naming its terms, no request is made for it, the next
    source is fetched, and the exit code is 0 — nothing was refused during the
    run (round 1, security-reviewer #3)."""
    import ingest.fetch as fetch
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    monkeypatch.setattr(cli, "SOURCES", _two_sources())
    code = main(["scrape", "--confirm=yes", "--confirm-origin=command line"])
    out, err = capsys.readouterr()
    assert code == 0
    assert err == ""
    assert "scrape: no: skipped — declared not fetchable: asked" in out
    assert out.count("scrape: yes:") == 1
    assert all("id=2/" in u for u in server.urls() if "rss" in u)


def test_cli_scrape_exits_2_only_on_a_refusal_met_during_the_run(
    capsys, monkeypatch, isolated_paths
):
    """The same two sources, the host now answering 500 on the fetchable one:
    one stderr line, exit 2. The skipped source is still not a refusal."""
    import ingest.fetch as fetch
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    server.page_status[1] = 500
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    monkeypatch.setattr(cli, "SOURCES", _two_sources())
    code = main(["scrape", "--confirm=yes", "--confirm-origin=command line"])
    out, err = capsys.readouterr()
    assert code == 2
    assert err.count("\n") == 1 and "returned 500" in err
    assert "scrape: no: skipped" in out and "scrape: yes:" not in out


def test_cli_scrape_naming_a_source_declared_not_fetchable_is_a_refusal(
    capsys, monkeypatch, isolated_paths
):
    """SOURCE=<a source declared not fetchable> asks for it on purpose: one
    stderr line, exit 2, no request."""
    import ingest.fetch as fetch
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    monkeypatch.setattr(cli, "SOURCES", _two_sources())
    code = main(
        ["scrape", "--source=no", "--confirm=yes", "--confirm-origin=command line"]
    )
    out, err = capsys.readouterr()
    assert code == 2
    assert err.count("\n") == 1 and "'no' is declared not fetchable" in err
    assert server.urls() == []
