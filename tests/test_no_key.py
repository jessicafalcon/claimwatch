"""The no-key guarantee (Phase 6a; durable, re-run every phase from here on).

Delete the API key and the pipeline still runs end to end: no Anthropic client is
constructed, no network is touched, every review the rules left `unclassified`
stays `unclassified`, and the combined output is exactly the rules-only output.
The whole suite already blocks every socket (conftest `_no_network`), so a test
that passes here also proves nothing reached for the network."""

from __future__ import annotations

import sys

from classify.combined import classify_all
from classify.labels import UNCLASSIFIED
from classify.llm import make_model_decider, model_available
from classify.rules import classify as rules_classify
from classify.rules import load_rules
from pipeline.warehouse import database_for


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


def test_no_key_make_model_decider_is_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert model_available() is False
    assert make_model_decider() is None


def test_no_key_combined_equals_rules_only(monkeypatch, synthetic_conn):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    rows, cache = classify_all(
        reviews, rules=rules, decide=make_model_decider(), decisions={}
    )
    assert rows == sorted(rules_classify(reviews, rules))  # model contributed nothing
    assert cache == {}  # no decisions made


def test_no_key_unresolved_reviews_stay_unclassified(monkeypatch, synthetic_conn):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    from classify.combined import unresolved_ids

    unresolved = set(unresolved_ids(rules_classify(reviews, rules)))
    rows, _ = classify_all(
        reviews, rules=rules, decide=make_model_decider(), decisions={}
    )
    by_id: dict[str, set[str]] = {}
    for rid, label in rows:
        by_id.setdefault(rid, set()).add(label)
    for rid in unresolved:
        assert by_id[rid] == {UNCLASSIFIED}  # never a theme, never positive


def test_no_key_never_touches_anthropic(monkeypatch, synthetic_conn):
    # Even with the SDK importable, the no-key path never accesses it: the decider
    # is None before any `import anthropic` can run.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _Boom:
        def __getattr__(self, name):
            raise AssertionError("anthropic was touched on the no-key path")

    monkeypatch.setitem(sys.modules, "anthropic", _Boom())
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    rows, cache = classify_all(
        reviews, rules=rules, decide=make_model_decider(), decisions={}
    )
    assert cache == {}
    assert rows == sorted(rules_classify(reviews, rules))


def test_no_key_rebuild_classify_step_is_green(monkeypatch, tmp_path, capsys):
    # The classify step `make rebuild` runs: build a synthetic warehouse, then the
    # CLI's classify step, with no key and a temp cache — it completes and prints
    # the 'not yet classified' band, writing nothing under the repo's data/.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from classify.cache import read_decisions, write_decisions
    from pipeline import cli
    from pipeline.build import rebuild

    cache = tmp_path / "decisions.csv"
    monkeypatch.setattr(cli, "read_decisions", lambda: read_decisions(cache))
    monkeypatch.setattr(cli, "write_decisions", lambda d: write_decisions(d, cache))

    rebuild("duckdb", "synthetic", root=tmp_path, run_id="t")
    cli._classify_and_print(database_for("synthetic", tmp_path))
    out = capsys.readouterr().out
    assert "not yet classified" in out
    assert "rules only" in out  # the no-key note
