"""Step 54.4 -- security evidence package generator."""

from __future__ import annotations

import json

from scripts.generate_security_evidence_package import build_evidence_package

SECRET_SHAPES = ("ghp_", "AKIA", "BEGIN RSA PRIVATE KEY", "-----BEGIN")
REQUIRED = {
    "sast",
    "dependencyScan",
    "secretScan",
    "sbom",
    "imagePolicy",
    "dockerfileSecurity",
    "threatModel",
    "releaseRisk",
    "audit",
    "qa",
}


def test_package_not_production_ready() -> None:
    pkg = build_evidence_package()
    assert pkg["productionReady"] is False
    assert pkg["schemaVersion"] == "1"


def test_all_evidence_sections_present() -> None:
    pkg = build_evidence_package()
    assert REQUIRED <= set(pkg["evidence"])


def test_absent_evidence_not_marked_clean() -> None:
    pkg = build_evidence_package()
    for key, entry in pkg["evidence"].items():
        status = str(entry.get("status", "")).lower()
        assert status in (
            "present",
            "not_run",
            "missing_evidence",
            "tool_unavailable",
        ), f"{key}: dishonest status {status!r}"


def test_no_secret_or_chain_of_thought() -> None:
    blob = json.dumps(build_evidence_package())
    for shape in SECRET_SHAPES:
        assert shape not in blob
    assert "chain_of_thought" not in blob
    assert "raw_finding" not in blob
