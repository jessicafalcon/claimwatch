"""Phase 8b — the guardrail simulator (Beat 4). Offline, no key, no clock, no
random draw: the claims are the fitted lognormal read at 1,000 fixed quantiles,
the hold timer is a rule, and the threshold is Beat 3 arithmetic. Every pinned
number is typed from the built output, never guessed."""

from __future__ import annotations

import math
from statistics import NormalDist

import pytest

from models import cost_model
from models import guardrail_sim as gs
from tests import pins

FIT = cost_model.Fit(
    mu=pins.DAMIR_MU, sigma=pins.DAMIR_SIGMA, n=pins.DAMIR_N, emp_p50=pins.DAMIR_EMP_P50
)


# --- the claims are the fit at fixed quantiles, never a random draw -----------


def test_synthetic_amounts_recomputed_by_hand():
    """The first, middle and last synthetic amount, each redone with math and
    statistics from the pinned fit: exp(mu + sigma * z((rank - 0.5)/n))."""
    claims = gs.synthetic_claims(cost_model.defaults(FIT))
    for rank, expected in pins.SYNTHETIC_AMOUNTS.items():
        quantile = (rank - 0.5) / pins.QUANTILE_N
        z = NormalDist().inv_cdf(quantile)
        amount = math.exp(pins.DAMIR_MU + pins.DAMIR_SIGMA * z)
        assert round(amount, 2) == expected
        assert claims[rank - 1].rank == rank
        assert claims[rank - 1].amount_eur == expected


def test_amounts_non_decreasing_and_scenario_invariant():
    """Amounts are non-decreasing in rank and identical in every scenario (they
    read only mu/sigma) — a per-rank amount that differed by scenario would fail
    the last assertion."""
    params = cost_model.defaults(FIT)
    claims = gs.synthetic_claims(params)
    assert len(claims) == pins.QUANTILE_N
    amounts = [c.amount_eur for c in claims]
    assert amounts == sorted(amounts)
    by_scenario = {s.name: gs.simulate(params, s.name) for s in gs.SIM_SCENARIOS}
    for rank in (1, 500, 1000):
        at_rank = {
            name: rows[rank - 1]["amount_eur"] for name, rows in by_scenario.items()
        }
        assert len(set(at_rank.values())) == 1, rank


def test_synthetic_claims_keyed_on_mu_and_sigma():
    """The memoized draw is keyed on (mu, sigma): two fits differing only in sigma
    give different claims — a slider on the fit moves them (spec Pinned decision 1).
    A cache key that dropped sigma would hand the second fit the first fit's stale
    draw and this fails."""
    base = dict(cost_model.defaults(FIT))
    wider = {**base, "sigma": base["sigma"] + 0.5}
    a = [c.amount_eur for c in gs.synthetic_claims(base)]
    b = [c.amount_eur for c in gs.synthetic_claims(wider)]
    assert a != b


# --- the threshold is three formulas over two guesses, linear then flat -------


def test_threshold_linear_in_days_and_share_monotone():
    """Every threshold amount equals the coefficient x min(day, loop) rounded —
    linear in the day up to the baseline loop (21), constant after (friction
    stops accruing when the loop ends) — and the share under it is
    non-decreasing. Three grid days are pinned; the whole grid is checked."""
    params = cost_model.defaults(FIT)
    table = gs.threshold_table(params)
    loop_days = cost_model.evaluate(params, "baseline")["loop_days"]
    friction_per_day = (
        params["contacts"] * params["cost_per_contact"]
        + params["churn_prob"] * (params["arr_eur"] / params["members"])
    ) / loop_days
    coeff = params["fp_share"] * friction_per_day / (1 - params["fp_share"])
    by_day = {r["timer_days"]: r for r in table}
    for row in table:
        expected = round(coeff * min(row["timer_days"], loop_days), 2)
        assert row["timer_amount_eur"] == expected, row["timer_days"]
    for day, pin in pins.SLA_THRESHOLD_SAMPLE.items():
        assert by_day[day]["timer_amount_eur"] == pin["timer_amount_eur"]
        assert by_day[day]["share_under"] == pin["share_under"]
    assert by_day[loop_days]["timer_amount_eur"] == by_day[60]["timer_amount_eur"]
    shares = [r["share_under"] for r in table]
    assert shares == sorted(shares)


def test_threshold_marks_exactly_one_default_day():
    """Exactly one grid row is the default timer day, and it is the default."""
    table = gs.threshold_table(cost_model.defaults(FIT))
    marked = [r for r in table if r["is_default"]]
    assert len(marked) == 1
    assert marked[0]["timer_days"] == pins.TIMER_DEFAULT_DAY


# --- the hold rule is closed: two hold lengths, three outcomes ----------------


def test_hold_rule_every_branch_by_hand():
    """The four branches, each a hand case: timer off; timer on and loop <= timer;
    timer on, loop > timer, claim under; timer on, loop > timer, claim not under.
    The loop <= timer branch is walked at both the strict case (loop < timer) and
    the equality boundary (loop == timer, reachable from the slider ranges), and
    the under-threshold comparison is walked at a claim exactly on the threshold
    (a tie is not "under") so the two guards are pinned strict."""
    small = gs.Claim(rank=1, quantile=0.0005, amount_eur=10.0)
    large = gs.Claim(rank=1000, quantile=0.9995, amount_eur=5000.0)
    on_threshold = gs.Claim(rank=500, quantile=0.5, amount_eur=42.67)
    long_loop = {"loop_days": 21, "timer_days": 14}
    short_loop = {"loop_days": 7, "timer_days": 14}
    equal_loop = {"loop_days": 14, "timer_days": 14}
    assert gs.hold(small, long_loop, timer_on=False, timer_amount=42.67) == (
        21,
        "loop_released",
    )
    assert gs.hold(small, short_loop, timer_on=True, timer_amount=42.67) == (
        7,
        "loop_released",
    )
    assert gs.hold(small, equal_loop, timer_on=True, timer_amount=42.67) == (
        14,
        "loop_released",
    )
    assert gs.hold(small, long_loop, timer_on=True, timer_amount=42.67) == (
        14,
        "timer_released",
    )
    assert gs.hold(on_threshold, long_loop, timer_on=True, timer_amount=42.67) == (
        21,
        "timer_escalated",
    )
    assert gs.hold(large, long_loop, timer_on=True, timer_amount=42.67) == (
        21,
        "timer_escalated",
    )


def test_share_under_is_strict_below():
    """A claim exactly at the threshold is not counted under it — the share-under
    guard is strict `<`, so the pinned share_under == timer_released-share identity
    (a claim on the threshold escalates, it is not released) holds at a tie."""
    claims = (
        gs.Claim(rank=1, quantile=0.25, amount_eur=10.0),
        gs.Claim(rank=2, quantile=0.5, amount_eur=42.67),
        gs.Claim(rank=3, quantile=0.75, amount_eur=100.0),
    )
    assert gs.share_under(claims, 42.67) == 1 / 3


# --- the scenarios are a closed set mapped onto the cost-model scenarios -------


def test_sim_scenarios_map_onto_cost_model_scenarios():
    """Every simulator scenario pairs with a member of cost_model.SCENARIOS, the
    mapping is the pinned one, and the contacts_once flag agrees with whether the
    paired scenario sets contacts to one."""
    params = cost_model.defaults(FIT)
    assert {s.name for s in gs.SIM_SCENARIOS} == set(pins.SIM_SCENARIO_MAP)
    for s in gs.SIM_SCENARIOS:
        assert s.curves_scenario in cost_model.SCENARIOS
        assert pins.SIM_SCENARIO_MAP[s.name] == s.curves_scenario
        applied = cost_model._apply_scenario(params, s.curves_scenario)
        assert (applied["contacts"] == 1.0) == s.contacts_once


def test_unknown_scenario_refused():
    """A name outside the set is refused at both layers, never simulated silently."""
    params = cost_model.defaults(FIT)
    with pytest.raises(ValueError, match="unknown simulator scenario"):
        gs.simulate(params, "fix_5")
    with pytest.raises(ValueError, match="unknown scenario"):
        cost_model.evaluate(params, "fix_5")


def test_timer_amount_is_the_baseline_one():
    """The timer is set from the un-fixed world: hold_timer releases claims under
    the baseline threshold, not under churn_halved's (the two differ)."""
    params = cost_model.defaults(FIT)
    claims = gs.synthetic_claims(params)
    baseline_amount = cost_model.evaluate(params, "baseline")["timer_amount_eur"]
    churn_amount = cost_model.evaluate(params, "churn_halved")["timer_amount_eur"]
    assert baseline_amount != churn_amount
    released = sum(
        1 for r in gs.simulate(params, "hold_timer") if r["outcome"] == "timer_released"
    )
    assert released == sum(1 for c in claims if c.amount_eur < baseline_amount)
    assert released != sum(1 for c in claims if c.amount_eur < churn_amount)


# --- a fix never lengthens a hold ---------------------------------------------


def test_a_fix_never_lengthens_a_hold():
    """Row by row over the grid: each single fix holds no longer than no_fix, and
    both_fixes holds no longer than either single fix."""
    params = cost_model.defaults(FIT)
    holds = {
        s.name: [r["hold_days"] for r in gs.simulate(params, s.name)]
        for s in gs.SIM_SCENARIOS
    }
    for i in range(pins.QUANTILE_N):
        assert holds["ask_once"][i] <= holds["no_fix"][i]
        assert holds["hold_timer"][i] <= holds["no_fix"][i]
        assert holds["both_fixes"][i] <= holds["ask_once"][i]
        assert holds["both_fixes"][i] <= holds["hold_timer"][i]
