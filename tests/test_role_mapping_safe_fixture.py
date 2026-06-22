"""Step 52.3 -- safe role mapping fixture (placeholder groups only)."""

from __future__ import annotations

from shared.sdk.identity import (
    IdentityClaims,
    load_rules,
    load_safe_fixture,
    map_identity_to_role,
    validate_rules,
)


def test_fixture_marked_non_production() -> None:
    assert load_safe_fixture()["nonProductionFixture"] is True


def test_fixture_groups_are_placeholders_only() -> None:
    for r in load_rules(load_safe_fixture()):
        assert "placeholder" in r.match_group


def test_fixture_validates_clean() -> None:
    assert validate_rules(load_rules(load_safe_fixture())) == []


def test_each_placeholder_group_maps_to_role() -> None:
    rules = load_rules(load_safe_fixture())
    expected = {
        "group-viewer-placeholder": "viewer",
        "group-reviewer-placeholder": "reviewer",
        "group-operator-placeholder": "operator",
        "group-platform-admin-placeholder": "platform_admin",
    }
    for group, role in expected.items():
        d = map_identity_to_role(
            IdentityClaims(
                subject="s",
                email="a@example.com",
                email_verified=True,
                groups=[group],
                provider_key="p",
            ),
            rules,
        )
        assert d.allowed and d.role == role
