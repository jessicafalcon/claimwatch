"""The held-out eval gate — grade the classifier on the fold it never saw.

5b's `precision.py` scores the rules on the four *tuning* folds (a dev
diagnostic). This gate scores the full classifier's predictions on the *held-out*
fold alone (`split.HELDOUT_FOLD`), and it measures recall as well as precision —
the number the study shows (B2.4, the `classifier_quality` mart).

For one label T on the held-out fold: `predicted` is the set of reviews the
classifier gave T, `actual` is the set the answer key marks T, and `hits` is
their overlap. `precision = hits / predicted` (when the classifier says T, how
often it is right); `recall = hits / actual` (of the reviews that truly are T,
how many it caught). The overlap is the shared numerator. A zero denominator
makes the ratio undefined — `None`, shown blank downstream, never faked as 0.

Like `precision.evaluate`, this takes predictions as input — it does not run the
classifier — so it stays a pure function of predictions and labels. It lives in
`classify/eval/` because it reads the answer key (through `labels_io`); nothing
outside this package may (the wall). The classifier is never shown the answers it
is graded against."""

from __future__ import annotations

from dataclasses import dataclass

from classify.eval.labels_io import LABELS_CSV, read_labels
from classify.eval.precision import SCORED_LABELS
from classify.split import HELDOUT_FOLD, is_heldout
from pipeline.warehouse import ROOT

# The ground truth the gate scores against, as the study cites it (BACKING's
# upstream source for B2.4). A path relative to the repo root, so the mart's
# `answer_key` column names the file without a machine-specific prefix.
ANSWER_KEY: str = str(LABELS_CSV.relative_to(ROOT))

__all__ = ["ANSWER_KEY", "HELDOUT_FOLD", "LabelScore", "score_heldout"]


@dataclass(frozen=True)
class LabelScore:
    """One label's held-out grade. `precision = hits/predicted`,
    `recall = hits/actual`, each `None` when its denominator is 0 (0/0 is
    undefined, not 0). `hits`, `predicted` and `actual` are kept so the ratios
    can be redone by hand."""

    label: str
    hits: int  # held-out reviews the classifier gave this label AND the key agrees
    predicted: int  # held-out reviews the classifier gave this label
    actual: int  # held-out reviews the answer key marks this label
    precision: float | None
    recall: float | None


def score_heldout(
    predictions: list[tuple[str, str]],
    *,
    labels: list[tuple[str, str]] | None = None,
) -> tuple[LabelScore, ...]:
    """Grade `predictions` (`(review_id, label)` from the full classifier) against
    the hand answer key, on the held-out fold only. `labels` defaults to the
    tracked answer key; a test may pass its own. Every fold but `HELDOUT_FOLD` is
    dropped from both sides and read nowhere below, so no scored number can depend
    on a tuning-fold review. One `LabelScore` per scored label (the five themes +
    `positive`); `unclassified` is the absence of a decision, not scored."""
    gold = read_labels() if labels is None else labels

    heldout_pred = {(rid, lab) for rid, lab in predictions if is_heldout(rid)}
    heldout_gold = {(rid, lab) for rid, lab in gold if is_heldout(rid)}

    scores: list[LabelScore] = []
    for label in SCORED_LABELS:
        predicted = {rid for rid, lab in heldout_pred if lab == label}
        actual = {rid for rid, lab in heldout_gold if lab == label}
        hits = predicted & actual
        precision = len(hits) / len(predicted) if predicted else None
        recall = len(hits) / len(actual) if actual else None
        scores.append(
            LabelScore(label, len(hits), len(predicted), len(actual), precision, recall)
        )
    return tuple(scores)


def format_gate(scores: tuple[LabelScore, ...]) -> str:
    """The one-line-per-label gate summary `make rebuild` prints under the
    classify summary. A blank ratio (undefined) prints as `n/a`."""
    lines = [f"classifier quality — held-out fold {HELDOUT_FOLD} (precision / recall):"]
    width = max((len(s.label) for s in scores), default=0)
    for s in scores:
        p = f"{s.precision:.2f}" if s.precision is not None else " n/a"
        r = f"{s.recall:.2f}" if s.recall is not None else " n/a"
        lines.append(f"  {s.label:{width}}  {p} / {r}   ({s.hits}/{s.predicted}, {s.hits}/{s.actual})")
    return "\n".join(lines)
