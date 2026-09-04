"""`make label-sample N=<n>` — a deterministic draw for a human to label, the
review text going only to a gitignored sheet while the tracked answer key stays
text-free (Phase 5a). Offline; the sampler reads a synthetic warehouse built in
a temp dir, never the real corpus."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from classify.eval.labels_io import LABEL_COLUMNS
from pipeline.build import rebuild
from pipeline.cli import main, positive_int
from pipeline.label_sample import SHEET, SHEET_COLUMNS, label_sample
from pipeline.warehouse import ROOT, database_for
from tests import pins


@pytest.fixture
def synthetic_db(tmp_path: Path) -> Path:
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="test")
    return database_for("synthetic", tmp_path)


def _rows(sheet: Path) -> list[dict[str, str]]:
    with sheet.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_sheet_is_byte_identical_on_rerun(synthetic_db: Path, tmp_path: Path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    assert label_sample(10, sheet=a, db=synthetic_db) == 10
    assert label_sample(10, sheet=b, db=synthetic_db) == 10
    assert a.read_bytes() == b.read_bytes()


def test_sheet_draw_order_is_sha256_of_review_id(synthetic_db: Path, tmp_path: Path):
    sheet = tmp_path / "s.csv"
    label_sample(5, sheet=sheet, db=synthetic_db)
    ids = [r["review_id"] for r in _rows(sheet)]
    assert tuple(ids[:3]) == pins.SAMPLE_ORDER_FIRST_3


def test_sample_is_nested_in_n(synthetic_db: Path, tmp_path: Path):
    small, big = tmp_path / "small.csv", tmp_path / "big.csv"
    label_sample(2, sheet=small, db=synthetic_db)
    label_sample(5, sheet=big, db=synthetic_db)
    small_ids = [r["review_id"] for r in _rows(small)]
    big_ids = [r["review_id"] for r in _rows(big)]
    assert big_ids[:2] == small_ids  # a larger N is a superset of a smaller


def test_n_caps_at_corpus_size(synthetic_db: Path, tmp_path: Path):
    sheet = tmp_path / "s.csv"
    written = label_sample(1000, sheet=sheet, db=synthetic_db)
    assert written == pins.SYNTHETIC_REVIEW_IDS  # 39, not 1000
    assert len(_rows(sheet)) == pins.SYNTHETIC_REVIEW_IDS


def test_missing_warehouse_writes_header_only(tmp_path: Path):
    sheet = tmp_path / "s.csv"
    assert label_sample(5, sheet=sheet, db=tmp_path / "nope.duckdb") == 0
    assert sheet.read_text(encoding="utf-8").splitlines() == [",".join(SHEET_COLUMNS)]
    assert _rows(sheet) == []


def test_empty_warehouse_writes_header_only(tmp_path: Path):
    # `ROWS=none` builds stg_reviews but with zero rows: a header-only sheet.
    rebuild("duckdb", "none", root=tmp_path, run_id="test")
    sheet = tmp_path / "s.csv"
    assert label_sample(5, sheet=sheet, db=database_for("none", tmp_path)) == 0
    assert _rows(sheet) == []


def test_labels_csv_has_no_text_column():
    # The wall as two shapes: the sheet carries text, the tracked key does not.
    assert "text" in SHEET_COLUMNS
    assert LABEL_COLUMNS == pins.LABELS_CSV_COLUMNS
    assert "text" not in LABEL_COLUMNS
    assert "body" not in LABEL_COLUMNS and "title" not in LABEL_COLUMNS


def test_sheet_lives_under_gitignored_data(synthetic_db: Path, tmp_path: Path):
    # The real sheet path is under data/ (matched by the gitignored `data/*`
    # rule) and is NOT the one tracked subtree data/snapshots/.
    rel = SHEET.relative_to(ROOT)
    assert rel.parts[0] == "data"
    assert rel.parts[1] != "snapshots"


def test_sheet_carries_the_review_text(synthetic_db: Path, tmp_path: Path):
    sheet = tmp_path / "s.csv"
    label_sample(pins.SYNTHETIC_REVIEW_IDS, sheet=sheet, db=synthetic_db)
    rows = _rows(sheet)
    assert all(r["source_url"].startswith("https://") for r in rows)
    assert any(r["text"].strip() for r in rows)  # the labeler has something to read


def test_positive_int_accepts_a_positive_integer():
    assert positive_int("400", "N") == 400
    assert positive_int("1", "N") == 1


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../x",
        '"; rm -rf x',
        "0",
        "-5",
        "3.5",
        "abc",
        "²",  # superscript two: str.isdigit True, int() raises ValueError
        "٣",  # Arabic-Indic three: str.isdigit True, int() would give 3
    ],
)
def test_n_rejects_empty_path_and_metachar_and_env(bad: str):
    # The CLI validates N as a positive ASCII integer in Python, whatever its
    # origin (command line or an environment-set make variable both reach this
    # guard as the same string); the output path is fixed, never built from N,
    # so a traversal or a metacharacter is just a string that is not an integer.
    # A non-ASCII digit refuses with one line — never a traceback (superscript),
    # never a surprise value (other-script digit).
    assert main(["label-sample", "--n", bad]) == 2
