"""The six frozen sets — fixtures/synthetic/ and fixtures/anchors/ (Phase 1,
done-when 5), fixtures/app-store/ (Phase 2, done-when 6), fixtures/listings/
and fixtures/opinion-assurances/ (Phase 3a, done-when 5), fixtures/trustpilot/
(Phase 3c, done-when 5) — match their MANIFEST.sha256. A byte flip, a missing
file or an extra file fails."""

from __future__ import annotations

import hashlib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _check(name: str) -> None:
    d = FIXTURES / name
    listed: dict[str, str] = {}
    for line in (d / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split("  ", 1)  # sha256sum format
        listed[filename] = digest
    present = {p.name for p in d.glob("*") if p.name != "MANIFEST.sha256"}
    assert set(listed) == present, (name, set(listed), present)
    for filename, digest in listed.items():
        actual = hashlib.sha256((d / filename).read_bytes()).hexdigest()
        assert actual == digest, (name, filename)


def test_manifests_match():
    _check("synthetic")
    _check("anchors")
    _check("app-store")
    _check("listings")
    _check("opinion-assurances")
    _check("trustpilot")
