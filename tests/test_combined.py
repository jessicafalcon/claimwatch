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


def test_no_new_mart():
    # 6a adds no mart; classifier_quality is Phase 6b's DDL-fed-by-Python table.
    assert not (ROOT / "sql" / "marts" / "classifier_quality.sql").exists()
    marts = {p.name for p in (ROOT / "sql" / "marts").glob("*.sql")}
    # None of the Beat-2 classifier marts exist yet (they are 6b / Phase 7).
    assert "classifier_quality.sql" not in marts
    assert "theme_share_by_month.sql" not in marts
    assert "theme_share_by_segment.sql" not in marts


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
