"""Step 52.2 -- disabled production OIDC config: fail-closed, not ready."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "production-oidc-disabled-config.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_auth_disabled_and_fail_closed() -> None:
    a = _d()["auth"]
    assert a["enabled"] is False
    assert a["productionEnabled"] is False
    assert a["failClosed"] is True
    assert a["testLocalFallbackAllowed"] is False


def test_status_not_ready() -> None:
    s = _d()["status"]
    assert s["configured"] is False
    assert s["ready"] is False
    assert s["reason"] == "required_fields_missing"


def test_required_fields_listed() -> None:
    req = _d()["requiredBeforeEnablement"]
    for field in (
        "issuer_url",
        "jwks_uri",
        "client_id_secret_ref",
        "client_secret_secret_ref",
        "role_mapping",
        "production_session_secret_store",
        "operator_approval",
    ):
        assert field in req


def test_provider_ref_points_to_placeholder() -> None:
    assert _d()["providerRef"] == "production-oidc-placeholder"
