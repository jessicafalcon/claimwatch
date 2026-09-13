"""The one Airflow DAG and its container (spec Phase 10a, invariants 1, 5, 6).
Airflow is never imported here — Docker only — so the DAG file is read with
`ast`: five BashOperator tasks in the brief's order, each one bare `make`
command of a declared target, no logic, one screen; the page's task tuple
equals the file's; the compose mounts the repo read-only, owns `data/`,
carries no env_file and binds the UI to the loopback address; the
demonstration doc and its captioned screenshot exist. Offline."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from review_common import make_targets

from pipeline.build import _CODE_PACKAGES
from pipeline.cli import STAGES
from pipeline.warehouse import ROOT
from study.text import DAG_TASKS
from tests import pins
from tests.repo_text import repo_text

DAGS = ROOT / "dags"
DAG_FILE = DAGS / "friction_ledger.py"
COMPOSE = DAGS / "docker-compose.yml"
DOCKERFILE = DAGS / "Dockerfile"
MOUNT = "/opt/friction-ledger"
# The DAG's five commands, by task id: one bare `make` invocation each.
COMMANDS = {
    "scrape": "make confirm scrape",
    "load_raw": "make rebuild STAGE=load",
    "clean": "make rebuild STAGE=clean",
    "classify": "make rebuild STAGE=classify",
    "publish": "make publish",
}
LOGIC = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
    ast.If,
    ast.IfExp,
    ast.For,
    ast.While,
    ast.Try,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
)
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_CAPTION = "synthetic fixture data — not a study finding"
# Amendment A1: the tracked top-level paths the five tasks read, each a
# read-only bind — the whole mount, so nothing gitignored can be inside it.
PROJECT_FILES = ("Makefile", "pyproject.toml", "uv.lock", ".python-version")
SOURCE_PACKAGES = ("pipeline", "ingest", "classify", "models", "opendata", "study")
DATA_PACKAGES = ("sql", "fixtures", "dags")
DATA_SUBTREES = ("snapshots", "damir", "ameli")
_ROOT_READ = re.compile(r'\bROOT / "([^"/]+)"')


def _tree() -> ast.Module:
    return ast.parse(repo_text(DAG_FILE))


def _operators(tree: ast.Module) -> list[dict[str, ast.expr]]:
    """Every `BashOperator(...)` call's keywords, in source order."""
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BashOperator"
    ]
    return [{kw.arg: kw.value for kw in call.keywords} for call in calls]


def _chain(tree: ast.Module) -> list[str]:
    """The task names of the one `a >> b >> ...` statement, left to right."""
    exprs = [
        node.value
        for node in tree.body[-1].body  # the `with DAG(...)` block
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.BinOp)
    ]
    assert len(exprs) == 1, "one chain statement"
    names: list[str] = []
    node: ast.expr = exprs[0]
    while isinstance(node, ast.BinOp):
        assert isinstance(node.op, ast.RShift)
        assert isinstance(node.right, ast.Name)
        names.insert(0, node.right.id)
        node = node.left
    assert isinstance(node, ast.Name)
    names.insert(0, node.id)
    return names


def test_the_dag_is_five_make_tasks_in_the_briefs_order_with_no_logic():
    """Invariant 1: five BashOperators, the task ids in the brief's order, one
    linear chain, no function/branch/loop/comprehension, Airflow and the stdlib
    the only imports, one screen."""
    tree = _tree()
    assert not [n for n in ast.walk(tree) if isinstance(n, LOGIC)]
    roots = {
        (n.module or "").split(".")[0] if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in n.names
    }
    assert roots <= {"airflow", "datetime"}, roots
    ops = _operators(tree)
    assert len(ops) == pins.DAG_TASK_COUNT
    ids = tuple(op["task_id"].value for op in ops)
    assert ids == DAG_TASKS
    assert _chain(tree) == list(DAG_TASKS)
    dag = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "DAG"
    )
    kw = {k.arg: k.value for k in dag.keywords}
    assert kw["dag_id"].value == "friction_ledger"
    assert kw["schedule"].value is None and kw["catchup"].value is False
    assert len(repo_text(DAG_FILE).splitlines()) <= pins.DAG_LINE_CAP


def test_every_dag_task_runs_one_declared_make_target_with_no_rows_argument():
    """Invariant 1: each command is one bare `make` invocation of goals `make
    help` lists, from the mounted repo root, with STAGE its only variable (in
    the CLI's closed set) and never a ROWS= — the input is the environment."""
    targets, err = make_targets(ROOT)
    assert err is None, err
    for op in _operators(_tree()):
        task = op["task_id"].value
        command = op["bash_command"].value
        assert command == COMMANDS[task]
        assert isinstance(op["cwd"], ast.Name) and op["cwd"].id == "REPO"
        words = command.split()
        assert words[0] == "make" and ";" not in command and "&&" not in command
        for word in words[1:]:
            if "=" in word:
                var, value = word.split("=", 1)
                assert var == "STAGE" and value in STAGES and value != "all", word
            else:
                assert word in targets, word
        assert "ROWS=" not in command
    repo = next(
        n
        for n in _tree().body
        if isinstance(n, ast.Assign) and n.targets[0].id == "REPO"  # type: ignore[attr-defined]
    )
    assert repo.value.value == MOUNT  # type: ignore[attr-defined]


def test_the_pages_task_tuple_equals_the_dags_task_ids():
    """Invariant 6: the B5.2 text diagram is built from `study.text.DAG_TASKS`,
    pinned here to the file's ids so the page cannot name a step the DAG does
    not run."""
    ids = tuple(op["task_id"].value for op in _operators(_tree()))
    assert ids == DAG_TASKS == tuple(COMMANDS)


def test_the_compose_mounts_the_repo_read_only_isolates_data_carries_no_env_file_and_binds_the_ui_locally():  # noqa: E501 -- the invariant it pins, named whole
    """Invariant 5, by the mounts: the repo is a read-only bind at the DAG's
    root, `data/` is a named volume (never the host's data/), the three tracked
    numbers-only subtrees are read-only binds inside it, the input is
    ROWS=synthetic from the environment, no env_file, the UI on 127.0.0.1, and
    uv's environment and cache are outside the mount."""
    doc = yaml.safe_load(repo_text(COMPOSE))
    assert list(doc["services"]) == ["airflow"]
    svc = doc["services"]["airflow"]
    assert "env_file" not in svc and svc["command"] == "standalone"
    assert svc["ports"] == ["127.0.0.1:8080:8080"]
    volumes = svc["volumes"]
    assert f"friction-data:{MOUNT}/data" in volumes
    assert not any(v.startswith(("..:", ".:")) for v in volumes)  # no whole tree (A1)
    for sub in ("snapshots", "damir", "ameli"):
        assert f"../data/{sub}:{MOUNT}/data/{sub}:ro" in volumes
    binds = [v for v in volumes if v.startswith("../")]
    assert all(v.endswith(":ro") for v in binds), binds
    assert set(doc["volumes"]) == {"friction-data"}
    env = svc["environment"]
    assert env["ROWS"] == "synthetic"
    assert env["AIRFLOW__CORE__DAGS_FOLDER"] == f"{MOUNT}/dags"
    assert str(env["UV_LOCKED"]) == "1" and str(env["PYTHONDONTWRITEBYTECODE"]) == "1"
    for var in ("UV_PROJECT_ENVIRONMENT", "UV_CACHE_DIR"):
        assert not env[var].startswith(MOUNT), var
    assert "ANTHROPIC_API_KEY" not in env and not any("KEY" in k for k in env)


def test_the_compose_mounts_only_tracked_paths_the_tasks_read():
    """Amendment A1 (invariant 5, exact): every bind source is one tracked
    top-level entry of HEAD (or one of the three tracked data/ subtrees) —
    never `..`, `.claude`, `.github` or a gitignored name — and the mounted
    set covers every `ROOT / "<top>"` the source packages read, every package
    `model_call_sites` scans, the packages themselves and the project files,
    so a new read path outside the mounts names itself here."""
    doc = yaml.safe_load(repo_text(COMPOSE))
    binds = [v for v in doc["services"]["airflow"]["volumes"] if v.startswith("../")]
    sources = [v.split(":", 1)[0][3:] for v in binds]
    tracked = set(
        subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    subtrees = {f"data/{sub}" for sub in DATA_SUBTREES}
    for source in sources:
        assert source in tracked or source in subtrees, source
    mounted = {s for s in sources if "/" not in s}
    assert mounted.isdisjoint({"..", ".", ".claude", ".github", "tests", "scripts"})
    assert set(sources) - mounted == subtrees
    # what the tasks read, derived from the source: every repo-root path a
    # package opens, the packages the facts writer scans, the project files
    reads: set[str] = set()
    for package in SOURCE_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            reads |= set(_ROOT_READ.findall(repo_text(path)))
    needed = (
        (reads - {"data"})
        | set(_CODE_PACKAGES)
        | set(SOURCE_PACKAGES)
        | set(DATA_PACKAGES)
        | set(PROJECT_FILES)
    )
    assert needed <= mounted, sorted(needed - mounted)
    assert mounted <= needed, sorted(mounted - needed)  # nothing mounted idly


def test_the_dockerfile_pins_the_python312_image_and_returns_to_the_airflow_user():
    """The image is the official one on the project's Python (3.12; the image's
    default is 3.13), `make` lands as root, `uv` as airflow at the project's
    pinned version, and the file ends as the airflow user."""
    text = repo_text(DOCKERFILE)
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert lines[0] == "FROM apache/airflow:3.3.1-python3.12"
    users = [ln for ln in lines if ln.startswith("USER ")]
    assert users == ["USER root", "USER airflow"]
    assert "apt-get install -y --no-install-recommends make" in text
    assert '"uv==0.12.5"' in text  # keep in lockstep with ci.yml's setup-uv


def test_demonstration_doc_and_synthetic_screenshot_exist_and_links_resolve():
    """Invariant 5 (the record): the walk is committed, captions the run as
    synthetic fixture data, every relative link resolves, and EVERY committed
    screenshot carries the caption in the doc's alt text and in the PNG's own
    text channel (the suite's one reader), so it says so wherever it travels.
    The screenshot is the developer's capture over the compose file's
    ROWS=synthetic; until it lands this test is red by design."""
    doc = DAGS / "DEMONSTRATION.md"
    text = repo_text(doc)
    assert _CAPTION in text
    shots = DAGS / "screenshots"
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://")):
            continue
        assert (doc.parent / target.split("#", 1)[0]).exists(), target
    linked = {Path(t).name: alt for alt, t in _IMAGE.findall(text)}
    committed = sorted(p.name for p in shots.glob("*.png"))
    assert committed and committed == sorted(linked), (committed, sorted(linked))
    for name in committed:
        assert _CAPTION in linked[name], name
        assert _CAPTION in repo_text(shots / name), name
