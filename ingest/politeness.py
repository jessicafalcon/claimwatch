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

# The one identifying header every fetch carries — the review crawler
# (ingest/fetch.py, httpx) and the open-data download (opendata/fetch.py,
# urllib) both set it from here, so who-we-are-on-the-network is defined once
# (Phase 7b: a second network module needed the same identity).
IDENTIFYING_HEADERS = {"User-Agent": USER_AGENT}

# One request's connect+read budget; a timeout is a refusal, not a retry.
TIMEOUT_S = 20.0

# The most pages one source may declare (spec Phase 3a, D6): the App Store
# feed's own cap is ten; a review profile with fourteen pages of forty reviews
# fits; a profile with thousands of reviews is cut off here — the most recent
# pages, one request every two seconds, about two minutes at most.
MAX_PAGES = 60

# A host may ask for a longer wait than ours (robots.txt Crawl-delay) and we
# obey it up to this ceiling; a host asking for more than a minute between
# requests is a one-line refusal, not a silent day-long sleep.
MAX_CRAWL_DELAY_S = 60.0

# The most a single response may be, in bytes, and the most a whole response
# may take to arrive. TIMEOUT_S bounds one socket operation; a page that keeps
# sending, or drips a byte at a time, is bounded here instead: the body is read
# in pieces and the fetch refuses the moment either ceiling is crossed. The
# largest page we read is a profile page of a few hundred kilobytes.
MAX_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_S = 60.0

# The only hosts the fetcher will ever contact; a URL elsewhere is refused
# before any request. A test pins that every fetchable declared source's host
# is here; a capture's meta is checked against its source's declared host, not
# this list, so shrinking it never unloads a legitimately captured row.
ALLOWED_HOSTS = ("itunes.apple.com", "play.google.com", "www.opinion-assurances.fr")
