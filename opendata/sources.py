"""The one declaration of the Open DAMIR source — the open-data analogue of
`ingest/sources.py`, but far smaller: DAMIR names no insurer, so there is no
profile, segment, channel or brand token here. One dataset, one column, one
delimiter, one cache directory.

Open DAMIR ("base complète sur les dépenses d'assurance maladie interrégimes")
is published on data.gouv.fr as one monthly CSV per period: files prefixed `A`
from 2015 (`A202401` = January 2024), `;`-delimited, 55 variables per service
line. We read exactly one column — `PRS_REM_MNT`, the reimbursed amount
(montant remboursé) — and fit a lognormal to its distribution. The monthly
files are resolved from the dataset's data.gouv resource list by their
`A<YYYYMM>` title; each is large (a national month is gigabytes), so a fetch is
developer-run and its output stays under the gitignored cache."""

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
