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
import tempfile
from datetime import date
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
# A snapshot's five measures (spec Phase 3a, pinned decision 1) and, with
# them, its fingerprint: the measures plus the attribution the key does not
# carry — segment, channel, seeded_from — so a corrected attribution on an
# existing key is a same-key pair and refuses like a corrected figure, never
# silently dropped by the `where not exists` guard (A3 (a)).
_MEASURES = (
    "rating",
    "review_count",
    "one_star_share",
    "response_rate",
    "response_delay_days",
)
_FINGERPRINT = _MEASURES + ("segment", "channel", "seeded_from")
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
_SLUG = re.compile(r"^[a-z0-9-]+$")
_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


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
    """sha256 of the five measures and the three attribution values outside
    the key, in a fixed order and one spelling each, so a row is its numbers
    and its attribution and nothing else."""
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
    if not _DAY.match(value):
        raise _refuse_row(where, line, field, f"is not YYYY-MM-DD: {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise _refuse_row(where, line, field, f"is not a real day: {value!r}") from exc
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
            if not _SLUG.match(row[field]):
                raise _refuse_row(where, i, field, f"is not a slug: {row[field]!r}")
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


SNAPSHOT_KEY = ("source", "profile", "origin", "source_url", "captured_at")
# The columns a snapshot row may never leave empty: the four provenance
# columns and the profile (invariant 1).
_NON_EMPTY = ("source", "profile", "source_url", "captured_at")


def attribution_labels(rows_input: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The `segment` and `channel` values the loader accepts for one rebuild
    input (A4 (b)): the closed sets, plus the literal `sample` iff the input
    is `samples` — derived from the closed `INPUTS` set, never a caller's
    flag — so that label exists only in the samples database."""
    if rows_input not in INPUTS:
        raise ValueError(f"rows input {rows_input!r} not in {INPUTS}")
    extra = (SAMPLE,) if rows_input == "samples" else ()
    return SEGMENTS + extra, CHANNELS + extra


def _check_row(r: dict[str, object], run_id: str, rows_input: str) -> None:
    """A row outside a closed set, or with an empty provenance column, refuses
    naming the field — whatever produced it (A4 (b))."""
    where = r.get("where", r.get("source_url", "?"))
    segments, channels = attribution_labels(rows_input)
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
    conn, rows: list[dict[str, object]], run_id: str, rows_input: str = "captured"
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
    corpus partly written."""
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
    reset` then `make rebuild`."""
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
    this one (A8)."""
    return [
        (name, kind, nullable)
        for name, kind, nullable in conn.execute(
            "select column_name, data_type, is_nullable "
            "from information_schema.columns "
            "where table_schema = ? and table_name = ? order by ordinal_position",
            [warehouse.default_schema(conn), table],
        ).fetchall()
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
    conn.execute(
        _CREATE_RAW.sub(f"create temporary table {scratch}", statements[0], count=1)
    )
    try:
        declared = _columns(conn, scratch)
    finally:
        conn.execute(f"drop table {scratch}")
    existing = _columns(conn, table)
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


def build_derived(conn) -> None:
    for stage in ("staging", "marts"):
        for path in _sql_files(stage):
            warehouse.run_sql_file(conn, path)


def read_fixture(name: str) -> list[dict[str, str]]:
    with (ROOT / "fixtures" / name / "reviews.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


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
            "(source, external_id, source_url, captured_at, run_id, "
            " review_date, rating, title, body, content_hash) "
            "select ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
            "where not exists (select 1 from raw_reviews "
            "where source = ? and external_id = ? and content_hash = ?)",
            [
                r["source"],
                r["external_id"],
                r["source_url"],
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


def rebuild(
    target: str = "duckdb",
    rows: str = "none",
    *,
    database: str | Path | None = None,
    run_id: str | None = None,
    cache_dir: str | Path | None = None,
    manual_file: str | Path | None = None,
) -> dict[str, int]:
    """Build the warehouse from raw and return the per-table row counts.
    `captured` loads the anchors, the hand-entry file and every capture under
    data/cache (zero captures -> the anchors and the file); `none` runs the
    pipeline end to end with zero rows; `synthetic` loads the review fixture
    and the anchors; `samples` loads the anchors and the frozen samples
    through the real parsers. Every input goes through the same guards. With
    no `database`, each input builds its own file (`warehouse.database_for`)."""
    if database is None:
        database = warehouse.database_for(rows)
    conn = connect(target, database=database)
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
            load_reviews(conn, read_fixture("synthetic"), run_id or "synthetic")
        if rows == "captured":
            path = Path(manual_file) if manual_file is not None else MANUAL_SNAPSHOTS
            load_snapshots(conn, read_manual_snapshots(path), run_id or "manual", rows)
        for source, root, prefix in captures_for(rows, cache_dir):
            for capture_id, parsed in read_captures(root, source):
                stamp = prefix if rows == "samples" else f"{prefix}/{capture_id}"
                load_reviews(conn, parsed.reviews, run_id or stamp)
                load_snapshots(conn, parsed.snapshots, run_id or stamp, rows)
        build_derived(conn)
        return table_counts(conn)
    finally:
        conn.close()


def idempotency_check(
    target: str = "duckdb",
    rows: str = "synthetic",
    *,
    cache_dir: str | Path | None = None,
    manual_file: str | Path | None = None,
) -> tuple[bool, dict[str, int], dict[str, int]]:
    """Rebuild twice into one fresh database (different `run_id` each time, to
    prove `run_id` is not in the natural key) and compare per-table counts. Uses a
    throwaway file so it depends on no prior state and touches no working db."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idempotency.duckdb"
        first = rebuild(
            target,
            rows,
            database=db,
            run_id="run-1",
            cache_dir=cache_dir,
            manual_file=manual_file,
        )
        second = rebuild(
            target,
            rows,
            database=db,
            run_id="run-2",
            cache_dir=cache_dir,
            manual_file=manual_file,
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
