"""The one reader for the suite's repository scanners — the layout tests that
walk models/, ingest/, classify/, pipeline/ or the tracked list and read each
file. It is the guards' reader (`scripts/review_common.py::read_text_or_error`)
with one difference: an unreadable file fails the test by name, never as a
`UnicodeDecodeError` traceback (LESSONS: traceback-at-boundary, hit again in
tests/ after the read boundary under scripts/ was closed). A declared binary
asset (`review_common.BINARY_ASSETS`) reads as the text it carries outside its
pixels — a PNG's text chunks — so the suite's scanners and `check_docs`'s
naming check see the same channels (LESSONS: site-fix). A test that reads its
own tmp_path file or a fixture through a parser is not a scanner and does not
read through here."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from review_common import ROOT, binary_asset_reader, read_text_or_error


def is_binary_asset(path: Path, root: Path = ROOT) -> bool:
    """True for a declared tracked binary asset: its directory and suffix."""
    return binary_asset_reader(path, root) is not None


def repo_text(path: Path, root: Path = ROOT) -> str:
    """The file's text — for a declared binary asset, the text beside its
    pixels; a file that is not readable as text fails the test naming it."""
    text, err = read_text_or_error(path, root)
    if text is None:
        pytest.fail(err)
    return text
