"""The one reader for the suite's repository scanners — the layout tests that
walk models/, ingest/, classify/, pipeline/ or the tracked list and read each
file. A file that is not UTF-8 text fails the test by name, never as a
`UnicodeDecodeError` traceback (LESSONS: traceback-at-boundary, hit again in
tests/ after the read boundary under scripts/ was closed). A test that reads
its own tmp_path file or a fixture through a parser is not a scanner and does
not read through here."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.warehouse import ROOT

# Tracked binary assets a full-tree text scanner skips — read by eye in review,
# never decoded (the Metabase demonstration screenshots, Phase 9g). A closed set:
# a tracked file with any OTHER suffix is expected to be UTF-8 text and still
# fails by name if it is not (the traceback-at-boundary guard is preserved).
BINARY_ASSET_SUFFIXES = frozenset({".png"})


def is_binary_asset(path: Path) -> bool:
    """True for a declared tracked binary asset a text scanner should skip."""
    return path.suffix.lower() in BINARY_ASSET_SUFFIXES


def repo_text(path: Path) -> str:
    """The file's text; a file that is not UTF-8 text fails the test naming it."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name
        pytest.fail(f"{shown}: not UTF-8 text")
