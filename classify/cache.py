"""The decision cache — what makes the classifier deterministic despite a model.

A language model can answer the same review two ways on two calls. The cache
freezes each decision the first time it is made, keyed by the review, the prompt
version and the model, so every later run reads the cache instead of calling the
model again: the pipeline is a pure function of the reviews, `rules.yaml`, the
prompt version, the model and this file (CLAUDE.md → Deterministic first).

The file is `data/classify/decisions.csv` — gitignored (the cache is
corpus-derived; brief §2.5 keeps the corpus out of git), and text-free: a
`review_id`, the `prompt_version`, the `model`, and one `theme` per row (a review
the model gave two themes is two rows; a review it could not place is one
`unclassified` row). No review body, no brand, no clock — a decision carries no
timestamp, so the cache key holds no time.

It is read strictly, the same shape guard the answer key and the snapshot files
use: the columns must be exactly the four declared, and every theme must be one
of the seven closed labels — a corrupted or hand-edited row refuses, naming the
line, rather than admitting an eighth label. A missing or header-only file is
zero decisions (a fresh clone before any model has run). Writing is idempotent
and order-stable: the file is rewritten in sorted key order, so re-recording the
same decisions leaves a byte-identical file."""

from __future__ import annotations

import csv
from pathlib import Path

from classify.labels import LABEL_SET
from pipeline.warehouse import ROOT

DECISIONS = ROOT / "data" / "classify" / "decisions.csv"
DECISION_COLUMNS: tuple[str, ...] = ("review_id", "prompt_version", "model", "theme")

# A decision is addressed by these three; its value is the tuple of themes.
CacheKey = tuple[str, str, str]


class CacheError(Exception):
    """A decisions.csv row outside the declared shape or the closed label set:
    one line naming the file and the line, never a traceback."""


def read_decisions(path: str | Path = DECISIONS) -> dict[CacheKey, tuple[str, ...]]:
    """The cached decisions as `{(review_id, prompt_version, model): themes}`.
    Rows sharing a key are one decision (its themes, in file order). A missing or
    header-only file is `{}`. A wrong column set, an empty cell or an out-of-set
    theme refuses with `CacheError`, naming the line; so does a file the
    parser cannot read (`csv.Error`, folded — the reader owns its failure
    type)."""
    path = Path(path)
    if not path.is_file():
        return {}
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    out: dict[CacheKey, list[str]] = {}
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if tuple(reader.fieldnames or ()) != DECISION_COLUMNS:
                raise CacheError(f"{where}: columns must be exactly {DECISION_COLUMNS}")
            for i, row in enumerate(reader, 2):
                if None in row or None in row.values():
                    raise CacheError(f"{where}: line {i}: wrong number of cells")
                rid = row["review_id"].strip()
                pv = row["prompt_version"].strip()
                model = row["model"].strip()
                theme = row["theme"].strip()
                required = (
                    ("review_id", rid),
                    ("prompt_version", pv),
                    ("model", model),
                )
                for name, value in required:
                    if not value:
                        raise CacheError(f"{where}: line {i}: field {name!r} is empty")
                if theme not in LABEL_SET:
                    raise CacheError(
                        f"{where}: line {i}: theme {theme!r} is not one of the "
                        f"seven closed labels {tuple(sorted(LABEL_SET))}"
                    )
                out.setdefault((rid, pv, model), []).append(theme)
    except csv.Error as exc:
        raise CacheError(f"{where}: not a CSV the reader can parse ({exc})") from exc
    return {key: tuple(themes) for key, themes in out.items()}


def write_decisions(
    decisions: dict[CacheKey, tuple[str, ...]], path: str | Path = DECISIONS
) -> None:
    """Write the cache to `path`, one row per `(key, theme)`, in sorted
    `(review_id, prompt_version, model, theme)` order — so re-recording the same
    decisions produces a byte-identical file. The parent directory is created if
    missing. The write replaces the file with the full set given, so the caller
    merges old and new before calling (the pipeline reads, extends, writes)."""
    path = Path(path)
    rows = sorted(
        (rid, pv, model, theme)
        for (rid, pv, model), themes in decisions.items()
        for theme in themes
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(DECISION_COLUMNS)
        writer.writerows(rows)
