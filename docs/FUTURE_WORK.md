# Future work — build order and open questions

**Status: proposal, not yet scheduled.** This document records the planned
order of the next round of work and the reasoning behind it. It does not
change any contract; each item that reaches implementation gets its own spec
or fix branch under the usual workflow. Items map to open rows in `BACKLOG.md`
by number where one exists.

The ordering principle: start anything time-gated or passive first so its
clock runs while other work proceeds; settle the one architecture question
that shapes later marts before adding to them; validate the classifier on real
data before any analysis leans on it; write the finding once it has a control
group and validated labels behind it; then reliability; then simplification.

The critical path is **§2 → §3 → §5 → §6**: settle the warehouse-tooling
question, validate the eval on real rows, add the comparison group, then lead
with the finding. Everything else parallelises around it.

---

## Build order at a glance

| § | Item | Backlog row | Position rationale |
|---|---|---|---|
| 1 | Observe two live weekly runs | 44 | Time-gated; start the clock now |
| 2 | Warehouse tooling: the dbt question | — | Settle before adding marts |
| 3 | Real eval labels + real precision/recall | 46 | The science leg; precedes any comparison |
| 4 | Standalone eval report + with-key sanity check | 48, 49 | Small follow-on to §3 |
| 5 | Traditional-segment comparison group | 51 | The headline result; needs §3 first |
| 6 | Lead with the finding | — | Only after §3 and §5 |
| 7 | Weekly-scrape edit detection and partial harvest | 30, 45 | Reliability once the corpus is refreshed for §5 |
| 8 | Mutation sweep on `classify/` and `models/` | 12 | Rigor evidence; off the critical path |
| 9 | Simplifications and framing | 76, others | Cosmetic; whenever there is slack |

---

## 1. Observe two live weekly runs (row 44)

**Why it is relevant work.** The Phase 4 done-when is "two scheduled runs
visible in the Actions history." The offline path is already proven by the
DONE command; what remains is confirmation that the scheduled path runs
unattended and that `data/snapshots/fetched_snapshots.csv` gains rows. This is
the only item whose constraint is calendar time rather than effort, so it
belongs first: the clock can run while everything below is built.

**What would solve it.** A manual dispatch of `weekly.yml` to seed the history,
then confirmation after the second Monday that two `weekly` runs appear and the
tracked snapshot file grew. A workflow on a quiet repository is disabled after
sixty days of inactivity; a manual dispatch keeps it live. If the runs do not
appear, a debug pass on the schedule trigger, recorded under DECISIONS →
Gotchas.

---

## 2. Warehouse tooling: the dbt question

This section records why the current SQL-plus-Python tooling was chosen, how
the same result would be expressed in dbt, and what dbt would and would not
solve. It is the one architecture question that shapes every mart added later,
so it is settled before §3–§5 add to the warehouse.

### 2.1 The current approach

The pipeline is plain SQL, one file per table under `sql/raw/`, `sql/staging/`
and `sql/marts/`, with a header comment naming each table's grain, provenance
columns and the BACKING rows it feeds. Python glues the steps (`pipeline/`),
one connection seam (`pipeline/warehouse.py`) knows DuckDB from Snowflake, and
a portability lint (`pipeline/sql_lint.py`) keeps every SQL file ANSI-only by
denying reader functions, regex and clock calls. A claim-to-table evidence
contract lives in `BACKING.md` and is enforced by `make check-backing`.
Idempotency is asserted in CI by `make idempotency-check`. A Python-fed mart
carries a DDL-only `.sql` file and one `write_*` function.

### 2.2 Why it was chosen

- **Zero data-tooling dependencies.** The stack is `duckdb` plus the standard
  library on the default path; the cloud path adds one optional connector. No
  package outside the phase allowlist is pulled in, which keeps the offline
  guarantee (no key, no services, no network) simple to state and to test.
- **Determinism stated as a contract, not inherited from a tool.** The rule
  that a rerun produces byte-identical output, and that a person can redo the
  arithmetic by hand, is checked directly by the suite and CI. The pinning
  tests and the idempotency check are the source of that guarantee, so it holds
  the same way on both engines and does not depend on a tool's own semantics.
- **Provenance and evidence expressed as first-class artifacts.** Each
  displayed number carries exactly one tag (Measured, Documented, Modeled,
  Pending), and each claim maps to a BACKING row. These are project-specific
  contracts with no direct off-the-shelf equivalent, so they are carried in the
  repository's own files and guards.
- **A small surface a reader can hold in their head.** One file per table, one
  seam file, one lint file. The full build system is legible from the repo map
  and the file headers without a separate tool's mental model.

### 2.3 How dbt would be implemented

dbt (data build tool) is the common way to express a SQL warehouse as a set of
`select` models with a compiled dependency graph, built and tested by a single
runner. A migration would map as follows:

- **Layering.** `sql/raw`, `sql/staging`, `sql/marts` become dbt's `staging`
  and `marts` model directories; the raw layer becomes dbt `sources` (external
  tables declared in YAML). The header comments' grain and column facts move
  into model **contracts** (typed column definitions dbt enforces at build).
- **Portability.** The DuckDB-versus-Snowflake seam becomes dbt **adapters**:
  the same models compile and run against `dbt-duckdb` and `dbt-snowflake`.
  This replaces `pipeline/sql_lint.py`'s portability denylist with the
  adapter's own dialect handling, and `pipeline/warehouse.py`'s dual connection
  wrappers with dbt's connection profiles.
- **Evidence and lineage.** `BACKING.md`'s claim-to-table mapping becomes dbt
  `exposures` (declared downstream uses of models) plus `dbt docs`, which
  renders the source-to-mart dependency graph. `make check-backing` is replaced
  by the exposure and source references being resolvable in the compiled graph.
- **Tests and idempotency.** The custom guards become `dbt test` (schema tests
  for uniqueness, not-null, accepted-values, and relationship tests). dbt runs
  are idempotent by construction (each model is a `create or replace`), so the
  bespoke idempotency check narrows to the append-only raw-load step.
- **Python-fed marts.** The DDL-only `.sql` plus `write_*` pattern becomes dbt
  **Python models** (or stays as pre-hooks that call the existing writers),
  keeping the cost model and simulator writers where they are.
- **Airflow.** The five `BashOperator`s over `make` become one `dbt run` /
  `dbt test` invocation (or the `dbt-airflow` operators), with the scrape and
  classify steps staying as their own tasks around it.

### 2.4 What dbt would solve

- Collapses `sql_lint.py`, the dual connection wrappers' catalog reads, the
  claim-to-table guard, and much of the idempotency check into tool
  configuration and built-in tests.
- Gives a rendered lineage graph (`dbt docs`) in place of header comments and
  the BACKING table, so the source-to-mart path is navigable rather than
  described.
- Makes the grain and column facts enforced contracts at build time rather than
  comments a reader trusts.
- Removes the hand-written staging/marts convention in favour of the ecosystem
  default, which lowers the onboarding cost for anyone who already knows dbt.

### 2.5 What dbt would not solve, and the residual decision

- The provenance tags (Measured/Documented/Modeled/Pending) and the neutrality
  contract have no direct dbt equivalent; they would remain project-specific,
  carried in `meta` fields and checked by the existing guards.
- The rules-first classifier, the single model call site, the eval gate against
  held-out hand labels, and the no-key-green guarantee sit outside the SQL
  layer and are untouched by a warehouse-tooling choice.
- dbt adds a dependency and a build-time model that the current zero-dependency,
  fully-in-repo approach deliberately avoids.

**Resolution to record.** Either adopt dbt and let it absorb §2.3's mappings,
or keep the current tooling with this section cited as the reason. The decision
belongs in `DECISIONS.md` with the tradeoff stated both ways; until it is made,
new marts added in §3–§5 follow the current one-file-per-table convention so
that a later migration moves a uniform set of files.

---

## 3. Real eval labels and real precision/recall (row 46)

**Why it is relevant work.** The eval gate currently scores the classifier
against thirty-nine synthetic ground-truth rows. Precision and recall on the
real corpus have nothing to score, so the classifier's quality on real reviews
is unmeasured. Any analysis that reads theme shares off the real corpus (§5 in
particular) rests on an unvalidated classifier until this is closed. This is
the science leg of the study, and it precedes the comparison work.

**What would solve it.** A held-out sample of real reviews labelled against the
closed seven-label set (`make label-sample N=`, then each review's themes
decided from the closed set and appended to `classify/eval/labels.csv` as
`(review_id, theme)` rows). The per-theme precision and recall test then scores
real rows against those labels; the synthetic ground truth stays for CI. The
labelling is offline work that produces the answer key; the gate wiring reads
it.

---

## 4. Standalone eval report and with-key sanity check (rows 48, 49)

**Why it is relevant work.** The held-out precision/recall report is visible
today only through a full `make rebuild`, which lands it in the
`classifier_quality` mart. A reviewer wanting the report without a rebuild has
no target. Separately, a with-key run lets the model decide the ambiguous
reviews, so the graded figures move and are not pinned; a real held-out fold
will carry disagreements and land off 1.0, unlike the synthetic fold of clear
cases.

**What would solve it.** A read-only, offline `make classify-gate` target that
reads the built corpus's predictions and prints the held-out report, mirroring
the existing `make classify-eval` tuning-fold report. Alongside it, a stated
way to sanity-check the with-key numbers without pinning a nondeterministic
value — for example, a bound the figures must fall within rather than an exact
pin. Both ride naturally on §3.

---

## 5. Traditional-segment comparison group (row 51)

**Why it is relevant work.** Every declared source is `digital-first`, so the
theme-share marts split by one segment only. The study's hypothesis compares
held-claim complaints across digital-first and traditional segments; without a
traditional column there is no control arm, and the headline comparison is
unanswerable. This is the largest single lift below and the highest analytical
payoff, and it is meaningful only once §3 has validated the classifier on real
rows.

**What would solve it.** A traditional-segment source declared and captured
under the existing source-declaration rules, so `theme_share_by_month` and
`theme_share_by_segment` gain a `traditional` segment. `theme_share_by_segment`
then renders it with no code change (x = segment, theme = series). The
by-month split needs one change: the month query filters `segment =
'digital-first'`, so a second series set or a second panel carries the
by-segment split — the spec that declares the source decides which. Until then
the affected SPEC panels state that the comparison waits.

---

## 6. Lead with the finding

**Why it is relevant work.** The build system is fully documented, but the
study's conclusion is not the first thing a reader meets. The value of the
study is the answer to its questions — whether held-claim complaints are
growing, how the segments compare, and what a wrongly blocked refund costs —
not the elegance of the pipeline behind it. Leading with the finding is only
honest once the finding has a control group (§5) and validated labels (§3)
behind it; done earlier it would headline a result with no comparison arm.

**What would solve it.** A reframed opening in the README and the study export
that states the finding first, each number wearing its tag and its caveats
(the sampling bias of unsolicited reviews named beside the trend it affects),
with the pipeline as the support rather than the lead. The two-layer writing
rule still applies: the plain statement first, the method below a signpost.

---

## 7. Weekly-scrape edit detection and partial harvest (rows 30, 45)

**Why it is relevant work.** Two data-quality gaps sit in the weekly path.
First, a source whose reviews carry no stable identifier keys each review on a
content hash, so an edited review becomes a new review rather than a new
version of one, and distinct-review counts can overstate by the number of
edits. Second, a weekly run where one source refuses aborts the whole commit,
so a partial but successful scrape records nothing. Both matter once the corpus
is being refreshed in earnest for §5.

**What would solve it.** For edits: count reviews whose body changed between two
captures (same dates and rating, different hash); if edits are more than a
handful, key on the stable fields and treat the body as content, with a
DECISIONS entry. For partial harvest: a per-source harvest that records a
succeeding source's figures even when another source refuses, so a partial week
is not a lost week. No partial or fabricated row is ever written.

---

## 8. Mutation sweep on `classify/` and `models/` (row 12)

**Why it is relevant work.** The load-bearing logic — the rules classifier and
the cost and simulator formulas — is pinned by goldens and the
formulas-equal-displayed-numbers test, and hand-mutated per review round. An
automated mutation sweep (delete-call, constant-return, invert-guard,
swap-sort-key over Python; arm operators over SQL `case`) would give standing
evidence that the tests bite, rather than a per-round manual check. It is off
the critical path and best run once §3–§5 have stabilised the logic.

**What would solve it.** Adopting the reference project's mutation sweep for the
`classify/` and `models/` surfaces, scoped to the classes those modules carry,
with surviving mutants treated as a test gap to close. Adoption can be narrowed
to one class first, per the row's trigger, rather than the whole surface at
once.

---

## 9. Simplifications and framing

**Why it is relevant work.** Three items lower surface or sharpen how existing
work reads, without changing the analytical story:

- **Neutrality check.** The hashed-token check in `make check-docs` is
  belt-and-suspenders over the D1 walk, which already confines the brand token
  to a single declaration file. The invariant "the token lives in exactly one
  file" is simpler and stronger than "hash every token and compare"; the walk
  can stay and the hash list can retire.
- **`pipeline/build.py` split (row 76).** The module carries the readers, the
  raw-declaration guard, the review load, the relocated month query and every
  Python-fed mart writer beside `rebuild()`. A split into a writers module (or
  a readers module) is re-homing with no behaviour change.
- **Process surface.** The spec, challenge, review-agent and ledger machinery
  is one place where the amount of process could be presented as a lighter
  variant suited to a team, so the surface reflects the judgement of how much
  process to run, not only the ability to run it.

**What would solve it.** Each is a dedicated tooling or fix branch off main,
never mixed into a phase: retire the hash list and keep the walk; move the mart
writers into their own module under `pipeline/` with imports re-pointed; and
record the lighter process variant alongside the current one. Each is small and
independent, to be taken up whenever there is slack between the items above.
