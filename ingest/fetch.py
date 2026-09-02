"""The fetcher — the ONLY `httpx` import in the repo (spec Phase 2, invariant
6). Developer-run through `make scrape CONFIRM=yes`; never called by CI, a
test, or a rebuild.

httpx is a small HTTP client; the manners are ours, from `politeness.py`: read
`robots.txt` first and stop on a disallow, send the identifying User-Agent,
keep >= MIN_INTERVAL_S between requests to a host, contact only ALLOWED_HOSTS,
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
import urllib.robotparser
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ingest.app_store import FeedShapeError, parse_page
from ingest.politeness import (
    ALLOWED_HOSTS,
    MAX_PAGES,
    MIN_INTERVAL_S,
    TIMEOUT_S,
    USER_AGENT,
)
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

    def get(self, url: str) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise FetchRefused(f"refusing: host {host!r} is not in {ALLOWED_HOSTS}")
        last = self._last.get(host)
        if last is not None:
            wait = MIN_INTERVAL_S - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise FetchRefused(f"refusing: {url}: {type(exc).__name__}") from exc
        finally:
            self._last[host] = self._clock()
        return response


def robots_allows(text: str, url: str) -> bool:
    """stdlib robots parsing; our product token is what the file is matched on."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(USER_AGENT, url)


def _write_page(
    capture_dir: Path, page: int, response: httpx.Response, captured_at: str
) -> None:
    (capture_dir / f"page-{page}.json").write_bytes(response.content)
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
    unfilled source, a robots disallow, or any non-200; pages already written
    stay — each is a complete, honest capture of what the site served."""
    if source.app_id == 0:
        raise FetchRefused(
            f"refusing: source {source.name!r} has no app_id — "
            "fill it in ingest/sources.py"
        )
    polite = client or PoliteClient(make_client())
    captured_at = stamp()
    capture_dir = cache_root / source.name / captured_at.replace(":", "-")
    capture_dir.mkdir(parents=True, exist_ok=False)

    robots = polite.get(source.robots_url)
    (capture_dir / "robots.txt").write_bytes(robots.content)
    if robots.status_code == 200:
        allowed = robots_allows(robots.text, source.page_url(1))
    elif robots.status_code == 404:
        allowed = True  # no robots file: nothing is disallowed
    else:
        raise FetchRefused(f"refusing: robots.txt returned {robots.status_code}")
    if not allowed:
        raise FetchRefused(f"refusing: robots.txt disallows {source.page_url(1)}")

    written = 0
    for page in range(1, MAX_PAGES + 1):
        url = source.page_url(page)
        response = polite.get(url)
        if response.status_code != 200:
            raise FetchRefused(f"refusing: {url} returned {response.status_code}")
        _write_page(capture_dir, page, response, captured_at)
        written += 1
        try:
            rows = parse_page(response.content, url, captured_at)
        except FeedShapeError as exc:
            raise FetchRefused(f"refusing: {exc}") from exc
        if not rows:
            break  # the end of the feed
    return capture_dir, written
