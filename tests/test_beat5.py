"""Phase 9e — Beat 5: the facts you can check, and reproducibility (spec
Invariants / Done-when). B5.1 (determinism_facts) is Measured and NOT
corpus-gated — a repo fact is constant on any input, so the committed synthetic
page shows the numbers; B5.2 (pipeline_row_counts) is Measured behind the corpus
gate, like Beat 2. These tests do what the bytes cannot: prove each B5.1 fact
equals the code it counts, that B5.2's stage counts equal a direct count(*),
that B5.2 gates the way Beat 2 does, that pipeline_row_counts (a classify-path
mart outside `idempotency-check`) is stable across a re-classify, and that the
render is byte-stable."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from models.cost_model import FORMULAS
from pipeline.build import model_call_sites
from pipeline.warehouse import ROOT, connect
from study import export, panels
from study.model import TAGS, Panel, Point, RenderRefused, Series, check_panel
from study.panels import beat3_panels, beat5_panels
from tests import pins
from tests.conftest import build_study_db

pytestmark = pytest.mark.slow  # slow: builds a warehouse; out of the edit-loop hook


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat5-syn"), "synthetic")


@pytest.fixture(scope="module")
def none_db(tmp_path_factory) -> Path:
    return build_study_db(tmp_path_factory.mktemp("beat5-none"), "none")


def _mutated(src: Path, tmp_path: Path, statements: tuple[str, ...]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    dst = tmp_path / "mutated.duckdb"
    shutil.copy(src, dst)
    con = duckdb.connect(str(dst))
    try:
        for sql in statements:
            con.execute(sql)
    finally:
        con.close()
    return dst


def _panels(db: Path) -> list[Panel]:
    conn = connect("duckdb", database=db)
    try:
        return beat5_panels(conn)
    finally:
        conn.close()


def _panel(db: Path, pid: str) -> Panel:
    return next(p for p in _panels(db) if p.id == pid)


def _html(db: Path) -> str:
    conn = connect("duckdb", database=db)
    try:
        return export.render(conn)
    finally:
        conn.close()


def _section(page: str, pid: str) -> str:
    end = page.index(f"Evidence: {pid}")
    start = page.rfind("<section", 0, end)
    return page[start : page.index("</section>", end)]


def _mart(db: Path, sql: str) -> list[tuple]:
    conn = connect("duckdb", database=db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _fact(db: Path, fact: str) -> int:
    (value,) = _mart(db, f"select value from determinism_facts where fact = '{fact}'")[
        0
    ]
    return value


# --- Done-when 1: Beat 5 renders both panels ----------------------------------
def test_beat_five_renders_both_panels(synthetic_db):
    page = _html(synthetic_db)
    assert "Beat 5 — How this was built, and where the rigor lives" in page
    for pid in pins.BEAT5_PANELS:
        assert f"Evidence: {pid}" in page
    b51 = _section(page, "B5.1")
    for fragment in pins.BEAT5_FRAGMENTS.values():
        assert fragment in b51, fragment
    # B5.2 is corpus-gated: over the frozen synthetic input it shows the fixture
    # note, not counts — the same "never faked" state Beat 2 shows.
    assert _panel(synthetic_db, "B5.2").fixture
    assert _panel(synthetic_db, "B5.2").series == ()


# --- Done-when 2 / invariant 2: B5.1 facts are counted from the code -----------
def test_b51_model_site_count_equals_import_walk(synthetic_db):
    # The displayed "one model site" equals the walk it is counted from — the
    # same walk tests/test_llm.py's guard reads (the fact cannot drift).
    assert model_call_sites() == ["classify/llm.py"]
    assert _fact(synthetic_db, "model_call_sites") == len(model_call_sites())
    assert _fact(synthetic_db, "model_call_sites") == pins.BEAT5_MODEL_SITES


def test_b51_formula_count_equals_rendered_formulas(synthetic_db):
    # "Defined" equals "displayed": the fact equals len(FORMULAS) AND the number
    # of formula rows the study actually renders in its formulas-kind panels.
    conn = connect("duckdb", database=synthetic_db)
    try:
        rendered = sum(
            len(p.series) for p in beat3_panels(conn) if p.kind == "formulas"
        )
    finally:
        conn.close()
    assert _fact(synthetic_db, "formulas_shown") == len(FORMULAS)
    assert _fact(synthetic_db, "formulas_shown") == rendered


def test_b51_evidence_tag_count_equals_the_tag_set(synthetic_db):
    assert _fact(synthetic_db, "evidence_tags") == len(TAGS) == pins.BEAT5_EVIDENCE_TAGS


def test_b51_facts_constant_over_inputs_and_no_key(synthetic_db, none_db):
    # A repo fact does not move with the corpus or the key (build_study_db is
    # rules-only, i.e. no key): determinism_facts is identical over none and
    # synthetic. It fills in rebuild(), so it is present even over none.
    facts_sql = "select fact, value from determinism_facts order by fact"
    both = {}
    for label, db in (("synthetic", synthetic_db), ("none", none_db)):
        both[label] = _mart(db, facts_sql)
    assert both["synthetic"] == both["none"]
    assert both["none"]  # non-empty: the facts render over none too


# --- Done-when 3 / invariant 4: B5.2 stage counts are direct counts -----------
def test_b52_stage_counts_equal_direct_counts(synthetic_db):
    rows = dict(
        (stage, value)
        for stage, value in _mart(
            synthetic_db, "select stage, value from pipeline_row_counts"
        )
    )
    # single grain: exactly the declared stages, no other row
    assert set(rows) == set(pins.BEAT5_STAGE_COUNTS)
    for stage, value in rows.items():
        (direct,) = _mart(synthetic_db, f"select count(*) from {stage}")[0]
        assert value == direct == pins.BEAT5_STAGE_COUNTS[stage], stage


# --- invariant 3: B5.2 gates the way Beat 2 does ------------------------------
def _b52_state(db: Path) -> tuple[bool, bool]:
    """(has counts, has fixture note) for B5.2 over `db`."""
    p = _panel(db, "B5.2")
    return (p.series != (), bool(p.fixture))


def test_b52_is_corpus_gated(synthetic_db, none_db, tmp_path):
    # synthetic (a fixture input): the fixture note, no counts — Beat 2's state.
    assert _b52_state(synthetic_db) == (False, True)
    # none: no data yet — no counts and no fixture note.
    assert _b52_state(none_db) == (False, False)
    # a captured input renders the counts (run_id mutated to captured, the state
    # a real scrape produces): the counts appear, the fixture note does not.
    counted = _mutated(
        synthetic_db,
        tmp_path / "counted",
        ("update pipeline_row_counts set run_id = 'captured'",),
    )
    assert _b52_state(counted) == (True, False)
    assert ">40<" in _section(_html(counted), "B5.2")  # raw_reviews, as scraped


# --- invariant 5: pipeline_row_counts is stable across a re-classify -----------
# `make idempotency-check` runs rebuild() only (before classify), so it never
# fills this mart; its stability is proven here, not by that target.
def test_pipeline_row_counts_stable_across_reclassify(tmp_path):
    from pipeline import cli
    from pipeline.build import rebuild
    from pipeline.warehouse import database_for

    root = tmp_path / "reclass"
    rebuild("duckdb", "synthetic", root=root)
    db = database_for("synthetic", root)

    def _classify_once() -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cli, "make_model_decider", lambda: None)
            mp.setattr(cli, "read_decisions", lambda *a, **k: {})
            mp.setattr(cli, "write_decisions", lambda *a, **k: None)
            cli._classify_and_print(db, "synthetic")

    counts_sql = "select stage, value, run_id, tag from pipeline_row_counts order by 1"
    _classify_once()
    first = _mart(db, counts_sql)
    _classify_once()
    second = _mart(db, counts_sql)
    assert first == second and first  # stable and non-empty


# --- Done-when 4: no new kind, byte-stable ------------------------------------
def test_beat_five_no_new_kind(synthetic_db):
    assert _panel(synthetic_db, "B5.1").kind == "stat_row"
    assert _panel(synthetic_db, "B5.2").kind == "table"


def test_beat_five_render_is_byte_stable(synthetic_db):
    assert _html(synthetic_db) == _html(synthetic_db)


# --- invariant 1: every Beat 5 number is a tagged mart cell -------------------
_OTHER_SECTIONS = ("B3.1", "B4.2", "B5.2")


def test_every_beat_five_number_is_a_tagged_mart_cell(synthetic_db, tmp_path):
    before = _html(synthetic_db)
    after = _html(
        _mutated(
            synthetic_db,
            tmp_path / "facts",
            (
                "update determinism_facts set value = 4242 "
                "where fact = 'formulas_shown'",
            ),
        )
    )
    assert ">4,242<" in _section(after, "B5.1")  # the mart cell moved the number
    assert _section(after, "B5.1") != _section(before, "B5.1")
    for pid in _OTHER_SECTIONS:
        assert _section(after, pid) == _section(before, pid), pid
    # a Beat 5 point with no tag is refused by the render contract
    with pytest.raises(RenderRefused):
        check_panel(
            Panel(
                "B5.9",
                "B5.9",
                "t",
                "b",
                "Measured",
                "stat_row",
                series=(Series("s", 0, (Point("x", 1.0, "", "", "count"),)),),
            )
        )


def test_beat_five_points_carry_the_marts_tag_not_a_literal(synthetic_db, tmp_path):
    # Flip the mart's tag; the rendered point carries the new tag, so the panel
    # reads its tag from the row, never a literal in the reader.
    flipped = _mutated(
        synthetic_db,
        tmp_path / "tag",
        ("update determinism_facts set tag = 'Documented'",),
    )
    point = _panel(flipped, "B5.1").series[0].points[0]
    assert point.tag == "Documented"


# --- Done-when 5: BACKING flipped, metrics.py gone, allowlist/queries ---------
def test_backing_b5_rows_measured_no_orphan():
    backing = (ROOT / "BACKING.md").read_text(encoding="utf-8")
    b51 = next(ln for ln in backing.splitlines() if ln.startswith("| B5.1 "))
    b52 = next(ln for ln in backing.splitlines() if ln.startswith("| B5.2 "))
    assert "determinism_facts" in b51 and b51.rstrip().endswith("Measured |")
    assert "pipeline_row_counts" in b52 and b52.rstrip().endswith("Measured |")
    for mart in ("determinism_facts", "pipeline_row_counts"):
        assert (ROOT / "sql" / "marts" / f"{mart}.sql").exists()


def test_metrics_module_is_gone_query_relocated():
    assert not (ROOT / "pipeline" / "metrics.py").exists()
    with pytest.raises(ModuleNotFoundError):
        __import__("pipeline.metrics")
    from pipeline.build import REVIEWS_PER_MONTH, reviews_per_month  # relocated

    assert "stg_reviews" in REVIEWS_PER_MONTH and callable(reviews_per_month)


def test_the_allowlist_and_queries_gain_the_beat_five_marts():
    for column in ("fact", "stage"):
        assert column in panels.ALLOWED_COLUMNS
    assert "title" not in panels.ALLOWED_COLUMNS
    assert "body" not in panels.ALLOWED_COLUMNS
    for sql in (panels._Q_DETERMINISM_FACTS, panels._Q_PIPELINE_ROW_COUNTS):
        assert sql in panels.STUDY_QUERIES
    # B5.2 is gated (reads run_id), B5.1 is not — a repo fact is constant.
    assert "pipeline_row_counts" in panels._CORPUS_MARTS
    assert "determinism_facts" not in panels._CORPUS_MARTS
