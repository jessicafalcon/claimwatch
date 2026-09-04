"""The closed label set and the review id, both defined once as data.

The classifier may answer only from a fixed list — the five complaint themes of
PROJECT_BRIEF.md §5, plus `positive` and `unclassified` — seven labels, no
eighth (CLAUDE.md → The five contracts, Classification). Membership is a check,
never a coercion: a value outside the set is refused where it is read (the
labels reader in the `eval/` package), not folded into a default. A slug names
the theme by what it means, not by a number, so a labeled row reads on its own.

`review_id` is the stable identity a review carries through classification: the
eval split hashes it, the answer key keys on it, and Phase 6 caches model
decisions by it. `stg_reviews` has no id column — its grain is
`(source, external_id)` — so the id is that pair joined here, in Python, and no
earlier phase's SQL changes (spec Phase 5a, pinned decision 2)."""

from __future__ import annotations

# The five §5 themes, each slug mapping to one theme in the brief. Named by
# meaning (CLAUDE.md → Writing rules), stable — a rename is a data migration.
THEMES: tuple[str, ...] = (
    "document-loop",  # §5.1 claim flagged; document after harder-to-get document
    "silent-rejection",  # §5.2 rejected with no notification; found in the app
    "second-payer",  # §5.3 secondary-coverage claims auto-rejected on first pass
    "support-traction",  # §5.4 chat off the mark, no phone, support cannot unblock
    "coverage-price",  # §5.5 benefit cuts, steering to the shop, premium rises
)
POSITIVE = "positive"
UNCLASSIFIED = "unclassified"

# The seven labels the classifier may write — the closed set. A model reply or a
# hand label outside this is impossible by construction: it is refused, never an
# eighth label (Classification contract).
LABELS: tuple[str, ...] = THEMES + (POSITIVE, UNCLASSIFIED)
LABEL_SET: frozenset[str] = frozenset(LABELS)


def is_label(value: str) -> bool:
    """True iff `value` is one of the seven closed labels."""
    return value in LABEL_SET


def review_id(source: str, external_id: str) -> str:
    """The stable identity of a review: its natural key `(source, external_id)`
    joined as `"{source}:{external_id}"`. Deterministic across runs and
    machines (plain string join, no clock, no hash of provenance), and distinct
    per staged review because `(source, external_id)` is `stg_reviews`' grain. A
    source slug carries no `:` and neither does an external id (a numeric feed
    id, a `OA-…` id or a content hash), so the join is unambiguous."""
    return f"{source}:{external_id}"
