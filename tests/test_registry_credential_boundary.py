"""Step 54.3 -- registry credential boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "registry-credential-boundary.yaml"


def _b() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["registryCredentialBoundary"]


def test_credential_via_secret_store_only() -> None:
    b = _b()
    assert b["credentialViaSecretStoreOnly"] is True
    assert b["credentialInRepo"] is False


def test_no_login_push_pull_this_stage() -> None:
    b = _b()
    assert b["registryLoginInThisStage"] is False
    assert b["imagePushInThisStage"] is False
    assert b["imagePullWithCredentialInThisStage"] is False
    assert b["productionRegistryAccess"] == "disabled"
    assert b["productionReady"] is False


def test_links_step53_secret_references() -> None:
    assert "infra/secrets" in _b()["secretReferenceCatalog"]
