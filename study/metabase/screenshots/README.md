# Screenshots

The demonstration screenshots live here, captured over `ROWS=synthetic` so every
review shown is a hand-written fake — **synthetic fixture data, not a study
finding**. Because the drill view carries only the non-text allowlist
(`review_id, theme, rating, review_date, segment, source` — never `body`,
`title` or `source_url`), no screenshot can show raw review text or a brand
address.

Capturing them is a developer step (it needs Docker and a running Metabase, which
CI does not have) — see [`../DEMONSTRATION.md`](../DEMONSTRATION.md) for the walk.
