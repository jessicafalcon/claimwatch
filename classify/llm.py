"""The one place a language model is called (CLAUDE.md → Deterministic first).

A language model reads each review the rules could not decide and answers with a
label from the fixed list. It is fenced three ways: it is called from THIS module
and nowhere else (the only `import anthropic` in the repo, imported lazily inside
the real-call function, so an offline or no-key run never loads the paid SDK); it
sees only the reviews `rules.yaml` left `unclassified`; and its reply is parsed
strictly against the seven closed labels — a token outside the set, or an empty
or uncertain reply, becomes `unclassified`, never an eighth label
(`normalize`/`parse_reply`).

It is never required. `model_available()` reads the key from the environment;
with no key, `make_model_decider()` returns `None` and every unresolved review
stays `unclassified` — the pipeline runs end to end and the study shows a gray
"not yet classified" band (the no-key guarantee, proven every phase from 6a on).

It carries no clock on the data path: a decision is a pure function of the review
text, the prompt version and the model, and it is cached by those three
(`classify/cache.py`), so a re-run calls the model only for reviews it has never
decided and the pipeline is deterministic despite a non-deterministic model."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence

from classify.labels import LABEL_SET, LABELS, POSITIVE, THEMES, UNCLASSIFIED

# Pinned constants, both part of the cache key: bumping either invalidates the
# cache by construction (the next run re-decides). MODEL is one current Claude id
# — a single constant to change if a different model is wanted; the study's
# quality figure (B2.4, Phase 6b) is measured against whatever model ran.
MODEL = "claude-opus-5"
PROMPT_VERSION = "v1"
API_KEY_ENV = "ANTHROPIC_API_KEY"

# A decider maps `(review_id, text)` pairs to `{review_id: labels}`; the real one
# calls the model, a test injects a fake. The returned labels are normalized to
# the grain by the combiner, so a decider need not (but the real one does).
Decide = Callable[[Sequence[tuple[str, str]]], dict[str, tuple[str, ...]]]

# The classifier's instruction: the seven labels named by meaning, and the one
# rule that keeps a reply inside the closed set — answer with slugs, or the word
# `unclassified`. The parse is strict regardless, so this only improves recall.
SYSTEM = """You label a French health-insurance review by what it complains about.

Answer with one or more of these exact slugs, separated by commas, and nothing else:
- document-loop: a claim flagged, then asked for document after harder-to-get document
- silent-rejection: rejected with no notification; the customer found out in the app
- second-payer: a secondary-coverage (mutuelle) claim auto-rejected on the first pass
- support-traction: chat off the mark, no phone, support that cannot unblock the case
- coverage-price: benefit cuts, steering to a partner shop, or premium rises
- positive: the review is satisfied or praises the service
- unclassified: none of the above clearly applies

Give every slug that applies. If none clearly applies, answer exactly: unclassified"""

# Tokens are the exact label slugs; a reply is split on anything that is not a
# lowercase letter or hyphen, hyphens are trimmed, and only whole tokens equal to
# a label count — so `document-loop-ish` is NOT `document-loop` (a foreign input
# is refused, never coerced to the nearest label).
_TOKEN_SPLIT = re.compile(r"[^a-z-]+")


def model_available() -> bool:
    """True iff an API key is set in the environment. No key → no model call."""
    return bool(os.environ.get(API_KEY_ENV))


def normalize(labels: object) -> tuple[str, ...]:
    """The grain the classifier writes, from any set of candidate labels: every
    theme that is present (in `THEMES` order), or `(positive,)` if no theme but a
    positive, or `(unclassified,)` otherwise. Anything outside `LABEL_SET` is
    dropped — never an eighth label. Deterministic (theme order fixed)."""
    present = {lab for lab in labels if lab in LABEL_SET}
    themes = tuple(t for t in THEMES if t in present)
    if themes:
        return themes
    if POSITIVE in present:
        return (POSITIVE,)
    return (UNCLASSIFIED,)


def parse_reply(reply: str) -> tuple[str, ...]:
    """A model reply → the closed-set labels it names, normalized to the grain.
    Strict: only whole tokens equal to a label slug are read, so free text or a
    near-miss (`document-loop-ish`) yields `(unclassified,)`, never an invented or
    nearest label."""
    tokens = {t.strip("-") for t in _TOKEN_SPLIT.split(reply.lower()) if t.strip("-")}
    return normalize(lab for lab in LABELS if lab in tokens)


def _call_model(client: object, text: str) -> str:
    """One classification call, returning the reply's text. Kept minimal and
    portable across `anthropic` 1.x: `model`, `max_tokens`, `system`, `messages`.
    The reply is parsed strictly by `parse_reply`, so the model is never trusted
    to stay inside the label set on its own."""
    message = client.messages.create(  # type: ignore[attr-defined]
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    return "".join(
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    )


def make_model_decider() -> Decide | None:
    """The real decider, or `None` when no key is set (the no-key path — the
    caller then leaves every unresolved review `unclassified`). `anthropic` is
    imported lazily HERE, so importing this module, and every offline or no-key
    run, loads no paid SDK. One model call per review; the cache makes re-runs
    free (`classify/cache.py`)."""
    if not model_available():
        return None

    def decide(reviews: Sequence[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
        import anthropic  # lazy: the one SDK import, off the no-key path

        client = anthropic.Anthropic()
        return {rid: parse_reply(_call_model(client, text)) for rid, text in reviews}

    return decide
