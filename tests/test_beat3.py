"""Phase 9c — Beat 3: the first Modeled panels, the formulas beside their numbers
(spec Invariants / Done-when). The committed baseline shows Beat 3's numbers
(the model marts fill on every input), so these tests do what the bytes cannot:
they prove every rendered value equals its mart cell, every expression equals
the `FORMULAS` entry of that name, that a mutated cell moves the page, the
markers, the absences, the fixed mark, the split by `sourcing`, the refusals,
and the domain rule."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

import duckdb
import pytest

from models.cost_model import FORMULAS, SCENARIOS
from pipeline.build import read_model_fit
from pipeline.warehouse import ROOT, connect
from study import export, panels, text
from study.model import (
    Panel,
    Point,
    RenderRefused,
    Series,
    check_panel,
    display,
    x_key,
)
from study.panels import ALLOWED_COLUMNS, STUDY_QUERIES, beat3_panels, curve_domain
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: builds a warehouse; out of the edit-loop hook

# One rendered formula row: the mart's identifier, then the expression as printed.
_FORMULA_ROW = re.compile(
    r'<code class="ident">(\w+)</code></th><td><code class="expr">(.*?)</code>'
)
_IDENT = re.compile(r'<code class="ident">(\w+)</code>')
_MARKER_LABEL = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" class="marker-label"[^>]*>([^<]*)</text>'
)


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat3-syn"), "synthetic")


@pytest.fixture(scope="module")
def none_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat3-none"), "none")


def _mutated(synthetic_db: Path, tmp_path: Path, statements: tuple[str, ...]) -> Path:
    """A test-owned copy of the synthetic warehouse with the given cells changed."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    dst = tmp_path / "mutated.duckdb"
    shutil.copy(synthetic_db, dst)
    con = duckdb.connect(str(dst))
    try:
        for sql in statements:
            con.execute(sql)
    finally:
        con.close()
    return dst


def _panels(db: Path) -> list[Panel]:
    conn = connect("duckdb", database=db)
    try:
        return beat3_panels(conn)
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


def _mart(db: Path, sql: str) -> list[tuple]:
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _row(section: str, key: str) -> str:
    """The rendered `<tr>` of the row whose identifier is `key`."""
    at = section.index(f'<code class="ident">{key}</code>')
    return section[section.rfind("<tr>", 0, at) : section.index("</tr>", at)]


# --- Done-when 1: Beat 3 renders into the baseline with numbers ---------------
def test_b3_1_renders_the_baseline_formula_rows_each_expression_beside_its_value(
    synthetic_db,
):
    b31 = _panel(synthetic_db, "B3.1")
    assert b31.tag == "Modeled" and b31.kind == "formulas"
    assert len(b31.series) == pins.BEAT3_FORMULA_ROWS
    by_name = {f.name: f for f in FORMULAS}
    for s in b31.series:
        (cell,) = s.points
        assert cell.label == by_name[s.key].expression  # the expression is the label
        assert cell.unit == panels._DISPLAY_UNIT[by_name[s.key].unit]
        assert cell.tag == pins.COST_MODELED_TAG
    sec = _section(_html(synthetic_db), "B3.1")
    assert pins.BEAT3_FRAGMENTS["formula value (fraud_saved, eur)"] in sec
    assert pins.BEAT3_FRAGMENTS["crossover row (rate as pct)"] in sec  # a flag rate
    assert ">707,858<" in sec and ">21.0 days<" in sec  # a count, a day count


def test_b3_2_draws_two_curves_and_three_markers_from_the_marts(synthetic_db, tmp_path):
    b32 = _panel(synthetic_db, "B3.2")
    assert b32.kind == "curve" and len(b32.series) == 2
    assert [len(s.points) for s in b32.series] == [pins.FLAG_RATE_GRID_POINTS] * 2
    assert b32.markers == pins.BEAT3_MARKERS
    sec = _section(_html(synthetic_db), "B3.2")
    x_of = export._curve_x(b32)
    for _label, x in b32.markers:
        assert f'<line x1="{x_of[x_key(x)]:.2f}" y1="{export._MT:.2f}"' in sec
    legend = sec[sec.index('<ul class="legend">') :]
    assert "Fraud saved" in legend and "Friction cost" in legend
    # The marker sits at the mart's crossover row, not at the first curve point
    # whose net is negative: a moved crossover row moves the marker while the
    # curves stay (invariant 1).
    moved = _mutated(
        synthetic_db,
        tmp_path,
        (
            "update cost_model_outputs set value = 0.15 where scenario = 'baseline' "
            "and name = 'crossover_flag_rate'",
        ),
    )
    after = _panel(moved, "B3.2")
    assert after.series == b32.series
    assert dict(after.markers)[text.MARKER_CROSSOVER] == 0.15


def test_coincident_markers_stack_their_labels_at_one_x(synthetic_db):
    # The baseline's own case: the default and the marginal crossover both at
    # 0.05 — two labels at one x, at the two index offsets, neither hidden.
    sec = _section(_html(synthetic_db), "B3.2")
    labels = _MARKER_LABEL.findall(sec)
    assert [label for _, _, label in labels] == [
        f"{label} ({display(x, 'pct')})" for label, x in pins.BEAT3_MARKERS
    ]
    (x0, y0, _), (_, _, _), (x2, y2, _) = labels
    assert x0 == x2  # one x
    assert float(y2) - float(y0) == 2 * export._MARKER_DY  # stacked by draw index
    # Two markers at one x share one line: three markers, two distinct x, two
    # `<line class="marker">` rules — no duplicate overlapping line (round 2 #1).
    assert sec.count('class="marker"') == 2
    note = _section(_html(synthetic_db), "B3.2")
    assert "cross at a flag rate of 9.5%" in note
    assert "stops paying for itself at 5.0%, where the default sits" in note


def test_b3_3_shows_the_derived_headline_figures_from_the_outputs_mart(synthetic_db):
    b33 = _panel(synthetic_db, "B3.3")
    assert tuple(s.key for s in b33.headline) == pins.BEAT3_HEADLINES
    for s in b33.headline:
        (cell,) = s.points
        assert cell.value == pins.COST_OUTPUTS["baseline"][s.key]
    sec = _section(_html(synthetic_db), "B3.3")
    headline = sec.index('class="metric formulas headline"')
    assert headline < sec.index('class="metric params"')  # above the rows
    assert ">€494.45<" in sec and ">707,858<" in sec


def test_b3_3_and_b3_4_render_every_parameter_with_default_unit_and_range(
    synthetic_db,
):
    b33, b34 = _panel(synthetic_db, "B3.3"), _panel(synthetic_db, "B3.4")
    mart = {
        name: (default, unit, low, high)
        for name, default, unit, low, high in _mart(
            synthetic_db,
            "select name, default_value, unit, low, high from cost_model_params",
        )
    }
    assert len(mart) == pins.BEAT3_PARAMETER_ROWS
    rows = b33.series + b34.series
    assert {s.key for s in rows} == set(mart)
    assert len(b33.series) == pins.BEAT3_SOURCED_ROWS
    assert len(b34.series) == pins.BEAT3_UNSOURCED_ROWS
    for s in rows:
        default, prose_unit, low, high = mart[s.key]
        cells = {p.label: p for p in s.points}
        assert set(cells) == {"low", "default", "high"}
        assert cells["default"].value == default
        assert (cells["low"].value, cells["high"].value) == (low, high)
        assert cells["default"].detail.startswith(f"{prose_unit} · ")  # prose unit
        assert cells["default"].unit == text.PARAMETER_NAMES[s.key][1]


def test_parameter_defaults_render_in_their_display_unit(synthetic_db):
    page = _html(synthetic_db)
    b33, b34 = _section(page, "B3.3"), _section(page, "B3.4")
    assert pins.BEAT3_FRAGMENTS["sourced default (arr_eur, eur)"] in _row(
        b33, "arr_eur"
    )
    assert pins.BEAT3_FRAGMENTS["fit default (mu, logeur)"] in _row(b33, "mu")
    assert pins.BEAT3_FRAGMENTS["unsourced default (flag_rate, pct)"] in _row(
        b34, "flag_rate"
    )
    assert "€ / year · " in _row(b33, "arr_eur")  # the prose unit beside it


def test_no_beat3_panel_prints_source_pending(synthetic_db):
    page = _html(synthetic_db)
    for pid in pins.BEAT3_PANELS:
        assert "source pending" not in _section(page, pid), pid
    for pid in ("B3.1", "B3.2", "B3.3"):
        sec = _section(page, pid)
        assert f"the repository file {panels.FIT_FILE}" in sec
        assert f'href="{panels._FIT_SOURCES[1]}"' in sec  # the Open DAMIR address
    assert f"the repository file {panels.MODEL_FILE}" in _section(page, "B3.4")
    assert (ROOT / panels.FIT_FILE).is_file() and (ROOT / panels.MODEL_FILE).is_file()


def test_beat3_renders_numbers_over_a_none_input(none_db):
    # No corpus gate on a Modeled panel: over ROWS=none Beat 2's corpus panels
    # say "no data yet" and every Beat 3 panel shows its numbers.
    page = _html(none_db)
    assert 'class="nodata"' in _section(page, "B2.2")
    for pid in pins.BEAT3_PANELS:
        sec = _section(page, pid)
        for state in ('class="nodata"', 'class="fixture"', 'class="pending"'):
            assert state not in sec, (pid, state)
    assert pins.BEAT3_FRAGMENTS["formula value (fraud_saved, eur)"] in page


# --- Done-when 2: every number is a mart cell; every expression is FORMULAS ----
def test_every_beat3_value_equals_its_mart_cell(synthetic_db):
    outputs = {
        name: value
        for name, value in _mart(
            synthetic_db,
            "select name, value from cost_model_outputs where scenario = 'baseline'",
        )
    }
    assert {k: v for k, v in outputs.items() if k in pins.COST_OUTPUTS["baseline"]} == (
        pins.COST_OUTPUTS["baseline"]
    )
    b31 = _panel(synthetic_db, "B3.1")
    for s in b31.series:
        assert s.points[0].value == outputs[s.key]
    curves = _mart(
        synthetic_db,
        "select flag_rate, fraud_saved, friction_cost, is_default from cost_curves "
        "where scenario = 'baseline' order by flag_rate",
    )
    b32 = _panel(synthetic_db, "B3.2")
    saved, cost = b32.series
    for (rate, fraud_saved, friction_cost, _), a, b in zip(
        curves, saved.points, cost.points, strict=True
    ):
        assert (a.label, a.value) == (x_key(rate), fraud_saved)
        assert (b.label, b.value) == (x_key(rate), friction_cost)
    (default_rate,) = [rate for rate, *_, is_default in curves if is_default]
    assert dict(b32.markers) == {
        text.MARKER_DEFAULT: default_rate,
        text.MARKER_CROSSOVER: pins.COST_CROSSOVERS["baseline"]["crossover_flag_rate"],
        text.MARKER_MARGINAL: pins.COST_CROSSOVERS["baseline"][
            "marginal_crossover_flag_rate"
        ],
    }
    assert display(outputs["crossover_flag_rate"], "pct") in b32.notes[0]
    params = {
        name: (low, default, high)
        for name, low, default, high in _mart(
            synthetic_db, "select name, low, default_value, high from cost_model_params"
        )
    }
    for s in _panel(synthetic_db, "B3.3").series + _panel(synthetic_db, "B3.4").series:
        assert tuple(p.value for p in s.points) == params[s.key]


def test_a_mutated_mart_cell_moves_the_page_and_the_expression_stays(
    synthetic_db, tmp_path
):
    before = _html(synthetic_db)
    moved = _mutated(
        synthetic_db,
        tmp_path,
        (
            "update cost_model_outputs set value = 123456.78 where scenario = "
            "'baseline' and name = 'fraud_saved'",
            "update cost_curves set friction_cost = 4999999.99 where scenario = "
            "'baseline' and flag_rate = 0.2",
        ),
    )
    after = _html(moved)
    assert ">€123,456.78<" in _section(after, "B3.1")
    assert "€4,999,999.99" in _section(after, "B3.2")  # a curve point's tooltip
    assert _FORMULA_ROW.findall(_section(after, "B3.1")) == _FORMULA_ROW.findall(
        _section(before, "B3.1")
    )
    # `net` is read by no panel: the crossover marker comes from the outputs row,
    # never from a scan of the curve, so a changed net cell moves nothing.
    net_only = _mutated(
        synthetic_db,
        tmp_path / "net",
        ("update cost_curves set net = -1 where scenario = 'baseline'",),
    )
    assert _html(net_only) == before


def test_every_rendered_expression_equals_the_formulas_entry_of_that_name(
    synthetic_db,
):
    rows = _FORMULA_ROW.findall(_section(_html(synthetic_db), "B3.1"))
    rendered = {name: html.unescape(expression) for name, expression in rows}
    assert rendered == {f.name: f.expression for f in FORMULAS}  # both directions


def test_rows_render_in_formulas_and_parameters_order(synthetic_db):
    page = _html(synthetic_db)
    assert _IDENT.findall(_section(page, "B3.1")) == [f.name for f in FORMULAS]
    assert list(text.FORMULA_NAMES) == [f.name for f in FORMULAS]
    from models.cost_model import parameters

    in_model = [p.name for p in parameters(read_model_fit())]
    assert list(text.PARAMETER_NAMES) == in_model  # `make model`'s row order
    b33 = _IDENT.findall(_section(page, "B3.3"))[len(pins.BEAT3_HEADLINES) :]
    b34 = _IDENT.findall(_section(page, "B3.4"))
    assert b33 == [n for n in in_model if n in b33]  # each panel keeps that order
    assert b34 == [n for n in in_model if n in b34]


def test_the_curve_domain_rule_is_pinned_over_two_inputs(synthetic_db, tmp_path):
    for top, upper in pins.BEAT3_CURVE_DOMAIN.items():
        assert curve_domain([top, 0.0, top / 2]) == (0.0, upper)
    assert curve_domain([]) == (0.0, 1.0)
    assert _panel(synthetic_db, "B3.2").domain == (0.0, 5_000_000.0)
    crossed = _mutated(
        synthetic_db,
        tmp_path,
        (
            "update cost_curves set friction_cost = 5000000.01 where scenario = "
            "'baseline' and flag_rate = 0.2",
        ),
    )
    assert _panel(crossed, "B3.2").domain == (0.0, 6_000_000.0)
    sec = _section(_html(crossed), "B3.2")
    assert ">€1,500,000.00<" in sec and "e+06" not in sec  # euros, never {:g}
    assert pins.BEAT3_FRAGMENTS["curve euro tick"] in _section(
        _html(synthetic_db), "B3.2"
    )


# --- Done-when 3: absences, the fixed mark, the refusals ----------------------
def test_a_null_crossover_renders_a_declared_absence_and_no_marker(synthetic_db):
    # The `both` scenario: the mart stores NULL for crossover_flag_rate.
    conn = connect("duckdb", database=synthetic_db)
    try:
        rows = panels._formula_rows(conn, "both", "B3.9")
        markers = panels._curve_markers(conn, "both", "B3.9")
        curves = panels._curve_series(conn, "both", "B3.9")
    finally:
        conn.close()
    cell = next(s for s in rows if s.key == "crossover_flag_rate").points[0]
    assert cell.value is None and cell.absent == text.NEVER_CROSSES
    assert [label for label, _ in markers] == [
        text.MARKER_DEFAULT,
        text.MARKER_MARGINAL,
    ]
    note = panels._crossover_note(markers)
    # The marginal sentence leads (round 1, study-editor #3); the null crossover
    # renders its declared-absence sentence after it.
    assert "On this grid the two curves never cross" in note
    panel = Panel(
        "B3.9",
        "B3.9",
        "t",
        "b",
        "Modeled",
        "curve",
        series=curves,
        markers=markers,
        domain=curve_domain(p.value for s in curves for p in s.points),
    )
    check_panel(panel)
    svg = "\n".join(export._render_curve(panel))
    assert svg.count('class="marker"') == 2 and text.MARKER_CROSSOVER not in svg
    table = "\n".join(
        export._render_formulas(
            Panel("B3.9", "B3.9", "t", "b", "Modeled", "formulas", series=rows)
        )
    )
    assert f'<span class="absent">{text.NEVER_CROSSES}</span>' in table


def test_a_single_point_range_renders_a_labelled_fixed_mark(synthetic_db):
    row = _row(_section(_html(synthetic_db), "B3.3"), pins.BEAT3_FIXED_PARAMETER)
    assert text.FIXED_RANGE in row
    assert "<svg" not in row  # no zero-width mark, no division by zero
    fixed = next(
        s
        for s in _panel(synthetic_db, "B3.3").series
        if s.key == pins.BEAT3_FIXED_PARAMETER
    )
    assert len({p.value for p in fixed.points}) == 1


def test_a_zero_width_range_with_an_off_centre_default_is_the_fixed_mark():
    # high == low but default off it: the position arithmetic would divide by
    # (high - low) == 0. The fixed-mark guard keys on the zero-width span, so
    # the mark draws and no ZeroDivisionError escapes render (invariant 6;
    # round 1, code-reviewer #1). check_parameter forbids this ordering upstream,
    # so this pins the renderer's own guard-by-shape, not a reachable mart row.
    series = Series(
        "cost per contact",
        0,
        (
            Point("low", 5.0, "Modeled", "", "eur"),
            Point("default", 9.0, "Modeled", "", "eur"),
            Point("high", 5.0, "Modeled", "", "eur"),
        ),
        key="k",
        sourcing="unsourced",
    )
    assert text.FIXED_RANGE in export._range_mark(series)


def test_a_default_outside_the_range_clamps_the_dot_to_the_edge():
    # default > high with a non-zero span: the fraction exceeds 1 and would draw
    # the dot past the range line; it clamps to the right edge (round 2, #2).
    # Like the zero-width case, check_parameter forbids this ordering upstream,
    # so this pins the renderer's guard-by-shape, not a reachable mart row.
    series = Series(
        "cost per contact",
        0,
        (
            Point("low", 5.0, "Modeled", "", "eur"),
            Point("default", 20.0, "Modeled", "", "eur"),
            Point("high", 10.0, "Modeled", "", "eur"),
        ),
        key="k",
        sourcing="unsourced",
    )
    assert f'cx="{export._n(export._RW - export._RPAD)}"' in export._range_mark(series)


def test_a_sourcing_outside_the_two_words_refuses_by_name(synthetic_db, tmp_path):
    bad = _mutated(
        synthetic_db,
        tmp_path,
        ("update cost_model_params set sourcing = 'guessed' where name = 'k'",),
    )
    with pytest.raises(RenderRefused) as exc:
        _panels(bad)
    assert "B3.3" in str(exc.value) and "guessed" in str(exc.value)
    assert "\n" not in str(exc.value)
    conn = connect("duckdb", database=synthetic_db)
    try:
        with pytest.raises(RenderRefused) as exc:
            panels._parameter_rows(conn, "maybe", "B3.9")
    finally:
        conn.close()
    assert "B3.9" in str(exc.value) and "maybe" in str(exc.value)
    # and the renderer's class lookup refuses a third word too.
    with pytest.raises(RenderRefused):
        export._range_mark(Series("x", 0, (), key="k", sourcing="maybe"))


def test_a_scenario_outside_scenarios_refuses_by_name(synthetic_db):
    conn = connect("duckdb", database=synthetic_db)
    try:
        for reader in (
            panels._formula_rows,
            panels._curve_series,
            panels._curve_markers,
        ):
            with pytest.raises(RenderRefused) as exc:
                reader(conn, "bogus", "B3.9")
            assert "B3.9" in str(exc.value) and "bogus" in str(exc.value)
        assert set(SCENARIOS) == set(pins.COST_SCENARIOS)
    finally:
        conn.close()


def test_a_name_outside_the_display_map_refuses_by_name(synthetic_db, tmp_path):
    renamed_formula = _mutated(
        synthetic_db,
        tmp_path / "f",
        (
            "update cost_model_outputs set name = 'mystery' where scenario = "
            "'baseline' and name = 'customer_value'",
        ),
    )
    with pytest.raises(RenderRefused) as exc:
        _panels(renamed_formula)
    assert "mystery" in str(exc.value) and "B3.1" in str(exc.value)
    renamed_parameter = _mutated(
        synthetic_db,
        tmp_path / "p",
        ("update cost_model_params set name = 'mystery' where name = 'k'",),
    )
    with pytest.raises(RenderRefused) as exc:
        _panels(renamed_parameter)
    assert "mystery" in str(exc.value) and "B3.3" in str(exc.value)


def test_a_null_expression_or_default_refuses_by_name(synthetic_db, tmp_path):
    cases = {
        "expression": "update cost_model_outputs set expression = null where "
        "scenario = 'baseline' and name = 'net'",
        "value": "update cost_model_outputs set value = null where "
        "scenario = 'baseline' and name = 'net'",  # a point formula, not a curve
        "default_value": "update cost_model_params set default_value = null "
        "where name = 'k'",
    }
    for column, sql in cases.items():
        bad = _mutated(synthetic_db, tmp_path / column, (sql,))
        with pytest.raises(RenderRefused) as exc:
            _panels(bad)
        assert column in str(exc.value) and "\n" not in str(exc.value), column


# --- Done-when 4: the split is the mart's sourcing column ---------------------
def test_the_sourced_unsourced_split_is_the_marts_sourcing_column(
    synthetic_db, tmp_path
):
    flipped = _mutated(
        synthetic_db,
        tmp_path,
        (
            "update cost_model_params set sourcing = 'sourced', citation = "
            "'a test citation' where name = 'k'",
        ),
    )
    b33 = {s.key for s in _panel(flipped, "B3.3").series}
    b34 = {s.key for s in _panel(flipped, "B3.4").series}
    assert "k" in b33 and "k" not in b34
    assert len(b33) == pins.BEAT3_SOURCED_ROWS + 1
    assert len(b34) == pins.BEAT3_UNSOURCED_ROWS - 1
    sourcing = dict(_mart(synthetic_db, "select name, sourcing from cost_model_params"))
    for s in _panel(synthetic_db, "B3.3").series:
        assert sourcing[s.key] == "sourced" == s.sourcing
    for s in _panel(synthetic_db, "B3.4").series:
        assert sourcing[s.key] == "unsourced" == s.sourcing


def test_a_sourced_row_shows_its_citation_and_an_unsourced_row_the_explore_label_never_both(  # noqa: E501 -- the spec's Evidence row names this test
    synthetic_db,
):
    citation = dict(_mart(synthetic_db, "select name, citation from cost_model_params"))
    for s in _panel(synthetic_db, "B3.3").series:
        detail = next(p for p in s.points if p.label == "default").detail
        assert citation[s.key] and citation[s.key] in detail
        assert text.UNSOURCED_LABEL not in detail
    for s in _panel(synthetic_db, "B3.4").series:
        detail = next(p for p in s.points if p.label == "default").detail
        assert citation[s.key] == "" and text.UNSOURCED_LABEL in detail
    page = _html(synthetic_db)
    b33, b34 = _section(page, "B3.3"), _section(page, "B3.4")
    assert "range-sourced" in b33 and "range-unsourced" not in b33
    assert "range-unsourced" in b34 and "range-sourced" not in b34
    assert text.UNSOURCED_LABEL not in b33 and text.UNSOURCED_LABEL in b34


# --- Done-when 5: the no-text guarantee extends over Beat 3 -------------------
def test_the_allowlist_gains_no_review_text_column():
    assert "title" not in ALLOWED_COLUMNS and "body" not in ALLOWED_COLUMNS
    beat3 = {
        "scenario",
        "name",
        "expression",
        "unit",
        "default_value",
        "sourcing",
        "citation",
        "low",
        "high",
        "flag_rate",
        "fraud_saved",
        "friction_cost",
        "net",
        "is_default",
    }
    assert beat3 <= ALLOWED_COLUMNS
    for sql in (panels._Q_COST_OUTPUTS, panels._Q_COST_CURVES, panels._Q_COST_PARAMS):
        assert sql in STUDY_QUERIES


def test_beat3_points_carry_the_mart_rows_tag_not_a_literal(synthetic_db, tmp_path):
    mixed = _mutated(
        synthetic_db,
        tmp_path,
        (
            "update cost_curves set tag = 'Measured' where scenario = 'baseline' "
            "and flag_rate = 0.05",
        ),
    )
    sec = _section(_html(mixed), "B3.2")
    assert "chip chip-measured" in sec and "chip chip-modeled" in sec
    assert "Measured, Modeled" in sec  # the footer names both, in TAGS order
    # a curve point with no tag is refused (9a's contract over the new kind).
    b32 = _panel(synthetic_db, "B3.2")
    untagged = Series("s", 0, (Point("0.050", 1.0, "", "", "eur"),))
    with pytest.raises(RenderRefused):
        check_panel(
            Panel("B3.9", "B3.9", "t", "b", "Modeled", "curve", series=(untagged,))
        )
    assert all(p.tag == pins.COST_MODELED_TAG for s in b32.series for p in s.points)


def test_a_marker_off_the_grid_or_on_a_non_curve_panel_is_refused():
    point = Point(x_key(0.05), 1.0, "Modeled", "", "eur")
    on_grid = Panel(
        "B3.9",
        "B3.9",
        "t",
        "b",
        "Modeled",
        "curve",
        series=(Series("s", 0, (point,)),),
        markers=((text.MARKER_DEFAULT, 0.05),),
    )
    check_panel(on_grid)
    off_grid = Panel(
        "B3.9",
        "B3.9",
        "t",
        "b",
        "Modeled",
        "curve",
        series=(Series("s", 0, (point,)),),
        markers=((text.MARKER_DEFAULT, 0.0525),),  # between two grid points
    )
    with pytest.raises(RenderRefused) as exc:
        check_panel(off_grid)
    assert "0.0525" in str(exc.value) and "B3.9" in str(exc.value)
    not_a_curve = Panel(
        "B3.9",
        "B3.9",
        "t",
        "b",
        "Modeled",
        "line",
        series=(Series("s", 0, (point,)),),
        markers=((text.MARKER_DEFAULT, 0.05),),
    )
    with pytest.raises(RenderRefused) as exc:
        check_panel(not_a_curve)
    assert "only a curve" in str(exc.value)


def test_display_formats_euros_and_log_euros_and_refuses_an_unknown_unit():
    assert display(1318719.82, "eur") == "€1,318,719.82"
    assert display(3.809814, "logeur") == "3.809814 log-euros"
    assert display(0.095, "pct") == "9.5%"
    with pytest.raises(RenderRefused):
        display(1.0, "rate")  # the mart's rounding unit, never a display unit
    # the note template: both figures named; the absent halves say so.
    both = text.crossover_note("9.5%", "5.0%", "5.0%")
    assert "9.5%" in both and "5.0%, where the default sits" in both
    neither = text.crossover_note(None, None, "5.0%")
    assert "never cross" in neither and "No point of the grid" in neither
