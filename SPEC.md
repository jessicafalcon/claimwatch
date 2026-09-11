# SPEC.md — the study structure

The study is told in five parts, from the customer's chair: what people say in
public, the shape of those complaints, what a wrongly held refund costs, three
small fixes, and how the whole thing was built. This file is the frozen list of
those parts and the exact charts inside them. Each panel below names two things:
the kind of evidence it carries, and the `BACKING.md` row (`B<beat>.<n>`) that
holds its query and its source. Nothing else is a chart in this study.

**How to read a panel.** Every number in a panel wears exactly one evidence tag
— *Measured* (we captured it), *Documented* (a sourced public report) or
*Modeled* (arithmetic we show). A panel with nothing to show yet is *Pending*:
an honest placeholder, never a made-up number. A panel that mixes kinds of
point names each tag it carries, and every point is marked. Most rows are still
Pending: the contracts were written before the data, so each panel names the
tag it will wear once its data lands and shows a gray "not yet" state until
then. The rating panels of Beat 1 and the peer context of Beat 2 show numbers
today. Those numbers are mostly the public figures gathered when the study was
scoped — we call them the *anchors* — tagged *Documented*. The figures we
capture or read off a page ourselves land beside them, tagged *Measured*. Each
point carries its own tag, so a chart can be read point by point. A panel never
invents a number to fill itself.

**The classification grain (settled here, before any theme chart is frozen).** A
review can be about more than one thing, so the classifier writes **one row per
review × theme**: a review carrying two themes produces two rows, and a review
with no theme produces a single `positive` or `unclassified` row. A "theme
share" therefore counts theme rows, not reviews, and the same review can appear
in two theme bars. CLAUDE.md's Classification contract states the same grain.

This file is a living document: `make check-docs` checks its links and that it
names no command that does not exist, and `make check-backing` checks that every
`B<beat>.<n>` it cites is a real row in [BACKING.md](BACKING.md) and that no row
goes uncited. The master plan is [PROJECT_BRIEF.md](PROJECT_BRIEF.md); the rules
are [CLAUDE.md](CLAUDE.md).

## Beat 1 — People are telling us what's wrong, in public

Thousands of customers write publicly about refunds that get stuck. This part
shows that voice: one story in full, then how the segment's public ratings have
moved and how they differ between channels the companies invite and channels
they do not.

*Under the hood:* ratings live in `platform_snapshots`: the anchors from
PROJECT_BRIEF.md §6, the figures a person read off a page whose terms forbid a
robot, and our own captures, each row marked with how it came to be. Repeated
captures start in Phase 4. A figure the brief dates to a month is placed on
the 15th of that month, and one it dates to a season on the 15th of that
season's first month ("early 2025" is 2025-01-15); one it dates to a span of
years is placed at mid-year of the span's first year ("2025–2026" is
2025-06-15); one it does not date is placed on the day of the figure it was
gathered beside (the Google Play figure beside the App Store's, 2024-09-15;
the Opinion Assurances figures beside the June 2026 reading, 2026-06-15). A
figure the brief gives as a range is stored at the range's midpoint, rounded
to the column ("~2.7–3.8" is 3.250), and a figure it does not give at all is
left empty. The day, and a midpoint, are placements, not readings.

- **B1.1 — The hero case.** One documented refund put on hold pending extra
  documents — a roughly €340 emergency-room claim reported unresolved for
  months. A "Day N — claim on hold" figure, frozen at the last publicly
  confirmed date (never a live counter, because we cannot verify it daily). Tag:
  *Documented* (Pending until the case is curated with its public link).
- **B1.2 — The rating trend.** The studied segment's public rating over time,
  as a monthly series. Tag: *Documented* for the anchors, *Measured* for our
  own points (see *How to read a panel*).
  *Sampling bias, stated beside the chart:* unsolicited review platforms are
  negatively self-selected — a company that stops inviting reviews drifts down
  — so part of any decline is a sampling choice, not only a service change.
- **B1.3 — The channel gap.** Ratings on channels a company controls or invites
  versus unsolicited platforms, side by side. Tag: *Documented* for the
  anchors, *Measured* for our own points (see *How to read a panel*).
- **B1.4 — The ratings in context.** One-star share on independent platforms, review
  counts, and the difference in how quickly companies answer reviews. Each
  stat is its own latest point, with its own tag and day. Tag: *Documented*
  for the anchors, *Measured* for our own points (see *How to read a panel*).
  *Stated beside the chart:* today the response rate and delay are measured
  for one profile on one platform, so the comparison across platforms waits
  for a second platform's measured figures; the brief's ranges for the studied
  insurer are not placed (BACKLOG).

## Beat 2 — The complaints have a shape

The complaints are not random. They fall into five recurring themes, and this
part counts how the share of each moves over time and how it differs between
digital-first insurers and traditional mutuelles. This is the part the whole
pipeline exists to produce.

*Under the hood:* rules label the clear reviews; a language model reads only the
ones the rules could not decide; the result passes a quality gate scored against
reviews we labeled by hand before any chart uses it. The five themes are the
document loop, silent rejections, second-payer failures, support without
traction, and coverage-and-price frustration (PROJECT_BRIEF.md §5).

- **B2.1 — The five kinds of complaint.** The five themes, each with a
  paraphrased example from public reviews. Tag: *Documented* — curated with their
  public sources in `study/paraphrases.yaml` (Phase 9g); shown beside the
  review-level drill in the Metabase demonstration, the only text that surface
  renders (a review's own words are never shown).
- **B2.2 — Theme share over time, by segment.** The share of each theme among
  every classified review, month by month, split digital-first versus
  traditional. Counts theme rows under the grain above; the denominator is every
  classified review (*positive* included, but never drawn as a theme bar — a
  theme chart counts complaints). Tag: *Measured* via the gated classifier. When
  the language model is switched off, the reviews it would have sorted stay in a
  gray *not yet classified* band — shown, never hidden. *Fixture state:* a share
  over the frozen synthetic reviews is never a number; the committed page shows a
  labelled fixture state, and the counted shares appear only over captured
  reviews. On the HTML page the counts (theme rows, reviews) ride in each share's
  tooltip so it can be redone by hand; the Metabase demonstration (Phase 9g) shows
  the same counts as visible cells and drills to the review rows behind each theme
  bar over the reader's own rebuild. *Placed beside the chart:* the corpus is digital-first only for now, so
  the traditional split awaits a traditional-mutuelle source (BACKLOG); the
  chart shows the segment the data has.
- **B2.3 — Peer context.** Public ratings across the market segment, so no one
  insurer is read in isolation. Tag: *Documented* for the anchors, *Measured*
  for our own points (see *How to read a panel*). *Placed points, stated
  beside the chart:* where the brief gives a range, the point is its midpoint,
  not a reading, and a count the brief does not give is left blank. A profile
  rated on two platforms is two points, each labelled by its platform, never
  one averaged point.
- **B2.4 — Classifier quality.** How often each theme label is right and how many
  true cases it catches, measured against the hand labels and shown next to the
  charts it feeds. The classifier is graded only on reviews it never saw while it
  was built (the held-out fold), so the scores are not flattered. Tag: *Measured*.
  A label with no case in the held-out fold shows *no held-out case* — an
  empty denominator, not a zero score — with its counts. *Fixture state:* like
  B2.2, the committed page shows a labelled fixture state; the graded table
  appears only over captured reviews.
- **B2.5 — Held-claim complaints, digital-first versus traditional.** The share
  of document-loop complaints at digital-first insurers next to the same share
  at traditional mutuelles, each share among every classified review in its
  segment (*positive* included in the total, not drawn as a bar). This is the
  study's hypothesis, not its verdict: if the data shows no gap, the chart says
  so and is published as-is. Tag: *Measured*. *Placed beside the chart:* the
  corpus is digital-first only for now, so the traditional column awaits a
  traditional-mutuelle source (BACKLOG); the chart shows the segments the data
  has. *Fixture state:* like B2.2, a share over the frozen synthetic reviews is a
  labelled fixture state, not a number.

## Beat 3 — What a wrongly held claim costs

A held claim that turns out to be legitimate is not free — it costs staff time
answering calls and messages, and it costs lost customers. This part puts a
number on that with plain
arithmetic: every formula is printed above its chart, and every assumption is
shown with its range, either sourced or openly marked as a guess. Each range is
a static mark, not a slider you drag: the permanent page carries no script, so
each parameter shows its low, default and high as a fixed mark, and a reader
redoes the arithmetic at any point of the range by hand with the printed formula.

*Under the hood:* the formulas live in `models/cost_model.py` and the study
renders them from there, so the printed formula and the computed number cannot
drift apart. Fraud savings rise with diminishing returns as the flag rate
climbs; friction cost rises with the false positives that same rate creates.

- **B3.1 — The formulas, next to their output.** Flagged claims, false
  positives, fraud saved, friction cost, and the net — each formula shown beside
  the value it produces. The hold timer's three formulas (the loop length, the
  friction per day, and the threshold amount) print in the same list, used by
  Beat 4 at the defaults, and so does the contrast count — claims per year at
  the sample's own mean reimbursement cell (each cell an aggregated total for
  a group of claims in the open DAMIR data), the same division as the claim
  volume over the plain average of the cells, used by nothing downstream. The
  list is the baseline scenario; the three toggled scenarios are B4.1's. Tag:
  *Modeled*.
- **B3.2 — The crossover chart.** Fraud euros saved and friction euros cost, both
  as curves over the flag rate, with a "you are here" marker. Where the two
  curves cross, the flagging as a whole starts to cost more than it recovers.
  *Under the hood:* an earlier point — where the next flag added costs more than
  it saves — is marked on the chart too. Each marker is a row of the model's
  own output, never read off the drawing; a grid the curves never cross draws
  no crossing marker and the note says "never crosses on this grid"; two
  markers at one flag rate (the baseline's own case) stack their labels,
  neither hidden. One channel the curves do not show, stated beside them: for
  a company plan, one employee stuck in a document loop complains to HR, and
  HR decides the renewal. Tag: *Modeled*.
- **B3.3 — The sourced defaults.** The parameters anchored to public figures —
  revenue per member (~€800/year), the fraud pool (a published savings figure as
  a lower bound), and claim volume derived from published refund totals and open
  reimbursement distributions. The headline figures — revenue per member, the
  mean claim, the claim volume and, beside the volume, the claim count at the
  sample's mean reimbursement cell — are derived from these inputs and shown
  above the parameter rows; the note beneath says which of the two means is
  the larger and so which count is the lower. Tag: *Modeled*, each default
  cited.
- **B3.4 — The declared-unsourced parameters.** The parameters with no public
  source — the false-positive share, the churn probability, contacts per stuck
  claim, the flag rate, how quickly extra flags stop catching new fraud, and the
  cost per contact — each with its explore-the-range span drawn, styled apart
  from the sourced rows, never as settled facts. Tag: *Modeled*.

## Beat 4 — Three small fixes, no rebuild required

The answer is not a better fraud model; it is three boring rules wrapped around
the one that already exists. This part shows each fix and what it does to the
Beat 3 curves.

*Under the hood:* a simulator runs synthetic claims — the distribution fitted to
real public reimbursement data, read at a thousand evenly spaced points, with the
fit shown — through a hold timer, and reports before-and-after hold durations. No
individual claims data is used; none is public. When a fix already cuts the
document loop to a single round, the timer has nothing left to cut, so "ask once"
and "both fixes" show the same hold.

- **B4.1 — Ask for everything once.** A lookup that returns the complete document
  list for a claim type and flag reason in one request, ending the serial
  document loop — contacts per stuck claim drop to one, and the curves move. The
  chart draws the net (fraud saved minus friction cost) over the flag rate for
  the baseline and all three toggled scenarios of B3.1/B3.2 — one net line each,
  the fixes lifting the line; the fraud caught is unchanged, so what moves is the
  cost. Tag: *Modeled*.
- **B4.2 — A clock on every hold.** A timer on each held claim: past a threshold,
  small low-risk claims auto-release and large ones escalate to a person. The
  threshold is computed from the Beat 3 model, not guessed, and the arithmetic
  is shown ("holds beyond N days on claims under €X are net-negative in
  expectation"). Tag: *Modeled*.
- **B4.3 — Before and after.** One bar per scenario — the no-fix hold and each
  fix beside it (scenario × hold days), so the before is shown once, not a
  distribution — with the share of claims the clock released as a note figure.
  Tag: *Modeled*.
- **B4.4 — Count the mistakes.** Logging how each hold ends — fraud-confirmed or
  released-clean — yields a false-positive rate per flag rule, the metric the
  system otherwise lacks; the same event stream also triggers a status
  notification, which fixes silent rejections for free. Tag: *Modeled* (Pending;
  a design panel, no number until the outcome log exists).

## Beat 5 — How this was built, and where the rigor lives

The study is built so the same data always produces the same numbers, and a
language model is used in only one small step. This part states the checkable
facts plainly and shows how anyone can reproduce every number.

*Under the hood:* the pipeline is idempotent and reruns to the same numbers; the
one place a model makes a decision is a single module, gated against hand labels.

- **B5.1 — The facts you can check.** One place a model makes a decision, every
  formula displayed next to its output, and the closed set of evidence tags every
  number wears — each a count read from the code (`determinism_facts`), so a
  displayed fact cannot drift from the repository. Not corpus-gated: a repo fact
  is constant on any input, so the committed page shows the numbers. Tag:
  *Measured*.
- **B5.2 — Reproducibility.** Row counts at each pipeline stage
  (`pipeline_row_counts`), the eval scores (B2.4's `classifier_quality`), and the
  one command that rebuilds everything from raw data (`make rebuild`). Measured
  behind the corpus gate, like Beat 2 — real counts over a captured input, the
  fixture-state note over the frozen synthetic input. Tag: *Measured*.

## Glossary

Ten terms, one sentence and an everyday example each.

- **Claim** — a request to be paid back for a health expense you already paid;
  for example, sending in a €30 dentist receipt to get reimbursed.
- **Hold** — a claim paused by the insurer until something is checked or sent;
  like a bank freezing a payment until you confirm it.
- **Flag** — an automatic mark on a claim that looks unusual and triggers a hold,
  the way a card gets blocked after an odd purchase.
- **False positive** — a legitimate claim wrongly marked suspicious, like a real
  customer's card declined for no good reason.
- **First-pass rejection** — a claim refused automatically before any person
  looks at it, like an online form rejected for a field it misread.
- **Second payer** — an insurer that covers what your main insurer did not, the
  way a discount code applies after the main price is set.
- **Document loop** — being asked for a new document each time you send the last
  one, like a form that keeps returning with one more required field.
- **Mart** — a small final table shaped for exactly one chart, like a single
  clean spreadsheet tab built for one graph.
- **Provenance** — where a piece of data came from and when we captured it, like
  the date and shop printed on a receipt.
- **Eval set** — reviews labeled by hand and kept aside to check whether the
  classifier can be trusted, like an answer key held back to grade a test.
