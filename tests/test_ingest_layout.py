"""Where things live (spec Phase 2, invariants 6 and 7, done-when 1 and 6):
`httpx` is imported only by the fetcher, the politeness knobs are defined only
in `ingest/politeness.py`, a rebuild never imports the fetcher, `ingest/` never
reads `.env`, the only clock is the fetcher's stamp, and exactly one source is
declared. Mechanical greps over the tracked modules (tests excluded — they build
`httpx.MockTransport`s)."""

from __future__ import annotations

import re
from pathlib import Path

from ingest import politeness
from ingest.sources import SOURCES, source_names

ROOT = Path(__file__).resolve().parent.parent
MODULE_DIRS = ("ingest", "pipeline", "scripts")


def _modules() -> list[Path]:
    return sorted(p for d in MODULE_DIRS for p in (ROOT / d).rglob("*.py"))


def _lines_matching(pattern: str) -> dict[str, list[str]]:
    rx = re.compile(pattern, re.M)
    hits: dict[str, list[str]] = {}
    for p in _modules():
        found = rx.findall(p.read_text(encoding="utf-8"))
        if found:
            hits[str(p.relative_to(ROOT))] = found
    return hits


def test_httpx_is_imported_only_by_the_fetcher():
    hits = _lines_matching(r"^\s*(?:import httpx|from httpx\b).*$")
    assert set(hits) == {"ingest/fetch.py"}, hits


def test_politeness_knobs_live_in_one_module():
    """The five knobs are assigned in politeness.py and nowhere else; the
    User-Agent header is set in the fetcher only, from that constant."""
    knobs = ("MIN_INTERVAL_S", "USER_AGENT", "TIMEOUT_S", "MAX_PAGES", "ALLOWED_HOSTS")
    for name in knobs:
        assert hasattr(politeness, name), name
        hits = _lines_matching(rf"^{name}\s*=.*$")
        assert set(hits) == {"ingest/politeness.py"}, (name, hits)
    ua = _lines_matching(r'"User-Agent"')
    assert set(ua) == {"ingest/fetch.py"}, ua
    assert politeness.MIN_INTERVAL_S >= 2.0
    assert "friction-ledger" in politeness.USER_AGENT
    assert politeness.ALLOWED_HOSTS == ("itunes.apple.com",)


def test_pipeline_never_imports_the_fetcher_at_module_level():
    """A rebuild reads captures from disk; the fetcher is loaded only inside the
    `scrape` command, so `make rebuild` never touches `httpx` or the network."""
    for p in (ROOT / "pipeline").glob("*.py"):
        for line in p.read_text(encoding="utf-8").splitlines():
            assert not re.match(r"^(from ingest\.fetch|import ingest\.fetch)", line), (
                p.name,
                line,
            )


def test_ingest_never_reads_env_or_credentials():
    hits = _lines_matching(r"\.env\b|dotenv|os\.environ|getenv")
    assert not {k: v for k, v in hits.items() if k.startswith("ingest/")}, hits


def test_the_only_clock_is_the_fetch_stamp():
    """No `now()`/`time.time()`/`utcnow` anywhere on the data path; the one
    clock is `ingest/fetch.py::utc_stamp`, which stamps `captured_at` at fetch."""
    hits = _lines_matching(r"datetime\.now\(|\.utcnow\(|time\.time\(|date\.today\(")
    assert set(hits) == {"ingest/fetch.py"}, hits


def test_exactly_one_source_is_declared():
    assert len(SOURCES) == 1
    (src,) = SOURCES
    assert source_names() == (src.name,)
    assert re.fullmatch(r"[a-z0-9-]+", src.name)
    assert src.host == "itunes.apple.com"
    assert src.page_url(2).startswith("https://itunes.apple.com/")
    assert "page=2/json" in src.page_url(2)
