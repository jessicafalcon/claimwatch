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
    # Grading is over reviews both classified and labeled (amendment A1). r5, h3,
    # t2 are all classified AND labeled; t2 is a genuine miss — classified as
    # silent-rejection but truly document-loop, so it lowers document-loop recall.
    predictions = [
        ("r5", "document-loop"),
        (
            "h3",
            "document-loop",
        ),  # classified document-loop but truly silent — a false positive
        (
            "t2",
            "silent-rejection",
        ),  # classified silent but truly document-loop — a miss
    ]
    labels = [
        ("r5", "document-loop"),
        ("h3", "silent-rejection"),
        ("t2", "document-loop"),
    ]
    dl = _by_label(score_heldout(predictions, labels=labels))["document-loop"]
    assert (dl.hits, dl.predicted, dl.actual) == (1, 2, 2)
    assert dl.precision == 0.5 and dl.recall == 0.5


def test_a_crafted_disagreement_scores_below_one():
    # The metric earns its keep: a wrong prediction on a LABELED review drops
    # precision below 1. h3 is labeled (silent-rejection), so it is graded.
    predictions = [("r5", "document-loop"), ("h3", "document-loop")]
    labels = [("r5", "document-loop"), ("h3", "silent-rejection")]
    dl = _by_label(score_heldout(predictions, labels=labels))["document-loop"]
    assert dl.precision == 0.5 and dl.precision < 1.0


def test_null_when_denominator_is_zero():
    # r5 is classified coverage-price but truly document-loop (both graded).
    # coverage-price: predicted but never true -> precision 0.0, recall undefined.
    # document-loop: true but never predicted -> precision undefined, recall 0.0.
    # support-traction: neither predicted nor true -> both undefined.
    by = _by_label(
        score_heldout([("r5", "coverage-price")], labels=[("r5", "document-loop")])
    )
    cp = by["coverage-price"]
    assert (cp.predicted, cp.actual) == (1, 0)
    assert cp.precision == 0.0 and cp.recall is None
    dl = by["document-loop"]
    assert (dl.predicted, dl.actual) == (0, 1)
    assert dl.precision is None and dl.recall == 0.0
    st = by["support-traction"]
    assert (st.predicted, st.actual) == (0, 0)
    assert st.precision is None and st.recall is None


def test_uncovered_corpus_grades_nothing():
    # A corpus the answer key does not cover (predictions and labels share no id)
    # grades nothing: every label is undefined, never a garbage 0.0 (amendment A1).
    scores = score_heldout([("r5", "document-loop")], labels=[("h3", "document-loop")])
    for s in scores:
        assert (s.predicted, s.actual, s.hits) == (0, 0, 0)
        assert s.precision is None and s.recall is None


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
