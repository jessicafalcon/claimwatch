"""The guardrail simulator (PROJECT_BRIEF.md §3 Beat 4, §7): how long a wrongly
held claim stays held before and after three boring fixes, and the hold-timer
threshold computed from the Beat 3 cost model.

A simulator here is not a random experiment. The claims are the DAMIR lognormal
fit — a real distribution, but synthetic claims: no individual claim is public —
read at a thousand evenly spaced quantiles, the same thousand amounts every run,
each one a formula a reader can redo by hand. The hold timer is a rule applied
to each claim, not a draw: with the timer off a claim takes the whole document
loop; with it on, a small claim is released at the timer (pay now, audit after)
and a large one is escalated to a person at the timer but still takes the loop,
because a person's turnaround has no public anchor and is not modeled.

Rules are data, the same way formulas are (models/cost_model.py). `RULES` is an
ordered tuple where each entry carries a name, the rule written out as text (what
`make simulate` prints), and the callable that computes it — so the printed rule
and the computed row are one entry and cannot drift. The threshold itself is Beat
3 arithmetic and lives in `cost_model.py::FORMULAS`, read here at the `baseline`
evaluation; this module owns only the draw, the hold and the share-under count.

No clock, no key, no file, no random draw: `statistics.NormalDist().inv_cdf` is
the standard-normal quantile (its own C and pure-Python paths compute the same
algorithm), and every number is rounded at the cost model's one site."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp
from statistics import NormalDist, fmean

from models import cost_model

# The claims are 1,000 evenly spaced quantile midpoints (i − ½) / n. 1,000 puts
# the share-under resolution at 0.1 %, finer than any slider; a midpoint keeps
# the draw off the 0 and 1 tails NormalDist().inv_cdf cannot take.
_N = 1000
QUANTILE_GRID: tuple[float, ...] = tuple((i - 0.5) / _N for i in range(1, _N + 1))

# The days the SLA-threshold table walks: 1..60, so the default timer (14) lies
# on the grid and exactly one row is the default.
TIMER_DAY_GRID: tuple[int, ...] = tuple(range(1, 61))


@dataclass(frozen=True)
class Claim:
    """One synthetic claim: its rank on the quantile grid (1..n), the quantile it
    sits at (rounded as a rate), and its amount in euros (the fit read at that
    quantile, rounded at the one site). Synthetic — no individual claim is
    public — drawn from a distribution fitted to real public data."""

    rank: int
    quantile: float
    amount_eur: float


@dataclass(frozen=True)
class Rule:
    """One entry of the simulator: its name, the rule written out as text (what
    the study prints), and the callable that computes it — the mirror of the cost
    model's Formula, so the printed rule and the computed row are one entry."""

    name: str
    text: str
    fn: Callable[..., object]


@dataclass(frozen=True)
class SimScenario:
    """One simulator scenario: its own name, the cost-curve scenario it pairs with
    (so Phase 9 lays hold durations beside the curves that move on one join),
    whether it applies the ask-once fix, and whether the hold timer is on. A
    closed set — an unknown name is refused, never simulated silently."""

    name: str
    curves_scenario: str
    contacts_once: bool
    timer_on: bool


# The four scenarios, in order. `hold_timer` pairs with `churn_halved` because
# brief §7 shows the timer's benefit as an illustrative halved churn — the
# cost-model effect the study displays beside the timer, not a quantity the
# simulator derives. `both_fixes` runs a one-round loop that ends before the
# default timer, so its clock never fires and its rows equal `ask_once`'s.
SIM_SCENARIOS: tuple[SimScenario, ...] = (
    SimScenario("no_fix", "baseline", False, False),
    SimScenario("ask_once", "contacts_once", True, False),
    SimScenario("hold_timer", "churn_halved", False, True),
    SimScenario("both_fixes", "both", True, True),
)

# The three possible outcomes of a hold — a closed set, never a free string.
OUTCOMES: tuple[str, ...] = ("loop_released", "timer_released", "timer_escalated")


def _sim_scenario(name: str) -> SimScenario:
    """The simulator scenario for `name`, or a refusal — an unknown name never
    falls through to a default."""
    for s in SIM_SCENARIOS:
        if s.name == name:
            return s
    known = tuple(s.name for s in SIM_SCENARIOS)
    raise ValueError(f"unknown simulator scenario {name!r}; expected {known}")


def _synthetic_amount(params: Mapping[str, float], rank: int) -> float:
    """The amount at one rank: the fitted lognormal read at the quantile
    midpoint (rank − ½) / n, over the mu/sigma parameters (so a slider on the fit
    moves the claims). Full precision; the caller rounds at the one site."""
    quantile = (rank - 0.5) / _N
    z = NormalDist().inv_cdf(quantile)
    return exp(params["mu"] + params["sigma"] * z)


def synthetic_claims(params: Mapping[str, float]) -> tuple[Claim, ...]:
    """One Claim per point of the fixed quantile grid, non-decreasing in rank and
    identical in every scenario (it reads only mu/sigma). The quantile is stored
    as a rate and the amount (the fitted lognormal read at that quantile) as
    euros, both rounded at the cost model's one site."""
    return tuple(
        Claim(
            rank=rank,
            quantile=cost_model.rounded("rate", quantile),
            amount_eur=cost_model.rounded("eur", _synthetic_amount(params, rank)),
        )
        for rank, quantile in enumerate(QUANTILE_GRID, start=1)
    )


def hold(
    claim: Claim,
    scenario_params: Mapping[str, int],
    timer_on: bool,
    timer_amount: float,
) -> tuple[int, str]:
    """How long this claim is held and why, over the four branches. `loop_days`
    and `timer_days` come in as whole days. Timer off, or on but the loop is no
    longer than the timer, the hold is the loop (`loop_released`); timer on and
    the claim under the threshold, the hold is the timer (`timer_released` — pay
    now, audit after); otherwise a person is pulled in at the timer and the claim
    still completes the loop (`timer_escalated`). The hold is the loop or the
    timer, the outcome one of three names."""
    loop_days = scenario_params["loop_days"]
    timer_days = scenario_params["timer_days"]
    if not timer_on or loop_days <= timer_days:
        return loop_days, "loop_released"
    if claim.amount_eur < timer_amount:
        return timer_days, "timer_released"
    return loop_days, "timer_escalated"


def share_under(claims: Sequence[Claim], amount: float) -> float:
    """The share of synthetic claims below `amount` — the fraction the timer
    releases at a threshold of that size. Full precision; the caller rounds."""
    return sum(1 for c in claims if c.amount_eur < amount) / len(claims)


RULES: tuple[Rule, ...] = (
    Rule(
        "synthetic_amount",
        "exp(mu + sigma * z((rank - 0.5) / n))  -- a real distribution, synthetic "
        "claims: no individual claim is public",
        _synthetic_amount,
    ),
    Rule(
        "hold",
        "loop_days, unless the timer is on and shorter and the claim is under the "
        "threshold (then timer_days); a claim over the threshold is escalated and "
        "still takes the loop",
        hold,
    ),
    Rule(
        "share_under",
        "count(amount_eur < amount) / n",
        share_under,
    ),
)


def _loop_and_timer_days(
    params: Mapping[str, float], curves_scenario: str
) -> dict[str, int]:
    """The whole-day loop for a scenario (the cost model's `loop_days` evaluated
    at that scenario — so `ask_once`'s one-round loop comes through the same
    FORMULAS) and the timer days (a parameter). Both as ints for the DDL columns
    and the hold comparison."""
    loop_days = cost_model.evaluate(params, curves_scenario)["loop_days"]
    timer_days = cost_model.rounded("count", params["timer_days"])
    return {"loop_days": loop_days, "timer_days": timer_days}


def simulate(params: Mapping[str, float], scenario: str) -> list[dict[str, object]]:
    """One row per synthetic claim for one simulator scenario: the claim, the
    scenario's loop, the hold and its outcome. The timer amount is the cost
    model's `timer_amount_eur` at `baseline` — the recommendation is made once,
    before any fix — whatever the scenario. An unknown scenario is refused."""
    sim = _sim_scenario(scenario)
    scenario_params = _loop_and_timer_days(params, sim.curves_scenario)
    timer_amount = cost_model.evaluate(params, "baseline")["timer_amount_eur"]
    rows: list[dict[str, object]] = []
    for claim in synthetic_claims(params):
        hold_days, outcome = hold(claim, scenario_params, sim.timer_on, timer_amount)
        rows.append(
            {
                "scenario": sim.name,
                "curves_scenario": sim.curves_scenario,
                "claim_rank": claim.rank,
                "quantile": claim.quantile,
                "amount_eur": claim.amount_eur,
                "loop_days": scenario_params["loop_days"],
                "hold_days": hold_days,
                "outcome": outcome,
            }
        )
    return rows


def threshold_table(params: Mapping[str, float]) -> list[dict[str, object]]:
    """One row per timer day of the grid, at the baseline parameters: the amount
    below which a hold that long is net-negative in expectation (the cost model's
    `timer_amount_eur` with `timer_days` set to that day) and the share of
    synthetic claims under it. Exactly one row — the default timer day — is
    marked. The recommendation is made once, so there is no scenario column."""
    default_day = cost_model.rounded("count", params["timer_days"])
    claims = synthetic_claims(params)
    rows: list[dict[str, object]] = []
    for day in TIMER_DAY_GRID:
        amount = cost_model.evaluate({**params, "timer_days": day}, "baseline")[
            "timer_amount_eur"
        ]
        rows.append(
            {
                "timer_days": day,
                "timer_amount_eur": amount,
                "share_under": cost_model.rounded("rate", share_under(claims, amount)),
                "is_default": day == default_day,
            }
        )
    return rows


def summarize(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, float]]:
    """Per simulator scenario, the mean hold in days and the share of claims the
    timer released — the one aggregation site, computed with plain arithmetic
    over the simulator rows, rounded at the cost model's one site. What the study
    quotes and a Phase 9 SQL aggregate over the mart must reproduce."""
    out: dict[str, dict[str, float]] = {}
    for sim in SIM_SCENARIOS:
        scenario_rows = [r for r in rows if r["scenario"] == sim.name]
        holds = [float(r["hold_days"]) for r in scenario_rows]
        released = sum(1 for r in scenario_rows if r["outcome"] == "timer_released")
        out[sim.name] = {
            "mean_hold_days": cost_model.rounded("days", fmean(holds)),
            "timer_released_share": cost_model.rounded(
                "rate", released / len(scenario_rows)
            ),
        }
    return out


def format_simulation(fit: cost_model.Fit) -> str:
    """The one-screen summary `make simulate` prints: the three rules each beside
    the value it gives at the defaults (the first synthetic claim and the default
    timer), the threshold table (one line per timer day, the default marked), and
    the hold-day summary per scenario. No clock, no key — the same fit always
    prints the same text."""
    params = cost_model.defaults(fit)
    claims = synthetic_claims(params)
    first = claims[0]
    baseline_days = _loop_and_timer_days(params, "baseline")
    timer_amount = cost_model.evaluate(params, "baseline")["timer_amount_eur"]
    first_hold = hold(first, baseline_days, True, timer_amount)
    lines = [
        "guardrail simulator — the rules, the threshold, and the holds each fix gives",
        "",
        "rules (each beside its value at the defaults, on the first synthetic claim):",
        f"  synthetic_amount = {RULES[0].text}",
        f"  {'':18} -> rank {first.rank}: {first.amount_eur}",
        f"  hold             = {RULES[1].text}",
        f"  {'':18} -> {first_hold}",
        f"  share_under      = {RULES[2].text}",
        f"  {'':18} -> at the default threshold {timer_amount}: "
        f"{cost_model.rounded('rate', share_under(claims, timer_amount))}",
        "",
        "SLA threshold — the amount below which a hold that long is net-negative "
        "in expectation, and the share of claims under it (baseline; * = default):",
    ]
    for row in threshold_table(params):
        mark = " *" if row["is_default"] else "  "
        lines.append(
            f" {mark} {row['timer_days']:>3} days  <= "
            f"{row['timer_amount_eur']:>10} €  {row['share_under']}"
        )
    lines.append("")
    lines.append("hold days per fix (mean hold, share the timer released):")
    summary = simulate_all(params)
    for sim in SIM_SCENARIOS:
        s = summary[sim.name]
        lines.append(
            f"  {sim.name:12} ({sim.curves_scenario}): mean {s['mean_hold_days']} "
            f"days, timer released {s['timer_released_share']}"
        )
    return "\n".join(lines)


def simulate_all(params: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """The summary over every scenario — `simulate` for each, then `summarize`
    over the concatenation. The one call the printer and the study both make."""
    rows: list[dict[str, object]] = []
    for sim in SIM_SCENARIOS:
        rows.extend(simulate(params, sim.name))
    return summarize(rows)
