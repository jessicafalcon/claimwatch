"""Fetch one month of Open DAMIR into the gitignored cache — developer-run,
never by an agent (CLAUDE.md → paid/network commands; the CLI gates it behind
`make confirm fetch-damir`). A plain bulk download over stdlib `urllib`, so
`ingest/fetch.py` stays the only `httpx` import and no dependency is added.

Open DAMIR's monthly files hang off one data.gouv dataset with machine-named
(UUID) download URLs, so we resolve the month asked for by its `A<YYYYMM>`
title in the dataset's resource list, then stream that one file to
`data/cache/damir/`. No proxy, no evasion, no retry; an identifying
User-Agent; a re-fetch overwrites the same path. The file is large (a national
month is gigabytes) — this is why it is cached, never committed, and the small
frozen fixture is what CI fits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from ingest.politeness import IDENTIFYING_HEADERS, TIMEOUT_S
from opendata.sources import DATASET_API, cache_path, month_token, valid_month

# One opener with proxies disabled: the httpx crawler sets `trust_env=False` for
# the same reason (CLAUDE.md → Scraping, "no proxy"), and the urllib download
# must not silently route through an ambient `http(s)_proxy` either. Used for
# both the metadata GET and the file stream.
_OPENER = build_opener(ProxyHandler({}))

# Stream the file body a megabyte at a time — a national month is gigabytes, so
# it never lands in memory at once — and refuse a body that runs past the size
# the dataset declared (plus a small slack), rather than filling the disk.
_CHUNK = 1 << 20  # 1 MiB
_SLACK = 1 << 20  # 1 MiB over the declared size before we call it a runaway


class FetchError(Exception):
    """A one-line failure on the developer-run network path — a month with no
    matching resource, or a download that did not complete."""


@dataclass(frozen=True)
class Resource:
    """One resolved monthly file: where to get it and how big it is said to be."""

    url: str
    title: str
    size: int | None


def _get(url: str) -> bytes:
    """Fetch a small resource (the dataset metadata JSON) fully into memory.
    https only, no proxy, no retry."""
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-https URL: {url!r}")
    request = Request(url, headers=IDENTIFYING_HEADERS)  # https checked above
    with _OPENER.open(request, timeout=TIMEOUT_S) as response:
        return response.read()


def _download(url: str, dest: Path, expected: int | None) -> int:
    """Stream a large resource to `dest` in `_CHUNK` pieces, so a gigabyte month
    never lands in memory at once. https only, no proxy, no retry. If the dataset
    declared a size, a body running past it (plus `_SLACK`) is refused and the
    partial file removed, rather than filling the disk. Returns the bytes written."""
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-https URL: {url!r}")
    request = Request(url, headers=IDENTIFYING_HEADERS)  # https checked above
    ceiling = expected + _SLACK if expected else None
    written = 0
    with (
        _OPENER.open(request, timeout=TIMEOUT_S) as response,
        dest.open("wb") as fh,
    ):
        while chunk := response.read(_CHUNK):
            written += len(chunk)
            if ceiling is not None and written > ceiling:
                raise FetchError(
                    f"refusing: {dest.name} ran past its declared size "
                    f"({expected} bytes) — stopped at {written}"
                )
            fh.write(chunk)
    return written


def resolve_resource(month: str) -> Resource:
    """Find the dataset resource whose title names this month (`A<YYYYMM>`).
    Raises `FetchError` if none does — a month the dataset does not publish is
    a clear refusal, not a silent empty download."""
    valid_month(month)  # refuse a bad month before any request
    token = month_token(month)
    payload = json.loads(_get(DATASET_API))
    for resource in payload.get("resources", []):
        title = str(resource.get("title", ""))
        if token in title.replace("_", "").replace("-", "").upper():
            url = str(resource.get("url", ""))
            if not url:
                continue
            size = resource.get("filesize")
            return Resource(url=url, title=title, size=int(size) if size else None)
    raise FetchError(
        f"no Open DAMIR resource for {month} (looked for {token!r} in the "
        f"resource titles at {DATASET_API})"
    )


def fetch_month(month: str) -> tuple[Path, int]:
    """Resolve and stream one month into the cache. Returns `(path, bytes)`.
    Developer-run: the CLI reaches here only past the `confirm` gate. A failed or
    empty download leaves no partial file behind."""
    resource = resolve_resource(month)
    dest = cache_path(month)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        size = _download(resource.url, dest, resource.size)
    except BaseException:
        dest.unlink(missing_ok=True)  # no partial file on a runaway or an error
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise FetchError(f"empty download for {month} from {resource.url}")
    return dest, size
