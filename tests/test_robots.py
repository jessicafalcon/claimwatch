"""The robots matcher (spec Phase 2, fix amendment A1; invariant 5): wildcards,
the end anchor, longest-match precedence, group selection, Crawl-delay — and the
rule the live host actually publishes, against the path we actually ask for."""

from __future__ import annotations

import pytest

from ingest.robots import PRODUCT_TOKEN, Robots, reads_as_robots
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
        ("friction", True),  # a substring of our token: written for us, tightens
        ("other-bot", False),
        # substrings of the rest of the User-Agent are NOT us (A6): a group
        # written for someone else must not become ours
        ("study", False),
        ("github", False),
        ("ai", False),
        ("f", False),  # a one-letter substring of our token is noise, not a name
        ("fr", False),
        ("fri", True),  # three characters of our token: written for us, tightens
        ("0.1", False),
        ("", False),  # an empty value selects nothing
    ],
)
def test_our_group_is_named_by_our_product_token_only(agent, selected):
    text = f"User-agent: {agent}\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    assert Robots.parse(text).allows(FEED) is (not selected)
    assert PRODUCT_TOKEN == "friction-ledger"


@pytest.mark.parametrize("agent", ["study", "ai", "f", "0.1", "friction-ledger"])
def test_no_group_can_loosen_what_the_catch_all_denies(agent):
    """A6: `*` applies beside ours, always. A foreign-but-similar group with no
    rules, or our own group allowing everything, leaves `*`'s Disallow in force;
    a wide selector can only tighten."""
    empty_group = f"User-agent: *\nDisallow: /\n\nUser-agent: {agent}\nDisallow:\n"
    assert Robots.parse(empty_group).allows(FEED) is False
    allow_all = f"User-agent: *\nDisallow: /\n\nUser-agent: {agent}\nAllow: /\n"
    assert Robots.parse(allow_all).allows(FEED) is False


def test_crawl_delay_is_the_longer_of_ours_and_the_catch_alls():
    ours = "User-agent: friction-ledger\nCrawl-delay: {a}\n"
    star = "User-agent: *\nCrawl-delay: {b}\n"
    assert Robots.parse(star.format(b=10) + ours.format(a=2)).crawl_delay == 10.0
    assert Robots.parse(star.format(b=2) + ours.format(a=10)).crawl_delay == 10.0
    foreign = "User-agent: study\nCrawl-delay: 99\n"
    assert Robots.parse(foreign + star.format(b=3)).crawl_delay == 3.0


@pytest.mark.parametrize(
    ("body", "is_robots"),
    [
        ("User-agent: *\nDisallow:\n", True),
        ("# only a comment\nSitemap: https://h/s.xml\n", True),
        ("User-agent: *\ncrawl-delay: 5", True),
        (
            "Host: example.org\nUser-agent: *\nDisallow: /a\n",
            True,
        ),  # unknown key, right shape
        ("", True),  # an empty file: no rules
        ("   \n# nothing but a comment\n", True),
        ("<!doctype html><html><body>Not found</body></html>", False),
        ('<html><a href="https://x/y">x</a><p style="color: red">e</p></html>', False),
        ('{"error": "not found", "status": 404}', False),
        ("Service Unavailable", False),
        ("Disallow: /\n", False),  # a rule before any group: nothing to belong to
        ("<html><body><pre>  Disallow: /</pre></body></html>", False),
        ("User-agent *\n", False),  # no colon: not a directive line
        (
            "User-agent: *\nDisallow: /\n<script>x</script>\n",
            False,
        ),  # one bad line spoils it
    ],
)
def test_reads_as_robots_is_decided_by_the_body_alone(body, is_robots):
    assert reads_as_robots(body) is is_robots


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


def test_a_non_user_agent_line_ends_the_naming_run():
    """A `Sitemap:` (or any unknown key) between `User-agent: *` and
    `User-agent: googlebot` must not fuse the two into one group: googlebot's
    long Allow would otherwise outrank the site's Disallow in the catch-all
    verdict. Without the line, one group naming both is what the file says."""
    star = "User-agent: *\nDisallow: /*/rss/*\n\n"
    fused = "User-agent: *\nSitemap: https://h/s.xml\nUser-agent: googlebot\n"
    fused += "Allow: /fr/rss/customerreviews\n"
    assert Robots.parse(star + fused).allows(FEED) is False
    honest = "User-agent: *\nUser-agent: googlebot\nAllow: /fr/rss/customerreviews\n"
    assert Robots.parse(star + honest).allows(FEED) is True
    assert Robots.parse(star + fused.replace("Sitemap", "Host")).allows(FEED) is False


def test_a_leading_byte_order_mark_is_skipped():
    """A valid file that starts with a BOM is a robots file, and its rules
    bind: not a false refusal, not a rule we cannot see."""
    assert reads_as_robots("\ufeffUser-agent: *\nDisallow:\n") is True
    assert Robots.parse("\ufeffUser-agent: *\nDisallow: /fr/\n").allows(FEED) is False


def test_two_crawl_delays_in_one_group_keep_the_longer():
    assert (
        Robots.parse("User-agent: *\nCrawl-delay: 30\nCrawl-delay: 1\n").crawl_delay
        == 30.0
    )
    assert (
        Robots.parse("User-agent: *\nCrawl-delay: 1\nCrawl-delay: 30\n").crawl_delay
        == 30.0
    )


def test_the_catch_all_is_never_our_group():
    """If `*` were merged into ours, the catch-all's longer Allow could
    outrank our own group's Disallow under longest-match; kept apart and
    conjoined, our Disallow stands. Pins the surviving round 4 mutant."""
    from ingest.robots import _names_us

    assert _names_us("*") is False
    ours = "User-agent: friction-ledger\nDisallow: /fr/\n\n"
    text = ours + "User-agent: *\nAllow: /fr/rss/\n"
    assert Robots.parse(text).allows(FEED) is False


@pytest.mark.parametrize(
    ("robots", "allowed"),
    [
        ("User-agent: *\nDisallow:\n", True),  # empty Disallow: nothing disallowed
        ("User-agent: *\nDisallow: /fr/rss/\n", False),  # plain prefix
        ("User-agent: *\nDisallow: /fr/rss/$\n", True),  # anchored: exact path only
        ("User-agent: *\nDisallow: /*/customerreviews/\n", False),  # inner wildcard
        ("User-agent: *\nDisallow: /*json$\n", False),  # wildcard then anchor
        ("User-agent: *\nDisallow: /\nAllow: /fr/rss/\n", True),  # longer Allow wins
        (
            "User-agent: *\nAllow: /\nDisallow: /fr/rss/\n",
            False,
        ),  # longer Disallow wins
        ("User-agent: *\nAllow: /fr/rss/\nDisallow: /fr/rss/\n", True),  # tie: Allow
        ("User-agent: *\nDisallow: /fr/rss/customerreviews/id=1/*\n", False),
        ("User-agent: *\nDisallow: /fr/rss/customerreviews/id=2/*\n", True),
    ],
)
def test_pattern_matching_and_precedence(robots: str, allowed: bool):
    """The rules of the game, pinned on their own: `*`, the `$` anchor,
    longest match wins, Allow wins a tie."""
    assert Robots.parse(robots).allows(FEED) is allowed
