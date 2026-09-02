"""robots.txt, matched the way the standard says (RFC 9309), in one small place
(spec Phase 2, fix amendment A1; invariant 5).

A robots file is a site's list of what it asks crawlers not to fetch. It is
groups of rules: each group names the crawlers it applies to (`User-agent:`)
and then the paths they may (`Allow:`) or may not (`Disallow:`) fetch. Two
details matter and the stdlib parser on Python 3.12 gets both wrong: a rule
may use `*` for "anything" and a trailing `$` for "ends here", and when two
rules match the same path the longer one wins. A rule like `Disallow: /*/rss/*`
therefore covers `/fr/rss/…`, which a prefix-only matcher does not see.

This module parses the file into groups, picks the groups written for us — any
whose User-agent value is a substring of our full User-Agent (else the `*`
group; no group means nothing is disallowed) — matches patterns
with `*` and `$`, lets the longest match win and `Allow` win a tie, and reports
the group's `Crawl-delay` so the fetcher can wait longer than its own minimum.
Nothing here fetches; the fetcher hands it the text it archived."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ingest.politeness import USER_AGENT

DIRECTIVES = ("user-agent", "allow", "disallow", "crawl-delay", "sitemap")


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    crawl_delay: float | None = None


def _parse_groups(text: str) -> list[_Group]:
    groups: list[_Group] = []
    current: _Group | None = None
    naming = False  # inside a run of consecutive User-agent lines
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if current is None or not naming:
                current = _Group()
                groups.append(current)
            current.agents.append(value.lower())
            naming = True
        elif current is None:
            continue  # a rule before any group applies to no one
        elif key in ("allow", "disallow"):
            naming = False
            if value:  # an empty `Disallow:` is "nothing disallowed": no rule
                current.rules.append((key == "allow", value))
        elif key == "crawl-delay":
            naming = False
            try:
                delay = float(value)
            except ValueError:
                continue  # not a number: no delay is declared
            if math.isfinite(delay) and delay >= 0:
                current.crawl_delay = delay  # inf, nan or negative: none declared
    return groups


def looks_like_robots(text: str) -> bool:
    """At least one recognised directive line: what makes a 200 body a robots
    file rather than a catch-all page served with a 200 (amendment A5)."""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        key, sep, _ = line.partition(":")
        if sep and key.strip().lower() in DIRECTIVES:
            return True
    return False


def _select(groups: list[_Group], user_agent: str) -> _Group | None:
    """The groups written for us — a non-empty User-agent value that is a
    substring of our full User-Agent, case-insensitively — merged; else the
    `*` groups; else none. Erring inclusive errs restrictive."""
    ours = user_agent.lower()
    for match in (
        lambda g: any(a and a in ours for a in g.agents),
        lambda g: "*" in g.agents,
    ):
        chosen = [g for g in groups if match(g)]
        if chosen:
            merged = _Group()
            for g in chosen:
                merged.rules.extend(g.rules)
                if g.crawl_delay is not None:  # several declared: the longest wait
                    merged.crawl_delay = max(merged.crawl_delay or 0.0, g.crawl_delay)
            return merged
    return None


def _matches(pattern: str, path: str) -> bool:
    """`*` is any run of characters, a trailing `$` anchors the end; everything
    else is literal. The pattern is anchored at the start of the path."""
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    rx = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.match(rx + ("$" if anchored else ""), path) is not None


@dataclass(frozen=True)
class Robots:
    """The verdict-giver for one host's robots.txt as it applies to us."""

    rules: tuple[tuple[bool, str], ...]
    crawl_delay: float | None

    @classmethod
    def parse(cls, text: str, user_agent: str = USER_AGENT) -> Robots:
        group = _select(_parse_groups(text), user_agent)
        if group is None:
            return cls((), None)
        return cls(tuple(group.rules), group.crawl_delay)

    @classmethod
    def permissive(cls) -> Robots:
        """No robots file (404): nothing is disallowed."""
        return cls((), None)

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        best: tuple[int, bool] | None = None
        for allow, pattern in self.rules:
            if _matches(pattern, path):
                key = (len(pattern), allow)  # longest wins; on a tie Allow wins
                if best is None or key > best:
                    best = key
        return True if best is None else best[1]
