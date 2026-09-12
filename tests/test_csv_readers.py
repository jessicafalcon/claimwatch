"""Every `csv` reader owns its failure type (code-craft → Error policy; the
LESSONS `traceback-at-boundary` class): the parser's own `csv.Error` — a field
past `csv.field_size_limit()`, no `ValueError` — folds into the one refusal each
reader declares, so a boundary catches its declared set and never a traceback.
One walk over every reader the source packages hold, pinned to the call sites by
an AST scan so a new reader cannot join unwalked; the two DAMIR CLI paths that
had no boundary catch at all get theirs (BACKLOG, "Every `csv` reader but one
maps `ValueError` only…")."""

from __future__ import annotations

import ast
import csv
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from classify.cache import DECISION_COLUMNS, CacheError, read_decisions
from classify.eval.labels_io import LABEL_COLUMNS, LabelError, read_labels
from ingest.parsed import CSV_UNREADABLE, PageShapeError
from ingest.sources import sample_source
from ingest.trustpilot import COLUMNS as TRUSTPILOT_COLUMNS
from ingest.trustpilot import parse as parse_trustpilot
from opendata.fee_split import AMELI_DELIMITER, read_national_families
from opendata.fee_split import FIXTURE_COLUMNS as AMELI_COLUMNS
from opendata.fit import read_name_value_rows
from opendata.slice import AMOUNT_COLUMN, TYPE_COLUMN, read_amounts
from opendata.slice import DELIMITER as DAMIR_DELIMITER
from pipeline import cli
from pipeline.build import (
    ANCHOR_COLUMNS,
    FIXTURE_REVIEW_COLUMNS,
    read_anchors,
    read_fixture,
)
from pipeline.cli import main
from tests import pins
from tests.repo_text import repo_text

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("ingest", "pipeline", "opendata", "classify", "models", "study")
REFUSAL = CSV_UNREADABLE
URL = "https://ca.trustpilot.com/review/exemple-fictif.com?languages=all"
STAMP = "2026-09-04T12:00:00"


@pytest.fixture
def wide_cell() -> Iterator[str]:
    """A cell one character past a narrowed `csv.field_size_limit()`, the limit
    restored afterwards — so every reader, the byte-capped fit artifact's
    included, meets the parser's own error on a small file."""
    previous = csv.field_size_limit(pins.CSV_FIELD_LIMIT_NARROWED)
    try:
        yield "9" * (pins.CSV_FIELD_LIMIT_NARROWED + 1)
    finally:
        csv.field_size_limit(previous)


@dataclass(frozen=True)
class Reader:
    """One `csv` call site: where it is, how to hand it a file whose one data
    row carries `wide`, and the refusal it declares."""

    site: tuple[str, str]  # (path under the repo, enclosing function)
    write: Callable[[Path, str], Path]  # (directory, wide cell) -> the file
    read: Callable[[Path], object]
    refusal: type[Exception]


def _lines(path: Path, header: str, row: str) -> Path:
    path.write_text(header + "\n" + row + "\n", encoding="utf-8")
    return path


def _export(path: Path, wide: str) -> Path:
    """The authorized export's header and one row whose last cell is `wide`."""
    cells = ["x"] * len(TRUSTPILOT_COLUMNS)
    cells[-1] = wide
    return _lines(path, ",".join(TRUSTPILOT_COLUMNS), ",".join(cells))


READERS: tuple[Reader, ...] = (
    Reader(
        ("pipeline/build.py", "_read_csv"),
        lambda d, w: _lines(d / "anchors.csv", ",".join(ANCHOR_COLUMNS), w),
        read_anchors,
        PageShapeError,
    ),
    Reader(
        ("classify/cache.py", "read_decisions"),
        lambda d, w: _lines(
            d / "decisions.csv", ",".join(DECISION_COLUMNS), f"r,v,m,{w}"
        ),
        read_decisions,
        CacheError,
    ),
    Reader(
        ("classify/eval/labels_io.py", "read_labels"),
        lambda d, w: _lines(d / "labels.csv", ",".join(LABEL_COLUMNS), f"r,{w}"),
        read_labels,
        LabelError,
    ),
    Reader(
        ("opendata/slice.py", "_iter_rows"),
        lambda d, w: _lines(
            d / "A202507.csv",
            DAMIR_DELIMITER.join((AMOUNT_COLUMN, TYPE_COLUMN)),
            f"{w};1",
        ),
        read_amounts,
        ValueError,
    ),
    Reader(
        ("opendata/fit.py", "read_name_value_rows"),
        lambda d, w: _lines(d / "claim_cost_fit.csv", "name,value", f"mu,{w}"),
        lambda p: read_name_value_rows(p, ("mu",), "fit"),
        ValueError,
    ),
    Reader(
        ("opendata/fee_split.py", "_iter_rows"),
        lambda d, w: _lines(
            d / "honoraires.csv",
            AMELI_DELIMITER.join(AMELI_COLUMNS),
            f"2024;99;999;x;{w};1",
        ),
        lambda p: read_national_families(p, 2024),
        ValueError,
    ),
    Reader(
        ("ingest/trustpilot.py", "parse"),
        lambda d, w: _export(d / "export.csv", w),
        lambda p: parse_trustpilot(
            p.read_text(encoding="utf-8"), URL, STAMP, sample_source("trustpilot")
        ),
        PageShapeError,
    ),
)


READER_NAMES = ("reader", "DictReader")


class _CsvCallScan(ast.NodeVisitor):
    """Records every call of the `csv` module's `reader`/`DictReader` with its
    enclosing function name, however the module or the name was bound:
    `import csv`, `import csv as c`, `from csv import DictReader [as d]`."""

    def __init__(self) -> None:
        self._funcs: list[str] = []
        self._modules: set[str] = set()  # names bound to the csv module
        self._readers: set[str] = set()  # names bound to csv.reader/DictReader
        self.sites: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "csv":
                self._modules.add(alias.asname or "csv")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "csv":
            for alias in node.names:
                if alias.name in READER_NAMES:
                    self._readers.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._funcs.append(node.name)
        self.generic_visit(node)
        self._funcs.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        via_module = (
            isinstance(func, ast.Attribute)
            and func.attr in READER_NAMES
            and isinstance(func.value, ast.Name)
            and func.value.id in self._modules
        )
        via_name = isinstance(func, ast.Name) and func.id in self._readers
        if via_module or via_name:
            self.sites.append(self._funcs[-1] if self._funcs else "<module>")
        self.generic_visit(node)


def _csv_call_sites(text: str, where: str) -> set[tuple[str, str]]:
    scan = _CsvCallScan()
    scan.visit(ast.parse(text))
    return {(where, func) for func in scan.sites}


def _repo_csv_call_sites() -> set[tuple[str, str]]:
    # rglob, not glob: a future subpackage under one of these is scanned too.
    sites: set[tuple[str, str]] = set()
    for pkg in PACKAGES:
        for path in sorted((ROOT / pkg).rglob("*.py")):
            where = str(path.relative_to(ROOT))
            sites |= _csv_call_sites(repo_text(path), where)
    return sites


def test_the_walk_covers_every_csv_reader_in_the_source_packages():
    """The readers walked below are exactly the `csv` call sites the six
    source packages hold: a new reader fails here until it joins the walk, and
    a reader that went away leaves no stale entry."""
    assert _repo_csv_call_sites() == {r.site for r in READERS}


@pytest.mark.parametrize(
    "source",
    [
        "import csv\n\ndef load(fh):\n    return list(csv.DictReader(fh))\n",
        "import csv\n\ndef load(fh):\n    return csv.reader(fh)\n",
        "import csv as c\n\ndef load(fh):\n    return c.reader(fh)\n",
        "from csv import DictReader\n\ndef load(fh):\n    return DictReader(fh)\n",
        "from csv import reader as r\n\ndef load(fh):\n    return r(fh)\n",
    ],
    ids=["csv.DictReader", "csv.reader", "import as", "from import", "from import as"],
)
def test_the_scan_catches_a_new_csv_reader_however_it_is_imported(source: str):
    assert _csv_call_sites(source, "x.py") == {("x.py", "load")}


def test_the_scan_ignores_a_reader_name_not_bound_to_csv():
    text = "def load(fh):\n    return reader(fh) + DictReader(fh)\n"
    assert _csv_call_sites(text, "x.py") == set()


@pytest.mark.parametrize("reader", READERS, ids=lambda r: ":".join(r.site))
def test_each_reader_folds_the_parsers_error_into_its_declared_refusal(
    reader: Reader, tmp_path: Path, wide_cell: str
):
    """A field past the parser's limit raises `csv.Error` inside the reader,
    and what comes out is the reader's own refusal naming the input — never
    `csv.Error`, which no boundary in the repo catches."""
    path = reader.write(tmp_path, wide_cell)
    with pytest.raises(reader.refusal, match=REFUSAL) as excinfo:
        reader.read(path)
    assert not isinstance(excinfo.value, csv.Error)
    named = path.name if reader.site[0] != "ingest/trustpilot.py" else URL
    assert named in str(excinfo.value)


def test_read_fixture_reads_the_synthetic_rows_through_the_strict_reader():
    rows = read_fixture("synthetic")
    assert len(rows) == pins.RAW_REVIEWS_ROWS
    assert all(tuple(row) == FIXTURE_REVIEW_COLUMNS for row in rows)


def test_sample_damir_refuses_a_month_the_parser_cannot_read(
    capsys, monkeypatch, tmp_path, wide_cell
):
    """`make sample-damir` on a cached month the parser cannot read: one
    refusal line and exit 2 — the boundary catch the path never had."""
    src = _lines(
        tmp_path / "A202507.csv",
        DAMIR_DELIMITER.join((AMOUNT_COLUMN, TYPE_COLUMN)),
        f"{wide_cell};1",
    )
    monkeypatch.setattr(cli, "cache_path", lambda m: src)
    assert main(["sample-damir", "--month=2025-07"]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"refusing: A202507.csv: {REFUSAL}")
    assert "Traceback" not in err


def test_fit_damir_refuses_a_fixture_the_parser_cannot_read(
    capsys, monkeypatch, tmp_path, wide_cell
):
    """`make fit-damir` on a fixture the parser cannot read: the same one line
    and exit 2 (the sibling DAMIR read path, fixed as the class)."""
    fixture = _lines(
        tmp_path / "damir-sample.csv",
        DAMIR_DELIMITER.join((AMOUNT_COLUMN, TYPE_COLUMN)),
        f"{wide_cell};1",
    )
    monkeypatch.setattr(cli, "FIXTURE_CSV", fixture)
    assert main(["fit-damir"]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"refusing: damir-sample.csv: {REFUSAL}")
    assert "Traceback" not in err
