# The Friction Ledger — Project Brief

This is the master document for building this project. Every Claude Code session should read this file first. It contains the full scope, the rules, the architecture, and the build phases. Nothing outside this file is needed to understand the project.

**This file is repo-safe.** It never names a specific company as the target of the study, and neither should any code, comment, commit message, or document in this repo. The study covers a market segment (French digital-first health insurance), with individual insurers appearing only as factual, sourced data points.

---

## 1. What this project is

**One sentence:** A public-data study of why health-insurance refunds get stuck — where every chart drills down to its raw evidence, every formula is printed next to its output, and every assumption is either sourced or clearly labeled as a guess.

**The full objective, in three verbs:**

1. **Quantify** how automated fraud controls at digital health insurers erode customer trust — using customers' own public words (reviews), classified and counted.
2. **Project** the business cost of that erosion as claim volume scales, with a deterministic model anyone can recompute by hand.
3. **Design** a set of lightweight, deployable guardrails that keep the fraud savings while capping the damage to legitimate customers.

**The deliverable** is a study (a dashboard + written narrative) sitting on top of a working data pipeline. The study is the surface; the pipeline is what makes every sentence in it defensible. The pipeline only exists to feed the study — any work that does not surface in the study does not belong in this repo.

**The hypothesis to test (not to prove):** held-claim complaints ("my refund is blocked, they keep asking for more documents") are growing as a share of negative reviews at digital-first insurers as their claim automation scales. If the data says otherwise, the study says otherwise. The pipeline is theme-agnostic; letting the data overrule the hypothesis is a feature.

---

## 2. Core principles (read before every session)

### 2.1 Deterministic first — always

This is the project's number one technical rule.

- Rules, SQL, and arithmetic decide everything that can be decided deterministically.
- AI/ML appears in **exactly one place**: classifying review text that the deterministic rules layer could not decide. Nowhere else.
- The AI's output is never trusted by default. It passes an evaluation gate (scored against hand-labeled data) before any chart uses it.
- **Graceful degradation test:** if the AI API key is deleted, the pipeline must still run end to end. Ambiguous reviews get labeled "unclassified" and the study shows a visible gray band instead of breaking.
- The cost model and the guardrail simulator are pure formulas. No fitted models, no black boxes. Every formula is displayed next to its output.

Why: trust is the bottleneck. If a reader has to take our word for a number, the study failed. Deterministic parts can be recomputed by hand; that is what makes them trustworthy by default.

### 2.2 Simple and elegant beats complex

- Every tool and every component must earn its maintenance cost. If it doesn't, remove it.
- The stack is the target team's stack, used minimally: **Python, plain SQL, Airflow (one small DAG), Snowflake (with a DuckDB fallback), Metabase.** No dbt, no ORM, no vector store, no fine-tuning, no cloud VMs.
- No dbt because at ~8 SQL models plain SQL is clearer. Say this in the README — knowing when NOT to use a tool is part of the point.
- No AWS/GCP. Scheduling is GitHub Actions cron (free, permanent, public run history). Storage is tiny. Compute is minutes on a laptop.
- Nothing load-bearing sits on a free trial. Snowflake trial is a demonstration only; DuckDB is the permanent path. One config flag switches between them; the SQL is written once, portable.

### 2.3 Plain English everywhere — without hiding the rigor

- **Two-layer writing:** every document section and every dashboard panel opens with 2–3 sentences a non-technical person fully understands. Technical detail goes below, clearly signposted. If the plain layer can't be written, the section isn't understood well enough yet.
- **Name things by what they mean, not what they are.** The metric is "days a legitimate claim spends blocked," not `fp_hold_duration_p90`. The dashboard tab is "What customers complain about," not "Classification Output." Table and column names follow the same spirit.
- **Banned words** in the README and study: orchestration, leverage, robust, scalable, cutting-edge, LLM-powered (in headlines), state-of-the-art, seamless. Use instead: "runs every night," "handles new reviews without redoing old work," "a language model reads each review and tags what it's about."
- **One glossary, ten terms max** (claim, hold, flag, false positive, first-pass rejection, second payer, etc.), each defined in one sentence with an everyday example.
- **The elevator test:** the repo's one-line description must work at a dinner table.
- **Rigor stays visible.** Simple language never means removing the validation, the sensitivity analysis, or the bias checks. They live one layer down, plainly written, under headings like "How we made sure the numbers are trustworthy." Simplicity in presentation, not in method.

### 2.4 Every number is provenance-labeled

Four evidence tags run through the entire study. Every figure carries exactly one:

- **Measured** — verified public data we captured ourselves (with source URL and capture timestamp).
- **Documented** — sourced individual reports (public reviews), paraphrased, linked.
- **Modeled** — deterministic output, formulas and assumptions shown right next to it.
- **Pending** — honest placeholder for what only more data can produce. Never fake a number to fill a chart.

Model parameters follow one rule with nothing in between: **every default is either sourced (with citation) or visibly declared unsourced** ("no public source exists; explore the range" — shown as a differently-styled slider).

### 2.5 Neutrality and fairness

- The repo describes a sector phenomenon, never an exposé of one company. Company-level findings are stated factually ("held-claim complaints appear at digital-first insurers at N× the rate of traditional mutuelles"), never editorially ("Company X traps its customers").
- Review quotes are paraphrased or quoted minimally, always linked to their public source. No personal data is reproduced.
- The scrape is for analysis; publish aggregated results and code, not the raw review corpus.

---

## 3. The study — the final deliverable

Five beats, told from the customer's chair. The customer is the protagonist; the technology appears only where the story needs credibility.

### Beat 1 — People are telling us what's wrong, in public, by the thousands
- Hero: one documented case — a parent's ~€340 emergency-room refund put on hold pending extra documents, publicly reported unresolved for months. Show "Day N — claim on hold," where N is frozen at the **last publicly confirmed date** (never a live counter ticking to today; we can't verify daily). Tag: Documented.
- Chart: the studied segment's public rating trend over time, from our own `platform_snapshots` time series (seeded with verified historical anchors, see §6). Tag: Measured.
- Chart: the channel gap — ratings on channels the company controls/solicits vs. unsolicited platforms. Tag: Measured.
- Stat row: one-star share on independent platforms, review counts, company response lag differences. Tag: Measured.
- Key nuance to state honestly: unsolicited platforms are negatively self-selected samples (companies that stop inviting reviews drift down). The score decline is partly a sampling choice. Naming this bias is part of the study.

### Beat 2 — The complaints have a shape
- The taxonomy (5 themes, see §5) with paraphrased documented examples. Tag: Documented.
- **The chart the pipeline exists to produce:** theme share of negative reviews over time, per insurer / per segment (digital-first vs traditional). Tag: Measured (via the gated classifier). Until real, it's tagged Pending — never faked.
- Peer context: public ratings across the market segment. Tag: Measured.
- Every theme bar must drill through to the underlying review excerpts (Metabase drill-through). Audit trail, not citation.
- Classifier quality (per-theme precision/recall vs hand labels) is displayed **inside the study**, next to the charts it feeds.

### Beat 3 — What a wrongly held claim costs
- The deterministic cost model. All formulas printed above the chart. Sliders for every assumption. Sourced defaults where public anchors exist; "unsourced — explore the range" styling where they don't.
- The one chart that matters: fraud € saved vs. friction € cost, as curves over the flag rate, with a "you are here" marker. Where the curves cross, each extra flag destroys more value than it recovers.
- Business context to explain in plain words: in business-to-business insurance, one employee stuck in a document loop complains to HR, and HR decides renewals. Friction cost compounds through that channel.
- Tag: Modeled.

### Beat 4 — Three small fixes, no rebuild required
The elegant answer is not a better fraud model. It is a cost function wrapped around the existing one. Each fix is boring on purpose:
1. **Ask for everything once.** A deterministic rule table computes the complete document list for a claim type + flag reason, requested in one message. Kills the serial document loop. Pure lookup logic.
2. **Put a clock on every hold.** Every held claim gets a timer. Past the threshold: small low-risk claims auto-release ("pay now, audit after"); large ones auto-escalate to a human. The threshold is computed from the Beat 3 model, not guessed — the study shows the arithmetic.
3. **Count the mistakes.** Every hold ends as fraud-confirmed or released-clean. Logging that outcome per flag rule yields a false-positive rate per rule — the metric the system otherwise lacks. The same event stream fixes silent rejections for free (it triggers a status notification).
- The guardrail simulator (on synthetic claims calibrated to real public cost distributions) shows before/after hold durations and moves the Beat 3 curves visibly. Tag: Modeled.

### Beat 5 — How this was built, and where the rigor lives
- Deterministic backbone, AI at the edges — stated plainly, with the checkable facts: "1 place where a model makes a decision," "100% of formulas displayed next to outputs," "0 numbers without a source or a Modeled label."
- The reproducibility section: DAG diagram, row counts per stage, eval scores, and the one command that rebuilds everything from raw data.

**Delivery formats:** Metabase dashboard (drill-throughs, reading the marts) + a static HTML export of the study (shareable, permanent, no Docker needed to view) + the README telling the same five beats in prose.

---

## 4. Architecture

```
 Review platforms      Open health data      Company disclosures
 (unsolicited voices)  (claim cost distros)  (revenue, fraud savings)
        \                     |                      /
         \                    v                     /
          +--------->  One Airflow DAG  <----------+
                       scrape -> load_raw -> clean -> classify -> publish
                              |
                              v
                  Warehouse (Snowflake OR DuckDB, one flag)
                   raw  ->  staging  ->  marts
                 (as-scraped, (clean,      (study-ready
                  provenance)  deduped)     metrics)
                              |
             +----------------+----------------+
             v                                 v
     Deterministic models              The study
     (cost model, guardrail sim)  ->   (Metabase + HTML export)
```

### 4.1 The classifier trust gate (the only non-deterministic point)

```
 New review --> Rules first (versioned YAML patterns) --> Theme label (clear cases, no model)
                     |
                     v  (only what rules could not decide)
               LLM labeler --> Eval gate (scored vs hand labels) --> Theme label
```

- Rules decide the clear cases deterministically. The LLM sees only the ambiguous remainder.
- The eval gate compares outputs against a held-out slice of the hand-labeled set; per-theme precision/recall is written to a mart table so the study can display it.
- If the LLM is unavailable: ambiguous cases become "unclassified," the pipeline still completes, the study shows the gray band.

### 4.2 Repo layout (the structure teaches the system)

```
friction-ledger/
├── PROJECT_BRIEF.md            # this file
├── SPEC.md                     # frozen study structure: 5 beats, exact chart list
├── BACKING.md                  # claim -> table -> SQL file -> source (see §8)
├── CLAUDE.md                   # standing rules for every Claude Code session (distilled from §2)
├── dags/friction_ledger.py     # the one DAG: 5 linear tasks, fits on a screen
├── ingest/                     # Python scrapers + platform snapshot capture
├── sql/staging/                # plain .sql, one file per table
├── sql/marts/
├── classify/rules.yaml         # deterministic patterns, versioned
├── classify/eval/labels.csv    # hand-labeled ground truth (300–500 reviews)
├── models/cost_model.py        # formulas mirrored 1:1 from the study
├── models/guardrail_sim.py     # SLA timer on calibrated synthetic claims
├── study/                      # Metabase config + static HTML export
├── .github/workflows/weekly.yml# Actions cron: scheduled scrape + snapshot commits
└── Makefile                    # `make rebuild` = full pipeline from raw, one command
```

### 4.3 Cross-cutting trust layer (properties, not a box)

- **Idempotency:** every task re-runs without duplicating. Raw is append-only with provenance columns (source, source_url, captured_at, run_id). Staging dedupes on natural keys. Verify by running twice and diffing row counts.
- **Contracts:** lightweight checks between layers — row counts reconcile, ratings within 1–5, no future dates — failing loudly in the DAG, never silently in a chart.
- **Lineage:** BACKING.md maps every study claim to its SQL file and source; Metabase drill-throughs make the map clickable.

### 4.4 Run modes

- **Portable (default, permanent):** DuckDB + `make rebuild`. Anyone clones the repo and gets data-to-dashboard on a laptop, forever, no accounts.
- **Full (demonstration):** Snowflake + Airflow scheduling. Run once, screenshot, keep configs. Same SQL, different connection string.
- **Scheduling in practice:** GitHub Actions weekly cron runs the scrape and commits new snapshots. Public, timestamped run history in the repo — the schedule itself becomes displayed evidence. Airflow remains the at-company-scale orchestration shown in the DAG file.

---

## 5. The complaint taxonomy (classification target)

Five themes. Documented, paraphrased seed examples exist for each (from public reviews, 2025–2026):

1. **The document loop** — claim flagged; document requested; once sent, a new harder-to-obtain document requested; repeat. Reviewers describe feeling exhausted into giving up. Example: a ~€340 ER claim stuck for months despite follow-ups.
2. **Silent rejections** — no notification when a claim is rejected; customers discover it by checking the app. Yet satisfaction-survey emails arrive after a complaint is resolved.
3. **Second-payer failures** — customers using the insurer as secondary coverage report systematic first-pass rejections: the automated reader can't parse another insurer's statement, or chokes when there is no public-insurance counterpart.
4. **Support without traction** — chat perceived as AI answering "off the mark"; no phone line (callback only); support unable to unblock what the claims system holds.
5. **Coverage & price frustration** — benefit cuts, steering to the insurer's own shop, premium increases. Real, but conventional insurance friction — kept separate so it doesn't pollute the systems-failure signal.

Plus: **positive** and **other/unclassified**. A review can carry multiple themes.

---

## 6. Verified anchor data points (seed + validation set)

These are real, sourced public figures gathered during scoping. They seed `platform_snapshots`, validate early pipeline output, and appear in the study as Documented figures marked as seeded (our own later captures are Measured — Phase 3a, decision D3). Each is stored with its source and, where this section gives one, the day it was read. SPEC.md's Beat 1 gives the rule for the rest: a figure dated only to a month, a season or a span, or not dated at all, is placed on a day; a figure given here as a range is stored at its midpoint; a figure this section does not give is left empty. A placed day or midpoint is a placement, not a reading (`fixtures/anchors/`). A rebuild loads them as stored and does not check them against the live page — our own later captures land beside them as Measured.

- Trustpilot France profile of the studied digital-first insurer: ~4.2/5 on 524 reviews (early 2025; then 75% five-star, 18% one-star) → 3.8/5 on 840 reviews (Sept 2025) → 3.9/5 on 975 reviews (June 2026). International profile: ~1,066 reviews (Aug 2026). Platform flags "no recent history of review invitations." Company answered ~76–84% of negative reviews, typical response time 1–2 weeks.
- Opinion Assurances: 534 reviews, ~23.1% one-star, company response rate 82%, response delay ~1.5 days.
- Company-published satisfaction (the channel-gap contrast): App Store 4.9/5 (~5,000 reviews, Sept 2024), Google 4.5/5 (~765 reviews), member NPS ~70, HR-team NPS ~50, "92% satisfied" (May 2025).
- Peer Trustpilot snapshots (2025–2026): traditional mutuelles ~4.4–4.6 (1k–5k reviews), other traditional insurers ~2.7–3.8, digital challenger ~3.1.
- Scale anchors for the cost model (public disclosures): 1M+ members; €800M+ annual recurring revenue (→ ~€800 revenue per member per year — a sourced anchor for customer value); €350M+ claims refunded per year; ~2M claim documents received per year; document-parsing automation ~50% (end 2023) with a 75% target; ~€4M fraud savings (2024) via ML scoring + anomaly detection + manual investigation.
- Documented compliance-hold justification (public company reply on a review platform, early 2026): certain treatments trigger compliance attention; extra documents are requested; justified by fraud costing "billions per year" sector-wide.

A complaint wave about compliance holds is visible in public reviews starting early 2026 — the time window the classifier's trend chart should examine closely.

---

## 7. The deterministic cost model (Beat 3 spec)

Pure arithmetic. Mirror these formulas 1:1 between `models/cost_model.py` and the study display.

```
flagged        = claims × flag_rate
false_pos      = flagged × fp_share
fraud_saved    = fraud_pool × (1 − e^(−k × flag_rate))      # diminishing returns: worst fraud caught first; k ≈ 8, stated as an assumption
friction_cost  = false_pos × (contacts × cost_per_contact + churn_prob × customer_value)
net            = fraud_saved − friction_cost
```

Parameter sourcing (the rule from §2.4 — sourced or declared unsourced, nothing in between):

- `customer_value` — **sourced**: revenue per member per year from public ARR / member count (~€800).
- `fraud_pool` — **sourced**: anchored on published fraud savings (~€4M/2024), presented as a lower bound.
- `claims` volume — **sourced**: derivable from published refund totals (~€350M/yr) and average claim sizes from open public-health reimbursement data (Open DAMIR / data.ameli distributions).
- `cost_per_contact` — sourced from published customer-service benchmarks if a citable one is found; otherwise declared unsourced.
- `fp_share`, `churn_prob`, `contacts` per stuck claim — **declared unsourced**: no public source exists; sliders styled differently, labeled "explore the range."

Guardrail toggle (recomputes the same formulas): one-shot documents ⇒ contacts → 1; hold timer ⇒ churn_prob halved. Constants and effects displayed, labeled illustrative. The SLA threshold recommendation is **computed** ("at these parameters, holds beyond N days on claims under €X are net-negative in expectation"), with the arithmetic visible.

The guardrail simulator draws synthetic claims from cost distributions fitted to real public reimbursement data (Open DAMIR: monthly CSVs of all French health-insurance reimbursements since 2009, 55 variables; data.ameli for practitioner-level fees). Clearly label: real distributions, synthetic claims — no individual-level claims data is publicly available (it is legally restricted), and the study says so.

---

## 8. BACKING.md — the evidence contract

Format: one row per study claim.

```
| Study claim (beat, chart/sentence) | Mart table | SQL file | Upstream source | Tag |
```

Rules:
- Written in Phase 0, before code. Every later phase's work must map to a row; work that maps to no row is out of scope.
- If a claim can't be backed, it gets rewritten or tagged Pending — never shipped as-is.
- This file is the scoping tool: it is how "the whole project" stays one project.

---

## 9. Build phases (one phase = one Claude Code session = one reviewable diff)

*Build note (2026-09-01): Phases 0, 3 and 5 are each split in two — 0a
machinery / 0b contracts, 3a snapshots and polite sources / 3b Trustpilot, 5a
label sample / 5b rules — see `docs/PLAN.md` §5. Each phase's
contract is its spec in `specs/`; the numbering below is otherwise unchanged.*

Feed each session: this file + SPEC.md + BACKING.md + CLAUDE.md + the current phase goal. Not the whole history. End every phase by writing its "done when" as an actual test or make target.

**Phase 0 — Skeleton and contracts (no code).**
Repo structure; write SPEC.md (freeze the 5 beats and exact chart list), BACKING.md (full claim table), CLAUDE.md (standing rules distilled from §2).
Done when: all three files exist and agree with this brief.

**Phase 1 — Schema and the empty warehouse.**
Raw and staging DDL with provenance columns in this phase; each mart lands with its upstream in a later phase (see BACKING.md), so Phase 1 has no mart. `make rebuild` scaffold runs against DuckDB with zero rows.
Done when: empty pipeline runs end to end; the raw/staging schema and BACKING.md agree.

**Phase 2 — One scraper, end to end.**
Easiest source only (app-store API or Opinion Assurances — NOT Trustpilot). Fetch → raw → staging dedupe → one queryable metric (reviews per month; no study claim needs it as a mart, so it is a pinned query until Beat 5's row-count mart lands).
Done when: `make rebuild` runs the real parser over a frozen sample of the feed and prints the metric, and running twice changes no row count. The first real rows land in Phase 3 with the first source whose robots file allows its feed (the Phase 2 source disallows it). Do not start a second source.

**Phase 3 — Scraper fleet + snapshots.**
Remaining sources (Trustpilot and its bot handling is its own session). Add `platform_snapshots` (rating, review count, timestamp, source URL per platform per run). Seed with §6 historical anchors, marked as such.
Done when: all sources land with provenance; running twice changes no row counts (idempotency proven).

**Phase 4 — GitHub Actions cron.**
Weekly scheduled scrape + snapshot commit. Deliberately early so the time series accrues while the rest is built.
Done when: two scheduled runs visible in the Actions history.

**Phase 5 — Hand labels + rules layer.**
Human work first: label 300–500 sampled reviews into the §5 taxonomy → `classify/eval/labels.csv`. Then `rules.yaml` + deterministic classifier, scored against the labels.
Done when: rules alone decide a measured share of cases, with per-theme precision reported. No LLM in this phase.

**Phase 6 — LLM fallback + eval gate.**
Model call for ambiguous cases only; gate scores against held-out labels; eval metrics written to a mart table; "unclassified" graceful degradation.
Done when: full corpus classified; killing the API key still yields a green pipeline with a gray band.

**Phase 7 — Findings marts + open-data calibration.**
Theme-share-by-month, peer comparison, and trend marts (everything Beats 1–2 display). Ingest Open DAMIR / data.ameli slices; fit the claim-cost distributions the simulator needs.
Done when: every Beat 1–2 chart in SPEC.md has its mart, populated.

**Phase 8 — Cost model + guardrail simulator.**
Implement §7 with sourced defaults (citations in code comments and BACKING.md); the SLA-timer simulation; the computed threshold recommendation.
Done when: model outputs land in marts; a test asserts the code's formulas equal the study's displayed numbers.

**Phase 9 — The study.**
Metabase dashboards on the marts with drill-throughs; the static HTML study export; final README in the two-layer voice.
Done when: a stranger goes from the README's first paragraph to any number's raw evidence without asking a human anything.

**Phase 10 — Airflow + Snowflake demonstration.**
Wrap the working steps in the one-screen DAG; run once against a Snowflake trial; screenshot; confirm the DuckDB path still passes.
Done when: both targets run green. (Last on purpose — the trial clock never threatens anything load-bearing.)

**Session working rules:**
1. One phase, one session, one diff. If a session reaches for a future phase's files, stop.
2. Every phase ends with its "done when" encoded as a test or make target — the next session inherits guardrails, not prose.
3. When in doubt between a clever solution and a boring one, choose boring and write one sentence in the README about why.

---

## 10. Scope guards — what this project deliberately does NOT do

- No scraping-at-scale infrastructure, proxies-as-a-service, or raw-corpus publishing.
- No fine-tuned models, embeddings pipelines, or vector stores. One prompt-based classifier call, gated.
- No dbt, no ORM, no Kubernetes, no cloud VMs, no Terraform.
- No live "days on hold" counters or any figure we cannot re-verify.
- No fabricated percentages: charts wait as Pending until real data exists.
- No editorial statements about any single company; findings are comparative and factual.
- No feature that does not surface in one of the five beats.

---

## 11. Glossary (keep to ~10 terms, one plain sentence each)

- **Claim** — a request to be paid back for a health expense you already paid.
- **Hold** — a claim paused by the insurer until something is checked or provided.
- **Flag** — an automatic mark on a claim that looks unusual and triggers a hold.
- **False positive** — a legitimate claim wrongly flagged as suspicious.
- **First-pass rejection** — a claim refused automatically before any human looks at it.
- **Second payer** — an insurer that pays what your main insurer didn't cover.
- **Document loop** — being asked for new documents each time you send the previous ones.
- **Mart** — a small, final table shaped exactly for one chart or metric in the study.
- **Provenance** — where a piece of data came from, and when we captured it.
- **Eval set** — reviews labeled by hand, used to check whether the classifier can be trusted.
