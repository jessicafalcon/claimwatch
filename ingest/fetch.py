"""The fetcher — the ONLY `httpx` import in the repo (spec Phase 2, invariant
6). Developer-run through `make scrape CONFIRM=yes`; never called by CI, a
test, or a rebuild.

httpx is a small HTTP client; the manners are ours, from `politeness.py`: read
`robots.txt` first (matched by `robots.py`, RFC 9309) and check every page's
address against it before that page is asked for, send the identifying
User-Agent, keep >= MIN_INTERVAL_S between requests to a host (more if the
robots file asks for a longer Crawl-delay), contact only ALLOWED_HOSTS,
make one request per page with no retry, and never use a proxy (`trust_env=
False` ignores HTTP(S)_PROXY). Every page is archived byte-exact under the
capture directory with its provenance beside it, so a rebuild reads no clock
and asks the site nothing.

`captured_at` is stamped here, once per run, in UTC as YYYY-MM-DDTHH:MM:SS (the
synthetic fixture's format); it names the capture directory (colons replaced)
and is written into every page's meta."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ingest.app_store import FeedShapeError, parse_page
from ingest.politeness import (
    ALLOWED_HOSTS,
    MAX_CRAWL_DELAY_S,
    MAX_PAGES,
    MIN_INTERVAL_S,
    TIMEOUT_S,
    USER_AGENT,
)
from ingest.robots import Robots, looks_like_robots
from ingest.sources import AppStoreSource


class FetchRefused(Exception):
    """One line, exit 2, no retry: robots said no, a bad status, a timeout, an
    unfilled source, or a host outside the allowed set."""


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """The one client shape: our User-Agent, our timeout, no proxy from the
    environment, no redirects followed silently."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_S,
        trust_env=False,
        follow_redirects=False,
        transport=transport,
    )


class PoliteClient:
    """Wraps an httpx client with the host allowlist and the per-host interval.
    `sleep` and `clock` are injectable so tests measure the spacing without
    waiting."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._interval: dict[str, float] = {}  # per host, never below the minimum

    def raise_interval(self, host: str, seconds: float) -> None:
        """A host's Crawl-delay lengthens our wait for that host; it never
        shortens it below MIN_INTERVAL_S."""
        self._interval[host] = max(self._interval.get(host, MIN_INTERVAL_S), seconds)

    def close(self) -> None:
        self._client.close()

    def get(self, url: str) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise FetchRefused(f"refusing: host {host!r} is not in {ALLOWED_HOSTS}")
        last = self._last.get(host)
        if last is not None:
            wait = self._interval.get(host, MIN_INTERVAL_S) - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise FetchRefused(f"refusing: {url}: {type(exc).__name__}") from exc
        finally:
            self._last[host] = self._clock()
        return response


def polite_client() -> PoliteClient:
    """The one client for a whole `make scrape`: every source in the run shares
    its per-host clock, so two sources on one host are still >= 2 s apart."""
    return PoliteClient(make_client())


def _write_page(
    capture_dir: Path,
    page: int,
    response: httpx.Response,
    captured_at: str,
    *,
    refused: bool = False,
) -> None:
    """A page the strict parser accepted is `page-<n>.json`; one it refused is
    kept as evidence under `page-<n>.refused.json`, a name no rebuild loads."""
    name = f"page-{page}.refused.json" if refused else f"page-{page}.json"
    (capture_dir / name).write_bytes(response.content)
    meta = {
        "source_url": str(response.request.url),
        "captured_at": captured_at,
        "status": response.status_code,
    }
    (capture_dir / f"page-{page}.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


def scrape(
    source: AppStoreSource,
    cache_root: Path,
    *,
    client: PoliteClient | None = None,
    stamp: Callable[[], str] = utc_stamp,
) -> tuple[Path, int]:
    """Fetch one source's feed into a new capture directory. Returns the
    directory and the number of pages written. Refuses (one line) on an
    unfilled source, a robots disallow, any non-200, or a page that is not the
    declared shape; pages already written stay — each is a complete, honest
    capture of what the site served — and a refused page is kept under a name
    a rebuild never loads."""
    if not source.fetchable:  # the recorded terms position, declared in code
        raise FetchRefused(
            f"refusing: source {source.name!r} is declared not fetchable — "
            f"{source.terms}"
        )
    if source.app_id == 0:
        raise FetchRefused(
            f"refusing: source {source.name!r} has no app_id — "
            "fill it in ingest/sources.py"
        )
    if client is None:
        own = polite_client()
        try:
            return scrape(source, cache_root, client=own, stamp=stamp)
        finally:
            own.close()
    polite = client
    captured_at = stamp()
    capture_dir = cache_root / source.name / captured_at.replace(":", "-")
    if capture_dir.exists():
        raise FetchRefused(
            f"refusing: capture {capture_dir} already exists (same second?)"
        )

    # Nothing is written until the site has answered: a run refused at the
    # robots request leaves no directory behind.
    robots = polite.get(source.robots_url)
    try:
        capture_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FetchRefused(
            f"refusing: capture {capture_dir} already exists (same second?)"
        ) from exc
    (capture_dir / "robots.txt").write_bytes(robots.content)
    if robots.status_code == 200:
        # A 200 is a robots file only if it says so (text/plain) or reads as one;
        # a catch-all page served with a 200 is a refusal, never permission.
        ctype = robots.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "text/plain" and not looks_like_robots(robots.text):
            raise FetchRefused(
                f"refusing: robots.txt returned 200 but is not a robots file "
                f"(content-type {ctype or 'none'!r})"
            )
        rules = Robots.parse(robots.text)
    elif robots.status_code == 404:
        rules = Robots.permissive()  # no robots file: nothing is disallowed
    else:
        raise FetchRefused(f"refusing: robots.txt returned {robots.status_code}")
    if rules.crawl_delay is not None:
        if rules.crawl_delay > MAX_CRAWL_DELAY_S:
            raise FetchRefused(
                f"refusing: robots.txt asks for a Crawl-delay of {rules.crawl_delay} s,"
                f" above our {MAX_CRAWL_DELAY_S} s ceiling"
            )
        polite.raise_interval(source.host, rules.crawl_delay)

    written = 0
    for page in range(1, MAX_PAGES + 1):
        url = source.page_url(page)
        if not rules.allows(url):  # every page's own address, before its request
            raise FetchRefused(f"refusing: robots.txt disallows {url}")
        response = polite.get(url)
        if response.status_code != 200:
            raise FetchRefused(f"refusing: {url} returned {response.status_code}")
        try:
            rows = parse_page(response.content, url, captured_at)
        except FeedShapeError as exc:
            _write_page(capture_dir, page, response, captured_at, refused=True)
            raise FetchRefused(f"refusing: {exc}") from exc
        _write_page(capture_dir, page, response, captured_at)
        written += 1
        if not rows:
            break  # the end of the feed
    return capture_dir, written
