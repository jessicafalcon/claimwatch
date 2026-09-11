"""Phase 8a — the cost model (Beat 3). Offline, no key, no clock: the formulas
are data in models/cost_model.py, evaluated over parameters that are either
sourced (recomputed from the record here by hand) or declared guesses with a
range. Every pinned number is typed from the built output, never guessed."""

from __future__ import annotations

import math

import pytest

from models.cost_model import (
    _ROUNDING,
    CURVE_FORMULAS,
    FLAG_RATE_GRID,
    FORMULAS,
    POINT_FORMULAS,
    SCENARIOS,
    Fit,
    Formula,
    Parameter,
    _apply_scenario,
    _crossover,
    _marginal_crossover,
    check_parameter,
    curves,
    defaults,
    evaluate,
    fit_parameters,
    format_model,
    parameters,
)
from tests import pins

FIT = Fit(
    mu=pins.DAMIR_MU,
    sigma=pins.DAMIR_SIGMA,
    n=pins.DAMIR_N,
    emp_p50=pins.DAMIR_EMP_P50,
    emp_mean=pins.DAMIR_EMP_MEAN,
)


# --- the formulas are data, evaluated to the pins -----------------------------


def test_formulas_evaluate_to_the_pins():
    """Every point output and both crossovers, per scenario, equal the built
    output pinned in tests/pins.py — the defaults are not tuned to a story."""
    values = defaults(FIT)
    for scenario in SCENARIOS:
        assert evaluate(values, scenario) == pins.COST_OUTPUTS[scenario], scenario
        _, crossovers = curves(values, scenario)
        assert crossovers == pins.COST_CROSSOVERS[scenario], scenario


def test_make_model_prints_each_expression_beside_its_value():
    """format_model prints every formula's expression text and, for the baseline,
    the value it produces — the printed formula and the number are one entry."""
    out = format_model(FIT)
    baseline = pins.COST_OUTPUTS["baseline"]
    for f in POINT_FORMULAS:
        assert f.expression in out
        assert f"-> {baseline[f.name]}" in out
    for f in CURVE_FORMULAS:
        assert f.expression in out
    assert "-> 0.095" in out  # the baseline crossover
    assert "-> 0.05" in out  # the marginal crossover / the default marker
    # One column for every point formula: the name is padded to the longest
    # name, so the "=" sits at the same offset on each line (9h, preflight).
    width = max(len(f.name) for f in POINT_FORMULAS)
    for f in POINT_FORMULAS:
        assert f"  {f.name.ljust(width)} = {f.expression}" in out
    # The parameter table too: the longest name sets the column (round 2,
    # coherence-auditor #2), so the default column starts at one offset.
    params = parameters(FIT)
    p_width = max(len(p.name) for p in params)
    for p in params:
        assert f"  {p.name.ljust(p_width)} {p.default:>16} " in out


def test_make_model_prints_the_unit_beside_each_value():
    """The unit is part of the entry, so the terminal shows it beside the number
    the way the mart stores it and the page will format it — one unit, one
    place: `-> <value> (<unit>)` for every formula, curve rows included."""
    out = format_model(FIT)
    baseline = pins.COST_OUTPUTS["baseline"]
    crossovers = pins.COST_CROSSOVERS["baseline"]
    for f in POINT_FORMULAS:
        assert f"-> {baseline[f.name]} ({f.unit})" in out, f.name
    for f in CURVE_FORMULAS:
        assert f"-> {crossovers[f.name]} ({f.unit})" in out, f.name
    # A crossover that never happens (the `both` scenario) prints its absence
    # with the unit it would have carried, never a bare `None`.
    never = pins.COST_CROSSOVERS["both"]["crossover_flag_rate"]
    assert never is None
    assert "-> None (rate)" in out


def test_every_formula_carries_a_rounding_unit():
    """Every FORMULAS entry's unit is a key of the one rounding table and equals
    its pin (the two curve formulas' `rate` included). On the point path
    `rounded()` refuses an unknown unit at evaluation; the curve path never
    rounds by `f.unit`, so for a curve formula this test is the guard."""
    assert {f.name: f.unit for f in FORMULAS} == pins.COST_FORMULA_UNITS
    for f in FORMULAS:
        assert f.unit in _ROUNDING, f.name
    # The field is required on the entry itself (no default, no map beside it).
    with pytest.raises(TypeError):
        Formula("x", "y", "point", lambda v: 0.0)  # type: ignore[call-arg]


# --- every parameter: a closed sourcing set, a citation when sourced, a range -


def test_parameters_sourcing_is_a_closed_set():
    """Each parameter's sourcing is one of the two words; a third word refuses."""
    for p in parameters(FIT):
        assert p.sourcing in ("sourced", "unsourced")
    with pytest.raises(ValueError, match="sourcing"):
        check_parameter(Parameter("x", 1.0, "u", "estimated", "", 0.0, 2.0))


def test_sourced_needs_a_citation_every_range_holds_its_default():
    """A sourced parameter with no citation, an unsourced one that carries one,
    and a default outside its range each refuse; every real parameter passes."""
    with pytest.raises(ValueError, match="no citation"):
        check_parameter(Parameter("x", 1.0, "u", "sourced", "", 0.0, 2.0))
    with pytest.raises(ValueError, match="carries a citation"):
        check_parameter(Parameter("x", 1.0, "u", "unsourced", "a", 0.0, 2.0))
    with pytest.raises(ValueError, match="outside range"):
        check_parameter(Parameter("x", 5.0, "u", "unsourced", "", 0.0, 2.0))
    for p in parameters(FIT):
        assert p.low <= p.default <= p.high


def test_sourced_defaults_recomputed_by_hand():
    """Revenue per member, the mean claim, claim volume and the mu/sigma ranges,
    each redone with math from the record — the value the model uses equals the
    hand recomputation."""
    values = defaults(FIT)
    baseline = pins.COST_OUTPUTS["baseline"]
    assert values["arr_eur"] / values["members"] == baseline["customer_value"]
    mean_full = math.exp(pins.DAMIR_MU + pins.DAMIR_SIGMA**2 / 2)
    assert round(mean_full, 2) == baseline["mean_claim"]
    assert round(values["refunded_eur"] / mean_full) == baseline["claims"]
    se_mu = pins.DAMIR_SIGMA / math.sqrt(pins.DAMIR_N)
    se_sigma = pins.DAMIR_SIGMA / math.sqrt(2 * pins.DAMIR_N)
    mu = next(p for p in parameters(FIT) if p.name == "mu")
    sigma = next(p for p in parameters(FIT) if p.name == "sigma")
    assert (mu.low, mu.high) == pins.DAMIR_MU_RANGE
    assert (mu.low, mu.high) == (
        round(pins.DAMIR_MU - 2 * se_mu, 6),
        round(pins.DAMIR_MU + 2 * se_mu, 6),
    )
    assert (sigma.low, sigma.high) == (
        round(pins.DAMIR_SIGMA - 2 * se_sigma, 6),
        round(pins.DAMIR_SIGMA + 2 * se_sigma, 6),
    )


def test_timer_formulas_recomputed_by_hand():
    """The three hold-timer point formulas (8b), redone with math from the record:
    the loop is contacts x days_per_round; friction per day is the model's
    friction for one false positive spread over the loop; the threshold is
    fp_share x friction_per_day x min(timer_days, loop_days) / (1 - fp_share) —
    the claim amount below which a hold that long is net-negative in expectation."""
    values = defaults(FIT)
    for scenario in SCENARIOS:
        p = _apply_scenario(values, scenario)
        out = evaluate(values, scenario)
        loop_days = p["contacts"] * p["days_per_round"]
        assert out["loop_days"] == round(loop_days)
        friction_per_day = (
            p["contacts"] * p["cost_per_contact"]
            + p["churn_prob"] * (p["arr_eur"] / p["members"])
        ) / loop_days
        assert out["friction_per_day"] == round(friction_per_day, 2)
        held = min(p["timer_days"], loop_days)
        timer_amount = p["fp_share"] * friction_per_day * held / (1 - p["fp_share"])
        assert out["timer_amount_eur"] == round(timer_amount, 2)
        assert (
            out["timer_amount_eur"] == pins.COST_OUTPUTS[scenario]["timer_amount_eur"]
        )


def test_the_reader_one_cent_floor_is_the_model_euro_rounding_scale():
    """opendata.fit refuses a mean under one cent because models.cost_model
    rounds euros to two places: the two constants are one fact, bound here
    since fit.py cannot import the model (round 2, code-reviewer #2)."""
    from opendata.fit import _MIN_EUR_MEAN

    one_euro_unit = 10 ** -_ROUNDING["eur"]  # 0.01: what euro rounding keeps
    assert one_euro_unit == _MIN_EUR_MEAN  # the constant on the right: SIM300


def test_fit_parameters_are_the_four_read_rows_two_of_them_fixed_marks():
    """The fit supplies four sourced rows in order — mu, sigma, emp_p50,
    emp_mean — each cited to the artifact; the two cells read off the sample
    are fixed marks (low == default == high), the two log-moments are not."""
    rows = fit_parameters(FIT)
    assert tuple(p.name for p in rows) == ("mu", "sigma", "emp_p50", "emp_mean")
    for p in rows:
        assert p.sourcing == "sourced" and "claim_cost_fit.csv" in p.citation
    fixed = {p.name for p in rows if p.low == p.default == p.high}
    assert fixed == {"emp_p50", "emp_mean"}
    emp_mean = rows[-1]
    assert emp_mean.default == round(pins.DAMIR_EMP_MEAN, 2) and emp_mean.unit == "€"
    assert [p.name for p in parameters(FIT)][4:8] == [p.name for p in rows]


def test_claims_at_mean_cell_is_the_division_by_hand():
    """9h, invariant 3: the contrast count is refunds paid over the sample's
    mean cell, redone by hand from the parameter table; the same on every
    scenario (nothing a scenario toggles enters it); the pinned figure is the
    same whether the reader divides by the page's two-place cell or the
    artifact's six-place one."""
    values = defaults(FIT)
    emp_mean = next(p for p in parameters(FIT) if p.name == "emp_mean")
    assert emp_mean.sourcing == "sourced" and emp_mean.citation
    assert emp_mean.low == emp_mean.default == emp_mean.high  # a fixed mark
    by_hand = round(values["refunded_eur"] / emp_mean.default)
    assert by_hand == pins.COST_OUTPUTS["baseline"]["claims_at_mean_cell"]
    assert round(values["refunded_eur"] / pins.DAMIR_EMP_MEAN) == by_hand
    for scenario in SCENARIOS:
        assert evaluate(values, scenario)["claims_at_mean_cell"] == by_hand
    contrast = next(f for f in POINT_FORMULAS if f.name == "claims_at_mean_cell")
    assert contrast.expression.startswith("refunded_eur / emp_mean")
    names = [f.name for f in POINT_FORMULAS]
    assert names.index("claims_at_mean_cell") == names.index("claims") + 1
    assert "claims_at_mean_cell" in format_model(FIT)


def test_mean_claim_prints_its_bias_and_the_median_cell():
    """mean_claim's expression carries the bias direction (a DAMIR cell sums >= 1
    claims, so the mean overstates a claim and understates claims/friction), and
    median_cell (emp_p50) prints beside it as the contrast."""
    mean = next(f for f in POINT_FORMULAS if f.name == "mean_claim")
    assert "overstates" in mean.expression and "understates" in mean.expression
    median = next(f for f in POINT_FORMULAS if f.name == "median_cell")
    assert "emp_p50" in median.expression
    assert evaluate(defaults(FIT))["median_cell"] == pins.DAMIR_EMP_P50


# --- the curves cross; both grid rules; one default marker --------------------


def test_crossover_is_first_grid_point_with_negative_net():
    """The crossover is the first grid flag_rate whose net is negative; a grid
    whose net never turns negative yields None (each checked by hand)."""
    rows = [
        {"flag_rate": 0.01 * i, "net": n} for i, n in enumerate([9.0, 5.0, -1.0, -8.0])
    ]
    assert _crossover(rows) == 0.02
    assert _crossover([{"flag_rate": 0.01 * i, "net": 3.0} for i in range(4)]) is None
    # the built baseline crosses where the net column first goes below zero
    grid, crossovers = curves(defaults(FIT), "baseline")
    first_negative = next(r["flag_rate"] for r in grid if r["net"] < 0)
    assert (
        crossovers["crossover_flag_rate"]
        == first_negative
        == pins.COST_CROSSOVERS["baseline"]["crossover_flag_rate"]
    )


def test_marginal_crossover_is_first_grid_point_below_the_previous():
    """The marginal crossover is the first grid flag_rate whose net is below the
    previous point's; a net that only rises yields None."""
    rising_then_fall = [
        {"flag_rate": 0.01 * i, "net": n} for i, n in enumerate([1.0, 2.0, 3.0, 2.5])
    ]
    assert _marginal_crossover(rising_then_fall) == 0.03
    assert (
        _marginal_crossover(
            [{"flag_rate": 0.01 * i, "net": float(i)} for i in range(5)]
        )
        is None
    )


def test_marginal_crossover_needs_a_strict_drop_not_a_plateau():
    """A flat plateau then a decline: the marginal crossover is the decline point,
    not the plateau — the rule is strictly below the previous point, so `<=` would
    wrongly fire on the plateau (invariant 6)."""
    rows = [
        {"flag_rate": 0.01 * i, "net": n} for i, n in enumerate([1.0, 2.0, 2.0, 1.5])
    ]
    assert _marginal_crossover(rows) == 0.03


def test_curves_mark_exactly_one_default_per_scenario():
    """Exactly one grid row per scenario is the default flag rate (0.05), the
    'you are here' marker, and 41 rows span the grid."""
    values = defaults(FIT)
    for scenario in SCENARIOS:
        grid, _ = curves(values, scenario)
        assert len(grid) == pins.FLAG_RATE_GRID_POINTS
        marked = [r for r in grid if r["is_default"]]
        assert len(marked) == 1, scenario
        assert marked[0]["flag_rate"] == values["flag_rate"] == 0.05
    assert len(FLAG_RATE_GRID) == pins.FLAG_RATE_GRID_POINTS


# --- scenarios are a closed set of parameter overrides -----------------------


def test_scenarios_are_a_closed_set():
    """The scenario names are exactly the four; an unknown name refuses."""
    assert set(SCENARIOS) == set(pins.COST_SCENARIOS)
    with pytest.raises(ValueError, match="unknown scenario"):
        evaluate(defaults(FIT), "fix_4")


def test_each_scenario_changes_only_its_toggled_parameters():
    """Each scenario differs from the defaults in exactly its toggled parameters:
    contacts_once sets contacts to 1, churn_halved halves churn_prob, both does
    both; baseline changes nothing."""
    base = defaults(FIT)

    def _changed(scenario: str) -> dict[str, tuple[float, float]]:
        after = _apply_scenario(base, scenario)
        return {k: (base[k], after[k]) for k in base if base[k] != after[k]}

    assert _changed("baseline") == {}
    assert _changed("contacts_once") == {"contacts": (3.0, 1.0)}
    assert _changed("churn_halved") == {"churn_prob": (0.05, 0.025)}
    assert set(_changed("both")) == {"contacts", "churn_prob"}
