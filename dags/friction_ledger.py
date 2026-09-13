"""The Friction Ledger's one Airflow DAG (PROJECT_BRIEF.md §4): five `make`
targets in the order the architecture draws them, each a BashOperator run from
the repo root, no logic here — the same five commands run by hand on a laptop.
The input (`ROWS`) is the run's environment, never this file: the
demonstration compose sets `ROWS=synthetic`; a company run would load what it
captured. Triggered by hand (`schedule=None`): the schedule in practice is the
weekly Actions cron (brief §4.4)."""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

REPO = "/opt/friction-ledger"  # the compose mounts the repo here, read-only

with DAG(
    dag_id="friction_ledger",
    schedule=None,
    catchup=False,
    # required by Airflow; inert under schedule=None — the phase's approval
    # date (specs/phase-10a-airflow.md, the Status line), never a clock read
    start_date=datetime(2026, 9, 13),
):
    scrape = BashOperator(
        task_id="scrape", bash_command="make confirm scrape", cwd=REPO
    )
    load_raw = BashOperator(
        task_id="load_raw", bash_command="make rebuild STAGE=load", cwd=REPO
    )
    clean = BashOperator(
        task_id="clean", bash_command="make rebuild STAGE=clean", cwd=REPO
    )
    classify = BashOperator(
        task_id="classify", bash_command="make rebuild STAGE=classify", cwd=REPO
    )
    publish = BashOperator(task_id="publish", bash_command="make publish", cwd=REPO)
    scrape >> load_raw >> clean >> classify >> publish
