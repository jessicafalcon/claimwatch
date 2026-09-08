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

  code packages  models/, pipeline/, classify/, ingest/, opendata/, study/,
                 dags/, scripts/, .claude/hooks/
  public         a name not starting with `_`, and not `main`
  changed        the def's `ast.dump` differs from the merge-base's: comments
                 and formatting do not count; a docstring or a body does
  named          the bare name as a whole word in any `tests/*.py` at HEAD

Every file is read from git (`git show <rev>:<path>`), the merge-base side and
the HEAD side alike: the gate reviews commits, and a blob never follows a
symlink out of the repository. A blob that is not UTF-8 text, or one that
does not parse, is a one-line refusal naming the path.

Output: one line per miss, `check-pins OK` when none. Exit 0 clean, 1 on a
miss, 2 on a refused BASE, a git failure, a non-text blob or a file that does
not parse. Never a traceback. Nothing here edits, commits or fixes."""

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
    "study/",
    "dags/",
    "scripts/",
    ".claude/hooks/",
)
MARTS = "sql/marts/"
EXEMPT = ("main",)
_DEF = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
# What ast.parse raises besides SyntaxError on 3.12: a nesting the parser
# cannot recurse (RecursionError). A null byte is a SyntaxError with no line,
# handled by the SyntaxError branch. A closed set; MemoryError ("parser stack
# overflowed") is not caught — it is not a property of the file.
_PARSE_ERRORS = (RecursionError,)


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


def _test_files(root: Path, rev: str) -> list[str]:
    """Every `tests/*.py` in the tree at `rev` (NUL-separated, read whole;
    `ls-tree` takes a directory, so the suffix is filtered here)."""
    code, out = run(
        ["git", "ls-tree", "-r", "-z", "--name-only", rev, "--", "tests"], root
    )
    if code != 0:
        raise Refused(f"refusing: git ls-tree {rev} tests failed: {tail(out, 1)}")
    return sorted(p for p in diff_paths(out) if p.endswith(".py"))


def source_at(root: Path, rev: str, path: str) -> str | None:
    """The blob at `rev:path` as text; None when the path is not in that tree;
    a Refused naming the path when the blob is not UTF-8 text."""
    if run(["git", "cat-file", "-e", f"{rev}:{path}"], root)[0] != 0:
        return None
    code, out = run(["git", "show", f"{rev}:{path}"], root)
    if code != 0:
        raise Refused(f"refusing: {path} at {rev}: {tail(out, 1)}")
    return out


def _def_misses(
    root: Path,
    base_rev: str,
    changed: set[str],
    all_tests: list[str],
    changed_tests: list[str],
) -> list[str]:
    misses: list[str] = []
    for path in sorted(p for p in changed if p.startswith(CODE_PACKAGES)):
        if not path.endswith(".py"):
            continue
        head_src = source_at(root, "HEAD", path)
        if head_src is None:
            continue  # deleted in the range: nothing to pin
        try:
            changes = symbol_changes(source_at(root, base_rev, path), head_src)
        except SyntaxError as exc:
            where = (
                f"line {exc.lineno}" if exc.lineno else exc.msg
            )  # a null byte has no line
            raise Refused(f"refusing: {path} does not parse: {where}") from exc
        except _PARSE_ERRORS as exc:
            raise Refused(
                f"refusing: {path} does not parse: {type(exc).__name__}"
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
    root: Path, base_rev: str, changed: set[str], changed_tests: list[str]
) -> list[str]:
    misses: list[str] = []
    for path in sorted(
        p for p in changed if p.startswith(MARTS) and p.endswith(".sql")
    ):
        if (
            source_at(root, "HEAD", path) is None
            or source_at(root, base_rev, path) is not None
        ):
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
    tests = {p: source_at(root, "HEAD", p) or "" for p in _test_files(root, "HEAD")}
    all_tests = list(tests.values())
    changed_tests = [t for p, t in tests.items() if p in changed]
    return _def_misses(
        root, base_rev, changed, all_tests, changed_tests
    ) + _mart_misses(root, base_rev, changed, changed_tests)


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
