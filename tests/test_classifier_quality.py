"""The classifier_quality mart (Phase 6b, B2.4): a DDL table fed by Python with
the held-out grades. Its shell is created by `sql/marts/classifier_quality.sql`
in every rebuild; `build.write_classifier_quality` fills it from the gate's
scores. Offline, no key: the rules-only classifier is graded on the synthetic
fold 4, and the mart is deterministic across reruns."""

from __future__ import annotations

from pathlib import Path

import pytest

from classify.eval.gate import ANSWER_KEY, HELDOUT_FOLD, LabelScore, score_heldout
from classify.labels import review_id
from classify.rules import classify as rules_classify
from classify.rules import load_rules
from pipeline.build import (
    ClassifyOutcome,
    classify_step,
    rebuild,
    write_classifier_quality,
)
from pipeline.warehouse import connect, database_for
from tests import pins

pytestmark = pytest.mark.slow  # slow: kept out of the fast edit-loop hook


def _staged_reviews(conn):
    rows = conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    out = []
    for source, external_id, title, body in rows:
        text = "\n".join(p for p in (title, body) if p).strip()
        out.append((review_id(source, external_id), text))
    return out


def _build_and_populate(tmp_path):
    """Rebuild the synthetic warehouse (which creates the empty mart), then grade
    the rules-only classifier on fold 4 and fill the mart — the exact steps the
    CLI runs with no key. Returns a fresh connection to the built db."""
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="synthetic")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    predictions = rules_classify(_staged_reviews(conn), load_rules())
    scores = score_heldout(predictions)
    write_classifier_quality(
        conn,
        scores,
        answer_key=ANSWER_KEY,
        heldout_fold=HELDOUT_FOLD,
        run_id="synthetic",
    )
    return conn


def _columns(conn):
    return tuple(
        r[0]
        for r in conn.execute(
            "select column_name from information_schema.columns "
            "where table_name = 'classifier_quality' order by ordinal_position"
        ).fetchall()
    )


def test_mart_exists_empty_after_rebuild(tmp_path):
    # rebuild alone creates the shell; the CLI classify step fills it, so the
    # table is present but empty after a bare rebuild.
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="t")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        assert _columns(conn) == pins.CLASSIFIER_QUALITY_COLUMNS
        assert (
            conn.execute("select count(*) from classifier_quality").fetchone()[0] == 0
        )
    finally:
        conn.close()


def test_classify_step_writes_no_quality_on_an_ungraded_corpus(tmp_path):
    # A1 (never fake a Measured number): on a corpus the answer key does not cover,
    # classify_step must leave classifier_quality empty, not fill it with all-null
    # Measured rows. `samples` has reviews but no held-out labels, so it grades
    # nothing. Pins the `if graded:` guard in classify_step (a mutation to it
    # survived the rest of the suite — round 1 functionality-tester).
    rebuild("duckdb", "samples", root=tmp_path, run_id="t")
    db = database_for("samples", tmp_path)
    outcome = classify_step(db, "t", cache_path=Path(db).with_name("decisions.csv"))
    assert isinstance(outcome, ClassifyOutcome) and outcome.graded is False
    conn = connect("duckdb", database=db)
    try:
        count = conn.execute("select count(*) from classifier_quality").fetchone()[0]
        assert count == 0
    finally:
        conn.close()


def test_mart_columns_are_the_computed_metric_shape(tmp_path):
    conn = _build_and_populate(tmp_path)
    try:
        cols = _columns(conn)
        assert cols == pins.CLASSIFIER_QUALITY_COLUMNS
        # A computed metric has no address and no capture instant.
        assert "source_url" not in cols and "captured_at" not in cols
    finally:
        conn.close()


def test_one_row_per_scored_label_all_measured(tmp_path):
    conn = _build_and_populate(tmp_path)
    try:
        rows = conn.execute(
            "select label, hits, predicted, actual, precision, recall, "
            " heldout_fold, answer_key, run_id, tag from classifier_quality "
            "order by label"
        ).fetchall()
        assert len(rows) == pins.CLASSIFIER_QUALITY_ROWS  # 6: five themes + positive
        for r in rows:
            assert r[6] == HELDOUT_FOLD  # heldout_fold
            assert r[7] == pins.CLASSIFIER_QUALITY_ANSWER_KEY  # answer_key
            assert r[9] == pins.CLASSIFIER_QUALITY_TAG  # every figure Measured
    finally:
        conn.close()


def test_components_reproduce_the_ratio(tmp_path):
    # precision = hits/predicted, recall = hits/actual, null exactly when the
    # denominator is 0 — a reader can redo the arithmetic from the stored ints.
    conn = _build_and_populate(tmp_path)
    try:
        rows = conn.execute(
            "select hits, predicted, actual, precision, recall from classifier_quality"
        ).fetchall()
        for hits, predicted, actual, precision, recall in rows:
            assert precision == (hits / predicted if predicted else None)
            assert recall == (hits / actual if actual else None)
    finally:
        conn.close()


def test_rules_only_heldout_values_are_pinned(tmp_path):
    conn = _build_and_populate(tmp_path)
    try:
        rows = conn.execute(
            "select label, hits, predicted, actual, precision, recall "
            "from classifier_quality"
        ).fetchall()
        got = {label: (h, p, a, prec, rec) for label, h, p, a, prec, rec in rows}
        assert got == pins.RULES_HELDOUT
    finally:
        conn.close()


def test_mart_column_mapping_under_asymmetry(tmp_path):
    # The synthetic fold-4 rows all have precision == recall, so a precision/recall
    # column swap in the INSERT would be invisible there. Craft an asymmetric score
    # (precision 0.5, recall 1.0) and assert each column carries its own value.
    rebuild("duckdb", "synthetic", root=tmp_path, run_id="t")
    conn = connect("duckdb", database=database_for("synthetic", tmp_path))
    try:
        scores = (
            LabelScore(
                "document-loop",
                hits=1,
                predicted=2,
                actual=1,
                precision=0.5,
                recall=1.0,
            ),
        )
        write_classifier_quality(
            conn,
            scores,
            answer_key=ANSWER_KEY,
            heldout_fold=HELDOUT_FOLD,
            run_id="synthetic",
        )
        row = conn.execute(
            "select hits, predicted, actual, precision, recall from classifier_quality "
            "where label = 'document-loop'"
        ).fetchone()
        assert row == (1, 2, 1, 0.5, 1.0)  # precision != recall, each in its own column
    finally:
        conn.close()


def test_write_is_idempotent_on_one_connection(tmp_path):
    # The inserter clears the table first, so re-populating on the same connection
    # keeps the row count (pins the `delete`, which create-or-replace would mask).
    conn = _build_and_populate(tmp_path)
    try:
        predictions = rules_classify(_staged_reviews(conn), load_rules())
        write_classifier_quality(
            conn,
            score_heldout(predictions),
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


def test_two_rebuilds_identical_mart_rows(tmp_path):
    # The mart is a deterministic function of the predictions and the answer key:
    # two independent rebuilds (no key) yield byte-identical rows.
    first = _build_and_populate(tmp_path / "a")
    second = _build_and_populate(tmp_path / "b")
    try:
        q = "select * from classifier_quality order by label"
        assert first.execute(q).fetchall() == second.execute(q).fetchall()
    finally:
        first.close()
        second.close()
