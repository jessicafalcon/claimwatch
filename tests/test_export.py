"""Phase 9a — the render contract and Beat 1 (spec Invariants / Done-when).

The export renders one deterministic, self-contained HTML from the frozen
synthetic marts: a Pending panel shows no number; a Documented panel whose mart
is empty shows a "no data yet" state, not a blank; every rendered number carries
exactly one tag and equals its mart; charts are byte-stable, locale-independent
inline SVG with no CDN and no external asset. Beat 1's rendered figures are the
anchor pins in tests/pins.py."""

from __future__ import annotations

import locale
from datetime import date
from pathlib import Path

import pytest

from pipeline.warehouse import connect
from study import export, model, panels
from study.export import render, write
from study.model import (
    Panel,
    Point,
    RenderRefused,
    Series,
    check_panel,
    has_values,
)
from study.panels import beat1_panels
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: rebuilds a warehouse; out of the edit-loop hook


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory) -> Path:
    # The full study warehouse (rebuild + the classify step), so the render walks
    # all nine panels — Beat 2's theme marts and classifier_quality included.
    return build_study_db(tmp_path_factory.mktemp("study"), "synthetic")


@pytest.fixture(scope="module")
def none_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("study-none"), "none")


def _html(db: Path) -> str:
    conn = connect("duckdb", database=db)
    try:
        return render(conn)
    finally:
        conn.close()


def _panels(db: Path) -> list[Panel]:
    conn = connect("duckdb", database=db)
    try:
        return beat1_panels(conn)
    finally:
        conn.close()


def test_make_study_is_byte_identical_on_rerun(synthetic_db, tmp_path):
    a, b = tmp_path / "a.html", tmp_path / "b.html"
    write(synthetic_db, a)
    write(synthetic_db, b)
    assert a.read_bytes() == b.read_bytes()
    assert a.stat().st_size > 0


def test_export_has_no_cdn_no_external_asset_no_timestamp(synthetic_db):
    page = _html(synthetic_db)
    for asset in ("<script", " src=", "<link ", "stylesheet", "url(http"):
        assert asset not in page, asset
    # a link to a data source is an anchor, not a loaded asset — allowed.
    assert 'href="https://www.trustpilot.com/"' in page
    # no render timestamp: today's date never leaks into the bytes.
    assert date.today().isoformat() not in page


def test_a_pending_panel_renders_a_gray_placeholder_with_no_value(synthetic_db):
    b11 = next(p for p in _panels(synthetic_db) if p.id == "B1.1")
    assert b11.tag == "Pending"
    assert not has_values(b11)
    page = _html(synthetic_db)
    assert 'class="pending"' in page
    assert "Awaiting the curated public case" in page


def test_a_documented_panel_with_an_empty_mart_renders_no_data_yet(none_db):
    # Under ROWS=none the Beat 1 marts exist but hold no rows: a Documented panel
    # renders a distinct "no data yet" state, never a blank or a crash.
    page = _html(none_db)
    assert "No data yet" in page
    b12 = next(p for p in _panels(none_db) if p.id == "B1.2")
    assert b12.tag == "Documented"
    assert not has_values(b12)


def test_a_pending_panel_with_a_value_is_refused_one_line_nonzero():
    bad = Panel(
        id="B9.9",
        backing_row="B9.9",
        title="t",
        blurb="b",
        tag="Pending",
        kind="line",
        series=(Series("s", 0, (Point("2025-01", 4.2, "Pending", "https://x/", ""),)),),
    )
    with pytest.raises(RenderRefused) as exc:
        check_panel(bad)
    assert "B9.9" in str(exc.value)
    assert "\n" not in str(exc.value)  # one line


def test_a_panel_with_no_tag_or_two_tags_is_refused():
    for bad_tag in ("", "Documented,Measured", "Guessed"):
        panel = Panel("B9.9", "B9.9", "t", "b", bad_tag, "hero")
        with pytest.raises(RenderRefused):
            check_panel(panel)
    with_bad_point = Panel(
        "B9.8",
        "B9.8",
        "t",
        "b",
        "Documented",
        "line",
        series=(Series("s", 0, (Point("m", 1.0, "Nope", "https://x/", "stars"),)),),
    )
    with pytest.raises(RenderRefused):
        check_panel(with_bad_point)


def test_every_panel_renders_its_backing_row_id_and_source_link(synthetic_db):
    page = _html(synthetic_db)
    # Nine panels after the split: Beat 1's four and Beat 2's five.
    for pid in ("B1.1", "B1.2", "B1.3", "B1.4", "B2.1", "B2.2", "B2.3", "B2.4", "B2.5"):
        assert f"Evidence: {pid}" in page
    assert "PROJECT_BRIEF §6" in page
    assert 'href="https://www.trustpilot.com/"' in page


def test_the_brief_citation_follows_the_documented_points_not_the_urls():
    # §6 is named exactly when a Documented anchor is drawn; a Measured panel over
    # the platform roots cites the roots alone, as BACKING B2.2/B2.5 do (exit
    # round, code-reviewer #1).
    def panel(tag):
        return Panel(
            "B9.3",
            "B9.3",
            "t",
            "b",
            tag,
            "line",
            series=(Series("s", 0, (Point("m", 1.0, tag, "", "pct"),)),),
            sources=("https://www.trustpilot.com/",),
        )

    measured = export._drill(panel("Measured"))
    documented = export._drill(panel("Documented"))
    assert (
        measured
        == 'opens to <a href="https://www.trustpilot.com/" rel="noopener">https://www.trustpilot.com/</a>'
    )
    assert documented == measured + " and PROJECT_BRIEF §6"


def test_a_panel_source_is_an_address_or_a_repository_file_else_refused():
    # Authored panel-level sources have a closed shape: an http(s) link, or a
    # repository file named in plain text (never a link); anything else refuses
    # by name. B2.4's answer key exists (exit round, coherence #2).
    from pipeline.warehouse import ROOT
    from study.panels import ANSWER_KEY_FILE

    assert (ROOT / ANSWER_KEY_FILE).is_file()

    def panel(sources, fixture=""):
        return Panel(
            "B9.4",
            "B9.4",
            "t",
            "b",
            "Measured",
            "table",
            series=(Series("s", 0, (Point("m", 1.0, "Measured", "", "pct"),)),),
            sources=sources,
            fixture=fixture,
        )

    drilled = export._drill(panel((ANSWER_KEY_FILE,)))
    assert drilled == f"opens to the repository file {ANSWER_KEY_FILE}"
    assert "href" not in drilled
    for bad in ("../secrets", "/etc/passwd", "javascript:alert(1)", "a b"):
        with pytest.raises(RenderRefused) as exc:
            export._drill(panel((bad,)))
        assert "B9.4" in str(exc.value)
    # over a fixture input the footer says where the figures WILL open.
    fixture = export._drill(panel(("https://x.example/",), fixture="fixture text"))
    assert fixture.startswith("the counted figures will open to ")


def test_svg_numbers_are_fixed_precision_and_locale_independent(synthetic_db):
    base = _html(synthetic_db)
    assert "48.00" in base  # a coordinate at fixed 2-decimal precision
    saved = locale.setlocale(locale.LC_ALL)  # restore the exact prior setting
    picked = None
    try:
        for name in ("de_DE.UTF-8", "fr_FR.UTF-8"):
            try:
                locale.setlocale(locale.LC_ALL, name)
                picked = name
                break
            except locale.Error:
                continue
        if picked is None:
            pytest.skip("no comma-decimal locale available")
        under_comma_locale = _html(synthetic_db)
    finally:
        locale.setlocale(locale.LC_ALL, saved)
    assert under_comma_locale == base


def test_beat1_panels_render_each_point_with_its_own_tag(synthetic_db):
    page = _html(synthetic_db)
    # B1.2 rating trend: each point tagged Documented, values the anchor pins.
    for month, rating in pins.RATING_TREND_DIGITAL_FIRST:
        assert f"{month}: {rating}★ (Documented)" in page
    # B1.3 channel gap: each bar tagged, ratings equal the mart pins (no recompute).
    gap = next(p for p in _panels(synthetic_db) if p.id == "B1.3")
    got = {p.label: p.value for s in gap.series for p in s.points}
    for (_, source), (rating, _, _) in pins.CHANNEL_GAP_DIGITAL_FIRST.items():
        assert got[source] == float(rating)
    # B1.4 stat row: values equal the mart pins.
    b14 = next(p for p in _panels(synthetic_db) if p.id == "B1.4")
    stat = {p.label: p.value for s in b14.series for p in s.points}
    oa = pins.PLATFORM_STATS_OPINION_ASSURANCES
    assert stat["One-star share"] == float(oa["one_star_share"])
    assert stat["Reviews"] == float(oa["review_count"])
    assert stat["Reviews answered"] == float(
        oa["response_rate"]
    )  # 0.820, round 2 CR#18
    assert ">534<" in page and ">23.1%<" in page and ">1.5 days<" in page
    assert ">82.0%<" in page  # response_rate rendered as a percent (round 2, CR#18)


def test_a_mixed_documented_measured_panel_names_both_tags():
    # A panel whose points carry two distinct valid tags shows a chip per tag in
    # the header and names both in the footer evidence line — the round-1
    # caller-sourced fix (both derived from _panel_tags), now pinned (round 2,
    # CR#17). Synthetic Beat 1 carries Documented points only.
    panel = Panel(
        "B9.3",
        "B9.3",
        "t",
        "b",
        "Documented",
        "stat_row",
        series=(
            Series(
                "s",
                0,
                (
                    Point("a", 1.0, "Documented", "https://a/", "count"),
                    Point("b", 2.0, "Measured", "https://b/", "count"),
                ),
            ),
        ),
    )
    page = "\n".join(export._render_panel(panel))
    assert "chip chip-documented" in page and "chip chip-measured" in page
    assert "Measured, Documented" in page  # footer names both, in TAGS order


def test_a_label_with_markup_is_escaped_in_the_svg_title():
    # Every value that reaches the HTML is escaped, including a point label in
    # the line-chart <title> (round 1, security #2).
    panel = Panel(
        "B9.1",
        "B9.1",
        "t",
        "b",
        "Documented",
        "line",
        series=(
            Series(
                "s", 0, (Point("<b>&2025", 4.0, "Documented", "https://x/", "stars"),)
            ),
        ),
    )
    svg = "\n".join(export._render_line(panel))
    assert "<b>&2025" not in svg
    assert "&lt;b&gt;&amp;2025" in svg


def test_drill_drops_a_non_http_source_url():
    # A non-http(s) scheme is never rendered as a clickable href (round 1,
    # security #16).
    panel = Panel(
        "B9.2",
        "B9.2",
        "t",
        "b",
        "Documented",
        "stat_row",
        series=(
            Series(
                "s", 0, (Point("x", 1.0, "Documented", "javascript:alert(1)", "count"),)
            ),
        ),
    )
    drilled = export._drill(panel)
    assert "javascript:" not in drilled and "href" not in drilled
    assert drilled == "opens to PROJECT_BRIEF §6"  # the Documented anchor's own source


def _rating_trend_conn(rows: list[tuple]):
    conn = connect("duckdb", database=":memory:")
    conn.execute(
        "create table rating_trend("
        "channel varchar, segment varchar, source varchar, profile varchar, "
        "month varchar, rating double, tag varchar, source_url varchar)"
    )
    conn.executemany("insert into rating_trend values (?,?,?,?,?,?,?,?)", rows)
    return conn


def test_rating_trend_orders_multi_source_points_deterministically():
    # Two unsolicited sources carrying a rating in the same profile+month: the
    # order-by closes on `source`, so the two points append in a fixed order —
    # not the engine's — and the bytes stay stable (round 2, CR#16). Insertion
    # order is zeta-then-alpha; the render must return alpha-then-zeta.
    rows = [
        (
            "unsolicited",
            "digital-first",
            "zeta",
            "fr-digital-first",
            "2025-01",
            3.0,
            "Documented",
            "https://z/",
        ),
        (
            "unsolicited",
            "digital-first",
            "alpha",
            "fr-digital-first",
            "2025-01",
            4.0,
            "Documented",
            "https://a/",
        ),
    ]
    conn = _rating_trend_conn(rows)
    try:
        (line,) = panels._rating_trend(conn)
    finally:
        conn.close()
    assert [p.value for p in line.points] == [4.0, 3.0]


def test_render_chip_class_is_a_closed_lookup_not_a_raw_tag():
    # The class attribute is derived from the closed tag→class map, safe by
    # construction; a tag outside the four is refused by name, never reflected
    # into the attribute on the trust that a caller validated it (round 2, SR#4).
    assert export._render_chip("Pending") == (
        '<span class="chip chip-pending">Pending</span>'
    )
    with pytest.raises(RenderRefused):
        export._render_chip('"><script>')


def test_a_null_mart_cell_is_refused_by_name_not_a_traceback():
    # A null value or provenance cell is refused in one line naming the column
    # and panel, never coerced into an uncaught float(None)/None.startswith that
    # escapes render (round 2, SR#5).
    assert model._require(4.2, "rating", "B1.2") == 4.2
    with pytest.raises(RenderRefused) as exc:
        model._require(None, "rating", "B1.2")
    assert "rating" in str(exc.value) and "B1.2" in str(exc.value)
    null_rating = [
        (
            "unsolicited",
            "digital-first",
            "alpha",
            "fr-digital-first",
            "2025-01",
            None,
            "Documented",
            "https://a/",
        ),
    ]
    conn = _rating_trend_conn(null_rating)
    try:
        with pytest.raises(RenderRefused) as exc:
            panels._rating_trend(conn)
    finally:
        conn.close()
    assert "rating" in str(exc.value)


def test_b1_2_renders_the_sampling_bias_note(synthetic_db):
    assert "negatively self-selected" in _html(synthetic_db)


def test_b1_4_states_the_response_comparison_waits(synthetic_db):
    assert "comparison across platforms waits" in _html(synthetic_db)


def test_main_exports_over_the_module_defaults(monkeypatch, tmp_path, synthetic_db):
    from study import __main__

    out = tmp_path / "friction_ledger.html"
    # One binding: __main__ references export.DEFAULT_DB, so patching the module
    # attribute is enough — no second binding to keep in sync (round 1, CR#13).
    monkeypatch.setattr(export, "DEFAULT_DB", synthetic_db)
    monkeypatch.setattr(export, "OUTPUT", out)
    assert __main__.main(["export"]) == 0
    assert out.is_file() and out.read_text(encoding="utf-8").startswith("<!doctype")
    assert __main__.main(["nope"]) == 2  # a bad usage is refused, non-zero


def test_main_refuses_a_missing_warehouse_exit_1(monkeypatch, tmp_path, capsys):
    from study import __main__

    monkeypatch.setattr(export, "DEFAULT_DB", tmp_path / "nope.duckdb")
    assert __main__.main(["export"]) == 1
    assert "no synthetic warehouse" in capsys.readouterr().err


def test_main_refuses_a_render_breach_one_line_exit_2(
    monkeypatch, synthetic_db, capsys
):
    from study import __main__

    monkeypatch.setattr(export, "DEFAULT_DB", synthetic_db)

    def boom(*_a, **_k):
        raise export.RenderRefused("B1.1: a Pending panel shows no number")

    monkeypatch.setattr(export, "write", boom)
    assert __main__.main(["export"]) == 2
    err = capsys.readouterr().err
    assert "B1.1" in err and err.count("\n") == 1  # one line naming the panel


def test_main_refuses_an_unreadable_warehouse_exit_2(monkeypatch, synthetic_db, capsys):
    from pipeline.warehouse import DriverError
    from study import __main__

    monkeypatch.setattr(export, "DEFAULT_DB", synthetic_db)

    def boom(*_a, **_k):
        raise DriverError("catalog error")

    monkeypatch.setattr(export, "write", boom)
    assert __main__.main(["export"]) == 2
    assert "could not be read" in capsys.readouterr().err
