"""The labels wall. This package is the ONLY reader of the hand-labeled answer
key, `eval/labels.csv` (spec Phase 5a, central constraint; docs/PLAN.md:64). No
rule file, no model call, no SQL and no mart reads it — a classifier that could
see the answers it is graded against would make its scores a lie. The
labels-isolation invariant is pinned by tests/test_labels_isolation.py, which
greps every other surface for a reader of the file and finds none.

Phase 5a ships `read_labels` (the validating reader) and a header-only
`labels.csv`. The per-theme precision/recall scoring that reads folds through
`classify.split` and writes the `classifier_quality` mart (B2.4) is Phase 5b/6."""
