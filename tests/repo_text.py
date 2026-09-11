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


# Tracked binary assets and the reader for the text each carries beside its
# pixels (the Metabase demonstration screenshots, Phase 9g). The pixels are
# reviewed by eye; the text channels are scanned like any tracked file. A
# closed set: a tracked file with any OTHER suffix is expected to be UTF-8
# text and still fails by name if it is not.
BINARY_ASSET_READERS: dict[str, Callable[[Path], str]] = {".png": png_text}


def is_binary_asset(path: Path) -> bool:
    """True for a declared tracked binary asset, by suffix, case-folded."""
    return path.suffix.lower() in BINARY_ASSET_READERS


def repo_text(path: Path) -> str:
    """The file's text — for a declared binary asset, the text beside its
    pixels; a file that is not UTF-8 text fails the test naming it."""
    if is_binary_asset(path):
        return BINARY_ASSET_READERS[path.suffix.lower()](path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _fail(path, "not UTF-8 text")
