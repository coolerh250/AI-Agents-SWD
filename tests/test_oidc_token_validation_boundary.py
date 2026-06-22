"""Step 52.2 -- OIDC token validation boundary: inactive, alg none rejected."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-token-validation-boundary.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_validation_inactive() -> None:
    tv = _d()["tokenValidation"]
    assert tv["enabled"] is False
    assert tv["realTokenValidationPerformed"] is False
    assert _d()["status"] == "disabled_until_provider_configured"


def test_requirements() -> None:
    r = _d()["requirements"]
    for key in (
        "issuerMustMatch",
        "audienceMustMatchClientId",
        "expRequired",
        "iatRequired",
        "nonceRequired",
        "signatureRequired",
        "keyIdRequired",
        "jwksKeyRotationRequired",
    ):
        assert r[key] is True


def test_algorithms_reject_none_and_hs256() -> None:
    a = _d()["algorithms"]
    assert a["allowed"] == ["RS256"]
    assert "none" in a["rejected"]
    assert "HS256" in a["rejected"]


def test_raw_token_not_audited_or_persisted() -> None:
    th = _d()["tokenHandling"]
    assert th["rawTokenAudited"] is False
    assert th["rawTokenPersisted"] is False
