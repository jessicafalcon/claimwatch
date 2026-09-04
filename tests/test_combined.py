"""The combined classification (Phase 6a): rules + model at the review × theme
grain, `unclassified` the single fallback, sorted and deterministic, and no mart.
Offline; the model is a fake decider (no key, no network)."""

from __future__ import annotations

from classify.combined import classify_all, unresolved_ids
from classify.labels import THEMES, UNCLASSIFIED
from classify.llm import MODEL, PROMPT_VERSION
from classify.rules import classify as rules_classify
from classify.rules import load_rules
from pipeline.warehouse import ROOT
from tests import pins


def _reviews(conn):
    from classify.labels import review_id

    rows = conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    out = []
    for source, external_id, title, body in rows:
        text = "\n".join(p for p in (title, body) if p).strip()
        out.append((review_id(source, external_id), text))
    return out


def test_no_key_combined_equals_rules_only(synthetic_conn):
    # decide=None (no key): the unresolved reviews stay unclassified, so the
    # combined output is exactly the rules-only output — the no-key guarantee.
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    rows, cache = classify_all(reviews, rules=rules, decide=None, decisions={})
    assert rows == sorted(rules_classify(reviews, rules))
    assert cache == {}  # no decisions made without a decider


def test_undecided_is_one_unclassified_row():
    # A neutral review no rule matches, no model to decide it → exactly one row.
    reviews = [("s:1", "azerty qwerty lorem ipsum")]
    rules = load_rules()
    rows, _ = classify_all(reviews, rules=rules, decide=None, decisions={})
    assert rows == [("s:1", UNCLASSIFIED)]


def test_review_times_theme_grain():
    # A review the rules leave unclassified, the model gives two themes → 2 rows.
    reviews = [("s:1", "azerty qwerty lorem ipsum")]
    rules = load_rules()

    def two_themes(batch):
        return {rid: ("document-loop", "coverage-price") for rid, _ in batch}

    rows, cache = classify_all(reviews, rules=rules, decide=two_themes, decisions={})
    assert rows == [("s:1", "coverage-price"), ("s:1", "document-loop")]  # sorted
    assert cache[("s:1", PROMPT_VERSION, MODEL)] == ("document-loop", "coverage-price")


def test_model_never_adds_an_eighth_label():
    # Even a misbehaving decider is normalized through the closed set.
    reviews = [("s:1", "azerty qwerty lorem ipsum")]
    rules = load_rules()

    def rogue(batch):
        return {rid: ("document-loop-ish", "eighth-label") for rid, _ in batch}

    rows, _ = classify_all(reviews, rules=rules, decide=rogue, decisions={})
    assert rows == [("s:1", UNCLASSIFIED)]  # nothing in the closed set → unclassified


def test_combined_is_sorted_and_deterministic(synthetic_conn):
    reviews = _reviews(synthetic_conn)
    rules = load_rules()

    def fixed(batch):
        return {rid: ("silent-rejection",) for rid, _ in batch}

    rows_a, _ = classify_all(reviews, rules=rules, decide=fixed, decisions={})
    reversed_reviews = list(reversed(reviews))
    rows_b, _ = classify_all(reversed_reviews, rules=rules, decide=fixed, decisions={})
    assert rows_a == sorted(rows_a)  # sorted
    assert rows_a == rows_b  # order of input reviews does not matter


def test_rebuild_twice_identical_classified_rows(synthetic_conn):
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    rows1, _ = classify_all(reviews, rules=rules, decide=None, decisions={})
    rows2, _ = classify_all(reviews, rules=rules, decide=None, decisions={})
    assert rows1 == rows2


def test_every_review_appears_and_labels_are_closed(synthetic_conn):
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    rows, _ = classify_all(reviews, rules=rules, decide=None, decisions={})
    from classify.labels import LABEL_SET

    assert {rid for rid, _ in rows} == {rid for rid, _ in reviews}  # no review dropped
    assert all(label in LABEL_SET for _, label in rows)


def test_no_key_synthetic_outcome_matches_pins(synthetic_conn):
    # The no-key (rules-only) combined outcome over the full corpus, pinned.
    from classify.labels import POSITIVE

    reviews = _reviews(synthetic_conn)
    rows, _ = classify_all(reviews, rules=load_rules(), decide=None, decisions={})
    theme_rows = sum(1 for _, label in rows if label in THEMES)
    positive = sum(1 for _, label in rows if label == POSITIVE)
    unclassified = sum(1 for _, label in rows if label == UNCLASSIFIED)
    assert len(reviews) == pins.CLASSIFY_NOKEY_REVIEWS
    assert theme_rows == pins.CLASSIFY_NOKEY_THEME_ROWS
    assert positive == pins.CLASSIFY_NOKEY_POSITIVE
    assert unclassified == pins.CLASSIFY_NOKEY_UNCLASSIFIED


def test_combined_writes_no_mart():
    # combined.py stays Python-only: the combined classification is a value, not
    # a table. The marts fed from it (classifier_quality in 6b, the theme-share
    # marts in 7a) are written by the CLI classify step, never by the combiner —
    # classify_all does no database write at all.
    import inspect

    import classify.combined as combined

    assert "execute(" not in inspect.getsource(combined)
    marts = {p.name for p in (ROOT / "sql" / "marts").glob("*.sql")}
    assert {
        "classifier_quality.sql",
        "theme_share_by_month.sql",
        "theme_share_by_segment.sql",
    } <= marts


def test_unresolved_ids_are_exactly_the_all_unclassified_reviews():
    rows = [
        ("a", "document-loop"),
        ("b", UNCLASSIFIED),
        ("c", "positive"),
        ("d", UNCLASSIFIED),
    ]
    assert set(unresolved_ids(rows)) == {"b", "d"}
    # A review with a theme AND (impossibly) unclassified is not unresolved.
    assert unresolved_ids([("e", "document-loop"), ("e", UNCLASSIFIED)]) == []
    assert THEMES  # sanity: themes exist
