"""The number-shape layout guard — the reworked mechanism for the
`unshaped-input` class (LESSONS). That class was already `promoted -> code-craft
-> Guards`; it recurred (a scraped Crawl-delay and the CLI's integer checks
parsed by hand), so the mechanism, not the row, is reworked (CLAUDE.md ->
Workflow rules). Every foreign count and decimal in `ingest/`, `pipeline/` and
`opendata/` is read through one shared shape in `ingest.parsed` —
`DECIMAL_SHAPE` and `is_ascii_decimal_integer` — so neither the `str.isdigit`
Unicode trap nor a bare `float()` on unshaped text can reappear at a new site.

An AST walk, not a substring grep: a grep denylist is the exact form this class
retired in tooling round 3 (a spawner-name denylist let `os.popen` slip). The
walk sees a real call node — so `float` in a comment, a string or a type hint
raises nothing — and names the enclosing function. What it flags is a bare
`float(...)` / `.isdigit()` / `.isdecimal()` call; a value-form alias
(`f = float; f(x)`) is out of its scope, as it is a grep's — none exists in this
codebase, and a reviewer catches one. The guard bans the two loose coercions
outright — `.isdigit`/`.isdecimal` (the methods that lie about Unicode) and
`float()` outside the shaped-decimal parsers. `int()` and `Decimal()` are not
banned: in this repo they are always preceded by a bounded digit shape (a date's
`int(m.group(...))`, `Decimal(text)` after a `Measure` pattern), so banning them
would force an ever-growing allowlist — the escape hatch this guard exists to
avoid (fix/foreign-shape-shared-home)."""

from __future__ import annotations

import ast
from pathlib import Path

from ingest.parsed import DECIMAL_SHAPE, count_in_range, is_ascii_decimal_integer

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("ingest", "pipeline", "opendata")

# `float()` belongs only to the shaped-decimal parsers: each matches
# `DECIMAL_SHAPE` before it calls `float()`, so the string it converts is
# already the shape. A new entry here is a new decimal parser, reviewed as one —
# not an escape hatch for an unshaped coercion.
FLOAT_CALLERS = frozenset(
    {
        ("opendata/slice.py", "parse_amount"),
        ("opendata/fit.py", "_finite_float"),
        ("ingest/robots.py", "_parse_groups"),
    }
)


class _CoercionScan(ast.NodeVisitor):
    """Records loose numeric coercions with their enclosing function name: a
    `.isdigit`/`.isdecimal` attribute call, or a bare `float(...)` call."""

    def __init__(self) -> None:
        self._funcs: list[str] = []
        self.isdigit_hits: list[int] = []
        self.float_hits: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._funcs.append(node.name)
        self.generic_visit(node)
        self._funcs.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("isdigit", "isdecimal"):
            self.isdigit_hits.append(node.lineno)
        if isinstance(func, ast.Name) and func.id == "float":
            where = self._funcs[-1] if self._funcs else "<module>"
            self.float_hits.append((where, node.lineno))
        self.generic_visit(node)


def _package_modules() -> list[Path]:
    # rglob, not glob: a future subpackage under one of these must be scanned too.
    return sorted(p for pkg in PACKAGES for p in (ROOT / pkg).rglob("*.py"))


def _scan(path: Path) -> _CoercionScan:
    scan = _CoercionScan()
    scan.visit(ast.parse(path.read_text(encoding="utf-8")))
    return scan


def test_no_isdigit_or_isdecimal_in_the_three_packages():
    """`str.isdigit`/`str.isdecimal` are true for other-script digits (`٣`) and
    so cannot stand for "an ASCII decimal"; the shared shape does. None appears
    in ingest/, pipeline/ or opendata/."""
    offenders = [
        f"{p.relative_to(ROOT)}:{ln}"
        for p in _package_modules()
        for ln in _scan(p).isdigit_hits
    ]
    assert offenders == [], offenders


def test_float_only_in_the_shaped_decimal_parsers():
    """A bare `float()` on unshaped text is the coercion this class forbids;
    every `float()` call in the three packages lives in a parser that matched
    `DECIMAL_SHAPE` first."""
    offenders = [
        f"{p.relative_to(ROOT)}:{ln}: float() in {func}()"
        for p in _package_modules()
        for func, ln in _scan(p).float_hits
        if (str(p.relative_to(ROOT)), func) not in FLOAT_CALLERS
    ]
    assert offenders == [], offenders
    # every allowlisted caller still exists and shape-checks in its own module
    for rel, func in FLOAT_CALLERS:
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert f"def {func}(" in source, rel
        assert "DECIMAL_SHAPE" in source, rel


def test_is_ascii_decimal_integer_is_the_shape():
    for good in ("0", "12", "4194304", str(2**40)):
        assert is_ascii_decimal_integer(good), good
    for bad in ("", " 1", "1 ", "1.0", "-1", "+1", "1e5", "1_000", "٣", "²", "0x1"):
        assert not is_ascii_decimal_integer(bad), bad


def test_decimal_shape_is_ascii_only():
    for good in ("1", "12.50", "-0.5", "1,5", "0"):
        assert DECIMAL_SHAPE.fullmatch(good), good
    for bad in ("٣", "1e5", "1_000", "nan", "inf", "+3", "", " 1"):
        assert not DECIMAL_SHAPE.fullmatch(bad), bad


def test_count_in_range_uses_the_shared_integer_shape():
    assert count_in_range("٣") is None  # the shape, not str.isdigit
    assert count_in_range("12") == 12
    assert count_in_range("0") == 0


def test_the_scan_catches_a_new_loose_coercion():
    """The guard's own edge: a fresh `float()` and `.isdigit()` are both seen as
    call nodes, each with its enclosing function named."""
    scan = _CoercionScan()
    scan.visit(ast.parse("def f(x):\n    return float(x) or x.isdigit()\n"))
    assert scan.float_hits == [("f", 2)]
    assert scan.isdigit_hits == [2]
