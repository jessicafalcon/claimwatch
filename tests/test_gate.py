"""The held-out eval gate (Phase 6b): precision and recall on fold 4 alone,
computed from predictions and the answer key. A pure function — it takes
predictions in, it does not run the classifier — so it is pinned on crafted
inputs. Offline; the answer key is passed explicitly, so no file is read here.

Held-out ids below (`r5`, `h3`, `t1`, `t2`) are `sha256(id) % 5 == 4`; tuning ids
(`r1`, `r2`, `r3`) are not. The gate must count only the held-out ones."""

from __future__ import annotations

from classify.eval.gate import LabelScore, score_heldout
from classify.eval.precision import SCORED_LABELS
from classify.split import is_heldout


def _by_label(scores: tuple[LabelScore, ...]) -> dict[str, LabelScore]:
    return {s.label: s for s in scores}


def test_scored_labels_are_the_five_themes_plus_positive():
    scores = score_heldout([], labels=[])
    assert tuple(s.label for s in scores) == SCORED_LABELS
    assert "unclassified" not in {s.label for s in scores}  # absence, not a label


def test_scores_heldout_fold_only():
    # r5, t1 are held out; r1 is a tuning fold. The tuning row must not move any
    # denominator — if it did, document-loop's `predicted` would be 3, not 2.
    assert is_heldout("r5") and is_heldout("t1") and not is_heldout("r1")
    predictions = [
        ("r5", "document-loop"),
        ("t1", "document-loop"),
        ("r1", "document-loop"),  # tuning fold — ignored
    ]
    labels = [
        ("r5", "document-loop"),
        ("t1", "silent-rejection"),
        ("r1", "document-loop"),  # tuning fold — ignored
    ]
    dl = _by_label(score_heldout(predictions, labels=labels))["document-loop"]
    assert dl.predicted == 2  # r5, t1 — not r1
    assert dl.actual == 1  # only r5
    assert dl.hits == 1
    assert dl.precision == 0.5 and dl.recall == 1.0


def test_precision_and_recall_formula():
    predictions = [
        ("r5", "document-loop"),
        ("h3", "document-loop"),
        ("t1", "silent-rejection"),
    ]
    labels = [
        ("r5", "document-loop"),
        ("h3", "silent-rejection"),  # classifier said document-loop — a miss
        ("t2", "document-loop"),  # classifier missed this one
    ]
    by = _by_label(score_heldout(predictions, labels=labels))
    dl = by["document-loop"]
    assert (dl.hits, dl.predicted, dl.actual) == (1, 2, 2)
    assert dl.precision == 0.5 and dl.recall == 0.5


def test_a_crafted_disagreement_scores_below_one():
    # The metric earns its keep: a wrong prediction drops precision below 1.
    predictions = [("r5", "document-loop"), ("h3", "document-loop")]
    labels = [("r5", "document-loop")]  # h3 is not document-loop
    dl = _by_label(score_heldout(predictions, labels=labels))["document-loop"]
    assert dl.precision == 0.5 and dl.precision < 1.0


def test_null_when_denominator_is_zero():
    # A label the classifier never predicted and the key never marks: both
    # denominators are 0 -> both ratios undefined (None, not 0).
    scores = _by_label(
        score_heldout([("r5", "document-loop")], labels=[("r5", "document-loop")])
    )
    empty = scores["coverage-price"]
    assert (empty.predicted, empty.actual) == (0, 0)
    assert empty.precision is None and empty.recall is None
    # Predicted but never true: precision defined (0.0), recall undefined.
    only_pred = _by_label(score_heldout([("r5", "coverage-price")], labels=[]))[
        "coverage-price"
    ]
    assert only_pred.predicted == 1 and only_pred.actual == 0
    assert only_pred.precision == 0.0 and only_pred.recall is None


def test_gate_takes_predictions_not_the_corpus(monkeypatch):
    # With `labels=` given, the gate reads no answer-key file: monkeypatch the
    # reader to explode and confirm it is never called.
    import classify.eval.gate as gate

    monkeypatch.setattr(
        gate,
        "read_labels",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("read")),
    )
    scores = score_heldout([("r5", "positive")], labels=[("r5", "positive")])
    assert _by_label(scores)["positive"].precision == 1.0
