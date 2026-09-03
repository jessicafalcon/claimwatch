"""Where things live (spec Phase 2, invariants 6 and 7, done-when 1 and 6):
`httpx` is imported only by the fetcher, the politeness knobs are defined only
in `ingest/politeness.py`, a rebuild never imports the fetcher, `ingest/` never
reads `.env`, the only clock is the fetcher's stamp, and every source is a
full declaration (Phase 3a). Mechanical greps over every `*.py` in the repo
outside `tests/` and dot-directories (tests build `httpx.MockTransport`s), so
a module landing in
`classify/`, `models/`, `dags/`, `study/` or the root is covered the day it
appears — invariant 6 says "all modules"."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest import politeness
from ingest.sources import (
    CHANNELS,
    PARSERS,
    SEGMENTS,
    SOURCES,
    Source,
    app_store_source,
    by_name,
    source_names,
)

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
    """The knobs are assigned in politeness.py and nowhere else; the
    User-Agent header is set in the fetcher only, from that constant."""
    knobs = (
        "MIN_INTERVAL_S",
        "USER_AGENT",
        "TIMEOUT_S",
        "MAX_PAGES",
        "ALLOWED_HOSTS",
        "MAX_CRAWL_DELAY_S",
        "MAX_BYTES",
        "MAX_RESPONSE_S",
    )
    for name in knobs:
        assert hasattr(politeness, name), name
        hits = _lines_matching(rf"^{name}\s*=.*$")
        assert set(hits) == {"ingest/politeness.py"}, (name, hits)
    ua = _lines_matching(r'"User-Agent"')
    assert set(ua) == {"ingest/fetch.py"}, ua
    assert politeness.MIN_INTERVAL_S >= 2.0
    assert politeness.MAX_PAGES == 60  # Phase 3a, D6: the per-source ceiling
    assert politeness.TIMEOUT_S == 20.0
    assert politeness.MAX_CRAWL_DELAY_S == 60.0
    assert politeness.MAX_BYTES == 4 * 1024 * 1024
    assert politeness.MAX_RESPONSE_S == 60.0
    assert "friction-ledger" in politeness.USER_AGENT
    assert politeness.ALLOWED_HOSTS == (
        "itunes.apple.com",
        "play.google.com",
        "www.opinion-assurances.fr",
    )


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


def test_the_phase_2_feed_source_is_declared_as_before():
    src = by_name("fr-digital-first")
    assert re.fullmatch(r"[a-z0-9-]+", src.name)
    assert src.host == "itunes.apple.com" and src.parser == "app_store"
    assert src.page_url(2).startswith("https://itunes.apple.com/")
    assert "page=2/json" in src.page_url(2) and len(src.pages) == 10
    # A sourced data point: the listing the id was read from, by id only —
    # no app or company name in the address.
    assert src.listing.startswith("https://apps.apple.com/fr/app/id")
    # The recorded terms position is declared, with its reason (amendment A5).
    assert src.fetchable is False
    assert "robots.txt" in src.terms and "2026-09-02" in src.terms


def test_every_source_declares_parser_cache_host_and_attribution():
    """Phase 3a, invariant 3: every fact the fetcher and the loader need is in
    the declaration — parser (a closed set), host, page addresses on that host,
    a cache directory under the one root, profile, segment, channel."""
    from datetime import date
    from urllib.parse import urlsplit

    from ingest import sources

    assert len(SOURCES) >= 3 and len(set(source_names())) == len(SOURCES)
    for src in SOURCES:
        assert src.parser is None or src.parser in PARSERS
        assert src.segment in SEGMENTS and src.channel in CHANNELS
        assert src.cache_dir == sources.CACHE_ROOT / src.platform / src.name
        assert all(urlsplit(u).hostname == src.host for u in src.pages), src.name
        assert all(u.startswith("https://") for u in src.pages)
        date.fromisoformat(src.declared_on)  # a real day, whichever (round 2)
        if src.fetchable:
            assert src.parser is not None and src.pages, src.name
    assert {s.platform for s in SOURCES} == {
        "app-store",
        "google-play",
        "opinion-assurances",
    }


def test_every_fetchable_sources_host_is_allowed():
    for src in SOURCES:
        if src.fetchable:
            assert src.host in politeness.ALLOWED_HOSTS, src.name


def test_the_cache_root_is_bound_once():
    """One binding (`ingest/sources.py::CACHE_ROOT`); no other module writes a
    `data/cache` path."""
    hits = _lines_matching(r'"cache"')
    assert set(hits) == {"ingest/sources.py"}, hits


def test_no_module_branches_on_a_platform_name():
    """Nothing outside the declarations and a parser's own constants compares
    against a platform or source name: the second platform is a declaration,
    not a branch."""
    rx = (
        r'(==|!=|\bin\b)\s*\(?\s*"'
        r'(app-store|google-play|opinion-assurances|fr-digital-first[a-z-]*)"'
    )
    hits = _lines_matching(rx)
    assert hits == {}, hits


@pytest.mark.parametrize("day", ["", "2026-9-1", "2026-02-30", "today"])
def test_a_declaration_without_a_real_declared_on_day_is_refused(day):
    """`declared_on` is provenance — it becomes `captured_at` on every page
    address in raw_source_pages — so a declaration carries a real day or does
    not exist; the empty string is no longer a default (round 1, code-reviewer
    #6)."""
    with pytest.raises(ValueError, match="declared_on"):
        app_store_source(
            name="x",
            app_id=1,
            country="fr",
            listing="",
            fetchable=True,
            declared_on=day,
        )
    with pytest.raises(TypeError):  # the field has no default at all
        app_store_source(name="x", app_id=1, country="fr", listing="", fetchable=True)


def test_brand_carrying_strings_appear_only_in_the_declarations():
    """D1, enforced over the tree: every string that spells the studied
    insurer (`ingest/sources.py::BRAND_TOKENS`) appears in no other tracked
    file — not a doc, a comment, a test name, a fixture or a record — as a
    whole word, in any case. Binary files are skipped by decoding (round 1,
    code-reviewer #9, security-reviewer #5)."""
    import subprocess

    from ingest.sources import BRAND_TOKENS

    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8", errors="replace")
    hits: list[str] = []
    for rel in filter(None, tracked.split("\0")):
        if rel == "ingest/sources.py":
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for token in BRAND_TOKENS:
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", line, re.I
                ):
                    hits.append(f"{rel}:{n}: {token}")
    assert hits == [], hits


def test_every_brand_form_in_the_declarations_is_a_declared_token():
    """Completeness of the guard (round 2, security-reviewer #3): every
    address a declaration carries that spells the brand contains a declared
    token as a whole word — the bare name, the package-id form, the store
    id — so a form the walk cannot match cannot hide in an address."""
    from ingest.sources import BRAND_TOKENS

    def forms(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    studied = [s for s in SOURCES if s.profile == "fr-digital-first"]
    assert studied
    for src in studied:
        words = set().union(*(forms(u) for u in (src.listing, *src.pages)))
        carrying = {w for w in words if any(t in w for t in BRAND_TOKENS)}
        assert carrying, src.name  # each studied-insurer source spells the brand
        assert carrying <= set(BRAND_TOKENS), (src.name, carrying - set(BRAND_TOKENS))


def test_no_two_hand_entered_sources_share_a_platform_and_listing():
    """A2: a hand-read row's key carries its declaration's platform and listing
    address, so two hand-entered sources may not share them; the declared
    tuple passes, a colliding pair refuses at declaration."""
    from ingest.sources import hand_entries_are_unique

    hand_entries_are_unique(SOURCES)
    store = by_name("fr-digital-first-app-store-listing")
    twin = Source(
        name="twin",
        platform=store.platform,
        host=store.host,
        parser=None,
        pages=(),
        profile="peer-x",
        segment="traditional",
        channel="invited",
        listing=store.listing,
        fetchable=False,
        declared_on="2026-09-02",
        terms="terms say no (2026-09-02)",
    )
    with pytest.raises(ValueError, match="both hand-entered"):
        hand_entries_are_unique(SOURCES + (twin,))


def test_every_non_fetchable_source_states_its_reason():
    """The property over every declaration, not today's: fetchable=False
    implies a reason naming robots or a terms clause and a date; the
    declaration itself refuses otherwise."""
    for src in SOURCES:
        if not src.fetchable:
            assert re.search(r"robots\.txt|terms|conditions", src.terms), src.name
            assert re.search(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", src.terms), src.name
    with pytest.raises(ValueError, match="needs terms"):
        app_store_source(
            name="x",
            app_id=1,
            country="fr",
            listing="",
            fetchable=False,
            declared_on="2026-09-01",
        )
    with pytest.raises(ValueError, match="needs terms"):
        app_store_source(
            name="x",
            app_id=1,
            country="fr",
            listing="",
            fetchable=False,
            terms="  ",
            declared_on="2026-09-01",
        )
    with pytest.raises(ValueError, match="needs a parser"):
        Source(
            name="x",
            platform="p",
            host="h",
            parser=None,
            pages=(),
            profile="x",
            segment="traditional",
            channel="unsolicited",
            listing="",
            fetchable=True,
            declared_on="2026-09-01",
        )
    with pytest.raises(ValueError, match="segment"):
        Source(
            name="x",
            platform="p",
            host="h",
            parser=None,
            pages=(),
            profile="x",
            segment="invited",
            channel="unsolicited",
            listing="",
            fetchable=False,
            terms="t",
            declared_on="2026-09-01",
        )
