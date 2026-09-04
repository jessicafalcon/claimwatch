"""The weekly cron workflow (spec Phase 4, done-when 3, 4, 5). Read the file,
not a live run: `.github/workflows/weekly.yml` triggers on a schedule and
manual dispatch only, holds the scoped write permission, scrapes exactly the
fetchable set, and commits a fixed, brand-free message under data/snapshots/
and nothing else."""

from __future__ import annotations

import yaml

from ingest.sources import BRAND_TOKENS, SOURCES, fetchable_sources
from pipeline.warehouse import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "weekly.yml"
_TEXT = WORKFLOW.read_text(encoding="utf-8")
_WF = yaml.safe_load(_TEXT)


def _on(wf: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1 truthy).
    return wf[True] if True in wf else wf["on"]


def _run_steps() -> list[str]:
    steps = _WF["jobs"]["scrape-and-commit"]["steps"]
    return [s["run"] for s in steps if "run" in s]


def test_workflow_triggers_on_schedule_and_dispatch_only():
    triggers = _on(_WF)
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert "pull_request" not in triggers and "push" not in triggers
    assert triggers["schedule"] and "cron" in triggers["schedule"][0]


def test_workflow_has_scoped_write_permission():
    assert _WF["permissions"] == {"contents": "write"}


def test_workflow_scrapes_exactly_the_fetchable_set():
    # The workflow runs the plain `make confirm scrape`, which fetches every
    # fetchable source and skips the rest — never a SOURCE= naming a source we
    # do not fetch.
    assert any("make confirm scrape" in r for r in _run_steps())
    assert not any("SOURCE=" in r for r in _run_steps())
    fetchable = {s.name for s in fetchable_sources()}
    assert fetchable == {s.name for s in SOURCES if s.fetchable}
    not_fetchable = {s.name for s in SOURCES if not s.fetchable}
    # the App Store feed + listing and both Trustpilot sources are excluded
    assert not (fetchable & not_fetchable)
    assert len(not_fetchable) >= 4


def test_workflow_commits_only_data_snapshots():
    commit = next(r for r in _run_steps() if "git add" in r)
    adds = [
        ln.strip() for ln in commit.splitlines() if ln.strip().startswith("git add")
    ]
    assert adds == ["git add data/snapshots/"]


def test_commit_message_is_fixed_and_brand_free():
    commit = next(r for r in _run_steps() if "git commit" in r)
    assert "data: weekly snapshot" in commit
    assert not any(tok in _TEXT for tok in BRAND_TOKENS)  # the whole file is clean


def test_record_snapshots_runs_after_the_scrape():
    steps = _run_steps()
    scrape = next(i for i, r in enumerate(steps) if "make confirm scrape" in r)
    record = next(i for i, r in enumerate(steps) if "make record-snapshots" in r)
    assert scrape < record
