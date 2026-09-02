"""The manners of every fetch, in one place (CLAUDE.md -> Conventions,
Scraping; spec Phase 2, invariant 6). Nothing else in the repo defines a rate,
a User-Agent, a host list or a page cap; a test pins that.

We fetch the way a considerate person would: read the site's robots.txt first
and stop if it says no, say who we are in the User-Agent, wait at least two
seconds between requests to one host, ask for at most the feed's own page
count, and keep every page we fetched so a rebuild never asks again. No proxy,
no rotation, no retry loop: a site that refuses is a site we stop asking."""

from __future__ import annotations

# Seconds between two consecutive requests to the same host.
MIN_INTERVAL_S = 2.0

# Identifies the project and where to find it; never varied.
USER_AGENT = (
    "friction-ledger/0.1 (public-review study; "
    "+https://github.com/jessicafalcon/claimwatch)"
)

# One request's connect+read budget; a timeout is a refusal, not a retry.
TIMEOUT_S = 20.0

# The App Store feed serves at most ten pages per app and country.
MAX_PAGES = 10

# A host may ask for a longer wait than ours (robots.txt Crawl-delay) and we
# obey it up to this ceiling; a host asking for more than a minute between
# requests is a one-line refusal, not a silent day-long sleep.
MAX_CRAWL_DELAY_S = 60.0

# The only hosts the fetcher will ever contact; a URL elsewhere is refused
# before any request.
ALLOWED_HOSTS = ("itunes.apple.com",)
