# BACKING.md — the evidence contract

Plain layer: this table is the promise behind every number in the study. Each
row says which claim we make, which table holds the number, which SQL file
builds that table, where the data came from, and how sure we are (the tag).
If a claim has no row here, it is not in the study. If a row cannot be filled,
the claim is rewritten or marked Pending — never shipped as-is.

Rules (PROJECT_BRIEF.md §8, checked mechanically by `make check-backing`):

- One row per study claim (a chart, a stat, or a sentence with a number).
- Tag is exactly one of **Measured**, **Documented**, **Modeled**, **Pending**
  (PROJECT_BRIEF.md §2.4).
- A Measured or Documented row names its upstream source (a public URL or a
  named open dataset).
- A non-Pending row's SQL file exists under `sql/`. A **Pending** row may name
  a file not built yet — the tag says so. Rows start Pending in Phase 0b and
  flip to Measured / Documented / Modeled in the phase that lands their mart;
  that flip is a Record update in that phase's spec.
- Every `sql/marts/*.sql` is named by at least one row. A mart no claim needs
  is out of scope and is removed.
- Written before code (Phase 0b). Every later phase's work maps to a row.

| Study claim (beat, chart/sentence) | Mart table | SQL file | Upstream source | Tag |
|---|---|---|---|---|
