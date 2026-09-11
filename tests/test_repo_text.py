"""The suite's scanner reader: a non-UTF-8 file is one failure naming the
file, a readable one is its text, and a declared binary asset (a PNG) is the
text it carries beside its pixels — never skipped, never a traceback."""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from tests.repo_text import (
    MAX_INFLATED,
    PNG_SIGNATURE,
    is_binary_asset,
    png_text,
    repo_text,
)


def _chunk(kind: bytes, body: bytes) -> bytes:
    crc = zlib.crc32(kind + body).to_bytes(4, "big")
    return len(body).to_bytes(4, "big") + kind + body + crc


def _png(*chunks: bytes) -> bytes:
    ihdr = _chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x00\x00\x00\x00")
    return PNG_SIGNATURE + ihdr + b"".join(chunks) + _chunk(b"IEND", b"")


def test_repo_text_fails_by_name_on_a_file_that_is_not_text(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")
    assert repo_text(good) == "x = 1\n"
    latin = tmp_path / "latin.py"
    latin.write_bytes(b"# caf\xe9\n")
    with pytest.raises(pytest.fail.Exception, match=r"^latin.py: not UTF-8 text$"):
        repo_text(latin)


def test_is_binary_asset_is_the_declared_suffix_case_folded():
    assert is_binary_asset(Path("a/shot.png"))
    assert is_binary_asset(Path("a/SHOT.PNG"))
    assert not is_binary_asset(Path("a/shot.py"))
    assert not is_binary_asset(Path("a/png"))  # a name, not a suffix


def test_a_png_reads_as_every_text_channel_it_carries(tmp_path: Path):
    """Each of the four text chunk kinds surfaces, keyed, one per line: the
    plain, the compressed, the international (both flags) and the EXIF
    payload's ASCII fields — so a brand token in any of them is a scanner hit."""
    itxt_plain = b"Title\0\0\0en\0\0plain \xc3\xa9 text"
    itxt_zip = b"XML:com.adobe.xmp\0\1\0\0\0" + zlib.compress(b"<x>zipped</x>")
    shot = tmp_path / "shot.png"
    shot.write_bytes(
        _png(
            _chunk(b"tEXt", b"Comment\0hello"),
            _chunk(b"zTXt", b"Note\0\0" + zlib.compress(b"inflated")),
            _chunk(b"iTXt", itxt_plain),
            _chunk(b"iTXt", itxt_zip),
            _chunk(b"eXIf", b"MM\0*\0\0\0\x08Screenshot\0"),
            _chunk(b"IDAT", zlib.compress(b"\0\0")),
        )
    )
    assert repo_text(shot).splitlines() == [
        "Comment: hello",
        "Note: inflated",
        "Title: plain é text",
        "XML:com.adobe.xmp: <x>zipped</x>",
        "MM\0*\0\0\0\x08Screenshot\0",
    ]


def test_a_png_with_no_text_chunk_reads_empty(tmp_path: Path):
    shot = tmp_path / "shot.png"
    shot.write_bytes(_png(_chunk(b"IDAT", zlib.compress(b"\0\0"))))
    assert png_text(shot) == ""


def test_a_file_named_png_that_is_not_a_png_fails_by_name(tmp_path: Path):
    """The suffix is a claim, not a proof: a text file mis-named `.png` is
    refused, never skipped as if its pixels had been reviewed."""
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"some text a scanner must not miss\n")
    with pytest.raises(pytest.fail.Exception, match=r"^fake.png: not a PNG$"):
        repo_text(fake)


def test_a_truncated_or_over_inflating_png_fails_by_name(tmp_path: Path):
    cut = tmp_path / "cut.png"
    cut.write_bytes(_png(_chunk(b"tEXt", b"Comment\0hello"))[:-9])
    with pytest.raises(pytest.fail.Exception, match=r"^cut.png: truncated PNG chunk$"):
        png_text(cut)
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(
        _png(_chunk(b"zTXt", b"Note\0\0" + zlib.compress(b"\0" * (MAX_INFLATED + 1))))
    )
    with pytest.raises(pytest.fail.Exception, match=r"inflates past"):
        png_text(bomb)
    bad = tmp_path / "bad.png"
    bad.write_bytes(_png(_chunk(b"zTXt", b"Note\0\0not-zlib")))
    with pytest.raises(pytest.fail.Exception, match=r"corrupt compressed text chunk"):
        png_text(bad)
