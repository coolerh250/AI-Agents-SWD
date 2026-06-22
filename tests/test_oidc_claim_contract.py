"""Step 52.2 -- OIDC claim contract: required claims, role claim not trusted."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-claim-contract.yaml"


def _c() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_required_claims() -> None:
    rc = _c()["requiredClaims"]
    assert rc["subject"]["claim"] == "sub"
    assert rc["email"]["required"] is True
    assert rc["email"]["verifiedRequired"] is True
    assert rc["emailVerified"]["claim"] == "email_verified"
    assert "groups" in rc


def test_role_claims_not_authoritative() -> None:
    c = _c()
    assert c["frontendRoleAuthority"] is False
    for claim in ("role", "is_admin", "platform_admin"):
        assert claim in c["forbiddenClaimsAsAuthority"]


def test_unknown_user_deny() -> None:
    assert _c()["unknownUserBehavior"] == "deny"
