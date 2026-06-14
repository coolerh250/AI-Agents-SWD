"""Stage 45 -- assignment policy tests."""

from __future__ import annotations

from shared.sdk.project_planning.assignment_policy import (
    assign_agent_role,
    is_future_role,
    is_runnable_role,
    resolve_dispatch_policy,
)


def test_work_type_maps_to_role() -> None:
    assert assign_agent_role("requirement") == "requirement-agent"
    assert assign_agent_role("qa") == "qa-agent"
    assert assign_agent_role("devops") == "devops-agent"
    assert assign_agent_role("backend") == "development-agent"


def test_unknown_work_type_defaults_to_development() -> None:
    assert assign_agent_role("nonsense") == "development-agent"
    assert assign_agent_role(None) == "development-agent"


def test_runnable_vs_future_roles() -> None:
    assert is_runnable_role("development-agent") is True
    assert is_runnable_role("qa-agent") is True
    assert is_future_role("architecture-capability") is True
    assert is_runnable_role("architecture-capability") is False


def test_future_role_never_auto_dispatched() -> None:
    # architecture maps to a future role -> planning_only, never auto-run.
    assert resolve_dispatch_policy("architecture", "low") == "planning_only"


def test_high_risk_requires_approval() -> None:
    assert resolve_dispatch_policy("backend", "high") == "approval_required"
    assert resolve_dispatch_policy("backend", "production") == "approval_required"


def test_runnable_role_uses_default_policy() -> None:
    assert (
        resolve_dispatch_policy("backend", "low", default_policy="auto_dev_test_allowed")
        == "auto_dev_test_allowed"
    )
    # default stays planning_only this stage
    assert resolve_dispatch_policy("backend", "low") == "planning_only"
