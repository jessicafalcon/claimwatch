"""Phase 9d — Beat 4: the three fixes, drawn beside the Beat 3 curves (spec
Invariants / Done-when). The Beat 4 marts fill on every rebuild input (no
reviews, no key), so the committed page shows these numbers; these tests do what
the bytes cannot — prove every rendered value is a `cost_curves`, `sla_threshold`
or `guardrail_sim` cell, that B4.1's net curves stay within the five-slot
palette, that the B4.3 SQL aggregate reproduces `guardrail_sim.summarize`, that
B4.4 carries no number, and that the numbers are the same over `ROWS=none` and
byte-stable."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from models.cost_model import SCENARIOS
from models.guardrail_sim import SIM_SCENARIOS, summarize
from pipeline.warehouse import connect
from study import export, panels, text
from study.model import Panel, Point, RenderRefused, Series, check_panel, display, x_key
from study.panels import beat4_panels, net_domain
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: builds a warehouse; out of the edit-loop hook


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat4-syn"), "synthetic")


@pytest.fixture(scope="module")
def none_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat4-none"), "none")


def _mutated(src: Path, tmp_path: Path, statements: tuple[str, ...]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    dst = tmp_path / "mutated.duckdb"
    shutil.copy(src, dst)
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
        return beat4_panels(conn)
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


# --- Done-when 1: Beat 4 renders into the baseline with numbers ---------------
def test_beat_four_renders_all_four_panels(synthetic_db):
    kinds = {
        "B4.1": ("Modeled", "curve"),
        "B4.2": ("Modeled", "stat_row"),
        "B4.3": ("Modeled", "grouped_bar"),
        "B4.4": ("Pending", "hero"),
    }
    got = {p.id: (p.tag, p.kind) for p in _panels(synthetic_db)}
    assert got == kinds
    page = _html(synthetic_db)
    assert "Beat 4 — Three small fixes, no rebuild required" in page
    for pid in pins.BEAT4_PANELS:
        assert f"Evidence: {pid}" in page


# --- Done-when 2 / invariant 2: B4.1 net curves are cost_curves cells, ≤ 5 ----
def test_b41_net_curves_are_cost_curves_cells_within_the_palette(synthetic_db):
    b41 = _panel(synthetic_db, "B4.1")
    assert b41.kind == "curve"
    assert len(b41.series) == pins.BEAT4_NET_SERIES == len(SCENARIOS)
    assert [s.colour for s in b41.series] == list(range(len(b41.series)))  # slots 0..3
    # each series is one scenario's `net` column, keyed by flag rate
    for scenario, s in zip(SCENARIOS, b41.series, strict=True):
        net = {
            x_key(rate): value
            for rate, value in _mart(
                synthetic_db,
                "select flag_rate, net from cost_curves where scenario = "
                f"'{scenario}' order by flag_rate",
            )
        }
        assert {p.label: p.value for p in s.points} == net
        assert s.name == text.SCENARIO_NAMES[scenario]
        assert all(p.unit == "eur" for p in s.points)
    # the display-name map is the closed scenario set, in order
    assert tuple(text.SCENARIO_NAMES) == tuple(SCENARIOS)
    # the domain is signed (net dips below zero) and rounds outward
    assert b41.domain == pins.BEAT4_NET_DOMAIN
    # the palette caps at five slots (0..4); B4.1's four are within it, and the
    # slot beyond the palette is refused — the mechanism that bounds the count
    assert len(b41.series) <= 5
    export._series_var(4)  # the last valid slot
    with pytest.raises(RenderRefused):
        export._series_var(5)  # one past the palette
    check_panel(b41)  # markers on grid, one tag per point


def test_the_net_domain_rule_is_signed_and_pinned(synthetic_db):
    assert net_domain([-1_337_879.52, 0.0, 1_309_102.82]) == pins.BEAT4_NET_DOMAIN
    assert net_domain([0.0, 189_978.67]) == (0.0, 200_000.0)  # non-negative: 0 floor
    assert net_domain([-42.0, -1.0]) == (-50.0, 0.0)  # all negative: 0 ceiling
    assert net_domain([]) == (0.0, 1.0)


def test_b41_marker_is_the_default_flag_rate_on_the_grid(synthetic_db):
    b41 = _panel(synthetic_db, "B4.1")
    (default_rate,) = [
        rate
        for rate, is_default in _mart(
            synthetic_db,
            "select flag_rate, is_default from cost_curves where scenario = 'baseline'",
        )
        if is_default
    ]
    assert b41.markers == ((text.MARKER_DEFAULT, default_rate),)
    sec = _section(_html(synthetic_db), "B4.1")
    assert f"{text.MARKER_DEFAULT} ({display(default_rate, 'pct')})" in sec


# --- Done-when 3: B4.2 reads the default sla_threshold row --------------------
def test_b42_threshold_reads_the_default_sla_row(synthetic_db):
    (row,) = _mart(
        synthetic_db,
        "select timer_days, timer_amount_eur, share_under, tag from sla_threshold "
        "where is_default",
    )
    timer_days, amount, share, tag = row
    assert timer_days == pins.TIMER_DEFAULT_DAY
    (series,) = _panel(synthetic_db, "B4.2").series
    values = {p.label: (p.value, p.unit, p.tag) for p in series.points}
    assert values["Clock fires after"] == (float(timer_days), "days", tag)
    assert values["Net-negative below"] == (amount, "eur", tag)
    assert values["Claims under that amount"] == (share, "pct", tag)
    sec = _section(_html(synthetic_db), "B4.2")
    assert pins.BEAT4_FRAGMENTS["threshold day (stat, days)"] in sec
    assert pins.BEAT4_FRAGMENTS["threshold amount (stat, eur)"] in sec
    assert pins.BEAT4_FRAGMENTS["threshold share (stat, pct)"] in sec
    # the arithmetic note is filled from the same cells, never a typed figure
    note = text.threshold_note(
        display(float(timer_days), "days"),
        display(amount, "eur"),
        display(share, "pct"),
    )
    assert note in sec


def test_b42_refuses_when_not_exactly_one_default_row(synthetic_db, tmp_path):
    two = _mutated(
        synthetic_db,
        tmp_path,
        ("update sla_threshold set is_default = true where timer_days = 1",),
    )
    with pytest.raises(RenderRefused) as exc:
        _panels(two)
    assert "B4.2" in str(exc.value) and "\n" not in str(exc.value)


# --- Done-when 4 / invariant 3: the SQL aggregate reproduces summarize --------
def test_b43_sql_aggregate_equals_summarize(synthetic_db):
    raw = [
        {"scenario": scenario, "hold_days": hold_days, "outcome": outcome}
        for scenario, hold_days, outcome in _mart(
            synthetic_db, "select scenario, hold_days, outcome from guardrail_sim"
        )
    ]
    expected = summarize(raw)
    conn = connect("duckdb", database=synthetic_db)
    try:
        got = panels._hold_summary(conn, "B4.3")
    finally:
        conn.close()
    assert set(got) == set(expected) == {s.name for s in SIM_SCENARIOS}
    for name, (mean_hold, released_share, tag) in got.items():
        assert mean_hold == expected[name]["mean_hold_days"]
        assert released_share == expected[name]["timer_released_share"]
        assert tag == pins.COST_MODELED_TAG
    # the pinned values, so a mart rebuild that shifts a hold is caught here too
    for name, cells in pins.SIM_SUMMARY.items():
        assert got[name][0] == cells["mean_hold_days"]
        assert got[name][1] == cells["timer_released_share"]


def test_b43_draws_two_holds_per_fix_and_names_the_released_share(synthetic_db):
    b43 = _panel(synthetic_db, "B4.3")
    assert b43.kind == "grouped_bar"
    assert tuple(text.FIX_NAMES) == pins.BEAT4_FIXES
    before = pins.SIM_SUMMARY["no_fix"]["mean_hold_days"]
    for fix, s in zip(pins.BEAT4_FIXES, b43.series, strict=True):
        cells = {p.label: p.value for p in s.points}
        assert cells == {
            text.HOLD_BEFORE: before,
            text.HOLD_AFTER: pins.SIM_SUMMARY[fix]["mean_hold_days"],
        }
        assert s.name == text.FIX_NAMES[fix]
    sec = _section(_html(synthetic_db), "B4.3")
    assert pins.BEAT4_FRAGMENTS["released share (note, pct)"] in sec
    # the released-share note is filled from the clock's aggregate cell, never a
    # typed figure — the note text is in the section verbatim.
    clock_share = display(pins.SIM_SUMMARY["hold_timer"]["timer_released_share"], "pct")
    assert text.released_note(clock_share) in sec
    # ask_once and both_fixes leave the timer nothing to release (the same hold)
    assert cells[text.HOLD_AFTER] == pins.SIM_SUMMARY["both_fixes"]["mean_hold_days"]


def test_b43_refuses_an_unknown_or_missing_simulator_scenario(synthetic_db, tmp_path):
    renamed = _mutated(
        synthetic_db,
        tmp_path / "unknown",
        ("update guardrail_sim set scenario = 'mystery' where scenario = 'no_fix'",),
    )
    conn = connect("duckdb", database=renamed)
    try:
        with pytest.raises(RenderRefused) as exc:
            panels._hold_summary(conn, "B4.3")
        assert "mystery" in str(exc.value) and "B4.3" in str(exc.value)
    finally:
        conn.close()


# --- Done-when 5 / invariant 4: B4.4 is Pending, no number --------------------
def test_b44_is_pending_and_carries_no_number(synthetic_db):
    b44 = _panel(synthetic_db, "B4.4")
    assert b44.tag == "Pending" and b44.series == () and b44.placeholder
    check_panel(b44)  # a Pending panel with no value is valid
    sec = _section(_html(synthetic_db), "B4.4")
    assert 'class="pending"' in sec and text.BEAT4_PENDING in sec
    # a value on the Pending panel is refused
    with pytest.raises(RenderRefused) as exc:
        check_panel(
            Panel(
                "B4.4",
                "B4.4",
                "t",
                "b",
                "Pending",
                "hero",
                series=(Series("s", 0, (Point("x", 1.0, "Modeled", ""),)),),
            )
        )
    assert "Pending" in str(exc.value)


# --- Done-when 6 / invariant 5: no corpus gate, no key, byte-stable -----------
def test_beat_four_numbers_equal_over_none_and_synthetic(synthetic_db, none_db):
    syn, non = _html(synthetic_db), _html(none_db)
    for pid in pins.BEAT4_PANELS:
        assert _section(syn, pid) == _section(non, pid), pid
    # Beat 4 shows real numbers over ROWS=none, no fixture/nodata/pending state
    for pid in ("B4.1", "B4.2", "B4.3"):
        sec = _section(non, pid)
        for state in ('class="nodata"', 'class="fixture"', 'class="pending"'):
            assert state not in sec, (pid, state)


def test_beat_four_render_is_byte_stable(synthetic_db):
    assert _html(synthetic_db) == _html(synthetic_db)


# --- invariant 1: every Beat 4 number is a tagged mart cell -------------------
def test_every_beat_four_number_is_a_tagged_mart_cell(synthetic_db, tmp_path):
    # A mutated cell in each Beat 4 mart moves its panel and no other.
    before = _html(synthetic_db)
    curve = _mutated(
        synthetic_db,
        tmp_path / "curve",
        ("update cost_curves set net = 777777.0 where scenario = 'both'",),
    )
    assert "€777,777.00" in _section(_html(curve), "B4.1")
    sla = _mutated(
        synthetic_db,
        tmp_path / "sla",
        ("update sla_threshold set timer_amount_eur = 99.99 where is_default",),
    )
    assert ">€99.99<" in _section(_html(sla), "B4.2")
    sim = _mutated(
        synthetic_db,
        tmp_path / "sim",
        ("update guardrail_sim set hold_days = 5 where scenario = 'no_fix'",),
    )
    assert _section(_html(sim), "B4.3") != _section(before, "B4.3")
    # a Beat 4 point with no tag is refused (the render contract over the kinds)
    with pytest.raises(RenderRefused):
        check_panel(
            Panel(
                "B4.9",
                "B4.9",
                "t",
                "b",
                "Modeled",
                "curve",
                series=(Series("s", 0, (Point("0.050", 1.0, "", "", "eur"),)),),
            )
        )


def test_beat_four_bars_carry_the_marts_tag_not_a_literal(synthetic_db, tmp_path):
    mixed = _mutated(
        synthetic_db,
        tmp_path,
        ("update guardrail_sim set tag = 'Measured' where scenario = 'ask_once'",),
    )
    sec = _section(_html(mixed), "B4.3")
    assert "chip chip-measured" in sec and "chip chip-modeled" in sec


def test_the_allowlist_and_queries_gain_the_beat_four_marts():
    for column in ("timer_days", "timer_amount_eur", "share_under", "mean_hold_days"):
        assert column in panels.ALLOWED_COLUMNS
    assert (
        "title" not in panels.ALLOWED_COLUMNS and "body" not in panels.ALLOWED_COLUMNS
    )
    for sql in (panels._Q_GUARDRAIL_AGG, panels._Q_SLA_THRESHOLD):
        assert sql in panels.STUDY_QUERIES
