"""robots.txt, matched the way the standard says (RFC 9309) and then some, in
one small place (spec Phase 2, amendments A1, A5, A6; invariant 5).

A robots file is a site's list of what it asks crawlers not to fetch. It is
groups of rules: each group names the crawlers it applies to (`User-agent:`)
and then the paths they may (`Allow:`) or may not (`Disallow:`) fetch. Two
details matter and the stdlib parser on Python 3.12 gets both wrong: a rule
may use `*` for "anything" and a trailing `$` for "ends here", and when two
rules match the same path the longer one wins. A rule like `Disallow: /*/rss/*`
therefore covers `/fr/rss/…`, which a prefix-only matcher does not see.

The invariant this module serves (A6): a feed request is made only if the body
reads as a robots file on its own terms, and the path is allowed by BOTH the
groups written for us and the catch-all `*` group. So: `reads_as_robots`
decides from the body alone whether there is a file to obey (an error page
served with a 200 is not one); the groups written for us are those naming our
product token (or a substring of it); `*` applies as well, always, so a wide
selector can only ever tighten; the Crawl-delay is the longer of the two.
Nothing here fetches; the fetcher hands it the text it archived."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ingest.politeness import USER_AGENT

PRODUCT_TOKEN = USER_AGENT.split("/", 1)[0].lower()  # "friction-ledger"
RULE_KEYS = ("allow", "disallow")
_DIRECTIVE_LINE = re.compile(
    r"^[A-Za-z-]+\s*:"
)  # `<key>: <value>`, letter-or-hyphen key


def _lines(text: str) -> list[str]:
    """Non-blank lines with comments stripped; a leading byte-order mark is
    skipped (RFC 9309 §2.3), not read as part of the first key."""
    out = []
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def reads_as_robots(text: str) -> bool:
    """Whether a 200 body is a robots file, decided by the body alone (A6):
    every line is directive-shaped; a non-empty body carries a `User-agent:`
    line unless every line is a `Sitemap:`; and no rule comes before the first
    `User-agent:`. So an empty body and a sitemap-only body are robots files
    with no rules, while an HTML or JSON page, a plain-text error (`Error:
    503`), or a rule before any group is not."""
    lines = _lines(text)
    if not all(_DIRECTIVE_LINE.match(line) for line in lines):
        return False
    keys = [line.partition(":")[0].strip().lower() for line in lines]
    if keys and "user-agent" not in keys and any(k != "sitemap" for k in keys):
        return False
    first_group = keys.index("user-agent") if "user-agent" in keys else len(keys)
    return not any(k in RULE_KEYS for k in keys[:first_group])


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    crawl_delay: float | None = None


def _parse_groups(text: str) -> list[_Group]:  # noqa: C901 -- the RFC 9309 line kinds, one branch each
    groups: list[_Group] = []
    current: _Group | None = None
    naming = False  # inside a run of consecutive User-agent lines
    for line in _lines(text):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if current is None or not naming:
                current = _Group()
                groups.append(current)
            current.agents.append(value.lower())
            naming = True
            continue
        # Any other line ends a run of User-agent lines — a `Sitemap:` or an
        # unknown key between two of them must not fuse two groups into one,
        # or a foreign group's Allow would land in the catch-all verdict.
        naming = False
        if current is None:
            continue  # a rule before any group applies to no one
        if key in RULE_KEYS:
            if value:  # an empty `Disallow:` is "nothing disallowed": no rule
                current.rules.append((key == "allow", value))
        elif key == "crawl-delay":
            try:
                delay = float(value)
            except ValueError:
                continue  # not a number: no delay is declared
            if math.isfinite(delay) and delay >= 0:  # inf, nan, negative: none declared
                current.crawl_delay = max(current.crawl_delay or 0.0, delay)  # longest
    return groups


def _names_us(agent: str) -> bool:
    """A value that is our product token, has it as a substring
    (`friction-ledger/0.1`), or is a substring of it at least three characters
    long (`friction`; a one- or two-letter value is noise, not a name). Never
    `*`, never the empty value. Selecting too widely only tightens (see
    `Robots.allows`), so the leniency costs nothing."""
    if not agent or agent == "*":
        return False
    return PRODUCT_TOKEN in agent or (len(agent) >= 3 and agent in PRODUCT_TOKEN)


def _merge(groups: list[_Group]) -> _Group:
    merged = _Group()
    for g in groups:
        merged.rules.extend(g.rules)
        if g.crawl_delay is not None:  # several declared: the longest wait
            merged.crawl_delay = max(merged.crawl_delay or 0.0, g.crawl_delay)
    return merged


def _matches(pattern: str, path: str) -> bool:
    """`*` is any run of characters, a trailing `$` anchors the end; everything
    else is literal. The pattern is anchored at the path's start, so an
    unanchored pattern matches a prefix — the same as matching `pattern*` in
    full. Matched directly, two pointers and one fallback to the last `*`
    (spec Phase 3a, pinned decision 6): time is bounded by pattern length ×
    path length, never exponential, so a file with many wildcards cannot stall
    a run. No regex."""
    if pattern.endswith("$"):
        pattern = pattern[:-1]
    else:
        pattern += "*"
    p = s = 0
    star, mark = -1, 0  # the last `*` seen, and where the path was then
    while s < len(path):
        if p < len(pattern) and pattern[p] == "*":
            star, mark = p, s
            p += 1
        elif p < len(pattern) and pattern[p] == path[s]:
            p += 1
            s += 1
        elif star != -1:  # let the last `*` swallow one more character
            mark += 1
            p, s = star + 1, mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


def _allowed(rules: tuple[tuple[bool, str], ...], path: str) -> bool:
    best: tuple[int, bool] | None = None
    for allow, pattern in rules:
        if _matches(pattern, path):
            key = (len(pattern), allow)  # longest wins; on a tie Allow wins
            if best is None or key > best:
                best = key
    return True if best is None else best[1]


@dataclass(frozen=True)
class Robots:
    """The verdict-giver for one host's robots.txt as it applies to us: the
    rules written for us and the catch-all rules, both consulted."""

    ours: tuple[tuple[bool, str], ...]
    everyone: tuple[tuple[bool, str], ...]
    crawl_delay: float | None

    @classmethod
    def parse(cls, text: str) -> Robots:
        """Which rules bind us is decided here, from the file and our product
        token — never by a caller."""
        groups = _parse_groups(text)
        ours = _merge([g for g in groups if any(_names_us(a) for a in g.agents)])
        everyone = _merge([g for g in groups if "*" in g.agents])
        delays = [d for d in (ours.crawl_delay, everyone.crawl_delay) if d is not None]
        return cls(
            tuple(ours.rules), tuple(everyone.rules), max(delays) if delays else None
        )

    @classmethod
    def permissive(cls) -> Robots:
        """No robots file (404): nothing is disallowed."""
        return cls((), (), None)

    def allows(self, url: str) -> bool:
        """Allowed only if both the rules written for us and the catch-all
        rules allow it: a group written for us can tighten `*`, never loosen it."""
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        return _allowed(self.ours, path) and _allowed(self.everyone, path)
