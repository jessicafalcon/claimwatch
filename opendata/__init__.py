"""Open-data ingest and the claim-cost fit (Phase 7b). Distinct from `ingest/`
(the review scrapers, which carry the studied insurer's brand) and from Phase
8's `models/` (the cost model and simulator that consume this fit). Open DAMIR
is France's public dataset of aggregated health-insurance reimbursements — no
individuals, no insurer named — so nothing here carries a brand token.

The one place a language model or a clock could sneak onto the data path is not
here: the fit is closed-form arithmetic (`opendata/fit.py`), the slice is a
guarded read of a foreign CSV (`opendata/slice.py`), and the fetch is a plain
bulk download over stdlib `urllib` (`opendata/fetch.py`, developer-run)."""
