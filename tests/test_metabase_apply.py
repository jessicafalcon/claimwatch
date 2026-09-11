"""Phase 9g: the Metabase applier — idempotent provisioning, the offline dry-run,
credential refusal. No network (the suite opens no socket): the live client is an
injected seam, so these tests drive `apply` with a fake client that records every
call."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import URLError

import pytest

from study.metabase.apply import (
    Client,
    Credentials,
    MetabaseError,
    UrllibClient,
    _base_url_ok,
    _require_id,
    apply,
    as_list,
    card_body,
    collection_body,
    dashboard_body,
    dashcards_body,
    database_body,
    dry_run_requests,
    dry_run_text,
    load_config,
    upsert,
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


def test_upsert_creates_when_absent_then_updates_when_present():
    """upsert is the idempotency mechanism: create when no object of the kind has
    the name, update the one that does — never a second create."""
    client = FakeClient()
    first_id = upsert(client, "card", "Q", {"name": "Q"})
    assert len(client.creates) == 1
    second_id = upsert(client, "card", "Q", {"name": "Q", "display": "table"})
    assert second_id == first_id  # found by name, not created again
    assert len(client.creates) == 1
    assert client.updates[-1][0] == "card"


def test_request_bodies_have_the_documented_shapes():
    """The pure body-builders emit the shapes the Metabase API documents."""
    db = database_body(_CONFIG)
    assert db["engine"] == "sqlite"
    assert db["details"]["db"].endswith(".sqlite")
    assert collection_body(_CONFIG)["name"] == _CONFIG["collection"]["name"]
    drill_question = _CONFIG["questions"][1]
    card = card_body(drill_question, 7, 3)
    assert card["dataset_query"]["type"] == "native"
    assert card["dataset_query"]["database"] == 7
    assert card["collection_id"] == 3
    assert "review_drill" in card["dataset_query"]["native"]["query"]
    assert dashboard_body(_CONFIG, 3)["collection_id"] == 3
    named = dict.fromkeys(_CONFIG["dashboard"]["cards"], 1)
    dashcards = dashcards_body(_CONFIG, named)["dashcards"]
    assert len(dashcards) == len(_CONFIG["dashboard"]["cards"])
    assert all(dc["size_x"] > 0 for dc in dashcards)


def test_as_list_accepts_a_list_or_data_wrapper_and_refuses_other_shapes():
    """A list endpoint returns a bare list on some versions, {'data': [...]} on
    others; anything else is unshaped input and is refused."""
    assert as_list([{"id": 1}]) == [{"id": 1}]
    assert as_list({"data": [{"id": 2}]}) == [{"id": 2}]
    with pytest.raises(MetabaseError):
        as_list({"unexpected": True})


def test_client_seam_is_defined_by_both_the_live_and_fake_clients():
    """The Client protocol names list/create/update; UrllibClient (the live one)
    and FakeClient (the test one) both provide them, so they are interchangeable."""
    for method in ("list", "create", "update"):
        assert hasattr(Client, method)
        assert callable(getattr(UrllibClient, method))
        assert callable(getattr(FakeClient, method))


def test_require_id_refuses_a_reply_that_is_not_an_object_with_an_id():
    """The Metabase reply is a foreign input: its id is shaped, not assumed — a
    reply missing id (or not a dict) is a one-line MetabaseError, not a KeyError."""
    assert _require_id({"id": 7, "name": "x"}, "card") == 7
    for bad in ({}, {"name": "x"}, [], "nope", None):
        with pytest.raises(MetabaseError, match="card"):
            _require_id(bad, "card")


def test_upsert_refuses_a_created_object_with_no_id():
    """upsert extracts the id through the shape guard, so a create returning no id
    refuses by name rather than raising KeyError deeper in."""

    class NoIdClient:
        def list(self, kind):
            return []

        def create(self, kind, body):
            return {"name": body.get("name")}  # no id

        def update(self, kind, object_id, body):
            return {}

    with pytest.raises(MetabaseError):
        upsert(NoIdClient(), "card", "Q", {"name": "Q"})


def test_base_url_is_https_or_local_http_only():
    """METABASE_URL reaches a declared shape: https anywhere, or http only to the
    local machine — the session token never travels to an arbitrary http host."""
    assert _base_url_ok("https://metabase.example.com")
    assert _base_url_ok("http://localhost:3000")
    assert _base_url_ok("http://127.0.0.1:3000")
    assert not _base_url_ok("http://metabase.example.com")
    assert not _base_url_ok("ftp://localhost")
    with pytest.raises(MetabaseError, match="METABASE_URL"):
        Credentials.from_env(
            {
                "METABASE_URL": "http://reporting.example.com",
                "METABASE_USER": "admin",
                "METABASE_PASSWORD": "secret",
            }
        )


def test_urllib_client_maps_a_network_error_to_a_one_line_refusal():
    """A network failure at the boundary is a one-line MetabaseError naming the
    host and cause — never a traceback, never the token or request body
    (traceback-at-boundary). The opener is injected, so no socket opens."""

    class FailingOpener:
        def open(self, request, timeout=None):
            raise URLError("connection refused")

    creds = Credentials.from_env(
        {
            "METABASE_URL": "http://localhost:3000",
            "METABASE_USER": "admin",
            "METABASE_PASSWORD": "secret",
        }
    )
    with pytest.raises(MetabaseError) as caught:
        UrllibClient(creds, opener=FailingOpener())  # authenticates on init
    message = str(caught.value)
    assert "localhost" in message
    assert "secret" not in message and "admin" not in message


def test_export_command_routes_rows_to_the_matching_database(monkeypatch):
    """`export --rows <input>` reads the database for that input, so the
    synthetic-screenshot path (ROWS=synthetic) exports the synthetic build, not
    the captured corpus (round-1 #1)."""
    import study.metabase.__main__ as entry
    from pipeline.warehouse import database_for

    seen = {}

    def fake_build(duck_db=None):
        seen["db"] = duck_db
        return Path("x")

    monkeypatch.setattr(entry, "build_sqlite", fake_build)
    assert entry.main(["export", "--rows", "synthetic"]) == 0
    assert seen["db"] == database_for("synthetic")
    assert seen["db"] != database_for("captured")
