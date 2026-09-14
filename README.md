# The Friction Ledger

Each month, thousands of people write publicly about health-insurance refunds
that got stuck. This study reads those reviews from the customer's side and asks
one question: when a legitimate refund is wrongly held, what does the delay
cost? It answers in five parts, and every figure
carries a tag saying where it came from — so any number on
[the study page](study/friction_ledger.html) can be opened down to the evidence
beneath it. The promise behind each number is recorded in
[BACKING.md](BACKING.md), which maps every claim to its table, its query and its
source; the chart-by-chart structure is [SPEC.md](SPEC.md); the full rationale
is [the project brief](PROJECT_BRIEF.md).

## How to read this study

The study is written in two layers. Each section and panel opens in plain
English that any reader can follow, and the technical detail sits one step down,
under a heading marked *How we made sure*. Rigor is never removed to make a point
simpler — it moves one layer down.

Every number wears exactly one tag:

- **Measured** — counted by us, from the reviews.
- **Documented** — taken from a named public source.
- **Modeled** — produced by arithmetic we print in full.
- **Pending** — not yet supported by data, so no number is shown rather than a
  fabricated one.

No insurer is named as the subject of the study. Insurers appear only as sourced
data points.

**A note on the shipped page.** The committed
[study page](study/friction_ledger.html) is rendered from a small set of
hand-written example reviews, so the figures the study *counts from reviews* —
Beat 2's theme shares and classifier quality, both Measured — are illustrative on
that page rather than findings. Your own rebuild fills the warehouse from the
captured reviews:

```
make rebuild ROWS=captured && make study
```

(`make study` still renders the committed synthetic page; the real counts land in
your warehouse and in the Metabase demonstration described below. Rendering the
page itself from your own reviews is a planned addition.) Beat 1's rating,
channel-gap and stat-row points are Documented from public sources, and Beats 3
and 4 are Modeled from public claim-cost data and fixed parameters, independent
of the review corpus — so those figures are real on the shipped page either way.
Only Beat 2's counts differ between the shipped page and your rebuild.

## Beat 1 — The complaints are public and unprompted

On independent review platforms, the segment under study — digital-first
insurers — carries public ratings that have drifted downward month over month,
and those ratings sit lower on the platforms nobody solicits than on the ones
these companies invite customers to. The pattern is visible in public, and no one
was prompted to leave it.

- The rating over time, month by month *(Documented — B1.2)*.
- The channel gap between invited channels and unsolicited platforms
  *(Documented — B1.3)*.
- A summary row: one-star share, review counts and response lag
  *(Documented — B1.4)*.
- The opening case — a single refund held for months — awaits a documented
  example, so no number stands in for it yet *(Pending — B1.1)*.

*How we made sure.* The sampling bias is stated beside the chart it affects.
Unsolicited platforms are negatively self-selected: a company that stops inviting
reviews will drift downward for that reason alone, so part of any decline is a
sampling choice rather than a change in service. The study says so where the
rating trend is drawn.

## Beat 2 — The complaints share a shape

The complaints are not random. They fall into five recurring themes, and the
chart the whole pipeline exists to produce is the share of reviews about held or
blocked claims over time, split by segment.

- Theme share over time, by segment, from the gated classifier
  *(Measured — B2.2)*.
- The classifier's own accuracy — precision and recall against hand labels —
  shown beside the charts it feeds *(Measured — B2.4)*.
- The held-claim share, digital-first insurers against traditional mutuelles
  *(Measured — B2.5)*.

On the shipped page these are fixture counts; a `make rebuild ROWS=captured` run
fills them from the real reviews.

*How we made sure.* Rules decide the clear cases first, and a language model reads
only the reviews the rules could not settle. Its answers are graded against hand
labels before any chart uses them, and a review the model cannot place stays in a
gray "not yet classified" band rather than being dropped from view.

## Beat 3 — What a wrongly held claim costs

A held claim that turns out to be legitimate is not free. It costs staff time
answering calls and messages, and it costs customers who leave. Beat 3 puts a
number on that cost with arithmetic printed in full, so that anyone can redo it by
hand.

- The formulas, each printed next to the value it produces *(Modeled — B3.1)*.
- Fraud saved and friction cost, drawn as curves against how aggressively claims
  are flagged; where they cross, the next flag destroys more than it recovers
  *(Modeled — B3.2)*.
- The sourced inputs — revenue per member, the fraud pool and claim volume —
  each shown with its source *(Modeled — B3.3)*.
- The parameters with no public source, drawn on a distinct range and labelled
  "explore the range" *(Modeled — B3.4)*.

*How we made sure.* The formulas live in `models/cost_model.py` as data, and the
study prints them from there, so the formula shown and the number computed cannot
drift apart. There is no fitted black box: every parameter sits on a slider,
sourced where a public anchor exists and openly marked a guess where it does not.
The claim volume the study uses is derived from the average claim size the fitted
curve gives; beside it, the page prints a second, lower count reached by dividing
instead by the plain average of the public reimbursement totals (each a grouped
figure in the open data), so the recomputation is on the page to check. One
sourced figure is context rather than an input — the share of practitioners' fees
billed above the public tariff, which the public insurer never reimburses and the
fitted claim size therefore leaves out, from the Assurance Maladie's own fee
table.

## Beat 4 — Three modest fixes

The useful answer is not a better fraud model. It is a cost function wrapped
around the model that already exists. Three fixes, each deliberately plain: ask
for every document once; put a clock on every hold; and log how each hold ends.

- Below about **€42.67** on a claim, a hold long enough to matter costs more than
  it saves, so small low-risk claims can auto-release once the clock fires
  *(Modeled — B4.2)*.
- About **49.0%** of claims are small enough to fall under that threshold
  *(Modeled — B4.2)*.
- The simulator shows hold durations before and after, on synthetic claims
  calibrated to real public cost data *(Modeled — B4.3)*.
- As each fix is switched on, the net line — fraud saved minus friction cost —
  lifts *(Modeled — B4.1)*.
- Counting how each hold ends would yield a false-positive rate per flag rule,
  but that needs an outcome log which does not exist yet *(Pending — B4.4)*.

*How we made sure.* The clock's threshold is not guessed; it is computed from the
Beat 3 model, and the arithmetic is shown. The simulator is plain arithmetic over
a claim-cost distribution fitted to public reimbursement data, with the fit
displayed so that anyone can redo it.

## Beat 5 — How the study is built

The backbone is deterministic — rules, SQL and arithmetic — and a language model
sits at the edges, in one narrow place, never trusted on its own. Three facts you
can check in the code:

- A language model makes a decision in exactly **1** place *(Measured — B5.1)*.
- **15** cost-model formulas are printed next to the numbers they produce
  *(Measured — B5.1)*.
- Every number in the study wears one of **4** evidence tags *(Measured — B5.1)*.

The row counts at each pipeline stage, the eval scores, and the single command
that rebuilds everything form the reproducibility panel *(Measured — B5.2)*. That
command is `make rebuild`: it rebuilds every number from the raw reviews, and
running it twice does not move the counts. The same steps, arranged the way a
company would schedule them, are the one Airflow DAG in
[`dags/friction_ledger.py`](dags/friction_ledger.py):
scrape → load_raw → clean → classify → publish — five boxes in a row, each
running one `make` command. The DAG holds no logic of its own, so what the
scheduler runs and what you run by hand are the same five commands. The walk with
a running Airflow is in [`dags/DEMONSTRATION.md`](dags/DEMONSTRATION.md).

*How we made sure.* We use plain SQL rather than dbt: at this handful of SQL
models, the extra tool would add more to learn than it saves, and knowing when not
to reach for a tool is part of the point. Where a clever path and a plain one both
worked, we chose the plain one.

## Glossary

- **Measured** — a number we counted ourselves, such as a theme share from the
  classified reviews.
- **Documented** — a number from a named public source, such as a platform's
  published rating.
- **Modeled** — a number produced by arithmetic we print in full, such as the
  fraud-versus-friction crossover.
- **Pending** — a claim we cannot yet back with a number, shown as a placeholder
  with no figure.
- **Held claim** — a refund a legitimate customer is owed that is stuck awaiting
  extra documents or review, such as an emergency-room receipt paused for a
  second copy of a prescription.
- **Theme share** — of all classified reviews in a period, the fraction that
  mention a given complaint theme, such as the slice of a month's reviews that
  name a blocked refund.
- **The gated classifier** — the rules-plus-model tagging step whose answers must
  pass an accuracy gate before any chart uses them, like a proofreader checking
  the tags against a hand-marked answer key.
- **Digital-first versus traditional** — app-native insurers compared against
  established mutuelles, the study's core comparison, such as an app-only insurer
  set beside a long-standing mutuelle.
- **The crossover** — the flag rate at which friction cost overtakes fraud saved,
  so the next flag destroys more than it recovers, like the point where checking
  one more claim begins to lose money.
- **Extra billing** — the part of a practitioner's fee above the public tariff,
  which the public insurer never reimburses, such as a specialist charging more
  than the tariff for a visit, with the patient or their complementary insurer
  paying the difference.

## Running it

`make help` lists every command. The study rebuilds and renders offline, with no
API key and no network:

- `make rebuild` — raw → cleaned → tagged, then the cost model and simulator.
  `STAGE=load|clean|classify` runs one of its three stages into the same file
  (the DAG's middle tasks `load_raw`, `clean` and `classify`); the default runs
  all three in order.
- `make study` — render the static HTML study, byte-identical on a rerun. It
  renders the frozen synthetic input, which is the committed page; a rebuild over
  your captured reviews fills the warehouse, not this page.
- `make publish` — write the file the Metabase demonstration reads, from your
  rebuild (`ROWS=captured` by default); the DAG's last task.
- `make model` and `make simulate` — print the cost model and the guardrail
  simulator, each formula beside its value.
- `make test` — the test suite; `make check-docs` and `make check-backing` — the
  documentation and evidence guards.

Delete the API key and the pipeline still runs end to end: the reviews the rules
could not settle stay "not yet classified", and the study shows them as a gray
band rather than hiding them.

### The Metabase demonstration — a clickable third surface

Alongside the permanent page and this README, the study has a third form that you
click through: a Metabase dashboard where a theme bar drills down to the
individual reviews counted under it, over your own rebuild. It needs Docker, so it
is developer-run rather than part of the automated checks. The full walk is in
[`study/metabase/DEMONSTRATION.md`](study/metabase/DEMONSTRATION.md); in outline:

```
make rebuild ROWS=captured && make publish
cd study/metabase && docker compose up -d
set -a; . ./.env; set +a                              # your Metabase login, exported
cd ../.. && uv run python -m study.metabase apply     # reads it from the environment
```

The export step copies the marts into a SQLite file that Metabase reads with its
built-in driver, so the stack is Docker plus one file and no extra download;
`apply` provisions the dashboard from `config.yaml` and reads your login from the
environment. The drill-down shows each review's theme, rating, date, segment and
platform — never its own words and never a per-review web address — and, per
theme, one paraphrased example with its public source. The audit trail is the
counted rows plus that paraphrase, not quoted excerpts.

### The Snowflake run — the same SQL on a cloud database

The study can run once against a cloud database (Snowflake) to show that the SQL
is written once and stays portable, and then confirm the laptop path still passes.
It is a one-off demonstration, never something the study depends on: a trial
account expires, so nothing load-bearing may rest on it.

Install the connector as an optional extra (`uv sync --extra snowflake`; the
laptop never downloads it otherwise), set the six `SNOWFLAKE_*` values (account,
user, password, warehouse, database, and an optional role — see `.env.example`),
then run `make rebuild TARGET=snowflake ROWS=synthetic`, `make idempotency-check
TARGET=snowflake ROWS=synthetic` and `make publish TARGET=snowflake
ROWS=synthetic`. Only the fixture inputs (`synthetic`, `none`) run there: the
scraped reviews and the frozen samples are real people's words and never leave the
laptop, refused by name on the cloud target. The walk and its output are in
[`pipeline/DEMONSTRATION.md`](pipeline/DEMONSTRATION.md).

**Caution:** the credentials are read from the environment, so an exported `.env`
lets any process in that shell — not only you — spend trial credits. Export them
only for the run, and keep the warehouse's auto-suspend on.

Why a thin wrapper and an optional extra rather than an ORM: one file wraps each
engine's connection in a single shape, so the SQL files stay identical and
readable, and a laptop clone carries no cloud driver it never uses. It is the
plain, standard choice.

## What is planned next

The next round of work is recorded in build order in
[`docs/FUTURE_WORK.md`](docs/FUTURE_WORK.md): what each open item is, why it is
worth doing, and what would close it. The near items validate the classifier on
hand-labelled real reviews (today it is scored on the synthetic answer key), add
a traditional-insurer comparison group to the theme charts (today every source
is digital-first), and lead each surface with its finding.

That note also holds one architecture question in full: why the warehouse is
built as portable SQL with a thin engine wrapper rather than a build tool such
as dbt, how the same tables would be expressed in dbt, and what dbt would and
would not change. It is a proposal; each item that is taken up gets its own
spec before any code moves.
