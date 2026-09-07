"""The suite's scanner reader: a non-UTF-8 file is one failure naming the
file, a readable one is its text."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.repo_text import repo_text


def test_repo_text_fails_by_name_on_a_file_that_is_not_text(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")
    assert repo_text(good) == "x = 1\n"
    latin = tmp_path / "latin.py"
    latin.write_bytes(b"# caf\xe9\n")
    with pytest.raises(pytest.fail.Exception, match=r"^latin.py: not UTF-8 text$"):
        repo_text(latin)
