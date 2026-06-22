"""Step 52.2 -- OIDC abstraction models (no network, no real values).

Strict pydantic models describing a future production OIDC provider. They carry
NO secret value: ``client_secret`` is expressible only as a reference (name/key),
never an inline string. ``enabled`` / ``production_allowed`` default to false and
``unknown_user_behavior`` is constrained to ``deny``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_ROLES = ("viewer", "reviewer", "operator", "platform_admin")

# Config status reported by the loader/validator.
OidcConfigStatus = Literal[
    "disabled_unconfigured",
    "disabled_missing_required_fields",
    "invalid",
    "ready_for_future_enablement",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SecretRef(_Strict):
    """Reference to a secret stored elsewhere -- never the value itself."""

    name: str = ""
    key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.name and self.key)


class OidcClaimContract(_Strict):
    subject_claim: str = "sub"
    email_claim: str = "email"
    email_verified_required: bool = True
    groups_claim: str = "groups"
    groups_configured: bool = False
    unknown_user_behavior: Literal["deny"] = "deny"
    frontend_role_authority: Literal[False] = False


class OidcProviderConfig(_Strict):
    enabled: bool = False
    provider_key: str
    issuer_url: str | None = None
    discovery_url: str | None = None
    jwks_uri: str | None = None
    client_id_ref: SecretRef | None = None
    client_secret_ref: SecretRef | None = None
    redirect_uris: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    claim_contract: OidcClaimContract = Field(default_factory=OidcClaimContract)
    role_mapping_ref: str | None = None
    unknown_user_behavior: Literal["deny"] = "deny"
    production_allowed: bool = False


__all__ = [
    "ALLOWED_ROLES",
    "OidcConfigStatus",
    "SecretRef",
    "OidcClaimContract",
    "OidcProviderConfig",
]
