"""The declared sources — a closed tuple (spec Phase 2, pinned decision 1).
`make scrape SOURCE=<name>` validates against these names and never treats a
value as a path. Phase 2 declares exactly one; Phase 3a adds the rest.

An app and a country are a sourced data point (the way `fixtures/anchors/`
carries platform URLs), never a name in prose. The developer fills `app_id`
before the first live fetch; a source left at 0 is refused before any request."""

from __future__ import annotations

from dataclasses import dataclass

FEED_HOST = "itunes.apple.com"


@dataclass(frozen=True)
class AppStoreSource:
    """One app's public customer-reviews feed on one country storefront."""

    name: str  # the SOURCE value and the capture directory; letters, digits, '-'
    app_id: int  # 0 = not filled in yet; the fetcher refuses it
    country: str  # two-letter storefront code

    @property
    def host(self) -> str:
        return FEED_HOST

    def page_url(self, page: int) -> str:
        """The feed address for one page — also the row's `source_url`."""
        return (
            f"https://{FEED_HOST}/{self.country}/rss/customerreviews/"
            f"id={self.app_id}/sortBy=mostRecent/page={page}/json"
        )

    @property
    def robots_url(self) -> str:
        return f"https://{FEED_HOST}/robots.txt"


# The studied segment's first app. `app_id` is filled by the developer at build
# (it is a number in a data declaration, not a name — CLAUDE.md -> Neutrality).
SOURCES: tuple[AppStoreSource, ...] = (
    AppStoreSource(name="fr-digital-first", app_id=0, country="fr"),
)


def source_names() -> tuple[str, ...]:
    return tuple(s.name for s in SOURCES)


def by_name(name: str) -> AppStoreSource:
    for s in SOURCES:
        if s.name == name:
            return s
    raise KeyError(name)
