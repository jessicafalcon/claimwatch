---
name: secure-by-construction
description: The security standard for this repo's real surface, applied while writing — foreign inputs parsed to a shape, paths derived not joined, no shell, decompression and size caps, safe YAML, the model prompt as a data boundary, secrets and personal data kept out of every tracked file and log, the Actions token, guarded destructive targets, hook conduct. Loads while a sensitive surface is being written; the security-reviewer is preloaded with the same text.
user-invocable: false
paths:
  - "ingest/**"
  - "opendata/**"
  - "classify/llm.py"
  - "classify/cache.py"
  - "pipeline/warehouse.py"
  - "pipeline/cli.py"
  - "Makefile"
  - ".github/**"
  - ".claude/hooks/**"
  - "scripts/**"
  - "dags/**"
---

Standing instructions while writing on a sensitive surface. This repo has no
web endpoint, no login, no session, no payment: do not import those
checklists. Its surface is fetching, keeping, holding and writing.

## What we do not own (parse it, cap it, refuse it by name)

Scraped pages and robots files, the model's reply, DAMIR rows, CLI variables
(`ROWS`, `SOURCE`, `MONTH`, `N`, `SPEC`, `BASE`), hook stdin, env vars, file
names under `data/cache/`, a capture's meta file.

- One declared shape per input (an anchored regex, a closed set, a typed
  parse with bounds) and a size cap; anything else is refused with the NAME
  of the input, never coerced.
- A path is derived from a validated slug, never joined from a variable.
  Refuse `..`, an absolute path, a quote, `;`, a newline. The final path
  resolves inside the cache root or `data/`; say so in code.
- A number from a foreign file is parsed to a declared decimal shape and
  bounds (the DAMIR amount, the snapshot figures, a rating's half-steps).

## Running things

- `subprocess` with a list; never `shell=True`; never an f-string into a
  command. The Makefile passes a value through `_Q` and keeps recipes one
  line; a variable never appears inside a recipe's shell text.
- SQL from Python: an identifier is interpolated only from the repo's own
  file list or a closed set, and the code says which; a value is a
  parameter.
- A gzip or zip member is read under a decompressed-byte cap, or the file
  carries the reason there is none (a developer-run path on a known portal
  is a reason; write it).
- `yaml.safe_load` only. No `pickle`, `eval`, `exec`, `literal_eval` on
  foreign text.

## Fetching (the platforms are not ours)

- Network code lives in `ingest/fetch.py` (the only `httpx` import) and
  `opendata/fetch.py` (stdlib `urllib`). Nowhere else.
- Every request: robots first (RFC 9309 matcher), the identifying header
  from `ingest/politeness.py`, ≥ 2 s per host (more if Crawl-delay asks),
  no retry, no proxy, at most 60 pages per source, hosts from the
  declaration only; a redirect to another host is refused, not followed.
- A source recorded as not fetchable (`fetchable=False`, reason and date in
  `sources.py` and DECISIONS) is refused before any request.
- Developer-run and `confirm`-gated: never run by an agent.

## The model call is a data boundary

- `classify/llm.py` is the one call site. Review text is untrusted: it goes
  in the user turn, the system prompt fixes the seven-slug closed set, the
  reply is parsed to whole tokens of that set, no tool is offered, a reply
  outside the set is `unclassified`. A directive inside a review can change
  nothing but that review's label.
- The decision cache is keyed `(review_id, prompt_version, model)` and holds
  no text. The SDK import is lazy; the no-key path loads it never.
- The paid path raises one typed, one-line error naming the model and the
  cause — never the key, never the review.

## Keeping (personal data) and holding (secrets)

- A review body, a reviewer's name, a claim number, a health detail never
  enters a tracked file, a log line, a test's output, a capture meta, a
  commit message, an exception message. Tracked outputs are numbers, slugs
  and dates: `data/snapshots/*.csv`, `data/damir/claim_cost_fit.csv`,
  `classify/eval/labels.csv` (`review_id`, `theme` only).
- The API key and warehouse credentials live in `.env` only; read by name;
  never in Actions, never printed. A refusal prints the variable's NAME.
- `.gitignore` covers `.env*`, `data/*` minus the two tracked subtrees,
  `*.duckdb`, `.claude/settings*.json`, `.mcp.json`. `git ls-files data/`
  shows only the two subtrees.

## Writing to the repo from a machine

- `ci.yml`: `permissions: contents: read`, `persist-credentials: false`,
  SHA-pinned actions, `uv sync --locked`, no secret.
- `weekly.yml`: the one `contents: write` workflow; `schedule` and
  `workflow_dispatch` only; stages `git add data/snapshots/` and nothing
  else; a fixed brand-free commit message; no key.
- A destructive, paid or fetching target needs the `confirm` GOAL in the
  same invocation; the stamp is a process id consumed either way; the spec's
  Threat model table (empty value, `../x`, `"; `, environment origin, no
  credentials) has a named test per cell. A new gate states what it does
  NOT hold against (`MAKEFILES`, `PATH`, a same-user process writing
  `data/`).

## Hooks and settings

- A hook parses stdin to one shape, else exits 0; fails OPEN only in the
  cases its header lists; times out (digits-only override); runs the suite
  in a reduced environment (PATH, HOME); is wired in the gitignored local
  settings, never a tracked `settings.json`.
- Before letting an agent edit on an inbound branch, its diff of
  `.claude/hooks/`, `tests/conftest.py`, `pyproject.toml` and `Makefile` is
  read first.

## Dependencies

- No package beyond the allowlist in CLAUDE.md → Conventions without a STOP
  and approval; `uv.lock` moves only with one. No scraping framework, no
  proxy client, no headless browser.

## Phrasing (Fable 5.1 safeguards)

- This is a review of our own code for bugs and weak spots. Ask and write
  "which input reaches this and what does it do", never "how to exploit".
  Keep base64 and raw captured pages out of tool output; grep a capture.
