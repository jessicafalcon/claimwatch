"""The one process behind `make rebuild|idempotency-check|reset|scrape`. It
validates every user value against a closed set, derives nothing from it as a
path, then acts — the settled shape in specs/TEMPLATE.md's Threat model. Make
passes each value UNEXPANDED and single-quoted via `$(call _Q,$(value VAR))`;
this process is the guard. A bad value is one line on stderr and exit 2, never a
traceback.

CONFIRM counts only from the command line: Make passes `$(origin CONFIRM)` and
this process requires it to be `command line` — an environment `CONFIRM=yes`
does not confirm a destructive `reset` or a network `scrape`. The fetcher is
imported only inside `scrape`, so a rebuild never loads `httpx`."""

from __future__ import annotations

import argparse
import sys

from ingest.app_store import FeedShapeError, has_pages
from ingest.politeness import ALLOWED_HOSTS, MAX_PAGES
from ingest.sources import SOURCES, by_name, source_names
from pipeline.build import (
    DEFAULT_CACHE,
    FIXTURES,
    capture_root,
    idempotency_check,
    rebuild,
    reset,
)
from pipeline.metrics import reviews_per_month
from pipeline.warehouse import TARGETS, connect, database_for


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


def confirmed(value: str, origin: str) -> bool:
    """A destructive action is confirmed only by `CONFIRM=yes` on the command
    line (its `$(origin)`)."""
    return origin == "command line" and value == "yes"


def _prompt(question: str, refusal: str) -> bool:
    """A tty gets a y/N question; anything else is refused with one line."""
    if sys.stdin.isatty():
        reply = input(question)
        return reply.strip().lower() in ("y", "yes")
    print(refusal)
    return False


def _do_rebuild(args: argparse.Namespace) -> int:
    target = resolve_choice(args.target, TARGETS, "duckdb")
    fixture = resolve_choice(args.fixture, FIXTURES, "cache")
    root = capture_root(fixture)
    if fixture == "cache" and not (root and has_pages(root)):
        shown = DEFAULT_CACHE.relative_to(DEFAULT_CACHE.parents[2])
        print(
            f"no captures under {shown} — nothing to load from the scraper; "
            "`make scrape CONFIRM=yes` fetches them (developer-run)"
        )
    db = database_for(fixture)  # one file per input; a fixture never touches the corpus
    for name, n in rebuild(target, fixture, database=db).items():
        print(f"{name:24} {n}")
    conn = connect(target, database=db)
    try:
        rows = reviews_per_month(conn)
    finally:
        conn.close()
    print("reviews per month (stg_reviews, by the review's own date):")
    for source, month, n in rows:
        print(f"  {source:14} {month}  {n}")
    if not rows:
        print("  (none)")
    return 0


def _do_scrape(args: argparse.Namespace) -> int:
    """Developer-run, network: fetch each chosen source into a new capture.
    SOURCE is a closed set of declared names (empty -> all of them); CONFIRM
    gates like `reset`, so an agent's non-interactive call refuses."""
    names = source_names()
    chosen = (
        [by_name(resolve_choice(args.source, names, ""))]
        if args.source
        else list(SOURCES)
    )
    if not chosen:
        raise Refused("refusing: no source is declared in ingest/sources.py")
    if not confirmed(args.confirm, args.confirm_origin):
        listed = ", ".join(s.name for s in chosen)
        ok = _prompt(
            f"Fetch robots.txt + up to {MAX_PAGES} feed pages from {ALLOWED_HOSTS[0]} "
            f"for {listed}, >= 2 s apart? [y/N] ",
            "scrape: refusing — pass CONFIRM=yes on the command line "
            "(an environment CONFIRM=yes does not count); nothing fetched",
        )
        if not ok:
            return 2
    # the only network import path
    from ingest.fetch import FetchRefused, polite_client, scrape

    polite = polite_client()  # one client, one per-host clock, for every source
    try:
        for source in chosen:
            try:
                capture_dir, pages = scrape(source, DEFAULT_CACHE, client=polite)
            except FetchRefused as exc:
                raise Refused(str(exc)) from exc
            print(f"scrape: {source.name}: {pages} page(s) -> {capture_dir}")
    finally:
        polite.close()
    return 0


def _do_idempotency(args: argparse.Namespace) -> int:
    target = resolve_choice(args.target, TARGETS, "duckdb")
    fixture = resolve_choice(args.fixture, FIXTURES, "synthetic")
    ok, first, second = idempotency_check(target, fixture)
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
    if not confirmed(args.confirm, args.confirm_origin):
        ok = _prompt(
            "Drop the DuckDB file? This deletes data. [y/N] ",
            "reset: refusing — pass CONFIRM=yes on the command line "
            "(an environment CONFIRM=yes does not count)",
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
        p.add_argument("--fixture", default="")
    p = sub.add_parser("reset", add_help=False)
    p.add_argument("--target", default="")
    p.add_argument("--confirm", default="")
    p.add_argument("--confirm-origin", dest="confirm_origin", default="undefined")
    p = sub.add_parser("scrape", add_help=False)
    p.add_argument("--source", default="")
    p.add_argument("--confirm", default="")
    p.add_argument("--confirm-origin", dest="confirm_origin", default="undefined")

    args = ap.parse_args(argv)
    dispatch = {
        "rebuild": _do_rebuild,
        "idempotency-check": _do_idempotency,
        "reset": _do_reset,
        "scrape": _do_scrape,
    }
    try:
        return dispatch[args.command](args)
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FeedShapeError as exc:
        # A stored capture that is not the declared shape (hand-edited, or a
        # parser tightened since it was written): one line, never a traceback.
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
