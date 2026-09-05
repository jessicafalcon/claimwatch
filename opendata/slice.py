"""Read the reimbursed-amount column out of a DAMIR CSV — a foreign input the
repo does not own, so its shape is declared and anything off it is dropped and
counted, never silently absorbed (CLAUDE.md "Before reporting DONE" #8).

The declared shape: a `;`-delimited CSV with a header row that includes
`PRS_REM_MNT`; a kept amount is that cell parsed as a number strictly greater
than zero. A blank, a non-numeric cell, a zero or a negative is dropped and
tallied. The same reader serves the real fetched month and the frozen fixture —
the fixture is written in exactly this shape (one `PRS_REM_MNT` column).

Reads stream, so a gigabyte national month never lands in memory at once. The
fixture is drawn by *systematic* sampling — every k-th valid amount across the
whole file — because a DAMIR month is sorted by its aggregation axes, so the
first N rows would be one biased corner (a department, a care category), not the
month. Systematic sampling is deterministic (no RNG) and spans the file."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from opendata.sources import AMOUNT_COLUMN, DELIMITER

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
    """A systematic draw: the sampled amounts, plus what the whole pass saw."""

    values: list[float]
    total_valid: int
    dropped: int
    stride: int


def parse_amount(cell: str) -> float | None:
    """A DAMIR amount cell -> a positive float, or `None` if it is not one.
    Accepts a `.` or a single `,` decimal separator (French CSVs use `,`); a
    blank, text, a zero, a negative or a non-finite value returns `None`."""
    text = cell.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        if text.count(",") == 1:
            try:
                value = float(text.replace(",", "."))
            except ValueError:
                return None
        else:
            return None
    if value != value or value in (float("inf"), float("-inf")) or value <= 0:
        return None
    return value


def _iter_cells(path: Path) -> Iterator[str]:
    """Yield the `PRS_REM_MNT` cell of every data row, streaming. Raises
    `ValueError` if the file has no such column — a file that is not the
    declared shape refuses; it does not read as an empty slice."""
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=DELIMITER)
        if reader.fieldnames is None or AMOUNT_COLUMN not in reader.fieldnames:
            raise ValueError(
                f"{path.name}: no {AMOUNT_COLUMN!r} column "
                f"(found {reader.fieldnames}); not a DAMIR slice"
            )
        for row in reader:
            yield row.get(AMOUNT_COLUMN, "")


def read_amounts(path: Path) -> Amounts:
    """Read `PRS_REM_MNT`, keeping only positive numbers, dropping and counting
    the rest. Holds the kept amounts in memory — use it on the fixture, not a
    national month (use `systematic_sample` for that)."""
    kept: list[float] = []
    dropped = 0
    for cell in _iter_cells(path):
        amount = parse_amount(cell)
        if amount is None:
            dropped += 1
        else:
            kept.append(amount)
    return Amounts(values=kept, dropped=dropped)


def systematic_sample(path: Path, n: int) -> Sample:
    """Draw N amounts spread across the whole file: two streaming passes, no
    RNG. Pass one counts the valid amounts; pass two keeps every k-th, where
    k = total // N (at least 1). Memory holds only the N kept, never the month.
    A file with N or fewer valid amounts returns them all (stride 1)."""
    if n <= 0:
        raise ValueError(f"sample size must be positive, got {n}")
    total_valid = 0
    dropped = 0
    for cell in _iter_cells(path):
        if parse_amount(cell) is None:
            dropped += 1
        else:
            total_valid += 1
    if total_valid == 0:
        return Sample(values=[], total_valid=0, dropped=dropped, stride=1)
    stride = max(1, total_valid // n)
    kept: list[float] = []
    index = 0
    for cell in _iter_cells(path):
        amount = parse_amount(cell)
        if amount is None:
            continue
        if index % stride == 0 and len(kept) < n:
            kept.append(amount)
        index += 1
    return Sample(values=kept, total_valid=total_valid, dropped=dropped, stride=stride)


def write_fixture(amounts: list[float], path: Path = FIXTURE_CSV) -> None:
    """Write a one-column `PRS_REM_MNT` CSV — the frozen fixture's shape, the
    same shape `read_amounts` reads. Amounts are written at two decimals for a
    byte-stable file. Numbers only: no address, no attribution, no brand."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=DELIMITER)
        writer.writerow([AMOUNT_COLUMN])
        for value in amounts:
            writer.writerow([f"{value:.2f}"])


def freeze_manifest(directory: Path = FIXTURE_DIR) -> None:
    """Write `MANIFEST.sha256` over every file in the fixture directory but the
    manifest itself — the `sha256sum` format the frozen-fixtures test reads."""
    lines = []
    for file in sorted(p for p in directory.glob("*") if p.name != MANIFEST.name):
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        lines.append(f"{digest}  {file.name}")
    (directory / MANIFEST.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
