"""The one model call site (Phase 6a): one place imports anthropic and does so
lazily; the model sees only rules-`unclassified` reviews; a reply is parsed
strictly to the seven closed labels; no clock on the data path. Offline — every
test here runs with no key and no network (the fake decider stands in)."""

from __future__ import annotations

from classify.combined import classify_all, unresolved_ids
from classify.labels import LABEL_SET, POSITIVE, THEMES, UNCLASSIFIED
from classify.llm import (
    MODEL,
    PROMPT_VERSION,
    make_model_decider,
    model_available,
    normalize,
    parse_reply,
)
from classify.rules import classify as rules_classify
from classify.rules import load_rules
from pipeline.warehouse import ROOT

# A tiny corpus: one clear document-loop review, one neutral (nothing matches).
_DOC_LOOP = "on me redemande un document après un autre document justificatif"
_NEUTRAL = "azerty qwerty lorem ipsum"


def _reviews(conn):
    rows = conn.execute(
        "select source, external_id, title, body from stg_reviews"
    ).fetchall()
    from classify.labels import review_id

    out = []
    for source, external_id, title, body in rows:
        text = "\n".join(p for p in (title, body) if p).strip()
        out.append((review_id(source, external_id), text))
    return out


def test_only_llm_imports_anthropic():
    # A language model is called from classify/llm.py and nowhere else.
    offenders = []
    for path in ROOT.rglob("*.py"):
        if path.name == "llm.py" and path.parent.name == "classify":
            continue
        if "/.venv/" in path.as_posix() or "/tests/" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        if "import anthropic" in text or "from anthropic" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"anthropic imported outside classify/llm.py: {offenders}"


def test_anthropic_import_is_lazy():
    # The import is inside the real-call function, not at module top: importing
    # classify.llm (this test file already did) loads no paid SDK, and an offline
    # or no-key run never touches it.
    lines = (ROOT / "classify" / "llm.py").read_text(encoding="utf-8").splitlines()
    top_level = [
        ln for ln in lines if ln.startswith(("import anthropic", "from anthropic"))
    ]
    assert not top_level, "anthropic must not be imported at module top level"
    indented = [ln for ln in lines if ln.lstrip().startswith("import anthropic")]
    assert indented, "the lazy `import anthropic` should exist inside a function"


def test_model_available_reads_the_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert model_available() is False
    assert make_model_decider() is None  # no key → no decider
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    assert model_available() is True
    assert make_model_decider() is not None  # a decider exists (never called here)


def test_reply_outside_the_set_becomes_unclassified():
    # A near-miss must NOT match the nearest label; free text yields unclassified.
    assert parse_reply("document-loop-ish") == (UNCLASSIFIED,)
    assert parse_reply("totally unrelated prose") == (UNCLASSIFIED,)
    assert parse_reply("") == (UNCLASSIFIED,)
    assert parse_reply("eighth-label document-loopy") == (UNCLASSIFIED,)


def test_valid_reply_maps_to_closed_labels():
    assert parse_reply("document-loop") == ("document-loop",)
    # Two themes → both, in THEMES order regardless of reply order.
    assert parse_reply("coverage-price, document-loop") == (
        "document-loop",
        "coverage-price",
    )
    assert parse_reply("positive") == (POSITIVE,)
    assert parse_reply("unclassified") == (UNCLASSIFIED,)
    # Themes win over positive when both are named.
    assert parse_reply("this is document-loop and positive") == ("document-loop",)
    for lab in parse_reply("silent-rejection second-payer support-traction"):
        assert lab in LABEL_SET


def test_normalize_drops_foreign_and_keeps_theme_order():
    assert normalize(["not-a-label", "coverage-price"]) == ("coverage-price",)
    assert normalize([]) == (UNCLASSIFIED,)
    assert normalize(["positive", "unclassified"]) == (POSITIVE,)
    assert normalize(list(THEMES)) == THEMES  # all themes, in order


def test_model_input_is_only_rules_unclassified(synthetic_conn):
    # The decider is handed exactly the ids the rules left unclassified — never a
    # review the rules already decided.
    reviews = _reviews(synthetic_conn)
    rules = load_rules()
    expected = set(unresolved_ids(rules_classify(reviews, rules)))
    seen: set[str] = set()

    def spy(batch):
        seen.update(rid for rid, _ in batch)
        return {rid: (UNCLASSIFIED,) for rid, _ in batch}

    classify_all(reviews, rules=rules, decide=spy, decisions={})
    assert seen == expected
    # And every decided review is genuinely not in the model's input.
    decided = {
        rid for rid, lab in rules_classify(reviews, rules) if lab != UNCLASSIFIED
    }
    assert seen.isdisjoint(decided)


def test_no_clock_on_the_data_path():
    for name in ("llm.py", "cache.py", "combined.py"):
        text = (ROOT / "classify" / name).read_text(encoding="utf-8")
        for banned in ("now(", "current_date", "current_timestamp", "time.time("):
            assert banned not in text, f"{name} touches a clock: {banned}"


def test_cache_key_fields_are_pinned():
    # The cache key is (review_id, prompt_version, model); both constants exist.
    assert isinstance(PROMPT_VERSION, str) and PROMPT_VERSION
    assert isinstance(MODEL, str) and MODEL.startswith("claude-")
