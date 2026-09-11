"""The Metabase demonstration (Phase 9g): the review-level drill over the
reader's own rebuild, developer-run and non-CI (PROJECT_BRIEF.md §4.4 "Full
(demonstration)", §90).

Two offline, CI-checkable pieces plus a developer-run live step:
 - `export.py` copies the marts Metabase reads into a gitignored SQLite file,
   through stdlib `sqlite3` — Metabase reads it with its built-in SQLite driver,
   no third-party DuckDB driver JAR (DECISIONS → Phase 9g).
 - `apply.py` provisions the dashboard from `config.yaml` over the HTTP API,
   idempotently (upsert by name); `--dry-run` builds the request bodies with no
   network and no credentials.
 - the live `docker compose up` + `apply` + screenshots are developer-run; the
   screenshots are captured over `ROWS=synthetic` and captioned as fixture data.

No review text or per-review brand address travels: `review_drill` carries the
non-text allowlist only, the sole text is `study/paraphrases.yaml` (B2.1)."""
