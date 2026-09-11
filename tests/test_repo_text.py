"""The suite's scanner reader: a non-UTF-8 file is one failure naming the
file, a readable one is its text, and a declared binary asset (a PNG) is the
text it carries beside its pixels — never skipped, never a traceback."""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from review_common import MAX_INFLATED, PNG_SIGNATURE, ROOT

from tests.repo_text import is_binary_asset, repo_text


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


SHOTS = "study/metabase/screenshots"


def test_is_binary_asset_is_the_declared_directory_and_suffix_case_folded(
    tmp_path: Path,
):
    """The declaration is a directory AND a suffix: a `.png` under the declared
    directory (any case) is an asset; the same suffix anywhere else, a
    subdirectory, or a bare name is not — an undeclared image is text to the
    scanners and fails by name like any other non-text file."""
    assert is_binary_asset(tmp_path / SHOTS / "shot.png", tmp_path)
    assert is_binary_asset(tmp_path / SHOTS / "SHOT.PNG", tmp_path)
    assert not is_binary_asset(tmp_path / "models" / "shot.png", tmp_path)
    assert not is_binary_asset(tmp_path / SHOTS / "sub" / "shot.png", tmp_path)
    assert not is_binary_asset(tmp_path / SHOTS / "shot.py", tmp_path)
    assert not is_binary_asset(tmp_path / SHOTS / "png", tmp_path)  # a name
    assert not is_binary_asset(Path("/elsewhere") / SHOTS / "shot.png", tmp_path)
    assert is_binary_asset(ROOT / SHOTS / "01-dashboard.png")  # the default root


def test_a_png_outside_the_declared_directory_fails_by_name(tmp_path: Path):
    stray = tmp_path / "models" / "stray.png"
    stray.parent.mkdir()
    stray.write_bytes(_png(_chunk(b"IDAT", zlib.compress(b"\0\0"))))
    with pytest.raises(
        pytest.fail.Exception, match=r"^models/stray.png: not UTF-8 text$"
    ):
        repo_text(stray, tmp_path)


def _asset(tmp_path: Path, name: str, data: bytes) -> Path:
    """A file at the declared screenshots path under a tmp root."""
    path = tmp_path / SHOTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_a_png_reads_as_every_text_channel_it_carries(tmp_path: Path):
    """Each of the four text chunk kinds surfaces, keyed, one per line: the
    plain, the compressed, the international (both flags) and the EXIF
    payload's ASCII fields — so a brand token in any of them is a scanner hit."""
    itxt_plain = b"Title\0\0\0en\0\0plain \xc3\xa9 text"
    itxt_zip = b"XML:com.adobe.xmp\0\1\0\0\0" + zlib.compress(b"<x>zipped</x>")
    shot = _asset(
        tmp_path,
        "shot.png",
        _png(
            _chunk(b"tEXt", b"Comment\0hello"),
            _chunk(b"zTXt", b"Note\0\0" + zlib.compress(b"inflated")),
            _chunk(b"iTXt", itxt_plain),
            _chunk(b"iTXt", itxt_zip),
            _chunk(b"eXIf", b"MM\0*\0\0\0\x08Screenshot\0"),
            _chunk(b"IDAT", zlib.compress(b"\0\0")),
        ),
    )
    assert repo_text(shot, tmp_path).splitlines() == [
        "Comment: hello",
        "Note: inflated",
        "Title: plain é text",
        "XML:com.adobe.xmp: <x>zipped</x>",
        "MM\0*\0\0\0\x08Screenshot\0",
    ]


def test_a_png_with_no_text_chunk_reads_empty(tmp_path: Path):
    shot = _asset(tmp_path, "shot.png", _png(_chunk(b"IDAT", zlib.compress(b"\0\0"))))
    assert repo_text(shot, tmp_path) == ""


def test_a_file_named_png_that_is_not_a_png_fails_by_name(tmp_path: Path):
    """The suffix is a claim, not a proof: a text file mis-named `.png` is
    refused, never skipped as if its pixels had been reviewed."""
    fake = _asset(tmp_path, "fake.png", b"some text a scanner must not miss\n")
    with pytest.raises(pytest.fail.Exception, match=rf"^{SHOTS}/fake.png: not a PNG$"):
        repo_text(fake, tmp_path)


def test_a_png_with_a_chunk_outside_the_closed_set_fails_by_name(tmp_path: Path):
    """The chunk kinds are a closed set — text (read), pixels/colour/layout
    (skipped) — so a private chunk that could carry text is refused by name,
    never silently skipped; the kinds macOS screenshots carry are in the set."""
    odd = _asset(tmp_path, "odd.png", _png(_chunk(b"prIv", b"hidden words")))
    with pytest.raises(pytest.fail.Exception, match=r"unknown PNG chunk 'prIv'"):
        repo_text(odd, tmp_path)
    mac = _asset(
        tmp_path,
        "mac.png",
        _png(
            _chunk(b"iCCP", b"p\0\0" + zlib.compress(b"icc")),
            _chunk(b"cICP", b"\1\r\0\1"),
            _chunk(b"pHYs", b"\0" * 9),
            _chunk(b"iDOT", b"\0" * 28),
            _chunk(b"IDAT", zlib.compress(b"\0\0")),
        ),
    )
    assert repo_text(mac, tmp_path) == ""


def test_a_truncated_or_over_inflating_png_fails_by_name(tmp_path: Path):
    cut = _asset(tmp_path, "cut.png", _png(_chunk(b"tEXt", b"Comment\0hello"))[:-9])
    with pytest.raises(
        pytest.fail.Exception, match=rf"^{SHOTS}/cut.png: truncated PNG chunk$"
    ):
        repo_text(cut, tmp_path)
    bomb = _asset(
        tmp_path,
        "bomb.png",
        _png(_chunk(b"zTXt", b"Note\0\0" + zlib.compress(b"\0" * (MAX_INFLATED + 1)))),
    )
    with pytest.raises(pytest.fail.Exception, match=r"inflates past"):
        repo_text(bomb, tmp_path)
    bad = _asset(tmp_path, "bad.png", _png(_chunk(b"zTXt", b"Note\0\0not-zlib")))
    with pytest.raises(pytest.fail.Exception, match=r"corrupt compressed text chunk"):
        repo_text(bad, tmp_path)
