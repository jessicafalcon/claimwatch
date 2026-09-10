"""The stranger acceptance test (Phase 9f).

The brief's Phase 9 done-when is that a stranger goes from the README's first
paragraph to any number's raw evidence without asking a human. These tests pin
the walk mechanically: every euro or percentage figure in the README wears one
of the four evidence tags and cites its own resolving BACKING row, the three
Beat 5 counts sit on tagged template lines, and the first paragraph and the
page/BACKING links resolve. The reader's last hop is README → `B<beat>.<n>` →
BACKING.md, which `make check-backing` already maps id → table → SQL → source.
"""

from __future__ import annotations

import re

from pipeline.warehouse import ROOT
from tests.repo_text import repo_text

README = ROOT / "README.md"
BACKING = ROOT / "BACKING.md"

TAG = re.compile(r"\b(?:Measured|Documented|Modeled|Pending)\b")
BID = re.compile(r"B\d+\.\d+")
FIGURE = re.compile(r"€\s?\d[\d.,]*|\d[\d.,]*\s?%")
BEAT5_COUNTS = ("1", "14", "4")


def _units(text: str) -> list[str]:
    """The README as logical units — one per heading, paragraph and list item,
    soft line wraps joined — with fenced blocks and inline code spans removed, so
    a figure and its tag on one wrapped bullet are read as one unit."""
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    body = re.sub(r"`[^`]*`", "", body)
    units: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            units.append(re.sub(r"\s+", " ", " ".join(current)).strip())
            current.clear()

    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped:
            flush()
        elif stripped.startswith(("- ", "#")):
            flush()
            current.append(stripped)
        else:
            current.append(stripped)
    flush()
    return [u for u in units if u]


def _backing_ids() -> set[str]:
    return set(BID.findall(repo_text(BACKING)))


def _figure_units() -> list[str]:
    return [u for u in _units(repo_text(README)) if FIGURE.search(u)]


def test_every_euro_or_percent_wears_a_tag() -> None:
    for unit in _figure_units():
        tags = TAG.findall(unit)
        assert len(tags) == 1, f"figure unit needs exactly one tag word: {unit!r}"


def test_every_tagged_figure_cites_a_resolving_row() -> None:
    real = _backing_ids()
    for unit in _figure_units():
        ids = BID.findall(unit)
        assert ids, f"figure unit cites no BACKING row: {unit!r}"
        unknown = [i for i in ids if i not in real]
        assert not unknown, f"figure unit cites a non-existent row {unknown}: {unit!r}"


def test_beat5_counts_use_the_tagged_template() -> None:
    units = _units(repo_text(README))
    for count in BEAT5_COUNTS:
        line = next((u for u in units if f"**{count}**" in u), None)
        assert line is not None, f"Beat 5 count **{count}** has no template line"
        assert "Measured" in line and "B5.1" in line, (
            f"Beat 5 count line must be Measured and cite B5.1: {line!r}"
        )


def test_readme_cites_only_real_backing_rows() -> None:
    real = _backing_ids()
    body = re.sub(r"```.*?```", "", repo_text(README), flags=re.S)
    cited = set(BID.findall(body))
    assert cited, "the README cites no BACKING row"
    assert cited <= real, (
        f"the README cites rows not in BACKING.md: {sorted(cited - real)}"
    )


def test_first_paragraph_links_into_evidence() -> None:
    text = repo_text(README)
    first = text.split("\n## ", 1)[0]
    assert re.search(r"\]\((?!https?://)[^)]+\)", first), (
        "the first paragraph carries no relative link into the evidence"
    )


def test_readme_links_to_study_and_backing() -> None:
    text = repo_text(README)
    assert "](study/friction_ledger.html)" in text, (
        "no link to the permanent study page"
    )
    assert "](BACKING.md)" in text, "no link to BACKING.md"


def test_readme_names_the_captured_rebuild_command() -> None:
    text = repo_text(README)
    assert "make rebuild ROWS=captured" in text, (
        "the captured-render rebuild command is not named"
    )
    assert "make study" in text, "`make study` is not named"
