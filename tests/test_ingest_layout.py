"""Where things live (spec Phase 2, invariants 6 and 7, done-when 1 and 6):
`httpx` is imported only by the fetcher, the politeness knobs are defined only
in `ingest/politeness.py`, a rebuild never imports the fetcher, `ingest/` never
reads `.env`, the only clock is the fetcher's stamp, and exactly one source is
declared. Mechanical greps over every `*.py` in the repo outside `tests/` and
dot-directories (tests build `httpx.MockTransport`s), so a module landing in
`classify/`, `models/`, `dags/`, `study/` or the root is covered the day it
appears — invariant 6 says "all modules"."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest import politeness
from ingest.sources import SOURCES, source_names

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_TOP = ("tests",)  # plus every dot-directory (.venv, .git, .claude)


def _modules() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        parts = p.relative_to(ROOT).parts
        if parts[0] in EXCLUDED_TOP or any(part.startswith(".") for part in parts):
            continue
        out.append(p)
    return sorted(out)


def test_the_module_walk_is_the_repo_not_a_list():
    """The walk covers the three Phase 2 directories and would cover a new one
    without editing this file; tests and dot-directories are the only exclusions."""
    seen = {p.relative_to(ROOT).parts[0] for p in _modules()}
    assert {"ingest", "pipeline", "scripts"} <= seen
    assert "tests" not in seen and not any(s.startswith(".") for s in seen)


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
    knobs = (
        "MIN_INTERVAL_S",
        "USER_AGENT",
        "TIMEOUT_S",
        "MAX_PAGES",
        "ALLOWED_HOSTS",
        "MAX_CRAWL_DELAY_S",
    )
    for name in knobs:
        assert hasattr(politeness, name), name
        hits = _lines_matching(rf"^{name}\s*=.*$")
        assert set(hits) == {"ingest/politeness.py"}, (name, hits)
    ua = _lines_matching(r'"User-Agent"')
    assert set(ua) == {"ingest/fetch.py"}, ua
    assert politeness.MIN_INTERVAL_S >= 2.0
    assert politeness.MAX_PAGES == 10  # the feed's own cap: the request budget
    assert politeness.TIMEOUT_S == 20.0
    assert politeness.MAX_CRAWL_DELAY_S == 60.0
    assert "friction-ledger" in politeness.USER_AGENT
    assert politeness.ALLOWED_HOSTS == ("itunes.apple.com",)


def test_the_stdlib_robots_parser_is_not_used():
    """Fix amendment A1: robots.txt is matched by `ingest/robots.py` (RFC 9309)
    and nowhere else; the prefix-only stdlib parser is absent from the repo."""
    assert _lines_matching(r"robotparser") == {}
    hits = _lines_matching(r"^\s*from ingest\.robots import|^\s*import ingest\.robots")
    assert set(hits) == {"ingest/fetch.py"}, hits
    # A6: which rules bind us is never a caller's value — parse takes the text only.
    import inspect

    from ingest.robots import Robots

    assert list(inspect.signature(Robots.parse).parameters) == ["text"]


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
    # A sourced data point: the listing the id was read from, by id only —
    # no app or company name in the address.
    assert src.listing == f"https://apps.apple.com/{src.country}/app/id{src.app_id}"
    # The recorded terms position is declared, with its reason (amendment A5).
    assert src.fetchable is False
    assert "robots.txt" in src.terms and "2026-09-02" in src.terms


def test_every_non_fetchable_source_states_its_reason():
    """The property over every declaration, not today's one: fetchable=False
    implies a non-empty reason; the declaration itself refuses otherwise."""
    for src in SOURCES:
        assert src.fetchable or src.terms.strip(), src.name
    from ingest.sources import AppStoreSource

    with pytest.raises(ValueError, match="needs terms"):
        AppStoreSource(name="x", app_id=1, country="fr", listing="", fetchable=False)
    with pytest.raises(ValueError, match="needs terms"):
        AppStoreSource(
            name="x", app_id=1, country="fr", listing="", fetchable=False, terms="  "
        )
