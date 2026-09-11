"""Phase 9g: the Metabase applier — idempotent provisioning, the offline dry-run,
credential refusal. No network (the suite opens no socket): the live client is an
injected seam, so these tests drive `apply` with a fake client that records every
call."""

from __future__ import annotations

import hashlib

import pytest

from study.metabase.apply import (
    Credentials,
    MetabaseError,
    apply,
    dry_run_requests,
    dry_run_text,
    load_config,
)
from tests import pins

_CONFIG = load_config()


class FakeClient:
    """A stand-in Metabase: it lists what it holds, and records every create and
    update, so a test can prove the applier never creates a duplicate."""

    def __init__(self, preload: dict[str, list[dict]] | None = None):
        self.state: dict[str, list[dict]] = {
            k: list(v) for k, v in (preload or {}).items()
        }
        self.creates: list[tuple[str, dict]] = []
        self.updates: list[tuple[str, object, dict]] = []
        self._next_id = 1000

    def list(self, kind: str) -> list[dict]:
        return self.state.get(kind, [])

    def create(self, kind: str, body: dict) -> dict:
        self.creates.append((kind, body))
        obj = {"id": self._next_id, **body}
        self._next_id += 1
        self.state.setdefault(kind, []).append(obj)
        return obj

    def update(self, kind: str, object_id: object, body: dict) -> dict:
        self.updates.append((kind, object_id, body))
        return {"id": object_id, **body}


def test_apply_twice_over_existing_state_issues_no_create():
    """Invariant: applying the same config twice creates no duplicate — the first
    apply creates the six objects, the second finds them by name and only updates."""
    client = FakeClient()  # nothing exists yet
    apply(_CONFIG, client)
    after_first = len(client.creates)
    # database, collection, three questions, dashboard
    assert after_first == 3 + len(_CONFIG["questions"])
    assert after_first == 6
    apply(_CONFIG, client)  # everything now exists — a re-apply
    assert len(client.creates) == after_first  # not one new object
    # the second apply reached every object as an update, never a create
    kinds_updated = {k for k, _, _ in client.updates}
    assert kinds_updated == {"database", "collection", "card", "dashboard"}


def test_dry_run_builds_pinned_request_bodies_without_network():
    """The dry-run is byte-stable and pinned; it needs no network and no
    credentials (this suite blocks sockets, so running at all proves it)."""
    text = dry_run_text(_CONFIG)
    assert dry_run_text(_CONFIG) == text  # deterministic on a rerun
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest == pins.METABASE_DRY_RUN_SHA256
    requests = dry_run_requests(_CONFIG)
    assert len(requests) == pins.METABASE_DRY_RUN_REQUESTS
    paths = [r["path"] for r in requests]
    assert paths.count("/api/card") == len(_CONFIG["questions"])
    for path in ("/api/database", "/api/collection", "/api/dashboard"):
        assert path in paths
    # the drill question reads review_drill; no credential is anywhere in the text
    queries = [
        r["body"].get("dataset_query", {}).get("native", {}).get("query", "")
        for r in requests
    ]
    assert any("review_drill" in q for q in queries)
    for secret in ("METABASE_URL", "METABASE_USER", "METABASE_PASSWORD", "password"):
        assert secret not in text


def test_dry_run_is_identical_with_key_unset(monkeypatch: pytest.MonkeyPatch):
    """The applier does not depend on the Anthropic key: the dry-run bytes are the
    same whether ANTHROPIC_API_KEY is set or unset (the no-key run's applier half)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-value")
    with_key = dry_run_text(_CONFIG)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    without_key = dry_run_text(_CONFIG)
    assert with_key == without_key


def test_apply_refuses_missing_credentials_by_name():
    """A missing credential is refused by the variable's name, never by any value
    — the value is the secret, the name is not (log hygiene)."""
    with pytest.raises(MetabaseError) as caught:
        Credentials.from_env({})
    assert "METABASE_URL" in str(caught.value)
    # a partial environment names the one that is missing, and leaks no value
    with pytest.raises(MetabaseError) as caught2:
        Credentials.from_env(
            {"METABASE_URL": "http://localhost:3000", "METABASE_USER": "admin"}
        )
    message = str(caught2.value)
    assert "METABASE_PASSWORD" in message
    assert "admin" not in message and "localhost" not in message


def test_credentials_from_a_full_environment_strips_trailing_slash():
    """A complete environment yields credentials; the URL's trailing slash is
    dropped so path joins do not double it."""
    creds = Credentials.from_env(
        {
            "METABASE_URL": "http://localhost:3000/",
            "METABASE_USER": "admin@example.com",
            "METABASE_PASSWORD": "secret",
        }
    )
    assert creds.url == "http://localhost:3000"
    assert creds.username == "admin@example.com"
