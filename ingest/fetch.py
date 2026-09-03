"""The fetcher — the ONLY `httpx` import in the repo (spec Phase 2, invariant
6). Developer-run through `make confirm scrape`; never called by CI, a
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

`captured_at` is stamped here, once per source per run, in UTC as
YYYY-MM-DDTHH:MM:SS (the synthetic fixture's format); it names the capture
directory (colons replaced) and is written into every page's meta."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ingest.captures import parser_module
from ingest.parsed import PageShapeError
from ingest.politeness import (
    ALLOWED_HOSTS,
    MAX_BYTES,
    MAX_CRAWL_DELAY_S,
    MAX_PAGES,
    MAX_RESPONSE_S,
    MIN_INTERVAL_S,
    TIMEOUT_S,
    USER_AGENT,
)
from ingest.robots import Robots, reads_as_robots
from ingest.sources import Source


class FetchRefused(Exception):
    """One line, exit 2, no retry: robots said no, a bad status, a timeout, a
    response past the size or duration ceiling, an unfilled source, or a host
    outside the allowed set."""


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
            with self._client.stream("GET", url) as streamed:
                body = self._read_bounded(streamed, url)
        except httpx.HTTPError as exc:
            raise FetchRefused(f"refusing: {url}: {type(exc).__name__}") from exc
        finally:
            self._last[host] = self._clock()
        # The body is already decoded, so the encoding and length headers of
        # the wire form are dropped; the rest (content-type) is kept as served.
        headers = [
            (k, v)
            for k, v in streamed.headers.items()
            if k.lower()
            not in ("content-encoding", "content-length", "transfer-encoding")
        ]
        return httpx.Response(
            streamed.status_code,
            headers=headers,
            content=body,
            request=streamed.request,
        )

    def _read_bounded(self, response: httpx.Response, url: str) -> bytes:
        """The body in pieces, refused the moment it passes MAX_BYTES or the
        clock passes MAX_RESPONSE_S since the first byte was asked for. TIMEOUT_S
        bounds each socket read; this bounds the whole answer, so a page that
        never ends or drips a byte at a time is a one-line refusal."""
        started = self._clock()
        size = 0
        pieces: list[bytes] = []
        for piece in response.iter_bytes():
            size += len(piece)
            if size > MAX_BYTES:
                raise FetchRefused(
                    f"refusing: {url}: the response passed {MAX_BYTES} bytes"
                )
            if self._clock() - started > MAX_RESPONSE_S:
                raise FetchRefused(
                    f"refusing: {url}: the response did not finish within "
                    f"{MAX_RESPONSE_S} s"
                )
            pieces.append(piece)
        return b"".join(pieces)


def polite_client() -> PoliteClient:
    """The one client for a whole `make scrape`: every source in the run shares
    its per-host clock, so two sources on one host are still >= 2 s apart."""
    return PoliteClient(make_client())


def _write_page(
    capture_dir: Path,
    page: int,
    response: httpx.Response,
    captured_at: str,
    ext: str,
    *,
    refused: bool = False,
) -> None:
    """A page the strict parser accepted is `page-<n>.<ext>` (the parser's
    extension); one it refused is kept as evidence under
    `page-<n>.refused.<ext>`, a name no rebuild loads."""
    name = f"page-{page}.refused.{ext}" if refused else f"page-{page}.{ext}"
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
    source: Source,
    cache_root: Path,
    *,
    client: PoliteClient | None = None,
    stamp: Callable[[], str] = utc_stamp,
) -> tuple[Path, int]:
    """Fetch one source's pages into a new capture directory under
    `cache_root / platform / name`. Returns the directory and the number of
    pages written. Everything — host, robots address, page addresses, cap,
    parser — is read from the declaration (Phase 3a, pinned decision 3).
    Refuses (one line) on a source declared not fetchable, an unfilled source,
    a robots disallow, any non-200, or a page that is not the declared shape;
    pages already written stay — each is a complete, honest capture of what the
    site served — and a refused page is kept under a name a rebuild never
    loads."""
    if not source.fetchable:  # the recorded terms position, declared in code
        raise FetchRefused(
            f"refusing: source {source.name!r} is declared not fetchable — "
            f"{source.terms}"
        )
    if not source.pages or source.parser is None:
        raise FetchRefused(
            f"refusing: source {source.name!r} has no page address — "
            "fill it in ingest/sources.py"
        )
    parser = parser_module(source.parser)
    if client is None:
        own = polite_client()
        try:
            return scrape(source, cache_root, client=own, stamp=stamp)
        finally:
            own.close()
    polite = client
    captured_at = stamp()
    capture_dir = (
        cache_root / source.platform / source.name / captured_at.replace(":", "-")
    )
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
    content_type = robots.headers.get("content-type", "")
    (capture_dir / "robots.meta.json").write_text(  # why the run proceeded (A6)
        json.dumps(
            {"status": robots.status_code, "content_type": content_type}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    if robots.status_code == 200:
        # The body alone decides whether this is a robots file; the content-type
        # is recorded, never trusted. An error page served with a 200 is a
        # refusal, never permission (A6).
        if not reads_as_robots(robots.text):
            raise FetchRefused(
                f"refusing: robots.txt returned 200 but its body is not a robots file "
                f"(content-type {content_type.split(';')[0].strip() or 'none'!r})"
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
    for page, url in enumerate(source.pages[:MAX_PAGES], 1):
        if not rules.allows(url):  # every page's own address, before its request
            raise FetchRefused(f"refusing: robots.txt disallows {url}")
        response = polite.get(url)
        if response.status_code != 200:
            raise FetchRefused(f"refusing: {url} returned {response.status_code}")
        try:
            parsed = parser.parse(response.content, url, captured_at, source)
        except PageShapeError as exc:
            _write_page(
                capture_dir, page, response, captured_at, parser.EXTENSION, refused=True
            )
            raise FetchRefused(f"refusing: {exc}") from exc
        _write_page(capture_dir, page, response, captured_at, parser.EXTENSION)
        written += 1
        if parsed.is_empty():
            break  # the end of the list
    return capture_dir, written
