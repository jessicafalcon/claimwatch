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
- The rating rows (B1.2, B1.3, B1.4, B2.3) mix three kinds of point, each
  carrying its own tag: the public figures gathered when the study was scoped
  (the *anchors*, Documented, `fixtures/anchors/platform_snapshots_seed.csv`);
  the figures a person read off a page whose terms forbid a robot (Measured,
  `data/snapshots/manual_snapshots.csv`); and our own captures (Measured),
  whose figures the weekly cron records to
  `data/snapshots/fetched_snapshots.csv` — the tracked series — while the full
  captures stay under `data/cache/`, gitignored. An anchor's address is its platform's
  root, not a profile page: a profile address spells the brand and may sit
  only in `ingest/sources.py` (DECISIONS, D1), so a Documented point opens to
  its platform and to PROJECT_BRIEF.md §6, not to a page. An anchor the brief
  gives as a range is stored at the range's midpoint, rounded to the column,
  and a figure the brief does not give is left empty; a placed day or midpoint
  is a placement, not a reading (SPEC.md Beat 1 states the rule). The row's own tag
  stays Documented until the points we measure make the series.

| Study claim (beat, chart/sentence) | Mart table (where the number lives) | SQL file (the query that builds it) | Upstream source (where the data came from) | Tag (what kind of evidence) |
|---|---|---|---|---|
| B1.1 Hero case: a roughly €340 ER refund on hold for months; "Day N" frozen at the last confirmed date (eventual Documented) | — (documented case) | — | — | Pending |
| B1.2 The studied segment's public rating over time, monthly (three kinds of point, each carrying its own tag — see the note above the table) | rating_trend | `sql/marts/rating_trend.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; `data/snapshots/manual_snapshots.csv`; `data/snapshots/fetched_snapshots.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B1.3 Channel gap: ratings on invited channels vs unsolicited platforms (three kinds of point, each carrying its own tag — see the note above the table) | channel_gap | `sql/marts/channel_gap.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; `data/snapshots/manual_snapshots.csv`; `data/snapshots/fetched_snapshots.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B1.4 Stat row: one-star share, review counts, response-lag differences (three kinds of point, each carrying its own tag — see the note above the table) | platform_stats | `sql/marts/platform_stats.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; `data/snapshots/manual_snapshots.csv`; `data/snapshots/fetched_snapshots.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/; https://apps.apple.com/; https://play.google.com/ | Documented |
| B2.1 The five-theme taxonomy with paraphrased public examples (eventual Documented) | — (documented examples) | — | — | Pending |
| B2.2 Theme share among every classified review over time, by segment, via the gated classifier (positive included in the denominator, never a theme bar) | theme_share_by_month | `sql/marts/theme_share_by_month.sql` | https://apps.apple.com/; https://play.google.com/; https://www.opinion-assurances.fr/; https://www.trustpilot.com/ | Measured |
| B2.3 Peer context: public ratings across the market segment (three kinds of point, each carrying its own tag — see the note above the table) | peer_ratings | `sql/marts/peer_ratings.sql` | `fixtures/anchors/platform_snapshots_seed.csv`; https://www.trustpilot.com/; https://www.opinion-assurances.fr/ | Documented |
| B2.4 Classifier quality: per-theme precision and recall vs hand labels, graded on the held-out fold | classifier_quality | `sql/marts/classifier_quality.sql` | `classify/eval/labels.csv` | Measured |
| B2.5 Held-claim complaint share among every classified review, digital-first vs traditional mutuelles | theme_share_by_segment | `sql/marts/theme_share_by_segment.sql` | https://apps.apple.com/; https://play.google.com/; https://www.opinion-assurances.fr/; https://www.trustpilot.com/ | Measured |
| B3.1 Cost-model formulas printed next to their output | cost_model_outputs | `sql/marts/cost_model_outputs.sql` | `open-damir` | Modeled |
| B3.2 Fraud saved vs friction cost curves over the flag rate, with the crossover | cost_curves | `sql/marts/cost_curves.sql` | `open-damir` | Modeled |
| B3.3 Sourced defaults: revenue per member, fraud pool, claim volume | cost_model_params | `sql/marts/cost_model_params.sql` | `open-damir` | Modeled |
| B3.4 Declared-unsourced parameters with their explore-the-range span drawn, styled apart | cost_model_params | `sql/marts/cost_model_params.sql` | — | Modeled |
| B4.1 Fix 1 ask once: contacts per stuck claim drop to one, the curves move | cost_curves | `sql/marts/cost_curves.sql` | `open-damir` | Modeled |
| B4.2 Fix 2 a clock on every hold: the computed hold-length threshold | sla_threshold | `sql/marts/sla_threshold.sql` | `open-damir` | Modeled |
| B4.3 Before and after hold durations from the simulator on calibrated synthetic claims | guardrail_sim | `sql/marts/guardrail_sim.sql` | `open-damir` | Modeled |
| B4.4 Fix 3 count the mistakes: a false-positive rate per flag rule (eventual Modeled) | — (outcome log) | — | — | Pending |
| B5.1 Determinism facts: one place a model decides, the formulas shown next to their output, the closed set of evidence tags every number wears | determinism_facts | `sql/marts/determinism_facts.sql` | `classify/llm.py`; `models/cost_model.py`; `study/model.py` | Measured |
| B5.2 Reproducibility: row counts per pipeline stage, the eval scores (B2.4), the one rebuild command | pipeline_row_counts | `sql/marts/pipeline_row_counts.sql` | `pipeline/build.py` | Measured |

**On the `open-damir` upstream (B3.3, B4.3).** Phase 7b landed that source: a
small, real, brand-free slice of Open DAMIR's reimbursed-amount column
(`fixtures/damir/`, from July 2025) and a lognormal fit computed from it, written
to the tracked `data/damir/claim_cost_fit.csv` (`mu`, `sigma`, the goodness-of-fit
deciles). The slice keeps only the legal Assurance Maladie reimbursement —
`PRS_REM_TYP ∈ {0,1}` (Amendment A1); rows carrying a *part supplémentaire*
(type ≥ 2) are dropped, so the fitted distribution is the claim cost the study
means, not a pool of legal + supplementary parts. Each DAMIR row is an
aggregated per-cell reimbursement total, not a single claim, so the lognormal
approximates the claim-cost distribution rather than measuring it claim by claim
— the honest label Phase 8 carries beside the fit. **B3.3 flipped to Modeled in
Phase 8a**: `cost_model_params` holds the sourced inputs, `mu`/`sigma`/`emp_p50`
among them. The fit's *effect* on the displayed euros — `mean_claim =
exp(mu + sigma²/2)` (with the median cell `emp_p50` printed beside it as the
contrast) and `claims = refunded_eur / mean_claim` — is a `cost_model_outputs`
row, which is why B3.1 and B3.2 also name `open-damir` as their upstream. (When
Phase 9 renders B3.3's headline derived figures it reads those from
`cost_model_outputs`, not `cost_model_params`.)

**What Beat 4 landed (Phase 8b).** The synthetic claims are the same fit read at
a thousand evenly spaced quantiles — a real distribution, synthetic claims: no
individual claim is public — so `guardrail_sim` and `sla_threshold` name
`open-damir` as their upstream too. **B4.1** is the net (fraud minus friction)
curve of `cost_curves` for the baseline and the three toggled scenarios — the
"curves move" as each fix lifts the net line; the hold durations are B4.3's.
**B4.2**'s printed arithmetic is the `loop_days` /
`friction_per_day` / `timer_amount_eur` rows of `cost_model_outputs` at
`baseline`, read into `sla_threshold` as the amount below which a hold that long
is net-negative in expectation. **B4.3** is the before/after hold durations in
`guardrail_sim`. **B4.4 stays Pending**: a false-positive rate per flag rule
needs an outcome log that does not exist.
