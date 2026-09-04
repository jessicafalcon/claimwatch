"""`make classify-eval` and its scorer (Phase 5b): per-theme precision on the
tuning folds vs pins, the decided share, the held-out fold left untouched, and
the precision formula on a crafted disagreement. Offline; no service, no key."""

from __future__ import annotations

from classify.eval.labels_io import read_labels
from classify.eval.precision import SCORED_LABELS, evaluate
from classify.labels import review_id
from classify.rules import classify, load_rules
from classify.split import HELDOUT_FOLD, is_heldout
from tests import pins


def _predictions(conn) -> list[tuple[str, str]]:
    pairs = conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    reviews = [
        (review_id(s, e), "\n".join(x for x in (t, b) if x)) for s, e, t, b in pairs
    ]
    return classify(reviews, load_rules())


def test_per_theme_precision_matches_pins(synthetic_conn):
    report = evaluate(_predictions(synthetic_conn))
    got = {p.label: (p.hits, p.predicted) for p in report.precisions}
    assert got == pins.RULES_PRECISION
    # Every scored label with a prediction is 1.0 on this clean corpus.
    for p in report.precisions:
        assert p.value == 1.0


def test_decided_share_matches_pins(synthetic_conn):
    report = evaluate(_predictions(synthetic_conn))
    assert report.decided == pins.RULES_DECIDED
    assert report.tuning_reviews == pins.RULES_TUNING_REVIEWS
    assert (
        abs(report.decided_share - pins.RULES_DECIDED / pins.RULES_TUNING_REVIEWS)
        < 1e-9
    )


def test_precision_is_tuning_folds_only(synthetic_conn):
    # A held-out review the rules would mislabel must not lower any precision: the
    # held-out fold is filtered out before scoring.
    predictions = _predictions(synthetic_conn)
    heldout_id = next(rid for rid, _ in predictions if is_heldout(rid))
    poisoned = predictions + [(heldout_id, "coverage-price")]  # a bogus held-out row
    assert evaluate(poisoned).precisions == evaluate(predictions).precisions


def test_heldout_fold_never_read(synthetic_conn):
    # Mutating the held-out fold's labels changes no printed number.
    predictions = _predictions(synthetic_conn)
    clean = read_labels()
    poisoned = [
        (rid, "coverage-price" if is_heldout(rid) else theme) for rid, theme in clean
    ]
    a = evaluate(predictions, labels=clean)
    b = evaluate(predictions, labels=poisoned)
    assert (a.precisions, a.decided, a.tuning_reviews) == (
        b.precisions,
        b.decided,
        b.tuning_reviews,
    )


def test_precision_formula_below_one():
    # Two predictions for label X, one agrees, one disagrees -> precision 0.5.
    # Both ids must be tuning-fold ids so they are scored.
    a, b = _two_tuning_ids()
    predictions = [(a, "document-loop"), (b, "document-loop")]
    labels = [(a, "document-loop"), (b, "silent-rejection")]
    report = evaluate(predictions, labels=labels)
    doc = next(p for p in report.precisions if p.label == "document-loop")
    assert (doc.hits, doc.predicted, doc.value) == (1, 2, 0.5)


def test_precision_is_none_when_nothing_predicted():
    a, _ = _two_tuning_ids()
    report = evaluate([(a, "positive")], labels=[(a, "positive")])
    doc = next(p for p in report.precisions if p.label == "document-loop")
    assert doc.predicted == 0 and doc.value is None  # 0/0 is undefined, not 0


def test_labels_csv_covers_the_synthetic_corpus(synthetic_conn):
    # The committed answer key has one closed-set row per staged review, keyed by
    # the same review ids the corpus produces (so classify-eval can grade it).
    corpus_ids = {
        review_id(s, e)
        for s, e in synthetic_conn.execute(
            "select source, external_id from stg_reviews"
        ).fetchall()
    }
    labelled = read_labels()
    assert {rid for rid, _ in labelled} == corpus_ids
    assert len(labelled) == pins.SYNTHETIC_REVIEW_IDS  # one row per review here


def test_scored_labels_exclude_unclassified():
    from classify.labels import UNCLASSIFIED

    assert UNCLASSIFIED not in SCORED_LABELS
    assert HELDOUT_FOLD == pins.HELDOUT_FOLD


def _two_tuning_ids() -> tuple[str, str]:
    """Two ids that are NOT in the held-out fold, for the formula tests."""
    found: list[str] = []
    i = 0
    while len(found) < 2:
        candidate = f"synthetic:{i}"
        if not is_heldout(candidate):
            found.append(candidate)
        i += 1
    return found[0], found[1]
