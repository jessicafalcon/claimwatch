"""Session-wide guard: the make user-variables (SPEC, BASE) and MAKEFLAGS are
scrubbed so the Makefile-invoking tests (tests/test_makefile.py) see a clean
environment, and UV_OFFLINE=1 is set so a test that spawns `uv run` (the gate,
`make test`) can never resolve or download — "offline" is enforced, not hoped.
No integration tests exist yet; every test here needs no service, no network
and no API key."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in ("SPEC", "BASE", "MAKEFLAGS", "MFLAGS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("UV_OFFLINE", "1")
    yield
