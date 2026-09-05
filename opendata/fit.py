"""Fit a lognormal to the DAMIR reimbursed-amount slice — the whole fit is two
numbers you can redo in a spreadsheet, no optimizer, no fitted predictive model
(PROJECT_BRIEF.md §2.1, §7).

A lognormal says: the *logs* of the amounts are normal. So the fit is the mean
and spread of the logs — `mu = mean(ln x)`, `sigma = population-std(ln x)` —
and that pair is exactly the maximum-likelihood lognormal fit, arrived at by
plain arithmetic rather than a solver. Health costs are lognormal because a few
large claims sit far above many small ones.

"The fit shown" (brief §7): a goodness-of-fit table puts each decile of the
real amounts next to what the fitted curve predicts for that decile,
`exp(mu + sigma·z_p)`, with the standard-normal quantile `z_p` printed beside
it. Close columns mean the lognormal describes the data; anyone can read the
two down the page. No clock, no randomness: the same slice always gives the
same numbers.

The fit and the goodness-of-fit land in one tracked, numbers-only CSV
(`data/damir/claim_cost_fit.csv`) that Phase 8's cost model and simulator read.
A test recomputes it from the frozen fixture and pins every value, so CI
reproduces the sourced fit offline."""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from math import exp, log
from pathlib import Path

# The tracked fit artifact — under data/, kept out of the gitignore's data/*
# by an explicit `!data/damir/` negation (the data/snapshots/ precedent).
_DATA = Path(__file__).resolve().parent.parent / "data" / "damir"
ARTIFACT = _DATA / "claim_cost_fit.csv"

# The deciles the goodness-of-fit compares at: the nine inner cut points that
# split the data into ten equal parts.
DECILES = (10, 20, 30, 40, 50, 60, 70, 80, 90)

# How many decimals each written number carries — fixed so the file is
# byte-identical on every rerun (mu/sigma to 6 places, amounts to 2, n whole).
_PARAM_DP = 6
_AMOUNT_DP = 2


@dataclass(frozen=True)
class Fit:
    """The lognormal fit: the two parameters and the sample size behind them."""

    mu: float
    sigma: float
    n: int


@dataclass(frozen=True)
class Decile:
    """One goodness-of-fit row: the real amount at this decile vs the fitted
    curve's prediction, with the standard-normal quantile that produced it."""

    decile: int
    z: float
    empirical: float
    predicted: float


def fit_lognormal(amounts: list[float]) -> Fit:
    """`mu = mean(ln x)`, `sigma = population-std(ln x)` over positive amounts —
    the closed-form (and maximum-likelihood) lognormal fit. Refuses an empty
    slice (nothing to fit) and, for `sigma`, a single value (no spread to
    measure): a fit needs at least two amounts."""
    if len(amounts) < 2:
        raise ValueError(
            f"a lognormal fit needs at least two amounts, got {len(amounts)}"
        )
    logs = [log(x) for x in amounts]
    mu = statistics.fmean(logs)
    sigma = statistics.pstdev(logs, mu)
    return Fit(mu=mu, sigma=sigma, n=len(amounts))


def goodness_of_fit(amounts: list[float], fit: Fit) -> list[Decile]:
    """For each decile, the empirical amount boundary vs the fitted prediction
    `exp(mu + sigma·z_p)`. `z_p` is the standard-normal quantile (stdlib
    `NormalDist().inv_cdf`), printed so the prediction is transparent."""
    cuts = statistics.quantiles(amounts, n=10, method="inclusive")
    normal = statistics.NormalDist()
    rows: list[Decile] = []
    for decile, empirical in zip(DECILES, cuts, strict=True):
        z = normal.inv_cdf(decile / 100)
        predicted = exp(fit.mu + fit.sigma * z)
        rows.append(
            Decile(decile=decile, z=z, empirical=empirical, predicted=predicted)
        )
    return rows


def write_fit(fit: Fit, gof: list[Decile], path: Path = ARTIFACT) -> None:
    """Write the fit and its goodness-of-fit as one tidy `name,value` CSV — the
    numbers Phase 8 reads. Numbers only: no address, no attribution, no brand.
    Fixed decimals make the file byte-identical on every rerun."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "value"])
        writer.writerow(["mu", f"{fit.mu:.{_PARAM_DP}f}"])
        writer.writerow(["sigma", f"{fit.sigma:.{_PARAM_DP}f}"])
        writer.writerow(["n", str(fit.n)])
        for row in gof:
            writer.writerow([f"emp_p{row.decile}", f"{row.empirical:.{_AMOUNT_DP}f}"])
            writer.writerow([f"fit_p{row.decile}", f"{row.predicted:.{_AMOUNT_DP}f}"])


def format_fit(fit: Fit, gof: list[Decile]) -> str:
    """The one-screen summary `make fit-damir` prints: the two parameters, the
    sample size, and the decile-by-decile fit-vs-real table."""
    lines = [
        f"lognormal fit over {fit.n} DAMIR reimbursed amounts (PRS_REM_MNT):",
        f"  mu    = {fit.mu:.{_PARAM_DP}f}   (mean of ln amount)",
        f"  sigma = {fit.sigma:.{_PARAM_DP}f}   (population std of ln amount)",
        "the fit shown — each decile, real amount vs the fitted curve:",
        f"  {'decile':>6}  {'z':>8}  {'real €':>12}  {'fitted €':>12}",
    ]
    for row in gof:
        lines.append(
            f"  {row.decile:>5}%  {row.z:>8.4f}  "
            f"{row.empirical:>12.2f}  {row.predicted:>12.2f}"
        )
    return "\n".join(lines)
