"""Open-data ingest and the two tracked open-data artifacts. Distinct from
`ingest/` (the review scrapers, which carry the studied insurers' brands) and
from `models/` (the cost model and simulator that consume what lands here).
Open DAMIR is France's public dataset of aggregated health-insurance
reimbursements and data.ameli's `honoraires` table is what liberal
practitioners billed by profession — no individuals, no insurer named — so
nothing here carries a brand token.

The one place a language model or a clock could sneak onto the data path is not
here: the fit is closed-form arithmetic (`opendata/fit.py`), the fee split is
two sums and a division (`opendata/fee_split.py`), each slice is a guarded read
of a foreign CSV (`opendata/slice.py`, `opendata/fee_split.py`), and the one
fetch is a plain bulk download over stdlib `urllib` (`opendata/fetch.py`,
developer-run; data.ameli is a hand download, its robots file honoured)."""
