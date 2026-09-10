"""The stranger acceptance test (Phase 9f).

The brief's Phase 9 done-when is that a stranger goes from the README's first
paragraph to any number's raw evidence without asking a human. These tests pin
the walk mechanically: every euro or percentage figure in the README carries one
tag→row citation, each Modeled figure equals its `tests/pins.py` value and cites
its *own* mart row (not merely a real one), the three Beat 5 counts sit on tagged
template lines bound to the same pins, and the first paragraph and the
page/BACKING links resolve. The reader's last hop is README → `B<beat>.<n>` →
BACKING.md, which `make check-backing` already maps id → table → SQL → source.
"""

from __future__ import annotations

import re

from pipeline.warehouse import ROOT
from tests import pins
from tests.repo_text import repo_text

README = ROOT / "README.md"
BACKING = ROOT / "BACKING.md"

BID = re.compile(r"B\d+\.\d+")
FIGURE = re.compile(r"€\s?\d[\d.,]*|\d[\d.,]*\s?%")
# One tag→row citation as the README writes it: `(Modeled — B4.2)`, em dash or hyphen.
CITATION = re.compile(r"\((Measured|Documented|Modeled|Pending)\s*[—-]\s*(B\d+\.\d+)\)")

# Each Modeled figure the README restates, its value read from the same pin the
# mart renders and the mart row it must cite (the per-figure "own row" pin).
_TIMER = pins.SLA_THRESHOLD_SAMPLE[pins.TIMER_DEFAULT_DAY]
FIGURE_ROWS = {
    f"€{_TIMER['timer_amount_eur']:.2f}": "B4.2",
    f"{pins.SLA_DEFAULT_SHARE * 100:.1f}%": "B4.2",
}
# Each Beat 5 checkable count, from its pin, on a template line citing B5.1.
BEAT5_COUNTS = {
    str(pins.BEAT5_MODEL_SITES): "B5.1",
    str(pins.BEAT3_FORMULA_ROWS): "B5.1",
    str(pins.BEAT5_EVIDENCE_TAGS): "B5.1",
}


def _units(text: str) -> list[str]:
    """The README as logical units — one per heading, paragraph and list item,
    soft line wraps joined — with fenced blocks, inline code spans and link
    targets removed, so a figure and its tag on one wrapped bullet read as one
    unit and a `%` inside a link target is not mistaken for a figure."""
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    body = re.sub(r"`[^`]*`", "", body)
    body = re.sub(r"\]\([^)]*\)", "]", body)
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
    figure_units = _figure_units()
    assert figure_units, "the README shows no euro or percent figure to check"
    for unit in figure_units:
        cites = CITATION.findall(unit)
        assert len(cites) == 1, (
            f"figure unit needs exactly one tag→row citation: {unit!r}"
        )


def test_every_tagged_figure_cites_a_resolving_row() -> None:
    real = _backing_ids()
    figure_units = _figure_units()
    assert figure_units, "the README shows no euro or percent figure to check"
    for unit in figure_units:
        rows = [row for _, row in CITATION.findall(unit)]
        assert rows, f"figure unit cites no BACKING row: {unit!r}"
        unknown = [r for r in rows if r not in real]
        assert not unknown, f"figure unit cites a non-existent row {unknown}: {unit!r}"


def test_modeled_figures_match_pins_and_cite_their_row() -> None:
    """The strong per-figure pin: each Modeled figure equals its `tests/pins.py`
    value (a model change breaks this until the README is updated) and cites its
    own mart row — a wrong-but-real citation fails here."""
    real = _backing_ids()
    text_units = _units(repo_text(README))
    for figure, row in FIGURE_ROWS.items():
        unit = next((u for u in text_units if figure in u), None)
        assert unit is not None, f"README is missing the pinned figure {figure}"
        rows = [r for _, r in CITATION.findall(unit)]
        assert rows == [row], (
            f"{figure} must cite exactly {row}, its own mart row: {unit!r}"
        )
        assert row in real


def test_beat5_counts_use_the_tagged_template() -> None:
    text_units = _units(repo_text(README))
    for count, row in BEAT5_COUNTS.items():
        line = next((u for u in text_units if f"**{count}**" in u), None)
        assert line is not None, f"Beat 5 count **{count}** has no template line"
        assert "Measured" in line and row in line, (
            f"Beat 5 count line must be Measured and cite {row}: {line!r}"
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
