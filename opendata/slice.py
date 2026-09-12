"""Read the reimbursed-amount column out of a DAMIR CSV — a foreign input the
repo does not own, so its shape is declared and anything off it is dropped and
counted, never silently absorbed (CLAUDE.md "Before reporting DONE" #8).

The declared shape: a `;`-delimited CSV with a header row that includes both
`PRS_REM_MNT` and `PRS_REM_TYP`. A kept amount is a `PRS_REM_MNT` cell parsed as
a number strictly greater than zero whose row's `PRS_REM_TYP` is a legal part
(`0`/`1` — Amendment A1: type >= 2 is a *part supplémentaire*, not the claim
cost, so it is dropped). A blank, a non-numeric cell, a zero, a negative, or a
non-legal type is dropped and tallied. The same reader serves the real fetched
month and the frozen fixture — the fixture is written in exactly this shape
(the `PRS_REM_MNT` and `PRS_REM_TYP` columns), so the type filter is
reproducible offline from the fixture alone.

Reads stream, so a gigabyte national month never lands in memory at once. The
fixture is drawn by *systematic* sampling — every k-th valid amount across the
whole file — because a DAMIR month is sorted by its aggregation axes, so the
first N rows would be one biased corner (a department, a care category), not the
month. Systematic sampling is deterministic (no RNG) and spans the file."""

from __future__ import annotations

import csv
import gzip
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from io import TextIOBase
from pathlib import Path

from ingest.parsed import DECIMAL_SHAPE
from opendata.sources import AMOUNT_COLUMN, DELIMITER, LEGAL_TYPES, TYPE_COLUMN

# The two bytes every gzip stream begins with (RFC 1952). We detect gzip by
# these, not by the file name, so a gzipped national month and a plain tracked
# fixture read through one path — a mis-named file is read by what it is, not
# what it is called (Amendment A2).
_GZIP_MAGIC = b"\x1f\x8b"

# The frozen fixture: a small, real, brand-free slice CI fits offline.
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "damir"
FIXTURE_CSV = FIXTURE_DIR / "damir-sample.csv"
MANIFEST = FIXTURE_DIR / "MANIFEST.sha256"

# The default fixture size when `make sample-damir` is called without N.
DEFAULT_SAMPLE_N = 1000


@dataclass(frozen=True)
class Amounts:
    """The kept amounts and what the guard dropped — the count is printed, so a
    slice that is mostly noise is visible, not hidden."""

    values: list[float]
    dropped: int

    @property
    def read(self) -> int:
        return len(self.values) + self.dropped


@dataclass(frozen=True)
class Sample:
    """A systematic draw: the sampled rows (amount + legal type), plus what the
    whole pass saw. `values` is the amounts alone, for the fit and the print."""

    rows: list[tuple[float, str]]
    total_valid: int
    dropped: int
    stride: int

    @property
    def values(self) -> list[float]:
        return [amount for amount, _ in self.rows]


# The one numeric shape a foreign decimal cell may take — plain ASCII digits,
# at most one `.` or French `,` separator, an optional leading minus — lives in
# `ingest.parsed.DECIMAL_SHAPE` (imported above) and is re-exported here for the
# DAMIR readers that have always named it `opendata.slice.DECIMAL_SHAPE`. It
# rejects the exotic forms `float()` would otherwise accept (`1_000`, `1e5`,
# `nan`, `inf`, `+3`) and, since the fix, a non-ASCII digit (`٣`); so the guard
# over this foreign column stays a declared shape, not "whatever float() parses"
# (round 1, code-reviewer #7; 9h round 2, code-reviewer #1;
# fix/foreign-shape-shared-home).


def parse_amount(cell: str) -> float | None:
    """A DAMIR amount cell -> a positive float, or `None` if it is not one.
    Accepts plain decimal digits with at most one `.` or `,` separator (French
    CSVs use `,`); a blank, text, an exotic numeric form (`1_000`, `1e5`), a
    zero, a negative or a non-finite value returns `None`."""
    text = cell.strip()
    if not DECIMAL_SHAPE.fullmatch(text):
        return None
    value = float(text.replace(",", "."))  # shape-checked, so this cannot raise
    return value if value > 0 else None


def _open_text(path: Path) -> TextIOBase:
    """Open a DAMIR CSV as a streaming UTF-8 text handle, transparently
    decompressing a gzip file. Gzip is detected by its magic bytes, not the file
    name, so the gzipped national month the portal serves and the plain tracked
    fixture read through one path (Amendment A2). Streams either way — a
    gigabyte month never lands in memory at once."""
    with path.open("rb") as probe:
        is_gzip = probe.read(2) == _GZIP_MAGIC
    if is_gzip:
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


def _iter_rows(path: Path) -> Iterator[tuple[str, str]]:
    """Yield the `(PRS_REM_MNT, PRS_REM_TYP)` cells of every data row, streaming.
    Raises `ValueError` if the file is missing either declared column — a file
    that is not the declared shape refuses; it does not read as an empty slice.
    The parser's own failure (`csv.Error`, a field past its limit — no
    `ValueError`) folds into the same refusal: the reader owns its failure
    type, so the CLI boundary catches one declared set (code-craft → Error
    policy; `fee_split._iter_rows` is the sibling)."""
    try:
        with _open_text(path) as fh:
            reader = csv.DictReader(fh, delimiter=DELIMITER)
            fields = reader.fieldnames or []
            missing = [c for c in (AMOUNT_COLUMN, TYPE_COLUMN) if c not in fields]
            if missing:
                raise ValueError(
                    f"{path.name}: missing column(s) {missing} "
                    f"(found {reader.fieldnames}); not a DAMIR slice"
                )
            for row in reader:
                yield row.get(AMOUNT_COLUMN, ""), row.get(TYPE_COLUMN, "")
    except csv.Error as exc:
        raise ValueError(
            f"{path.name}: not a CSV the reader can parse ({exc}); not a DAMIR slice"
        ) from exc


def legal_amount(amount_cell: str, type_cell: str) -> float | None:
    """A DAMIR row's kept amount: a positive `PRS_REM_MNT` whose `PRS_REM_TYP`
    is a legal part (`0`/`1`). A non-legal type (a *part supplémentaire*, `>= 2`),
    a blank type, or a non-positive/non-numeric amount returns `None` — dropped
    and counted by the caller (Amendment A1)."""
    if type_cell.strip() not in LEGAL_TYPES:
        return None
    return parse_amount(amount_cell)


def read_amounts(path: Path) -> Amounts:
    """Read `PRS_REM_MNT`, keeping only positive legal-type (`0`/`1`) amounts,
    dropping and counting the rest. Holds the kept amounts in memory — use it on
    the fixture, not a national month (use `systematic_sample` for that)."""
    kept: list[float] = []
    dropped = 0
    for amount_cell, type_cell in _iter_rows(path):
        amount = legal_amount(amount_cell, type_cell)
        if amount is None:
            dropped += 1
        else:
            kept.append(amount)
    return Amounts(values=kept, dropped=dropped)


def systematic_sample(path: Path, n: int) -> Sample:
    """Draw N rows spread across the whole file: two streaming passes, no RNG.
    Pass one counts the valid (positive, legal-type) amounts; pass two keeps
    every k-th, where k = total // N (at least 1). Each kept row carries its
    amount and its legal type, so the fixture is written in the declared two-
    column shape. Memory holds only the N kept, never the month. A file with N
    or fewer valid amounts returns them all (stride 1)."""
    if n <= 0:
        raise ValueError(f"sample size must be positive, got {n}")
    total_valid = 0
    dropped = 0
    for amount_cell, type_cell in _iter_rows(path):
        if legal_amount(amount_cell, type_cell) is None:
            dropped += 1
        else:
            total_valid += 1
    if total_valid == 0:
        return Sample(rows=[], total_valid=0, dropped=dropped, stride=1)
    stride = max(1, total_valid // n)
    kept: list[tuple[float, str]] = []
    index = 0
    for amount_cell, type_cell in _iter_rows(path):
        amount = legal_amount(amount_cell, type_cell)
        if amount is None:
            continue
        if index % stride == 0 and len(kept) < n:
            kept.append((amount, type_cell.strip()))
        index += 1
    return Sample(rows=kept, total_valid=total_valid, dropped=dropped, stride=stride)


def write_damir_fixture(
    rows: list[tuple[float, str]], path: Path = FIXTURE_CSV
) -> None:
    """Write a two-column `PRS_REM_MNT;PRS_REM_TYP` CSV — the frozen fixture's
    shape, the same shape `read_amounts` reads, so the legal-type filter is
    reproducible offline from the fixture. Amounts are written at two decimals
    for a byte-stable file. Numbers only (a `0`/`1` type code is no brand and no
    personal data): no address, no attribution, no review body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=DELIMITER)
        writer.writerow([AMOUNT_COLUMN, TYPE_COLUMN])
        for value, type_code in rows:
            writer.writerow([f"{value:.2f}", type_code])


def freeze_manifest(directory: Path = FIXTURE_DIR) -> None:
    """Write `MANIFEST.sha256` over every file in the fixture directory but the
    manifest itself — the `sha256sum` format the frozen-fixtures test reads."""
    lines = []
    for file in sorted(p for p in directory.glob("*") if p.name != MANIFEST.name):
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        lines.append(f"{digest}  {file.name}")
    (directory / MANIFEST.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
