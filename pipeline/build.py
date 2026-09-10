"""raw -> staging -> marts, run the same way twice (PROJECT_BRIEF.md §4.3,
docs/PLAN.md §4 decision 2). The stages:

  create_raw   -> run every sql/raw/*.sql (`create table if not exists`)
  load_reviews -> insert each row only if (source, external_id, content_hash)
                  is unseen; the rows come from the fixture (stdlib csv, no
                  pandas) or from the scraper's captures, each declared
                  source's through its declared parser (Phase 3a) — the SAME
                  guard for all
  load_snapshots-> insert each platform snapshot only if (source, profile,
                  origin, source_url, captured_at, content_hash) is unseen —
                  the key names what produced the row (A2) — and REFUSE a row
                  whose key is already there under other figures; the rows
                  come from the anchors fixture (Documented), the hand-entry
                  file under data/snapshots/ or a capture (Measured) — Phase 3a
  build_derived-> run sql/staging/*.sql then sql/marts/*.sql (`create or replace`)

Idempotency: raw is append-only keyed on the natural key + a content
fingerprint, so a re-run of an unchanged review inserts nothing and an edited
review (new fingerprint) appends a new row; staging keeps the latest capture.
`run_id` is stamped here in Python (never in SQL — no clock on the data path)
and is in no natural key and no mart's sort or key — a mart carries it through
as provenance only — so a changing `run_id` never duplicates a row or moves a
number; for a fixture input it is the input name and for captures the capture
id, making every rebuild from the same input byte-stable, not merely
count-stable. A rebuild reads captures from disk and never imports the
fetcher: no network on the data path."""

from __future__ import annotations

import csv
import hashlib
import re
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ingest.captures import parser_module, read_captures
from ingest.parsed import MEASURES, PageShapeError, count_in_range, review_rating
from ingest.sources import (
    CHANNELS,
    ORIGINS,
    PARSERS,
    SAMPLE,
    SEGMENTS,
    SOURCES,
    Source,
    by_name,
    sample_source,
)
from models import cost_model, guardrail_sim
from opendata.fit import read_fit
from pipeline import warehouse
from pipeline.warehouse import ROOT, connect

# The closed set of rebuild inputs, named by what they are (`ROWS=`, spec
# Phase 3a, pinned decision 5): the scraper's captures under data/ (the real
# run, the default), nothing, the synthetic fixture, or the frozen samples
# read as captures (the offline proof of every parser path).
INPUTS = ("captured", "none", "synthetic", "samples")
_SEP = "\x1f"  # unit separator — cannot appear in the CSV content fields
# The content fields whose hash is the fingerprint (provenance is excluded, so a
# re-capture of the same review at a new time is NOT a new row).
_CONTENT = ("rating", "review_date", "title", "body")
# A snapshot's five figures — the four measures and the review count (spec
# Phase 3a, pinned decision 1; `parsed.MEASURES` declares the four) — and,
# with them, its fingerprint: the figures plus the attribution the key does not
# carry — segment, channel, seeded_from — so a corrected attribution on an
# existing key is a same-key pair and refuses like a corrected figure, never
# silently dropped by the `where not exists` guard (A3 (a)).
_FIGURES = (
    "rating",
    "review_count",
    "one_star_share",
    "response_rate",
    "response_delay_days",
)
_FINGERPRINT = _FIGURES + ("segment", "channel", "seeded_from")
ANCHORS = ROOT / "fixtures" / "anchors" / "platform_snapshots_seed.csv"
ANCHOR_COLUMNS = (
    "platform",
    "profile",
    "segment",
    "channel",
    "rating",
    "review_count",
    "one_star_share",
    "response_rate",
    "response_delay_days",
    "captured_at",
    "source_url",
    "seeded_from",
)
# Figures a person read off a page whose terms forbid a robot (spec Phase 3a,
# pinned decision 4): a tracked file under the one tracked subtree of data/,
# hand-edited, eight columns, no address and no name.
MANUAL_SNAPSHOTS = ROOT / "data" / "snapshots" / "manual_snapshots.csv"
MANUAL_COLUMNS = (
    "source",
    "captured_at",
    "rating",
    "review_count",
    "one_star_share",
    "response_rate",
    "response_delay_days",
    "read_from",
)
# The fetched rating series' tracked home (spec Phase 4, pinned decision 1): a
# numbers-only file under the one tracked subtree of data/, written by `make
# record-snapshots` from the week's capture, read by `rebuild ROWS=captured`.
# It names a source by its slug and carries only the capture's instant and the
# five figures — the address, profile, segment and channel come from the
# declaration (D1), so no brand and no review body ever enters the file. The
# instant is the capture's own (`captured_at`, stamped once per fetch), so a
# fetched row here and its live-cache twin share the snapshot key and the
# double read is a no-op (invariant: offline-stable).
FETCHED_SNAPSHOTS = ROOT / "data" / "snapshots" / "fetched_snapshots.csv"
FETCHED_COLUMNS = (
    "source",
    "captured_at",
    "rating",
    "review_count",
    "one_star_share",
    "response_rate",
    "response_delay_days",
)
# A shape guard matches the whole value: `fullmatch` at the call, and `\A…\Z`
# in the shape itself so any other call matches whole too — a `$` under
# `match` accepts a trailing newline, so `x\n` would pass as the slug `x`
# (round 5, code-reviewer #6; exit pass, #8).
_SLUG = re.compile(r"\A[a-z0-9-]+\Z")
_DAY = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
# A capture instant, the shape `ingest/captures.py` writes in each meta and the
# fetched file carries as its `captured_at` (the snapshot key), so a fetched
# row matches its live-cache twin exactly.
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\Z")


def content_hash(row: dict[str, str]) -> str:
    """sha256 of the content fields, in a fixed order, so it is stable across runs
    and machines."""
    payload = _SEP.join(_canonical(row[c]) for c in _CONTENT)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    """A measure's one spelling: an absent measure is the empty string, a
    decimal drops trailing zeros and never takes exponent form, so `4.9` and
    `4.90` — one figure, two spellings — hash alike and a re-spelling of a
    tracked file is not a corrected figure (round 2, code-reviewer #12). A
    string is hashed as written: the text `1.0` and the text `1` are two
    spellings here, and what makes a review rating one fingerprint is that
    `load_reviews` admits it only as a member of `REVIEW_RATINGS`, so `1.0`
    as text never reaches this hash (round 4, functionality-tester #7)."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def snapshot_hash(row: dict[str, object]) -> str:
    """sha256 of the five snapshot figures (the four measures and the review
    count) and the three attribution values outside the key, in a fixed order
    and one spelling each, so a row is its numbers and its attribution and
    nothing else."""
    payload = _SEP.join(_canonical(row.get(c, "")) for c in _FINGERPRINT)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refuse_row(where: str, line: int, field: str, why: str) -> PageShapeError:
    return PageShapeError(f"{where}: line {line}: field {field!r} {why}")


def _decimal(value: str, *, where: str, line: int, field: str) -> Decimal | None:
    """An optional measure, exactly as written, inside its column's digit
    shape and range (`parsed.MEASURES`, A4 (a)); empty -> None. A figure with
    more decimals than the column's scale is outside the shape and refuses
    here, never rounded by the engine at the load."""
    if value == "":
        return None
    measure = MEASURES[field]
    number = measure.exact(value)
    if number is None:
        raise _refuse_row(
            where,
            line,
            field,
            f"is not a number the column holds (decimal({measure.precision}, "
            f"{measure.scale}), digits only): {value!r}",
        )
    if not measure.in_range(number):
        raise _refuse_row(
            where,
            line,
            field,
            f"is outside the range {measure.lo}..{measure.hi}: {value!r}",
        )
    return number


def _count(value: str, *, where: str, line: int, field: str) -> int | None:
    """An optional count (A4 (e): a figure the brief does not give is empty,
    like the other measures); a present one fits the column's shape."""
    if value == "":
        return None
    count = count_in_range(value)  # the column's shape: never a traceback
    if count is None:
        raise _refuse_row(
            where,
            line,
            field,
            f"is not a non-negative integer the count column holds: {value!r}",
        )
    return count


def _day(value: str, *, where: str, line: int, field: str) -> str:
    if not _DAY.fullmatch(value):
        raise _refuse_row(where, line, field, f"is not YYYY-MM-DD: {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise _refuse_row(where, line, field, f"is not a real day: {value!r}") from exc
    return value


def _stamp(value: str, *, where: str, line: int, field: str) -> str:
    """A capture instant, `YYYY-MM-DDTHH:MM:SS` and a real one — the shape the
    fetched file carries so its key matches the live capture's."""
    if not _INSTANT.fullmatch(value):
        raise _refuse_row(where, line, field, f"is not an instant: {value!r}")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise _refuse_row(
            where, line, field, f"is not a real instant: {value!r}"
        ) from exc
    return value


def _measures(row: dict[str, str], *, where: str, line: int) -> dict[str, object]:
    out: dict[str, object] = {
        "rating": _decimal(row["rating"], where=where, line=line, field="rating"),
        "review_count": _count(
            row["review_count"], where=where, line=line, field="review_count"
        ),
    }
    for field in ("one_star_share", "response_rate", "response_delay_days"):
        out[field] = _decimal(row[field], where=where, line=line, field=field)
    return out


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != columns:
            raise PageShapeError(f"{where}: columns must be exactly {columns}")
        rows = list(reader)
    for i, row in enumerate(rows, 2):
        if None in row or None in row.values():
            raise PageShapeError(f"{where}: line {i}: wrong number of cells")
    return rows


def read_anchors(path: Path = ANCHORS) -> list[dict[str, object]]:
    """The brief's §6 public figures, parsed strictly to snapshot rows with
    `origin = anchor` (Documented downstream). A row outside the declared shape
    refuses the seed, naming line and field."""
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    out: list[dict[str, object]] = []
    for i, row in enumerate(_read_csv(path, ANCHOR_COLUMNS), 2):
        for field in ("platform", "profile"):
            if not _SLUG.fullmatch(row[field]):
                raise _refuse_row(where, i, field, f"is not a slug: {row[field]!r}")
        if row["profile"] == SAMPLE:  # the sample declaration's profile, its alone
            raise _refuse_row(where, i, "profile", "is the sample declaration's")
        if row["segment"] not in SEGMENTS:
            raise _refuse_row(
                where, i, "segment", f"not in {SEGMENTS}: {row['segment']!r}"
            )
        if row["channel"] not in CHANNELS:
            raise _refuse_row(
                where, i, "channel", f"not in {CHANNELS}: {row['channel']!r}"
            )
        if not row["source_url"].startswith("https://"):
            raise _refuse_row(where, i, "source_url", "is not an https address")
        if not row["seeded_from"].strip():
            raise _refuse_row(where, i, "seeded_from", "is empty")
        out.append(
            {
                "where": f"{where}: line {i}",
                "source": row["platform"],
                "profile": row["profile"],
                "segment": row["segment"],
                "channel": row["channel"],
                "origin": "anchor",
                **_measures(row, where=where, line=i),
                "source_url": row["source_url"],
                "captured_at": _day(
                    row["captured_at"], where=where, line=i, field="captured_at"
                ),
                "seeded_from": row["seeded_from"],
            }
        )
    return out


def read_manual_snapshots(path: Path = MANUAL_SNAPSHOTS) -> list[dict[str, object]]:
    """Hand-read figures -> snapshot rows with `origin = manual` (Measured
    downstream). The row names a declared source with NO parser — exactly the
    set `hand_entries_are_unique` covers (A3 (c)), so two hand entries can
    never collapse onto one snapshot key — and platform, address, profile,
    segment and channel come from the declaration, so the file carries no
    address and no name; a source with a parser gets its figures from its
    capture, never from a hand entry. A missing file is zero rows (a clone
    before any reading)."""
    if not path.is_file():
        return []
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    out: list[dict[str, object]] = []
    for i, row in enumerate(_read_csv(path, MANUAL_COLUMNS), 2):
        try:
            source = by_name(row["source"])
        except KeyError as exc:
            raise _refuse_row(
                where, i, "source", f"is not a declared source: {row['source']!r}"
            ) from exc
        if source.parser is not None:
            raise _refuse_row(
                where,
                i,
                "source",
                f"{row['source']!r} has a parser: a hand entry names a source with "
                "no parser, since a parsed source's figures come from its capture",
            )
        if row["read_from"] != "page":
            raise _refuse_row(
                where, i, "read_from", f"must be the word 'page': {row['read_from']!r}"
            )
        out.append(
            {
                "where": f"{where}: line {i}",
                "source": source.platform,
                "profile": source.profile,
                "segment": source.segment,
                "channel": source.channel,
                "origin": "manual",
                **_measures(row, where=where, line=i),
                "source_url": source.listing,
                "captured_at": _day(
                    row["captured_at"], where=where, line=i, field="captured_at"
                ),
                "seeded_from": "",
            }
        )
    return out


def read_fetched_snapshots(path: Path = FETCHED_SNAPSHOTS) -> list[dict[str, object]]:
    """The tracked fetched series -> snapshot rows with `origin = fetch`
    (Measured downstream). The row names a declared source that IS fetchable
    and HAS a parser — the mirror of a hand entry (which names a source with no
    parser) — since only such a source produces a fetched capture; the
    address, profile, segment and channel come from its declaration, so the
    file carries no brand and no review body. The address is the source's first
    page (`pages[0]`), the page every declared fetchable source carries its
    aggregate on, so a fetched row's key equals its live-cache twin's and the
    two never double-count. A missing file is zero rows (a clone before the
    first weekly run)."""
    if not path.is_file():
        return []
    where = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    out: list[dict[str, object]] = []
    for i, row in enumerate(_read_csv(path, FETCHED_COLUMNS), 2):
        try:
            source = by_name(row["source"])
        except KeyError as exc:
            raise _refuse_row(
                where, i, "source", f"is not a declared source: {row['source']!r}"
            ) from exc
        if not (source.fetchable and source.parser is not None):
            raise _refuse_row(
                where,
                i,
                "source",
                f"{row['source']!r} is not a fetchable, parsed source: a fetched "
                "row names a source the weekly scrape reads into a capture",
            )
        out.append(
            {
                "where": f"{where}: line {i}",
                "source": source.platform,
                "profile": source.profile,
                "segment": source.segment,
                "channel": source.channel,
                "origin": "fetch",
                **_measures(row, where=where, line=i),
                "source_url": source.pages[0],
                "captured_at": _stamp(
                    row["captured_at"], where=where, line=i, field="captured_at"
                ),
                "seeded_from": "",
            }
        )
    return out


SNAPSHOT_KEY = ("source", "profile", "origin", "source_url", "captured_at")
# The columns a snapshot row may never leave empty: the four provenance
# columns and the profile (invariant 1).
_NON_EMPTY = ("source", "profile", "source_url", "captured_at")


def attribution_labels(
    rows_input: str, profile: object
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The `segment` and `channel` values the loader accepts for one row: the
    closed sets, plus the literal `sample` iff the input is `samples` — the
    file a sample declaration exists in, derived from the closed `INPUTS`
    set (A4 (b)) — AND the row's `profile` is the sample declaration's
    (`SAMPLE`, the one profile only a `sample=True` declaration may carry),
    so the label is a sample row's alone: an anchor or a hand-entered row
    under `samples` refuses it like any other input does (A9 (c))."""
    if rows_input not in INPUTS:
        raise ValueError(f"rows input {rows_input!r} not in {INPUTS}")
    extra = (SAMPLE,) if rows_input == "samples" and profile == SAMPLE else ()
    return SEGMENTS + extra, CHANNELS + extra


def _check_row(r: dict[str, object], run_id: str, rows_input: str) -> None:
    """A row outside a closed set, or with an empty provenance column, refuses
    naming the field — whatever produced it (A4 (b))."""
    where = r.get("where", r.get("source_url", "?"))
    segments, channels = attribution_labels(rows_input, r.get("profile"))
    for field, allowed in (
        ("origin", ORIGINS),
        ("segment", segments),
        ("channel", channels),
    ):
        if r.get(field) not in allowed:
            raise PageShapeError(
                f"{where}: field {field!r} is not in {allowed}: {r.get(field)!r}"
            )
    for field in _NON_EMPTY:
        if not isinstance(r.get(field), str) or not r[field].strip():
            raise PageShapeError(f"{where}: field {field!r} is empty")
    if not run_id.strip():
        raise PageShapeError(f"{where}: field 'run_id' is empty")


def load_snapshots(
    conn, rows: list[dict[str, object]], run_id: str, rows_input: str
) -> None:
    """Append each snapshot not already present under its natural key + hash —
    the same guard shape as `load_reviews`. The key (A2) names what produced
    the row: the platform, the profile, how the row came to be and the address
    it was read from — a platform root for an anchor, the declared listing
    address for a hand-read row, the page address for a capture — and its day
    or instant. A row whose key is already in raw under OTHER figures or
    another attribution is refused with one line: that arises from a corrected
    hand entry, a re-frozen seed or a parser whose fingerprint changed, and
    the fix is
    `make confirm reset` then `make rebuild`, since the corpus is rebuilt
    from tracked inputs. Nothing is tiebroken downstream: the key is unique
    in raw. The batch is one transaction (A4 (a)): a refusal on any row
    leaves none of the batch in raw, so a refused rebuild never leaves the
    corpus partly written. `rows_input` — which closed set of labels applies —
    is required and is the rebuild's input, a member of `INPUTS`, never a
    signature's default (A8 (e))."""
    conn.execute("begin transaction")
    try:
        _load_snapshots(conn, rows, run_id, rows_input)
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def _load_snapshots(
    conn, rows: list[dict[str, object]], run_id: str, rows_input: str
) -> None:
    for r in rows:
        _check_row(r, run_id, rows_input)
        h = snapshot_hash(r)
        key = [r[c] for c in SNAPSHOT_KEY]
        seen = {
            row[0]
            for row in conn.execute(
                "select content_hash from raw_platform_snapshots "
                "where source = ? and profile = ? and origin = ? "
                "and source_url = ? and captured_at = ?",
                key,
            ).fetchall()
        }
        if seen and seen != {h}:
            where = r.get("where", r["source_url"])
            raise PageShapeError(
                f"{where}: a snapshot for ({r['source']}, {r['profile']}, "
                f"{r['origin']}, {r['captured_at']}) is already in the corpus with "
                "other figures or another attribution — a corrected entry, a "
                "re-frozen seed or a changed parse needs `make confirm reset` "
                "then `make rebuild`"
            )
        conn.execute(
            "insert into raw_platform_snapshots "
            "(source, profile, segment, channel, origin, rating, review_count, "
            " one_star_share, response_rate, response_delay_days, source_url, "
            " captured_at, run_id, seeded_from, content_hash) "
            "select ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
            "where not exists (select 1 from raw_platform_snapshots "
            "where source = ? and profile = ? and origin = ? and source_url = ? "
            "and captured_at = ? and content_hash = ?)",
            [
                r["source"],
                r["profile"],
                r["segment"],
                r["channel"],
                r["origin"],
                r["rating"],
                r["review_count"],
                r["one_star_share"],
                r["response_rate"],
                r["response_delay_days"],
                r["source_url"],
                r["captured_at"],
                run_id,
                r.get("seeded_from", ""),
                h,
                *key,
                h,
            ],
        )


def source_pages(sources: tuple[Source, ...] = SOURCES) -> list[dict[str, str]]:
    """One row per declared page address: the closed set of `source_url` values
    a source's rows can carry, with the attribution they inherit."""
    return [
        {
            "source": s.platform,
            "source_url": url,
            "profile": s.profile,
            "segment": s.segment,
            "channel": s.channel,
            "captured_at": s.declared_on,
        }
        for s in sources
        for url in s.pages
    ]


def write_source_pages(
    conn, run_id: str, sources: tuple[Source, ...] = SOURCES
) -> None:
    """Append each declared page not already present under (source, source_url)
    + the hash of its attribution — the same guard shape as the other loaders.
    A declared page whose attribution differs from the row already in raw
    REFUSES the rebuild (A3 (a)): a page's attribution is one fact, not a
    series, and the review join must stay one-to-one, so a re-declaration
    never appends a second row for one address; the fix is `make confirm
    reset` then `make rebuild`. The batch is one transaction, as the review
    and snapshot loaders' are: a refusal on the third declaration leaves the
    first two's pages uncommitted (A9 (b))."""
    conn.execute("begin transaction")
    try:
        _write_source_pages(conn, run_id, sources)
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def _write_source_pages(conn, run_id: str, sources: tuple[Source, ...]) -> None:
    for r in source_pages(sources):
        h = hashlib.sha256(
            _SEP.join((r["profile"], r["segment"], r["channel"])).encode("utf-8")
        ).hexdigest()
        seen = {
            row[0]
            for row in conn.execute(
                "select content_hash from raw_source_pages "
                "where source = ? and source_url = ?",
                [r["source"], r["source_url"]],
            ).fetchall()
        }
        if seen and seen != {h}:
            raise PageShapeError(
                f"{r['source_url']}: the declared page is already in the corpus "
                "under another attribution (profile, segment or channel) — a "
                "re-declaration needs `make confirm reset` then `make rebuild`"
            )
        conn.execute(
            "insert into raw_source_pages "
            "(source, source_url, profile, segment, channel, captured_at, run_id, "
            " content_hash) "
            "select ?, ?, ?, ?, ?, ?, ?, ? "
            "where not exists (select 1 from raw_source_pages "
            "where source = ? and source_url = ? and content_hash = ?)",
            [
                r["source"],
                r["source_url"],
                r["profile"],
                r["segment"],
                r["channel"],
                r["captured_at"],
                run_id,
                h,
                r["source"],
                r["source_url"],
                h,
            ],
        )


def _sql_files(stage: str) -> list[Path]:
    """The sql/<stage>/*.sql files in name order (deterministic). A missing or
    empty stage directory yields no files (marts is empty in Phase 1)."""
    return sorted((ROOT / "sql" / stage).glob("*.sql"))


_CREATE_RAW = re.compile(r"^create table if not exists ([a-z_]+)\b")
_COMMENT = re.compile(r"--[^\n]*")


def _statements(sql: str) -> list[str]:
    """The statements a SQL file holds, comments stripped, empty ones dropped —
    so a phrase in a header comment is never mistaken for a statement (A8)."""
    return [part.strip() for part in _COMMENT.sub("", sql).split(";") if part.strip()]


def _columns(conn, table: str) -> list[tuple[str, str, str]]:
    """(name, type, is_nullable) per column in position order, in the engine's
    own vocabulary, read from the schema the engine names as its default
    (`warehouse.default_schema`): a same-named table in another schema is not
    this one (A8). The position is the catalog's `ordinal_position`, a value
    read and sorted on here, never the order the engine happens to return
    rows in (round 5, functionality-tester #1)."""
    rows = conn.execute(
        "select ordinal_position, column_name, data_type, is_nullable "
        "from information_schema.columns "
        "where table_schema = ? and table_name = ?",
        [warehouse.default_schema(conn), table],
    ).fetchall()
    return [
        (name, kind, nullable)
        for _, name, kind, nullable in sorted(rows, key=lambda r: int(r[0]))
    ]


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = ? and table_name = ?",
            [warehouse.default_schema(conn), table],
        ).fetchone()[0]
        > 0
    )


def _describe(column: tuple[str, str, str]) -> str:
    name, kind, nullable = column
    return f"{name!r} {kind} {'nullable' if nullable == 'YES' else 'not null'}"


def check_raw_declaration(conn, path: Path) -> None:
    """A raw table that already exists must be the one its file declares (A7,
    A8). `create table if not exists` keeps an older column silently and the
    engine casts into it on insert — 109 half-step ratings rounded on the
    first live run — so the declaration is created as a temporary table under
    a scratch name, both column lists (name, type, nullability, by position)
    are read back from information_schema in the engine's own words, and the
    first difference refuses the rebuild naming position, column and both
    sides. A table not yet created passes. The file is exactly one statement,
    and only that statement is run for the scratch, so nothing else in a raw
    file can reach the corpus during the check; a table already sitting under
    the scratch name refuses, naming itself, since the corpus is not what is
    wrong then."""
    where_file = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    statements = _statements(path.read_text(encoding="utf-8"))
    if len(statements) != 1:
        raise PageShapeError(
            f"{where_file}: holds {len(statements)} statements, not one "
            "`create table if not exists`"
        )
    m = _CREATE_RAW.match(statements[0])
    if m is None:
        raise PageShapeError(
            f"{where_file}: is not one `create table if not exists` statement"
        )
    table = m.group(1)
    if not _table_exists(conn, table):
        return
    scratch = f"declared_{table}"
    if _table_exists(conn, scratch):
        raise PageShapeError(
            f"{where_file}: a table {scratch!r} already exists in the database "
            "and is not one this repo builds — remove it, then `make rebuild` "
            "(the corpus is not what is wrong)"
        )
    try:
        conn.execute(
            _CREATE_RAW.sub(f"create temporary table {scratch}", statements[0], count=1)
        )
        try:
            declared = _columns(conn, scratch)
        finally:
            conn.execute(f"drop table {scratch}")
        existing = _columns(conn, table)
    except warehouse.DriverError as exc:
        # The one statement the file holds did not parse as one — a `--` or a
        # `;` inside a literal, say — or the catalog read or the drop failed:
        # the engine's refusal is relayed as this module's one line, never a
        # traceback (round 5, security-reviewer #4, functionality-tester #7;
        # the whole scratch block since the exit pass, code-reviewer #6).
        raise PageShapeError(
            f"{where_file}: the engine refused the declaration as one statement: "
            + " ".join(str(exc).split())
        ) from exc
    where = f"{where_file}: the corpus's table {table}"
    tail = "a changed raw declaration needs `make confirm reset` then `make rebuild`"
    for position, (have, want) in enumerate(
        zip(existing, declared, strict=False), start=1
    ):
        if have != want:
            raise PageShapeError(
                f"{where}: column {position} is {_describe(have)} in the "
                f"database, {_describe(want)} in the file — {tail}"
            )
    if len(existing) != len(declared):
        extra = existing[len(declared) :] or declared[len(existing) :]
        side = (
            "in the database only"
            if len(existing) > len(declared)
            else "in the file only"
        )
        raise PageShapeError(f"{where}: column {extra[0][0]!r} is {side} — {tail}")


def create_raw(conn) -> None:
    for path in _sql_files("raw"):
        check_raw_declaration(conn, path)
        warehouse.run_sql_file(conn, path)


# The marts that count the classifier's output: they read stg_classified_reviews,
# which Python fills in the classify step (pipeline/cli.py) after staging. The
# generic pass runs before classify, so it would build them empty — the classify
# step runs them instead (build_theme_share_marts), after the table is filled.
POST_CLASSIFY_MARTS = frozenset(
    {"theme_share_by_month.sql", "theme_share_by_segment.sql"}
)


def build_derived(conn) -> None:
    for stage in ("staging", "marts"):
        for path in _sql_files(stage):
            if stage == "marts" and path.name in POST_CLASSIFY_MARTS:
                continue  # the classify step runs it, once its input is filled
            warehouse.run_sql_file(conn, path)


def write_classified_reviews(conn, rows, run_id: str) -> None:
    """Fill `stg_classified_reviews` from the combined classifier's output: one
    row per `(source, external_id, theme)`. `rows` is at the review x theme grain
    classify_all returns (already sorted, so a re-run is byte-identical). The
    table is cleared first, so a re-populate is idempotent; no clock and no
    address is invented — a classification carries only its run_id."""
    conn.execute("begin transaction")
    try:
        conn.execute("delete from stg_classified_reviews")
        for source, external_id, theme in rows:
            conn.execute(
                "insert into stg_classified_reviews "
                "(source, external_id, theme, run_id) values (?, ?, ?, ?)",
                [source, external_id, theme, run_id],
            )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def build_theme_share_marts(conn) -> None:
    """Run the two theme-share marts (B2.2, B2.5) after stg_classified_reviews is
    filled. Segment is a review column (Phase 7a, A1), so the marts group by it
    with no join — a review is counted under exactly one segment, on any input."""
    for name in sorted(POST_CLASSIFY_MARTS):
        warehouse.run_sql_file(conn, ROOT / "sql" / "marts" / name)


def write_classifier_quality(
    conn,
    scores,
    *,
    answer_key: str,
    heldout_fold: int,
    run_id: str,
    tag: str = "Measured",
) -> None:
    """Fill the `classifier_quality` mart its `.sql` created empty: one row per
    scored label. `scores` is the gate's per-label grades (attributes `label`,
    `hits`, `predicted`, `actual`, `precision`, `recall`); the scoring itself,
    which reads the answer key, lives in `classify/eval/` — this inserter takes the
    grades in and never reads the key. The three provenance values a computed
    metric has (`answer_key`, `heldout_fold`, `run_id`) and the `tag` are passed
    in, so no clock and no address is invented here. The table is cleared first,
    so a re-populate is idempotent; rows go in the order given (the gate's fixed
    label order), so a re-run is byte-identical."""
    conn.execute("begin transaction")
    try:
        conn.execute("delete from classifier_quality")
        for s in scores:
            conn.execute(
                "insert into classifier_quality (label, hits, predicted, actual, "
                " precision, recall, heldout_fold, answer_key, run_id, tag) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    s.label,
                    s.hits,
                    s.predicted,
                    s.actual,
                    s.precision,
                    s.recall,
                    heldout_fold,
                    answer_key,
                    run_id,
                    tag,
                ],
            )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


_MODEL_TAG = "Modeled"


def read_model_fit(path: Path | None = None) -> cost_model.Fit:
    """Read the tracked lognormal fit and shape it into the cost model's `Fit`:
    the two log-moments, the sample size behind them, and the median cell
    (`emp_p50`). This is the one place the artifact is read for the model — the
    caller hands the result to `write_model_marts`, so `models/` reads no file.
    A malformed or unreadable artifact (a hand-corrupted tracked file) is refused
    as a `PageShapeError`, so the `model` and `rebuild` CLI paths print one line
    and exit 2 rather than a traceback; `path` lets a test exercise that."""
    try:
        fit, gof = read_fit() if path is None else read_fit(path)
    except (ValueError, OSError) as exc:
        raise PageShapeError(f"the fit artifact is unreadable: {exc}") from exc
    emp_p50 = next(d.empirical for d in gof if d.decile == 50)
    return cost_model.Fit(mu=fit.mu, sigma=fit.sigma, n=fit.n, emp_p50=emp_p50)


def write_model_marts(conn, fit: cost_model.Fit, run_id: str) -> None:
    """Fill the three cost-model marts (B3.1–B3.4) from `models/cost_model.py` —
    the one place the formulas and parameters are written. Every number is a
    `FORMULAS` callable evaluated over the parameters or a `PARAMETERS` cell; no
    literal is typed here. Cleared and inserted in one transaction, rows in
    parameter / scenario / FORMULAS / grid order, so a re-run is byte-identical;
    `run_id` is provenance (in no key or sort) and the Modeled tag is stamped.
    `rebuild()` calls this after `build_derived` on every input, so every caller
    sees filled marts."""
    params = cost_model.parameters(fit)
    values = {p.name: p.default for p in params}
    conn.execute("begin transaction")
    try:
        for table in ("cost_model_params", "cost_model_outputs", "cost_curves"):
            conn.execute(f"delete from {table}")
        for p in params:
            conn.execute(
                "insert into cost_model_params (name, default_value, unit, sourcing, "
                " citation, low, high, run_id, tag) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    p.name,
                    p.default,
                    p.unit,
                    p.sourcing,
                    p.citation,
                    p.low,
                    p.high,
                    run_id,
                    _MODEL_TAG,
                ],
            )
        for scenario in cost_model.SCENARIOS:
            outputs = cost_model.evaluate(values, scenario)
            grid, crossovers = cost_model.curves(values, scenario)
            for f in cost_model.POINT_FORMULAS:
                _insert_output(conn, scenario, f, outputs[f.name], run_id)
            for f in cost_model.CURVE_FORMULAS:
                _insert_output(conn, scenario, f, crossovers[f.name], run_id)
            for row in grid:
                conn.execute(
                    "insert into cost_curves (scenario, flag_rate, fraud_saved, "
                    " friction_cost, net, is_default, run_id, tag) "
                    "values (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        scenario,
                        row["flag_rate"],
                        row["fraud_saved"],
                        row["friction_cost"],
                        row["net"],
                        row["is_default"],
                        run_id,
                        _MODEL_TAG,
                    ],
                )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def _insert_output(conn, scenario: str, formula, value, run_id: str) -> None:
    """One (scenario, formula) row of cost_model_outputs — the expression beside
    its value and the unit the entry carries. A curve whose crossover never
    happens inserts NULL (its unit stays `rate`)."""
    conn.execute(
        "insert into cost_model_outputs "
        "(scenario, name, expression, value, unit, run_id, tag) "
        "values (?, ?, ?, ?, ?, ?, ?)",
        [
            scenario,
            formula.name,
            formula.expression,
            value,
            formula.unit,
            run_id,
            _MODEL_TAG,
        ],
    )


@contextmanager
def _no_pandas_probe() -> Iterator[None]:
    """Suppress DuckDB's per-value `import pandas` probe for the duration of a bulk
    insert. Binding a Python value, DuckDB checks whether it is a pandas type by
    importing pandas; pandas is not installed here (a hard project rule — no pandas
    on a pipeline path) and Python does not cache a failed import, so the check
    re-scans `sys.path` on every value — ~4,000 rows × 10 columns per rebuild turns
    a sub-second write into ~5 s, and every rebuild (and every test that rebuilds)
    pays it. A sentinel `None` in `sys.modules` makes `import pandas` fail
    immediately with no path scan; it is set only around the insert and restored
    after, and the repo never uses DuckDB's dataframe API, so nothing else is
    affected. DECISIONS → Phase 8b Gotchas."""
    sentinel = object()
    previous = sys.modules.get("pandas", sentinel)
    sys.modules["pandas"] = None  # type: ignore[assignment]
    try:
        yield
    finally:
        if previous is sentinel:
            del sys.modules["pandas"]
        else:
            sys.modules["pandas"] = previous  # type: ignore[assignment]


def _insert_rows(conn, table: str, columns: str, rows: list[list]) -> None:
    """Insert `rows` into `table` with one `executemany`, under the no-pandas-probe
    guard. `table` and `columns` are literals from the caller (no user input
    reaches the SQL); the placeholder count is the columns' arity."""
    if not rows:
        return
    placeholders = ",".join(["?"] * len(rows[0]))
    with _no_pandas_probe():
        conn.executemany(
            f"insert into {table} ({columns}) values ({placeholders})", rows
        )


def write_sim_marts(conn, fit: cost_model.Fit, run_id: str) -> None:
    """Fill the two simulator marts (B4.1–B4.3) from models/guardrail_sim.py — the
    one place the draw, the hold and the share-under count are written; the
    threshold itself is the cost model's formula, read at baseline. Every number
    is a callable over the parameters; no literal is typed here. Cleared and
    inserted in one transaction via `_insert_rows` (one guarded `executemany` per
    mart — the ~4,000 sim rows make the per-value pandas probe worth suppressing),
    rows in scenario / rank and day order, so a re-run is byte-identical.
    `rebuild()` calls this after write_model_marts on every input, so every caller
    sees filled marts."""
    params = cost_model.defaults(fit)
    sim_rows = [
        [
            row["scenario"],
            row["curves_scenario"],
            row["claim_rank"],
            row["quantile"],
            row["amount_eur"],
            row["loop_days"],
            row["hold_days"],
            row["outcome"],
            run_id,
            _MODEL_TAG,
        ]
        for sim in guardrail_sim.SIM_SCENARIOS
        for row in guardrail_sim.simulate(params, sim.name)
    ]
    sla_rows = [
        [
            row["timer_days"],
            row["timer_amount_eur"],
            row["share_under"],
            row["is_default"],
            run_id,
            _MODEL_TAG,
        ]
        for row in guardrail_sim.threshold_table(params)
    ]
    conn.execute("begin transaction")
    try:
        for table in ("guardrail_sim", "sla_threshold"):
            conn.execute(f"delete from {table}")
        _insert_rows(
            conn,
            "guardrail_sim",
            "scenario, curves_scenario, claim_rank, quantile, amount_eur, "
            "loop_days, hold_days, outcome, run_id, tag",
            sim_rows,
        )
        _insert_rows(
            conn,
            "sla_threshold",
            "timer_days, timer_amount_eur, share_under, is_default, run_id, tag",
            sla_rows,
        )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def read_fixture(name: str) -> list[dict[str, str]]:
    with (ROOT / "fixtures" / name / "reviews.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def segment_by_platform(sources: tuple[Source, ...] = SOURCES) -> dict[str, str]:
    """platform -> segment, from the real declarations — how a review loaded from
    the synthetic fixture (which carries no segment of its own) is stamped with
    its segment. Every declaration of one platform shares that platform's
    segment; a platform declared under two segments is a declaration bug and
    refuses here rather than stamping a review at random (Phase 7a, A1)."""
    out: dict[str, str] = {}
    for s in sources:
        if out.setdefault(s.platform, s.segment) != s.segment:
            raise ValueError(
                f"platform {s.platform!r} is declared under two segments "
                f"({out[s.platform]!r} and {s.segment!r})"
            )
    return out


def _reviews_with_segment(
    rows: list[dict[str, str]], segment: str
) -> list[dict[str, str]]:
    """The review rows with `segment` stamped on each — attribution from the
    source they were loaded from (Phase 7a, A1)."""
    return [{**r, "segment": segment} for r in rows]


def _fixture_reviews_with_segment(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """The synthetic fixture reviews, each stamped with its platform's segment.
    A fixture review from a platform no source declares refuses the rebuild —
    it could not be attributed (Phase 7a, A1)."""
    seg = segment_by_platform()
    out: list[dict[str, str]] = []
    for r in rows:
        platform = r["source"]
        if platform not in seg:
            raise PageShapeError(
                f"synthetic review {platform}/{r.get('external_id', '?')}: "
                f"platform {platform!r} is not a declared source, so it has no "
                "segment"
            )
        out.append({**r, "segment": seg[platform]})
    return out


def load_reviews(conn, rows: list[dict[str, str]], run_id: str) -> None:
    """Append each review not already present under its natural key + content
    hash. ANSI `insert ... select ... where not exists (...)`, parameterized — no
    reader function in SQL, so the load stays portable. The batch is one
    transaction, as a snapshot batch is (A4 (a)): a refused rating in the
    fifth row leaves rows one to four uncommitted, so a refused rebuild never
    leaves raw partly written (A8 (b))."""
    conn.execute("begin transaction")
    try:
        _load_reviews(conn, rows, run_id)
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def _load_reviews(conn, rows: list[dict[str, str]], run_id: str) -> None:
    for r in rows:
        rating = review_rating(r["rating"])
        if rating is None:
            raise _refuse_row(
                f"{r['source']}/{r['external_id']}",
                0,
                "rating",
                f"is not a half-step 1..5 (parsed.REVIEW_RATINGS): {r['rating']!r}",
            )
        h = content_hash(r)
        conn.execute(
            "insert into raw_reviews "
            "(source, external_id, source_url, segment, captured_at, run_id, "
            " review_date, rating, title, body, content_hash) "
            "select ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
            "where not exists (select 1 from raw_reviews "
            "where source = ? and external_id = ? and content_hash = ?)",
            [
                r["source"],
                r["external_id"],
                r["source_url"],
                r["segment"],
                r["captured_at"],
                run_id,
                r["review_date"],
                rating,
                r["title"],
                r["body"],
                h,
                r["source"],
                r["external_id"],
                h,
            ],
        )


# Reviews per month — a pipeline-health query, not a study number and not a mart
# (no SPEC panel shows it, so a sql/marts/ file would be an orphan). It lived in
# pipeline/metrics.py until Phase 9e folded that module away; the query moves here
# beside table_counts (a query is not an orphan — the orphan rule bites marts),
# still printed by `make rebuild`, still portability-linted (tests/test_sql_portable).
# Plain ANSI: substr on the review's own ISO date, group by, count(*). No clock
# (time is review_date), no dialect. `order by` is fine — a query, not a table.
REVIEWS_PER_MONTH = """
select
    source,
    substr(review_date, 1, 7) as month,
    count(*) as n
from stg_reviews
group by source, substr(review_date, 1, 7)
order by source, month
"""


def reviews_per_month(conn) -> list[tuple[str, str, int]]:
    """(source, 'YYYY-MM', reviews) per month over the deduplicated reviews."""
    return [
        (str(s), str(m), int(n))
        for s, m, n in conn.execute(REVIEWS_PER_MONTH).fetchall()
    ]


# The model SDK the classifier calls. The import needle is BUILT from this, never
# spelled as a literal, so this module is not itself a false match for the
# one-call-site walk below (and so tests/test_llm.py's guard, which reads the same
# walk, does not flag build.py) — putting the literal "import <sdk>" in a non-test
# module would count it and break that guard.
_MODEL_CLIENT = "anthropic"


def model_call_sites() -> list[str]:
    """The repository modules that import the model client — the one place a model
    makes a decision (Classification contract: classify/llm.py, and nowhere else).
    B5.1's fact counts these, so it is counted from the source, not a literal, and
    cannot drift; tests/test_llm.py's guard reads the same walk. Tests and the
    virtualenv are not repository modules and are skipped."""
    needle_import = f"import {_MODEL_CLIENT}"
    needle_from = f"from {_MODEL_CLIENT}"
    sites: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        posix = path.as_posix()
        if "/.venv/" in posix or "/tests/" in posix:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:  # a boundary: a non-text .py refuses by name
            raise ValueError(f"{path.relative_to(ROOT)}: not UTF-8 text") from exc
        if needle_import in source or needle_from in source:
            sites.append(path.relative_to(ROOT).as_posix())
    return sites


def write_determinism_facts(conn, run_id: str, *, tag: str = "Measured") -> None:
    """Fill the `determinism_facts` mart (B5.1): the checkable facts about the
    repository, each counted from the code it describes. Not corpus-gated — a repo
    fact is constant on any input — so this runs inside rebuild() on every input.
    The tag-set size is study/model.py::TAGS, the render contract's own tag set (a
    leaf module: no warehouse import, so importing it here makes no cycle); the
    formula count is the FORMULAS the study displays beside their output in B3.1;
    the model-decision count is the one-call-site walk. The table is cleared first
    so a re-populate is idempotent; rows go in a fixed order, so a re-run is
    byte-identical."""
    from study.model import TAGS  # a leaf constant (the four evidence tags)

    facts = (
        ("model_call_sites", len(model_call_sites())),
        ("formulas_shown", len(cost_model.FORMULAS)),
        ("evidence_tags", len(TAGS)),
    )
    conn.execute("begin transaction")
    try:
        conn.execute("delete from determinism_facts")
        for fact, value in facts:
            conn.execute(
                "insert into determinism_facts (fact, value, run_id, tag) "
                "values (?, ?, ?, ?)",
                [fact, value, run_id, tag],
            )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


# The review-pipeline stages B5.2 counts, in flow order: as-scraped, deduped,
# classified (one row per review x theme). Each key is a table name, so a count
# equals a direct count(*) of that stage; the closed tuple is the only source of
# the names interpolated below (no user input reaches the SQL).
_ROW_COUNT_STAGES = ("raw_reviews", "stg_reviews", "stg_classified_reviews")


def write_pipeline_row_counts(conn, run_id: str, *, tag: str = "Measured") -> None:
    """Fill the `pipeline_row_counts` mart (B5.2): one row per review-pipeline
    stage, each value a direct count(*) of that stage's table. Runs in the CLI
    classify path (after stg_classified_reviews is filled), so the classified
    stage is counted; corpus-gated at render like classifier_quality. The table is
    cleared first so a re-populate is idempotent; the stages go in flow order, so a
    re-run is byte-identical."""
    conn.execute("begin transaction")
    try:
        conn.execute("delete from pipeline_row_counts")
        for stage in _ROW_COUNT_STAGES:
            value = conn.execute(f"select count(*) from {stage}").fetchone()[0]
            conn.execute(
                "insert into pipeline_row_counts (stage, value, run_id, tag) "
                "values (?, ?, ?, ?)",
                [stage, value, run_id, tag],
            )
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def table_counts(conn) -> dict[str, int]:
    """Row count per table in the default schema — the reproducibility signal
    `idempotency-check` diffs. The schema is the engine's own answer
    (`warehouse.default_schema`), never a name spelled here."""
    names = [
        row[0]
        for row in conn.execute(
            "select table_name from information_schema.tables "
            "where table_schema = ? order by table_name",
            [warehouse.default_schema(conn)],
        ).fetchall()
    ]
    return {n: conn.execute(f"select count(*) from {n}").fetchone()[0] for n in names}


def captures_for(
    rows: str, cache_root: str | Path | None = None
) -> list[tuple[Source, Path, str]]:
    """What a capture-fed rebuild reads: for `captured`, every declared source
    with a parser and its cache directory under the cache root (the one
    binding in `ingest/sources.py`, or `cache_root` in tests); for `samples`,
    every parser's frozen sample under its sample declaration. The third
    element is the `run_id` prefix. The other inputs read no capture."""
    if rows == "captured":
        from ingest import sources  # the module attribute, so tests can redirect it

        root = Path(cache_root) if cache_root is not None else sources.CACHE_ROOT
        return [
            (s, root / s.platform / s.name, f"{s.platform}/{s.name}")
            for s in SOURCES
            if s.parser is not None
        ]
    if rows == "samples":
        out = []
        for parser in PARSERS:
            src = sample_source(parser)
            out.append(
                (src, parser_module(parser).SAMPLE_DIR, f"sample:{src.platform}")
            )
        return out
    return []


def harvest_snapshots(
    cache_root: str | Path | None = None,
) -> list[dict[str, str]]:
    """The week's fetched snapshots as tracked-file rows: for every declared
    fetchable, parsed source, each capture's snapshot as a source slug, the
    capture's instant and the five figures in one canonical spelling — nothing
    else, so no address and no review body leaves the capture. Reuses
    `read_captures` (the one parser path); reads captures from disk, never the
    network."""
    from ingest import sources  # the module attribute, so tests can redirect it

    root = Path(cache_root) if cache_root is not None else sources.CACHE_ROOT
    rows: list[dict[str, str]] = []
    for s in SOURCES:
        if not (s.fetchable and s.parser is not None):
            continue
        for _capture_id, parsed in read_captures(root / s.platform / s.name, s):
            for snap in parsed.snapshots:
                rows.append(
                    {
                        "source": s.name,
                        "captured_at": str(snap["captured_at"]),
                        **{f: _canonical(snap.get(f, "")) for f in _FIGURES},
                    }
                )
    return rows


def record_snapshots(
    path: str | Path = FETCHED_SNAPSHOTS, cache_root: str | Path | None = None
) -> int:
    """Append this week's fetched snapshots to the tracked file, numbers only,
    and return how many rows were new. A `(source, captured_at)` already in the
    file is left alone (re-recording the same capture is a no-op), so the write
    is idempotent; the file is rewritten in a stable `(source, captured_at)`
    order so a re-record with nothing new leaves a byte-identical file and an
    empty git diff. A missing file starts from the header."""
    path = Path(path)
    existing = _read_csv(path, FETCHED_COLUMNS) if path.is_file() else []
    seen = {(r["source"], r["captured_at"]) for r in existing}
    new = 0
    merged = {(r["source"], r["captured_at"]): r for r in existing}
    for r in harvest_snapshots(cache_root):
        key = (r["source"], r["captured_at"])
        if key not in seen:
            seen.add(key)
            new += 1
        merged[key] = {c: r[c] for c in FETCHED_COLUMNS}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FETCHED_COLUMNS)
        writer.writeheader()
        for key in sorted(merged):
            writer.writerow(merged[key])
    return new


def rebuild(
    target: str = "duckdb",
    rows: str = "none",
    *,
    root: str | Path | None = None,
    run_id: str | None = None,
    cache_dir: str | Path | None = None,
    manual_file: str | Path | None = None,
    fetched_file: str | Path | None = None,
) -> dict[str, int]:
    """Build the warehouse from raw and return the per-table row counts.
    `captured` loads the anchors, the hand-entry file, the tracked fetched
    file and every capture under data/cache (zero captures -> the anchors and
    the two files); `none` runs the
    pipeline end to end with zero rows; `synthetic` loads the review fixture
    and the anchors; `samples` loads the anchors and the frozen samples
    through the real parsers. Every input goes through the same guards. The
    file is always `warehouse.database_for(rows, root)`: a caller names the
    directory the files live in, never the file an input lands in, so the
    literal `sample` can exist only in the samples file (A8 (e))."""
    if rows not in INPUTS:
        raise ValueError(f"rows input {rows!r} not in {INPUTS}")
    conn = connect(target, database=warehouse.database_for(rows, root))
    try:
        create_raw(conn)
        if rows != "none":
            # every declaration the input loads, the samples' under `samples`,
            # so every captured row joins exactly one page (A4 (c))
            declared = SOURCES + (
                tuple(sample_source(p) for p in PARSERS) if rows == "samples" else ()
            )
            write_source_pages(conn, run_id or "declared", declared)
            load_snapshots(conn, read_anchors(), run_id or "anchors", rows)
        if rows == "synthetic":
            load_reviews(
                conn,
                _fixture_reviews_with_segment(read_fixture("synthetic")),
                run_id or "synthetic",
            )
        if rows == "captured":
            path = Path(manual_file) if manual_file is not None else MANUAL_SNAPSHOTS
            load_snapshots(conn, read_manual_snapshots(path), run_id or "manual", rows)
            fetched = (
                Path(fetched_file) if fetched_file is not None else FETCHED_SNAPSHOTS
            )
            load_snapshots(
                conn, read_fetched_snapshots(fetched), run_id or "fetched", rows
            )
        for source, capture_dir, prefix in captures_for(rows, cache_dir):
            for capture_id, parsed in read_captures(capture_dir, source):
                stamp = prefix if rows == "samples" else f"{prefix}/{capture_id}"
                load_reviews(
                    conn,
                    _reviews_with_segment(parsed.reviews, source.segment),
                    run_id or stamp,
                )
                load_snapshots(conn, parsed.snapshots, run_id or stamp, rows)
        build_derived(conn)
        # the model and simulator marts need no key, no reviews and no classify
        # step — they compute over the tracked fit, so they fill inside rebuild()
        # on every input, and idempotency-check (which calls rebuild() only) sees
        # them. One read of the fit feeds both writers.
        fit = read_model_fit()
        write_model_marts(conn, fit, run_id or "model")
        write_sim_marts(conn, fit, run_id or "model")
        # The repo facts (B5.1) are constant on any input and need no key, no
        # reviews and no classify step, so they fill here beside the model marts —
        # on every ROWS input, none included, and covered by idempotency-check.
        write_determinism_facts(conn, run_id or "model")
        return table_counts(conn)
    finally:
        conn.close()


def idempotency_check(
    target: str = "duckdb",
    rows: str = "synthetic",
    *,
    cache_dir: str | Path | None = None,
    manual_file: str | Path | None = None,
    fetched_file: str | Path | None = None,
) -> tuple[bool, dict[str, int], dict[str, int]]:
    """Rebuild twice into one fresh database (different `run_id` each time, to
    prove `run_id` is not in the natural key) and compare per-table counts. Uses a
    throwaway file so it depends on no prior state and touches no working db."""
    with tempfile.TemporaryDirectory() as tmp:
        first = rebuild(
            target,
            rows,
            root=tmp,
            run_id="run-1",
            cache_dir=cache_dir,
            manual_file=manual_file,
            fetched_file=fetched_file,
        )
        second = rebuild(
            target,
            rows,
            root=tmp,
            run_id="run-2",
            cache_dir=cache_dir,
            manual_file=manual_file,
            fetched_file=fetched_file,
        )
    return first == second, first, second


def built_databases() -> list[Path]:
    """Every database file a rebuild of this repo can have written, whatever
    its input was called when it ran: the corpus, and `<stem>.<input>.duckdb`
    beside it for ANY input name — today's four and the names earlier phases
    used (`app-store`, `empty`), which a list drawn from INPUTS would miss.
    The shape is `warehouse.database_for`'s, read back as a pattern."""
    base = warehouse.DEFAULT_DB
    beside = (
        sorted(base.parent.glob(f"{base.stem}.*{base.suffix}"))
        if base.parent.is_dir()
        else []
    )
    return [base] + [p for p in beside if p != base]


def reset(target: str = "duckdb", *, database: str | Path | None = None) -> list[Path]:
    """Delete the DuckDB files (and their write-ahead logs): with no `database`,
    every file this repo built — the real corpus and one per rebuild input,
    past or present (`built_databases`). The CLI gates this on the `confirm`
    goal of the same invocation; this function does the deletion once
    confirmed. Returns
    the files removed."""
    if target != "duckdb":
        raise ValueError(f"reset only handles the DuckDB file, not {target!r}")
    dbs = built_databases() if database is None else [Path(database)]
    removed: list[Path] = []
    for db in dbs:
        for p in (db, db.with_name(db.name + ".wal")):
            if p.exists():
                p.unlink()
                removed.append(p)
    return removed
