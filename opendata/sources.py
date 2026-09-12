"""The declarations of the two open-data sources — the open-data analogue of
`ingest/sources.py`, but far smaller: neither names an insurer, so there is no
profile, segment, channel or brand token here.

**Open DAMIR** ("base complète sur les dépenses d'assurance maladie
interrégimes") is published on data.gouv.fr as one monthly CSV per period:
files prefixed `A` from 2015 (`A202401` = January 2024), `;`-delimited, 55
variables per service line. We read exactly one column — `PRS_REM_MNT`, the
reimbursed amount (montant remboursé) — and fit a lognormal to its
distribution. Each row is an aggregated per-cell total (a combination of the
dataset's dimensions), not a single claim, so the fit approximates the
claim-cost distribution rather than measuring it claim by claim. The monthly
files are resolved from the dataset's data.gouv resource list by their
`A<YYYYMM>` title; each is large (a national month is gigabytes), so a fetch is
developer-run and its output stays under the gitignored cache.

**data.ameli `honoraires`** (Phase 9i) is the Assurance Maladie's own table of
what liberal practitioners billed: one row per year × profession × territory,
carrying that year's total fees at the public tariff and total *extra billing*
(dépassements d'honoraires — the part billed above the tariff, which the
Assurance Maladie never reimburses). Annual per-practitioner totals, not
per-act amounts: nothing to fit, one share to read. The host's robots file
disallows its API and download paths to every crawler, so nothing here fetches
it — the developer saves the CSV export from a browser to the gitignored cache
and `make slice-ameli` reads that file offline."""

from __future__ import annotations

import re
from pathlib import Path

from ingest.sources import CACHE_ROOT  # the one binding of the data/cache root

# The BACKING dataset name (a backticked, `-`-joined slug; BACKING §, the source
# cell of B3.3/B4.3). Nothing brand-carrying: DAMIR is aggregate public data.
DATASET = "open-damir"

# The data.gouv dataset the monthly files hang off. The developer-run fetch
# reads this resource list and picks the month asked for; the slug doubles as
# the API id.
DATASET_API = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "open-damir-base-complete-sur-les-depenses-dassurance-maladie-interregimes/"
)

# The columns we read and their file's delimiter — declared once, read by the
# slice. `PRS_REM_MNT` is the reimbursed amount; French open-data CSVs are
# `;`-delimited (a `,` may be the decimal separator, which the slice handles).
AMOUNT_COLUMN = "PRS_REM_MNT"
DELIMITER = ";"

# The reimbursement-type column and the codes that are the legal Assurance
# Maladie part. The official variable dictionary (Amendment A1) says
# `PRS_REM_MNT` read without a `PRS_REM_TYP` filter pools two distinct things:
# type 0/1 = the legal reimbursement (the "claim cost" the study means), type
# >= 2 = *parts supplémentaires* (complementary / top-up shares). The slice
# keeps only the legal part so the fit is the claim cost, not a pool — a closed
# set of accepted codes, not a special-case skip.
TYPE_COLUMN = "PRS_REM_TYP"
LEGAL_TYPES = frozenset({"0", "1"})

# A fetched month lands here, gitignored (data/*), under the one cache-root
# binding. One file per month, named by the period so a re-fetch overwrites
# rather than piles up.
CACHE_DIR = CACHE_ROOT / "damir"

# The month a fetch takes: a closed `YYYY-MM` shape, validated in Python before
# any path is built from it (the settled Threat-model shape). Matched whole.
_MONTH = re.compile(r"\A(20[0-9]{2})-(0[1-9]|1[0-2])\Z")


def valid_month(month: str) -> tuple[int, int]:
    """`YYYY-MM` -> `(year, month)`, or raise `ValueError`. Empty, a
    path-escaping value (`../x`), a shell-metacharacter value (`"; `) and any
    out-of-range month fail the whole-string match — the value is never used to
    build a path until it has passed here."""
    m = _MONTH.fullmatch(month)
    if m is None:
        raise ValueError(f"month must be YYYY-MM in 2000-01..2099-12, got {month!r}")
    return int(m.group(1)), int(m.group(2))


def month_token(month: str) -> str:
    """The `A<YYYYMM>` token that names the monthly file in the resource list."""
    year, mon = valid_month(month)
    return f"A{year}{mon:02d}"


def cache_path(month: str) -> Path:
    """Where a fetched month is cached — derived only from a validated month.
    Keeps the portal's real `.csv.gz` extension: DAMIR months are served
    gzipped and the slice reads them so (Amendment A2)."""
    return CACHE_DIR / f"{month_token(month)}.csv.gz"


# --- data.ameli `honoraires` — the fee split (Phase 9i) ----------------------

# The BACKING dataset name (a backticked, `-`-joined slug; the source cell of
# B3.3 beside `open-damir`) and the dataset's public page, which the study's
# B3.3 panel names as a source. The publisher is a public institution, not an
# insurer the study reads about.
AMELI_DATASET = "data-ameli-honoraires"
AMELI_DATASET_URL = "https://data.ameli.fr/explore/dataset/honoraires/"

# Where the developer's browser download lands — a fixed path under the one
# cache-root binding, gitignored; no variable ever names it. The portal's CSV
# export is `;`-delimited with a UTF-8 byte-order mark on the header — one
# from the API, two with CRLF from a browser's Export (DECISIONS → Gotchas).
AMELI_EXPORT = CACHE_ROOT / "ameli" / "honoraires.csv"
AMELI_DELIMITER = ";"

# The six columns the slice reads, declared once. The two totals are whole
# euros for the year; the national rows carry the portal's "all" codes.
AMELI_YEAR_COLUMN = "annee"
AMELI_PROFESSION_COLUMN = "profession_sante"
AMELI_REGION_COLUMN = "region"
AMELI_DEPARTMENT_COLUMN = "departement"
AMELI_TARIFF_COLUMN = "hono_sans_depassement_totaux"
AMELI_EXTRA_COLUMN = "depassements_totaux"
AMELI_NATIONAL_REGION = "99"  # libelle_region FRANCE
AMELI_NATIONAL_DEPARTMENT = "999"  # libelle_departement FRANCE / Tout département

# The four top-level profession families, each with the slug the fee-split
# artifact names it by. They are the whole: the dataset's other national labels
# (généralistes and spécialistes under médecins, the five auxiliary professions,
# the two dentist groups) nest under these four, so a sum over every label would
# double-count. A closed set — a label outside it is not a family row.
AMELI_FAMILIES: tuple[tuple[str, str], ...] = (
    ("medecins", "Ensemble des médecins"),
    ("dentistes", "Ensemble des chirurgiens-dentistes"),
    ("sages_femmes", "Sages-femmes"),
    ("auxiliaires", "Ensemble des auxiliaires médicaux"),
)

# The year `slice-ameli` takes: the century-bounded alphabet `_MONTH` uses (one
# shape family), matched whole; the value filters rows and never names a path.
_YEAR = re.compile(r"\A20[0-9]{2}\Z")


def valid_year(year: str) -> int:
    """`YYYY` -> the year, or raise `ValueError`. Empty, a path-escaping value
    (`../x`), a shell-metacharacter value (`"; `) and anything outside
    2000..2099 fail the whole-string match."""
    if _YEAR.fullmatch(year) is None:
        raise ValueError(f"year must be YYYY in 2000..2099, got {year!r}")
    return int(year)
