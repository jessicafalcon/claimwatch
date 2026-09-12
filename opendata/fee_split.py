"""The fee split: of everything liberal practitioners billed in a year, the part
above the public tariff — *extra billing* (dépassements d'honoraires) — read
from data.ameli's `honoraires` table for the four top-level profession
families (Phase 9i, Beat 3's B3.3).

In France a practitioner's fee has a public tariff; the Assurance Maladie
reimburses a set share of the tariff and never the part billed above it. That
part, and the unreimbursed share of the tariff, are what a complementary
insurer covers. Open DAMIR (the claim-cost anchor Beat 3 draws from) is what
the Assurance Maladie reimbursed, so the extra billing is absent from it by
construction; this file lands the one public number that says how large the
part it never sees is: `extra / (tariff + extra)`, two sums and a division a
reader redoes in a spreadsheet. Nothing is fitted — the table holds annual
per-practitioner totals, not claim amounts, so there is no curve to fit.

Two foreign inputs, each read to a declared shape. The developer's browser
download of the export (`;`-delimited, a UTF-8 byte-order mark on the header,
whole-euro totals, `NS`/`NC` where suppressed): the slice keeps one year's
four national family rows and refuses by name a year with no national rows, a
column missing, a family missing or repeated, or a total off the bounded
euro-total shape — a dropped family would silently move the national total —
and drops and counts every other row. The tracked artifact
(`data/ameli/fee_split.csv`, `name,value`, numbers only): its reader is the
strict mirror of its writer, one closed name set for both. The frozen fixture
under `fixtures/ameli/` is the four rows in exactly the columns the slice
reads, so CI reproduces the artifact offline from the fixture alone.

No fetch lives here: the host's robots file disallows its API and download
paths to every crawler, and the repo honours that (Phases 2, 3a, 3c)."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ingest.parsed import euro_total_in_range
from opendata.fit import finite_float, read_name_value_rows, shown, shown_names
from opendata.sources import (
    AMELI_DELIMITER,
    AMELI_DEPARTMENT_COLUMN,
    AMELI_EXTRA_COLUMN,
    AMELI_FAMILIES,
    AMELI_NATIONAL_DEPARTMENT,
    AMELI_NATIONAL_REGION,
    AMELI_PROFESSION_COLUMN,
    AMELI_REGION_COLUMN,
    AMELI_TARIFF_COLUMN,
    AMELI_YEAR_COLUMN,
    valid_year,
)

_ROOT = Path(__file__).resolve().parent.parent
# The frozen fixture: one year's four national family rows, brand-free (a
# profession family and two whole-euro totals), read-only after 9i.
FIXTURE_DIR = _ROOT / "fixtures" / "ameli"
FIXTURE_CSV = FIXTURE_DIR / "ameli-national.csv"
# The tracked artifact — under data/, kept out of the gitignore's data/* by the
# explicit `!data/ameli/` negation (the data/damir/ precedent).
ARTIFACT = _ROOT / "data" / "ameli" / "fee_split.csv"

# The six columns the slice reads, in the order the fixture writes them — one
# declared shape for the developer's export and the frozen fixture alike.
FIXTURE_COLUMNS: tuple[str, ...] = (
    AMELI_YEAR_COLUMN,
    AMELI_PROFESSION_COLUMN,
    AMELI_REGION_COLUMN,
    AMELI_DEPARTMENT_COLUMN,
    AMELI_TARIFF_COLUMN,
    AMELI_EXTRA_COLUMN,
)
# A share is written at six places — `_PARAM_DP` of the fit artifact: a range's
# ends and a default shown as a one-place percentage need no more.
_SHARE_DP = 6
_LABELS = frozenset(label for _slug, label in AMELI_FAMILIES)


@dataclass(frozen=True)
class FamilyRow:
    """One profession family's year: the fees billed at the tariff and the fees
    billed above it, whole euros, and the share the second is of the whole."""

    slug: str
    label: str
    tariff_eur: int
    extra_eur: int

    @property
    def billed_eur(self) -> int:
        return self.tariff_eur + self.extra_eur

    @property
    def share(self) -> float:
        """`extra / (tariff + extra)` — the family's extra-billing share."""
        return self.extra_eur / self.billed_eur


@dataclass(frozen=True)
class FeeTotals:
    """The fee split of one year: the four families in `AMELI_FAMILIES` order,
    and the all-families figures summed from them — the same division over the
    summed totals, which lies between the lowest and highest family share
    because it is their billed-euro-weighted mean."""

    year: int
    families: tuple[FamilyRow, ...]

    @property
    def tariff_eur_all(self) -> int:
        return sum(f.tariff_eur for f in self.families)

    @property
    def extra_eur_all(self) -> int:
        return sum(f.extra_eur for f in self.families)

    @property
    def share_all(self) -> float:
        return self.extra_eur_all / (self.tariff_eur_all + self.extra_eur_all)

    @property
    def lowest_share(self) -> float:
        return min(f.share for f in self.families)

    @property
    def highest_share(self) -> float:
        return max(f.share for f in self.families)


@dataclass(frozen=True)
class NationalSlice:
    """What the slice kept and what it dropped — the count is printed, so an
    export that is mostly other territories and years is visible, not hidden."""

    totals: FeeTotals
    dropped: int


# The byte-order mark U+FEFF. The portal's API export carries one before the
# first header cell; the browser's "Export" of the same table carries two (the
# portal's and the export option's), with CRLF line ends. The shape is "the
# header, after any leading marks": every leading mark on the first field is
# dropped, not exactly one (`utf-8-sig` would drop one and leave `\ufeffannee`
# as a missing column). DECISIONS → Gotchas, Phase 9i.
_BOM = "\ufeff"


def _iter_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield each data row as `{column: cell}` over the six declared columns.
    Any leading byte-order marks on the first header cell are dropped (one from
    the portal's API export, two from a browser export; none on the fixture).
    A file missing any declared column refuses — it is not this shape, not an
    empty slice. Streams row by row, so there is no byte cap on the file: a
    developer-placed download from a known portal is never landed in memory
    at once (the `opendata/slice.py` reason), and a wrong shape refuses on the
    header before a data row is read. The parser's own failure (`csv.Error`, a
    field past its limit — not a `ValueError`) is folded into the one refusal
    this reader declares, as `decode_json` folds the JSON decoder's, so the
    CLI boundary catches the declared type and never a traceback (review round
    2, security #1)."""
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter=AMELI_DELIMITER)
            fields = list(reader.fieldnames or [])
            if fields:
                fields[0] = fields[0].lstrip(_BOM)
                reader.fieldnames = fields
            missing = [c for c in FIXTURE_COLUMNS if c not in fields]
            if missing:
                found = [shown(f) for f in fields[: len(FIXTURE_COLUMNS)]]
                raise ValueError(
                    f"{path.name}: missing column(s) {missing} (found {found}); "
                    "not a data.ameli honoraires export"
                )
            for row in reader:
                yield {c: (row.get(c) or "") for c in FIXTURE_COLUMNS}
    except csv.Error as exc:
        raise ValueError(
            f"{path.name}: not a CSV the reader can parse ({exc}); "
            "not a data.ameli honoraires export"
        ) from exc


def _is_national(row: dict[str, str]) -> bool:
    return (
        row[AMELI_REGION_COLUMN].strip() == AMELI_NATIONAL_REGION
        and row[AMELI_DEPARTMENT_COLUMN].strip() == AMELI_NATIONAL_DEPARTMENT
    )


def _euro_total(cell: str, what: str, where: str) -> int:
    """A total in the bounded euro-total shape, or a refusal that names what it
    was (`'Sages-femmes' depassements_totaux`, `'tariff_eur_all'`) — a
    suppressed `NS`/`NC`, a decimal, a sign or a value past the ceiling would
    otherwise move the national total. The one helper both readers use. The
    cell is stripped first — the foreign-CSV cell convention
    `opendata/slice.py::parse_amount` set; the shape itself takes no
    whitespace (review round 2, code #3)."""
    value = euro_total_in_range(cell.strip())
    if value is None:
        raise ValueError(f"{where}: {what} is not a whole-euro total: {shown(cell)}")
    return value


def _families_from_rows(
    rows: Iterable[dict[str, str]], year: int, where: str
) -> NationalSlice:
    """The year's four national family rows out of the rows given (an export's
    stream or a fixture's list); drop and count every other row. Refuses by
    name, in this order: a year with no national rows at all, a family
    repeated, a family missing, a total off its shape, a family that billed
    nothing (its share is a division by zero)."""
    wanted = str(year)
    kept: dict[str, dict[str, str]] = {}
    national_years: set[str] = set()
    dropped = 0
    for row in rows:
        if not _is_national(row):
            dropped += 1
            continue
        national_years.add(row[AMELI_YEAR_COLUMN].strip())
        label = row[AMELI_PROFESSION_COLUMN].strip()
        if row[AMELI_YEAR_COLUMN].strip() != wanted or label not in _LABELS:
            dropped += 1
            continue
        if label in kept:
            raise ValueError(f"{where}: family {label!r} appears twice for {year}")
        kept[label] = row
    if wanted not in national_years:
        raise ValueError(
            f"{where}: no national rows for {year} (years found: "
            f"{shown_names(sorted(national_years))})"
        )
    if missing := [label for _slug, label in AMELI_FAMILIES if label not in kept]:
        raise ValueError(f"{where}: family row(s) missing for {year}: {missing}")
    families = []
    for slug, label in AMELI_FAMILIES:
        row = kept[label]
        family = FamilyRow(
            slug=slug,
            label=label,
            tariff_eur=_euro_total(
                row[AMELI_TARIFF_COLUMN], f"{label!r} {AMELI_TARIFF_COLUMN}", where
            ),
            extra_eur=_euro_total(
                row[AMELI_EXTRA_COLUMN], f"{label!r} {AMELI_EXTRA_COLUMN}", where
            ),
        )
        if family.billed_eur == 0:
            raise ValueError(f"{where}: family {label!r} billed nothing in {year}")
        families.append(family)
    return NationalSlice(totals=FeeTotals(year, tuple(families)), dropped=dropped)


def read_national_families(path: Path, year: int) -> NationalSlice:
    """Keep the year's four national family rows (`region = 99`, `departement =
    999`, a label in `AMELI_FAMILIES`) out of a data.ameli export, streaming;
    drop and count every other row; refuse by name as `_families_from_rows`
    says."""
    return _families_from_rows(_iter_rows(path), year, path.name)


def read_fixture(path: Path = FIXTURE_CSV) -> NationalSlice:
    """The frozen fixture, read once: it holds exactly one year — `split-ameli`
    takes no variable, so the year is read off the file — and that year's four
    family rows. No rows, two years, or a year off `valid_year`'s shape refuses
    by name."""
    rows = list(_iter_rows(path))
    years = {row[AMELI_YEAR_COLUMN].strip() for row in rows}
    if len(years) != 1:
        raise ValueError(
            f"{path.name}: the fixture must hold exactly one year, found "
            f"{shown_names(sorted(years))}"
        )
    (year,) = years
    try:
        wanted = valid_year(year)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc
    return _families_from_rows(rows, wanted, path.name)


def write_ameli_fixture(totals: FeeTotals, path: Path = FIXTURE_CSV) -> None:
    """Write the four family rows in exactly the six columns the slice reads,
    the national codes constant, so `read_national_families` reproduces the
    split offline from the fixture alone. A profession family and two whole-euro
    totals: no address, no attribution, no brand, no person."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=AMELI_DELIMITER)
        writer.writerow(FIXTURE_COLUMNS)
        for f in totals.families:
            writer.writerow(
                [
                    str(totals.year),
                    f.label,
                    AMELI_NATIONAL_REGION,
                    AMELI_NATIONAL_DEPARTMENT,
                    str(f.tariff_eur),
                    str(f.extra_eur),
                ]
            )


# Every name the artifact carries, in write order: the year, then each family's
# three figures (its two totals and its share), then the all-families three.
# The writer emits exactly this tuple, the reader requires exactly it and the
# tracked-files test reads it — one closed set, no copy that can drift.
_FAMILY_SLUGS = tuple(slug for slug, _label in AMELI_FAMILIES)
FEE_SPLIT_FIELD_NAMES: tuple[str, ...] = (
    "year",
    *(
        name
        for slug in (*_FAMILY_SLUGS, "all")
        for name in (f"tariff_eur_{slug}", f"extra_eur_{slug}", f"share_{slug}")
    ),
)


def write_fee_split(totals: FeeTotals, path: Path = ARTIFACT) -> None:
    """Write the fee split as one tidy `name,value` CSV in `FEE_SPLIT_FIELD_NAMES`
    order: whole euros as the source publishes them, shares at six places.
    Numbers only; fixed decimals make the file byte-identical on every rerun."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str]] = [("year", str(totals.year))]
    triples = [(f.slug, f.tariff_eur, f.extra_eur, f.share) for f in totals.families]
    triples.append(
        ("all", totals.tariff_eur_all, totals.extra_eur_all, totals.share_all)
    )
    for slug, tariff, extra, share in triples:
        rows.append((f"tariff_eur_{slug}", str(tariff)))
        rows.append((f"extra_eur_{slug}", str(extra)))
        rows.append((f"share_{slug}", f"{share:.{_SHARE_DP}f}"))
    assert tuple(name for name, _ in rows) == FEE_SPLIT_FIELD_NAMES
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "value"])
        writer.writerows(rows)


def _share(raw: dict[str, str], name: str, where: str, expected: float) -> float:
    """A written share: a finite decimal in [0, 1] that equals its own totals'
    division at the written places — never a figure the totals do not give."""
    value = finite_float(raw, name, where)
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{where}: {name!r} is a share and must be in [0, 1]: {value!r}"
        )
    if f"{value:.{_SHARE_DP}f}" != f"{expected:.{_SHARE_DP}f}":
        raise ValueError(
            f"{where}: {name!r} is not its totals' division "
            f"({expected:.{_SHARE_DP}f}): {value!r}"
        )
    return value


def read_fee_split(path: Path = ARTIFACT) -> FeeTotals:
    """Read the tracked artifact back into its `FeeTotals` — the strict mirror
    of `write_fee_split`. Exactly the closed name set; the year in `valid_year`'s
    shape; every total in the bounded euro-total shape; every share a finite
    decimal in [0, 1] equal to its totals' division; the all-families totals
    equal to the family sums. Anything else refuses by name — never a silent
    default, never a traceback downstream. Row order does not matter."""
    where = path.name
    raw = read_name_value_rows(path, FEE_SPLIT_FIELD_NAMES, "fee split")
    try:
        year = valid_year(raw["year"])
    except ValueError as exc:
        raise ValueError(f"{where}: 'year': {exc}") from exc
    families = []
    for slug, label in AMELI_FAMILIES:
        family = FamilyRow(
            slug=slug,
            label=label,
            tariff_eur=_euro_total(
                raw[f"tariff_eur_{slug}"], repr(f"tariff_eur_{slug}"), where
            ),
            extra_eur=_euro_total(
                raw[f"extra_eur_{slug}"], repr(f"extra_eur_{slug}"), where
            ),
        )
        if family.billed_eur == 0:
            raise ValueError(f"{where}: family {label!r} billed nothing")
        _share(raw, f"share_{slug}", where, family.share)
        families.append(family)
    totals = FeeTotals(year, tuple(families))
    for name, expected in (
        ("tariff_eur_all", totals.tariff_eur_all),
        ("extra_eur_all", totals.extra_eur_all),
    ):
        if _euro_total(raw[name], repr(name), where) != expected:
            raise ValueError(
                f"{where}: {name!r} is not the sum of the four families ({expected})"
            )
    _share(raw, "share_all", where, totals.share_all)
    return totals


def format_fee_split(totals: FeeTotals) -> str:
    """The one-screen summary `make split-ameli` prints: each family's two totals
    and share, then the all-families line with its lowest and highest family."""
    width = max(len(f.label) for f in totals.families)
    lines = [
        f"fee split {totals.year} — data.ameli honoraires, national, the four "
        "profession families:",
        f"  {'family':{width}}  {'at the tariff €':>18}  {'above it €':>16}  share",
    ]
    for f in totals.families:
        lines.append(
            f"  {f.label:{width}}  {f.tariff_eur:>18,}  {f.extra_eur:>16,}  "
            f"{f.share:.{_SHARE_DP}f}"
        )
    lines.append(
        f"  {'all four':{width}}  {totals.tariff_eur_all:>18,}  "
        f"{totals.extra_eur_all:>16,}  {totals.share_all:.{_SHARE_DP}f}"
    )
    lines.append(
        f"extra-billing share = extra / (tariff + extra) = "
        f"{totals.share_all:.{_SHARE_DP}f}; lowest family "
        f"{totals.lowest_share:.{_SHARE_DP}f}, "
        f"highest {totals.highest_share:.{_SHARE_DP}f}"
    )
    return "\n".join(lines)
