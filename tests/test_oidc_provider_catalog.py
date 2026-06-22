"""Step 52.2 -- OIDC provider catalog: disabled, unconfigured, no real values."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-provider-catalog.yaml"


def _prov() -> dict:
    data = yaml.safe_load(F.read_text(encoding="utf-8"))
    return data["providers"]["production-oidc-placeholder"]


def test_provider_disabled_and_unconfigured() -> None:
    p = _prov()
    assert p["enabled"] is False
    assert p["productionAllowed"] is False
    assert p["configured"] is False
    assert p["status"] == "disabled_unconfigured"


def test_no_real_issuer_or_jwks_or_redirect() -> None:
    p = _prov()
    assert p["issuer"]["value"] == ""
    assert p["jwks"]["uri"] == ""
    assert p["redirectUris"]["values"] == []


def test_fetch_disabled() -> None:
    p = _prov()
    assert p["discovery"]["fetchEnabled"] is False
    assert p["jwks"]["fetchEnabled"] is False


def test_client_secret_is_ref_only_and_empty() -> None:
    p = _prov()
    assert p["client"]["clientId"]["valueRef"] == ""
    ref = p["client"]["clientSecret"]["secretRef"]
    assert ref["name"] == "" and ref["key"] == ""


def test_role_mapping_deny_unknown() -> None:
    p = _prov()
    assert p["roleMapping"]["configured"] is False
    assert p["roleMapping"]["behavior"] == "deny_unknown"
