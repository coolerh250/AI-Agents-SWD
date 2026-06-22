"""Step 53 -- secret classification."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-classification.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_classes_present() -> None:
    classes = _d()["classes"]
    for c in ("critical", "high", "medium", "public-config", "placeholder"):
        assert c in classes


def test_critical_secrets_store_only() -> None:
    crit = _d()["classes"]["critical"]
    assert crit["handling"] == "secret_store_only"
    for k in ("oidc_client_secret", "session_signing_key", "backup_encryption_key"):
        assert k in crit["examples"]


def test_public_config_is_not_secret() -> None:
    pub = _d()["classes"]["public-config"]
    assert pub["handling"] == "config_allowed_not_secret"
    assert "oidc_issuer_url" in pub["examples"]


def test_rules_client_secret_must_be_ref() -> None:
    r = _d()["rules"]
    assert r["oidcClientSecretMustBeSecretRef"] is True
    assert r["sessionSigningKeyMustBeSecretRef"] is True
    assert r["oidcIssuerUrlRealValueAllowedThisStage"] is False
