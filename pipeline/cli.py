"""The one process behind `make rebuild|idempotency-check|reset|scrape`. It
validates every user value against a closed set, derives nothing from it as a
path, then acts — the settled shape in specs/TEMPLATE.md's Threat model. Make
passes each value UNEXPANDED and single-quoted via `$(call _Q,$(value VAR))`;
this process is the guard. A bad value is one line on stderr and exit 2, never a
traceback.

A destructive `reset` or a network `scrape` is confirmed by the `confirm` goal
in the same make invocation (`make confirm reset`): the `confirm` recipe stamps
its make process's id, the gated recipe passes its own, and `confirmed` says
yes only when they are one process — a goal cannot arrive through MAKEFLAGS
in the environment, where a variable's "command line" origin can (spec Phase
3a, A4 (d)). The fetcher is imported only inside `scrape`, so a rebuild never
loads `httpx`."""

from __future__ import annotations

import argparse
import os
import sys

from ingest import sources
from ingest.captures import has_pages, parser_module
from ingest.parsed import PageShapeError
from ingest.politeness import MAX_PAGES
from ingest.sources import SOURCES
from pipeline.build import INPUTS, captures_for, idempotency_check, rebuild, reset
from pipeline.metrics import reviews_per_month
from pipeline.warehouse import ROOT, TARGETS, connect, database_for

# The one binding of the confirmation stamp: under the gitignored data/ root,
# never tracked, written by `make confirm` and consumed by the next `reset` or
# `scrape` of the same invocation.
CONFIRM_STAMP = ROOT / "data" / ".confirm"


class Refused(Exception):
    """A one-line refusal: printed as-is, exit 2, never a traceback."""


def resolve_choice(value: str, allowed: tuple[str, ...], default: str) -> str:
    """Empty -> default; a value in the closed set -> itself; anything else
    (`../x`, `"; …`, an unknown name) is refused. The value is never used as a
    path, so a traversal or a metacharacter is just a name not in the set."""
    if not value:
        return default
    if value not in allowed:
        raise Refused(f"refusing: expected one of {allowed}, got {value!r}")
    return value


def confirmed(make_pid: str) -> bool:
    """A destructive or network action is confirmed only by the `confirm` goal
    of the SAME make invocation: the stamp `make confirm` wrote names this
    recipe's make process. The stamp is consumed either way, so a `confirm`
    left over from an earlier invocation confirms nothing later (a different
    process id), and no environment can supply a goal."""
    try:
        stamped = CONFIRM_STAMP.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    try:
        CONFIRM_STAMP.unlink()
    except OSError:
        pass
    return bool(make_pid) and make_pid.isdigit() and stamped == make_pid


def _do_confirm(args: argparse.Namespace) -> int:
    """`make confirm`: stamp this invocation's make process id for the `reset`
    or `scrape` goal that follows it in the same command. A `confirm` that is
    the last goal (or the only one) refuses, so no armed stamp outlives its
    invocation; the stamp is created exclusively with owner-only permissions,
    so a file already there — planted, or left by a killed run — makes this
    recipe refuse naming it rather than overwrite it (A8 (d)). What the gate
    holds against is a variable, an environment, `MAKEFLAGS` and a stale
    invocation; a same-user process able to write `data/` while make runs is
    outside it, and the Threat model says so."""
    if not args.make_pid.isdigit():
        raise Refused("refusing: --make-pid is not a process id")
    goals = args.goals.split()
    if not goals or goals[-1] == "confirm":
        raise Refused(
            "refusing: `confirm` arms the goal that follows it in the same command; "
            "nothing follows (`make confirm reset`, `make confirm scrape`)"
        )
    CONFIRM_STAMP.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(CONFIRM_STAMP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Refused(
            f"refusing: a confirmation stamp already exists at {CONFIRM_STAMP}; it "
            "is not this invocation's — remove it and run the command again"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(args.make_pid + "\n")
    print(
        "confirm: armed for this make invocation — `reset` or `scrape` must follow "
        "in the same command (`make confirm reset`, `make confirm scrape`)"
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
    for name, n in rebuild(target, rows).items():  # the file is the input's own
        print(f"{name:24} {n}")
    conn = connect(target, database=database_for(rows))
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
    return 0


def _do_scrape(args: argparse.Namespace) -> int:
    """Developer-run, network: fetch each chosen source into a new capture.
    SOURCE is a closed set of declared names; empty means every source whose
    site lets us fetch it — a source declared not fetchable is then skipped
    with one line, not refused, so a plain run's exit code speaks only of
    refusals met during the run (a robots rule, a status, a page shape).
    Naming such a source with SOURCE= asks for it on purpose: that is a
    refusal, exit 2. The `confirm` goal gates it like `reset`, so an agent's
    non-interactive call refuses."""
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
    if not confirmed(args.make_pid):
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
    target = resolve_choice(args.target, ("duckdb",), "duckdb")
    if not confirmed(args.make_pid):
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
    p = sub.add_parser("reset", add_help=False)
    p.add_argument("--target", default="")
    p.add_argument("--make-pid", dest="make_pid", default="")
    p = sub.add_parser("scrape", add_help=False)
    p.add_argument("--source", default="")
    p.add_argument("--make-pid", dest="make_pid", default="")

    args = ap.parse_args(argv)
    dispatch = {
        "rebuild": _do_rebuild,
        "idempotency-check": _do_idempotency,
        "confirm": _do_confirm,
        "reset": _do_reset,
        "scrape": _do_scrape,
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
