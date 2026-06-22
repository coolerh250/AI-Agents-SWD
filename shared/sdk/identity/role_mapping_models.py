"""Step 52.3 -- role mapping models (no network, no real IdP).

Inputs/outputs for the local role mapping engine. ``IdentityClaims`` carries no
``role``/``is_admin`` field on purpose: a token role claim is never authoritative.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_ROLES = ("viewer", "reviewer", "operator", "platform_admin")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IdentityClaims(_Strict):
    subject: str = ""
    email: str = ""
    email_verified: bool = False
    groups: list[str] = Field(default_factory=list)
    provider_key: str = ""


class RoleMappingRule(_Strict):
    rule_id: str
    match_group: str
    role: Literal["viewer", "reviewer", "operator", "platform_admin"]


class RoleMappingDecision(_Strict):
    allowed: bool
    role: str | None
    reason: str
    matched_rule: str | None
    unknown_user: bool


__all__ = [
    "ALLOWED_ROLES",
    "IdentityClaims",
    "RoleMappingRule",
    "RoleMappingDecision",
]
