"""Provision the Metabase demonstration from study/metabase/config.yaml over the
HTTP API, idempotently (9g). Developer-run: it reads Metabase credentials from
`.env` and talks to a localhost Metabase (never a paid API, never the public
network); `--dry-run` builds every request body with no network and no
credentials.

Idempotent by upsert-by-name: for each object (the SQLite database connection,
the collection, the questions, the dashboard) the applier lists what exists,
matches by name, and updates it if present or creates it if not — so a second
apply creates no duplicate (the tested invariant). Request bodies are built from
config by pure functions, so `--dry-run` prints exactly what a live apply would
send, byte-stable on a rerun.

The HTTP client is an injected seam (`Client`): the live `UrllibClient` uses
stdlib `urllib` (no dependency, the opendata/fetch.py precedent), and the tests
pass a fake client — the suite opens no socket."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.request import ProxyHandler, Request, build_opener

import yaml

CONFIG = Path(__file__).resolve().parent / "config.yaml"

# The four object kinds the applier provisions, each its API path. Order matters:
# a card needs the database and collection ids, the dashboard needs the cards.
_PATHS = {
    "database": "/api/database",
    "collection": "/api/collection",
    "card": "/api/card",
    "dashboard": "/api/dashboard",
}

# Credential environment variable names — read from .env, never echoed.
_ENV = ("METABASE_URL", "METABASE_USER", "METABASE_PASSWORD")


class MetabaseError(Exception):
    """A one-line refusal on the developer-run applier path — a missing
    credential, or a response that is not the shape the API documents."""


@dataclass(frozen=True)
class Credentials:
    """Metabase login, from `.env`. A missing variable is refused by name, never
    by value (the value is a secret; the name is not)."""

    url: str
    username: str
    password: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Credentials:
        source = os.environ if env is None else env
        missing = [name for name in _ENV if not source.get(name)]
        if missing:
            raise MetabaseError(
                f"missing Metabase credential(s) {missing} — set them in .env "
                "(never in a tracked file or in Actions)"
            )
        return cls(
            source["METABASE_URL"].rstrip("/"),
            source["METABASE_USER"],
            source["METABASE_PASSWORD"],
        )


# --- request bodies, pure functions of config (and resolved ids) -----------------


def database_body(config: dict) -> dict:
    db = config["database"]
    return {
        "name": db["name"],
        "engine": db["engine"],
        "details": {"db": db["file"]},
    }


def collection_body(config: dict) -> dict:
    return {"name": config["collection"]["name"]}


def _sql(question: dict) -> str:
    """Collapse the YAML-folded SQL to a single spaced line, so the body is the
    same whatever the file's wrapping."""
    return " ".join(question["sql"].split())


def card_body(question: dict, database_id: object, collection_id: object) -> dict:
    return {
        "name": question["name"],
        "display": question["display"],
        "collection_id": collection_id,
        "visualization_settings": {},
        "dataset_query": {
            "type": "native",
            "native": {"query": _sql(question)},
            "database": database_id,
        },
    }


def dashboard_body(config: dict, collection_id: object) -> dict:
    return {"name": config["dashboard"]["name"], "collection_id": collection_id}


def dashcards_body(config: dict, card_id_by_name: dict[str, object]) -> dict:
    """The dashboard's cards, one per configured card in a simple vertical stack.
    Keyed by card_id (stable because cards upsert by name), so re-applying PUTs
    the same set — no duplicate dashcard. The exact dashcard shape is confirmed
    against the running version in the build's first hour (spec stack risk)."""
    dashcards = [
        {
            "id": -(i + 1),  # negative id = a new dashcard, per the API
            "card_id": card_id_by_name[name],
            "row": i * 4,
            "col": 0,
            "size_x": 12,
            "size_y": 4,
        }
        for i, name in enumerate(config["dashboard"]["cards"])
    ]
    return {"dashcards": dashcards}


# --- the client seam -------------------------------------------------------------


class Client(Protocol):
    """The HTTP operations the applier needs, so the live client and the test's
    fake client are interchangeable (the suite opens no socket)."""

    def list(self, kind: str) -> list[dict]: ...
    def create(self, kind: str, body: dict) -> dict: ...
    def update(self, kind: str, object_id: object, body: dict) -> dict: ...


def as_list(response: object) -> list[dict]:
    """Normalise a list endpoint: some Metabase versions return a bare list, some
    wrap it as `{"data": [...]}`. Anything else is refused (unshaped input)."""
    if isinstance(response, list):
        return response
    if isinstance(response, dict) and isinstance(response.get("data"), list):
        return response["data"]
    raise MetabaseError(
        f"expected a list or {{'data': [...]}}, got {type(response).__name__}"
    )


class UrllibClient:
    """The live client: authenticate once, then carry the session token in the
    `X-Metabase-Session` header. stdlib `urllib`, proxies disabled, https or a
    localhost http url only. Developer-run."""

    def __init__(self, creds: Credentials):
        self._base = creds.url
        self._opener = build_opener(ProxyHandler({}))
        self._token = self._authenticate(creds)

    def _authenticate(self, creds: Credentials) -> str:
        payload = self._request(
            "POST",
            "/api/session",
            {"username": creds.username, "password": creds.password},
            token=None,
        )
        token = payload.get("id") if isinstance(payload, dict) else None
        if not token:
            raise MetabaseError("authentication returned no session id")
        return str(token)

    def _request(
        self, method: str, path: str, body: dict | None, *, token: str | None = ""
    ) -> object:
        url = f"{self._base}{path}"
        headers = {"Content-Type": "application/json"}
        session = self._token if token == "" else token
        if session:
            headers["X-Metabase-Session"] = session
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers=headers, method=method)
        with self._opener.open(request, timeout=30) as response:
            raw = response.read()
        return json.loads(raw) if raw else {}

    def list(self, kind: str) -> list[dict]:
        return as_list(self._request("GET", _PATHS[kind], None))

    def create(self, kind: str, body: dict) -> dict:
        result = self._request("POST", _PATHS[kind], body)
        return result if isinstance(result, dict) else {}

    def update(self, kind: str, object_id: object, body: dict) -> dict:
        result = self._request("PUT", f"{_PATHS[kind]}/{object_id}", body)
        return result if isinstance(result, dict) else {}


# --- the apply flow --------------------------------------------------------------


def upsert(client: Client, kind: str, name: str, body: dict) -> object:
    """Create the object if no object of `kind` has this name, else update the one
    that does. Returns its id. This is the idempotency mechanism: a second apply
    finds the object and updates it, never creating a duplicate."""
    for existing in client.list(kind):
        if existing.get("name") == name:
            object_id = existing["id"]
            client.update(kind, object_id, body)
            return object_id
    return client.create(kind, body)["id"]


def apply(config: dict, client: Client) -> dict[str, object]:
    """Provision every object idempotently and return the resolved ids. Order:
    database -> collection -> cards -> dashboard -> the dashboard's cards."""
    database_id = upsert(
        client, "database", config["database"]["name"], database_body(config)
    )
    collection_id = upsert(
        client, "collection", config["collection"]["name"], collection_body(config)
    )
    card_id_by_name = {
        q["name"]: upsert(
            client, "card", q["name"], card_body(q, database_id, collection_id)
        )
        for q in config["questions"]
    }
    dashboard_id = upsert(
        client,
        "dashboard",
        config["dashboard"]["name"],
        dashboard_body(config, collection_id),
    )
    client.update("dashboard", dashboard_id, dashcards_body(config, card_id_by_name))
    return {
        "database": database_id,
        "collection": collection_id,
        "cards": card_id_by_name,
        "dashboard": dashboard_id,
    }


# --- dry run (offline, no credentials) -------------------------------------------

# Sentinel ids the dry run shows in place of the live ones it cannot resolve
# without the server — so the printed bodies are deterministic and pinnable.
_DB_ID = "<database_id>"
_COLLECTION_ID = "<collection_id>"


def dry_run_requests(config: dict) -> list[dict]:
    """The requests a fresh apply (nothing exists yet) would send, with sentinel
    ids for what the server assigns. Pure and deterministic — pinned in tests."""
    requests = [
        {"method": "POST", "path": _PATHS["database"], "body": database_body(config)},
        {
            "method": "POST",
            "path": _PATHS["collection"],
            "body": collection_body(config),
        },
    ]
    card_ids = {}
    for question in config["questions"]:
        requests.append(
            {
                "method": "POST",
                "path": _PATHS["card"],
                "body": card_body(question, _DB_ID, _COLLECTION_ID),
            }
        )
        card_ids[question["name"]] = f"<card_id:{question['name']}>"
    requests.append(
        {
            "method": "POST",
            "path": _PATHS["dashboard"],
            "body": dashboard_body(config, _COLLECTION_ID),
        }
    )
    requests.append(
        {
            "method": "PUT",
            "path": f"{_PATHS['dashboard']}/<dashboard_id>",
            "body": dashcards_body(config, card_ids),
        }
    )
    return requests


def dry_run_text(config: dict) -> str:
    """The dry-run requests as sorted, indented JSON — byte-stable on a rerun."""
    return json.dumps(
        dry_run_requests(config), indent=2, sort_keys=True, ensure_ascii=False
    )


def load_config(path: str | Path = CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
