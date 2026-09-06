"""Phase 7b — the Open DAMIR slice and the lognormal claim-cost fit. Offline,
no key, no network: the fit is closed-form arithmetic over a frozen fixture,
the amount column is a guarded read of a foreign CSV, and the fetch target's
gate and month validation refuse before any request. The real-fixture pins
(`test_fit_params_over_fixture`, `test_artifact_equals_recompute`) run once
`fixtures/damir/` exists; until then they skip."""

from __future__ import annotations

import math
import statistics
from pathlib import Path

import pytest

import pipeline.cli as cli
from opendata.fit import (
    fit_lognormal,
    goodness_of_fit,
    read_fit,
    write_fit,
)
from opendata.slice import (
    FIXTURE_CSV,
    freeze_manifest,
    parse_amount,
    read_amounts,
    systematic_sample,
    write_fixture,
)
from opendata.sources import cache_path, month_token, valid_month
from pipeline.cli import main

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "--goals-origin=default"


@pytest.fixture(autouse=True)
def _stamp_in_tmp(tmp_path, monkeypatch):
    """The confirmation stamp lives under the repo's data/; tests write theirs
    in a temp dir (the test_cli pattern)."""
    monkeypatch.setattr(cli, "CONFIRM_STAMP", tmp_path / ".confirm")


def _write_csv(
    path: Path,
    amounts: list[str],
    types: list[str] | None = None,
    header: str = "PRS_REM_MNT;PRS_REM_TYP",
) -> Path:
    """A DAMIR-shaped `;`-CSV: a header row then `amount;type` per line. `types`
    defaults to the legal `0` for every row, so an amounts-only caller writes a
    valid legal slice (every row kept)."""
    if types is None:
        types = ["0"] * len(amounts)
    body = "\n".join(f"{a};{t}" for a, t in zip(amounts, types, strict=True))
    path.write_text(header + "\n" + body + "\n", encoding="utf-8")
    return path


# --- the fit is plain arithmetic anyone can redo -----------------------------


def test_fit_reproducible_by_hand():
    """mu = mean(ln x), sigma = population-std(ln x) — the function equals the
    hand formula, no pinned magic number needed to prove the arithmetic."""
    amounts = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0]
    logs = [math.log(a) for a in amounts]
    mu_hand = sum(logs) / len(logs)
    var_hand = sum((x - mu_hand) ** 2 for x in logs) / len(logs)
    fit = fit_lognormal(amounts)
    assert fit.mu == pytest.approx(mu_hand)
    assert fit.sigma == pytest.approx(var_hand**0.5)
    assert fit.n == 6


def test_fit_is_the_lognormal_mle():
    """Log-moments IS the lognormal maximum-likelihood fit: statistics.fmean /
    pstdev over the logs give the same two numbers, computed the boring way."""
    amounts = [10.0, 12.5, 40.0, 100.0, 250.0, 3.0, 7.5]
    logs = [math.log(a) for a in amounts]
    fit = fit_lognormal(amounts)
    assert fit.mu == pytest.approx(statistics.fmean(logs))
    assert fit.sigma == pytest.approx(statistics.pstdev(logs))


def test_fit_needs_at_least_two_amounts():
    with pytest.raises(ValueError, match="at least two"):
        fit_lognormal([42.0])
    with pytest.raises(ValueError, match="at least two"):
        fit_lognormal([])


def test_fit_is_deterministic():
    """No clock, no RNG: the same amounts always give the same fit."""
    amounts = [3.0, 9.0, 27.0, 81.0, 243.0]
    assert fit_lognormal(amounts) == fit_lognormal(amounts)


# --- the fit shown: goodness-of-fit deciles ----------------------------------


def test_goodness_of_fit_deciles():
    """Each decile pairs the empirical amount boundary with the fitted
    prediction exp(mu + sigma·z_p); both recomputed independently here."""
    amounts = [float(x) for x in range(1, 1001)]
    fit = fit_lognormal(amounts)
    gof = goodness_of_fit(amounts, fit)
    assert [row.decile for row in gof] == [10, 20, 30, 40, 50, 60, 70, 80, 90]
    cuts = statistics.quantiles(amounts, n=10, method="inclusive")
    normal = statistics.NormalDist()
    for row, empirical, decile in zip(gof, cuts, range(10, 100, 10), strict=True):
        z = normal.inv_cdf(decile / 100)
        assert row.z == pytest.approx(z)
        assert row.empirical == pytest.approx(empirical)
        assert row.predicted == pytest.approx(math.exp(fit.mu + fit.sigma * z))


# --- the amount column is a guarded foreign shape ----------------------------


def test_parse_amount_keeps_only_positive_numbers():
    assert parse_amount("12.50") == 12.5
    assert parse_amount("12,50") == 12.5  # French decimal comma
    assert parse_amount("  3 ") == 3.0
    junk = (
        "",
        "  ",
        "abc",
        "0",
        "0.0",
        "-5",
        "-0.01",
        "1,2,3",
        "nan",
        "inf",
        "1_000",
        "1e5",
        "1.5e3",
        "0x10",
        "+3",  # exotic float() forms, refused
    )
    for j in junk:
        assert parse_amount(j) is None, j


def test_amount_domain_guard_drops_and_counts(tmp_path):
    """A slice with a blank amount, text, zero, a negative, a supplementary-part
    type (>= 2) and a blank type keeps only the positive legal-type rows and
    tallies the rest — never silently absorbed. A real (multi-column) DAMIR row
    with an empty PRS_REM_MNT is a row, so it counts as dropped (unlike a wholly
    empty line, which the CSV reader skips)."""
    path = tmp_path / "s.csv"
    path.write_text(
        "PRS_REM_MNT;PRS_REM_TYP\n"
        "10.0;0\n"  # kept: positive, legal type 0
        "20,5;1\n"  # kept: French decimal comma, legal type 1
        ";0\n"  # dropped: blank amount
        "abc;0\n"  # dropped: non-numeric
        "0;0\n"  # dropped: zero
        "-5;1\n"  # dropped: negative
        "30.0;2\n"  # dropped: supplementary part (type 2), positive amount
        "40.0;\n",  # dropped: blank type
        encoding="utf-8",
    )
    amounts = read_amounts(path)
    assert amounts.values == [10.0, 20.5]
    assert amounts.dropped == 6
    assert amounts.read == 8


def test_reads_a_gzip_file_like_a_plain_one(tmp_path):
    """The portal serves DAMIR months gzipped; the slice reads a gzip file the
    same as a plain one, detected by magic bytes not the name (Amendment A2).
    read_amounts and systematic_sample give identical results either way."""
    import gzip

    plain = _write_csv(
        tmp_path / "m.csv",
        ["10", "20", "30", "40"],
        types=["0", "2", "1", "0"],
    )
    body = plain.read_bytes()
    gz = tmp_path / "m.csv.gz"  # a .gz name
    gz.write_bytes(gzip.compress(body))
    misnamed = tmp_path / "looks_plain.csv"  # gzip bytes under a .csv name
    misnamed.write_bytes(gzip.compress(body))

    assert read_amounts(gz).values == read_amounts(plain).values == [10.0, 30.0, 40.0]
    assert read_amounts(misnamed).values == [10.0, 30.0, 40.0]  # read by content
    assert systematic_sample(gz, 10).rows == systematic_sample(plain, 10).rows


def test_read_amounts_refuses_a_file_missing_either_column(tmp_path):
    """A CSV missing either declared column refuses; it does not read as an
    empty slice as if it were valid data."""
    no_amount = tmp_path / "no_amount.csv"
    no_amount.write_text("FOO;PRS_REM_TYP\n1;0\n2;0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="PRS_REM_MNT"):
        read_amounts(no_amount)
    no_type = tmp_path / "no_type.csv"
    no_type.write_text("PRS_REM_MNT;OTHER\n1;x\n2;y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="PRS_REM_TYP"):
        read_amounts(no_type)


# --- systematic sampling spans the file, deterministically -------------------


def test_systematic_sample_takes_every_kth_across_the_file(tmp_path):
    src = _write_csv(tmp_path / "m.csv", [str(x) for x in range(1, 101)])
    sample = systematic_sample(src, 10)
    assert sample.total_valid == 100
    assert sample.stride == 10
    assert sample.values == [1.0, 11.0, 21.0, 31.0, 41.0, 51.0, 61.0, 71.0, 81.0, 91.0]


def test_systematic_sample_returns_all_when_fewer_than_n(tmp_path):
    src = _write_csv(tmp_path / "m.csv", ["5", "x", "6", "-1", "7"])
    sample = systematic_sample(src, 1000)
    assert sample.values == [5.0, 6.0, 7.0]
    assert sample.total_valid == 3 and sample.dropped == 2 and sample.stride == 1


def test_systematic_sample_is_deterministic(tmp_path):
    src = _write_csv(tmp_path / "m.csv", [str(x) for x in range(1, 51)])
    assert systematic_sample(src, 7).values == systematic_sample(src, 7).values


def test_systematic_sample_drops_supplementary_types(tmp_path):
    """A supplementary-part row (PRS_REM_TYP >= 2) is dropped and counted even
    when its amount is positive — only legal types 0/1 reach the draw, and the
    kept rows carry their type so the fixture is the declared two-column shape."""
    src = _write_csv(
        tmp_path / "m.csv",
        ["10", "20", "30", "40"],
        types=["0", "2", "1", "3"],
    )
    sample = systematic_sample(src, 10)
    assert sample.values == [10.0, 30.0]
    assert sample.rows == [(10.0, "0"), (30.0, "1")]
    assert sample.total_valid == 2
    assert sample.dropped == 2


# --- the tracked artifact: written, idempotent, hand-checkable ---------------


def test_write_fit_is_byte_identical_on_rerun(tmp_path):
    amounts = [float(x) for x in range(1, 201)]
    fit = fit_lognormal(amounts)
    gof = goodness_of_fit(amounts, fit)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_fit(fit, gof, a)
    write_fit(fit, gof, b)
    assert a.read_bytes() == b.read_bytes()


def test_artifact_carries_mu_sigma_n_and_deciles(tmp_path):
    amounts = [float(x) for x in range(1, 201)]
    fit = fit_lognormal(amounts)
    gof = goodness_of_fit(amounts, fit)
    out = tmp_path / "fit.csv"
    write_fit(fit, gof, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("name,value\n")
    for name in ("mu,", "sigma,", "n,", "emp_p50,", "fit_p50,"):
        assert name in text


def test_fixture_round_trips_through_the_same_reader(tmp_path):
    """write_fixture writes the exact two-column shape read_amounts reads — one
    path, so the legal-type filter is reproducible from the fixture alone."""
    out = tmp_path / "damir-sample.csv"
    write_fixture([(1.5, "0"), (2.5, "1"), (300.0, "0")], out)
    assert read_amounts(out).values == [1.5, 2.5, 300.0]
    assert out.read_text(encoding="utf-8").startswith("PRS_REM_MNT;PRS_REM_TYP\n")


def test_freeze_manifest_matches_sha256(tmp_path):
    import hashlib

    (tmp_path / "damir-sample.csv").write_text("PRS_REM_MNT\n1.00\n", encoding="utf-8")
    freeze_manifest(tmp_path)
    listed = (tmp_path / "MANIFEST.sha256").read_text(encoding="utf-8").strip()
    digest, name = listed.split("  ", 1)
    assert name == "damir-sample.csv"
    assert digest == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()


# --- the fetch target: confirm-gated, month-validated, developer-run ---------


def test_valid_month_refuses_bad_shapes():
    assert valid_month("2024-01") == (2024, 1)
    for bad in ("", "../x", '"; ', "2024-13", "2024-00", "2024-1", "24-01", "2024/01"):
        with pytest.raises(ValueError, match="month must be"):
            valid_month(bad)


def test_month_token_is_the_A_prefixed_period():
    assert month_token("2024-01") == "A202401"
    assert month_token("2016-07") == "A201607"


def test_cache_path_keeps_the_gzip_extension():
    """The portal serves DAMIR months as A<YYYYMM>.csv.gz; the cache keeps that
    real extension and the slice reads it gzipped (Amendment A2)."""
    assert cache_path("2025-07").name == "A202507.csv.gz"


def test_fetch_damir_month_validation_refuses_before_any_network():
    """A bad MONTH refuses at valid_month, before fetch_month is ever called —
    no network, whatever the arming state (valid_month runs before the gate
    prompt). Empty, ../x, "; and an out-of-range month all exit 2."""
    for bad in ("", "../x", '"; ', "2024-13", "2024-1"):
        code = main(["fetch-damir", f"--month={bad}", "--make-pid=1"])
        assert code == 2, bad


def test_fetch_damir_refuses_without_the_confirm_goal(capsys, monkeypatch):
    """Unconfirmed and non-interactive: refuse with one line, fetch nothing —
    an agent's call cannot reach the network (the scrape pattern)."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    code = main(["fetch-damir", "--month=2024-01", "--make-pid=1"])
    assert code == 2
    out = capsys.readouterr().out
    assert "run `make confirm fetch-damir`" in out and "nothing fetched" in out


def test_confirm_arms_fetch_damir_and_the_armed_path_proceeds(capsys, monkeypatch):
    """confirm arms fetch-damir (GATED includes it), and the armed path reaches
    the download — stubbed here so the test stays offline."""
    calls: list[str] = []

    def _stub(month: str):
        calls.append(month)
        return cache_path(month), 123

    monkeypatch.setattr(cli, "fetch_month", _stub)
    assert main(["confirm", "--make-pid=1", ORIGIN, "--goals=confirm fetch-damir"]) == 0
    assert cli.CONFIRM_STAMP.exists()
    assert main(["fetch-damir", "--month=2024-01", "--make-pid=1"]) == 0
    assert calls == ["2024-01"]
    assert "fetch-damir: 123 bytes" in capsys.readouterr().out


# --- fit-damir target glue ---------------------------------------------------


def test_sample_damir_no_cached_month_is_a_message(capsys, monkeypatch, tmp_path):
    """sample-damir with no cached month: exit 1 with a clear message, and it
    never writes the fixture (the guard branch, previously untested)."""
    monkeypatch.setattr(cli, "cache_path", lambda m: tmp_path / "A202507.csv.gz")
    assert main(["sample-damir", "--month=2025-07"]) == 1
    assert "no cached month" in capsys.readouterr().out


def test_sample_damir_no_positive_legal_amount_is_a_message(
    capsys, monkeypatch, tmp_path
):
    """A cached month whose only rows are supplementary parts (type >= 2): nothing
    legal to draw, so exit 1 and the fixture is not overwritten (guard branch)."""
    src = _write_csv(tmp_path / "cached.csv", ["10", "20"], types=["2", "3"])
    monkeypatch.setattr(cli, "cache_path", lambda m: src)
    assert main(["sample-damir", "--month=2025-07"]) == 1
    assert "no positive legal-type" in capsys.readouterr().out


def test_fit_damir_missing_fixture_is_a_message(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "FIXTURE_CSV", tmp_path / "nope.csv")
    assert main(["fit-damir"]) == 1
    assert "no fixture" in capsys.readouterr().out


def test_fit_damir_writes_and_prints(capsys, monkeypatch, tmp_path):
    rows = [f"{x}.0" for x in range(1, 51)]
    fixture = _write_csv(tmp_path / "damir-sample.csv", rows)
    artifact = tmp_path / "claim_cost_fit.csv"
    monkeypatch.setattr(cli, "FIXTURE_CSV", fixture)
    monkeypatch.setattr(cli, "ARTIFACT", artifact)
    assert main(["fit-damir"]) == 0
    assert artifact.is_file()
    out = capsys.readouterr().out
    assert "lognormal fit" in out and "mu" in out and "the fit shown" in out


# --- the strict fit reader: the mirror of write_fit --------------------------


def _valid_fit_file(tmp_path: Path) -> Path:
    """A byte-valid fit artifact written by write_fit — the base each broken
    variant mutates."""
    amounts = [float(x) for x in range(1, 201)]
    fit = fit_lognormal(amounts)
    write_fit(fit, goodness_of_fit(amounts, fit), tmp_path / "fit.csv")
    return tmp_path / "fit.csv"


def test_read_fit_returns_the_pinned_fit():
    """The tracked artifact reads back to the pinned fit and the median cell —
    read_fit is the mirror of write_fit."""
    from tests import pins

    fit, gof = read_fit()
    assert round(fit.mu, 6) == pins.DAMIR_MU
    assert round(fit.sigma, 6) == pins.DAMIR_SIGMA
    assert fit.n == pins.DAMIR_N
    assert next(d.empirical for d in gof if d.decile == 50) == pins.DAMIR_EMP_P50


def test_read_fit_refuses_unknown_missing_or_non_numeric_names(tmp_path):
    """A file with a name missing, an extra name, or a non-numeric value refuses
    with the name — never a silent default."""
    lines = _valid_fit_file(tmp_path).read_text(encoding="utf-8").splitlines()

    missing = tmp_path / "missing.csv"
    missing.write_text(
        "\n".join(x for x in lines if not x.startswith("mu,")) + "\n", "utf-8"
    )
    with pytest.raises(ValueError, match="mu"):
        read_fit(missing)

    added = tmp_path / "added.csv"
    added.write_text("\n".join(lines) + "\nmean,42.0\n", "utf-8")
    with pytest.raises(ValueError, match="mean"):
        read_fit(added)

    nonnum = tmp_path / "nonnum.csv"
    nonnum.write_text(
        "\n".join("sigma,abc" if x.startswith("sigma,") else x for x in lines) + "\n",
        "utf-8",
    )
    with pytest.raises(ValueError, match="sigma"):
        read_fit(nonnum)


def test_read_fit_refuses_duplicate_oversized_and_bad_n(tmp_path):
    """The remaining guards refuse too: a duplicate name, a file over the size
    cap, and a non-positive-integer `n` — each with the reason, never a silent
    default."""
    lines = _valid_fit_file(tmp_path).read_text(encoding="utf-8").splitlines()

    dup = tmp_path / "dup.csv"
    dup.write_text("\n".join(lines) + "\nmu,3.5\n", "utf-8")  # mu twice
    with pytest.raises(ValueError, match="duplicate"):
        read_fit(dup)

    for bad_n in ("0", "-1", "x"):
        p = tmp_path / f"n_{bad_n}.csv"
        p.write_text(
            "\n".join(f"n,{bad_n}" if x.startswith("n,") else x for x in lines) + "\n",
            "utf-8",
        )
        with pytest.raises(ValueError, match="positive integer"):
            read_fit(p)

    oversized = tmp_path / "big.csv"
    oversized.write_text(
        "name,value\n" + "\n".join(f"junk{i},1" for i in range(20000)) + "\n", "utf-8"
    )
    with pytest.raises(ValueError, match="over the"):
        read_fit(oversized)


def test_read_fit_refuses_a_negative_sigma(tmp_path):
    """sigma is a standard deviation: a negative value is domain-invalid and
    refuses, rather than flowing into exp(mu + sigma²/2) as a wrong number."""
    lines = _valid_fit_file(tmp_path).read_text(encoding="utf-8").splitlines()
    neg = tmp_path / "neg_sigma.csv"
    neg.write_text(
        "\n".join("sigma,-1.5" if x.startswith("sigma,") else x for x in lines) + "\n",
        "utf-8",
    )
    with pytest.raises(ValueError, match="sigma"):
        read_fit(neg)


# --- 7b lands no mart; 8a lands the cost-model marts, 8b the simulator's ------


def test_cost_model_marts_exist_and_8b_marts_do_not():
    """8a lands the three cost-model marts (Beat 3); 8b's simulator marts, and
    any damir-named mart, do not exist yet."""
    marts = ROOT / "sql" / "marts"
    for landed in (
        "cost_model_params.sql",
        "cost_model_outputs.sql",
        "cost_curves.sql",
    ):
        assert (marts / landed).exists()
    for pending in ("guardrail_sim.sql", "sla_threshold.sql"):
        assert not (marts / pending).exists()
    assert not any("damir" in p.name for p in marts.glob("*.sql"))


# --- the real fixture: pinned once it exists ---------------------------------


@pytest.mark.skipif(not FIXTURE_CSV.is_file(), reason="fixtures/damir/ not built yet")
def test_fit_params_over_fixture():
    """Once the developer has fetched a month and drawn the fixture, the fit is
    pinned here (fill DAMIR_MU / DAMIR_SIGMA in tests/pins.py)."""
    from tests import pins

    amounts = read_amounts(FIXTURE_CSV)
    fit = fit_lognormal(amounts.values)
    assert round(fit.mu, 6) == pins.DAMIR_MU
    assert round(fit.sigma, 6) == pins.DAMIR_SIGMA
    assert fit.n == pins.DAMIR_N


@pytest.mark.skipif(not FIXTURE_CSV.is_file(), reason="fixtures/damir/ not built yet")
def test_artifact_equals_recompute(tmp_path):
    """The committed data/damir/claim_cost_fit.csv equals the fit recomputed
    from the frozen fixture — no drift. Recompute into a throwaway file and
    compare bytes, so the tracked file is never touched."""
    from opendata.fit import ARTIFACT

    amounts = read_amounts(FIXTURE_CSV)
    fit = fit_lognormal(amounts.values)
    gof = goodness_of_fit(amounts.values, fit)
    recomputed = tmp_path / "recompute.csv"
    write_fit(fit, gof, recomputed)
    assert ARTIFACT.read_bytes() == recomputed.read_bytes()
