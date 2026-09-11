"""The one reader for the suite's repository scanners — the layout tests that
walk models/, ingest/, classify/, pipeline/ or the tracked list and read each
file. A file that is not UTF-8 text fails the test by name, never as a
`UnicodeDecodeError` traceback (LESSONS: traceback-at-boundary, hit again in
tests/ after the read boundary under scripts/ was closed). A declared binary
asset reads as the text it carries outside its pixels — a PNG's text chunks —
so a scanner sees every channel a reviewer's eye cannot. A test that reads
its own tmp_path file or a fixture through a parser is not a scanner and does
not read through here."""

from __future__ import annotations

import zlib
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import pytest

from pipeline.warehouse import ROOT

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The PNG chunk types that carry text beside the pixels: the three textual
# chunks of the specification and the EXIF payload (its ASCII fields read
# through latin-1). A closed set: any other chunk is pixels or layout.
# REF: https://www.w3.org/TR/png-3/#11textinfo
PNG_TEXT_CHUNKS = frozenset({b"tEXt", b"zTXt", b"iTXt", b"eXIf"})
MAX_INFLATED = 1 << 20  # a compressed text chunk may not inflate past 1 MiB


def _fail(path: Path, why: str) -> NoReturn:
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name
    pytest.fail(f"{shown}: {why}")


def _inflate(path: Path, data: bytes) -> bytes:
    inflater = zlib.decompressobj()
    try:
        out = inflater.decompress(data, MAX_INFLATED)
    except zlib.error:
        _fail(path, "corrupt compressed text chunk")
    if not inflater.eof or inflater.unconsumed_tail:
        _fail(path, f"a text chunk inflates past {MAX_INFLATED} bytes")
    return out


def _chunk_text(path: Path, kind: bytes, body: bytes) -> str:
    """One text chunk decoded: `keyword: text` for the keyed kinds."""
    if kind == b"eXIf":
        return body.decode("latin-1")
    keyword, _, rest = body.partition(b"\0")
    if kind == b"tEXt":
        text = rest
    elif kind == b"zTXt":
        text = _inflate(path, rest[1:])  # one byte of compression method
    else:  # iTXt: flag, method, language\0, translated keyword\0, UTF-8 text
        compressed = rest[:1] == b"\1"
        _, _, rest = rest[2:].partition(b"\0")
        _, _, text = rest.partition(b"\0")
        if compressed:
            text = _inflate(path, text)
    encoding = "utf-8" if kind == b"iTXt" else "latin-1"
    return f"{keyword.decode('latin-1')}: {text.decode(encoding, errors='replace')}"


def png_text(path: Path) -> str:
    """The text a PNG carries beside its pixels, one chunk per line; a file
    that is not a PNG, or whose chunks are truncated, fails the test by name."""
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        _fail(path, "not a PNG")
    lines: list[str] = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(kind) != 4 or len(body) != length:
            _fail(path, "truncated PNG chunk")
        if kind in PNG_TEXT_CHUNKS:
            lines.append(_chunk_text(path, kind, body))
        pos += 12 + length  # length, type, body, CRC
    return "\n".join(lines)


# The tracked binary assets, each declared by the directory that holds it AND
# its suffix, with the reader for the text it carries beside its pixels (the
# Metabase demonstration screenshots, Phase 9g). The pixels are reviewed by
# eye; the text channels are scanned like any tracked file. A closed set: a
# `.png` outside its declared directory is not an asset — it is expected to be
# UTF-8 text like every other tracked file and fails by name when it is not,
# so a stray image has to be declared here before the scanners accept it.
BINARY_ASSETS: tuple[tuple[str, str, Callable[[Path], str]], ...] = (
    ("study/metabase/screenshots", ".png", png_text),
)


def binary_asset_reader(path: Path, root: Path = ROOT) -> Callable[[Path], str] | None:
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


def is_binary_asset(path: Path, root: Path = ROOT) -> bool:
    """True for a declared tracked binary asset: its directory and suffix."""
    return binary_asset_reader(path, root) is not None


def repo_text(path: Path, root: Path = ROOT) -> str:
    """The file's text — for a declared binary asset, the text beside its
    pixels; a file that is not UTF-8 text fails the test naming it."""
    reader = binary_asset_reader(path, root)
    if reader is not None:
        return reader(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _fail(path, "not UTF-8 text")
