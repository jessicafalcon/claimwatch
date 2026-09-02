"""The robots matcher (spec Phase 2, fix amendment A1; invariant 5): wildcards,
the end anchor, longest-match precedence, group selection, Crawl-delay — and the
rule the live host actually publishes, against the path we actually ask for."""

from __future__ import annotations

import pytest

from ingest.robots import Robots, looks_like_robots
from ingest.sources import AppStoreSource

FEED = AppStoreSource(
    name="t", app_id=1, country="fr", listing="", fetchable=True
).page_url(1)
LIVE_FILE = "User-agent: *\nDisallow: /*/rss/*\n\nUser-agent: Googlebot\nDisallow:\n"


def test_the_live_hosts_wildcard_rule_disallows_the_feed_path():
    """`Disallow: /*/rss/*` under `User-agent: *` covers `/fr/rss/…`. This is
    the rule that was read and missed on 2026-09-02."""
    assert Robots.parse(LIVE_FILE).allows(FEED) is False
    assert Robots.parse(LIVE_FILE).allows("https://itunes.apple.com/fr/app/x") is True


@pytest.mark.parametrize(
    ("agent", "selected"),
    [
        ("friction-ledger", True),
        ("Friction-Ledger", True),
        ("FRICTION-LEDGER", True),
        ("friction-ledger/0.1", True),  # our full product token with version
        ("friction", True),  # a shorter substring: erring inclusive errs restrictive
        ("other-bot", False),
        ("", False),  # an empty value selects nothing
    ],
)
def test_our_group_is_any_whose_value_is_a_substring_of_our_user_agent(agent, selected):
    text = f"User-agent: {agent}\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    assert Robots.parse(text).allows(FEED) is (not selected)


@pytest.mark.parametrize(
    ("body", "is_robots"),
    [
        ("User-agent: *\nDisallow:\n", True),
        ("# only a comment\nSitemap: https://h/s.xml\n", True),
        ("crawl-delay: 5", True),
        ("<!doctype html><html><body>Not found</body></html>", False),
        ("", False),
        ("User-agent *\n", False),  # no colon: not a directive line
    ],
)
def test_looks_like_robots_wants_at_least_one_directive_line(body, is_robots):
    assert looks_like_robots(body) is is_robots


@pytest.mark.parametrize(
    ("robots", "allowed"),
    [
        ("User-agent: *\nDisallow:\n", True),  # empty Disallow: nothing disallowed
        ("User-agent: *\nDisallow: /fr/rss/\n", False),  # plain prefix
        ("User-agent: *\nDisallow: /fr/rss/$\n", True),  # anchored: exact path
        ("User-agent: *\nDisallow: /*/customerreviews/\n", False),  # inner wildcard
        ("User-agent: *\nDisallow: /*json$\n", False),  # wildcard then anchor
        ("User-agent: *\nDisallow: /\nAllow: /fr/rss/\n", True),  # longer wins
        ("User-agent: *\nAllow: /\nDisallow: /fr/rss/\n", False),  # longer wins
        ("User-agent: *\nAllow: /fr/rss/\nDisallow: /fr/rss/\n", True),  # tie: Allow
        ("User-agent: other-bot\nDisallow: /\n", True),  # someone else's group
        ("User-agent: Friction-Ledger\nDisallow: /\nUser-agent: *\nDisallow:\n", False),
        ("User-agent: *\nDisallow: /\nUser-agent: friction-ledger\nAllow: /\n", True),
        ("Disallow: /\n", True),  # a rule before any group applies to no one
        ("", True),  # an empty file
        ("# comment only\n\nSitemap: https://x/s.xml\n", True),
    ],
)
def test_matching_and_group_selection(robots: str, allowed: bool):
    assert Robots.parse(robots).allows(FEED) is allowed


def test_consecutive_user_agent_lines_form_one_group():
    text = "User-agent: a\nUser-agent: friction-ledger\nDisallow: /fr/\n"
    assert Robots.parse(text).allows(FEED) is False


def test_our_group_is_merged_across_the_file():
    text = "User-agent: *\nDisallow: /a\n\nUser-agent: *\nDisallow: /fr/\n"
    assert Robots.parse(text).allows(FEED) is False


def test_crawl_delay_is_read_from_our_group_only():
    assert Robots.parse("User-agent: *\nCrawl-delay: 5\n").crawl_delay == 5.0
    assert Robots.parse("User-agent: other\nCrawl-delay: 5\n").crawl_delay is None
    assert Robots.parse("User-agent: *\nCrawl-delay: soon\n").crawl_delay is None
    for absurd in ("1e400", "nan", "-5"):  # not finite, or negative: none declared
        assert (
            Robots.parse(f"User-agent: *\nCrawl-delay: {absurd}\n").crawl_delay is None
        )
    assert Robots.permissive().crawl_delay is None


def test_two_groups_naming_us_keep_the_longest_crawl_delay():
    longest_first = "User-agent: *\nCrawl-delay: 30\n\nUser-agent: *\nCrawl-delay: 1\n"
    longest_last = "User-agent: *\nCrawl-delay: 1\n\nUser-agent: *\nCrawl-delay: 30\n"
    assert Robots.parse(longest_first).crawl_delay == 30.0
    assert Robots.parse(longest_last).crawl_delay == 30.0


def test_the_query_string_is_part_of_the_matched_path():
    rules = Robots.parse("User-agent: *\nDisallow: /*?q=\n")
    assert rules.allows("https://h/p?q=1") is False
    assert rules.allows("https://h/p") is True
