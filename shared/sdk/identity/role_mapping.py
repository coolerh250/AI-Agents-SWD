"""Step 52.3 -- safe local role mapping engine (no network, no real IdP).

Maps OIDC-style group claims to a backend role using ONLY explicit rules. Every
failure path denies. Unknown users, unverified email, missing claims, wildcard
groups, and unmatched groups all yield a deny decision with role ``None``. A
token's ``role``/``is_admin`` claim is never read, so it can never be
authoritative. No default role is ever granted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.identity.role_mapping_models import (
    ALLOWED_ROLES,
    IdentityClaims,
    RoleMappingDecision,
    RoleMappingRule,
)

ROOT = Path(__file__).resolve().parents[3]
IDENTITY_DIR = ROOT / "infra" / "identity"

# Anything that would match more than one specific group is a wildcard.
_WILDCARD_TOKENS = {"", "*", "**", ".*", "*.*", "all", "any", ".+", "^.*$"}


def is_wildcard_group(match_group: str) -> bool:
    g = (match_group or "").strip()
    if g.lower() in _WILDCARD_TOKENS:
        return True
    # any unanchored regex-all fragment
    return "*" in g or g in (".*", ".+")


_RULE_KEY_ALIASES = {"ruleId": "rule_id", "matchGroup": "match_group"}


def load_rules(data: dict[str, Any]) -> list[RoleMappingRule]:
    """Parse rule dicts into RoleMappingRule (accepts camelCase YAML keys)."""
    rules = []
    for r in data.get("rules") or []:
        norm = {_RULE_KEY_ALIASES.get(k, k): v for k, v in r.items()}
        rules.append(RoleMappingRule(**norm))
    return rules


def validate_rules(rules: list[RoleMappingRule]) -> list[str]:
    """Return reasons a rule set is unsafe (wildcard group / disallowed role)."""
    errors: list[str] = []
    for r in rules:
        if is_wildcard_group(r.match_group):
            errors.append(f"wildcard group not allowed: {r.rule_id} -> {r.match_group!r}")
        if r.role not in ALLOWED_ROLES:
            errors.append(f"role not allowed: {r.rule_id} -> {r.role!r}")
    return errors


def _deny(reason: str) -> RoleMappingDecision:
    return RoleMappingDecision(
        allowed=False, role=None, reason=reason, matched_rule=None, unknown_user=True
    )


def map_identity_to_role(
    claims: IdentityClaims, rules: list[RoleMappingRule]
) -> RoleMappingDecision:
    """Resolve claims to a role via explicit rules only; deny by default."""
    if not claims.subject:
        return _deny("missing_subject")
    if not claims.email:
        return _deny("missing_email")
    if not claims.email_verified:
        return _deny("email_not_verified")
    if not claims.groups:
        return _deny("missing_groups")

    for rule in rules:
        if is_wildcard_group(rule.match_group):
            continue  # wildcard never matches -> cannot grant a role
        if rule.role not in ALLOWED_ROLES:
            continue
        if rule.match_group in claims.groups:
            return RoleMappingDecision(
                allowed=True,
                role=rule.role,
                reason="explicit_group_match",
                matched_rule=rule.rule_id,
                unknown_user=False,
            )
    return _deny("no_group_match")


def load_policy(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    return yaml.safe_load(
        (base / "infra" / "identity" / "role-mapping-policy.yaml").read_text(encoding="utf-8")
    )


def load_safe_fixture(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    return yaml.safe_load(
        (
            base / "infra" / "identity" / "test-fixtures" / "role-mapping-safe-fixture.yaml"
        ).read_text(encoding="utf-8")
    )


__all__ = [
    "is_wildcard_group",
    "load_rules",
    "validate_rules",
    "map_identity_to_role",
    "load_policy",
    "load_safe_fixture",
]
