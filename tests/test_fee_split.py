"""Phase 9i — the data.ameli fee split: the extra-billing share read from the
`honoraires` table's four national profession-family rows. Offline, no key, no
network: the slice is a guarded read of a hand-downloaded export, the split is
two sums and a division over a frozen fixture, and the tracked artifact's
reader is the strict mirror of its writer. The real-fixture pins run once
`fixtures/ameli/` exists; until then they skip (the 7b precedent)."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

import pipeline.cli as cli
from ingest.parsed import MAX_EURO_TOTAL, euro_total_in_range
from opendata.fee_split import (
    ARTIFACT,
    FEE_SPLIT_FIELD_NAMES,
    FIXTURE_COLUMNS,
    FIXTURE_CSV,
    FIXTURE_DIR,
    FamilyRow,
    FeeTotals,
    NationalSlice,
    fixture_year,
    format_fee_split,
    read_fee_split,
    read_national_families,
    write_fee_split,
    write_fixture,
)
from opendata.fit import MAX_ARTIFACT_BYTES, read_name_value_rows, shown, shown_names
from opendata.slice import freeze_manifest
from opendata.sources import AMELI_FAMILIES, valid_year
from pipeline.cli import main
from tests import pins

ROOT = Path(__file__).resolve().parents[1]
HEADER = ";".join(FIXTURE_COLUMNS)
# A small synthetic year: four families with round totals, so every share is a
# division a reader checks in their head (0.2, 0.5, 0.01, 0.0; all 710/4000).
SMALL = {
    "Ensemble des médecins": (800, 200),
    "Ensemble des chirurgiens-dentistes": (500, 500),
    "Sages-femmes": (990, 10),
    "Ensemble des auxiliaires médicaux": (1000, 0),
}


def _line(
    year: str,
    label: str,
    tariff: str,
    extra: str,
    *,
    region: str = "99",
    dept: str = "999",
) -> str:
    return f"{year};{label};{region};{dept};{tariff};{extra}"


def _national_lines(year: str = "2024", **override: tuple[str, str]) -> list[str]:
    lines = []
    for label, (tariff, extra) in SMALL.items():
        t, e = override.get(label, (str(tariff), str(extra)))
        lines.append(_line(year, label, t, e))
    return lines


def _write_export(
    path: Path,
    lines: list[str],
    *,
    header: str = HEADER,
    bom: bool = True,
    marks: int = 1,
    eol: str = "\n",
) -> Path:
    """An export-shaped `;`-CSV: the portal's byte-order mark on the header by
    default (`marks` of them — the browser export carries two), then one row
    per line, `eol`-terminated (the browser export is CRLF)."""
    text = ("\ufeff" * marks if bom else "") + eol.join([header, *lines]) + eol
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _small_totals(year: int = 2024) -> FeeTotals:
    return FeeTotals(
        year,
        tuple(FamilyRow(slug, label, *SMALL[label]) for slug, label in AMELI_FAMILIES),
    )


# --- the slice: one declared shape over the export and the fixture ---------


def test_slice_keeps_the_four_national_family_rows_of_the_year(tmp_path):
    """A sub-group row, another year, another region or département are not
    kept — only the year's four national family rows, in AMELI_FAMILIES order,
    each total read as a whole-euro integer."""
    lines = _national_lines() + [
        _line("2024", "Infirmiers", "700", "0"),  # a sub-group under auxiliaires
        _line("2024", "Ensemble des médecins", "1", "1", region="11"),  # a region
        _line("2024", "Ensemble des médecins", "1", "1", dept="75"),  # a département
        *_national_lines("2023"),  # another year
    ]
    national = read_national_families(_write_export(tmp_path / "e.csv", lines), 2024)
    assert isinstance(national, NationalSlice)
    assert [f.label for f in national.totals.families] == [
        label for _, label in AMELI_FAMILIES
    ]
    assert [(f.tariff_eur, f.extra_eur) for f in national.totals.families] == list(
        SMALL.values()
    )
    assert national.dropped == 3 + 4
    assert national.totals.year == 2024


def test_slice_drops_and_counts_every_other_row(tmp_path):
    """Every row that is not one of the four kept rows is dropped and counted —
    never silently absorbed — and a national row of another family label is
    dropped too (the closed set)."""
    lines = _national_lines() + [
        _line(
            "2024", "Ensemble des médecins spécialistes (hors généralistes)", "9", "9"
        ),
        _line("2024", "", "9", "9"),
    ]
    national = read_national_families(_write_export(tmp_path / "e.csv", lines), 2024)
    assert national.dropped == 2 and len(national.totals.families) == 4


def test_slice_refuses_a_year_with_no_national_rows_by_name(tmp_path):
    """A valid year the file does not hold refuses in one line naming the year
    — before any family is checked, so it is not four 'family missing' lines."""
    path = _write_export(tmp_path / "e.csv", _national_lines("2024"))
    with pytest.raises(ValueError, match="no national rows for 2031"):
        read_national_families(path, 2031)


def test_slice_refuses_a_missing_repeated_or_suppressed_family_by_name(tmp_path):
    """A family missing, a family twice, a suppressed `NC`/`NS` total, a
    decimal, a signed or a too-large total each refuse by the family's name —
    a dropped family would silently move the national total."""
    missing = [line for line in _national_lines() if "Sages-femmes" not in line]
    with pytest.raises(ValueError, match="missing.*Sages-femmes"):
        read_national_families(_write_export(tmp_path / "m.csv", missing), 2024)
    twice = _national_lines() + [_line("2024", "Sages-femmes", "1", "1")]
    with pytest.raises(ValueError, match="Sages-femmes.*appears twice"):
        read_national_families(_write_export(tmp_path / "t.csv", twice), 2024)
    for bad in ("NC", "NS", "", "12.5", "-1", "+1", "1e3", str(MAX_EURO_TOTAL + 1)):
        lines = _national_lines(**{"Ensemble des chirurgiens-dentistes": (bad, "5")})
        with pytest.raises(ValueError, match="chirurgiens-dentistes.*not a whole-euro"):
            read_national_families(_write_export(tmp_path / "s.csv", lines), 2024)
    zero = _national_lines(**{"Sages-femmes": ("0", "0")})
    with pytest.raises(ValueError, match="Sages-femmes.*billed nothing"):
        read_national_families(_write_export(tmp_path / "z.csv", zero), 2024)


def test_slice_reads_a_bom_header_and_refuses_a_missing_column(tmp_path):
    """The portal's UTF-8 byte-order mark before `annee` is read through — one
    from the API export, two with CRLF from a browser export — and the same file
    without it reads the same; a file lacking a declared column (or using `,` as
    its delimiter) refuses as not this shape, never as an empty slice."""
    with_bom = read_national_families(
        _write_export(tmp_path / "b.csv", _national_lines(), bom=True), 2024
    )
    without = read_national_families(
        _write_export(tmp_path / "n.csv", _national_lines(), bom=False), 2024
    )
    browser = read_national_families(  # two marks and CRLF, as a browser saves it
        _write_export(tmp_path / "w.csv", _national_lines(), marks=2, eol="\r\n"),
        2024,
    )
    assert with_bom == without == browser
    short = HEADER.replace(";depassements_totaux", "")
    with pytest.raises(ValueError, match="missing column.*depassements_totaux"):
        read_national_families(
            _write_export(tmp_path / "c.csv", _national_lines(), header=short), 2024
        )
    comma = _write_export(tmp_path / "k.csv", [], header=HEADER.replace(";", ","))
    with pytest.raises(ValueError, match="missing column"):
        read_national_families(comma, 2024)


def test_euro_total_shape_is_ascii_bounded_and_refuses_by_name():
    """The bounded euro-total shape: ASCII digits below one trillion — the
    count shape's ceiling (2^31 - 1) is below the national totals, so this is
    its own shape; a sign, a separator, a suppressed token, a non-ASCII digit or
    a value past the ceiling is None."""
    assert euro_total_in_range("0") == 0
    assert euro_total_in_range("25970577462") == 25_970_577_462  # above 2**31 - 1
    assert euro_total_in_range(str(MAX_EURO_TOTAL)) == MAX_EURO_TOTAL
    assert MAX_EURO_TOTAL == 10**12 - 1
    for bad in ("", " 1", "1.0", "-1", "+1", "NC", "NS", "٣", "1e5", str(10**12)):
        assert euro_total_in_range(bad) is None, bad
    assert pins.AMELI_TOTALS_ALL[0] > 2**31 - 1  # why the count shape cannot hold it


# --- the split is plain arithmetic ------------------------------------------


def test_shares_recomputed_by_hand():
    """Each family's share is extra / (tariff + extra); the all-families share
    is the same division over the summed totals and lies between the lowest and
    highest family — a weighted mean. Over the synthetic year and, when the
    fixture exists, over the pinned real totals."""
    totals = _small_totals()
    assert [f.share for f in totals.families] == [
        200 / 1000,
        500 / 1000,
        10 / 1000,
        0.0,
    ]
    assert (totals.tariff_eur_all, totals.extra_eur_all) == (3290, 710)
    assert totals.share_all == 710 / 4000
    assert totals.lowest_share == 0.0 and totals.highest_share == 0.5
    assert totals.lowest_share <= totals.share_all <= totals.highest_share
    real = FeeTotals(
        pins.AMELI_YEAR,
        tuple(
            FamilyRow(slug, label, *pins.AMELI_FAMILY_TOTALS[slug])
            for slug, label in AMELI_FAMILIES
        ),
    )
    for f in real.families:
        assert (
            round(f.extra_eur / (f.tariff_eur + f.extra_eur), 6)
            == pins.AMELI_SHARES[f.slug]
        )
    assert (real.tariff_eur_all, real.extra_eur_all) == pins.AMELI_TOTALS_ALL
    assert round(real.share_all, 6) == pins.AMELI_SHARE_ALL
    assert (
        round(real.lowest_share, 6),
        round(real.highest_share, 6),
    ) == pins.AMELI_SHARE_RANGE


def test_fee_split_field_names_is_the_write_order(tmp_path):
    """The artifact's names are exactly FEE_SPLIT_FIELD_NAMES, in that order —
    the writer's column sequence, the reader's requirement, the tracked-files
    test's set: one closed set."""
    path = tmp_path / "fee_split.csv"
    write_fee_split(_small_totals(), path)
    rows = path.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "name,value"
    assert tuple(r.split(",")[0] for r in rows[1:]) == FEE_SPLIT_FIELD_NAMES
    assert len(FEE_SPLIT_FIELD_NAMES) == 1 + 3 * (len(AMELI_FAMILIES) + 1)
    assert rows[1] == "year,2024" and rows[-1] == "share_all,0.177500"


def test_write_fee_split_is_byte_identical_on_rerun(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_fee_split(_small_totals(), a)
    write_fee_split(_small_totals(), b)
    assert a.read_bytes() == b.read_bytes()


def test_format_fee_split_prints_each_family_and_the_division():
    out = format_fee_split(_small_totals())
    assert "Sages-femmes" in out and "0.177500" in out
    assert "extra / (tariff + extra)" in out and "lowest family 0.000000" in out


# --- the strict reader: the mirror of write_fee_split -----------------------


def _valid_file(tmp_path: Path) -> Path:
    path = tmp_path / "fee_split.csv"
    write_fee_split(_small_totals(), path)
    return path


def _mutated(tmp_path: Path, name: str, value: str | None, extra: str = "") -> Path:
    """The valid file with one named row replaced (or dropped when value is
    None) and an optional extra line appended."""
    lines = _valid_file(tmp_path).read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        key = line.split(",")[0]
        if key == name:
            if value is None:
                continue
            line = f"{name},{value}"
        out.append(line)
    if extra:
        out.append(extra)
    bad = tmp_path / "bad.csv"
    bad.write_text("\n".join(out) + "\n", encoding="utf-8")
    return bad


def test_read_fee_split_is_order_independent(tmp_path):
    valid = _valid_file(tmp_path)
    lines = valid.read_text(encoding="utf-8").splitlines()
    shuffled = tmp_path / "shuffled.csv"
    shuffled.write_text(
        "\n".join([lines[0], *reversed(lines[1:])]) + "\n", encoding="utf-8"
    )
    assert read_fee_split(shuffled) == read_fee_split(valid) == _small_totals()


def test_read_fee_split_refuses_unknown_missing_or_non_numeric_names(tmp_path):
    with pytest.raises(ValueError, match="not in the fee split artifact's shape"):
        read_fee_split(_mutated(tmp_path, "year", "2024", extra="share_optam,0.1"))
    with pytest.raises(ValueError, match="missing.*share_all"):
        read_fee_split(_mutated(tmp_path, "share_all", None))
    with pytest.raises(ValueError, match="'share_medecins' is not a plain decimal"):
        read_fee_split(_mutated(tmp_path, "share_medecins", "abc"))
    with pytest.raises(ValueError, match="'tariff_eur_medecins' is not a whole-euro"):
        read_fee_split(_mutated(tmp_path, "tariff_eur_medecins", "800.0"))
    with pytest.raises(ValueError, match="'year'.*must be YYYY"):
        read_fee_split(_mutated(tmp_path, "year", "1999"))
    with pytest.raises(ValueError, match="duplicate name"):
        read_fee_split(_mutated(tmp_path, "year", "2024", extra="year,2024"))
    with pytest.raises(ValueError, match="header must be exactly"):
        bad = tmp_path / "h.csv"
        bad.write_text("name;value\n", encoding="utf-8")
        read_fee_split(bad)


def test_read_fee_split_refuses_a_share_outside_zero_one_a_negative_total_and_an_oversized_file(  # noqa: E501 -- the spec's Evidence row names this test
    tmp_path,
):
    with pytest.raises(ValueError, match="'share_dentistes' is a share.*\\[0, 1\\]"):
        read_fee_split(_mutated(tmp_path, "share_dentistes", "1.5"))
    with pytest.raises(
        ValueError, match="'share_dentistes' is not its totals' division"
    ):
        read_fee_split(_mutated(tmp_path, "share_dentistes", "0.4"))
    with pytest.raises(ValueError, match="'extra_eur_dentistes' is not a whole-euro"):
        read_fee_split(_mutated(tmp_path, "extra_eur_dentistes", "-5"))
    with pytest.raises(ValueError, match="'tariff_eur_all' is not the sum"):
        read_fee_split(_mutated(tmp_path, "tariff_eur_all", "3291"))
    with pytest.raises(ValueError, match="billed nothing"):
        read_fee_split(_mutated(tmp_path, "tariff_eur_auxiliaires", "0"))
    big = tmp_path / "big.csv"
    big.write_text(
        "name,value\n" + "x,1\n" * (MAX_ARTIFACT_BYTES // 4 + 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="over the .* cap"):
        read_fee_split(big)


def test_read_name_value_rows_is_the_shared_artifact_read(tmp_path):
    """The generic `name,value` read both artifact readers share: the size cap,
    the header, two cells, no duplicate, exactly the closed set; a shown token
    is cut, a stray-name list shows three and counts the rest."""
    path = tmp_path / "t.csv"
    path.write_text("name,value\nb,2\na,1\n", encoding="utf-8")
    assert read_name_value_rows(path, ("a", "b"), "test") == {"a": "1", "b": "2"}
    path.write_text("name,value\na,1,extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="wrong number of cells"):
        read_name_value_rows(path, ("a",), "test")
    assert shown("x" * 100).endswith("… (100 chars)")
    assert shown_names(["a", "b", "c", "d", "e"]).endswith("and 2 more")


# --- the frozen fixture and the developer-run targets -----------------------


def test_fixture_year_requires_exactly_one_year(tmp_path):
    assert (
        fixture_year(_write_export(tmp_path / "one.csv", _national_lines("2023")))
        == 2023
    )
    two = _write_export(
        tmp_path / "two.csv", _national_lines("2023") + _national_lines("2024")
    )
    with pytest.raises(ValueError, match="exactly one year"):
        fixture_year(two)
    with pytest.raises(ValueError, match="must be YYYY"):
        fixture_year(_write_export(tmp_path / "bad.csv", _national_lines("24")))


def test_fixture_round_trips_through_the_same_reader(tmp_path):
    """write_fixture writes the six declared columns, so the slice reads it
    back to the same totals — the split is reproducible from the fixture alone."""
    path = tmp_path / "ameli-national.csv"
    write_fixture(_small_totals(2022), path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == HEADER
    assert fixture_year(path) == 2022
    assert read_national_families(path, 2022).totals == _small_totals(2022)


def test_fee_split_freeze_manifest_matches_sha256(tmp_path):
    fixture_dir = tmp_path / "ameli"
    write_fixture(_small_totals(), fixture_dir / "ameli-national.csv")
    freeze_manifest(fixture_dir)
    digest, name = (fixture_dir / "MANIFEST.sha256").read_text().split()
    assert name == "ameli-national.csv"
    assert digest == hashlib.sha256((fixture_dir / name).read_bytes()).hexdigest()


def test_valid_year_refuses_bad_shapes():
    assert valid_year("2024") == 2024
    for bad in ("", "../x", '"; ', "1999", "2100", "24", "2024-01", "２０２４"):
        with pytest.raises(ValueError, match="year must be YYYY"):
            valid_year(bad)


def test_slice_ameli_year_validation_refuses_before_any_read(monkeypatch, tmp_path):
    """A bad YEAR refuses at valid_year (exit 2) before the export is opened —
    the export path is a constant the value never touches."""
    monkeypatch.setattr(cli, "AMELI_EXPORT", tmp_path / "never-read.csv")
    for bad in ("", "../x", '"; ', "1999", "2024-01"):
        assert main(["slice-ameli", f"--year={bad}"]) == 2, bad


def test_slice_ameli_no_export_is_a_message(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "AMELI_EXPORT", tmp_path / "honoraires.csv")
    assert main(["slice-ameli", "--year=2024"]) == 1
    out = capsys.readouterr().out
    assert "no export" in out and "robots" in out


def test_slice_ameli_writes_the_fixture_and_manifest(capsys, monkeypatch, tmp_path):
    """The happy path over a synthetic export: the fixture and its manifest are
    written where cli's names point, and an export off its shape is one
    refusal line, exit 2, nothing written."""
    export = _write_export(
        tmp_path / "honoraires.csv",
        _national_lines() + [_line("2024", "Infirmiers", "1", "1")],
    )
    fixture_dir = tmp_path / "fixtures" / "ameli"
    monkeypatch.setattr(cli, "AMELI_EXPORT", export)
    monkeypatch.setattr(cli, "AMELI_FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(cli, "AMELI_FIXTURE_CSV", fixture_dir / "ameli-national.csv")
    assert main(["slice-ameli", "--year=2024"]) == 0
    out = capsys.readouterr().out
    assert "4 national family rows for 2024 (1 other rows dropped)" in out
    assert (fixture_dir / "MANIFEST.sha256").is_file()
    assert (
        read_national_families(fixture_dir / "ameli-national.csv", 2024).totals
        == _small_totals()
    )
    monkeypatch.setattr(
        cli,
        "AMELI_EXPORT",
        _write_export(
            tmp_path / "nc.csv", _national_lines(**{"Sages-femmes": ("NC", "1")})
        ),
    )
    assert main(["slice-ameli", "--year=2024"]) == 2
    assert "not a whole-euro total" in capsys.readouterr().err


def test_split_ameli_missing_fixture_is_a_message(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "AMELI_FIXTURE_CSV", tmp_path / "nope.csv")
    assert main(["split-ameli"]) == 1
    assert "no fixture" in capsys.readouterr().out


def test_split_ameli_writes_and_prints(capsys, monkeypatch, tmp_path):
    fixture = tmp_path / "ameli-national.csv"
    write_fixture(_small_totals(), fixture)
    artifact = tmp_path / "fee_split.csv"
    monkeypatch.setattr(cli, "AMELI_FIXTURE_CSV", fixture)
    monkeypatch.setattr(cli, "FEE_SPLIT_ARTIFACT", artifact)
    assert main(["split-ameli"]) == 0
    out = capsys.readouterr().out
    assert "fee split 2024" in out and "0.177500" in out and "fee split written" in out
    assert read_fee_split(artifact) == _small_totals()


def test_fee_split_module_imports_no_network_module():
    """Invariant 9: nothing in the fee-split path can reach the network — the
    module imports neither `urllib` nor `httpx` (the host's robots file is
    honoured by having no fetch at all)."""
    source = (ROOT / "opendata" / "fee_split.py").read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"urllib", "httpx", "socket", "http"}, imported


# --- the real fixture: pinned once it exists ----------------------------------


@pytest.mark.skipif(not FIXTURE_CSV.is_file(), reason="fixtures/ameli/ not built yet")
def test_fixture_holds_the_pinned_year_and_totals():
    """The frozen fixture is the four national family rows of the pinned year,
    with the pinned whole-euro totals; its manifest matches its bytes."""
    year = fixture_year()
    assert year == pins.AMELI_YEAR
    national = read_national_families(FIXTURE_CSV, year)
    assert national.dropped == 0
    for f in national.totals.families:
        assert (f.tariff_eur, f.extra_eur) == pins.AMELI_FAMILY_TOTALS[f.slug]
    digest, name = (FIXTURE_DIR / "MANIFEST.sha256").read_text().split()
    assert name == FIXTURE_CSV.name
    assert digest == hashlib.sha256(FIXTURE_CSV.read_bytes()).hexdigest()


@pytest.mark.skipif(not FIXTURE_CSV.is_file(), reason="fixtures/ameli/ not built yet")
def test_fee_split_artifact_equals_recompute(tmp_path):
    """The committed data/ameli/fee_split.csv equals the split recomputed from
    the frozen fixture — no drift. Recompute into a throwaway file and compare
    bytes, so the tracked file is never touched."""
    totals = read_national_families(FIXTURE_CSV, fixture_year()).totals
    recomputed = tmp_path / "recompute.csv"
    write_fee_split(totals, recomputed)
    assert ARTIFACT.read_bytes() == recomputed.read_bytes()


@pytest.mark.skipif(not ARTIFACT.is_file(), reason="data/ameli/ not built yet")
def test_read_fee_split_returns_the_pinned_split():
    totals = read_fee_split()
    assert totals.year == pins.AMELI_YEAR
    assert {f.slug: round(f.share, 6) for f in totals.families} == pins.AMELI_SHARES
    assert round(totals.share_all, 6) == pins.AMELI_SHARE_ALL
    assert (
        round(totals.lowest_share, 6),
        round(totals.highest_share, 6),
    ) == pins.AMELI_SHARE_RANGE
