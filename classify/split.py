"""The deterministic held-out split (docs/PLAN.md §4 decision 4, §5 5a).

To check whether a classifier can be trusted, some hand-labeled reviews are
hidden from it while it is built and tuned, then it is graded only on those
hidden ones — a test with questions the student never saw. The fold a review
lands in is a pure function of its id, `sha256(review_id) % 5`: the same review
lands in the same fold on every machine and every run, which a coin toss or a
stored shuffle could not promise. Four folds are the tuning set Phase 5b's
rules may look at; one — `HELDOUT_FOLD` — is held out for Phase 6's gate.

No clock, no randomness, no state on disk: `fold` is the whole mechanism."""

from __future__ import annotations

import hashlib

FOLDS = 5
# The one fold held out for the Phase 6 eval gate; the other four tune the
# rules in Phase 5b. A pinned constant, not a runtime choice (tests/pins.py).
HELDOUT_FOLD = 4


def fold(review_id: str) -> int:
    """The fold `0..FOLDS-1` a review belongs to: `sha256(review_id) % 5`, a
    pure function of the id. The digest is taken over the id's UTF-8 bytes, so
    the fold is identical on macOS and Linux."""
    digest = hashlib.sha256(review_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % FOLDS


def is_heldout(review_id: str) -> bool:
    """True iff the review is in the held-out fold (Phase 6's gate reads it;
    Phase 5b's tuning never does)."""
    return fold(review_id) == HELDOUT_FOLD
