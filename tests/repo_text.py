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


def repo_text(path: Path) -> str:
    """The file's text; a file that is not UTF-8 text fails the test naming it."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name
        pytest.fail(f"{shown}: not UTF-8 text")
