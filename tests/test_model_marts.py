"""Phase 8a — the three cost-model marts, filled inside rebuild() from
models/cost_model.py. Offline, no key: the marts compute over the tracked fit,
so they fill on every ROWS input, are byte-stable across runs, and carry the
Modeled tag. models/ imports only stdlib that reads no clock and no RNG."""

from __future__ import annotations

import ast

import pytest

from models import cost_model
from pipeline.build import read_model_fit, rebuild
from pipeline.cli import main
from pipeline.warehouse import ROOT, connect, database_for
from tests import pins
from tests.repo_text import repo_text

pytestmark = pytest.mark.slow  # slow: kept out of the fast edit-loop hook

_MARTS = ("cost_model_params", "cost_model_outputs", "cost_curves")
# stdlib that reads no clock and draws no random number, plus the package's own
# modules; 8b widened this by `statistics` (the normal quantile) and `models`.
_IMPORT_ALLOWLIST = {
    "math",
    "statistics",
    "dataclasses",
    "collections",
    "typing",
    "__future__",
    "models",
}
# Attribute names models/ must never touch: a clock, and statistics' one random
# method (NormalDist().samples) — the gap the import allowlist cannot close, since
# `statistics` is allowed for the quantile.
_FORBIDDEN_ATTRS = {"samples", "now", "today", "utcnow", "time", "random", "seed"}


def _built(tmp_path, rows: str = "synthetic", run_id: str = "test"):
    rebuild("duckdb", rows, root=tmp_path, run_id=run_id)
    return connect("duckdb", database=database_for(rows, tmp_path))


def _rows(conn, table: str, columns: str) -> list[tuple]:
    return conn.execute(f"select {columns} from {table} order by 1, 2").fetchall()


def test_outputs_mart_equals_formulas_at_defaults(tmp_path):
    """Every cost_model_outputs value equals the FORMULAS callable evaluated over
    the defaults for its scenario — mart and code cannot drift."""
    fit = read_model_fit()
    values = cost_model.defaults(fit)
    expected: dict[tuple[str, str], float | None] = {}
    for scenario in cost_model.SCENARIOS:
        for name, value in cost_model.evaluate(values, scenario).items():
            expected[(scenario, name)] = value
        _, crossovers = cost_model.curves(values, scenario)
        for name, value in crossovers.items():
            expected[(scenario, name)] = value
    conn = _built(tmp_path)
    try:
        got = {
            (scenario, name): value
            for scenario, name, value in conn.execute(
                "select scenario, name, value from cost_model_outputs"
            ).fetchall()
        }
    finally:
        conn.close()
    assert got == expected


def test_curves_mart_equals_curves_at_defaults(tmp_path):
    """Every cost_curves grid row equals curves() over the defaults for its
    scenario — the B3.2 chart's fraud/friction/net/marker columns cannot drift
    from the callable (invariant 1, the curve half)."""
    fit = read_model_fit()
    values = cost_model.defaults(fit)
    expected: dict[tuple[str, float], tuple] = {}
    for scenario in cost_model.SCENARIOS:
        grid, _ = cost_model.curves(values, scenario)
        for row in grid:
            expected[(scenario, row["flag_rate"])] = (
                row["fraud_saved"],
                row["friction_cost"],
                row["net"],
                row["is_default"],
            )
    conn = _built(tmp_path)
    try:
        got = {
            (scenario, flag_rate): (fraud, friction, net, is_default)
            for scenario, flag_rate, fraud, friction, net, is_default in conn.execute(
                "select scenario, flag_rate, fraud_saved, friction_cost, net, "
                "is_default from cost_curves"
            ).fetchall()
        }
    finally:
        conn.close()
    assert got == expected


def test_params_mart_has_one_row_per_parameter(tmp_path):
    """cost_model_params holds one row per parameter, each cell equal to the
    Parameter it came from."""
    params = cost_model.parameters(read_model_fit())
    conn = _built(tmp_path)
    try:
        rows = conn.execute(
            "select name, default_value, unit, sourcing, citation, low, high, tag "
            "from cost_model_params"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == pins.COST_PARAM_ROWS
    by_name = {r[0]: r for r in rows}
    assert set(by_name) == {p.name for p in params}
    for p in params:
        assert by_name[p.name] == (
            p.name,
            p.default,
            p.unit,
            p.sourcing,
            p.citation,
            p.low,
            p.high,
            pins.COST_MODELED_TAG,
        )


def test_outputs_mart_carries_each_formulas_unit(tmp_path):
    """Every cost_model_outputs row's unit equals the FORMULAS entry's own unit
    for that name, in every scenario — the column is written from the entry, so
    the page's number format cannot drift from the model's rounding unit; a
    NULL crossover still carries `rate`."""
    conn = _built(tmp_path)
    try:
        rows = conn.execute(
            "select scenario, name, unit, value from cost_model_outputs"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == pins.COST_OUTPUT_ROWS
    for scenario, name, unit, value in rows:
        assert unit == pins.COST_FORMULA_UNITS[name], (scenario, name)
        if value is None:
            assert unit == "rate", (scenario, name)
    assert any(value is None for *_, value in rows)  # the NULL case is exercised


def test_three_marts_filled_on_every_input(tmp_path):
    """none, synthetic and samples each leave the three marts with their constant
    counts — the marts compute over the fit, not the input."""
    for rows in ("none", "synthetic", "samples"):
        conn = _built(tmp_path / rows, rows)
        try:
            counts = {
                m: conn.execute(f"select count(*) from {m}").fetchone()[0]
                for m in _MARTS
            }
        finally:
            conn.close()
        assert counts == {
            "cost_model_params": pins.COST_PARAM_ROWS,
            "cost_model_outputs": pins.COST_OUTPUT_ROWS,
            "cost_curves": pins.COST_CURVE_ROWS,
        }, rows


def test_two_rebuilds_identical_model_mart_rows(tmp_path):
    """Two rebuilds with different run_ids into the same file give byte-identical
    model-mart rows (run_id aside) — run_id is provenance, in no key or sort."""
    param_cols = "name, default_value, unit, sourcing, citation, low, high, tag"
    output_cols = "scenario, name, expression, value, unit, tag"
    curve_cols = "scenario, flag_rate, fraud_saved, friction_cost, net, is_default, tag"

    conn = _built(tmp_path, run_id="run-1")
    try:
        first = (
            _rows(conn, "cost_model_params", param_cols),
            _rows(conn, "cost_model_outputs", output_cols),
            _rows(conn, "cost_curves", curve_cols),
        )
        run_ids_1 = {
            r[0]
            for r in conn.execute("select run_id from cost_model_params").fetchall()
        }
    finally:
        conn.close()
    conn = _built(tmp_path, run_id="run-2")
    try:
        second = (
            _rows(conn, "cost_model_params", param_cols),
            _rows(conn, "cost_model_outputs", output_cols),
            _rows(conn, "cost_curves", curve_cols),
        )
        run_ids_2 = {
            r[0]
            for r in conn.execute("select run_id from cost_model_params").fetchall()
        }
    finally:
        conn.close()
    assert first == second
    assert run_ids_1 == {"run-1"} and run_ids_2 == {"run-2"}  # run_id did change


def test_rows_carry_run_id_and_modeled_tag(tmp_path):
    """Every model-mart row carries the rebuild's run_id and the Modeled tag."""
    conn = _built(tmp_path, run_id="rid")
    try:
        for mart in _MARTS:
            marks = conn.execute(f"select distinct run_id, tag from {mart}").fetchall()
            assert marks == [("rid", pins.COST_MODELED_TAG)], mart
    finally:
        conn.close()


def test_models_imports_only_stdlib_math():
    """Every import in models/ is from the closed allowlist (stdlib that reads no
    clock and no RNG, plus the package's own modules) — no opendata, pipeline or
    ingest, no network, database or model-client module — and no source touches a
    forbidden attribute (a clock, or NormalDist().samples, the one random method
    the allowed `statistics` carries)."""
    for path in sorted((ROOT / "models").glob("*.py")):
        tree = ast.parse(repo_text(path))
        roots: set[str] = set()
        attrs: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
            elif isinstance(node, ast.Attribute):
                attrs.add(node.attr)
        assert roots <= _IMPORT_ALLOWLIST, (path.name, roots - _IMPORT_ALLOWLIST)
        assert not (attrs & _FORBIDDEN_ATTRS), (path.name, attrs & _FORBIDDEN_ATTRS)


def test_read_model_fit_refuses_a_malformed_artifact(tmp_path):
    """A hand-corrupted fit artifact is refused as a PageShapeError, so the model
    and rebuild CLI paths surface one line and exit 2 (main catches it), never a
    traceback."""
    from ingest.parsed import PageShapeError

    bad = tmp_path / "bad.csv"
    bad.write_text("name,value\nmu,abc\n", encoding="utf-8")  # non-numeric, short
    with pytest.raises(PageShapeError, match="fit artifact is unreadable"):
        read_model_fit(bad)


def test_make_model_is_byte_identical_on_rerun(capsys):
    """`make model` prints identical text on a rerun — no clock, no key."""
    assert main(["model"]) == 0
    first = capsys.readouterr().out
    assert main(["model"]) == 0
    second = capsys.readouterr().out
    assert first == second and first.strip()
