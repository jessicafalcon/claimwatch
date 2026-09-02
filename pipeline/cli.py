"""The one process behind `make rebuild|idempotency-check|reset`. It validates
every user value against a closed set, derives nothing from it as a path, then
acts — the settled shape in specs/TEMPLATE.md's Threat model. Make passes each
value UNEXPANDED and single-quoted via `$(call _Q,$(value VAR))`; this process is
the guard. A bad value is one line on stderr and exit 2, never a traceback.

CONFIRM counts only from the command line: Make passes `$(origin CONFIRM)` and
this process requires it to be `command line` — an environment `CONFIRM=yes`
does not confirm a destructive `reset`."""

from __future__ import annotations

import argparse
import sys

from pipeline.build import FIXTURES, idempotency_check, rebuild, reset
from pipeline.warehouse import TARGETS


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


def _do_rebuild(args: argparse.Namespace) -> int:
    target = resolve_choice(args.target, TARGETS, "duckdb")
    fixture = resolve_choice(args.fixture, FIXTURES, "empty")
    for name, n in rebuild(target, fixture).items():
        print(f"{name:24} {n}")
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
    target = resolve_choice(args.target, TARGETS, "duckdb")
    if not confirmed(args.confirm, args.confirm_origin):
        if sys.stdin.isatty():
            reply = input("Drop the DuckDB file? This deletes data. [y/N] ")
            if reply.strip().lower() not in ("y", "yes"):
                print("reset: not confirmed; nothing deleted")
                return 2
        else:
            print(
                "reset: refusing — pass CONFIRM=yes on the command line "
                "(an environment CONFIRM=yes does not count)"
            )
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

    args = ap.parse_args(argv)
    dispatch = {
        "rebuild": _do_rebuild,
        "idempotency-check": _do_idempotency,
        "reset": _do_reset,
    }
    try:
        return dispatch[args.command](args)
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 2
