"""The CLI behind `make` (pipeline/cli.py, pipeline/build.py::reset). Every
refused value is exit 2 and one line, never a traceback; `reset` handles only
the DuckDB file and deletes only it. Offline, temp file."""

from __future__ import annotations

import pytest

from ingest.sources import app_store_source, by_name
from pipeline.build import reset
from pipeline.cli import main

pytestmark = pytest.mark.slow  # slow: kept out of the fast edit-loop hook


@pytest.fixture(autouse=True)
def _stamp_in_tmp(tmp_path, monkeypatch):
    """The confirmation stamp lives under the repo's data/; tests write theirs
    in a temp dir."""
    import pipeline.cli as cli

    monkeypatch.setattr(cli, "CONFIRM_STAMP", tmp_path / ".confirm")


ORIGIN = "--goals-origin=default"  # what the recipe passes when make holds the list


def armed(argv: list[str]) -> int:
    """`make confirm <target>` as the CLI sees it: the stamp of make process 1,
    with the invocation's goal list, then the target with the same id
    (A4 (d), A8 (d))."""
    assert main(["confirm", "--make-pid=1", ORIGIN, f"--goals=confirm {argv[0]}"]) == 0
    return main([*argv, "--make-pid=1"])


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
    code = armed(["reset", "--target=snowflake"])
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
    assert "make confirm scrape" in out
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

    from tests import pins
    from tests.test_ingest_rebuild import _capture

    # a capture lives under platform/name, at the feed's declared addresses
    _capture(isolated_paths, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "no captures" not in out
    assert f"{'stg_reviews':24} {pins.APP_STORE_SAMPLE_STG_ROWS}" in out


def test_cli_scrape_refuses_without_the_confirm_goal(capsys, monkeypatch):
    """Non-interactive and unconfirmed — no stamp, or a stamp of another make
    process: one line, exit 2, no fetch attempted (conftest would raise on a
    socket; nothing is imported from the fetcher)."""
    import sys

    import pipeline.cli as cli

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    code = main(["scrape", "--make-pid=1"])
    assert code == 2
    out = capsys.readouterr().out
    assert "run `make confirm scrape`" in out and "nothing fetched" in out
    assert main(["confirm", "--make-pid=2", ORIGIN, "--goals=confirm scrape"]) == 0
    assert main(["scrape", "--make-pid=1"]) == 2
    assert not cli.CONFIRM_STAMP.exists()  # consumed by the refusal


def test_confirm_stamps_one_invocation_and_reset_consumes_it(capsys, isolated_paths):
    """A4 (d): `confirm` writes the make process id; `reset` with the same id
    is confirmed once and the stamp is gone; a missing stamp, another id or a
    non-numeric or non-ASCII-digit id refuses and deletes nothing."""
    import pipeline.cli as cli
    import pipeline.warehouse as warehouse

    assert main(["confirm", "--make-pid=x", ORIGIN, "--goals=confirm reset"]) == 2
    assert "not a process id" in capsys.readouterr().err
    # a non-ASCII digit is not a process id either: make_pid reads through the
    # shared is_ascii_decimal_integer shape, not str.isdigit (F8).
    assert main(["confirm", "--make-pid=٣", ORIGIN, "--goals=confirm reset"]) == 2
    assert "not a process id" in capsys.readouterr().err
    corpus = warehouse.DEFAULT_DB
    corpus.write_text("x")
    assert main(["reset", "--make-pid=1"]) == 2 and corpus.exists()  # no stamp
    goals = [ORIGIN, "--goals=confirm reset"]
    assert main(["confirm", "--make-pid=1", *goals]) == 0 and cli.CONFIRM_STAMP.exists()
    assert main(["reset", "--make-pid=2"]) == 2 and corpus.exists()  # another
    assert not cli.CONFIRM_STAMP.exists()  # consumed by the mismatch
    assert armed(["reset"]) == 0 and not corpus.exists()
    assert not cli.CONFIRM_STAMP.exists()
    corpus.write_text("x")
    assert main(["reset", "--make-pid=1"]) == 2 and corpus.exists()  # once only


def test_confirm_refuses_with_nothing_after_it_and_a_planted_stamp(capsys):
    """A8 (d): `confirm` as the last goal, or alone, arms nothing and leaves no
    stamp; a stamp already there makes `confirm` refuse naming it and leaves
    the file as it was; the stamp it does write is owner-only."""
    import os
    import stat

    import pipeline.cli as cli

    for goals in ("", "confirm", "reset confirm"):
        assert main(["confirm", "--make-pid=1", ORIGIN, f"--goals={goals}"]) == 2
        assert "nothing follows" in capsys.readouterr().err
        assert not cli.CONFIRM_STAMP.exists()
    cli.CONFIRM_STAMP.write_text("planted\n", encoding="utf-8")
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 2
    err = capsys.readouterr().err
    assert "already exists" in err and str(cli.CONFIRM_STAMP) in err
    assert cli.CONFIRM_STAMP.read_text(encoding="utf-8") == "planted\n"
    cli.CONFIRM_STAMP.unlink()
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 0
    mode = stat.S_IMODE(os.stat(cli.CONFIRM_STAMP).st_mode)
    assert mode == 0o600, oct(mode)


def test_confirm_arms_only_a_gated_goal_from_makes_own_list(
    capsys, isolated_paths, tmp_path
):
    """A9 (a): the goal after `confirm` is a member of a closed set, so
    `make confirm help` refuses and leaves no stamp — the typo A8 (d)'s
    trailing-goal check left open; the goal list is trusted only with make's
    own origin (`default`), so a MAKECMDGOALS definition from the
    environment, MAKEFLAGS or the command line confirms nothing; a gated
    target consumes the stamp before its own refusals; a stamp the process
    cannot write refuses with one line (round 5, findings 1–5)."""
    import os
    import stat

    import pipeline.cli as cli
    import pipeline.warehouse as warehouse

    for goal in ("help", "rebuild", "test", "probe"):
        assert main(["confirm", "--make-pid=1", ORIGIN, f"--goals=confirm {goal}"]) == 2
        err = capsys.readouterr().err
        assert "arms `reset` or `scrape`" in err and f"`{goal}` follows" in err
        assert not cli.CONFIRM_STAMP.exists()
    for origin in ("environment", "command line", "file", ""):
        code = main(
            [
                "confirm",
                "--make-pid=1",
                f"--goals-origin={origin}",
                "--goals=confirm reset",
            ]
        )
        assert code == 2
        assert "did not come from make itself" in capsys.readouterr().err
        assert not cli.CONFIRM_STAMP.exists()
    for goal in ("reset", "scrape"):
        assert main(["confirm", "--make-pid=1", ORIGIN, f"--goals=confirm {goal}"]) == 0
        assert cli.CONFIRM_STAMP.exists()
        cli.CONFIRM_STAMP.unlink()
    # A gated target's own refusal consumes the stamp first: a refused TARGET
    # after `confirm` leaves nothing armed.
    corpus = warehouse.DEFAULT_DB
    corpus.write_text("x")
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 0
    assert main(["reset", "--target=snowflake", "--make-pid=1"]) == 2
    assert "got 'snowflake'" in capsys.readouterr().err
    assert not cli.CONFIRM_STAMP.exists() and corpus.exists()
    # The stamp cannot be written: one line, exit 2, no traceback.
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        cli.CONFIRM_STAMP = ro / ".confirm"
        if os.access(ro, os.W_OK):  # root ignores modes: nothing to prove here
            pytest.skip("the directory is writable despite its mode")
        assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 2
        err = capsys.readouterr().err
        assert "cannot write the confirmation stamp" in err and "\n" not in err.strip()
    finally:
        ro.chmod(stat.S_IRWXU)


def test_cli_scrape_refuses_a_bad_source_with_exit_2(capsys):
    code = armed(["scrape", "--source=../x"])
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
    code = armed(["scrape"])
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
    code = armed(["scrape"])
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
    assert armed(["reset"]) == 0
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
    assert armed(["reset"]) == 0
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

    from tests.test_ingest_rebuild import _capture

    d = _capture(isolated_paths, "2026-09-01T08-00-00", "2026-09-01T08:00:00")
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
    """`make confirm scrape SOURCE=<the feed>` today, on the real
    declaration: one line, exit 2, and no socket (the suite would raise on
    one). The terms position holds without a request."""
    code = armed(["scrape", "--source=fr-digital-first"])
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
    """A plain `make confirm scrape`: the source declared not fetchable is
    one stdout line naming its terms, no request is made for it, the next
    source is fetched, and the exit code is 0 — nothing was refused during the
    run (round 1, security-reviewer #3)."""
    import ingest.fetch as fetch
    from pipeline import cli
    from tests.test_app_store_fetch import Clock, Served, _polite

    server, clock = Served(), Clock()
    monkeypatch.setattr(fetch, "polite_client", lambda: _polite(server, clock))
    monkeypatch.setattr(cli, "SOURCES", _two_sources())
    code = armed(["scrape"])
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
    code = armed(["scrape"])
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
    code = armed(["scrape", "--source=no"])
    out, err = capsys.readouterr()
    assert code == 2
    assert err.count("\n") == 1 and "'no' is declared not fetchable" in err
    assert server.urls() == []
    assert not cli.CONFIRM_STAMP.exists()  # consumed before the refusal (A9 (a))


def test_a_dangling_symlink_at_the_stamp_is_consumed_by_the_next_gated_run(capsys):
    """A link to nowhere at the stamp path makes `confirm` refuse (exclusive
    create) and used to be never consumed, wedging the gate until removed by
    hand; a gated run now consumes the stamp whatever its state, confirming
    nothing, so the next `confirm` works (exit pass, security-reviewer #4)."""
    import os

    import pipeline.cli as cli

    os.symlink(cli.CONFIRM_STAMP.parent / "nowhere", cli.CONFIRM_STAMP)
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 2
    assert "already exists" in capsys.readouterr().err
    assert main(["reset", "--make-pid=1"]) == 2  # confirms nothing
    assert not os.path.lexists(cli.CONFIRM_STAMP)  # and the link is gone
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm reset"]) == 0
    cli.CONFIRM_STAMP.unlink()


def test_model_error_is_one_line_exit_2(capsys, monkeypatch):
    """A model failure on the developer-run paid path surfaces as one line and
    exit 2, never a traceback (round 1, code-reviewer). The handler mirrors the
    Refused/PageShapeError catches; record-snapshots stands in as a hijacked
    command so no real model call or rebuild runs."""
    import pipeline.cli as cli

    def boom(_args):
        raise cli.ModelError("model call failed for s:1 (model claude-haiku-4-5): boom")

    monkeypatch.setattr(cli, "_do_record_snapshots", boom)
    assert main(["record-snapshots"]) == 2
    assert "refusing: model call failed" in capsys.readouterr().err
