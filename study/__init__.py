"""The study surface (Phase 9): the static HTML export of The Friction Ledger.

`study/export.py` renders one self-contained HTML file from the marts and
`models/cost_model.py::FORMULAS` — inline SVG, no CDN, no external asset, no
render timestamp — so `make study` writes byte-identical bytes on a re-run and
CI can diff the committed baseline. The Metabase dashboard (a later, non-CI
demonstration) and the README are separate sub-phases; this package is the
permanent, CI-checkable artifact the others read alongside (DECISIONS decision
3; brief §4.4)."""
