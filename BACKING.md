# BACKING.md — the evidence contract

This table is the promise behind every number in the study. Each row says what
we claim, where the number lives, the exact query that builds it (so anyone
can recompute it), where the data came from, and what kind of evidence stands
behind it: measured by us, documented from a public source, modeled by
arithmetic we show, or pending more data. If a claim has no row here, it is
not in the study. If a row cannot be filled, the claim is rewritten or marked
Pending — never published as-is.

**How a row is filled in — for the data team.** `make check-backing` enforces
every rule below except the last sentence, which is editorial (PROJECT_BRIEF.md
§8):

- One row per study claim (a chart, a stat, or a sentence with a number). The
  claim cell starts with a row id `B<beat>.<n>` (for example `B2.3`);
  `SPEC.md` panels cite that id, never a `make` target.
- Tag is exactly one of the bare words **Measured**, **Documented**,
  **Modeled**, **Pending** (PROJECT_BRIEF.md §2.4).
- A Measured or Documented row names its source in a declared shape, each
  `;`-separated part being exactly one of: a URL (`https://…`, no spaces), a
  markdown link to such a URL, or a backticked dataset name of two or more
  lowercase segments joined by `-`, `_`, `.` or `/` (`` `open-damir-2026-01` ``).
  `TBD`, `?`, `—`, `` `TBD` `` or prose is not a source.
- Every SQL path given resolves under `sql/`; "no file yet" is a blank cell or
  `—`. A non-Pending row's file exists. A **Pending** row may name a file not
  built yet — the tag says so. Rows start
  Pending in Phase 0b and flip to Measured / Documented / Modeled in the phase
  that lands their mart; that flip is a Record update in that phase's spec.
- Every `sql/marts/*.sql` is named by at least one row. A mart no claim needs
  is out of scope and is removed.
- Cells never contain `|` (write "or"). Written before code (Phase 0b); every
  later phase's work maps to a row.

| Study claim (beat, chart/sentence) | Mart table (where the number lives) | SQL file (the query that builds it) | Upstream source (where the data came from) | Tag (what kind of evidence) |
|---|---|---|---|---|
