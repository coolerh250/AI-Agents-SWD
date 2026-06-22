"""Step 52.1 -- identity trust boundary model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-boundary-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_frontend_cannot_authorize() -> None:
    b = _d()["boundaries"]
    assert b["adminConsoleFrontend"]["mayAuthorizeActions"] is False
    assert b["browser"]["canStoreTokens"] is False


def test_backend_authoritative() -> None:
    b = _d()["boundaries"]
    assert b["backendSession"]["validatesIdentity"] is True
    assert b["policyEngine"]["authorizesAction"] is True


def test_future_boundaries_disabled() -> None:
    b = _d()["boundaries"]
    for k in ("externalIdP", "kubernetesCluster", "argocd"):
        assert b[k]["enabled"] is False
        assert b[k]["trusted"] == "future"


def test_invariants() -> None:
    inv = _d()["invariants"]
    assert inv["frontendCannotSelfAuthorize"] is True
    assert inv["humanAcceptanceIsNotDeployment"] is True
    assert inv["platformAdminIsNotInfrastructureAdmin"] is True
    assert inv["csrfIsNotAuthorization"] is True
