"""Stage 46 -- discussion session builder + participant policy tests."""

from __future__ import annotations

from shared.sdk.agent_discussion.participant_policy import participants_for
from shared.sdk.agent_discussion.session_builder import build_session

EXPECTED_ROLES = {
    "requirement-agent",
    "project-planner-agent",
    "architecture-capability",
    "development-agent",
    "qa-agent",
    "security-capability",
    "devops-agent",
    "delivery-capability",
}


def test_full_review_has_expected_roles() -> None:
    parts = participants_for("project_design_review")
    roles = {p.agent_role for p in parts}
    assert EXPECTED_ROLES <= roles
    assert len(parts) >= 7


def test_build_session_in_progress() -> None:
    session, participants = build_session(project_id="p1")
    assert session.status == "in_progress"
    assert session.planning_only is True
    assert len(participants) >= 7


def test_unknown_session_type_falls_back_to_full() -> None:
    parts = participants_for("nonexistent")
    assert len(parts) >= 7
