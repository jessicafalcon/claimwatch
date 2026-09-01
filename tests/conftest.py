"""Session-wide guard: the make user-variables (SPEC, BASE) and MAKEFLAGS are
scrubbed so the Makefile-invoking tests (tests/test_makefile.py) see a clean
environment. No integration tests exist yet; every test here is offline, needs
no service, no network and no API key."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in ("SPEC", "BASE", "MAKEFLAGS", "MFLAGS"):
        monkeypatch.delenv(var, raising=False)
    yield
