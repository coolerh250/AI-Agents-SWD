"""Step 52.2 -- OIDC discovery metadata contract: schema only, no fetch."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-discovery-contract.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_no_fetch() -> None:
    d = _d()["discovery"]
    assert d["fetchEnabled"] is False
    assert d["lastFetchedAt"] is None
    assert d["metadataConfigured"] is False
    assert d["validated"] is False


def test_expected_metadata_fields() -> None:
    fields = _d()["expectedMetadataFields"]
    for f in (
        "issuer",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "id_token_signing_alg_values_supported",
        "claims_supported",
    ):
        assert f in fields


def test_no_external_request_allowed() -> None:
    c = _d()["constraints"]
    assert c["externalRequestAllowed"] is False
    assert c["realEndpointStored"] is False
    assert c["requiredSigningAlg"] == "RS256"
