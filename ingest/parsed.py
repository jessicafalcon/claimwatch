"""What every parser hands back, and how every parser refuses (spec Phase 3a,
pinned decision 3). A page is a foreign input: a parser declares the shape it
accepts and turns one page into raw-shape rows for `raw_reviews`
(`reviews`) and `raw_platform_snapshots` (`snapshots`); anything outside the
declared shape raises `PageShapeError` naming page, item and field, and the
whole page loads nothing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# `raw_platform_snapshots.review_count` is an `integer` column (32-bit signed):
# the shape every count must fit, whatever brought it — a store page's JSON
# number or digit string, a profile page's meta content, a hand entry's cell.
# It is checked at the parse, so a value the column cannot hold is a one-line
# refusal there, never a driver exception at the load (round 2, code-reviewer
# #2 #3, security-reviewer #1 #2).
MAX_COUNT = 2**31 - 1
_COUNT = re.compile(
    r"^[0-9]{1,10}$"
)  # ten digits cover MAX_COUNT; longer never reaches int()


def count_in_range(value: object) -> int | None:
    """`value` as a non-negative integer the count column holds — a JSON
    integer (never a bool) or a digit string — or None when it is neither."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        if not _COUNT.match(value):
            return None
        number = int(value)
    elif isinstance(value, int):
        number = value
    else:
        return None
    return number if 0 <= number <= MAX_COUNT else None


class PageShapeError(ValueError):
    """The page is not the declared shape; nothing from it is loaded."""


def refuse(
    page_url: str, item_id: str | None, field_name: str, why: str
) -> PageShapeError:
    where = f"item {item_id!r}" if item_id is not None else "page"
    return PageShapeError(f"{page_url}: {where}: field {field_name!r} {why}")


@dataclass
class Parsed:
    """One page's rows: review rows in the eight-column raw shape, snapshot
    rows in the snapshot shape. A page with neither is the end of a list."""

    reviews: list[dict[str, object]] = field(default_factory=list)
    snapshots: list[dict[str, object]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.reviews and not self.snapshots

    def extend(self, other: Parsed) -> None:
        self.reviews.extend(other.reviews)
        self.snapshots.extend(other.snapshots)
