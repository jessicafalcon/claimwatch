#!/usr/bin/env python3
"""The pin guard. Standalone, no pytest, no services — `make check-pins
[BASE=main]`; the review gate runs it as its `pins` line. Not a pytest file:
its verdict depends on the branch, and a suite test must not.

The rule, one sentence: a public top-level function or class added or changed
in `<base>...HEAD` under a code package is named in a test — a NEW one, in a
test file the same range changed — and a new `sql/marts/<table>.sql` is named
by `<table>` in a changed test. Where the most frequent review finding since
Phase 0a ("pin the …": a rule, a key, a pairing, a boundary with no test) is
turned into a red line before an agent reads the diff.

  code packages  models/, pipeline/, classify/, ingest/, opendata/, scripts/,
                 .claude/hooks/
  public         a name not starting with `_`, and not `main`
  changed        the def's `ast.dump` differs from the merge-base's: comments
                 and formatting do not count; a docstring or a body does
  named          the bare name as a whole word in any tracked `tests/*.py`
                 (read from the working tree, the files pytest runs)

Output: one line per miss, `check-pins OK` when none. Exit 0
clean, 1 on a miss, 2 on a refused BASE, a git failure or a file that does not
parse. Never a traceback. Nothing here edits, commits or fixes."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import ROOT, Refused, die, diff_paths, resolve_base, run, tail

CODE_PACKAGES = (
    "models/",
    "pipeline/",
    "classify/",
    "ingest/",
    "opendata/",
    "scripts/",
    ".claude/hooks/",
)
MARTS = "sql/marts/"
EXEMPT = ("main",)
_DEF = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def public_defs(source: str) -> dict[str, str]:
    """Top-level public def or class → its `ast.dump` (raises SyntaxError)."""
    tree = ast.parse(source)
    return {
        node.name: ast.dump(node)
        for node in tree.body
        if isinstance(node, _DEF)
        and not node.name.startswith("_")
        and node.name not in EXEMPT
    }


def symbol_changes(base_src: str | None, head_src: str) -> dict[str, str]:
    """Public name → `new` (absent at base) or `changed` (a different dump);
    an unchanged or deleted def is not a pin question."""
    base = public_defs(base_src) if base_src is not None else {}
    head = public_defs(head_src)
    out: dict[str, str] = {}
    for name, dump in head.items():
        if name not in base:
            out[name] = "new"
        elif base[name] != dump:
            out[name] = "changed"
    return out


def names_in(texts: list[str], name: str) -> bool:
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return any(pattern.search(t) for t in texts)


def tracked(root: Path, *pathspecs: str) -> list[str]:
    code, out = run(["git", "ls-files", "-z", "--", *pathspecs], root)
    return sorted(diff_paths(out)) if code == 0 else []


def source_at(root: Path, rev: str, path: str) -> str | None:
    """The file at `rev`, or None when it did not exist there."""
    code, out = run(["git", "show", f"{rev}:{path}"], root)
    return out if code == 0 else None


def _read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def _def_misses(
    root: Path, base_rev: str, changed: set[str], tests: dict[str, str]
) -> list[str]:
    all_tests = list(tests.values())
    changed_tests = [t for p, t in tests.items() if p in changed]
    misses: list[str] = []
    for path in sorted(p for p in changed if p.startswith(CODE_PACKAGES)):
        if not path.endswith(".py") or not (root / path).is_file():
            continue  # a deleted file has nothing to pin
        try:
            changes = symbol_changes(source_at(root, base_rev, path), _read(root, path))
        except SyntaxError as exc:
            raise Refused(
                f"refusing: {path} does not parse: line {exc.lineno}"
            ) from exc
        for name, kind in changes.items():
            pool = changed_tests if kind == "new" else all_tests
            if not names_in(pool, name):
                where = (
                    "no test in the diff names it"
                    if kind == "new"
                    else "no test names it"
                )
                misses.append(f"{path}::{name} — {kind}, {where}")
    return misses


def _mart_misses(
    root: Path, base_rev: str, changed: set[str], tests: dict[str, str]
) -> list[str]:
    changed_tests = [t for p, t in tests.items() if p in changed]
    misses: list[str] = []
    for path in sorted(
        p for p in changed if p.startswith(MARTS) and p.endswith(".sql")
    ):
        if not (root / path).is_file() or source_at(root, base_rev, path) is not None:
            continue  # deleted, or it existed at base: not a new mart
        table = Path(path).stem
        if not names_in(changed_tests, table):
            misses.append(f"{path} — new mart, no test in the diff names {table}")
    return misses


def unpinned(root: Path, base: str) -> list[str]:
    """One line per public def or new mart in `<base>...HEAD` that no test
    names under the rule above; [] when every one is pinned. A git failure
    (an unknown BASE, no repository) is a Refused naming the command, never
    an empty green list."""
    code, out = run(["git", "merge-base", base, "HEAD"], root)
    if code != 0:
        raise Refused(f"refusing: git merge-base {base} HEAD failed: {tail(out, 1)}")
    base_rev = out.strip()
    code, out = run(["git", "diff", "-z", "--name-only", f"{base}...HEAD"], root)
    if code != 0:
        raise Refused(f"refusing: git diff {base}...HEAD failed: {tail(out, 1)}")
    changed = diff_paths(out)
    tests = {
        p: _read(root, p) for p in tracked(root, "tests/*.py") if (root / p).is_file()
    }
    return _def_misses(root, base_rev, changed, tests) + _mart_misses(
        root, base_rev, changed, tests
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--base", default="main")
    args = ap.parse_args(argv)
    try:
        base = resolve_base(args.base)
        misses = unpinned(ROOT, base)
    except Refused as exc:
        die(exc)
    for line in misses:
        print(line)
    if misses:
        print(f"check-pins FAILED: {len(misses)} unpinned")
        return 1
    print("check-pins OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
