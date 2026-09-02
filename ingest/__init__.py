"""Scrapers and capture archiving (PROJECT_BRIEF.md §4, docs/PLAN.md §5 row 2).

Phase 2 holds one source: the App Store customer-reviews feed. The manners of
every fetch live in `politeness.py`, the only `httpx` import is `fetch.py`, the
declared sources are `sources.py`, and `app_store.py` is the strict parser from
the feed's shape to the eight `raw_reviews` columns. `pipeline/` reads captures
through `app_store.read_captures`; it never imports the fetcher, so a rebuild
touches no network."""
