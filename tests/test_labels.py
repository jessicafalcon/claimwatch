"""The closed label set, the stable review id, and the labels reader (Phase
5a). Offline; no service, no key."""

from __future__ import annotations

from pathlib import Path

import pytest

from classify.eval.labels_io import LABEL_COLUMNS, LABELS_CSV, LabelError, read_labels
from classify.labels import LABEL_SET, LABELS, POSITIVE, THEMES, UNCLASSIFIED, review_id
from tests import pins


def test_theme_set_is_the_seven():
    # Exactly seven labels: five themes plus positive and unclassified.
    assert len(LABELS) == pins.LABEL_COUNT
    assert len(THEMES) == pins.THEME_COUNT
    assert LABELS == THEMES + (POSITIVE, UNCLASSIFIED)
    assert LABEL_SET == frozenset(LABELS)
    assert len(LABEL_SET) == pins.LABEL_COUNT  # no duplicate slug
    assert POSITIVE not in THEMES and UNCLASSIFIED not in THEMES


def test_review_id_is_source_and_external_id():
    assert review_id("app-store", "900000001") == "app-store:900000001"
    assert review_id("opinion-assurances", "OA-101") == "opinion-assurances:OA-101"


def test_review_id_stable_and_distinct_over_corpus(synthetic_conn):
    pairs = synthetic_conn.execute(
        "select source, external_id from stg_reviews"
    ).fetchall()
    ids = [review_id(s, e) for s, e in pairs]
    again = [review_id(s, e) for s, e in pairs]
    assert ids == again  # deterministic
    assert len(ids) == pins.SYNTHETIC_REVIEW_IDS
    assert len(set(ids)) == len(ids)  # distinct per staged review


def test_labels_csv_ships_header_only():
    # The tracked answer key is real, text-free, and empty until a human labels.
    with LABELS_CSV.open(encoding="utf-8") as fh:
        first = fh.readline().rstrip("\n")
    assert tuple(first.split(",")) == LABEL_COLUMNS
    assert read_labels() == []


def test_out_of_set_theme_is_refused(tmp_path: Path):
    csv = tmp_path / "labels.csv"
    csv.write_text(
        "review_id,theme\napp-store:1,document-loop\napp-store:2,document-loop-ish\n",
        encoding="utf-8",
    )
    with pytest.raises(LabelError, match="not one of the seven"):
        read_labels(csv)


def test_absent_labels_is_zero_rows(tmp_path: Path):
    assert read_labels(tmp_path / "nope.csv") == []


def test_small_labels_scores_what_exists(tmp_path: Path):
    # A handful of hand labels read back exactly — the basis 5b/6 will score.
    csv = tmp_path / "labels.csv"
    csv.write_text(
        "review_id,theme\n"
        "opinion-assurances:OA-101,document-loop\n"
        "opinion-assurances:OA-101,silent-rejection\n"  # one review, two themes
        "opinion-assurances:OA-106,positive\n",
        encoding="utf-8",
    )
    rows = read_labels(csv)
    assert rows == [
        ("opinion-assurances:OA-101", "document-loop"),
        ("opinion-assurances:OA-101", "silent-rejection"),
        ("opinion-assurances:OA-106", "positive"),
    ]


def test_wrong_columns_refused(tmp_path: Path):
    csv = tmp_path / "labels.csv"
    csv.write_text("review_id,theme,body\nx,positive,leaked\n", encoding="utf-8")
    with pytest.raises(LabelError, match="columns must be exactly"):
        read_labels(csv)


def test_empty_review_id_refused(tmp_path: Path):
    csv = tmp_path / "labels.csv"
    csv.write_text("review_id,theme\n,positive\n", encoding="utf-8")
    with pytest.raises(LabelError, match="'review_id' is empty"):
        read_labels(csv)
