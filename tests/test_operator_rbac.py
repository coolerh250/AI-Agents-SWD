"""Stage 52 -- RBAC matrix (backend authoritative)."""

from __future__ import annotations

import pytest

from shared.sdk.operator_actions.rbac import allowed_actions_for_roles, highest_role, role_can


@pytest.mark.parametrize(
    "role,action,expected",
    [
        ("viewer", "operator_review.add_note", False),
        ("viewer", "delivery_package.accept", False),
        ("reviewer", "operator_review.add_note", True),
        ("reviewer", "delivery_package.request_changes", True),
        ("reviewer", "delivery_package.accept", False),
        ("reviewer", "delivery_package.reject", False),
        ("operator", "delivery_package.accept", True),
        ("operator", "delivery_package.reject", True),
        ("operator", "verification.rerun", True),
        ("platform_admin", "delivery_package.accept", True),
        ("operator", "deployment.execute", False),
        ("platform_admin", "github.create_pr", False),
        ("platform_admin", "workflow.pause", False),
    ],
)
def test_role_can(role, action, expected) -> None:
    assert role_can(role, action) is expected


def test_highest_role() -> None:
    assert highest_role(["viewer", "operator"]) == "operator"
    assert highest_role(["reviewer"]) == "reviewer"
    assert highest_role([]) == "viewer"


def test_platform_admin_equals_operator() -> None:
    assert set(allowed_actions_for_roles(["platform_admin"])) == set(
        allowed_actions_for_roles(["operator"])
    )


def test_viewer_has_no_actions() -> None:
    assert allowed_actions_for_roles(["viewer"]) == []
