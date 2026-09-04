"""The labels wall (Phase 5a; docs/PLAN.md:64). The hand-labeled answer key is
read by exactly one package, `classify/eval/`. Every other surface that
participates in classification or the pipeline — the rules and the model call
when they exist (5b, 6), the SQL, the marts, the models, and the rest of the
pipeline — is grepped for a reader of the answer key and must have none. A
classifier that could see the answers it is graded against would make its
scores a lie."""

from __future__ import annotations

from pipeline.warehouse import ROOT

# The tokens a reader of the answer key would carry: the file name, the reader
# module and its symbols. A module that opens the file, imports the reader, or
# names the path trips at least one of these; a docstring about the wall does
# not (the concept is described without these literals, on purpose).
READER_TOKENS = ("labels.csv", "labels_io", "read_labels", "LABELS_CSV")

# Where a classifier or pipeline module could read the answer key from. The one
# legitimate reader, classify/eval/, is excluded; tests, specs and docs may name
# the file freely (they are not the pipeline).
SURFACES = (
    "classify", "pipeline", "sql", "models", "ingest", "dags", "study", "scripts"
)
EXCLUDED = ROOT / "classify" / "eval"


def _source_files():
    for surface in SURFACES:
        base = ROOT / surface
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in (".py", ".sql", ".yaml", ".yml"):
                continue
            if path.is_relative_to(EXCLUDED):
                continue
            yield path


def test_no_reader_of_labels_outside_eval():
    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        hits = [tok for tok in READER_TOKENS if tok in text]
        if hits:
            offenders.append(f"{path.relative_to(ROOT)}: {hits}")
    assert not offenders, (
        "the answer key must be read only by classify/eval/; found references in: "
        + "; ".join(offenders)
    )


def test_the_rules_layer_is_covered_by_the_wall():
    # Phase 5b's rules classifier must be one of the swept surfaces — the wall
    # actively covers classify/rules.py, not incidentally. If the rules ever read
    # the answer key, test_no_reader_of_labels_outside_eval must catch it.
    swept = {path.relative_to(ROOT).as_posix() for path in _source_files()}
    assert "classify/rules.py" in swept
    assert "classify/rules.yaml" in swept


def test_the_model_call_site_is_covered_by_the_wall():
    # Phase 6a's model call site and its cache must be swept surfaces — the model
    # is never shown its own answer key. The whole classify/ tree outside eval/ is
    # swept; assert the new modules are actually in the set.
    swept = {path.relative_to(ROOT).as_posix() for path in _source_files()}
    assert "classify/llm.py" in swept
    assert "classify/cache.py" in swept
    assert "classify/combined.py" in swept


def test_the_one_reader_actually_reads_it():
    # A live wall: the reader package DOES carry the tokens (so the test above is
    # excluding a real reader, not passing on an empty repo).
    reader = (EXCLUDED / "labels_io.py").read_text(encoding="utf-8")
    assert "labels.csv" in reader and "read_labels" in reader
