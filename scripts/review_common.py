"""Shared by scripts/review_gate.py, check_pins.py, check_docs.py and
check_backing.py (not a pytest file). One spec-path validator, one base-rev
validator, one diff-path reader, one section parser, one subprocess runner,
one file reader (UTF-8 text, or a declared binary asset's text channels), one
Makefile-target reader. Stdlib only.

The read boundary: every file a script reads and every subprocess it runs
goes through `read_text_or_error` / `readable` and `run` here, so a file that
is not UTF-8 text, a path that cannot be read or output that does not decode
is one line naming the input, never a traceback — the class, not the site
(LESSONS: traceback-at-boundary, site-fix). A grep test pins that no other
module under scripts/ reads or spawns on its own."""

from __future__ import annotations

import re
import subprocess
import sys
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A git rev used as an argv token: a safe charset and never a leading `-`.
_BASE = re.compile(r"^[\w./-]+$")

# A target is DECLARED by a rule line `name:` at column 0 (not `.PHONY`).
# `x:= v` and `x::= v` are assignments, not targets; `x::` (a double-colon rule) is one.
_TARGET_LINE = re.compile(r"^([a-z][a-z0-9-]*):(?!:?=)", re.M)
# A `make` target NAMED in backticks — the one regex check_docs and the gate share.
MAKE_TICK = re.compile(r"`make ([a-z][a-z0-9-]*)[^`]*`")
# Document classes (check_docs.py explains them); the gate's record files build on them.
LIVING_DOCS = ("CLAUDE.md", "README.md", "SPEC.md", "BACKING.md")
RECORD_DOCS = ("DECISIONS.md", "BACKLOG.md", "LESSONS.md")


class Refused(Exception):
    """A one-line refusal: printed as-is, exit 2, never a traceback."""


class Unreadable(Exception):
    """Why a file is not readable as text — one clause, reported after the
    path by `read_text_or_error`, never raised past it."""


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The PNG chunk types that carry text beside the pixels: the three textual
# chunks of the specification and the EXIF payload (its ASCII fields read
# through latin-1). A closed set: any other chunk is pixels or layout.
# REF: https://www.w3.org/TR/png-3/#11textinfo
PNG_TEXT_CHUNKS = frozenset({b"tEXt", b"zTXt", b"iTXt", b"eXIf"})
# The chunk types that carry no text — pixels, palette, colour, layout, timing
# (the specification's critical and ancillary chunks, APNG's three) and Apple's
# private `iDOT` (parallel-decode offsets; every macOS screenshot carries it).
# With the text chunks these are the whole closed set: a chunk of any other
# kind is refused by name rather than skipped, so no channel goes unread.
PNG_OTHER_CHUNKS = frozenset(
    {
        b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"cHRM", b"gAMA", b"iCCP",
        b"sBIT", b"sRGB", b"cICP", b"mDCV", b"cLLI", b"bKGD", b"hIST", b"pHYs",
        b"sPLT", b"tIME", b"acTL", b"fcTL", b"fdAT", b"iDOT",
    }
)  # fmt: skip
MAX_INFLATED = 1 << 20  # a compressed text chunk may not inflate past 1 MiB


def _inflate(data: bytes) -> bytes:
    inflater = zlib.decompressobj()
    try:
        out = inflater.decompress(data, MAX_INFLATED)
    except zlib.error:
        raise Unreadable("corrupt compressed text chunk") from None
    if not inflater.eof or inflater.unconsumed_tail:
        raise Unreadable(f"a text chunk inflates past {MAX_INFLATED} bytes")
    return out


def _fields(kind: bytes, body: bytes, count: int) -> list[bytes]:
    """`body` split on exactly `count` NUL separators, or malformed by name."""
    fields = body.split(b"\0", count)
    if len(fields) != count + 1 or not 1 <= len(fields[0]) <= 79:
        raise Unreadable(f"malformed {kind.decode('latin-1')} chunk")
    return fields


def _chunk_text(kind: bytes, body: bytes) -> str:
    """One text chunk decoded to `keyword: text`, each kind parsed to the shape
    the specification declares (a 1–79 byte keyword, its NUL separators, the
    flag and method bytes); a chunk off that shape is malformed by name."""
    if kind == b"eXIf":
        return body.decode("latin-1")
    if kind == b"tEXt":
        keyword, text = _fields(kind, body, 1)
    elif kind == b"zTXt":
        keyword, rest = _fields(kind, body, 1)
        if rest[:1] != b"\0":  # the one compression method
            raise Unreadable("malformed zTXt chunk")
        text = _inflate(rest[1:])
    else:  # iTXt: keyword, flag, method, language, translated keyword, text
        keyword, rest = _fields(kind, body, 1)
        if rest[:1] not in (b"\0", b"\1") or rest[1:2] != b"\0":
            raise Unreadable("malformed iTXt chunk")
        _, _, text = _fields(kind, keyword + b"\0" + rest[2:], 3)[1:]
        if rest[:1] == b"\1":
            text = _inflate(text)
    encoding = "utf-8" if kind == b"iTXt" else "latin-1"
    return f"{keyword.decode('latin-1')}: {text.decode(encoding, errors='replace')}"


def png_text(data: bytes) -> str:
    """The text a PNG carries beside its pixels, one chunk per line; bytes that
    are not a PNG, whose chunks are truncated, or that carry a chunk kind
    outside the closed set are `Unreadable` by name."""
    if not data.startswith(PNG_SIGNATURE):
        raise Unreadable("not a PNG")
    lines: list[str] = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(kind) != 4 or len(body) != length:
            raise Unreadable("truncated PNG chunk")
        if kind in PNG_TEXT_CHUNKS:
            lines.append(_chunk_text(kind, body))
        elif kind not in PNG_OTHER_CHUNKS:
            raise Unreadable(f"unknown PNG chunk {kind.decode('latin-1')!r}")
        pos += 12 + length  # length, type, body, CRC
    return "\n".join(lines)


# The tracked binary assets, each declared by the directory that holds it AND
# its suffix, with the reader for the text it carries beside its pixels (the
# Metabase demonstration screenshots, Phase 9g). The pixels are reviewed by
# eye; the text channels are read here, so every scanner — the suite's and
# `check_docs`'s naming check alike — sees the same channels. A closed set: a
# `.png` outside its declared directory is not an asset — it is expected to be
# UTF-8 text like every other tracked file and is reported by name when it is
# not, so a stray image has to be declared here before a scanner accepts it.
BINARY_ASSETS: tuple[tuple[str, str, Callable[[bytes], str]], ...] = (
    ("study/metabase/screenshots", ".png", png_text),
)


def binary_asset_reader(path: Path, root: Path = ROOT) -> Callable[[bytes], str] | None:
    """The declared reader for `path` (under `root`), or None for a text file:
    a match is the declared directory (exactly, no subdirectory) and the
    suffix, case-folded."""
    if not path.is_relative_to(root):
        return None
    rel = path.relative_to(root)
    for directory, suffix, reader in BINARY_ASSETS:
        if rel.parent.as_posix() == directory and rel.suffix.lower() == suffix:
            return reader
    return None


def die(exc: Refused) -> None:
    print(str(exc), file=sys.stderr)
    sys.exit(2)


def resolve_spec(arg: str, root: Path = ROOT) -> Path:
    """`--spec` must name an existing FILE under `<root>/specs/`; nothing else is
    derived from it. Empty, absolute, `../x`, a directory, or anything outside
    specs/ is refused."""
    if not arg or not arg.strip():
        raise Refused("refusing: SPEC is empty (usage: SPEC=specs/<file>.md)")
    if Path(arg).is_absolute():
        raise Refused(f"refusing: SPEC must be a path under specs/, got {arg!r}")
    specs = (root / "specs").resolve()
    target = (root / arg).resolve()
    if specs not in target.parents:
        raise Refused(f"refusing: SPEC must be a path under specs/, got {arg!r}")
    if not target.is_file():
        raise Refused(f"refusing: SPEC is not an existing file: {arg!r}")
    return target


def resolve_base(arg: str) -> str:
    """`--base` is a git rev used as an argv token: a safe charset and never a
    leading `-` (git would read it as an option). Refused, never a traceback."""
    if not arg or not _BASE.match(arg) or arg.startswith("-"):
        raise Refused(f"refusing: BASE must be a plain git rev, got {arg!r}")
    return arg


def diff_paths(out: str) -> set[str]:
    """Paths from `git diff -z --name-only`: NUL-separated, read whole — a
    space, a quote or a non-ASCII letter never splits or hides a path."""
    return {p for p in out.split("\0") if p}


def section(text: str, heading: str) -> str:
    """Body of the first `## <heading>…` section (heading matched as a prefix, so
    `Evidence (REQUIRED)` is found by `Evidence`); '' if absent."""
    m = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run `cmd`, capture stdout+stderr merged, never raise: a non-zero exit is
    returned, a missing executable is (127, one line), output that is not
    UTF-8 text is (1, one line) — never a traceback."""
    try:
        res = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except UnicodeDecodeError:
        return 1, f"output of {cmd[0]} is not UTF-8 text"
    return res.returncode, res.stdout + res.stderr


def shown(path: Path, root: Path) -> str:
    """The one form a report names a file in: its path relative to the repo
    root (its bare name only when it is not under the root)."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def read_text_or_error(
    path: Path, root: Path = ROOT
) -> tuple[str, None] | tuple[None, str]:
    """(text, None) or (None, one error line naming the path): a file that is
    not UTF-8 text or cannot be read is reported, never raised — exactly one
    side is None, so a caller never needs a fallback line. A declared binary
    asset (`BINARY_ASSETS`) reads as the text it carries beside its pixels."""
    reader = binary_asset_reader(path, root)
    try:
        if reader is not None:
            return reader(path.read_bytes()), None
        return path.read_text(encoding="utf-8"), None
    except Unreadable as exc:
        return None, f"{shown(path, root)}: {exc}"
    except UnicodeDecodeError:
        return None, f"{shown(path, root)}: not UTF-8 text"
    except OSError as exc:
        return None, f"{shown(path, root)}: cannot be read: {exc.strerror}"


def readable(
    files: list[Path], root: Path, errors: list[str]
) -> Iterator[tuple[Path, str]]:
    """Yield (file, text) for every file that reads; an unreadable one adds
    its error line to `errors` and is skipped, so a per-file check goes on."""
    for f in files:
        text, err = read_text_or_error(f, root)
        if text is None:
            errors.append(err)
            continue
        yield f, text


def make_targets(root: Path = ROOT) -> tuple[set[str], str | None]:
    """(targets the Makefile declares as rule lines, None), read as text — never
    `make -n`; or (an empty set, the one line naming why the Makefile did not
    read). The caller reports the line and checks nothing against the empty
    set: a reader that failed never hands back a default (LESSONS: empty-default)."""
    text, err = read_text_or_error(root / "Makefile", root)
    return (set(_TARGET_LINE.findall(text)), None) if text is not None else (set(), err)


def tail(text: str, n: int = 20) -> str:
    return "\n".join(text.splitlines()[-n:])
