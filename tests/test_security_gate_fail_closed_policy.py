"""Step 54.1 -- security gate fail-closed policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "security-gate-fail-closed-policy.yaml"


def _g() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["gate"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _g()


def test_fail_closed_and_missing_evidence_not_ready() -> None:
    g = _g()
    assert g["failClosed"] is True
    for v in g["missingEvidenceBehavior"].values():
        assert v == "not_ready"


def test_findings_fail() -> None:
    fb = _g()["findingBehavior"]
    assert fb["confirmedSecretLeak"] == "fail"
    assert fb["criticalFinding"] == "fail"


def test_production_gate_disabled_no_mutation() -> None:
    g = _g()
    assert g["productionGateEnabled"] is False
    assert g["releaseGateMutationEnabled"] is False
    assert g["blocksNonProductionVerification"] is False
