"""The classification layer. Phase 5a lays the trust foundation only: the
closed label set and a stable review id (`labels.py`), the deterministic
held-out split (`split.py`), and the labels wall (`eval/`, the one reader of
the hand-labeled answer key). The rules that read reviews (`rules.yaml`,
`rules.py`) are Phase 5b; the one model call site (`llm.py`) is Phase 6.

Nothing here reads the hand-labeled answer key except the `eval/` package
itself — a rule or a model that could see the answers it is graded against would
make its scores a lie (the labels-isolation invariant, pinned by
tests/test_labels_isolation.py)."""
