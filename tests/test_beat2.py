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
from study.panels import ALLOWED_COLUMNS, STUDY_QUERIES, beat2_panels
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: builds a warehouse; out of the edit-loop hook

_CORPUS_MARTS = (
    "theme_share_by_month",
    "theme_share_by_segment",
    "classifier_quality",
)
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
        for mart in _CORPUS_MARTS:
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
    by_name = {p.label: p for s in b23.series for p in s.points}
    for profile, (rating, count) in pins.BEAT2_PEER_RATINGS.items():
        point = by_name[panels._PROFILE_NAMES[profile]]
        assert point.value == rating
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
        assert "hand-written fixture reviews" in body
        assert not any(ch.isdigit() for ch in body), (pid, body)  # no number


# --- Done-when 2: the corpus gate is data ------------------------------------
def test_the_corpus_gate_reads_run_id_from_the_mart():
    assert set(INPUTS) == {"captured", "none", "synthetic", "samples"}

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
        label: (reviews, theme_rows, share)
        for label, reviews, theme_rows, share in _mart(
            captured_db,
            "select label, reviews, theme_rows, share from theme_share_by_segment "
            "order by label",
        )
    }
    b25 = _panel(captured_db, "B2.5")
    drawn = {}
    for s in b25.series:
        label = UNCLASSIFIED_LABEL if s.colour == NEUTRAL else _LABEL_OF[s.name]
        drawn[label] = s
        for point in s.points:
            reviews, theme_rows, share = seg[label]
            assert point.value == float(share)  # value equals its mart
            assert point.detail == f"{int(theme_rows)} of {int(reviews)} reviews"
    assert pins.BEAT2_POSITIVE_EXCLUDED not in drawn  # positive is not a bar
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
    page = _html(captured_db)
    assert f"Not yet classified ({total})" in page and "var(--sN)" in page
    # an empty band still appears in the legend, at zero — never hidden.
    empty = panels._theme_series(
        [("2026-01", "document-loop", 10, 3, 0.3)], "B2.9", "period"
    )
    band0 = next(s for s in empty if s.colour == NEUTRAL)
    assert band0.name == "Not yet classified (0)" and band0.points == ()
    # a series colour outside the closed choice refuses by name.
    for bad in (5, -1, "purple"):
        with pytest.raises(RenderRefused):
            export._series_var(bad)


def test_b2_2_plots_each_share_against_the_axis_not_stacked():
    # A cell whose shares sum past 1 (three themes, each 0.6) plots every point at
    # its own share — no cumulative stack — so the y of each is _y_of(0.6).
    rows = [
        ("2026-01", "document-loop", 10, 6, 0.6),
        ("2026-01", "silent-rejection", 10, 6, 0.6),
        ("2026-01", "second-payer", 10, 6, 0.6),
    ]
    panel = Panel(
        "B2.9", "B2.9", "t", "b", "Measured", "line",
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
        "select segment, label, reviews, theme_rows, share from "
        "theme_share_by_segment order by label",
    )
    series = panels._theme_series(rows, "B2.5", "theme")
    assert all(_label_of(s) != pins.BEAT2_POSITIVE_EXCLUDED for s in series)
    page = _html(captured_db)
    # the denominator (positive included) is stated beside the chart.
    assert "positive reviews included in the total" in _section(page, "B2.5")


def test_reviews_and_theme_rows_render_beside_each_share(captured_db):
    page = _html(captured_db)
    # document-loop's monthly counts ride on each point as "theme_rows of reviews".
    for month, theme_rows in pins.BEAT2_MONTH_DOCUMENT_LOOP.items():
        reviews = pins.THEME_SHARE_BY_MONTH_REVIEWS[month]
        assert f"{theme_rows} of {reviews} reviews" in page


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
    page = _html(captured_db)
    assert "no held-out case" in page and "0 predicted" in page
    # the graded labels show the percentage with the held-out counts.
    for label, (p_pct, p_cnt, r_pct, r_cnt) in pins.BEAT2_QUALITY_CELLS.items():
        precision, recall = cells[label]
        if p_pct.endswith("%"):
            assert export._display(precision.value, "pct") == p_pct
            assert export._display(recall.value, "pct") == r_pct
            assert precision.detail == p_cnt and recall.detail == r_cnt


def test_a_null_cell_with_no_declared_absence_is_still_refused_by_name():
    panel = Panel(
        "B2.9", "B2.9", "t", "b", "Measured", "table",
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
        "B2.9", "B2.9", "t", "b", "Measured", "table",
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
        "B2.9", "B2.9", "t", "b", "Measured", "table",
        columns=("Theme", "Precision", "Recall"),
        series=(
            Series(
                "Coverage and price",
                0,
                (
                    Point(
                        "Precision", None, "Measured", "", "pct",
                        absent="no held-out case", detail="0 predicted",
                    ),
                    Point(
                        "Recall", None, "Measured", "", "pct",
                        absent="no held-out case", detail="0 actual",
                    ),
                ),
            ),
        ),
    )
    assert has_content(panel)  # a cell is present (an absence), so not "no data yet"
    body = "\n".join(export._render_body(panel))
    assert "<table" in body and "No data yet" not in body
    assert "no held-out case" in body


# The label slug for `positive`, used to prove it is not drawn as a theme bar.
UNCLASSIFIED_LABEL = "unclassified"


def _label_of(series: Series) -> str:
    return UNCLASSIFIED_LABEL if series.colour == NEUTRAL else _LABEL_OF[series.name]
