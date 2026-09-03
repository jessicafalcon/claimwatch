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
- **B1.4 — The stat row.** One-star share on independent platforms, review
  counts, and the difference in how quickly companies answer reviews. Each
  stat is its own latest point, with its own tag and day. Tag: *Documented*
  for the anchors, *Measured* for our own points (see *How to read a panel*).

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

- **B2.1 — The five kinds of complaint.** The five themes, each with
  paraphrased examples from public reviews. Tag: *Documented* (Pending until
  the examples are curated with links).
- **B2.2 — Theme share over time, by segment.** The share of negative reviews in
  each theme, month by month, split digital-first versus traditional. Counts
  theme rows under the grain above. Tag: *Measured* via the gated classifier
  (Pending until its mart lands — never faked).
- **B2.3 — Peer context.** Public ratings across the market segment, so no one
  insurer is read in isolation. Tag: *Documented* for the anchors, *Measured*
  for our own points (see *How to read a panel*). *Placed points, stated
  beside the chart:* where the brief gives a range, the point is its midpoint,
  not a reading, and a count the brief does not give is left blank.
- **B2.4 — Classifier quality.** How often each theme label is right and how many
  true cases it catches, measured against the hand labels and shown next to the
  charts it feeds. Tag: *Measured* (Pending until the eval gate writes its mart).
- **B2.5 — Held-claim complaints, digital-first versus traditional.** The share
  of document-loop complaints at digital-first insurers next to the same share
  at traditional mutuelles. This is the study's hypothesis, not its verdict: if
  the data shows no gap, the chart says so and is published as-is. Tag:
  *Measured* (Pending).

## Beat 3 — What a wrongly held claim costs

A held claim that turns out to be legitimate is not free — it costs staff time
answering calls and messages, and it costs lost customers. This part puts a
number on that with plain
arithmetic: every formula is printed above its chart, and every assumption is a
slider that is either sourced or openly marked as a guess.

*Under the hood:* the formulas live in `models/cost_model.py` and the study
renders them from there, so the printed formula and the computed number cannot
drift apart. Fraud savings rise with diminishing returns as the flag rate
climbs; friction cost rises with the false positives that same rate creates.

- **B3.1 — The formulas, next to their output.** Flagged claims, false
  positives, fraud saved, friction cost, and the net — each formula shown beside
  the value it produces. Tag: *Modeled* (Pending until the model mart lands).
- **B3.2 — The crossover chart.** Fraud euros saved and friction euros cost, both
  as curves over the flag rate, with a "you are here" marker. Where the curves
  cross, each extra flag destroys more value than it recovers. Tag: *Modeled*
  (Pending).
- **B3.3 — The sourced defaults.** The parameters anchored to public figures —
  revenue per member (~€800/year), the fraud pool (a published savings figure as
  a lower bound), and claim volume derived from published refund totals and open
  reimbursement distributions. Tag: *Modeled*, each default cited (Pending).
- **B3.4 — The declared-unsourced sliders.** The parameters with no public
  source — the false-positive share, the churn probability, and contacts per
  stuck claim — shown as differently-styled "explore the range" sliders, never
  as settled facts. Tag: *Modeled* (Pending).

## Beat 4 — Three small fixes, no rebuild required

The answer is not a better fraud model; it is three boring rules wrapped around
the one that already exists. This part shows each fix and what it does to the
Beat 3 curves.

*Under the hood:* a simulator runs synthetic claims — drawn from cost
distributions fitted to real public reimbursement data, with the fit shown —
through a hold timer, and reports before-and-after hold durations. No individual
claims data is used; none is public.

- **B4.1 — Ask for everything once.** A lookup that returns the complete document
  list for a claim type and flag reason in one request, ending the serial
  document loop — contacts per stuck claim drop to one, and the curves move. Tag:
  *Modeled* (Pending).
- **B4.2 — A clock on every hold.** A timer on each held claim: past a threshold,
  small low-risk claims auto-release and large ones escalate to a person. The
  threshold is computed from the Beat 3 model, not guessed, and the arithmetic
  is shown ("holds beyond N days on claims under €X are net-negative in
  expectation"). Tag: *Modeled* (Pending).
- **B4.3 — Before and after.** Hold durations and the Beat 3 curves, simulated
  with the fixes off and on, side by side. Tag: *Modeled* (Pending until the
  simulator mart lands).
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
  formula displayed next to its output, and no number anywhere without a source
  or a Modeled label. Tag: *Measured* (Pending until the pipeline is complete
  enough to count).
- **B5.2 — Reproducibility.** Row counts at each pipeline stage, the eval scores,
  and the one command that rebuilds everything from raw data. Tag: *Measured*
  (Pending until the rebuild produces counts).

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
