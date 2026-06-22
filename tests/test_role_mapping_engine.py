"""Step 52.3 -- role mapping engine: explicit mapping only, deny by default."""

from __future__ import annotations

from shared.sdk.identity import (
    IdentityClaims,
    RoleMappingRule,
    map_identity_to_role,
)

_RULES = [
    RoleMappingRule(rule_id="r-op", match_group="group-operator-placeholder", role="operator"),
    RoleMappingRule(rule_id="r-pa", match_group="group-pa-placeholder", role="platform_admin"),
]


def _claims(**kw: object) -> IdentityClaims:
    base = dict(
        subject="s", email="a@example.com", email_verified=True, groups=[], provider_key="p"
    )
    base.update(kw)
    return IdentityClaims(**base)  # type: ignore[arg-type]


def test_explicit_group_grants_role() -> None:
    d = map_identity_to_role(_claims(groups=["group-operator-placeholder"]), _RULES)
    assert d.allowed and d.role == "operator" and d.matched_rule == "r-op"


def test_missing_subject_denies() -> None:
    assert (
        map_identity_to_role(
            _claims(subject="", groups=["group-operator-placeholder"]), _RULES
        ).reason
        == "missing_subject"
    )


def test_missing_email_denies() -> None:
    assert (
        map_identity_to_role(
            _claims(email="", groups=["group-operator-placeholder"]), _RULES
        ).reason
        == "missing_email"
    )


def test_unverified_email_denies() -> None:
    d = map_identity_to_role(
        _claims(email_verified=False, groups=["group-operator-placeholder"]), _RULES
    )
    assert d.allowed is False and d.reason == "email_not_verified"


def test_missing_groups_denies() -> None:
    assert map_identity_to_role(_claims(groups=[]), _RULES).reason == "missing_groups"


def test_unknown_group_denies() -> None:
    d = map_identity_to_role(_claims(groups=["nope"]), _RULES)
    assert d.allowed is False and d.role is None and d.unknown_user is True


def test_platform_admin_requires_explicit_group() -> None:
    d = map_identity_to_role(_claims(groups=["group-pa-placeholder"]), _RULES)
    assert d.allowed and d.role == "platform_admin"


def test_default_role_is_none_on_deny() -> None:
    assert map_identity_to_role(_claims(groups=["nope"]), _RULES).role is None


def test_identity_claims_has_no_role_field() -> None:
    assert "role" not in IdentityClaims.model_fields
    assert "is_admin" not in IdentityClaims.model_fields
