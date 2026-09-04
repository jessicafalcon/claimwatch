"""The rules layer (Phase 5b): the closed set at load, determinism, the review ×
theme grain, the word-start match, and the strict parse of rules.yaml. Offline;
no service, no key, no answer key (the rules never read it)."""

from __future__ import annotations

from pathlib import Path

import pytest

from classify.labels import LABEL_SET, POSITIVE, THEMES, UNCLASSIFIED, review_id
from classify.rules import (
    RULE_LABELS,
    RuleError,
    classify,
    load_rules,
    themes_for,
)


def test_rule_labels_are_the_five_themes_and_positive():
    # A group may be keyed only by a theme or `positive`; `unclassified` is the
    # fallback, never a rule group.
    assert RULE_LABELS == THEMES + (POSITIVE,)
    assert UNCLASSIFIED not in RULE_LABELS
    assert set(RULE_LABELS) <= LABEL_SET


def test_shipped_rules_load_and_key_only_closed_labels():
    rules = load_rules()
    assert rules  # the shipped file is non-empty
    assert set(rules) <= set(RULE_LABELS)  # no key outside the closed rule set


def test_labels_are_the_closed_seven_over_the_corpus(synthetic_conn):
    rules = load_rules()
    pairs = synthetic_conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    reviews = [
        (review_id(s, e), "\n".join(x for x in (t, b) if x)) for s, e, t, b in pairs
    ]
    rows = classify(reviews, rules)
    assert rows
    assert all(label in LABEL_SET for _, label in rows)  # never an eighth label


def test_out_of_set_rule_key_refuses_load(tmp_path: Path):
    bad = tmp_path / "rules.yaml"
    bad.write_text("document-loop-ish:\n  - foo\n", encoding="utf-8")
    with pytest.raises(RuleError, match="not a rule label"):
        load_rules(bad)


def test_unclassified_is_not_a_rule_key(tmp_path: Path):
    # `unclassified` is the fallback; it may not be a rule group.
    bad = tmp_path / "rules.yaml"
    bad.write_text("unclassified:\n  - foo\n", encoding="utf-8")
    with pytest.raises(RuleError, match="not a rule label"):
        load_rules(bad)


def test_strict_parse_of_rules_yaml(tmp_path: Path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(RuleError, match="no such rules file"):
        load_rules(missing)

    not_a_map = tmp_path / "list.yaml"
    not_a_map.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(RuleError, match="must be a mapping"):
        load_rules(not_a_map)

    empty_list = tmp_path / "empty.yaml"
    empty_list.write_text("positive: []\n", encoding="utf-8")
    with pytest.raises(RuleError, match="non-empty list"):
        load_rules(empty_list)

    empty_pat = tmp_path / "blank.yaml"
    empty_pat.write_text("positive:\n  - '  '\n", encoding="utf-8")
    with pytest.raises(RuleError, match="empty or non-string"):
        load_rules(empty_pat)


def test_rules_are_idempotent(synthetic_conn):
    rules = load_rules()
    pairs = synthetic_conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    reviews = [
        (review_id(s, e), "\n".join(x for x in (t, b) if x)) for s, e, t, b in pairs
    ]
    first = classify(reviews, rules)
    second = classify(list(reversed(reviews)), rules)  # order in must not matter
    assert first == second  # sorted output, a pure function
    assert first == sorted(first)  # stable (review_id, label) order


def test_review_times_theme_grain():
    rules = load_rules()
    # A review written to match two theme groups (document + support) is two rows.
    two = themes_for("on me reclame un document et le support ne repond pas", rules)
    assert "document-loop" in two and "support-traction" in two
    assert UNCLASSIFIED not in two and POSITIVE not in two
    rows = classify(
        [("r1", "on me reclame un document; le support ne repond pas")], rules
    )
    assert [label for _, label in rows] == sorted(["document-loop", "support-traction"])


def test_no_match_is_one_unclassified_row():
    rules = load_rules()
    assert themes_for("texte totalement neutre xyz", rules) == [UNCLASSIFIED]
    rows = classify([("r1", "texte totalement neutre xyz")], rules)
    assert rows == [("r1", UNCLASSIFIED)]


def test_positive_only_when_no_theme_matched():
    rules = load_rules()
    # A warm word alone -> positive.
    assert themes_for("service rapide et impeccable", rules) == [POSITIVE]
    # A warm word next to a complaint -> the theme, not positive.
    mixed = themes_for("remboursement rapide mais on redemande un document", rules)
    assert mixed == ["document-loop"]
    assert POSITIVE not in mixed


def test_word_start_match_not_naive_substring():
    rules = load_rules()
    # `bot` (support) must not fire on `rabotees` (a coverage word); the review is
    # coverage-price only. This is the substring bug the word-start match kills.
    labels = themes_for("garanties rabotees d'annee en annee", rules)
    assert labels == ["coverage-price"]
    assert "support-traction" not in labels
    # `chat` (support) must not fire on `achat`.
    assert "support-traction" not in themes_for("un achat malheureux", rules)


def test_patterns_are_literals_not_regex(tmp_path: Path):
    # A rules.yaml pattern with a regex metacharacter is matched literally, never
    # run: `a.b` matches the text `a.b`, not `axb` — the `.` is a dot, not a
    # wildcard (re.escape). Patterns are word-start-anchored, so this one starts
    # with a word char.
    f = tmp_path / "rules.yaml"
    f.write_text("positive:\n  - 'a.b'\n", encoding="utf-8")
    rules = load_rules(f)
    assert themes_for("note axb ici", rules) == [UNCLASSIFIED]  # . is not a wildcard
    assert themes_for("note a.b ici", rules) == [POSITIVE]  # matches the literal


def test_no_new_mart():
    # Pattern-matching lives in rules.yaml/Python; 5b adds no SQL mart.
    from pipeline.warehouse import ROOT

    marts = {p.name for p in (ROOT / "sql" / "marts").glob("*.sql")}
    assert marts == {
        "channel_gap.sql",
        "peer_ratings.sql",
        "platform_stats.sql",
        "rating_trend.sql",
        # classifier_quality lands in 6b (DDL fed by Python, not by the rules).
        "classifier_quality.sql",
        # the theme-share marts land in 7a (SQL over stg_classified_reviews).
        "theme_share_by_month.sql",
        "theme_share_by_segment.sql",
    }
