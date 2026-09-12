# The Friction Ledger

Health-insurance refunds get stuck, and the people they get stuck on say so in
public, by the thousands. This study reads those reviews from the customer's
chair and asks one plain question: when a legitimate refund is wrongly held,
what does that cost? It answers in five beats, and every number carries a tag
saying where it came from — so you can open [the study page](study/friction_ledger.html)
and follow any figure down to its evidence without asking anyone. The promise
behind every number is [BACKING.md](BACKING.md) (claim → table → query →
source); the chart-by-chart structure is [SPEC.md](SPEC.md); the full rationale
is [the project brief](PROJECT_BRIEF.md).

## What you're looking at

Two layers everywhere: a plain-English opening any reader can follow, then the
detail one signpost down under *How we made sure*. Rigor is never removed to
simplify — it moves one layer down.

Every number wears exactly one tag: **Measured** (counted by us), **Documented**
(from a named public source), **Modeled** (arithmetic we print in full), or
**Pending** (not enough data yet — so no number is shown, never a fake one). No
insurer is named as the target of the study; insurers appear only as sourced
data points.

**About the shipped page.** The committed [study page](study/friction_ledger.html)
is rendered from a small set of hand-written example reviews. The figures we
*count from reviews* — Beat 2's theme shares and classifier quality (Measured) —
are therefore illustrative fixtures on it, not findings; your own rebuild over
the captured reviews fills them from real data:

```
make rebuild ROWS=captured && make study
```

Beat 1's rating, channel-gap and stat-row points are **Documented** from public
sources, and Beat 3 and Beat 4 are **Modeled** from public claim-cost data and
fixed parameters (independent of the review corpus) — all real either way. Only
Beat 2's counts differ between the shipped page and your rebuild.

## Beat 1 — People are telling us what's wrong, in public

On independent review platforms the studied segment — digital-first insurers —
shows public ratings that have drifted down over the months, sitting lower on
the platforms nobody solicits than on the ones these companies invite people to.
The pattern is public and unprompted.

- The rating over time, month by month *(Documented — B1.2)*.
- The channel gap: invited channels versus unsolicited platforms *(Documented — B1.3)*.
- A stat row: one-star share, review counts, response lag *(Documented — B1.4)*.
- The hero — one refund held for months — is awaited as a documented case, so
  no number stands in for it yet *(Pending — B1.1)*.

*How we made sure.* The bias sits beside the chart: unsolicited platforms are
negatively self-selected — a company that stops inviting reviews drifts down —
so part of any decline is a sampling choice, not only a change in service. The
study states this where the rating trend is drawn.

## Beat 2 — The complaints have a shape

The complaints are not random. They fall into five recurring themes, and the
chart the whole pipeline exists to produce is the share of reviews about held
or blocked claims over time, split by segment.

- Theme share over time, by segment, through the gated classifier *(Measured — B2.2)*.
- The classifier's own accuracy — precision and recall against hand labels —
  shown right beside the charts it feeds *(Measured — B2.4)*.
- The held-claim share, digital-first versus traditional mutuelles *(Measured — B2.5)*.

On the shipped page these are fixture counts; your `make rebuild ROWS=captured`
run fills them from the real reviews.

*How we made sure.* Rules decide the clear cases first; a language model reads
only the reviews the rules could not settle, and its answers are graded against
hand labels before any chart uses them. A review the model cannot place stays in
a gray "not yet classified" band rather than being hidden.

## Beat 3 — What a wrongly held claim costs

A held claim that turns out to be legitimate is not free: it costs staff time
answering calls and messages, and it costs lost customers. Beat 3 puts a number
on that with arithmetic printed in full, so anyone can redo it by hand.

- The formulas, each printed next to the value it produces *(Modeled — B3.1)*.
- Fraud saved and friction cost as curves over how aggressively claims are
  flagged; where they cross, the next flag destroys more than it recovers
  *(Modeled — B3.2)*.
- The sourced inputs — revenue per member, the fraud pool, claim volume — each
  shown with its source; the claim volume the study uses comes from the
  average claim size the fitted curve gives, and beside it the page shows a
  second, lower count a reader gets by dividing instead by the plain average
  of the public reimbursement totals (each a grouped figure in the open data),
  so that recompute is on the page to check *(Modeled — B3.3)*.
- The parameters with no public source, drawn on a differently-styled range and
  labelled "explore the range" *(Modeled — B3.4)*.

*How we made sure.* The formulas live in `models/cost_model.py` as data, and the
study prints them from there, so the shown formula and the computed number
cannot drift apart. No fitted black box: every parameter is on a slider, sourced
where a public anchor exists and openly marked a guess where it does not.

## Beat 4 — Three small fixes, no rebuild required

The elegant answer is not a better fraud model — it is a cost function wrapped
around the one that already exists. Three fixes, each boring on purpose: ask for
every document once; put a clock on every hold; and log how each hold ends.

- Below about **€42.67** on a claim, a hold that long costs more than it saves,
  so small low-risk claims can auto-release once the clock fires *(Modeled — B4.2)*.
- About **49.0%** of claims are small enough to fall under that threshold
  *(Modeled — B4.2)*.
- The simulator shows hold durations before and after, on synthetic claims
  calibrated to real public cost data *(Modeled — B4.3)*.
- As each fix is switched on, the net line — fraud saved minus friction cost —
  lifts *(Modeled — B4.1)*.
- Counting how each hold ends would give a false-positive rate per flag rule —
  it needs an outcome log that does not exist yet *(Pending — B4.4)*.

*How we made sure.* The clock's threshold is not guessed; it is computed from the
Beat 3 model and the arithmetic is shown. The simulator is plain arithmetic over
a claim-cost distribution fitted to public reimbursement data, with the fit
displayed so anyone can redo it.

## Beat 5 — How this was built, and where the rigor lives

The backbone is deterministic — rules, SQL and arithmetic — and a language model
sits only at the edges, in one narrow place, never trusted on its own. Three
facts you can check in the code:

- A language model makes a decision in exactly **1** place *(Measured — B5.1)*.
- **15** cost-model formulas are printed next to the numbers they produce
  *(Measured — B5.1)*.
- Every number in the study wears one of **4** evidence tags *(Measured — B5.1)*.

The row counts at each pipeline stage, the eval scores, and the one command that
rebuilds everything are the reproducibility panel *(Measured — B5.2)*. One
command rebuilds every number from the raw reviews: `make rebuild`. Run it twice
and the counts do not move.

*How we made sure.* We use plain SQL, not dbt: at a handful of SQL models the
extra tool adds more to learn than it saves, and knowing when not to reach for a
tool is part of the point. When in doubt between a clever way and a boring one,
we chose boring.

## Glossary

- **Measured** — a number we counted ourselves, like a theme share from the
  classified reviews.
- **Documented** — a number from a named public source, like a platform's
  published rating.
- **Modeled** — a number produced by arithmetic we print in full, like the
  fraud-versus-friction crossover.
- **Pending** — a claim we cannot back with a number yet, shown as a placeholder
  with no figure.
- **Held claim** — a refund a legitimate customer is owed that is stuck awaiting
  extra documents or review, like an emergency-room receipt paused for a second
  copy of a prescription.
- **Theme share** — of all classified reviews in a period, the fraction that
  mention a given complaint theme, like the slice of a month's reviews that name
  a blocked refund.
- **The gated classifier** — the rules-plus-model tagging step whose answers must
  pass an accuracy gate before any chart uses them, like a proofreader checking
  the tags against a hand-marked answer key.
- **Digital-first versus traditional** — app-native insurers compared against
  established mutuelles, the study's core comparison, like an app-only insurer set
  beside a long-standing mutuelle.
- **The crossover** — the flag rate where friction cost overtakes fraud saved, so
  the next flag destroys more than it recovers, like the point where checking one
  more claim starts to lose money.

## Running it

`make help` lists every command. The study rebuilds and renders offline, with no
API key and no network:

- `make rebuild` — raw → cleaned → tagged, then the cost model and simulator.
- `make study` — render the static HTML study; byte-identical on a rerun.
- `make model` and `make simulate` — print the cost model and the guardrail
  simulator, each formula beside its value.
- `make test` — the suite; `make check-docs` and `make check-backing` — the
  documentation and evidence guards.

Delete the API key and the pipeline still runs end to end: the reviews the rules
could not settle stay "not yet classified", and the study shows them as a gray
band rather than hiding them.

### The Metabase demonstration — the clickable third surface

Beside the permanent page and this README, the study has a third form you *click*:
a Metabase dashboard where a theme bar drills to the individual reviews counted
under it, over your own rebuild. It needs Docker (so it is developer-run, not part
of the automated checks). The walk is in
[`study/metabase/DEMONSTRATION.md`](study/metabase/DEMONSTRATION.md); in short:

```
make rebuild ROWS=captured && uv run python -m study.metabase export
cd study/metabase && docker compose up -d
set -a; . ./.env; set +a                              # your Metabase login, exported
cd ../.. && uv run python -m study.metabase apply     # reads it from the environment
```

The export step copies the marts into a SQLite file that Metabase reads with its
built-in driver, so the stack is Docker plus one file and no extra download; `apply`
provisions the dashboard from `config.yaml` and reads your login from the
environment. The drill shows each review's theme, rating, date, segment and platform — never
its own words and never a per-review web address — and, per theme, one paraphrased
example with its public source. The audit trail is the counted rows plus that
paraphrase, not quoted excerpts.
