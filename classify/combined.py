"""The combined classification: the rules decide the clear cases, a language
model decides only what they left `unclassified`, and the two are one table.

`classify_all` is a pure function of the reviews, the loaded rules, the decider
and the cache — no clock, no disk, no network of its own (the caller does the
file I/O around it). It returns rows at the review × theme grain SPEC.md settled
(a review carrying K themes is K rows; a review no rule and no model can place is
exactly one `unclassified` row), sorted by `(review_id, theme)` so a re-run is
byte-identical.

The model sees only the reviews the rules left `unclassified`, and only those not
already in the cache: a warm cache means zero model calls. With no decider (no
key), the unresolved reviews stay `unclassified` — the combined output is exactly
the rules-only output, which is the no-key guarantee (6a). The model's answer is
normalized through the closed set (`classify.llm.normalize`), so even a
misbehaving decider can never introduce an eighth label."""

from __future__ import annotations

from collections.abc import Sequence

from classify.cache import CacheKey
from classify.labels import UNCLASSIFIED
from classify.llm import MODEL, PROMPT_VERSION, Decide, normalize
from classify.rules import classify as rules_classify


def unresolved_ids(rows: Sequence[tuple[str, str]]) -> list[str]:
    """The review ids the rules left `unclassified` — the only reviews the model
    is ever shown. A review is unresolved iff its sole rules row is
    `unclassified` (the three-tier fallback in `classify.rules`)."""
    by_id: dict[str, set[str]] = {}
    for rid, label in rows:
        by_id.setdefault(rid, set()).add(label)
    return [rid for rid, labels in by_id.items() if labels == {UNCLASSIFIED}]


def classify_all(
    reviews: Sequence[tuple[str, str]],
    *,
    rules: dict,
    decide: Decide | None = None,
    decisions: dict[CacheKey, tuple[str, ...]] | None = None,
) -> tuple[list[tuple[str, str]], dict[CacheKey, tuple[str, ...]]]:
    """Classify `(review_id, text)` reviews into sorted `(review_id, theme)` rows,
    combining the rules with the cached/model decisions for the reviews the rules
    left `unclassified`. Returns the rows and the (possibly extended) cache, so
    the caller can persist new decisions. `decide=None` (no key) leaves the
    unresolved reviews `unclassified`."""
    cache = dict(decisions or {})
    rules_rows = rules_classify(reviews, rules)
    unresolved = set(unresolved_ids(rules_rows))

    # Ask the model only for unresolved reviews with no cached decision.
    missing = [
        (rid, text)
        for rid, text in reviews
        if rid in unresolved and (rid, PROMPT_VERSION, MODEL) not in cache
    ]
    if decide is not None and missing:
        for rid, labels in decide(missing).items():
            cache[(rid, PROMPT_VERSION, MODEL)] = normalize(labels)

    rows: list[tuple[str, str]] = []
    for rid, label in rules_rows:
        if rid not in unresolved:
            rows.append((rid, label))  # the rules decided it
    for rid, _text in reviews:
        if rid in unresolved:
            themes = cache.get((rid, PROMPT_VERSION, MODEL), (UNCLASSIFIED,))
            rows.extend((rid, theme) for theme in themes)
    return sorted(rows), cache
