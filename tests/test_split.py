"""The deterministic held-out split, `sha256(review_id) % 5` (Phase 5a). No
clock, no randomness, no state — a pure function of the id."""

from __future__ import annotations

import hashlib

from classify.labels import review_id
from classify.split import FOLDS, HELDOUT_FOLD, fold, is_heldout
from tests import pins


def test_fold_is_sha256_mod_5():
    assert FOLDS == pins.SPLIT_FOLDS
    for rid, expected in pins.FOLD_OF.items():
        assert fold(rid) == expected
        # …and it really is sha256 % 5, not some other hash.
        assert fold(rid) == int(hashlib.sha256(rid.encode("utf-8")).hexdigest(), 16) % 5


def test_fold_stable_across_runs():
    ids = [f"app-store:{i}" for i in range(200)]
    assert [fold(i) for i in ids] == [fold(i) for i in ids]


def test_heldout_fold_is_pinned():
    assert HELDOUT_FOLD == pins.HELDOUT_FOLD
    assert is_heldout(next(r for r in pins.FOLD_OF)) == (
        fold(next(r for r in pins.FOLD_OF)) == HELDOUT_FOLD
    )
    # is_heldout agrees with fold for a spread of ids
    for i in range(200):
        rid = f"opinion-assurances:{i}"
        assert is_heldout(rid) == (fold(rid) == HELDOUT_FOLD)


def test_split_is_usable_over_the_corpus(synthetic_conn):
    pairs = synthetic_conn.execute(
        "select source, external_id from stg_reviews"
    ).fetchall()
    ids = [review_id(s, e) for s, e in pairs]
    heldout = [i for i in ids if is_heldout(i)]
    tuning = [i for i in ids if not is_heldout(i)]
    # Both sides non-empty: a held-out set to grade on and folds to tune on.
    assert len(heldout) == pins.SYNTHETIC_HELDOUT_REVIEW_IDS
    assert len(tuning) == pins.SYNTHETIC_REVIEW_IDS - pins.SYNTHETIC_HELDOUT_REVIEW_IDS
    assert heldout and tuning
    # Every fold index is in range.
    assert all(0 <= fold(i) < FOLDS for i in ids)
