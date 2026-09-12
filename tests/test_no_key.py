"""The no-key guarantee (Phase 6a; durable, re-run every phase from here on).

Delete the API key and the pipeline still runs end to end: no Anthropic client is
constructed, no network is touched, every review the rules left `unclassified`
stays `unclassified`, and the combined output is exactly the rules-only output.
The whole suite already blocks every socket (conftest `_no_network`), so a test
that passes here also proves nothing reached for the network."""

from __future__ import annotations

import sys

import pytest

from classify.combined import classify_all
from classify.eval.gate import ANSWER_KEY, HELDOUT_FOLD, score_heldout
from classify.labels import UNCLASSIFIED
from classify.llm import make_model_decider, model_available
from classify.rules import classify as rules_classify
from classify.rules import load_rules
from pipeline.build import rebuild, write_classifier_quality
from pipeline.warehouse import connect, database_for
from tests import pins

pytestmark = pytest.mark.slow  # slow: kept out of the fast edit-loop hook


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


def test_no_key_classify_stays_unclassified(monkeypatch, synthetic_conn):
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


def test_no_key_constructs_no_client_and_no_network(monkeypatch, synthetic_conn):
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
    from pipeline import build, cli
    from pipeline.build import rebuild

    # Redirect the classify step's cache (now build.read/write_decisions, called
    # by build.classify_step) to a temp path, so the no-key run writes nothing
    # under the repo's data/. The extra cache_path arg the step passes is ignored.
    cache = tmp_path / "decisions.csv"
    monkeypatch.setattr(
        build, "read_decisions", lambda *a, **k: read_decisions(cache)
    )
    monkeypatch.setattr(
        build, "write_decisions", lambda d, *a, **k: write_decisions(d, cache)
    )

    rebuild("duckdb", "synthetic", root=tmp_path, run_id="t")
    cli._classify_and_print(database_for("synthetic", tmp_path), "synthetic")
    out = capsys.readouterr().out
    assert "not yet classified" in out
    assert "rules only" in out  # the no-key note
    assert "held-out fold 4" in out  # the gate summary rides the same step


def test_no_key_mart_is_rules_only_and_populated(monkeypatch, tmp_path):
    # With no key the classifier is rules-only; the gate scores THOSE predictions
    # and the mart populates honestly (never a faked with-key number).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="synthetic")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        preds, cache = classify_all(
            _reviews(conn),
            rules=load_rules(),
            decide=make_model_decider(),
            decisions={},
        )
        assert cache == {}  # no model decisions with no key
        write_classifier_quality(
            conn,
            score_heldout(preds),
            answer_key=ANSWER_KEY,
            heldout_fold=HELDOUT_FOLD,
            run_id="synthetic",
        )
        rows = conn.execute(
            "select label, hits, predicted, actual, precision, recall "
            "from classifier_quality"
        ).fetchall()
        got = {label: (h, p, a, prec, rec) for label, h, p, a, prec, rec in rows}
        assert got == pins.RULES_HELDOUT
    finally:
        conn.close()


def test_theme_share_shows_unclassified_band(monkeypatch, tmp_path):
    # Central constraint (Phase 7a): with no key the theme-share marts still
    # populate and the `unclassified` band is non-empty — the rules leave
    # ambiguous reviews unplaced, and the marts show them as the gray band, never
    # dropped and never an empty mart. Runs the CLI classify step, which builds
    # the marts.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from classify.cache import read_decisions, write_decisions
    from pipeline import build, cli

    cache = tmp_path / "decisions.csv"
    monkeypatch.setattr(
        build, "read_decisions", lambda *a, **k: read_decisions(cache)
    )
    monkeypatch.setattr(
        build, "write_decisions", lambda d, *a, **k: write_decisions(d, cache)
    )

    rebuild("duckdb", "synthetic", root=tmp_path, run_id="t")
    db = database_for("synthetic", tmp_path)
    cli._classify_and_print(db, "synthetic")
    conn = connect("duckdb", database=db)
    try:
        (band,) = conn.execute(
            "select theme_rows from theme_share_by_segment where label = 'unclassified'"
        ).fetchone()
        assert band == pins.THEME_SHARE_BY_SEGMENT_NOKEY["unclassified"]  # > 0
        band_months = conn.execute(
            "select count(*) from theme_share_by_month where label = 'unclassified'"
        ).fetchone()[0]
        assert band_months >= 1
        tags = {
            r[0]
            for r in conn.execute(
                "select distinct tag from theme_share_by_segment"
            ).fetchall()
        }
        assert tags == {pins.THEME_SHARE_TAG}  # honest rules-only Measured output
    finally:
        conn.close()


def test_no_key_model_marts_are_filled(monkeypatch, tmp_path):
    # The three cost-model marts (Beat 3) compute over the tracked lognormal fit,
    # not the model API — with no key they fill exactly the same. Durable no-key
    # guard from Phase 8a on.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="synthetic")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        for mart, expected in (
            ("cost_model_params", pins.COST_PARAM_ROWS),
            ("cost_model_outputs", pins.COST_OUTPUT_ROWS),
            ("cost_curves", pins.COST_CURVE_ROWS),
        ):
            assert (
                conn.execute(f"select count(*) from {mart}").fetchone()[0] == expected
            )
    finally:
        conn.close()


def test_no_key_sim_marts_are_filled(monkeypatch, tmp_path):
    # The two simulator marts (Beat 4) compute over the tracked lognormal fit,
    # not the model API — with no key they fill exactly the same. Durable no-key
    # guard from Phase 8b on.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="synthetic")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        for mart, expected in (
            ("guardrail_sim", pins.GUARDRAIL_SIM_ROWS),
            ("sla_threshold", pins.SLA_THRESHOLD_ROWS),
        ):
            assert (
                conn.execute(f"select count(*) from {mart}").fetchone()[0] == expected
            )
    finally:
        conn.close()


def test_no_key_scores_call_no_model(monkeypatch, tmp_path):
    # Grading is offline: even with the SDK importable, scoring and writing the
    # mart never touch it — the gate compares stored predictions to the key.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _Boom:
        def __getattr__(self, name):
            raise AssertionError("anthropic was touched while grading")

    monkeypatch.setitem(sys.modules, "anthropic", _Boom())
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="synthetic")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        preds, _ = classify_all(
            _reviews(conn),
            rules=load_rules(),
            decide=make_model_decider(),
            decisions={},
        )
        write_classifier_quality(
            conn,
            score_heldout(preds),
            answer_key=ANSWER_KEY,
            heldout_fold=HELDOUT_FOLD,
            run_id="synthetic",
        )
        assert (
            conn.execute("select count(*) from classifier_quality").fetchone()[0]
            == pins.CLASSIFIER_QUALITY_ROWS
        )
    finally:
        conn.close()
