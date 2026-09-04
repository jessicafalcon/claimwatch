"""The rules layer: hand-written patterns that decide the clear cases.

A rule reads a review's text and `classify/rules.yaml` and tags what the review
is about — nothing else. It never reads the hand-labeled answer key; that read
stays inside the `classify/eval/` package, so the rules cannot see the labels
they are graded against (the 5a wall). The output is a pure function
of the reviews and the pattern file: same corpus, same rows, in the same order,
on every machine — no clock, no randomness, no reliance on dict iteration order.

The label of every emitted row is one of the seven closed labels
(`classify.labels.LABEL_SET`): a group in `rules.yaml` keyed by anything but the
five §5 themes or `positive` refuses the load, so an eighth label is impossible
by construction. A review is scored against every theme group; each match is one
`(review_id, theme)` row (the review × theme grain SPEC.md settled at Beat 2). A
review that matches no theme is `positive` if a positive pattern matches,
otherwise `unclassified` — one fallback row, the model's to decide in Phase 6.

Matching folds accents and case (NFKD, drop combining marks, casefold) on both
the text and the pattern, so `refus` matches `refusé` and the synthetic corpus's
unaccented text. A pattern matches at a WORD START — `\b` then the pattern — so
`bot` matches `bot` and `bots` but not `rabotées`, and `chat` matches `chat` but
not `achat`: word-boundary matching, not naive substring, so a short token does
not fire on an unrelated word (the substring bug precision would otherwise
catch). The matching lives here in Python, never in SQL — that is what keeps the
SQL portable (CLAUDE.md → The five contracts, Portability)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import yaml

from classify.labels import POSITIVE, THEMES, UNCLASSIFIED, is_label
from pipeline.warehouse import ROOT

RULES_YAML = ROOT / "classify" / "rules.yaml"

# The labels a rule group may be keyed by: the five themes and `positive`.
# `unclassified` is the fallback, never a group — you do not write patterns for
# "no pattern matched" — so it is not an allowed key.
RULE_LABELS: tuple[str, ...] = THEMES + (POSITIVE,)


class RuleError(Exception):
    """A `rules.yaml` outside the declared shape or the closed label set: one
    line naming the file and what is wrong, never a traceback."""


def _fold(text: str) -> str:
    """Lower-case, accent-folded form for matching: NFKD, drop the combining
    marks, casefold. Deterministic and identical across platforms."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def _compile(folded_pattern: str) -> re.Pattern[str]:
    """A pattern matches at a word start: `\\b` then the literal folded pattern.
    So `bot` matches `bot`/`bots` but not `rabotees`, and `piece` matches
    `piece`/`pieces` but not `crepiece`. `re.escape` keeps the pattern a literal,
    never a user-authored regex (a rules.yaml `.*` is matched, not run)."""
    return re.compile(r"\b" + re.escape(folded_pattern))


def load_rules(path: str | Path = RULES_YAML) -> dict[str, tuple[re.Pattern[str], ...]]:
    """Load `rules.yaml` as `{label: compiled word-start patterns}`, strictly.
    Every key must be one of `RULE_LABELS` (a theme or `positive`) — a key
    outside the closed set, including `unclassified`, refuses the load naming it.
    Every value must be a non-empty list of non-empty strings; patterns are
    folded and compiled once here. A missing file, a non-mapping document, an
    unknown key, or an empty pattern refuses with `RuleError`."""
    path = Path(path)
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if not path.is_file():
        raise RuleError(f"{where}: no such rules file")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise RuleError(f"{where}: top level must be a mapping of label to patterns")
    rules: dict[str, tuple[re.Pattern[str], ...]] = {}
    for label, patterns in doc.items():
        if not is_label(label) or label not in RULE_LABELS:
            raise RuleError(
                f"{where}: {label!r} is not a rule label; a group may be keyed only "
                f"by a theme or 'positive' {RULE_LABELS} — never an eighth label"
            )
        if not isinstance(patterns, list) or not patterns:
            raise RuleError(f"{where}: {label!r} must map to a non-empty list")
        compiled: list[re.Pattern[str]] = []
        for pat in patterns:
            if not isinstance(pat, str) or not pat.strip():
                raise RuleError(
                    f"{where}: {label!r} has an empty or non-string pattern"
                )
            compiled.append(_compile(_fold(pat)))
        rules[label] = tuple(compiled)
    return rules


def themes_for(text: str, rules: dict[str, tuple[re.Pattern[str], ...]]) -> list[str]:
    """The labels a single review's text earns, in `RULE_LABELS` order (theme
    order, then `positive`): every theme whose patterns match, or `[positive]`
    if no theme matched but a positive pattern did, or `[unclassified]` if
    nothing matched. Never an empty list, never a label outside the closed set."""
    folded = _fold(text)
    matched = [
        label
        for label in THEMES
        if any(rx.search(folded) for rx in rules.get(label, ()))
    ]
    if matched:
        return matched
    if any(rx.search(folded) for rx in rules.get(POSITIVE, ())):
        return [POSITIVE]
    return [UNCLASSIFIED]


def classify(
    reviews: Iterable[tuple[str, str]],
    rules: dict[str, tuple[re.Pattern[str], ...]],
) -> list[tuple[str, str]]:
    """Classify `(review_id, text)` pairs into `(review_id, label)` rows, one per
    review × matched theme (a review matching K themes is K rows; a review
    matching none is one `positive` or `unclassified` row). The result is sorted
    by `(review_id, label)`, so it is byte-identical on re-run regardless of the
    order the reviews arrived in — a pure function of the reviews and `rules`."""
    rows: list[tuple[str, str]] = []
    for review_id, text in reviews:
        for label in themes_for(text, rules):
            rows.append((review_id, label))
    return sorted(rows)
