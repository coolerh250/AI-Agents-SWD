"""Step 52.1 -- human acceptance identity boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "human-acceptance-identity-boundary.yaml"


def _h() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["humanAcceptance"]


def test_roles() -> None:
    h = _h()
    assert set(h["canAccept"]) == {"operator", "platform_admin"}
    assert "reviewer" in h["canRequestChanges"]


def test_acceptance_is_not_deployment() -> None:
    h = _h()
    assert h["isProductionApproval"] is False
    for forbidden in ("deploy", "merge_pr", "sync_argocd", "mark_production_readiness"):
        assert forbidden in h["acceptanceDoesNot"]


def test_identity_recorded() -> None:
    h = _h()
    assert "identity_key" in h["identityRecorded"]
    assert h["requiresReason"] is True
    assert h["requiresConfirmation"] is True
