"""The one reader of the hand-labeled answer key, `labels.csv`.

The file is the ground truth the classifier is graded against: `review_id,
theme`, one row per review × theme (a review with two hand-assigned themes is
two rows; a review with none is one `positive` or `unclassified` row — the grain
SPEC.md settled at Beat 2). It carries NO review text — an id and a theme,
nothing a body or a brand could ride in on (the wall's whole point).

The reader is strict at an input the repo grows by hand: the columns must be
exactly `(review_id, theme)`, and every theme must be one of the seven closed
labels (`classify.labels.LABEL_SET`) — an unknown theme refuses the read,
naming the line, rather than admitting an eighth label. A missing or
header-only file is zero rows, never a raise: a fresh clone before anyone
labels, or before the real 300–500 rows are appended offline, still reads
sanely (spec Phase 5a, done-when 6)."""

from __future__ import annotations

import csv
from pathlib import Path

from classify.labels import LABEL_SET
from ingest.parsed import CSV_UNREADABLE
from pipeline.warehouse import ROOT

LABELS_CSV = ROOT / "classify" / "eval" / "labels.csv"
LABEL_COLUMNS: tuple[str, ...] = ("review_id", "theme")


class LabelError(Exception):
    """A labels.csv row outside the declared shape or the closed label set:
    one line naming the file and the line, never a traceback."""


def _label(row: dict[str, str], i: int, where: str) -> tuple[str, str]:
    """One answer-key row as `(review_id, theme)`, both cells present and
    stripped, the theme in the closed label set — or the `LabelError` naming
    the line."""
    if None in row or None in row.values():
        raise LabelError(f"{where}: line {i}: wrong number of cells")
    review_id, theme = row["review_id"].strip(), row["theme"].strip()
    if not review_id:
        raise LabelError(f"{where}: line {i}: field 'review_id' is empty")
    if theme not in LABEL_SET:
        raise LabelError(
            f"{where}: line {i}: theme {theme!r} is not one of the seven closed "
            f"labels {tuple(sorted(LABEL_SET))}"
        )
    return review_id, theme


def read_labels(path: str | Path = LABELS_CSV) -> list[tuple[str, str]]:
    """The hand labels as `(review_id, theme)` rows, each theme validated
    against the seven closed labels. A missing file is zero rows; a header-only
    file is zero rows. A wrong column set, an empty cell or an out-of-set theme
    refuses with `LabelError`, naming the line; so does a file the parser
    cannot read (`csv.Error`, folded — the reader owns its failure type)."""
    path = Path(path)
    if not path.is_file():
        return []
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    out: list[tuple[str, str]] = []
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if tuple(reader.fieldnames or ()) != LABEL_COLUMNS:
                raise LabelError(f"{where}: columns must be exactly {LABEL_COLUMNS}")
            for i, row in enumerate(reader, 2):
                out.append(_label(row, i, where))
    except csv.Error as exc:
        raise LabelError(f"{where}: {CSV_UNREADABLE} ({exc})") from exc
    return out
