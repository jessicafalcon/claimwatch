"""Grade the rules layer against the hand labels — on the tuning folds only.

Precision for a label is: of the reviews the rules gave that label, the fraction
the hand labels agree with — how often the rule is right when it fires. We score
only the four tuning folds (`sha256(review_id) % 5 != HELDOUT_FOLD`), the reviews
Phase 5b is allowed to look at. The held-out fold is never read here: it is kept
untouched for Phase 6's gate, which also measures recall and writes the
`classifier_quality` mart (B2.4). 5b reports precision and the share the rules
could decide, not recall.

This module lives inside `classify/eval/` because it reads the answer key
(through `labels_io`); nothing outside this package may (the wall). It takes the
rules' predictions as input — it does not run the rules — so the scorer stays a
pure function of predictions and labels, easy to pin."""

from __future__ import annotations

from dataclasses import dataclass

from classify.eval.labels_io import read_labels
from classify.labels import POSITIVE, THEMES, UNCLASSIFIED
from classify.split import HELDOUT_FOLD, is_heldout

# The labels precision is reported for: the five themes and `positive`.
# `unclassified` is the absence of a decision, not a prediction to score.
SCORED_LABELS: tuple[str, ...] = THEMES + (POSITIVE,)


@dataclass(frozen=True)
class Precision:
    """One label's tuning-fold precision: `hits / predicted`, or `None` when the
    rules made no prediction for it in the tuning folds (0/0 is undefined, not 0)."""

    label: str
    hits: int  # rules said this label AND the hand labels agree, on tuning reviews
    predicted: int  # rules said this label, on tuning reviews
    value: float | None


@dataclass(frozen=True)
class Report:
    """The rules layer graded on the tuning folds."""

    precisions: tuple[Precision, ...]
    decided: int  # tuning reviews the rules placed in a theme or `positive`
    tuning_reviews: int  # tuning reviews in all
    heldout_fold: int

    @property
    def decided_share(self) -> float:
        return self.decided / self.tuning_reviews if self.tuning_reviews else 0.0


def evaluate(
    predictions: list[tuple[str, str]],
    *,
    labels: list[tuple[str, str]] | None = None,
) -> Report:
    """Grade `predictions` (`(review_id, label)` rows from the rules) against the
    hand labels, on the tuning folds only. `labels` defaults to the tracked
    answer key; a test may pass its own. Every review id in `predictions` counts
    toward the tuning total (each review gets at least one row); the held-out
    fold's reviews and labels are filtered out and never consulted."""
    gold = read_labels() if labels is None else labels

    # Restrict both sides to the tuning folds. The held-out fold is dropped here
    # and read nowhere below, so no printed number can depend on it.
    tuning_pred = {(rid, lab) for rid, lab in predictions if not is_heldout(rid)}
    tuning_gold = {(rid, lab) for rid, lab in gold if not is_heldout(rid)}
    tuning_ids = {rid for rid, _ in tuning_pred}

    precisions: list[Precision] = []
    for label in SCORED_LABELS:
        predicted = {rid for rid, lab in tuning_pred if lab == label}
        hits = predicted & {rid for rid, lab in tuning_gold if lab == label}
        value = len(hits) / len(predicted) if predicted else None
        precisions.append(Precision(label, len(hits), len(predicted), value))

    decided = {rid for rid, lab in tuning_pred if lab != UNCLASSIFIED}
    return Report(
        precisions=tuple(precisions),
        decided=len(decided),
        tuning_reviews=len(tuning_ids),
        heldout_fold=HELDOUT_FOLD,
    )


def format_report(report: Report) -> str:
    """The `make classify-eval` printout: one line per scored label with its
    tuning-fold precision, then the decided share, then the held-out note."""
    lines = [
        "rules classifier — per-theme precision on the tuning folds "
        f"(fold != {report.heldout_fold}):"
    ]
    width = max(len(p.label) for p in report.precisions)
    for p in report.precisions:
        shown = f"{p.value:.2f}" if p.value is not None else " n/a"
        lines.append(f"  {p.label:{width}}  {shown}   ({p.hits}/{p.predicted})")
    lines.append(
        f"decided share: {report.decided}/{report.tuning_reviews} reviews the rules "
        f"placed in a theme or positive ({report.decided_share:.2f})"
    )
    lines.append(
        f"held-out fold {report.heldout_fold} reserved for Phase 6's gate "
        "(precision and recall there; not scored here)"
    )
    return "\n".join(lines)
