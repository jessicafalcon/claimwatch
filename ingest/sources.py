"""The declared sources — a closed tuple (spec Phase 2, pinned decision 1;
Phase 3a, pinned decision 3). Each thing we read from is declared once, here:
which platform, which host, which parser reads its pages, which page addresses
it has (the closed set a row's `source_url` can take), which cache directory
its captures go to, which profile / segment / channel its rows belong to, and
whether its site lets us fetch it. Every other module reads those facts from
the declaration; none knows a platform by name.

An app, a storefront or a profile is a sourced data point. Where an address
spells the brand (a store package id, a profile path) it sits in this file and
nowhere else (decision D1): no prose, comment, commit, test name or fixture
repeats it. A source declared not fetchable states its reason — the robots rule
or the terms clause, with the date it was read — and is refused before any
request, whatever its robots file says on a later day."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ingest.politeness import MAX_PAGES

ROOT = Path(__file__).resolve().parent.parent
# The one binding of the cache root (closes the BACKLOG row "DEFAULT_CACHE is
# bound in two modules"): a source's captures live under
# CACHE_ROOT / <platform> / <source name> / <captured_at>/ — gitignored (data/*).
CACHE_ROOT = ROOT / "data" / "cache"

SEGMENTS = ("digital-first", "traditional", "digital-challenger")
CHANNELS = ("invited", "unsolicited")
ORIGINS = ("anchor", "manual", "fetch")  # how a snapshot row came to be
# The parsers, by module name under `ingest/` — a closed set; each module
# exposes parse(), EXTENSION, SAMPLE_PLATFORM, SAMPLE_HOST, SAMPLE_DIR.
PARSERS = ("app_store", "listing", "opinion_assurances")
SAMPLE = "sample"  # the name and attribution of a frozen sample's declaration

_SLUG = re.compile(r"^[a-z0-9-]+$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
FEED_HOST = "itunes.apple.com"
# The strings that spell the studied insurer (D1), one per form the
# declarations below carry: the bare name (a profile path), the package id's
# segment (the name with a suffix, which a whole-word walk for the bare name
# cannot match — round 2, security-reviewer #3) and the store id. This file
# is the one place they may appear; a test walks every tracked file for them,
# as words, and fails on any other hit — the guard is mechanical, not a
# reading. A new source that spells the brand in a new form adds its form
# here, in the same commit; a test pins that every form the declarations
# carry is declared (the store id stands bare in the feed address and as
# `id<store id>` in the listing address: two forms, two tokens).
BRAND_TOKENS = ("alan", "alanmobile", "1277025964", "id1277025964")


@dataclass(frozen=True)
class Source:
    """One thing we read from, declared in full."""

    name: str  # the SOURCE value and the capture directory; letters, digits, '-'
    platform: str  # the `source` column: app-store, google-play, opinion-assurances
    host: str  # the only host this source's pages live on
    parser: str | None  # one of PARSERS; None = snapshots hand-entered only
    pages: tuple[str, ...]  # every page address, in order; () = not filled in yet
    profile: str  # whose figures these are: the studied insurer or a peer
    segment: str  # SEGMENTS
    channel: str  # CHANNELS
    listing: str  # the address the id or figure is read from (D1: here only)
    fetchable: bool  # the recorded terms position; False is refused before any request
    declared_on: str  # the real day (YYYY-MM-DD) the declaration was recorded
    terms: str = ""  # why, when not fetchable — a reason and a date, never a name
    # The frozen samples' declaration, and only it (A3 (b)): a property, not a
    # name, so the closed-set check on segment and channel keys on it — the
    # literal `sample` exists only in the samples database.
    sample: bool = False

    def __post_init__(self) -> None:
        if not _SLUG.match(self.name) or not _SLUG.match(self.platform):
            raise ValueError(f"source {self.name!r}: name and platform are slugs")
        if self.parser is not None and self.parser not in PARSERS:
            raise ValueError(
                f"source {self.name!r}: parser {self.parser!r} not in {PARSERS}"
            )
        if len(self.pages) > MAX_PAGES:
            raise ValueError(
                f"source {self.name!r}: {len(self.pages)} pages > {MAX_PAGES}"
            )
        if not self.fetchable and not self.terms.strip():
            raise ValueError(f"source {self.name!r}: fetchable=False needs terms")
        if self.fetchable and self.parser is None:
            raise ValueError(f"source {self.name!r}: a fetchable source needs a parser")
        if self.name == SAMPLE and not self.sample:
            raise ValueError(
                f"source {self.name!r}: the name is the sample declaration's; "
                "declare it with sample=True or choose another name"
            )
        if not self.sample and (
            self.segment not in SEGMENTS or self.channel not in CHANNELS
        ):
            raise ValueError(
                f"source {self.name!r}: segment in {SEGMENTS} and channel in {CHANNELS}"
            )
        # The day is provenance: it is written as `captured_at` on every page
        # address the declaration puts in raw_source_pages, so it is required
        # and must be a real day — never empty, never 2026-02-30.
        if not _DATE.match(self.declared_on):
            raise ValueError(f"source {self.name!r}: declared_on is YYYY-MM-DD")
        try:
            date.fromisoformat(self.declared_on)
        except ValueError as exc:
            raise ValueError(
                f"source {self.name!r}: declared_on is not a real day"
            ) from exc

    def page_url(self, page: int) -> str:
        """The address of page `page` (1-based) — also the row's `source_url`."""
        return self.pages[page - 1]

    @property
    def robots_url(self) -> str:
        return f"https://{self.host}/robots.txt"

    @property
    def cache_dir(self) -> Path:
        return CACHE_ROOT / self.platform / self.name


def app_store_source(
    name: str,
    app_id: int,
    country: str,
    listing: str,
    fetchable: bool,
    terms: str = "",
    *,
    declared_on: str,
    profile: str = "fr-digital-first",
    segment: str = "digital-first",
    channel: str = "invited",
) -> Source:
    """An app's public customer-reviews feed on one storefront (Phase 2's
    shape): ten pages at most, the feed's own cap. An app id of 0 is a source
    not filled in yet — no page address, refused before any request."""
    pages = tuple(
        f"https://{FEED_HOST}/{country}/rss/customerreviews/"
        f"id={app_id}/sortBy=mostRecent/page={n}/json"
        for n in range(1, 11)
    )
    return Source(
        name=name,
        platform="app-store",
        host=FEED_HOST,
        parser="app_store",
        pages=pages if app_id else (),
        profile=profile,
        segment=segment,
        channel=channel,
        listing=listing,
        fetchable=fetchable,
        declared_on=declared_on,
        terms=terms,
    )


def profile_pages(profile_url: str, pages: int) -> tuple[str, ...]:
    """An Opinion Assurances profile's pages: the profile itself, then
    `<profile>-page<n>.html` — the path form its robots file allows (every
    query-string address is disallowed there)."""
    assert profile_url.endswith(".html")
    stem = profile_url[: -len(".html")]
    return (profile_url,) + tuple(f"{stem}-page{n}.html" for n in range(2, pages + 1))


def sample_source(parser: str) -> Source:
    """The declaration a frozen sample is read under (`ROWS=samples`): its
    profile, segment and channel are the literal `sample` — labels that exist
    only in the samples database — and it is never fetched."""
    from ingest.captures import parser_module  # the closed-set lookup

    mod = parser_module(parser)
    return Source(
        name=SAMPLE,
        platform=mod.SAMPLE_PLATFORM,
        host=mod.SAMPLE_HOST,
        parser=parser,
        pages=(),
        profile=SAMPLE,
        segment=SAMPLE,
        channel=SAMPLE,
        listing="",
        fetchable=False,
        declared_on="2026-09-01",
        terms="a frozen sample, read from fixtures/, never fetched",
        sample=True,
    )


# The studied insurer's sources, each a sourced data point (an id and the
# address it was read from — never a name in prose; CLAUDE.md -> Neutrality;
# D1). Positions as checked on 2026-09-02 (DECISIONS -> Scrape politely).
SOURCES: tuple[Source, ...] = (
    # The App Store customer-reviews feed (Phase 2): the host's robots.txt
    # disallows the feed path for every crawler, so it is refused before any
    # request.
    app_store_source(
        name="fr-digital-first",
        app_id=1277025964,
        country="fr",
        listing="https://apps.apple.com/fr/app/id1277025964",
        fetchable=False,
        terms="robots.txt disallows /*/rss/* for every crawler (2026-09-02)",
        declared_on="2026-09-02",
    ),
    # The Google Play listing: allowed by the host's robots.txt (the catch-all
    # group disallows `/_`, `/store/getreviews` and `/store/xhr`, not the
    # details page) and by Google's terms, which forbid automated access only
    # where it breaches robots.txt. Its JSON-LD block carries the aggregate
    # rating. Its reviews load through the disallowed `/_` call and are never
    # fetched.
    Source(
        name="fr-digital-first-google-play-listing",
        platform="google-play",
        host="play.google.com",
        parser="listing",
        pages=(
            "https://play.google.com/store/apps/details?id=com.alanmobile&hl=fr&gl=FR",
        ),
        profile="fr-digital-first",
        segment="digital-first",
        channel="invited",
        listing="https://play.google.com/store/apps/details?id=com.alanmobile&hl=fr",
        fetchable=True,
        declared_on="2026-09-02",
    ),
    # The Opinion Assurances profile (A1): its robots.txt allows the profile
    # and its path-based pages; its conditions générales (V.3) forbid automated
    # extraction without prior written authorization — which the developer
    # holds (granted 2026-09-02), so the source is fetchable. Fourteen pages of
    # about forty reviews on 2026-09-02; the fetcher stops at the first page
    # with no review. The profile path spells the brand: D1, here only.
    Source(
        name="fr-digital-first-opinion-assurances",
        platform="opinion-assurances",
        host="www.opinion-assurances.fr",
        parser="opinion_assurances",
        pages=profile_pages("https://www.opinion-assurances.fr/assureur-alan.html", 14),
        profile="fr-digital-first",
        segment="digital-first",
        channel="unsolicited",
        listing="https://www.opinion-assurances.fr/assureur-alan.html",
        fetchable=True,
        terms=(
            "written authorization from the site, granted 2026-09-02 (its conditions"
            " générales V.3 forbid automated extraction without it)"
        ),
        declared_on="2026-09-02",
    ),
    # The App Store listing: allowed by robots.txt, forbidden by Apple's
    # website terms of use ("Your Use of the Site": no robot, spider,
    # page-scrape or automated means to access or copy the site). Its figures
    # are read by hand and entered in data/snapshots/manual_snapshots.csv.
    Source(
        name="fr-digital-first-app-store-listing",
        platform="app-store",
        host="apps.apple.com",
        parser=None,
        pages=(),
        profile="fr-digital-first",
        segment="digital-first",
        channel="invited",
        listing="https://apps.apple.com/fr/app/id1277025964",
        fetchable=False,
        terms=(
            "Apple website terms of use, 'Your Use of the Site': no robot, spider,"
            " page-scrape or automated means to access or copy the site (2026-09-02)"
        ),
        declared_on="2026-09-02",
    ),
)


def hand_entries_are_unique(sources: tuple[Source, ...]) -> None:
    """A hand-read row keys on its declaration's platform and listing address
    (A2), so two hand-entered sources (no parser) may not share them; an app's
    feed and its store listing share theirs by design and only the listing
    writes a snapshot from it. Checked when the tuple is declared."""
    seen: dict[tuple[str, str], str] = {}
    for s in sources:
        if s.parser is not None:
            continue
        key = (s.platform, s.listing)
        if key in seen:
            raise ValueError(
                f"sources {seen[key]!r} and {s.name!r} are both hand-entered on the "
                f"same platform and listing address"
            )
        seen[key] = s.name


hand_entries_are_unique(SOURCES)


def source_names() -> tuple[str, ...]:
    return tuple(s.name for s in SOURCES)


def by_name(name: str) -> Source:
    for s in SOURCES:
        if s.name == name:
            return s
    raise KeyError(name)


def fetchable_sources(sources: tuple[Source, ...] = SOURCES) -> tuple[Source, ...]:
    return tuple(s for s in sources if s.fetchable)
