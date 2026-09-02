"""The fetcher's manners (spec Phase 2, invariant 5; done-when 1), exercised
against `httpx.MockTransport` — no socket is opened (conftest blocks them). The
transport serves the frozen sample and records every request, so the tests
can say what was asked, in what order, how far apart, and with which headers."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ingest.captures import read_captures
from ingest.fetch import FetchRefused, PoliteClient, make_client, scrape
from ingest.politeness import MAX_PAGES, USER_AGENT
from ingest.sources import app_store_source, by_name
from tests import pins

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "app-store"
SRC = app_store_source(
    name="test-source",
    app_id=1,
    country="fr",
    listing="https://apps.apple.com/fr/app/id1",
    fetchable=True,
)
STAMP = "2026-09-02T10:00:00"
CAPTURE = Path(SRC.platform) / SRC.name / STAMP.replace(":", "-")  # under a cache root


class Served:
    """A scripted server: robots text, a status per page, and a request log."""

    def __init__(self, robots: str = "User-agent: *\nDisallow:\n", robots_status=200):
        self.robots = robots
        self.robots_status = robots_status
        self.page_status: dict[int, int] = {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(self.robots_status, text=self.robots)
        page = int(path.rsplit("page=", 1)[1].split("/")[0])
        status = self.page_status.get(page, 200)
        if status != 200:
            return httpx.Response(status, text="no")
        n = min(page, pins.APP_STORE_SAMPLE_PAGES)  # past page 3 the sample ends
        return httpx.Response(200, content=(SAMPLE / f"page-{n}.json").read_bytes())

    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]


class Clock:
    """A clock that only moves when told; `sleep` is recorded, not slept."""

    def __init__(self) -> None:
        self.t = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _polite(server: Served, clock: Clock) -> PoliteClient:
    client = make_client(httpx.MockTransport(server))
    return PoliteClient(client, sleep=clock.sleep, clock=clock.now)


def test_make_client_sets_our_manners():
    client = make_client(httpx.MockTransport(Served()))
    assert client.headers["User-Agent"] == USER_AGENT
    assert client.trust_env is False  # HTTP(S)_PROXY from the environment ignored
    assert client.follow_redirects is False


def test_robots_disallow_refuses_before_any_feed_request(tmp_path):
    server = Served(robots="User-agent: *\nDisallow: /fr/rss/\n")
    with pytest.raises(FetchRefused, match="robots.txt disallows"):
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.urls() == ["https://itunes.apple.com/robots.txt"]
    capture = tmp_path / CAPTURE
    assert (capture / "robots.txt").read_text() == server.robots
    assert not list(capture.glob("page-*"))


def test_the_live_hosts_wildcard_rule_refuses_before_any_feed_request(tmp_path):
    """The rule the host publishes (`Disallow: /*/rss/*`), against the path the
    fetcher asks for: refused after robots.txt, no feed page requested."""
    server = Served(robots="User-agent: *\nDisallow: /*/rss/*\n")
    with pytest.raises(FetchRefused, match="robots.txt disallows"):
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.urls() == ["https://itunes.apple.com/robots.txt"]


def test_every_page_is_checked_against_robots_before_its_own_request(tmp_path):
    """Page 1 allowed, page 2 disallowed: page 1 is fetched and kept, page 2
    is never asked for."""
    server = Served(robots="User-agent: *\nDisallow: /*/page=2/*\n")
    with pytest.raises(FetchRefused, match="disallows .*page=2/json"):
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.urls() == ["https://itunes.apple.com/robots.txt", SRC.page_url(1)]
    capture = tmp_path / CAPTURE
    assert (capture / "page-1.json").exists()


def test_a_longer_crawl_delay_lengthens_the_wait_and_a_shorter_one_does_not(tmp_path):
    server, clock = Served(robots="User-agent: *\nDisallow:\nCrawl-delay: 5\n"), Clock()
    scrape(SRC, tmp_path / "a", client=_polite(server, clock), stamp=lambda: STAMP)
    assert clock.sleeps == [5.0] * (len(server.requests) - 1)
    short = "User-agent: *\nDisallow:\nCrawl-delay: 0.1\n"
    server, clock = Served(robots=short), Clock()
    scrape(SRC, tmp_path / "b", client=_polite(server, clock), stamp=lambda: STAMP)
    assert clock.sleeps == [2.0] * (len(server.requests) - 1)


def test_a_crawl_delay_above_the_ceiling_is_a_one_line_refusal(tmp_path):
    """A host asking for more than MAX_CRAWL_DELAY_S between requests is refused
    after robots.txt, with no feed page asked for and no day-long sleep."""
    server, clock = (
        Served(robots="User-agent: *\nDisallow:\nCrawl-delay: 86400\n"),
        Clock(),
    )
    with pytest.raises(FetchRefused, match="Crawl-delay of 86400.0 s") as exc:
        scrape(SRC, tmp_path, client=_polite(server, clock), stamp=lambda: STAMP)
    assert "\n" not in str(exc.value)
    assert server.urls() == ["https://itunes.apple.com/robots.txt"]
    assert clock.sleeps == []


class _RobotsAs:
    """A server whose robots.txt answer has a chosen body and content-type;
    feed pages come from the sample. Logs every request."""

    def __init__(self, body: bytes, content_type: str | None) -> None:
        self.body, self.content_type = body, content_type
        self.urls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        if request.url.path == "/robots.txt":
            headers = (
                {} if self.content_type is None else {"content-type": self.content_type}
            )
            return httpx.Response(200, content=self.body, headers=headers)
        return httpx.Response(200, content=(SAMPLE / "page-3.json").read_bytes())


NOT_ROBOTS = (
    b'<!doctype html><html><a href="https://x/y">x</a>'
    b'<p style="color: red">?</p></html>',
    b'{"error": "not found", "status": 404}',
    b"Service Unavailable",
    b"Error: 503 backend unavailable",  # colon-bearing, no User-agent line
    b"Disallow: /\n",
    b"Disallow: /*/rss/*\nUser-agent: *\nDisallow:\n",  # a rule before the first group
)
CONTENT_TYPES = ("text/plain; charset=utf-8", "text/html", None)


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
@pytest.mark.parametrize("body", NOT_ROBOTS)
def test_a_200_whose_body_is_not_a_robots_file_refuses_before_any_feed_request(
    tmp_path, body, content_type
):
    """A6: the body alone decides; the content-type is recorded, never trusted.
    An HTML page (with colons in it), a JSON error, a plain-text error and a
    rule before any group each refuse under text/plain, text/html and no
    content-type alike, with only /robots.txt requested."""
    server = _RobotsAs(body, content_type)
    polite = PoliteClient(
        make_client(httpx.MockTransport(server)), sleep=lambda s: None
    )
    with pytest.raises(FetchRefused, match="body is not a robots file") as exc:
        scrape(SRC, tmp_path, client=polite, stamp=lambda: STAMP)
    assert "\n" not in str(exc.value)
    assert server.urls == ["https://itunes.apple.com/robots.txt"]
    capture = tmp_path / CAPTURE
    meta = json.loads((capture / "robots.meta.json").read_text())
    assert meta == {"status": 200, "content_type": content_type or ""}
    assert (capture / "robots.txt").read_bytes() == body


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
@pytest.mark.parametrize(
    "body", [b"", b"Sitemap: https://h/s.xml\n", b"User-agent: *\nDisallow:\n"]
)
def test_a_body_that_reads_as_a_robots_file_is_obeyed_whatever_its_content_type(
    tmp_path, body, content_type
):
    """An empty file, a sitemap-only file and an allow-all file are robots files
    with no rule against us, under any content-type or none."""
    server = _RobotsAs(body, content_type)
    polite = PoliteClient(
        make_client(httpx.MockTransport(server)), sleep=lambda s: None
    )
    _, pages = scrape(SRC, tmp_path, client=polite, stamp=lambda: STAMP)
    assert pages == 1


def test_a_foreign_group_cannot_loosen_the_catch_all_in_the_fetcher(tmp_path):
    """End to end: `*` disallows the feed, a `study` group says nothing; the
    fetch is refused after robots.txt with no feed request (A6)."""
    server = Served(
        robots="User-agent: *\nDisallow: /*/rss/*\n\nUser-agent: study\nDisallow:\n"
    )
    with pytest.raises(FetchRefused, match="robots.txt disallows"):
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.urls() == ["https://itunes.apple.com/robots.txt"]


def test_a_source_declared_not_fetchable_is_refused_before_any_request(tmp_path):
    """Amendment A5(b): the recorded terms position lives in the declaration;
    the declared source refuses with its reason, whatever robots.txt would say
    today, and nothing is asked of the site."""
    declared = by_name("fr-digital-first")
    server = Served()
    with pytest.raises(FetchRefused, match="not fetchable — robots.txt disallows"):
        scrape(declared, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.requests == []
    assert not (tmp_path / declared.platform).exists()


def test_robots_error_status_is_a_refusal_and_404_is_not(tmp_path):
    with pytest.raises(FetchRefused, match="robots.txt returned 503"):
        scrape(
            SRC,
            tmp_path / "a",
            client=_polite(Served(robots_status=503), Clock()),
            stamp=lambda: STAMP,
        )
    server = Served(robots_status=404)
    _, pages = scrape(
        SRC, tmp_path / "b", client=_polite(server, Clock()), stamp=lambda: STAMP
    )
    assert pages == pins.APP_STORE_SAMPLE_PAGES


def test_every_request_carries_the_identifying_user_agent(tmp_path):
    server = Served()
    scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.requests
    assert all(r.headers["User-Agent"] == USER_AGENT for r in server.requests)


def test_consecutive_requests_are_spaced_two_seconds(tmp_path):
    """With a clock that does not advance on its own, every request after the
    first waits the full two seconds; the first waits nothing. The literal is
    deliberate: pinned to MIN_INTERVAL_S, a shorter constant would pass."""
    server, clock = Served(), Clock()
    scrape(SRC, tmp_path, client=_polite(server, clock), stamp=lambda: STAMP)
    n = len(server.requests)
    assert n == 1 + pins.APP_STORE_SAMPLE_PAGES  # robots + three pages
    assert clock.sleeps == [2.0] * (n - 1)


def test_a_slow_response_does_not_shorten_the_gap(tmp_path):
    """The interval is measured from the END of the previous request: a server
    that took 1.5 s to answer still gets the full two seconds after it did."""
    clock = Clock()

    def slow(request: httpx.Request) -> httpx.Response:
        clock.t += 1.5
        return httpx.Response(200, text="User-agent: *\nDisallow:\n")

    polite = PoliteClient(
        make_client(httpx.MockTransport(slow)), sleep=clock.sleep, clock=clock.now
    )
    polite.get("https://itunes.apple.com/robots.txt")
    polite.get("https://itunes.apple.com/robots.txt")
    assert clock.sleeps == [pytest.approx(2.0)]


def test_pages_are_archived_byte_exact_with_meta(tmp_path):
    server = Served()
    capture, pages = scrape(
        SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP
    )
    assert capture == tmp_path / CAPTURE
    assert pages == pins.APP_STORE_SAMPLE_PAGES
    for n in range(1, pages + 1):
        assert (capture / f"page-{n}.json").read_bytes() == (
            SAMPLE / f"page-{n}.json"
        ).read_bytes()
        meta = json.loads((capture / f"page-{n}.meta.json").read_text())
        assert meta == {
            "source_url": SRC.page_url(n),
            "captured_at": STAMP,
            "status": 200,
        }
    assert (capture / "robots.txt").read_text() == server.robots
    robots_meta = json.loads((capture / "robots.meta.json").read_text())
    assert robots_meta == {"status": 200, "content_type": "text/plain; charset=utf-8"}


def test_stops_at_the_end_of_the_feed_and_never_beyond_max_pages(tmp_path):
    server = Served()
    scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert SRC.page_url(pins.APP_STORE_SAMPLE_PAGES + 1) not in server.urls()
    assert len(server.requests) - 1 <= MAX_PAGES


def test_non_200_is_a_one_line_refusal_with_no_retry(tmp_path):
    server = Served()
    server.page_status[2] = 429
    with pytest.raises(FetchRefused, match="page=2/json returned 429") as exc:
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert "\n" not in str(exc.value)
    assert server.urls().count(SRC.page_url(2)) == 1  # asked once, never again
    assert SRC.page_url(3) not in server.urls()
    capture = tmp_path / CAPTURE
    assert (capture / "page-1.json").exists()  # what was served stays
    assert not (capture / "page-2.json").exists()


def test_a_refused_robots_request_leaves_no_capture_directory(tmp_path):
    """A run that never got an answer from the site writes nothing: no empty
    capture directory for `read_captures` to step over."""

    def failing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    polite = PoliteClient(
        make_client(httpx.MockTransport(failing)), sleep=lambda s: None
    )
    with pytest.raises(FetchRefused, match="ConnectTimeout"):
        scrape(SRC, tmp_path, client=polite, stamp=lambda: STAMP)
    assert not (tmp_path / SRC.platform).exists()


def test_transport_error_is_a_refusal_not_a_retry():
    calls = 0

    def failing(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("slow", request=request)

    polite = PoliteClient(
        make_client(httpx.MockTransport(failing)), sleep=lambda s: None
    )
    with pytest.raises(FetchRefused, match="ConnectTimeout"):
        polite.get("https://itunes.apple.com/robots.txt")
    assert calls == 1


def test_host_outside_the_allowlist_is_refused_before_any_request():
    server = Served()
    polite = _polite(server, Clock())
    with pytest.raises(FetchRefused, match="host 'example.com' is not in"):
        polite.get("https://example.com/fr/rss/customerreviews/id=1/page=1/json")
    assert server.requests == []


def test_unfilled_source_is_refused_before_any_request(tmp_path):
    server = Served()
    unfilled = app_store_source(
        name="blank", app_id=0, country="fr", listing="", fetchable=True
    )
    with pytest.raises(FetchRefused, match="has no page address"):
        scrape(unfilled, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.requests == []
    assert not (tmp_path / "app-store").exists()


def test_a_malformed_page_is_kept_under_a_name_no_rebuild_loads(tmp_path):
    """Fix amendment A3: the page is archived as evidence, the run is refused,
    and a later rebuild over the capture loads nothing from it and refuses
    nothing — no poison page."""

    def bad_page(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow:\n")
        return httpx.Response(200, content=b'{"feed": {"entry": {"not": "a list"}}}')

    polite = PoliteClient(
        make_client(httpx.MockTransport(bad_page)), sleep=lambda s: None
    )
    with pytest.raises(FetchRefused, match="'entry' is dict, not a list"):
        scrape(SRC, tmp_path, client=polite, stamp=lambda: STAMP)
    capture = tmp_path / CAPTURE
    assert (capture / "page-1.refused.json").exists()  # evidence of what was served
    assert not (capture / "page-1.json").exists()
    assert (capture / "page-1.meta.json").exists()
    assert read_captures(tmp_path, SRC) == []


def test_an_existing_capture_directory_is_a_refusal_not_a_traceback(tmp_path):
    """Two runs stamped in the same second would share a directory; the second
    refuses with one line and asks nothing of the site."""
    server = Served()
    (tmp_path / CAPTURE).mkdir(parents=True)
    with pytest.raises(FetchRefused, match="already exists"):
        scrape(SRC, tmp_path, client=_polite(server, Clock()), stamp=lambda: STAMP)
    assert server.requests == []
