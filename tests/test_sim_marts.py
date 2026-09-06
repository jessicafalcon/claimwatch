"""Phase 8b — the two simulator marts, filled inside rebuild() from
models/guardrail_sim.py. Offline, no key: they compute over the tracked fit, so
they fill on every ROWS input, are byte-stable across runs, and carry the Modeled
tag. The hold rule's outcomes are a closed set and the summary the study quotes
is recomputed from the mart rows."""

from __future__ import annotations

from models import guardrail_sim as gs
from pipeline.build import rebuild
from pipeline.cli import main
from pipeline.warehouse import connect, database_for
from tests import pins

_SIM_MARTS = ("guardrail_sim", "sla_threshold")


def _built(tmp_path, rows: str = "synthetic", run_id: str = "test"):
    rebuild("duckdb", rows, root=tmp_path, run_id=run_id)
    return connect("duckdb", database=database_for(rows, tmp_path))


def test_two_marts_filled_on_every_input(tmp_path):
    """none, synthetic and samples each leave the two marts with their constant
    counts — the marts compute over the fit, not the input."""
    for rows in ("none", "synthetic", "samples"):
        conn = _built(tmp_path / rows, rows)
        try:
            counts = {
                m: conn.execute(f"select count(*) from {m}").fetchone()[0]
                for m in _SIM_MARTS
            }
        finally:
            conn.close()
        assert counts == {
            "guardrail_sim": pins.GUARDRAIL_SIM_ROWS,
            "sla_threshold": pins.SLA_THRESHOLD_ROWS,
        }, rows


def test_two_rebuilds_identical_sim_mart_rows(tmp_path):
    """Two rebuilds with different run_ids into the same file give byte-identical
    simulator-mart rows (run_id aside) — run_id is provenance, in no key or sort."""
    sim_cols = (
        "scenario, curves_scenario, claim_rank, quantile, amount_eur, loop_days, "
        "hold_days, outcome, tag"
    )
    sla_cols = "timer_days, timer_amount_eur, share_under, is_default, tag"

    def snapshot(run_id: str):
        conn = _built(tmp_path, run_id=run_id)
        try:
            sim = conn.execute(
                f"select {sim_cols} from guardrail_sim order by scenario, claim_rank"
            ).fetchall()
            sla = conn.execute(
                f"select {sla_cols} from sla_threshold order by timer_days"
            ).fetchall()
            run_ids = {
                r[0]
                for r in conn.execute("select run_id from guardrail_sim").fetchall()
            }
        finally:
            conn.close()
        return (sim, sla), run_ids

    first, ids_1 = snapshot("run-1")
    second, ids_2 = snapshot("run-2")
    assert first == second
    assert ids_1 == {"run-1"} and ids_2 == {"run-2"}


def test_rows_carry_run_id_and_modeled_tag(tmp_path):
    """Every simulator-mart row carries the rebuild's run_id and the Modeled tag."""
    conn = _built(tmp_path, run_id="rid")
    try:
        for mart in _SIM_MARTS:
            marks = conn.execute(f"select distinct run_id, tag from {mart}").fetchall()
            assert marks == [("rid", "Modeled")], mart
    finally:
        conn.close()


def test_outcomes_are_the_closed_set_and_hold_is_loop_or_timer(tmp_path):
    """Every outcome is one of the three names and every hold is the loop or the
    default timer — the closed set the study relies on."""
    conn = _built(tmp_path)
    try:
        outcomes = {
            r[0]
            for r in conn.execute(
                "select distinct outcome from guardrail_sim"
            ).fetchall()
        }
        bad_hold = conn.execute(
            "select count(*) from guardrail_sim where hold_days not in (loop_days, ?)",
            [pins.TIMER_DEFAULT_DAY],
        ).fetchone()[0]
    finally:
        conn.close()
    assert outcomes <= set(gs.OUTCOMES)
    assert bad_hold == 0


def test_summary_recomputed_from_the_mart_rows(tmp_path):
    """The mean hold and the released share per scenario, recomputed from the mart
    with plain arithmetic, equal the pins and summarize()'s own output."""
    conn = _built(tmp_path)
    try:
        rows = [
            {"scenario": s, "hold_days": h, "outcome": o}
            for s, h, o in conn.execute(
                "select scenario, hold_days, outcome from guardrail_sim"
            ).fetchall()
        ]
    finally:
        conn.close()
    for sim in gs.SIM_SCENARIOS:
        srows = [r for r in rows if r["scenario"] == sim.name]
        mean = round(sum(r["hold_days"] for r in srows) / len(srows), 2)
        released = round(
            sum(1 for r in srows if r["outcome"] == "timer_released") / len(srows), 6
        )
        assert mean == pins.SIM_SUMMARY[sim.name]["mean_hold_days"], sim.name
        assert released == pins.SIM_SUMMARY[sim.name]["timer_released_share"], sim.name
    assert gs.summarize(rows) == pins.SIM_SUMMARY


def test_default_day_share_equals_timer_released_share(tmp_path):
    """The share_under at the default day and hold_timer's share of timer-released
    claims are the same count by construction (decision 6)."""
    conn = _built(tmp_path)
    try:
        default_share = conn.execute(
            "select share_under from sla_threshold where is_default"
        ).fetchone()[0]
        released = conn.execute(
            "select count(*) from guardrail_sim where scenario = 'hold_timer' "
            "and outcome = 'timer_released'"
        ).fetchone()[0]
        n = conn.execute(
            "select count(*) from guardrail_sim where scenario = 'hold_timer'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert round(released / n, 6) == default_share == pins.SLA_DEFAULT_SHARE


def test_make_simulate_is_byte_identical_on_rerun(capsys):
    """`make simulate` prints identical text on a rerun and writes nothing — no
    clock, no key."""
    assert main(["simulate"]) == 0
    first = capsys.readouterr().out
    assert main(["simulate"]) == 0
    second = capsys.readouterr().out
    assert first == second and first.strip()
