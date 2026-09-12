"""The one process behind `make rebuild|idempotency-check|reset|scrape|
fetch-damir|sample-damir|fit-damir|slice-ameli|split-ameli` (and the other
offline targets). It
validates every user value against a closed set, derives nothing from it as a
path, then acts — the settled shape in specs/TEMPLATE.md's Threat model. Make
passes each value UNEXPANDED and single-quoted via `$(call _Q,$(value VAR))`;
this process is the guard. A bad value is one line on stderr and exit 2, never a
traceback.

A destructive `reset` or a network `scrape`/`fetch-damir` is confirmed by the
`confirm` goal in the same make invocation (`make confirm reset`): the `confirm`
recipe stamps its make process's id, the gated recipe passes its own, and
`confirmed` says yes only when they are one process — a goal cannot arrive
through MAKEFLAGS in the environment, where a variable's "command line" origin
can (spec Phase 3a, A4 (d)). The httpx fetcher is imported only inside `scrape`,
so a rebuild never loads `httpx`; the DAMIR download uses stdlib `urllib`."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import suppress

from classify.cache import read_decisions, write_decisions
from classify.combined import classify_all
from classify.eval.gate import ANSWER_KEY, HELDOUT_FOLD, format_gate, score_heldout
from classify.eval.precision import evaluate, format_report
from classify.labels import POSITIVE, THEMES, UNCLASSIFIED, review_id
from classify.llm import ModelError, make_model_decider, model_available
from classify.rules import classify as classify_reviews
from classify.rules import load_rules
from ingest import sources
from ingest.captures import has_pages, parser_module
from ingest.parsed import (
    MAX_COUNT,
    PageShapeError,
    count_in_range,
    is_ascii_decimal_integer,
)
from ingest.politeness import MAX_PAGES
from ingest.sources import SOURCES
from models.cost_model import format_model
from models.guardrail_sim import format_simulation
from opendata.fee_split import ARTIFACT as FEE_SPLIT_ARTIFACT
from opendata.fee_split import FIXTURE_CSV as AMELI_FIXTURE_CSV
from opendata.fee_split import FIXTURE_DIR as AMELI_FIXTURE_DIR
from opendata.fee_split import (
    fixture_year,
    format_fee_split,
    read_national_families,
    write_fee_split,
)
from opendata.fee_split import write_fixture as write_ameli_fixture
from opendata.fetch import FetchError, fetch_month
from opendata.fit import (
    ARTIFACT,
    fit_lognormal,
    format_fit,
    goodness_of_fit,
    write_fit,
)
from opendata.slice import (
    DEFAULT_SAMPLE_N,
    FIXTURE_CSV,
    freeze_manifest,
    read_amounts,
    systematic_sample,
    write_fixture,
)
from opendata.sources import AMELI_EXPORT, cache_path, valid_month, valid_year
from pipeline.build import (
    FETCHED_SNAPSHOTS,
    INPUTS,
    build_post_classify_marts,
    captures_for,
    idempotency_check,
    read_model_inputs,
    rebuild,
    record_snapshots,
    reset,
    reviews_per_month,
    write_classified_reviews,
    write_classifier_quality,
    write_pipeline_row_counts,
)
from pipeline.label_sample import SHEET, label_sample
from pipeline.warehouse import ROOT, TARGETS, connect, database_for

# The one binding of the confirmation stamp: under the gitignored data/ root,
# never tracked, written by `make confirm` and consumed by the next `reset` or
# `scrape` of the same invocation.
CONFIRM_STAMP = ROOT / "data" / ".confirm"


class Refused(Exception):
    """A one-line refusal: printed as-is, exit 2, never a traceback."""


def _rel(path):
    """A path shown relative to the repo root when it is under it, else as-is —
    so a display line never crashes on a path outside ROOT (a test's tmp dir)."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def positive_int(value: str, name: str) -> int:
    """A user value that must be a positive integer (`N`), read through the one
    shared count shape `ingest.parsed.count_in_range` — ASCII digits only, in
    the count column's range — so a superscript (`²`) or other-script digit
    (`٣`) is not the shape and nothing non-ASCII reaches `int()`. Empty, a
    non-digit (`../x`, `"; …`), a sign or zero is refused; the value is never
    used to build a path (the sheet path is fixed), so a traversal or a
    metacharacter is just a string that is not a positive integer — one refusal
    line, never a traceback and never a surprise value (round 1, code-reviewer;
    fix/foreign-shape-shared-home). The count column bounds it: a value above
    `MAX_COUNT` is refused too, so the message names the range rather than call a
    too-large integer 'not a positive integer'."""
    number = count_in_range(value)
    if number is None or number < 1:
        raise Refused(
            f"refusing: {name} must be a positive integer at most {MAX_COUNT}, "
            f"got {value!r}"
        )
    return number


def resolve_choice(value: str, allowed: tuple[str, ...], default: str) -> str:
    """Empty -> default; a value in the closed set -> itself; anything else
    (`../x`, `"; …`, an unknown name) is refused. The value is never used as a
    path, so a traversal or a metacharacter is just a name not in the set."""
    if not value:
        return default
    if value not in allowed:
        raise Refused(f"refusing: expected one of {allowed}, got {value!r}")
    return value


# The goals `confirm` may arm — a closed set; `make confirm <anything else>`
# refuses and leaves no stamp (A9 (a)). `fetch-damir` joined in Phase 7b (the
# open-data download is network, developer-run).
GATED = ("reset", "scrape", "fetch-damir")


def confirmed(make_pid: str) -> bool:
    """A destructive or network action is confirmed only by the `confirm` goal
    of the SAME make invocation: the stamp `make confirm` wrote names this
    recipe's make process. The stamp is consumed either way, so a `confirm`
    left over from an earlier invocation confirms nothing later (a different
    process id). A gated target calls this as its first act, before its own
    refusals, so no refusal on a gated path leaves the stamp armed (A9 (a))."""
    try:
        stamped = CONFIRM_STAMP.read_text(encoding="utf-8").strip()
    except OSError:
        stamped = None  # absent, unreadable, or a link to nowhere
    with suppress(OSError):
        CONFIRM_STAMP.unlink()  # consumed whatever its state (exit pass)
    return (
        stamped is not None
        and is_ascii_decimal_integer(make_pid)
        and stamped == make_pid
    )


def _do_confirm(args: argparse.Namespace) -> int:
    """`make confirm`: stamp this invocation's make process id for the `reset`,
    `scrape` or `fetch-damir` goal that follows it in the same command. The goal
    after `confirm` must be one of `GATED`, so `make confirm help` and a trailing
    `confirm` refuse and leave no stamp — no ordinary command leaves an armed
    stamp behind; the goal list is trusted only when its origin is make's own
    (`$(origin MAKECMDGOALS)` is `default`): a list from the environment,
    `MAKEFLAGS` or the command line is refused (A9 (a)). The stamp is created
    exclusively with owner-only permissions, so a file already there —
    planted, or left by a killed run — makes this recipe refuse naming it
    rather than overwrite it (A8 (d)); a create that fails for any other
    reason refuses with one line too. What the gate does not hold against —
    an environment that chooses what make reads or runs (`MAKEFILES`, `PATH`),
    a same-user process writing `data/` while make runs — the Threat model
    states."""
    if not is_ascii_decimal_integer(args.make_pid):
        raise Refused("refusing: --make-pid is not a process id")
    if args.goals_origin != "default":
        raise Refused(
            "refusing: the goal list did not come from make itself (origin "
            f"{args.goals_origin!r}, not 'default'); a MAKECMDGOALS definition "
            "from the environment, MAKEFLAGS or the command line confirms nothing"
        )
    goals = args.goals.split()
    following = goals[goals.index("confirm") + 1 :] if "confirm" in goals else []
    if not following or following[0] not in GATED:
        after = f"`{following[0]}` follows" if following else "nothing follows"
        raise Refused(
            f"refusing: `confirm` arms {' or '.join(f'`{g}`' for g in GATED)} and "
            f"nothing else; {after} "
            "(`make confirm reset`, `make confirm scrape`, `make confirm fetch-damir`)"
        )
    try:
        CONFIRM_STAMP.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(CONFIRM_STAMP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Refused(
            f"refusing: a confirmation stamp already exists at {CONFIRM_STAMP}; it "
            "is not this invocation's — remove it and run the command again"
        ) from exc
    except OSError as exc:
        raise Refused(
            f"refusing: cannot write the confirmation stamp at {CONFIRM_STAMP}: "
            f"{exc.strerror}"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(args.make_pid + "\n")
    print(
        "confirm: armed for this make invocation — a gated goal "
        f"({', '.join(GATED)}) must follow in the same command "
        "(`make confirm reset`, `make confirm scrape`, `make confirm fetch-damir`)"
    )
    return 0


def _prompt(question: str, refusal: str) -> bool:
    """A tty gets a y/N question; anything else is refused with one line."""
    if sys.stdin.isatty():
        reply = input(question)
        return reply.strip().lower() in ("y", "yes")
    print(refusal)
    return False


def _do_rebuild(args: argparse.Namespace) -> int:
    target = resolve_choice(args.target, TARGETS, "duckdb")
    rows = resolve_choice(args.rows, INPUTS, "captured")
    if rows == "captured" and not any(
        has_pages(root, parser_module(src.parser).EXTENSION)
        for src, root, _ in captures_for(rows)
        if src.parser is not None
    ):
        shown = sources.CACHE_ROOT.relative_to(sources.CACHE_ROOT.parents[1])
        print(
            f"no captures under {shown} — nothing to load from the scraper; "
            "`make confirm scrape` fetches them (developer-run)"
        )
    db = database_for(rows)
    for name, n in rebuild(target, rows).items():  # the file is the input's own
        print(f"{name:24} {n}")
    conn = connect(target, database=db)
    try:
        months = reviews_per_month(conn)
    finally:
        conn.close()
    print("reviews per month (stg_reviews, by the review's own date):")
    width = max((len(source) for source, _, _ in months), default=0)
    for source, month, n in months:
        print(f"  {source:{width}} {month}  {n}")
    if not months:
        print("  (none)")
    _classify_and_print(db, rows)
    return 0


def _classify_and_print(db, rows_input: str) -> None:
    """Run the combined classification (rules + model) over the warehouse's
    `stg_reviews`, grade it on the held-out fold, write the `classifier_quality`
    mart (B2.4), and print both summaries. The model is called from
    `classify/llm.py` only, and only when a key is set (developer-run, paid) and
    only for rules-`unclassified` reviews not already in the cache. With no key the
    ambiguous reviews stay `unclassified` — the gray 'not yet classified' band —
    the classifier is rules-only, and the gate scores that truthfully (lower
    recall). Deterministic given the cache; the gate itself is offline (it grades
    stored predictions against the hand answer key — no model call)."""
    reviews = _staged_reviews_text(db)
    if reviews is None:
        print("classification: no stg_reviews yet (nothing to classify)")
        return
    decide = make_model_decider()  # None when no key
    decisions = read_decisions()
    rows, decisions = classify_all(
        reviews, rules=load_rules(), decide=decide, decisions=decisions
    )
    write_decisions(decisions)

    # Persist the classification at the (source, external_id, theme) grain and
    # build the theme-share marts (B2.2, B2.5) over it. review_id maps back to
    # (source, external_id) so nothing hashes in SQL. run_id is the rebuild input
    # name: provenance, byte-stable per input.
    identity = _review_identities(db)
    classified = sorted(
        (identity[rid][0], identity[rid][1], theme) for rid, theme in rows
    )

    # Grade on the held-out fold. The CLI hands the gate the classifier's
    # predictions and gets scores back — it reads no answer key (the wall). The
    # gate scores only reviews both classified and labeled (amendment A1), so a
    # corpus the answer key does not cover grades nothing — write no mart then,
    # rather than a mart of all-`None` Measured rows for a corpus we did not grade.
    scores = score_heldout(rows)
    graded = any(s.predicted or s.actual for s in scores)
    conn = connect("duckdb", database=db)
    try:
        write_classified_reviews(conn, classified, run_id=rows_input)
        build_post_classify_marts(conn)
        # B5.2: the per-stage row counts, after the classified stage exists, so
        # pipeline_row_counts counts it too (corpus-gated at render like the theme
        # marts). Idempotency-check runs rebuild() only, so a named test proves
        # this mart's stability instead of that target (spec invariant 5).
        write_pipeline_row_counts(conn, run_id=rows_input)
        if graded:
            write_classifier_quality(
                conn,
                scores,
                answer_key=ANSWER_KEY,
                heldout_fold=HELDOUT_FOLD,
                run_id=rows_input,
            )
    finally:
        conn.close()

    theme_rows = sum(1 for _, label in rows if label in THEMES)
    positive = sum(1 for _, label in rows if label == POSITIVE)
    unclassified = sum(1 for _, label in rows if label == UNCLASSIFIED)
    key_note = (
        "rules + model"
        if model_available()
        else "rules only — no ANTHROPIC_API_KEY, ambiguous reviews are unclassified"
    )
    print(f"classification ({key_note}; one row per review x theme):")
    print(f"  reviews         {len(reviews)}")
    print(f"  theme rows      {theme_rows}")
    print(f"  positive        {positive}")
    print(f"  unclassified    {unclassified}   (the 'not yet classified' band)")
    if graded:
        print(format_gate(scores))
    else:
        print(
            f"classifier quality — no reviews on the held-out fold {HELDOUT_FOLD} "
            "are in the answer key for this corpus; classifier_quality left empty "
            "(the answer key covers the synthetic corpus; real labels are Phase 7)"
        )


def _do_scrape(args: argparse.Namespace) -> int:
    """Developer-run, network: fetch each chosen source into a new capture.
    SOURCE is a closed set of declared names; empty means every source whose
    site lets us fetch it — a source declared not fetchable is then skipped
    with one line, not refused, so a plain run's exit code speaks only of
    refusals met during the run (a robots rule, a status, a page shape).
    Naming such a source with SOURCE= asks for it on purpose: that is a
    refusal, exit 2. The `confirm` goal gates it like `reset`, so an agent's
    non-interactive call refuses."""
    armed = confirmed(args.make_pid)  # consumed first, before any refusal (A9)
    names = tuple(s.name for s in SOURCES)
    if args.source:
        wanted = resolve_choice(args.source, names, "")
        chosen = [s for s in SOURCES if s.name == wanted]
    else:
        chosen = [s for s in SOURCES if s.fetchable]
        for s in SOURCES:
            if not s.fetchable:
                print(f"scrape: {s.name}: skipped — declared not fetchable: {s.terms}")
    if not chosen:
        raise Refused("refusing: no fetchable source is declared in ingest/sources.py")
    if not armed:
        listed = ", ".join(s.name for s in chosen)
        hosts = ", ".join(sorted({s.host for s in chosen if s.fetchable})) or "no host"
        ok = _prompt(
            f"Fetch robots.txt + up to {MAX_PAGES} pages per source from {hosts} "
            f"for {listed}, >= 2 s apart? [y/N] ",
            "scrape: refusing — run `make confirm scrape` (the confirm goal in the "
            "same invocation; no variable and no environment counts); nothing fetched",
        )
        if not ok:
            return 2
    # the only network import path
    from ingest.fetch import FetchRefused, polite_client, scrape

    polite = polite_client()  # one client, one per-host clock, for every source
    refused = 0
    try:
        for source in chosen:  # one source's refusal is its own line; the run goes on
            try:
                capture_dir, pages = scrape(source, sources.CACHE_ROOT, client=polite)
            except FetchRefused as exc:
                print(str(exc), file=sys.stderr)
                refused += 1
                continue
            print(f"scrape: {source.name}: {pages} page(s) -> {capture_dir}")
    finally:
        polite.close()
    return 2 if refused else 0


def _do_record_snapshots(_args: argparse.Namespace) -> int:
    """Non-network, non-destructive: read the captures already on disk under
    data/cache and append this week's fetched snapshot figures to the tracked
    `data/snapshots/fetched_snapshots.csv`, numbers only. No `confirm` gate —
    it fetches nothing and deletes nothing. Idempotent: recording the same
    capture twice writes no new row."""
    new = record_snapshots()
    shown = FETCHED_SNAPSHOTS.relative_to(ROOT)
    print(f"record-snapshots: {new} new row(s) -> {shown}")
    return 0


def _do_label_sample(args: argparse.Namespace) -> int:
    """Non-network, non-destructive: draw N reviews from the built corpus into
    the gitignored `data/label_sample.csv` for a human to label. N is validated
    as a positive integer here; the output path is fixed, not built from N. No
    `confirm` gate — it fetches nothing and deletes nothing."""
    n = positive_int(args.n, "N")
    written = label_sample(n)
    shown = SHEET.relative_to(ROOT)
    if written == 0:
        print(
            f"label-sample: no stg_reviews in the warehouse — wrote a header-only "
            f"{shown}; run `make rebuild` first"
        )
    else:
        print(f"label-sample: {written} review(s) -> {shown} (label offline)")
    return 0


def _staged_reviews_text(db) -> list[tuple[str, str]] | None:
    """`(review_id, text)` for every staged review, or None if the warehouse has
    no `stg_reviews` yet. `text` is the review's title and body — the words the
    rules read; the answer key is never touched here."""
    if not db.is_file():
        return None
    conn = connect("duckdb", database=db)
    try:
        exists = conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name = 'stg_reviews'"
        ).fetchone()[0]
        if not exists:
            return None
        rows = conn.execute(
            "select source, external_id, title, body from stg_reviews"
        ).fetchall()
    finally:
        conn.close()
    out: list[tuple[str, str]] = []
    for source, external_id, title, body in rows:
        text = "\n".join(part for part in (title, body) if part).strip()
        out.append((review_id(source, external_id), text))
    return out


def _review_identities(db) -> dict[str, tuple[str, str]]:
    """`review_id -> (source, external_id)` for every staged review, so the
    classifier's `(review_id, theme)` rows map back to the review's natural key
    when they are persisted — the identity is a Python hash, never recomputed in
    SQL. Empty when the warehouse has no `stg_reviews`."""
    if not db.is_file():
        return {}
    conn = connect("duckdb", database=db)
    try:
        exists = conn.execute(
            "select count(*) from information_schema.tables "
            "where table_name = 'stg_reviews'"
        ).fetchone()[0]
        if not exists:
            return {}
        rows = conn.execute("select source, external_id from stg_reviews").fetchall()
    finally:
        conn.close()
    return {
        review_id(source, external_id): (source, external_id)
        for source, external_id in rows
    }


def _do_classify_eval(_args: argparse.Namespace) -> int:
    """Non-network, non-destructive: run the rules over the synthetic corpus's
    `stg_reviews` and print per-theme precision on the tuning folds. No user
    variable — the corpus is the fixed synthetic input for 5b (real rows are
    Phase 7). The rules read the reviews and rules.yaml only; the answer key is
    read inside classify/eval/, not here."""
    reviews = _staged_reviews_text(database_for("synthetic"))
    if reviews is None:
        print(
            "classify-eval: no stg_reviews in the synthetic warehouse — "
            "run `make rebuild ROWS=synthetic` first"
        )
        return 1
    predictions = classify_reviews(reviews, load_rules())
    print(format_report(evaluate(predictions)))
    return 0


def _do_fetch_damir(args: argparse.Namespace) -> int:
    """Developer-run, network: download one month of Open DAMIR into the
    gitignored cache. MONTH is a closed `YYYY-MM` shape validated here before
    any path is built from it; the `confirm` goal gates it like `scrape`, so an
    agent's non-interactive call refuses. A plain bulk GET over urllib — no
    key, no account (DAMIR is open data). A re-fetch overwrites the same file."""
    armed = confirmed(args.make_pid)  # consumed first, before any refusal (A9)
    try:
        valid_month(args.month)  # empty / ../x / "; / a bad month -> Refused
    except ValueError as exc:
        raise Refused(f"refusing: {exc}") from exc
    if not armed:
        ok = _prompt(
            f"Download Open DAMIR {args.month} (a large file) from data.gouv.fr "
            "into data/cache/damir/? [y/N] ",
            "fetch-damir: refusing — run `make confirm fetch-damir` (the confirm "
            "goal in the same invocation; no variable and no environment counts); "
            "nothing fetched",
        )
        if not ok:
            return 2
    path, size = fetch_month(args.month)  # FetchError -> one line, exit 2 in main
    print(f"fetch-damir: {size} bytes -> {_rel(path)}")
    return 0


def _do_sample_damir(args: argparse.Namespace) -> int:
    """Offline, developer-run: draw a small, representative fixture from a
    cached month — every k-th valid legal-type amount across the whole file (no
    RNG). N is a positive integer (default DEFAULT_SAMPLE_N); MONTH names which
    cached month. Writes the two-column (`PRS_REM_MNT;PRS_REM_TYP`) fixture and
    re-freezes its MANIFEST. No `confirm` gate — it fetches nothing and deletes
    no data."""
    try:
        valid_month(args.month)
    except ValueError as exc:
        raise Refused(f"refusing: {exc}") from exc
    n = positive_int(args.n, "N") if args.n else DEFAULT_SAMPLE_N
    src = cache_path(args.month)
    if not src.is_file():
        print(
            f"sample-damir: no cached month at {_rel(src)} — run "
            "`make confirm fetch-damir MONTH=... ` first (developer-run)"
        )
        return 1
    sample = systematic_sample(src, n)
    if not sample.rows:
        print(
            f"sample-damir: no positive legal-type (0/1) PRS_REM_MNT in {src.name} "
            f"({sample.dropped} row(s) dropped) — nothing written"
        )
        return 1
    write_fixture(sample.rows)
    freeze_manifest()
    print(
        f"sample-damir: {len(sample.rows)} of {sample.total_valid} amounts "
        f"(every {sample.stride}th; {sample.dropped} dropped) -> "
        f"{_rel(FIXTURE_CSV)} + MANIFEST.sha256"
    )
    return 0


def _do_fit_damir(_args: argparse.Namespace) -> int:
    """Offline, deterministic: fit a lognormal to the frozen DAMIR fixture and
    write the tracked fit artifact (mu, sigma, n, the goodness-of-fit deciles
    and the sample mean cell) Phase 8 reads. Closed-form arithmetic, no key, no
    clock, no RNG — the same fixture always gives the same numbers. Prints the
    fit and the fit-vs-real table. A missing fixture is a clear message and
    exit 1, not a traceback."""
    if not FIXTURE_CSV.is_file():
        print(
            f"fit-damir: no fixture at {_rel(FIXTURE_CSV)} yet — run "
            "`make confirm fetch-damir MONTH=YYYY-MM` then "
            "`make sample-damir MONTH=YYYY-MM` (developer-run)"
        )
        return 1
    amounts = read_amounts(FIXTURE_CSV)
    fit = fit_lognormal(amounts.values)
    gof = goodness_of_fit(amounts.values, fit)
    write_fit(fit, gof, ARTIFACT)
    print(format_fit(fit, gof))
    if amounts.dropped:
        print(f"  ({amounts.dropped} fixture row(s) dropped: not a positive number)")
    print(f"fit written -> {_rel(ARTIFACT)}")
    return 0


def _do_slice_ameli(args: argparse.Namespace) -> int:
    """Offline, developer-run: keep one year's four national profession-family
    rows out of the hand-downloaded data.ameli export and write them as the
    frozen fixture, re-freezing its MANIFEST. YEAR is a closed `YYYY` shape
    validated here; it filters rows and never names a path (the export and the
    fixture paths are constants). No `confirm` gate — it fetches nothing and
    deletes no data. A missing export is a clear message and exit 1; an export
    off the declared shape is one refusal line naming what was off, exit 2."""
    try:
        year = valid_year(args.year)  # empty / ../x / "; / 1999 -> Refused
    except ValueError as exc:
        raise Refused(f"refusing: {exc}") from exc
    if not AMELI_EXPORT.is_file():
        print(
            f"slice-ameli: no export at {_rel(AMELI_EXPORT)} — save the data.ameli "
            "`honoraires` CSV export (`;`-delimited) from your browser there first "
            "(developer-run; the host's robots file disallows a fetch)"
        )
        return 1
    try:
        national = read_national_families(AMELI_EXPORT, year)
    except ValueError as exc:
        raise Refused(f"refusing: {exc}") from exc
    write_ameli_fixture(national.totals, AMELI_FIXTURE_CSV)
    freeze_manifest(AMELI_FIXTURE_DIR)
    print(
        f"slice-ameli: {len(national.totals.families)} national family rows for "
        f"{year} ({national.dropped} other rows dropped) -> "
        f"{_rel(AMELI_FIXTURE_CSV)} + MANIFEST.sha256"
    )
    return 0


def _do_split_ameli(_args: argparse.Namespace) -> int:
    """Offline, deterministic, no variable: read the frozen data.ameli fixture
    (its one year read off the file), compute each family's extra-billing share
    and the all-families share, write the tracked fee-split artifact and print
    it. Two sums and a division — no key, no clock, no RNG. A missing fixture
    is a clear message and exit 1; a fixture off its shape is one refusal line."""
    if not AMELI_FIXTURE_CSV.is_file():
        print(
            f"split-ameli: no fixture at {_rel(AMELI_FIXTURE_CSV)} yet — save the "
            "data.ameli export, then `make slice-ameli YEAR=YYYY` (developer-run)"
        )
        return 1
    try:
        totals = read_national_families(
            AMELI_FIXTURE_CSV, fixture_year(AMELI_FIXTURE_CSV)
        ).totals
    except ValueError as exc:
        raise Refused(f"refusing: {exc}") from exc
    write_fee_split(totals, FEE_SPLIT_ARTIFACT)
    print(format_fee_split(totals))
    print(f"fee split written -> {_rel(FEE_SPLIT_ARTIFACT)}")
    return 0


def _missing_artifact(command: str) -> int | None:
    """The model paths need both tracked artifacts; a missing one is a clear
    message naming the target that writes it, and exit 1 — not a traceback."""
    if not ARTIFACT.is_file():
        print(
            f"{command}: no fit artifact at {_rel(ARTIFACT)} — run `make fit-damir` "
            "first (developer-run)"
        )
        return 1
    if not FEE_SPLIT_ARTIFACT.is_file():
        print(
            f"{command}: no fee split artifact at {_rel(FEE_SPLIT_ARTIFACT)} — run "
            "`make split-ameli` first (developer-run)"
        )
        return 1
    return None


def _do_model(_args: argparse.Namespace) -> int:
    """Offline, no variable, no warehouse: read the two tracked artifacts and
    print the parameter table (each row with its range; a sourced one with its
    citation), the formula table (each expression beside its value at the
    defaults, per scenario) and the two crossovers. Writes nothing. Run twice:
    identical text — nothing on this path reads a clock or a key. A missing
    artifact is a clear message and exit 1, not a traceback."""
    if (code := _missing_artifact("model")) is not None:
        return code
    print(format_model(read_model_inputs()))
    return 0


def _do_simulate(_args: argparse.Namespace) -> int:
    """Offline, no variable, no warehouse: read the two tracked artifacts and
    print the three rules (each beside its value at the defaults), the SLA
    threshold table (one line per timer day, the default marked) and the hold-day
    summary per fix. Writes nothing. Run twice: identical text — nothing on this
    path reads a clock or a key. A missing artifact is a clear message and exit
    1, not a traceback."""
    if (code := _missing_artifact("simulate")) is not None:
        return code
    print(format_simulation(read_model_inputs()))
    return 0


def _do_idempotency(args: argparse.Namespace) -> int:
    target = resolve_choice(args.target, TARGETS, "duckdb")
    rows = resolve_choice(args.rows, INPUTS, "synthetic")
    ok, first, second = idempotency_check(target, rows)
    for name in sorted(set(first) | set(second)):
        a, b = first.get(name), second.get(name)
        flag = "" if a == b else "  <- CHANGED"
        print(f"{name:24} {a} -> {b}{flag}")
    if not ok:
        print("idempotency-check FAILED: a row count changed on the second rebuild")
        return 1
    print("idempotency-check OK: every row count unchanged on the second rebuild")
    return 0


def _do_reset(args: argparse.Namespace) -> int:
    # reset handles only the DuckDB file; TARGET=snowflake is refused with one
    # line here, not a traceback from reset() downstream.
    armed = confirmed(args.make_pid)  # consumed first, before any refusal (A9)
    target = resolve_choice(args.target, ("duckdb",), "duckdb")
    if not armed:
        ok = _prompt(
            "Drop every DuckDB file this repo built (the corpus and one per "
            "rebuild input, past or present)? "
            "This deletes data. [y/N] ",
            "reset: refusing — run `make confirm reset` (the confirm goal in the "
            "same invocation; no variable and no environment counts)",
        )
        if not ok:
            print("reset: not confirmed; nothing deleted")
            return 2
    removed = reset(target)
    print(f"reset: removed {len(removed)} file(s): {[str(p) for p in removed]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline", add_help=False)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("rebuild", "idempotency-check"):
        p = sub.add_parser(name, add_help=False)
        p.add_argument("--target", default="")
        p.add_argument("--rows", default="")
    p = sub.add_parser("confirm", add_help=False)
    p.add_argument("--make-pid", dest="make_pid", default="")
    p.add_argument("--goals", default="")  # make's own goal list, in order
    p.add_argument("--goals-origin", dest="goals_origin", default="")  # $(origin)
    p = sub.add_parser("reset", add_help=False)
    p.add_argument("--target", default="")
    p.add_argument("--make-pid", dest="make_pid", default="")
    p = sub.add_parser("scrape", add_help=False)
    p.add_argument("--source", default="")
    p.add_argument("--make-pid", dest="make_pid", default="")
    sub.add_parser("record-snapshots", add_help=False)  # no user variable
    p = sub.add_parser("label-sample", add_help=False)
    p.add_argument("--n", default="")
    sub.add_parser("classify-eval", add_help=False)  # no user variable
    p = sub.add_parser("fetch-damir", add_help=False)
    p.add_argument("--month", default="")
    p.add_argument("--make-pid", dest="make_pid", default="")
    p = sub.add_parser("sample-damir", add_help=False)
    p.add_argument("--month", default="")
    p.add_argument("--n", default="")
    sub.add_parser("fit-damir", add_help=False)  # no user variable
    p = sub.add_parser("slice-ameli", add_help=False)
    p.add_argument("--year", default="")
    sub.add_parser("split-ameli", add_help=False)  # no user variable
    sub.add_parser("model", add_help=False)  # no user variable
    sub.add_parser("simulate", add_help=False)  # no user variable

    args = ap.parse_args(argv)
    dispatch = {
        "rebuild": _do_rebuild,
        "idempotency-check": _do_idempotency,
        "confirm": _do_confirm,
        "reset": _do_reset,
        "scrape": _do_scrape,
        "record-snapshots": _do_record_snapshots,
        "label-sample": _do_label_sample,
        "classify-eval": _do_classify_eval,
        "fetch-damir": _do_fetch_damir,
        "sample-damir": _do_sample_damir,
        "fit-damir": _do_fit_damir,
        "slice-ameli": _do_slice_ameli,
        "split-ameli": _do_split_ameli,
        "model": _do_model,
        "simulate": _do_simulate,
    }
    try:
        return dispatch[args.command](args)
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except PageShapeError as exc:
        # A stored capture that is not the declared shape (hand-edited, or a
        # parser tightened since it was written): one line, never a traceback.
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    except ModelError as exc:
        # A model call failed on the developer-run paid path (a bad model id, a
        # rate limit, a network error): one line, never a traceback. The no-key
        # path never reaches here.
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        # The developer-run DAMIR download hit no matching month or an empty
        # body: one line, exit 2, never a traceback. The offline fit path (the
        # DONE command, CI) never reaches here.
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
