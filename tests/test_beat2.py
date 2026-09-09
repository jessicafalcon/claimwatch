"""Phase 9b — Beat 2: the corpus gate, the counted band, the trail, the table
(spec Invariants / Done-when). The committed baseline shows the fixture state
for the corpus panels, so these tests do what the bytes cannot: they render over
a test-owned copy of the synthetic DB whose `run_id` is rewritten to `captured`,
prove every value equals its mart, exercise the gate's refusals directly, and
pin the render fragments per kind."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from pipeline.build import INPUTS
from pipeline.sql_lint import find_clock, find_nonportable
from pipeline.warehouse import connect
from study import export, panels
from study.model import (
    NEUTRAL,
    Panel,
    Point,
    RenderRefused,
    Series,
    check_panel,
    has_content,
)
from study.panels import ALLOWED_COLUMNS, STUDY_QUERIES, beat1_panels, beat2_panels
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: builds a warehouse; out of the edit-loop hook

# Display name -> label slug, so a rendered series can be matched to its mart row.
_LABEL_OF = {name: label for label, name in panels._LABEL_NAMES.items()}


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat2-syn"), "synthetic")


@pytest.fixture(scope="module")
def none_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat2-none"), "none")


@pytest.fixture(scope="module")
def captured_db(tmp_path_factory, synthetic_db) -> Path:
    # A test-owned copy of the synthetic warehouse with the corpus marts' run_id
    # relabelled `captured` — same figures, so the corpus panels render numbers.
    dst = tmp_path_factory.mktemp("beat2-cap") / "captured.duckdb"
    shutil.copy(synthetic_db, dst)
    con = duckdb.connect(str(dst))
    try:
        for mart in panels._CORPUS_MARTS:  # the export's own list, not a copy
            con.execute(f"update {mart} set run_id = 'captured'")
    finally:
        con.close()
    return dst


def _panels(db: Path) -> list[Panel]:
    conn = connect("duckdb", database=db)
    try:
        return beat2_panels(conn)
    finally:
        conn.close()


def _panel(db: Path, pid: str) -> Panel:
    return next(p for p in _panels(db) if p.id == pid)


def _html(db: Path) -> str:
    conn = connect("duckdb", database=db)
    try:
        return export.render(conn)
    finally:
        conn.close()


def _section(page: str, pid: str) -> str:
    end = page.index(f"Evidence: {pid}")
    start = page.rfind("<section", 0, end)
    return page[start : page.index("</section>", end)]


def _legend(section: str) -> str:
    """The `<ul class="legend">` block of one rendered panel section."""
    start = section.index('<ul class="legend">')
    return section[start : section.index("</ul>", start) + len("</ul>")]


def _fixture_body(page: str, pid: str) -> str:
    sec = _section(page, pid)
    start = sec.index('<div class="fixture">')
    return sec[start : sec.index("</div>", start)]


def _mart(db: Path, sql: str) -> list[tuple]:
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _gate_conn(run_ids: list[str]):
    """An in-memory `theme_share_by_month` carrying the given run_id values, to
    exercise the corpus gate directly."""
    conn = connect("duckdb", database=":memory:")
    conn.execute("create table theme_share_by_month(run_id varchar)")
    for run_id in run_ids:
        conn.execute("insert into theme_share_by_month values (?)", [run_id])
    return conn


def test_the_cli_binds_the_file_it_builds_to_the_run_id_it_classifies_under(
    monkeypatch,
):
    # The gate reads run_id off the mart; that value is what `make rebuild`
    # stamped. The binding — the file `database_for(rows)` is the one the classify
    # step stamps `run_id = rows` — lives in the CLI alone, so pin it there: every
    # writer patched out, no data/ write (challenge round 2, #6).
    import argparse

    from pipeline import cli

    calls: list[tuple] = []

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(cli, "rebuild", lambda target, rows: {})
    monkeypatch.setattr(cli, "connect", lambda target, database: _Conn())
    monkeypatch.setattr(cli, "reviews_per_month", lambda conn: [])
    monkeypatch.setattr(
        cli, "_classify_and_print", lambda db, rows: calls.append((db, rows))
    )
    for rows in ("synthetic", "samples", "none"):  # captured needs pages on disk
        args = argparse.Namespace(target="duckdb", rows=rows)
        assert cli._do_rebuild(args) == 0
        assert calls[-1] == (cli.database_for(rows), rows)
    # and the classify step writes that very value: over a built warehouse each
    # corpus mart carries run_id = rows (the conftest path mirrors _do_rebuild).


def test_each_corpus_mart_carries_the_input_it_was_built_from(synthetic_db):
    for mart in panels._CORPUS_MARTS:
        assert _mart(synthetic_db, f"select distinct run_id from {mart}") == [
            ("synthetic",)
        ], mart


# --- Done-when 1: the honest baseline -----------------------------------------
def test_b2_1_renders_the_pending_placeholder_with_no_value(synthetic_db):
    b21 = _panel(synthetic_db, "B2.1")
    assert b21.tag == "Pending"
    assert not any(p.value is not None for s in b21.series for p in s.points)
    page = _html(synthetic_db)
    assert "Awaiting the five themes" in _section(page, "B2.1")


def test_b2_3_labels_each_point_by_platform_and_states_placed_points(synthetic_db):
    b23 = _panel(synthetic_db, "B2.3")
    assert b23.tag == "Documented"
    by_short = {p.label: p for s in b23.series for p in s.points}
    for profile, (rating, count) in pins.BEAT2_PEER_RATINGS.items():
        point = by_short[panels._PROFILE_SHORT[profile]]  # short axis label
        assert point.value == rating
        assert panels._PROFILE_NAMES[profile] in point.detail  # full name in tooltip
        assert "on trustpilot" in point.detail  # labelled by platform
        if count is None:
            assert "reviews" not in point.detail  # a missing count renders blank
        else:
            assert f"{count:,} reviews" in point.detail
    page = _html(synthetic_db)
    assert "Placed points" in _section(page, "B2.3")
    # _PROFILE_NAMES covers the four anchor profiles; an unknown one refuses.
    assert set(pins.BEAT2_PEER_RATINGS) <= set(panels._PROFILE_NAMES)
    with pytest.raises(RenderRefused):
        panels._profile_name("brand-x")


def test_corpus_panels_render_the_fixture_state_over_synthetic(synthetic_db):
    page = _html(synthetic_db)
    for pid in ("B2.2", "B2.4", "B2.5"):
        sec = _section(page, pid)
        assert 'class="fixture"' in sec  # distinct from Pending and "no data yet"
        assert 'class="pending"' not in sec and 'class="nodata"' not in sec
        body = _fixture_body(page, pid)
        assert "hand-written example reviews" in body
        assert not any(ch.isdigit() for ch in body), (pid, body)  # no number


def test_a_fixture_state_panel_with_content_is_refused():
    # The contract, not the builder: a panel carrying both fixture text and a
    # value (or a declared absence) is refused in one line naming the panel, as
    # Pending-with-value is (challenge round 2 amendment). Fixture text with
    # empty series — the committed state — passes.
    def panel(points):
        return Panel(
            "B2.9",
            "B2.9",
            "t",
            "b",
            "Measured",
            "line",
            series=(Series("x", 0, points),),
            fixture=panels._FIXTURE_NOTE,
            domain=(0.0, 1.0),
        )

    check_panel(panel(()))
    value = Point("m", 0.5, "Measured", "", "pct")
    absence = Point("m", None, "Measured", "", "pct", absent="no held-out case")
    for content in (value, absence):
        with pytest.raises(RenderRefused) as exc:
            check_panel(panel((content,)))
        assert "B2.9" in str(exc.value) and "\n" not in str(exc.value)


# --- Done-when 2: the corpus gate is data ------------------------------------
def test_the_corpus_gate_reads_run_id_from_the_mart():
    assert set(INPUTS) == {"captured", "none", "synthetic", "samples"}
    # the gate's state mapping is closed over exactly the inputs (no default arm).
    assert set(panels._STATE_OF_INPUT) == set(INPUTS)

    # captured → numbers; a fixture input → the fixture state; none/empty → nodata.
    def build():
        return (Series("x", 0, (Point("m", 0.5, "Measured", "", "pct"),)),)

    cases = {
        "captured": (True, ""),
        "synthetic": (False, panels._FIXTURE_NOTE),
        "samples": (False, panels._FIXTURE_NOTE),
        "none": (False, ""),
    }
    for run_id, (has_series, fixture) in cases.items():
        conn = _gate_conn([run_id])
        try:
            series, fx = panels._corpus_series(
                conn, "theme_share_by_month", "B2.2", build
            )
        finally:
            conn.close()
        assert bool(series) == has_series and fx == fixture, run_id
    # an empty mart (no rows) → no data yet
    conn = _gate_conn([])
    try:
        assert panels._corpus_input(conn, "theme_share_by_month", "B2.2") is None
    finally:
        conn.close()
    # over ROWS=none the mart does not exist at all — still no data yet, no crash.
    conn = connect("duckdb", database=":memory:")
    try:
        assert panels._corpus_input(conn, "theme_share_by_month", "B2.2") is None
    finally:
        conn.close()


def test_two_run_ids_or_one_outside_inputs_refuse_one_line():
    conn = _gate_conn(["synthetic", "captured"])
    try:
        with pytest.raises(RenderRefused) as exc:
            panels._corpus_input(conn, "theme_share_by_month", "B2.2")
    finally:
        conn.close()
    assert "B2.2" in str(exc.value) and "\n" not in str(exc.value)
    conn = _gate_conn(["bogus"])
    try:
        with pytest.raises(RenderRefused) as exc:
            panels._corpus_input(conn, "theme_share_by_month", "B2.2")
    finally:
        conn.close()
    assert "B2.2" in str(exc.value) and "bogus" in str(exc.value)


# --- Done-when 3: values equal the marts; the band is counted -----------------
def test_beat2_values_equal_their_marts_over_a_captured_run_id(captured_db):
    seg = {
        label: (reviews, theme_rows, share, tag)
        for label, reviews, theme_rows, share, tag in _mart(
            captured_db,
            "select label, reviews, theme_rows, share, tag "
            "from theme_share_by_segment order by label",
        )
    }
    b25 = _panel(captured_db, "B2.5")
    drawn = {}
    for s in b25.series:
        label = _label_of(s)
        drawn[label] = s
        for point in s.points:
            reviews, theme_rows, share, tag = seg[label]
            assert point.value == float(share)  # value equals its mart
            assert point.tag == tag  # and so does its tag (round 2, CR#1)
            assert point.detail == f"{int(theme_rows)} of {int(reviews)} reviews"
    assert pins.BEAT2_POSITIVE_EXCLUDED not in drawn  # positive is not a bar
    # B2.4's cells carry the classifier_quality row's tag, value or absence alike.
    quality_tag = {
        label: tag
        for label, tag in _mart(
            captured_db, "select label, tag from classifier_quality order by label"
        )
    }
    b24 = _panel(captured_db, "B2.4")
    assert b24.series  # the table renders over a captured input
    for s in b24.series:
        for cell in s.points:
            assert cell.tag == quality_tag[_LABEL_OF[s.name]]
    # the pinned theme_rows behind each drawn bar
    for label, theme_rows in pins.BEAT2_SEGMENT_BARS.items():
        assert seg[label][1] == theme_rows


def test_the_unclassified_band_is_the_neutral_token_and_always_in_the_legend(
    captured_db,
):
    b22 = _panel(captured_db, "B2.2")
    band = next(s for s in b22.series if s.colour == NEUTRAL)
    rows = {
        month: (reviews, theme_rows)
        for month, reviews, theme_rows in _mart(
            captured_db,
            "select month, reviews, theme_rows from theme_share_by_month "
            "where segment = 'digital-first' and label = 'unclassified' "
            "order by month",
        )
    }
    for point in band.points:
        reviews, theme_rows = rows[point.label]
        assert point.value == float(theme_rows) / float(reviews)
        assert point.detail == f"{int(theme_rows)} of {int(reviews)} reviews"
    total = sum(theme_rows for _, theme_rows in rows.values())
    assert band.name == f"Not yet classified ({total})"  # counted in the legend
    # The render mapping is pinned on the function and on the band's own legend
    # swatch inside the panel — not on the page, whose `.fixture` CSS carries
    # `var(--sN)` unconditionally (round 2, functionality-tester F1).
    assert export._series_var(NEUTRAL) == "var(--sN)"
    assert [export._series_var(slot) for slot in range(5)] == [
        f"var(--s{slot})" for slot in range(5)
    ]
    legend = _legend(_section(_html(captured_db), "B2.2"))
    assert (
        f'<span class="swatch" style="background:var(--sN)"></span>'
        f"Not yet classified ({total})</li>" in legend
    )
    # an empty band still appears in the legend, at zero — never hidden.
    empty = panels._theme_series(
        [("2026-01", "document-loop", 10, 3, 0.3, "Measured")], "B2.9", "period"
    )
    band0 = next(s for s in empty if s.colour == NEUTRAL)
    assert band0.name == "Not yet classified (0)" and band0.points == ()
    # a series colour outside the closed choice refuses by name.
    for bad in (5, -1, "purple"):
        with pytest.raises(RenderRefused):
            export._series_var(bad)


def test_a_band_only_panel_still_lists_the_band_in_the_legend():
    # A corpus the rules sort into positive/unclassified alone leaves one series
    # — the band — and the legend still names it with its count (invariant 3:
    # never hidden; round 2, code-reviewer #2). A one-series Beat 1 panel keeps
    # no legend.
    rows = [
        ("2026-01", "positive", 10, 3, 0.3, "Measured"),
        ("2026-01", "unclassified", 10, 7, 0.7, "Measured"),
    ]
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Measured",
        "line",
        series=panels._theme_series(rows, "B2.9", "period"),
        domain=(0.0, 1.0),
    )
    check_panel(panel)
    assert len(panel.series) == 1
    legend = "\n".join(export._render_legend(panel))
    assert 'style="background:var(--sN)"></span>Not yet classified (7)' in legend
    one = Panel(
        "B1.9",
        "B1.9",
        "t",
        "b",
        "Measured",
        "line",
        series=(Series("x", 0, (Point("m", 0.5, "Measured", "", "pct"),)),),
        domain=(0.0, 1.0),
    )
    assert export._render_legend(one) == []


def test_b2_2_plots_each_share_against_the_axis_not_stacked():
    # A cell whose shares sum past 1 (three themes, each 0.6) plots every point at
    # its own share — no cumulative stack — so the y of each is _y_of(0.6).
    rows = [
        ("2026-01", "document-loop", 10, 6, 0.6, "Measured"),
        ("2026-01", "silent-rejection", 10, 6, 0.6, "Measured"),
        ("2026-01", "second-payer", 10, 6, 0.6, "Measured"),
    ]
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Measured",
        "line",
        series=panels._theme_series(rows, "B2.9", "period"),
        domain=(0.0, 1.0),
    )
    check_panel(panel)
    for s in panel.series:
        for point in s.points:
            if point.value is not None:
                assert point.value == 0.6  # the share itself, never a running sum
    svg = "\n".join(export._render_line(panel))
    assert svg.count(f"{export._y_of(0.6, (0.0, 1.0)):.2f}") >= 3


def test_positive_rows_are_excluded_from_the_theme_series_and_stated(captured_db):
    rows = _mart(
        captured_db,
        "select segment, label, reviews, theme_rows, share, tag from "
        "theme_share_by_segment order by label",
    )
    series = panels._theme_series(rows, "B2.5", "theme")
    assert all(_label_of(s) != pins.BEAT2_POSITIVE_EXCLUDED for s in series)
    page = _html(captured_db)
    # the denominator (positive included) is stated beside the chart.
    assert "positive reviews included in the total" in _section(page, "B2.5")


def test_reviews_and_theme_rows_render_beside_each_share(captured_db):
    b22 = _section(_html(captured_db), "B2.2")  # the panel, never the whole page
    # document-loop's monthly counts ride on each point as "theme_rows of reviews".
    for month, theme_rows in pins.BEAT2_MONTH_DOCUMENT_LOOP.items():
        reviews = pins.THEME_SHARE_BY_MONTH_REVIEWS[month]
        assert f"{theme_rows} of {reviews} reviews" in b22


# --- Done-when 4: the column allowlist ----------------------------------------
def test_every_export_query_projects_only_allowlisted_columns(captured_db):
    assert "title" not in ALLOWED_COLUMNS and "body" not in ALLOWED_COLUMNS
    conn = connect("duckdb", database=captured_db)
    try:
        for sql in STUDY_QUERIES:
            projected = [d[0] for d in conn.execute(sql).description]
            assert set(projected) <= ALLOWED_COLUMNS, sql
        # select * over the review corpus fails by name (title/body are blocked).
        with pytest.raises(RenderRefused) as exc:
            panels._rows(conn, "select * from stg_reviews")
    finally:
        conn.close()
    assert "non-allowlisted" in str(exc.value)
    # STUDY_QUERIES excludes `_mart_exists`'s catalog probe by design: it projects
    # a literal `1` (no data column), so no review text can leak, and its mart
    # name comes from the hardcoded `_CORPUS_MARTS` tuple (round 1, code-reviewer).


class _Recording:
    """A connection wrapper that records every SQL text `execute` receives, so
    a render's queries are read off the connection, not off a hand-kept list."""

    def __init__(self, conn):
        self._conn = conn
        self.seen: list[str] = []

    def execute(self, sql: str, *args, **kwargs):
        self.seen.append(sql)
        return self._conn.execute(sql, *args, **kwargs)


# The catalog reads a render runs beside STUDY_QUERIES: the mart probe and the
# engine's schema (pipeline/warehouse.py::default_schema). Both project no data
# column; every other query must be a listed study query.
_CATALOG_READS = frozenset({panels._MART_PROBE, "select current_schema()"})


def test_every_query_the_export_runs_is_a_listed_study_query(captured_db):
    # Invariant 5's for-all is over the queries the export RUNS, so a reader that
    # bypasses `_rows` (a direct `conn.execute("select body …")`) must fail by
    # name — recorded on the connection, not asserted over STUDY_QUERIES alone
    # (challenge round 2, #1).
    conn = _Recording(connect("duckdb", database=captured_db))
    try:
        page = export.render(conn)
    finally:
        conn._conn.close()
    assert "Evidence: B2.5" in page  # a full render, both beats
    unlisted = [
        sql for sql in conn.seen if sql not in set(STUDY_QUERIES) | _CATALOG_READS
    ]
    assert unlisted == [], unlisted
    assert set(STUDY_QUERIES) <= set(conn.seen)  # and every listed query ran


def test_every_study_query_passes_the_sql_lint():
    for sql in STUDY_QUERIES:
        assert find_nonportable(sql) == [], sql
        assert find_clock(sql) == [], sql


# --- Done-when 5: value xor declared absence ----------------------------------
def test_a_zero_denominator_metric_renders_a_labelled_absence_with_its_counts(
    captured_db,
):
    b24 = _panel(captured_db, "B2.4")
    cells = {}
    for s in b24.series:
        precision, recall = s.points
        cells[_LABEL_OF[s.name]] = (precision, recall)
    # support-traction and coverage-price carry no held-out case: absence + count.
    for label in ("support-traction", "coverage-price"):
        precision, recall = cells[label]
        assert precision.value is None and precision.absent == "no held-out case"
        assert precision.detail == "0 predicted" and recall.detail == "0 actual"
    b24 = _section(_html(captured_db), "B2.4")  # the panel, never the whole page
    assert "no held-out case" in b24 and "0 predicted" in b24
    # the graded labels show the percentage with the held-out counts.
    for label, (p_pct, p_cnt, r_pct, r_cnt) in pins.BEAT2_QUALITY_CELLS.items():
        precision, recall = cells[label]
        if p_pct.endswith("%"):
            assert export._display(precision.value, "pct") == p_pct
            assert export._display(recall.value, "pct") == r_pct
            assert precision.detail == p_cnt and recall.detail == r_cnt


def test_a_null_cell_with_no_declared_absence_is_still_refused_by_name():
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Measured",
        "table",
        columns=("Theme", "Precision"),
        series=(
            Series("Document loop", 0, (Point("Precision", None, "Measured", ""),)),
        ),
    )
    with pytest.raises(RenderRefused) as exc:
        check_panel(panel)
    assert "Precision" in str(exc.value) and "neither" in str(exc.value)


def test_a_point_with_both_value_and_absence_is_refused():
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Measured",
        "table",
        columns=("Theme", "Precision"),
        series=(
            Series(
                "Document loop",
                0,
                (Point("Precision", 1.0, "Measured", "", "pct", absent="no case"),),
            ),
        ),
    )
    with pytest.raises(RenderRefused) as exc:
        check_panel(panel)
    assert "both" in str(exc.value)


def test_an_all_absent_table_renders_as_a_table_not_no_data():
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Measured",
        "table",
        columns=("Theme", "Precision", "Recall"),
        series=(
            Series(
                "Coverage and price",
                0,
                (
                    Point(
                        "Precision",
                        None,
                        "Measured",
                        "",
                        "pct",
                        absent="no held-out case",
                        detail="0 predicted",
                    ),
                    Point(
                        "Recall",
                        None,
                        "Measured",
                        "",
                        "pct",
                        absent="no held-out case",
                        detail="0 actual",
                    ),
                ),
            ),
        ),
    )
    assert has_content(panel)  # a cell is present (an absence), so not "no data yet"
    body = "\n".join(export._render_body(panel))
    assert "<table" in body and "No data yet" not in body
    assert "no held-out case" in body


def test_b2_2_and_b2_5_render_their_declared_kind_over_captured(captured_db):
    # Over a captured input the corpus panels draw a real chart, not the fixture
    # state: B2.2 a line, B2.5 grouped bars. The kind is pinned so a swap is
    # caught — over synthetic they render the fixture state, so the bytes alone
    # never cover it (round 1, functionality-tester).
    b22 = _panel(captured_db, "B2.2")
    b25 = _panel(captured_db, "B2.5")
    assert b22.kind == "line" and b22.fixture == ""
    assert b25.kind == "grouped_bar" and b25.fixture == ""
    page = _html(captured_db)
    assert "<circle" in _section(page, "B2.2")  # a line draws point circles
    assert "<rect" in _section(page, "B2.5")  # grouped bars draw rects


def test_corpus_panels_render_no_data_yet_over_none(none_db):
    # ROWS=none never builds the Python-fed corpus marts, so B2.2/B2.4/B2.5 render
    # the "no data yet" state — not the fixture state, not a fabricated number
    # (round 1, functionality-tester).
    page = _html(none_db)
    for pid in ("B2.2", "B2.4", "B2.5"):
        sec = _section(page, pid)
        assert 'class="nodata"' in sec
        assert 'class="fixture"' not in sec and 'class="pending"' not in sec


# --- Round 1 fix amendment: a panel's notes are a sequence ---------------------
def test_a_panel_renders_one_block_per_note():
    # The second layer is a sequence: each note is its own <p class="note">, so a
    # packed note splits into scannable ideas (round 1 amendment, brief §2.3).
    panel = Panel(
        "B2.9",
        "B2.9",
        "t",
        "b",
        "Pending",
        "hero",
        placeholder="x",
        notes=("first idea", "second idea"),
    )
    html = "\n".join(export._render_panel(panel))
    assert html.count('<p class="note">') == 2
    assert "first idea" in html and "second idea" in html


def test_b2_2_and_b2_5_name_the_self_selection_bias(synthetic_db):
    # The two theme-share panels carry the negative-self-selection caveat as one
    # of their notes, as B1.2 does beside the rating trend (round 1 amendment,
    # brief §2.5). The notes render over any input, so synthetic suffices.
    page = _html(synthetic_db)
    for pid in ("B2.2", "B2.5"):
        assert "negatively self-selected" in _section(page, pid), pid


def test_every_measured_panel_over_the_platforms_names_the_self_selection(
    synthetic_db,
):
    # The caveat's for-all is derived, not authored per id: every Measured panel
    # whose panel-level sources are the review platforms (a computed share from
    # unsolicited reviews) carries one note naming the negative self-selection —
    # so a later corpus panel (the traditional split, B5.2) cannot omit it
    # (challenge round 2, #3). Over synthetic the notes render the same.
    conn = connect("duckdb", database=synthetic_db)
    try:
        built = beat1_panels(conn) + beat2_panels(conn)
    finally:
        conn.close()
    over_platforms = [
        p
        for p in built
        if p.tag == "Measured" and set(p.sources) & set(panels.PLATFORM_ROOTS)
    ]
    assert {p.id for p in over_platforms} == {"B2.2", "B2.5"}  # today's two
    for p in over_platforms:
        assert any("negatively self-selected" in note for note in p.notes), p.id


# The `unclassified` band's label slug, so a rendered series maps back to its
# mart label (the neutral band carries no theme name of its own).
UNCLASSIFIED_LABEL = "unclassified"


def _label_of(series: Series) -> str:
    return UNCLASSIFIED_LABEL if series.colour == NEUTRAL else _LABEL_OF[series.name]
