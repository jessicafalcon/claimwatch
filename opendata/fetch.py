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
from urllib.request import Request, urlopen

from ingest.politeness import IDENTIFYING_HEADERS, TIMEOUT_S
from opendata.sources import DATASET_API, cache_path, month_token, valid_month


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
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-https URL: {url!r}")
    request = Request(url, headers=IDENTIFYING_HEADERS)  # noqa: S310 (https checked)
    with urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
        return response.read()


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
    """Resolve and download one month into the cache. Returns `(path, bytes)`.
    Developer-run: the CLI reaches here only past the `confirm` gate."""
    resource = resolve_resource(month)
    dest = cache_path(month)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _get(resource.url)
    if not data:
        raise FetchError(f"empty download for {month} from {resource.url}")
    dest.write_bytes(data)
    return dest, len(data)
