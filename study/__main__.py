"""`python -m study export` (the `make study` entry): render the static HTML
study over the frozen synthetic database and write the committed file. No user
variable, no key, no network — a read over marts already built, so two runs
write identical bytes; CI diffs the committed baseline. A render-contract breach
(a Pending panel with a value, a panel with no tag) or an unreadable warehouse
is one line on stderr and exit 2, never a traceback."""

from __future__ import annotations

import sys

from pipeline.warehouse import ROOT, DriverError
from study.export import DEFAULT_DB, RenderRefused, write


def _rel(path):
    """The written path shown relative to the repo root when it is under it,
    else as-is — so the success line never crashes on a path outside ROOT (a
    test's tmp dir), the same shape as pipeline/cli.py's `_rel`."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["export"]:
        print("usage: python -m study export", file=sys.stderr)
        return 2
    if not DEFAULT_DB.is_file():
        print(
            f"study: no synthetic warehouse at {DEFAULT_DB} — run "
            "`make rebuild ROWS=synthetic` first",
            file=sys.stderr,
        )
        return 1
    try:
        out = write()
    except RenderRefused as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    except DriverError as exc:
        print(f"refusing: the warehouse could not be read: {exc}", file=sys.stderr)
        return 2
    print(f"study: wrote {_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
