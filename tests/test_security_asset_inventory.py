"""Step 54.1 -- application security asset inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "application-security-asset-inventory.yaml"

REQUIRED = {
    "orchestrator",
    "policy-engine",
    "approval-engine",
    "audit-service",
    "communication-gateway",
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
    "retry-scheduler",
    "admin-console",
    "shared-sdk",
    "kubernetes-helm-gitops",
    "migration-backup-restore-jobs",
}


def _data() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8")) or {}


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _data().get("assets")


def test_required_components_covered() -> None:
    keys = {a["key"] for a in _data()["assets"]}
    assert REQUIRED <= keys


def test_assets_have_security_flags() -> None:
    for a in _data()["assets"]:
        for field in (
            "handlesSecrets",
            "handlesUserInput",
            "handlesAuth",
            "handlesNetwork",
            "handlesPersistence",
            "productionRelevant",
        ):
            assert isinstance(a.get(field), bool), (a["key"], field)
        assert isinstance(a.get("requiredScans"), list)


def test_production_relevant_classified() -> None:
    assets = _data()["assets"]
    assert any(a["productionRelevant"] for a in assets)
    assert any(not a["productionRelevant"] for a in assets)  # scaffolds excluded
