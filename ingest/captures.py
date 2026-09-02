"""Reading captures back, for every parser (spec Phase 3a, pinned decision 3).
A capture is one run's saved copy of a source's pages exactly as they arrived:
`page-<n>.<ext>` (the body as served; `<ext>` is the parser's) beside
`page-<n>.meta.json` (the provenance stamped at fetch: `source_url`,
`captured_at`, `status`), plus the robots file the run obeyed. A rebuild reads
no clock and asks the site nothing: everything comes from these files.

The meta is parsed strictly (fix amendment A4): exactly the three fields,
`captured_at` a real `YYYY-MM-DDTHH:MM:SS` instant (staging's dedup sort key),
`source_url` an https address on the declaring source's own host — the host
the declaration names, not the fetch-time allowlist, so shrinking the
allowlist never unloads a legitimately captured row — and `status` the integer
200. Anything else refuses the capture with the file and field named."""

from __future__ import annotations

import importlib
import json
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

from ingest.parsed import PageShapeError, Parsed
from ingest.sources import PARSERS, Source

META_FIELDS = ("source_url", "captured_at", "status")
_STAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")


def parser_module(name: str) -> ModuleType:
    """The parser a declaration names — a closed set, never a value used as a
    module path."""
    if name not in PARSERS:
        raise ValueError(f"parser {name!r} not in {PARSERS}")
    return importlib.import_module(f"ingest.{name}")


def page_pattern(ext: str) -> re.Pattern[str]:
    return re.compile(rf"^page-([0-9]+)\.{re.escape(ext)}$")


def read_meta(path: Path, host: str) -> dict[str, object]:
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PageShapeError(f"{path}: meta is missing or not JSON") from exc
    if not isinstance(meta, dict) or set(meta) != set(META_FIELDS):
        raise PageShapeError(f"{path}: meta must have exactly {META_FIELDS}")
    stamp = meta["captured_at"]
    if not isinstance(stamp, str) or not _STAMP.match(stamp):
        raise PageShapeError(f"{path}: field 'captured_at' is not YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise PageShapeError(
            f"{path}: field 'captured_at' is not a real instant"
        ) from exc
    url = meta["source_url"]
    parts = urlsplit(url) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or parts.hostname != host:
        raise PageShapeError(
            f"{path}: field 'source_url' is not an https address on {host!r}"
        )
    status = meta["status"]
    if type(status) is not int or status != 200:
        raise PageShapeError(f"{path}: field 'status' is not 200")
    return meta


def capture_pages(capture_dir: Path, ext: str) -> list[Path]:
    """The `page-<n>.<ext>` files of one capture, in page order."""
    rx = page_pattern(ext)
    pages = []
    for p in capture_dir.iterdir():
        m = rx.match(p.name)
        if m:
            pages.append((int(m.group(1)), p))
    return [p for _, p in sorted(pages)]


def has_pages(root: Path, ext: str) -> bool:
    """Whether anything under `root` is a page a rebuild would load — the same
    rule `read_captures` applies, so a refused page (`page-<n>.refused.<ext>`)
    counts for neither."""
    rx = page_pattern(ext)
    return root.is_dir() and any(rx.match(p.name) for p in root.rglob(f"page-*.{ext}"))


def read_captures(root: Path, source: Source) -> list[tuple[str, Parsed]]:
    """Every capture under `root`, parsed by the source's declared parser ->
    [(capture_id, Parsed)], captures in name order, pages in page order, items
    in page order. A capture is any directory holding `page-<n>.<ext>` files;
    `root` itself may be one (a frozen sample). A missing root is zero
    captures, not an error (a fresh clone)."""
    if not root.is_dir() or source.parser is None:
        return []
    mod = parser_module(source.parser)
    rx = page_pattern(mod.EXTENSION)
    dirs = sorted(
        {p.parent for p in root.rglob(f"page-*.{mod.EXTENSION}") if rx.match(p.name)}
    )
    out: list[tuple[str, Parsed]] = []
    for d in dirs:
        parsed = Parsed()
        for page in capture_pages(d, mod.EXTENSION):
            try:
                meta = read_meta(
                    page.with_name(page.name[: -len(mod.EXTENSION) - 1] + ".meta.json"),
                    source.host,
                )
                parsed.extend(
                    mod.parse(
                        page.read_bytes(),
                        str(meta["source_url"]),
                        str(meta["captured_at"]),
                        source,
                    )
                )
            except PageShapeError as exc:
                # Which file to fix: the capture directory, then the page's own line.
                raise PageShapeError(f"capture {d}: {exc}") from exc
        out.append((d.name, parsed))
    return out
