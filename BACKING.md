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
| B1.1 Hero case: a roughly €340 ER refund on hold for months; "Day N" frozen at the last confirmed date (eventual Documented) | — (documented case) | — | — | Pending |
| B1.2 The studied segment's public rating over time, monthly (Documented from the seeded anchors; Measured once our own captures accrue, Phase 4 — each point carries its own tag) | rating_trend | `sql/marts/rating_trend.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B1.3 Channel gap: ratings on invited channels vs unsolicited platforms (Documented from the seeded anchors; Measured once our own captures accrue, Phase 4 — each point carries its own tag) | channel_gap | `sql/marts/channel_gap.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B1.4 Stat row: one-star share, review counts, response-lag differences (Documented from the seeded anchors; Measured once our own captures accrue, Phase 4 — each point carries its own tag) | platform_stats | `sql/marts/platform_stats.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B2.1 The five-theme taxonomy with paraphrased public examples (eventual Documented) | — (documented examples) | — | — | Pending |
| B2.2 Theme share of negative reviews over time, by segment, via the gated classifier (eventual Measured) | theme_share_by_month | `sql/marts/theme_share_by_month.sql` | — | Pending |
| B2.3 Peer context: public ratings across the market segment (Documented from the seeded anchors; Measured once our own captures accrue, Phase 4 — each point carries its own tag) | peer_ratings | `sql/marts/peer_ratings.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B2.4 Classifier quality: per-theme precision and recall vs hand labels (eventual Measured) | classifier_quality | `sql/marts/classifier_quality.sql` | — | Pending |
| B2.5 Held-claim complaint share, digital-first vs traditional mutuelles (eventual Measured) | theme_share_by_segment | `sql/marts/theme_share_by_segment.sql` | — | Pending |
| B3.1 Cost-model formulas printed next to their output (eventual Modeled) | cost_model_outputs | `sql/marts/cost_model_outputs.sql` | — | Pending |
| B3.2 Fraud saved vs friction cost curves over the flag rate, with the crossover (eventual Modeled) | cost_curves | `sql/marts/cost_curves.sql` | — | Pending |
| B3.3 Sourced defaults: revenue per member, fraud pool, claim volume (eventual Modeled) | cost_model_params | `sql/marts/cost_model_params.sql` | `open-damir` | Pending |
| B3.4 Declared-unsourced parameters as explore-the-range sliders (eventual Modeled) | cost_model_params | `sql/marts/cost_model_params.sql` | — | Pending |
| B4.1 Fix 1 ask once: contacts per stuck claim drop to one, the curves move (eventual Modeled) | guardrail_sim | `sql/marts/guardrail_sim.sql` | — | Pending |
| B4.2 Fix 2 a clock on every hold: the computed SLA threshold (eventual Modeled) | sla_threshold | `sql/marts/sla_threshold.sql` | — | Pending |
| B4.3 Before and after hold durations from the simulator on calibrated synthetic claims (eventual Modeled) | guardrail_sim | `sql/marts/guardrail_sim.sql` | `open-damir` | Pending |
| B4.4 Fix 3 count the mistakes: a false-positive rate per flag rule (eventual Modeled) | — (outcome log) | — | — | Pending |
| B5.1 Determinism facts: one model decision, formulas shown, no untagged number (eventual Measured) | — (repo facts) | — | — | Pending |
| B5.2 Reproducibility: row counts per stage, eval scores, the one rebuild command (eventual Measured) | pipeline_row_counts | `sql/marts/pipeline_row_counts.sql` | — | Pending |
