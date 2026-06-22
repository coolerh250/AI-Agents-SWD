"""Step 52.3 -- unsafe role mapping fixtures must fail validation / deny."""

from __future__ import annotations

import pytest

from shared.sdk.identity import (
    IdentityClaims,
    RoleMappingRule,
    is_wildcard_group,
    map_identity_to_role,
    validate_rules,
)


@pytest.mark.parametrize("group", ["*", "**", ".*", "", "all", "any"])
def test_wildcard_groups_detected(group: str) -> None:
    assert is_wildcard_group(group) is True


def test_wildcard_rule_rejected_by_validation() -> None:
    rules = [RoleMappingRule(rule_id="w", match_group="*", role="platform_admin")]
    assert validate_rules(rules) != []


def test_wildcard_rule_never_matches() -> None:
    rules = [RoleMappingRule(rule_id="w", match_group="*", role="platform_admin")]
    d = map_identity_to_role(
        IdentityClaims(
            subject="s", email="a@example.com", email_verified=True, groups=["*"], provider_key="p"
        ),
        rules,
    )
    assert d.allowed is False


def test_bad_role_rejected_by_strict_model() -> None:
    with pytest.raises(Exception):
        RoleMappingRule(rule_id="x", match_group="g", role="root")  # type: ignore[arg-type]


def test_non_placeholder_real_group_value_is_allowed_shape_but_still_explicit() -> None:
    # A non-wildcard explicit group is structurally valid; safety comes from it
    # being explicit (not a default/wildcard). This documents the boundary.
    rules = [RoleMappingRule(rule_id="r", match_group="some-explicit-group", role="viewer")]
    assert validate_rules(rules) == []
    d = map_identity_to_role(
        IdentityClaims(
            subject="s",
            email="a@example.com",
            email_verified=True,
            groups=["other"],
            provider_key="p",
        ),
        rules,
    )
    assert d.allowed is False  # no match -> deny
