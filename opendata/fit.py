"""Fit a lognormal to the DAMIR reimbursed-amount slice — the whole fit is two
numbers you can redo in a spreadsheet, no optimizer, no fitted predictive model
(PROJECT_BRIEF.md §2.1, §7).

A lognormal says: the *logs* of the amounts are normal. So the fit is the mean
and spread of the logs — `mu = mean(ln x)`, `sigma = population-std(ln x)` —
and that pair is exactly the maximum-likelihood lognormal fit, arrived at by
plain arithmetic rather than a solver. Health costs are lognormal because a few
large claims sit far above many small ones.

The amounts are DAMIR's aggregated per-cell reimbursement totals, not single
claims, so the curve approximates the claim-cost distribution rather than
measuring it claim by claim — the honest label for the anchor Phase 8 draws from.

"The fit shown" (brief §7): a goodness-of-fit table puts each decile of the
real amounts next to what the fitted curve predicts for that decile,
`exp(mu + sigma·z_p)`, with the standard-normal quantile `z_p` printed beside
it. Close columns mean the lognormal describes the data; anyone can read the
two down the page. No clock, no randomness: the same slice always gives the
same numbers.

The fit and the goodness-of-fit land in one tracked, numbers-only CSV
(`data/damir/claim_cost_fit.csv`) that Phase 8's cost model and simulator read,
with the sample's own arithmetic mean (`emp_mean`, Phase 9h) as the last row:
the contrast the study prints beside the lognormal's mean, a number a reader
recomputes from the fixture with no fit involved. A test recomputes the file
from the frozen fixture and pins every value, so CI reproduces the sourced fit
offline."""

from __future__ import annotations

import csv
import math
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
    """The lognormal fit: the two parameters, the sample size behind them, and
    the sample's arithmetic mean (`emp_mean`, `mean(x)` — no fit involved, the
    contrast to the lognormal's own mean `exp(mu + sigma²/2)`)."""

    mu: float
    sigma: float
    n: int
    emp_mean: float


# Every name the artifact carries, in write order: the three fit parameters,
# then `emp_p<d>`/`fit_p<d>` for each decile, then the sample mean last (Phase
# 9h, appended so the pre-9h file is a byte prefix of the new one). The writer
# emits exactly these, the reader requires exactly these, and the tracked-files
# test reads this tuple — one closed set, no hand-typed copy.
FIT_FIELD_NAMES: tuple[str, ...] = (
    "mu",
    "sigma",
    "n",
    *(name for d in DECILES for name in (f"emp_p{d}", f"fit_p{d}")),
    "emp_mean",
)


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
    return Fit(mu=mu, sigma=sigma, n=len(amounts), emp_mean=statistics.fmean(amounts))


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
        # The mean is a divisor downstream (claims at the mean cell), so it is
        # written at the parameters' precision: a reader's hand division from
        # six places lands on one count, from two it could straddle two.
        writer.writerow(["emp_mean", f"{fit.emp_mean:.{_PARAM_DP}f}"])


# The fit artifact is tiny (three parameters + two figures per decile + the
# mean); a file larger than this is not the shape we wrote, so refuse before
# reading it.
_MAX_FIT_BYTES = 64 * 1024
# The smallest amount a euro slice can carry, and the smallest value the cost
# model's euro rounding keeps: a mean under one cent is not a mean of euro
# amounts, and divided by after rounding it would be zero (invariant 7 —
# never a traceback downstream; review round 1, security-reviewer #1).
_MIN_EUR_MEAN = 0.01


# A refusal names what it refused, but a foreign token (a cell or a name the
# file carried) is shown at most this long: the file is capped at 64 KiB, and
# one corrupted cell must not put that much free text on one refusal line
# (review round 1, security-reviewer #3).
_SHOWN_CHARS = 40


def _shown(token: str) -> str:
    """The repr of a foreign token, cut to `_SHOWN_CHARS` with an ellipsis."""
    if len(token) <= _SHOWN_CHARS:
        return repr(token)
    return repr(token[:_SHOWN_CHARS]) + f"… ({len(token)} chars)"


def _finite_float(raw: dict[str, str], name: str, where: str) -> float:
    value = raw[name]
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{where}: {name!r} is not a number: {_shown(value)}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{where}: {name!r} is not a finite number: {_shown(value)}")
    return number


def _positive_int(raw: dict[str, str], name: str, where: str) -> int:
    value = raw[name]
    if not (value.isascii() and value.isdigit()) or int(value) <= 0:
        raise ValueError(
            f"{where}: {name!r} is not a positive integer: {_shown(value)}"
        )
    return int(value)


def read_fit(path: Path = ARTIFACT) -> tuple[Fit, list[Decile]]:
    """Read the tracked fit artifact back into the Fit and its goodness-of-fit
    deciles — the strict mirror of `write_fit`, the one place besides the writer
    that knows the artifact's shape. Every declared name must be present, numeric
    and finite (`n` a positive integer); an unknown, missing, duplicate or
    non-numeric name refuses with the name, never a silent default; `emp_mean`
    is a divisor downstream, rounded to cents first, so a value under one cent
    refuses too. `z` is the
    standard-normal quantile recomputed per decile (the writer stores none), the
    same value `goodness_of_fit` used, so the returned deciles carry it."""
    where = path.name
    size = path.stat().st_size
    if size > _MAX_FIT_BYTES:
        raise ValueError(
            f"{where}: fit artifact is {size} bytes, over the {_MAX_FIT_BYTES} cap"
        )
    raw: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        if next(reader, None) != ["name", "value"]:
            raise ValueError(f"{where}: header must be exactly 'name,value'")
        for lineno, row in enumerate(reader, 2):
            if len(row) != 2:
                raise ValueError(
                    f"{where}: line {lineno}: wrong number of cells ({len(row)})"
                )
            name = row[0]
            if name in raw:
                raise ValueError(
                    f"{where}: line {lineno}: duplicate name {_shown(name)}"
                )
            raw[name] = row[1]
    expected = set(FIT_FIELD_NAMES)
    if unknown := sorted(set(raw) - expected):
        shown = ", ".join(_shown(n) for n in unknown)
        raise ValueError(f"{where}: name(s) not in the fit artifact's shape: {shown}")
    if missing := sorted(expected - set(raw)):
        raise ValueError(
            f"{where}: name(s) the fit artifact must carry are missing: {missing}"
        )
    sigma = _finite_float(raw, "sigma", where)
    if sigma < 0:
        raise ValueError(
            f"{where}: 'sigma' is a standard deviation and must be >= 0: {sigma!r}"
        )
    emp_mean = _finite_float(raw, "emp_mean", where)
    if emp_mean < _MIN_EUR_MEAN:
        raise ValueError(
            f"{where}: 'emp_mean' is a mean of euro amounts and a divisor, "
            f"must be at least one cent ({_MIN_EUR_MEAN}): {emp_mean!r}"
        )
    fit = Fit(
        mu=_finite_float(raw, "mu", where),
        sigma=sigma,
        n=_positive_int(raw, "n", where),
        emp_mean=emp_mean,
    )
    normal = statistics.NormalDist()
    gof = [
        Decile(
            decile=decile,
            z=normal.inv_cdf(decile / 100),
            empirical=_finite_float(raw, f"emp_p{decile}", where),
            predicted=_finite_float(raw, f"fit_p{decile}", where),
        )
        for decile in DECILES
    ]
    return fit, gof


def format_fit(fit: Fit, gof: list[Decile]) -> str:
    """The one-screen summary `make fit-damir` prints: the two parameters, the
    sample size, and the decile-by-decile fit-vs-real table."""
    lines = [
        f"lognormal fit over {fit.n} DAMIR reimbursed amounts (PRS_REM_MNT):",
        f"  mu    = {fit.mu:.{_PARAM_DP}f}   (mean of ln amount)",
        f"  sigma = {fit.sigma:.{_PARAM_DP}f}   (population std of ln amount)",
        f"  mean  = {fit.emp_mean:.{_PARAM_DP}f}   (arithmetic mean of the amounts, "
        "no fit — the contrast to exp(mu + sigma²/2))",
        "the fit shown — each decile, real amount vs the fitted curve:",
        f"  {'decile':>6}  {'z':>8}  {'real €':>12}  {'fitted €':>12}",
    ]
    for row in gof:
        lines.append(
            f"  {row.decile:>5}%  {row.z:>8.4f}  "
            f"{row.empirical:>12.2f}  {row.predicted:>12.2f}"
        )
    return "\n".join(lines)
