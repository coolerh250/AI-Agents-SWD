"""Step 53 -- secret lifecycle model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-lifecycle-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_stages_present() -> None:
    stages = _d()["lifecycle"]["stages"]
    for s in (
        "request",
        "approval",
        "provisioning",
        "rotation",
        "emergency_rotation",
        "revocation",
        "audit",
        "decommission",
    ):
        assert s in stages


def test_production_approval_required() -> None:
    assert _d()["lifecycle"]["productionApprovalRequired"] is True


def test_value_never_traverses_repo_audit_console_logs_fixtures() -> None:
    vh = _d()["valueHandling"]
    assert vh["valueViaRepo"] is False
    assert vh["valueInAudit"] is False
    assert vh["valueInAdminConsole"] is False
    assert vh["valueInLogs"] is False
    assert vh["valueInTestFixtures"] is False
    assert vh["rotationRecordStoresMetadataOnly"] is True
