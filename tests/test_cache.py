"""The decision cache (Phase 6a): text-free round trip, a warm re-run makes zero
model calls, a prompt/model change is a new key, and a bad row refuses. Offline."""

from __future__ import annotations

import pytest

from classify.cache import (
    DECISION_COLUMNS,
    DECISIONS,
    CacheError,
    read_decisions,
    write_decisions,
)
from classify.combined import classify_all
from classify.labels import UNCLASSIFIED
from classify.llm import MODEL, PROMPT_VERSION
from classify.rules import load_rules
from pipeline.warehouse import ROOT


def test_cache_lives_under_gitignored_data():
    # data/* is gitignored (only data/snapshots/ is tracked), so the cache never
    # enters git — the corpus-derived decisions stay off the repo.
    assert DECISIONS.is_relative_to(ROOT / "data")
    assert not DECISIONS.is_relative_to(ROOT / "data" / "snapshots")


def test_cache_columns_are_text_free():
    assert DECISION_COLUMNS == ("review_id", "prompt_version", "model", "theme")
    assert "text" not in DECISION_COLUMNS and "body" not in DECISION_COLUMNS


def test_cache_round_trip_is_text_free(tmp_path):
    path = tmp_path / "decisions.csv"
    decisions = {
        ("s:2", PROMPT_VERSION, MODEL): ("coverage-price", "document-loop"),
        ("s:1", PROMPT_VERSION, MODEL): ("positive",),
        ("s:3", PROMPT_VERSION, MODEL): (UNCLASSIFIED,),  # a real "model gave up"
    }
    write_decisions(decisions, path)
    assert read_decisions(path) == decisions
    first = path.read_bytes()
    write_decisions(read_decisions(path), path)  # re-record
    assert path.read_bytes() == first  # byte-identical (sorted key order)


def test_missing_and_header_only_are_empty(tmp_path):
    assert read_decisions(tmp_path / "absent.csv") == {}
    header_only = tmp_path / "header.csv"
    header_only.write_text(",".join(DECISION_COLUMNS) + "\n", encoding="utf-8")
    assert read_decisions(header_only) == {}


def test_bad_columns_and_out_of_set_theme_refuse(tmp_path):
    wrong_cols = tmp_path / "wrong.csv"
    wrong_cols.write_text("review_id,theme\ns:1,positive\n", encoding="utf-8")
    with pytest.raises(CacheError):
        read_decisions(wrong_cols)
    bad_theme = tmp_path / "bad.csv"
    bad_theme.write_text(
        "review_id,prompt_version,model,theme\ns:1,v1,m,eighth-label\n",
        encoding="utf-8",
    )
    with pytest.raises(CacheError):
        read_decisions(bad_theme)


class _CountingDecider:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def __call__(self, batch):
        self.calls += 1
        return {rid: self.answer for rid, _ in batch}


def test_warm_rerun_makes_zero_model_calls(synthetic_conn):
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    decider = _CountingDecider(("silent-rejection",))

    rows1, cache1 = classify_all(reviews, rules=rules, decide=decider, decisions={})
    calls_after_cold = decider.calls
    assert calls_after_cold >= 1  # the cold run decided the unresolved reviews

    rows2, cache2 = classify_all(reviews, rules=rules, decide=decider, decisions=cache1)
    assert decider.calls == calls_after_cold  # warm run: no further model calls
    assert rows1 == rows2  # byte-identical rows
    assert cache1 == cache2


def test_prompt_version_or_model_change_is_a_new_key(synthetic_conn):
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    # Seed the cache under an OLD prompt version: the current run must not hit it.
    from classify.combined import unresolved_ids
    from classify.rules import classify as rules_classify

    unresolved = unresolved_ids(rules_classify(reviews, rules))
    stale = {(rid, "old-version", MODEL): ("positive",) for rid in unresolved}
    decider = _CountingDecider((UNCLASSIFIED,))
    classify_all(reviews, rules=rules, decide=decider, decisions=stale)
    assert decider.calls >= 1  # the stale-keyed decisions did not satisfy the lookup


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
