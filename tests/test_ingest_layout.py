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
from tests.repo_text import repo_text

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
        found = rx.findall(repo_text(p))
        if found:
            hits[str(p.relative_to(ROOT))] = found
    return hits


def test_httpx_is_imported_only_by_the_fetcher():
    hits = _lines_matching(r"^\s*(?:import httpx|from httpx\b).*$")
    assert set(hits) == {"ingest/fetch.py"}, hits


def test_politeness_knobs_live_in_one_module():
    """The knobs are assigned in politeness.py and nowhere else; the
    User-Agent header is built there too (`IDENTIFYING_HEADERS`), so both the
    review crawler (httpx) and the open-data download (urllib) identify us from
    one place (Phase 7b)."""
    knobs = (
        "MIN_INTERVAL_S",
        "USER_AGENT",
        "IDENTIFYING_HEADERS",
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
    assert set(ua) == {"ingest/politeness.py"}, ua
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
        for line in repo_text(p).splitlines():
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


def test_no_module_spells_an_engines_schema_name():
    """Portability: `pipeline/warehouse.py` is the one file that knows DuckDB
    from Snowflake, and it reads the default schema from the engine. A
    `table_schema = 'main'` literal anywhere else lists nothing on Snowflake,
    so `idempotency-check` would diff two empty maps and report OK (round 4,
    code-reviewer #3)."""
    hits = _lines_matching(r"table_schema\s*=\s*'[A-Za-z_]+'")
    assert hits == {}, hits


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
        "trustpilot",
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


@pytest.mark.parametrize(
    "day",
    [
        "",
        "2026-9-1",
        "2026-02-30",
        "today",
        # Spellings `date.fromisoformat` accepts and the declared `YYYY-MM-DD`
        # shape does not — written verbatim as `captured_at` if let through
        # (round 4, functionality-tester #4).
        "20260902",
        "2026-09-02T00:00",
        "2026-09-02\n",
        "2026-W36-3",
    ],
)
def test_a_declaration_without_a_real_declared_on_day_is_refused(day):
    """`declared_on` is provenance — it becomes `captured_at` on every page
    address in raw_source_pages — so a declaration carries a real day or does
    not exist; the empty string is no longer a default (round 1, code-reviewer
    #6). The shape is the one spelling, not whatever the stdlib parses."""
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


def test_only_the_sample_declaration_carries_the_sample_profile():
    """A9 (c): the loader keys the `sample` labels on the row's profile, so a
    real declaration may not carry that profile — the shape refuses at the
    declaration, like the name (A3 (b))."""
    with pytest.raises(ValueError, match="profile is the sample declaration's"):
        app_store_source(
            name="x",
            app_id=1,
            country="fr",
            listing="",
            fetchable=True,
            declared_on="2026-09-03",
            profile="sample",
        )


def test_brand_carrying_strings_appear_only_in_the_declarations():
    """D1, enforced over the tree: every string that spells the studied
    insurer (`ingest/sources.py::BRAND_TOKENS`) appears in no other tracked
    file — not a doc, a comment, a test name, a fixture or a record — as a
    whole word, in any case. Every tracked file is UTF-8 text (the repo holds
    no binary), so a file that does not decode fails by name rather than
    being skipped (round 1 skipped it; tooling round 3 closed the class)."""
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
        for n, line in enumerate(repo_text(path).splitlines(), 1):
            for token in BRAND_TOKENS:
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", line, re.I
                ):
                    hits.append(f"{rel}:{n}: {token}")
    assert hits == [], hits


# The words an address of the studied insurer may carry WITHOUT being a brand
# form: the scheme, the hosts' labels, the stores' path vocabulary, the query
# keys. A closed set: a word outside it is a brand form and must be a
# declared token, so a new form that shares no letter with today's tokens is
# caught the day it is declared (round 3, code-reviewer #10).
ADDRESS_WORDS = frozenset(
    [
        "https",
        "www",
        "com",
        "fr",
        "html",
        "json",
        "id",
        "hl",
        "gl",
        "apple",
        "apps",
        "app",
        "itunes",
        "rss",
        "customerreviews",
        "sortby",
        "mostrecent",
        "google",
        "play",
        "store",
        "details",
        "opinion",
        "assurances",
        "assureur",
        "page",
        "trustpilot",
        "review",
        "ca",
        "languages",
        "all",
    ]
)


def test_every_brand_form_in_the_declarations_is_a_declared_token():
    """Completeness of the guard (round 2, security-reviewer #3; round 3,
    code-reviewer #10): every word of every address a studied-insurer
    declaration carries is a declared generic address word, a page number, or
    a declared brand token — nothing else — and each such source spells the
    brand at least once. A brand form is found by what it is NOT, so a form
    sharing no substring with today's tokens cannot hide in an address."""
    from ingest.sources import BRAND_TOKENS

    def words(text: str) -> set[str]:
        return set(re.findall(r"[a-z]+|[0-9]+", text.lower()))

    studied = [s for s in SOURCES if s.profile == "fr-digital-first"]
    assert studied
    for src in studied:
        found = set().union(*(words(u) for u in (src.listing, *src.pages)))
        page_numbers = {w for w in found if w.isdigit() and len(w) <= 2}
        brand = found - ADDRESS_WORDS - page_numbers
        assert brand, src.name  # each studied-insurer source spells the brand
        assert brand <= set(BRAND_TOKENS), (src.name, brand - set(BRAND_TOKENS))


def test_the_sample_declaration_is_a_property_not_a_name():
    """A3 (b): the closed-set check on `segment` and `channel` keys on the
    `sample` property, which only `sample_source` sets — a declaration named
    `sample` without it refuses, and a source of any other name carrying an
    out-of-set label refuses whatever it is called (round 2, code-reviewer
    #5, #6)."""
    from ingest.sources import SAMPLE, sample_source

    def declare(name: str, **over):
        fields = dict(
            name=name,
            platform="google-play",
            host="play.google.com",
            parser="listing",
            pages=(),
            profile="p",
            segment="NOT-A-SEGMENT",
            channel="NOT-A-CHANNEL",
            listing="",
            fetchable=False,
            declared_on="2026-09-01",
            terms="a test declaration",
        )
        fields.update(over)
        return Source(**fields)

    for parser in PARSERS:
        assert sample_source(parser).sample is True
    with pytest.raises(ValueError, match="sample=True"):
        declare(SAMPLE)  # the name alone earns nothing
    with pytest.raises(ValueError, match="segment in"):
        declare("not-a-sample")  # any other name: the closed sets
    with pytest.raises(ValueError, match="segment in"):
        declare("not-a-sample", segment="digital-first")  # channel still out
    assert declare(SAMPLE, sample=True).segment == "NOT-A-SEGMENT"
    assert declare("twin", sample=True).channel == "NOT-A-CHANNEL"


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
            listing="https://h/x",
            fetchable=False,
            terms="t",
            declared_on="2026-09-01",
        )


def test_a_hand_entered_declaration_needs_a_listing():
    """A4 (b): a source with no parser writes its listing address as every
    hand-read row's `source_url`, a provenance column, so the declaration
    refuses an empty one; a parsed source may leave it empty (round 3,
    code-reviewer #2)."""
    store = by_name("fr-digital-first-app-store-listing")
    assert store.parser is None and store.listing
    import dataclasses

    for empty in ("", "  "):
        with pytest.raises(ValueError, match="needs a listing address"):
            dataclasses.replace(store, name="twin", listing=empty)
    assert dataclasses.replace(store, name="twin", listing="https://h/x").listing


def test_a_shape_guard_takes_the_whole_value_not_a_prefix_before_a_newline(
    tmp_path,
):
    """Every declared shape is matched whole: under `re.match` an anchored
    `$` accepts a trailing newline, so `x\\n` passed as the slug `x`, `4\\n`
    as the digit string `4`, and round 4's `2026-09-02\\n` pin held only
    because the stdlib parse behind the shape refused it (round 5,
    code-reviewer #6). Each case here has no guard behind the shape, or a
    refusal that names the shape rather than the parse."""
    import json

    from ingest import app_store
    from ingest.captures import read_meta
    from ingest.parsed import PageShapeError, count_in_range

    with pytest.raises(ValueError, match="slugs"):
        app_store_source(
            name="x\n",
            app_id=1,
            country="fr",
            listing="",
            fetchable=True,
            declared_on="2026-09-02",
        )
    assert count_in_range("512\n") is None
    with pytest.raises(PageShapeError, match="is not a digit string"):
        app_store._rating("4\n", "https://itunes.apple.com/x", "item")
    src = by_name("fr-digital-first")
    meta = tmp_path / "page-1.meta.json"
    meta.write_text(
        json.dumps(
            {
                "source_url": src.pages[0],
                "captured_at": "2026-09-02T10:00:00\n",
                "status": 200,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PageShapeError, match="is not YYYY-MM-DDTHH:MM:SS"):
        read_meta(meta, src)


def test_every_shape_carries_its_own_anchors():
    """The whole-value property lives in the shape, not only at the call:
    under a bare `search`, a value with text around it is still refused by
    every declared shape (exit pass, code-reviewer #8)."""
    from ingest import app_store, captures, opinion_assurances, parsed, sources
    from pipeline import build

    shapes = (
        build._SLUG,
        build._DAY,
        sources._SLUG,
        sources._DATE,
        captures._STAMP,
        captures.page_pattern("xml"),
        app_store._DIGITS,
        parsed._COUNT,
        opinion_assurances._REVIEW_TYPE,
    )
    good = (
        "abc",
        "2026-09-03",
        "abc",
        "2026-09-03",
        "2026-09-03T10:00:00",
        "page-1.xml",
        "12",
        "12",
        "https://schema.org/review",
    )
    for shape, value in zip(shapes, good, strict=True):
        assert shape.search(value)
        assert not shape.search(f" {value}"), shape.pattern
        assert not shape.search(f"{value}\n"), shape.pattern
