"""Portability + no-clock guard for `sql/` (docs/PLAN.md §4.10, CLAUDE.md ->
Deterministic first). The same SQL must run on DuckDB and Snowflake, so a file
may use only the shared subset: no engine-specific reader, no pattern matching
(regex, `like`, `similar to` — patterns live in `rules.yaml`/Python; a file
with no pattern carries no dialect and attribution joins on exact values), and
no clock (time is `captured_at` or the review's own date, never `now()`).

A denylist, not a parser: it strips `--` line comments (so a header sentence is
never a false hit), lowercases, and looks for forbidden substrings. The set is
deliberately small and extendable — a false hit or a missed form is a BACKLOG
row, not a silent widening (spec Phase 1, Review & stack risk). The tests exercise
it on every `sql/` file and on planted strings."""

from __future__ import annotations

import re

_COMMENT = re.compile(r"--[^\n]*")

# DuckDB-only or otherwise non-ANSI-both forms, and every form of pattern
# matching: `regexp` catches every regex function, ` like ` and `similar to`
# the ANSI patterns — attribution joins on exact values or on a column written
# in Python, never a pattern (spec Phase 3a, invariant 4); `read_csv/parquet/
# json` catch readers; the rest are DuckDB select/aggregate sugar Snowflake
# does not share.
NONPORTABLE = (
    "read_csv",
    "read_parquet",
    "read_json",
    "regexp",
    "summarize",
    "unpivot",
    "list_value",
    "group by all",
    # DuckDB spells its pattern operators with a tilde (`~~` is `like`, `~` a
    # regex match, with `!` and `*` variants): the one character every one of
    # them carries, and one no portable statement uses (round 3).
    "~",
)
# A clock on the data path is a bug: the number would change between runs.
CLOCK = (
    "now(",
    "current_date",
    "current_timestamp",
    "current_time",
    "today(",
    "getdate(",
)


# Pattern matching by keyword, each matched as a whole word, so `like(`,
# `like` before a newline or a tab, and `LIKE` are caught alike and
# `unlike_count` is not (round 1, code-reviewer on the spaced needle). The set
# is every pattern keyword either engine documents — a denylist by design
# (Phase 1), widened only with a record: round 2 added `ilike` and `rlike`,
# round 3 `glob` and the tilde operators above (DECISIONS → Phase 3a). The
# keyword, not the regex, is what a hit reports — it is what a reader must
# remove.
PATTERN_WORDS = (
    ("like", r"\blike\b"),
    ("ilike", r"\bilike\b"),
    ("rlike", r"\brlike\b"),
    ("glob", r"\bglob\b"),
    ("similar to", r"\bsimilar\s+to\b"),
)


def _scan(text: str, needles: tuple[str, ...]) -> list[str]:
    body = _COMMENT.sub("", text).lower()
    return [n for n in needles if n in body]


def find_nonportable(text: str) -> list[str]:
    """DuckDB-only / non-portable forms and pattern keywords present in `text`
    (comments stripped)."""
    body = _COMMENT.sub("", text).lower()
    words = [word for word, rx in PATTERN_WORDS if re.search(rx, body)]
    return _scan(text, NONPORTABLE) + words


def find_clock(text: str) -> list[str]:
    """Clock functions present in `text` (comments stripped)."""
    return _scan(text, CLOCK)
