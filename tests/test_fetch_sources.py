"""The fetcher over declarations other than the feed (spec Phase 3a, invariants
3 and 5): a listing source is robots then one page, archived with the parser's
extension; two hosts keep two clocks; a source declared not fetchable is refused
before any request whatever its robots file says."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ingest.captures import read_captures
from ingest.fetch import FetchRefused, PoliteClient, make_client, scrape
from ingest.listing import SAMPLE_DIR
from ingest.sources import Source, app_store_source, by_name
from tests import pins
from tests.test_app_store_fetch import Clock

STAMP = "2026-09-02T10:00:00"
LISTING = Source(
    name="test-listing",
    platform="google-play",
    host="play.google.com",
    parser="listing",
    pages=(
        "https://play.google.com/store/apps/details"
        "?id=example.fictional.app&hl=fr&gl=FR",
    ),
    profile="fr-digital-first",
    segment="digital-first",
    channel="invited",
    listing="https://play.google.com/store/apps/details?id=example.fictional.app",
    fetchable=True,
    declared_on="2026-09-01",
)
APP_STORE_SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"


class Sites:
    """Two hosts behind one transport: robots per host, the frozen samples as
    pages, and a request log."""

    def __init__(self, robots: dict[str, str] | None = None) -> None:
        self.robots = robots or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path = request.url.host, request.url.path
        if path == "/robots.txt":
            text = self.robots.get(host, "User-agent: *\nDisallow:\n")
            return httpx.Response(200, text=text)
        if host == "play.google.com":
            return httpx.Response(
                200, content=(SAMPLE_DIR / "page-1.html").read_bytes()
            )
        page = int(path.rsplit("page=", 1)[1].split("/")[0])
        n = min(page, pins.APP_STORE_SAMPLE_PAGES)
        return httpx.Response(
            200, content=(APP_STORE_SAMPLE / f"page-{n}.json").read_bytes()
        )

    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]


def _polite(sites: Sites, clock: Clock) -> PoliteClient:
    return PoliteClient(
        make_client(httpx.MockTransport(sites)), sleep=clock.sleep, clock=clock.now
    )


def test_a_listing_source_fetches_robots_then_one_page_and_archives_both(tmp_path):
    sites, clock = Sites(), Clock()
    capture, pages = scrape(
        LISTING, tmp_path, client=_polite(sites, clock), stamp=lambda: STAMP
    )
    assert sites.urls() == ["https://play.google.com/robots.txt", LISTING.page_url(1)]
    assert clock.sleeps == [2.0]
    assert capture == tmp_path / "google-play" / LISTING.name / STAMP.replace(":", "-")
    assert pages == 1
    assert (capture / "page-1.html").read_bytes() == (
        SAMPLE_DIR / "page-1.html"
    ).read_bytes()
    assert json.loads((capture / "page-1.meta.json").read_text()) == {
        "source_url": LISTING.page_url(1),
        "captured_at": STAMP,
        "status": 200,
    }
    ((capture_id, parsed),) = read_captures(
        tmp_path / "google-play" / LISTING.name, LISTING
    )
    assert capture_id == STAMP.replace(":", "-")
    assert parsed.reviews == [] and len(parsed.snapshots) == 1
    row = parsed.snapshots[0]
    assert (row["profile"], row["segment"], row["channel"], row["origin"]) == (
        "fr-digital-first",
        "digital-first",
        "invited",
        "fetch",
    )
    assert row["review_count"] == 1234 and row["captured_at"] == STAMP


def test_two_sources_on_two_hosts_keep_two_clocks(tmp_path):
    """The interval is per host: the second host's first request waits for
    nothing, and each host's own requests stay two seconds apart."""
    feed = app_store_source(
        name="feed",
        app_id=1,
        country="fr",
        listing="",
        fetchable=True,
        declared_on="2026-09-01",
    )
    sites, clock = Sites(), Clock()
    polite = _polite(sites, clock)
    scrape(feed, tmp_path, client=polite, stamp=lambda: STAMP)
    n_feed = len(sites.requests)
    scrape(LISTING, tmp_path, client=polite, stamp=lambda: STAMP)
    assert len(sites.requests) == n_feed + 2
    # feed: robots + pages, each after the first waits 2 s; listing: its robots
    # waited nothing (a new host), its page waited 2 s.
    assert clock.sleeps == [2.0] * (n_feed - 1) + [2.0]


def test_a_disallow_on_one_host_stops_that_source_only(tmp_path):
    sites = Sites(robots={"play.google.com": "User-agent: *\nDisallow: /store/\n"})
    polite = _polite(sites, Clock())
    with pytest.raises(FetchRefused, match="robots.txt disallows"):
        scrape(LISTING, tmp_path, client=polite, stamp=lambda: STAMP)
    feed = app_store_source(
        name="feed",
        app_id=1,
        country="fr",
        listing="",
        fetchable=True,
        declared_on="2026-09-01",
    )
    _, pages = scrape(feed, tmp_path, client=polite, stamp=lambda: STAMP)
    assert pages == pins.APP_STORE_SAMPLE_PAGES
    assert LISTING.page_url(1) not in sites.urls()


def test_a_review_page_source_stops_at_the_first_page_with_no_review(tmp_path):
    """The profile has three declared pages in the sample's shape and a fourth
    declared but never asked for: page 3 holds the aggregate and no review, so
    the fetcher stops there (Phase 3a, pinned decision 4)."""
    from ingest.opinion_assurances import SAMPLE_DIR as OA
    from ingest.sources import profile_pages

    base = "https://www.opinion-assurances.fr/assureur-exemple-fictif.html"
    profile = Source(
        name="test-profile",
        platform="opinion-assurances",
        host="www.opinion-assurances.fr",
        parser="opinion_assurances",
        pages=profile_pages(base, 6),
        profile="fr-digital-first",
        segment="digital-first",
        channel="unsolicited",
        listing=base,
        fetchable=True,
        declared_on="2026-09-01",
    )

    def site(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /*?*\n")
        n = 1 if request.url.path.endswith("fictif.html") else int(request.url.path[-6])
        n = min(n, pins.OA_SAMPLE_PAGES)
        return httpx.Response(200, content=(OA / f"page-{n}.html").read_bytes())

    urls: list[str] = []

    def logged(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return site(request)

    polite = PoliteClient(
        make_client(httpx.MockTransport(logged)), sleep=lambda s: None
    )
    capture, pages = scrape(profile, tmp_path, client=polite, stamp=lambda: STAMP)
    assert pages == pins.OA_SAMPLE_PAGES  # 1, 2 and the empty 3; never 4
    assert urls == [profile.robots_url] + list(profile.pages[:3])
    ((_, parsed),) = read_captures(tmp_path / profile.platform / profile.name, profile)
    assert len(parsed.reviews) == sum(
        pins.OA_SAMPLE_REVIEWS_ON_PAGES
    )  # before the guard
    # pages 1 and 2 both carry the aggregate; the capture yields ONE snapshot
    # row, page 1's (round 1, code-reviewer: a moving figure lands once)
    assert [r["source_url"] for r in parsed.snapshots] == [profile.page_url(1)]
    assert all(r["title"] == "" for r in parsed.reviews)


def test_a_non_fetchable_source_is_refused_before_any_request_whatever_robots_says(
    tmp_path,
):
    """The App Store listing: robots allows the path, the site's terms do not;
    the declaration decides, and nothing is asked."""
    declared = by_name("fr-digital-first-app-store-listing")
    assert declared.fetchable is False and declared.parser is None
    sites = Sites()
    with pytest.raises(FetchRefused, match="not fetchable — Apple website terms"):
        scrape(declared, tmp_path, client=_polite(sites, Clock()), stamp=lambda: STAMP)
    assert sites.requests == []
    assert not (tmp_path / declared.platform).exists()


def test_a_listing_page_outside_the_shape_is_kept_as_evidence_and_never_loaded(
    tmp_path,
):
    def two_blocks(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow:\n")
        body = (SAMPLE_DIR / "page-1.html").read_text()
        block = body[body.index("<script") : body.index("</script>") + 9]
        return httpx.Response(200, text=body.replace("</head>", block + "</head>"))

    polite = PoliteClient(
        make_client(httpx.MockTransport(two_blocks)), sleep=lambda s: None
    )
    with pytest.raises(FetchRefused, match="appears 2 times"):
        scrape(LISTING, tmp_path, client=polite, stamp=lambda: STAMP)
    capture = tmp_path / "google-play" / LISTING.name / STAMP.replace(":", "-")
    assert (capture / "page-1.refused.html").exists()
    assert not (capture / "page-1.html").exists()
    assert read_captures(tmp_path / "google-play" / LISTING.name, LISTING) == []
