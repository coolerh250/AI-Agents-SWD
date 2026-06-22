"""Step 52.1 -- production OIDC prerequisites (unconfigured)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "production-oidc-prerequisites.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_meta_unconfigured() -> None:
    m = _d()["meta"]
    assert m["oidcConfigured"] is False
    assert m["oidcDiscoveryPerformed"] is False
    assert m["realIssuer"] is False
    assert m["realClientId"] is False
    assert m["realClientSecret"] is False
    assert m["productionLogin"] is False


def test_provider_all_unconfigured() -> None:
    prov = _d()["oidcPrerequisites"]["provider"]
    for k in ("issuerUrl", "jwksUri", "clientId", "clientSecret", "redirectUris"):
        assert prov[k]["required"] is True
        assert prov[k]["configured"] is False


def test_unknown_user_deny() -> None:
    rm = _d()["oidcPrerequisites"]["roleMapping"]
    assert rm["configured"] is False
    assert rm["unknownUserBehavior"] == "deny"
    assert rm["defaultRole"] == "none"


def test_client_secret_storage_is_secret_store() -> None:
    cs = _d()["oidcPrerequisites"]["provider"]["clientSecret"]
    assert cs["storage"] == "production_secret_store_required"
