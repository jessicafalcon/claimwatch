"""What every parser hands back, and how every parser refuses (spec Phase 3a,
pinned decision 3). A page is a foreign input: a parser declares the shape it
accepts and turns one page into raw-shape rows for `raw_reviews`
(`reviews`) and `raw_platform_snapshots` (`snapshots`); anything outside the
declared shape raises `PageShapeError` naming page, item and field, and the
whole page loads nothing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

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


@dataclass(frozen=True)
class Measure:
    """One snapshot measure as its column holds it — `decimal(precision,
    scale)` inside [lo, hi] — and the two ways a value may reach it: a hand
    entry EXACTLY as written (more decimals than the scale is outside the
    shape: a person's reading is never rounded for them) or a page's figure
    ROUNDED half-even to the scale. Either way nothing reaches the loader
    that the column would rescale, so the fingerprint is the stored value
    (spec Phase 3a, A4 (a))."""

    precision: int
    scale: int
    lo: Decimal
    hi: Decimal

    @property
    def places(self) -> Decimal:
        return Decimal(1).scaleb(-self.scale)

    @property
    def pattern(self) -> str:
        """The digit shape the column holds: at most precision - scale digits
        before the point and scale after — bounded, so nothing long reaches
        Decimal()."""
        return rf"[0-9]{{1,{self.precision - self.scale}}}(\.[0-9]{{1,{self.scale}}})?"

    def exact(self, text: str) -> Decimal | None:
        """A hand-read figure, as written; None when its digit shape is not
        the column's (the caller then names the field)."""
        if not re.fullmatch(self.pattern, text):
            return None
        return Decimal(text)

    def rounded(self, value: Decimal) -> Decimal:
        """A page's figure, rounded half-even to the column's scale."""
        return value.quantize(self.places, rounding=ROUND_HALF_EVEN)

    def in_range(self, value: Decimal) -> bool:
        return value.is_finite() and self.lo <= value <= self.hi


def _ceiling(precision: int, scale: int) -> Decimal:
    return Decimal(10) ** (precision - scale) - Decimal(1).scaleb(-scale)


# `raw_platform_snapshots`' four decimal measures, declared once with their
# columns' precision, scale and range; every reader — a hand entry, a store
# page's JSON-LD, a profile page's microdata — derives its check from here,
# the way `count_in_range` does for the count (A4 (a)).
MEASURES: dict[str, Measure] = {
    "rating": Measure(4, 3, Decimal(0), Decimal(5)),
    "one_star_share": Measure(4, 3, Decimal(0), Decimal(1)),
    "response_rate": Measure(4, 3, Decimal(0), Decimal(1)),
    "response_delay_days": Measure(5, 1, Decimal(0), _ceiling(5, 1)),
}


def rating_from_page(value: str) -> Decimal | None:
    """A page's rating text -> the column's value: a bounded digit run,
    rounded to the column's scale, inside its range; None otherwise (the
    parser names page and field)."""
    if not re.fullmatch(r"[0-9]{1,2}(\.[0-9]{1,32})?", value):
        return None
    try:
        rating = MEASURES["rating"].rounded(Decimal(value))
    except InvalidOperation:
        return None
    return rating if MEASURES["rating"].in_range(rating) else None


# `raw_reviews.rating` is `decimal(2,1)`: a review's rating is a half-step, 1
# to 5 — the closed set a review source's value must belong to, declared once
# beside the snapshot measures (A6: the profile site rates in half stars; the
# App Store feed in digits, which are members). A digit, or a digit and `.5`,
# written so; `4.0`, `4.25`, `0.5` and `6` are outside it.
REVIEW_RATINGS: frozenset[Decimal] = frozenset(Decimal(n) / 2 for n in range(2, 11))
# Each member's one spelling — the column's, trailing zeros dropped — derived
# from the set, so the parse below is a lookup in the declaration and not a
# second copy of it (round 4, code-reviewer #6).
_REVIEW_RATING_SPELLINGS: dict[str, Decimal] = {
    format(r, "f"): r for r in REVIEW_RATINGS
}


def review_rating(value: object) -> Decimal | None:
    """A review's rating as a parser or a fixture hands it — a string as
    written, an integer, or a Decimal — as the column's value iff its spelling
    is a member's; None otherwise (the caller names item and field). A bool
    spells `True`, a float is not accepted at all, and no text reaches
    `Decimal()`: the lookup is the whole parse."""
    if isinstance(value, Decimal):
        text = format(value.normalize(), "f") if value.is_finite() else ""
    elif isinstance(value, (int, str)):
        text = str(value)
    else:
        return None
    return _REVIEW_RATING_SPELLINGS.get(text)


class PageShapeError(ValueError):
    """The page is not the declared shape; nothing from it is loaded."""


def refuse(
    page_url: str, item_id: str | None, field_name: str, why: str
) -> PageShapeError:
    where = f"item {item_id!r}" if item_id is not None else "page"
    return PageShapeError(f"{page_url}: {where}: field {field_name!r} {why}")


def decode_json(text: bytes | str, page_url: str, field_name: str) -> object:
    """`text` decoded as JSON, or a refusal naming `field_name`. The decoder
    fails in exactly two ways — malformed text (`ValueError`) and nesting
    deeper than the interpreter's stack (`RecursionError`) — and both are the
    page being outside the shape: a refusal at the boundary, never a
    traceback out of `make scrape` or `make rebuild` (round 3,
    security-reviewer #3)."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise refuse(
            page_url, None, field_name, "is not JSON the decoder can read"
        ) from exc


@dataclass
class Parsed:
    """One page's rows: review rows in the eight-column raw shape, snapshot
    rows in the snapshot shape. A page with neither is the end of a list."""

    reviews: list[dict[str, object]] = field(default_factory=list)
    snapshots: list[dict[str, object]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.reviews and not self.snapshots
