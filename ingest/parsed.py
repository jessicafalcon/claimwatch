"""What every parser hands back, and how every parser refuses (spec Phase 3a,
pinned decision 3). A page is a foreign input: a parser declares the shape it
accepts and turns one page into raw-shape rows for `raw_reviews`
(`reviews`) and `raw_platform_snapshots` (`snapshots`); anything outside the
declared shape raises `PageShapeError` naming page, item and field, and the
whole page loads nothing."""

from __future__ import annotations

from dataclasses import dataclass, field


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
