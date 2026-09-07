"""The deterministic cost model (PROJECT_BRIEF.md §7, Beat 3): what a wrongly
held claim costs, as plain arithmetic a reader can redo by hand.

Formulas are data. `FORMULAS` is an ordered tuple where each entry carries a
name, the formula written out as text, whether it is a single number (`point`)
or a point read off the whole flag-rate curve (`curve`), and the function that
computes it. The study prints the text; a test evaluates the function at the
defaults and pins the result; the mart stores both side by side. The printed
formula and the computed number therefore cannot drift apart — they are one
entry, 1:1 by construction (docs/PLAN.md §4 decision 5).

`PARAMETERS` carries the static assumptions; the three DAMIR-fit rows (`mu`,
`sigma`, `emp_p50`) are handed in by the caller as a `Fit` and added by
`parameters(fit)`, so this layer reads no file, no clock and no key — it
computes over what it is given. Every parameter carries a range the study's
sliders span: a sourced figure the record gives as a floor spans the floor to
twice it (the study's stated exploration bound, not a fact); `mu`/`sigma` span
the fit plus and minus two standard errors; an unsourced guess spans the range
worth exploring. Nothing is a fitted predictive model — the only fit is the
lognormal the caller supplies, whose own goodness-of-fit is shown upstream.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, sqrt

# Rounding to fixed places at one site (pinned decision): euros to 2, rates and
# log-euros to 6, counts whole — so mart rows and printed text are byte-identical
# across runs and machines. `rounded(unit, value)` is the ONLY rounding site;
# the writer, the printer and the tests all call it.
_ROUNDING = {"eur": 2, "count": 0, "rate": 6, "logeur": 6, "days": 2}


def rounded(unit: str, value: float | None) -> float | int | None:
    """Round `value` to the fixed places its unit carries (the one rounding
    site). `None` (a crossover that never happens) stays `None`; a unit outside
    the closed set refuses, never rounds by a silent default."""
    if value is None:
        return None
    places = _ROUNDING.get(unit)
    if places is None:
        raise ValueError(f"unknown rounding unit {unit!r}; expected {tuple(_ROUNDING)}")
    return round(value) if places == 0 else round(value, places)


@dataclass(frozen=True)
class Fit:
    """What the cost model needs from the DAMIR lognormal fit: the two
    log-moments, the sample size behind them (for the standard-error ranges on
    `mu`/`sigma`), and the median DAMIR cell (`emp_p50`, the contrast to the
    mean). The caller reads these from `data/damir/claim_cost_fit.csv` via
    `opendata.fit.read_fit` and hands them in, so this module imports no reader
    and touches no file."""

    mu: float
    sigma: float
    n: int
    emp_p50: float


@dataclass(frozen=True)
class Parameter:
    """One assumption on a slider: its default, the unit it is quoted in, whether
    it is `sourced` (with a citation) or `unsourced` (a declared guess, no
    citation), and the `low`/`high` the study's slider spans."""

    name: str
    default: float
    unit: str
    sourcing: str
    citation: str
    low: float
    high: float


# A point formula reads a mapping of the parameters and the results before it;
# a curve formula reads the whole flag-rate grid's rows and returns a flag rate
# (or None when its crossover never happens).
PointFn = Callable[[Mapping[str, float]], float]
CurveFn = Callable[[Sequence[Mapping[str, float]]], float | None]


@dataclass(frozen=True)
class Formula:
    """One entry of the model: its name, the expression written out as text
    (what the study prints), its `kind` (`point` — one number per parameter set,
    or `curve` — a point read off the whole flag-rate grid), and the callable
    that computes it."""

    name: str
    expression: str
    kind: str
    fn: PointFn | CurveFn


SOURCING = ("sourced", "unsourced")
KIND = ("point", "curve")

# The second-hand citation the four scale anchors share: the brief records them
# as public disclosures with no address, each a floor, and the study says so
# beside them (DECISIONS → Phase 3a D1; an address, when handed over, becomes a
# brand-free declaration in ingest/sources.py — a BACKLOG row).
_DISCLOSURE_FLOOR_CITE = "PROJECT_BRIEF.md §6 (public disclosure, second-hand; a floor)"
# The fit artifact the caller reads and hands in as a Fit.
_FIT_CITE = "data/damir/claim_cost_fit.csv ← open-damir"

# The scale anchors (sourced; the record gives each as a floor, so the range is
# the floor to twice it — the study's exploration bound, printed as such).
SCALE_PARAMETERS = (
    Parameter(
        "arr_eur",
        800_000_000.0,
        "€ / year",
        "sourced",
        _DISCLOSURE_FLOOR_CITE,
        800_000_000.0,
        1_600_000_000.0,
    ),
    Parameter(
        "members",
        1_000_000.0,
        "members",
        "sourced",
        _DISCLOSURE_FLOOR_CITE,
        1_000_000.0,
        2_000_000.0,
    ),
    Parameter(
        "fraud_pool_eur",
        4_000_000.0,
        "€ / year",
        "sourced",
        _DISCLOSURE_FLOOR_CITE,
        4_000_000.0,
        8_000_000.0,
    ),
    Parameter(
        "refunded_eur",
        350_000_000.0,
        "€ / year",
        "sourced",
        _DISCLOSURE_FLOOR_CITE,
        350_000_000.0,
        700_000_000.0,
    ),
)
# The declared-unsourced guards, each a guess with an explore-the-range span,
# never a fact. `cost_per_contact` flips to sourced if a public benchmark is
# handed over before build (a one-cell change; brief §7 allows either).
KNOB_PARAMETERS = (
    Parameter("flag_rate", 0.05, "share of claims", "unsourced", "", 0.00, 0.20),
    Parameter("fp_share", 0.50, "share of flagged", "unsourced", "", 0.10, 0.90),
    Parameter("contacts", 3.0, "contacts per stuck claim", "unsourced", "", 1.0, 8.0),
    Parameter("cost_per_contact", 8.0, "€", "unsourced", "", 2.0, 30.0),
    Parameter("churn_prob", 0.05, "probability", "unsourced", "", 0.00, 0.30),
    Parameter("k", 8.0, "diminishing-returns constant", "unsourced", "", 2.0, 20.0),
    # The two hold-timer knobs (Phase 8b): one document round trip, and the days
    # a hold may run before the clock fires. `timer_days` spans the day grid
    # sla_threshold walks (1..60), so its default (14) lies on it.
    Parameter(
        "days_per_round",
        7.0,
        "days per document round trip",
        "unsourced",
        "",
        1.0,
        21.0,
    ),
    Parameter(
        "timer_days",
        14.0,
        "days a hold may run before the clock",
        "unsourced",
        "",
        1.0,
        60.0,
    ),
)
# The static table (fit rows are inserted by parameters()).
PARAMETERS = SCALE_PARAMETERS + KNOB_PARAMETERS


def fit_parameters(fit: Fit) -> tuple[Parameter, ...]:
    """The three sourced rows the DAMIR fit supplies, with their computed ranges.
    `mu`/`sigma` span the fit ± 2 standard errors (`se_mu = sigma / √n`,
    `se_sigma = sigma / √(2n)`, the closed-form lognormal-MLE standard errors);
    `emp_p50` is a read figure whose slider is `mu`/`sigma`, so its range is
    itself. Every cell is rounded at the one site, so the rows are byte-stable."""
    se_mu = fit.sigma / sqrt(fit.n)
    se_sigma = fit.sigma / sqrt(2 * fit.n)
    return (
        Parameter(
            "mu",
            rounded("logeur", fit.mu),
            "log-euros",
            "sourced",
            _FIT_CITE,
            rounded("logeur", fit.mu - 2 * se_mu),
            rounded("logeur", fit.mu + 2 * se_mu),
        ),
        Parameter(
            "sigma",
            rounded("logeur", fit.sigma),
            "log-euros",
            "sourced",
            _FIT_CITE,
            rounded("logeur", fit.sigma - 2 * se_sigma),
            rounded("logeur", fit.sigma + 2 * se_sigma),
        ),
        Parameter(
            "emp_p50",
            rounded("eur", fit.emp_p50),
            "€",
            "sourced",
            _FIT_CITE,
            rounded("eur", fit.emp_p50),
            rounded("eur", fit.emp_p50),
        ),
    )


def check_parameter(p: Parameter) -> None:
    """A parameter is well-formed, or this refuses: `sourcing` is one of the two
    words (nothing in between); a sourced one carries a citation and an unsourced
    one does not; and `low <= default <= high`. The closed-set guard the mart
    and the study's sliders rely on — a malformed table fails fast, never reaches
    a chart."""
    if p.sourcing not in SOURCING:
        raise ValueError(
            f"parameter {p.name!r}: sourcing {p.sourcing!r} not in {SOURCING}"
        )
    if p.sourcing == "sourced" and not p.citation:
        raise ValueError(f"parameter {p.name!r}: sourced but carries no citation")
    if p.sourcing == "unsourced" and p.citation:
        raise ValueError(f"parameter {p.name!r}: unsourced but carries a citation")
    if not p.low <= p.default <= p.high:
        raise ValueError(
            f"parameter {p.name!r}: default {p.default} "
            f"outside range [{p.low}, {p.high}]"
        )


def parameters(fit: Fit) -> tuple[Parameter, ...]:
    """The full ordered parameter set: the four scale anchors, the three
    fit-derived rows, then the unsourced knobs — one row per slider the study
    shows, the fit never a second literal here. Every row is checked well-formed."""
    params = SCALE_PARAMETERS + fit_parameters(fit) + KNOB_PARAMETERS
    for p in params:
        check_parameter(p)
    return params


def defaults(fit: Fit) -> dict[str, float]:
    """`{name: default}` over every parameter — the value set `evaluate` and
    `curves` run at, before any slider moves."""
    return {p.name: p.default for p in parameters(fit)}


# The point formulas, in order (brief §7 plus the three derived defaults and the
# median contrast). Each fn reads one mapping of the parameters and the results
# computed before it, so a later formula names an earlier one by key.
def _customer_value(v: Mapping[str, float]) -> float:
    return v["arr_eur"] / v["members"]


def _mean_claim(v: Mapping[str, float]) -> float:
    return exp(v["mu"] + v["sigma"] ** 2 / 2)


def _median_cell(v: Mapping[str, float]) -> float:
    return v["emp_p50"]


def _claims(v: Mapping[str, float]) -> float:
    return v["refunded_eur"] / v["mean_claim"]


def _flagged(v: Mapping[str, float]) -> float:
    return v["claims"] * v["flag_rate"]


def _false_pos(v: Mapping[str, float]) -> float:
    return v["flagged"] * v["fp_share"]


def _fraud_saved(v: Mapping[str, float]) -> float:
    return v["fraud_pool_eur"] * (1 - exp(-v["k"] * v["flag_rate"]))


def _friction_cost(v: Mapping[str, float]) -> float:
    return v["false_pos"] * (
        v["contacts"] * v["cost_per_contact"] + v["churn_prob"] * v["customer_value"]
    )


def _net(v: Mapping[str, float]) -> float:
    return v["fraud_saved"] - v["friction_cost"]


# The hold-timer threshold (Phase 8b, brief §7): Beat 3 arithmetic, so it lives
# in FORMULAS beside the model it is computed from, never in the simulator. The
# loop is the contacts spread over document round trips; friction accrues evenly
# over the loop and stops when it ends; the threshold is the claim amount below
# which a hold planned to run `timer_days` is net-negative in expectation, with
# the claim itself the ceiling on what a hold can recover (so it errs toward
# holding). Used by Beat 4 at the `baseline` evaluation, whatever the scenario.
def _loop_days(v: Mapping[str, float]) -> float:
    return v["contacts"] * v["days_per_round"]


def _friction_per_day(v: Mapping[str, float]) -> float:
    return (
        v["contacts"] * v["cost_per_contact"] + v["churn_prob"] * v["customer_value"]
    ) / v["loop_days"]


def _timer_amount_eur(v: Mapping[str, float]) -> float:
    held = min(v["timer_days"], v["loop_days"])
    return v["fp_share"] * v["friction_per_day"] * held / (1 - v["fp_share"])


POINT_FORMULAS = (
    Formula("customer_value", "arr_eur / members", "point", _customer_value),
    Formula(
        "mean_claim",
        "exp(mu + sigma^2 / 2)  -- a DAMIR cell sums >= 1 claims, so this "
        "overstates a claim's cost and understates claims and friction_cost",
        "point",
        _mean_claim,
    ),
    Formula(
        "median_cell",
        "emp_p50  -- the middle DAMIR cell, the contrast to the mean",
        "point",
        _median_cell,
    ),
    Formula("claims", "refunded_eur / mean_claim", "point", _claims),
    Formula("flagged", "claims * flag_rate", "point", _flagged),
    Formula("false_pos", "flagged * fp_share", "point", _false_pos),
    Formula(
        "fraud_saved",
        "fraud_pool_eur * (1 - exp(-k * flag_rate))",
        "point",
        _fraud_saved,
    ),
    Formula(
        "friction_cost",
        "false_pos * (contacts * cost_per_contact + churn_prob * customer_value)",
        "point",
        _friction_cost,
    ),
    Formula("net", "fraud_saved - friction_cost", "point", _net),
    Formula("loop_days", "contacts * days_per_round", "point", _loop_days),
    Formula(
        "friction_per_day",
        "(contacts * cost_per_contact + churn_prob * customer_value) / loop_days"
        "  -- friction assumed to accrue evenly over the loop and stop when it ends",
        "point",
        _friction_per_day,
    ),
    Formula(
        "timer_amount_eur",
        "fp_share * friction_per_day * min(timer_days, loop_days) / (1 - fp_share)"
        "  -- a hold planned to run timer_days on a claim under this is "
        "net-negative in expectation; the claim is the recovery ceiling, so this "
        "errs toward holding",
        "point",
        _timer_amount_eur,
    ),
)
# The rounding unit each point output carries.
_OUTPUT_UNIT = {
    "customer_value": "eur",
    "mean_claim": "eur",
    "median_cell": "eur",
    "claims": "count",
    "flagged": "count",
    "false_pos": "count",
    "fraud_saved": "eur",
    "friction_cost": "eur",
    "net": "eur",
    "loop_days": "count",
    "friction_per_day": "eur",
    "timer_amount_eur": "eur",
}


# The two curve formulas: each reads the grid's rows and returns a flag rate (or
# None when it never happens). Net is zero at the origin and concave in the flag
# rate, so each rule fires at most once and "first" is well defined.
def _crossover(rows: Sequence[Mapping[str, float]]) -> float | None:
    return next((r["flag_rate"] for r in rows if r["net"] < 0), None)


def _marginal_crossover(rows: Sequence[Mapping[str, float]]) -> float | None:
    return next(
        (
            rows[i]["flag_rate"]
            for i in range(1, len(rows))
            if rows[i]["net"] < rows[i - 1]["net"]
        ),
        None,
    )


CURVE_FORMULAS = (
    Formula(
        "crossover_flag_rate",
        "first grid flag_rate with net < 0 (the curves cross; the flags as a "
        "whole cost more than they recover); null if none",
        "curve",
        _crossover,
    ),
    Formula(
        "marginal_crossover_flag_rate",
        "first grid flag_rate whose net is below the previous point's (each "
        "extra flag costs more than it recovers); null if none",
        "curve",
        _marginal_crossover,
    ),
)
FORMULAS = POINT_FORMULAS + CURVE_FORMULAS


# The flag-rate grid: 0.000 to 0.200 in steps of 0.005 (41 points), rounded so
# the default (0.05) lies exactly on it and the grid is byte-stable.
_GRID_STEP = 0.005
_GRID_POINTS = 41
FLAG_RATE_GRID = tuple(rounded("rate", i * _GRID_STEP) for i in range(_GRID_POINTS))


# The §7 guardrail toggles, named by their effect (so 8b's simulated hold timer
# needs no second name in the same mart column). Each scenario is a tuple of
# override-builders composed in order — `both` reuses the two singles, so the
# halving rule is written once.
def _contacts_once(_p: Mapping[str, float]) -> dict[str, float]:
    return {"contacts": 1.0}


def _churn_halved(p: Mapping[str, float]) -> dict[str, float]:
    return {"churn_prob": p["churn_prob"] / 2}


SCENARIOS: dict[str, tuple[Callable[[Mapping[str, float]], dict[str, float]], ...]] = {
    "baseline": (),
    "contacts_once": (_contacts_once,),
    "churn_halved": (_churn_halved,),
    "both": (_contacts_once, _churn_halved),
}


def _apply_scenario(params: Mapping[str, float], scenario: str) -> dict[str, float]:
    """The parameter set with the scenario's toggles applied — the overrides
    brief §7 states, labeled illustrative. An unknown scenario refuses, never
    evaluates the defaults silently."""
    toggles = SCENARIOS.get(scenario)
    if toggles is None:
        raise ValueError(f"unknown scenario {scenario!r}; expected {tuple(SCENARIOS)}")
    out = dict(params)
    for toggle in toggles:
        out.update(toggle(out))
    return out


def _run_points(values: Mapping[str, float]) -> dict[str, float | int]:
    """Run the point formulas in order over a parameter set, chaining full
    precision, and return each output rounded at the one site."""
    v = dict(values)
    for f in POINT_FORMULAS:
        v[f.name] = f.fn(v)
    return {f.name: rounded(_OUTPUT_UNIT[f.name], v[f.name]) for f in POINT_FORMULAS}


def evaluate(
    params: Mapping[str, float], scenario: str = "baseline"
) -> dict[str, float | int]:
    """The point outputs for one scenario: the same formulas over the parameter
    set that scenario's toggles produce."""
    return _run_points(_apply_scenario(params, scenario))


def curves(
    params: Mapping[str, float], scenario: str = "baseline"
) -> tuple[list[dict[str, float | int | bool]], dict[str, float | None]]:
    """The grid and the two crossovers for one scenario. Each grid row carries
    the flag rate, fraud saved, friction cost, net (all rounded) and whether it
    is the default flag rate (the "you are here" marker — exactly one row).
    The crossovers read the rounded net column, so the chart's reader finds the
    same points by eye."""
    base = _apply_scenario(params, scenario)
    default_rate = rounded("rate", base["flag_rate"])
    rows: list[dict[str, float | int | bool]] = []
    for rate in FLAG_RATE_GRID:
        out = _run_points({**base, "flag_rate": rate})
        rows.append(
            {
                "flag_rate": rate,
                "fraud_saved": out["fraud_saved"],
                "friction_cost": out["friction_cost"],
                "net": out["net"],
                "is_default": rate == default_rate,
            }
        )
    crossovers = {f.name: f.fn(rows) for f in CURVE_FORMULAS}
    return rows, crossovers


def format_model(fit: Fit) -> str:
    """The one-screen summary `make model` prints: the parameter table (each row
    with its range; a sourced one with its citation), the formula table (each
    expression beside its value at the defaults, per scenario) and the two
    crossovers. No clock, no key — the same fit always prints the same text."""
    params = parameters(fit)
    values = {p.name: p.default for p in params}
    lines = [
        "cost model — the formulas, their defaults, and where the curves cross",
        "",
    ]
    lines.append(
        "parameters (every unsourced default is a guess to explore, never a fact):"
    )
    for p in params:
        cite = p.citation if p.sourcing == "sourced" else "declared unsourced"
        lines.append(
            f"  {p.name:16} {p.default:>16} {p.unit:24} "
            f"[{p.low} .. {p.high}]  {p.sourcing}: {cite}"
        )
    for scenario in SCENARIOS:
        outputs = evaluate(values, scenario)
        _, crossovers = curves(values, scenario)
        lines.append("")
        lines.append(
            f"scenario {scenario} — each formula beside its value at the defaults:"
        )
        for f in POINT_FORMULAS:
            lines.append(f"  {f.name:16} = {f.expression}")
            lines.append(f"  {'':16}   -> {outputs[f.name]}")
        for f in CURVE_FORMULAS:
            lines.append(f"  {f.name:28} = {f.expression}")
            lines.append(f"  {'':28}   -> {crossovers[f.name]}")
    return "\n".join(lines)
