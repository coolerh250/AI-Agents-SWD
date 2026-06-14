"""Stage 46 -- which agent roles participate in a discussion session.

Deterministic, table-driven. Roles are *review output sources*, not real
LLM conversants. Future roles (architecture-capability, security-capability,
delivery-capability) participate as reviewers but never dispatch work.
"""

from __future__ import annotations

from shared.sdk.agent_discussion.models import DiscussionParticipant

# Full pre-execution design review participants, in review order.
_FULL_REVIEW_ROLES = (
    ("requirement-agent", "reviewer"),
    ("project-planner-agent", "reviewer"),
    ("architecture-capability", "reviewer"),
    ("development-agent", "reviewer"),
    ("qa-agent", "reviewer"),
    ("security-capability", "reviewer"),
    ("devops-agent", "reviewer"),
    ("delivery-capability", "approver"),
)

_SESSION_TYPE_ROLES = {
    "project_design_review": _FULL_REVIEW_ROLES,
    "requirement_review": (("requirement-agent", "owner"), ("project-planner-agent", "reviewer")),
    "architecture_review": (
        ("architecture-capability", "owner"),
        ("development-agent", "reviewer"),
    ),
    "qa_strategy_review": (("qa-agent", "owner"), ("development-agent", "reviewer")),
    "security_review": (("security-capability", "owner"),),
    "delivery_readiness_review": (("delivery-capability", "owner"), ("devops-agent", "reviewer")),
    "risk_review": (("project-planner-agent", "owner"), ("security-capability", "reviewer")),
    "implementation_strategy_review": (
        ("development-agent", "owner"),
        ("architecture-capability", "reviewer"),
    ),
}


def participants_for(session_type: str) -> list[DiscussionParticipant]:
    """Return the deterministic participant list for a session type."""
    roles = _SESSION_TYPE_ROLES.get(session_type, _FULL_REVIEW_ROLES)
    return [
        DiscussionParticipant(agent_role=role, participation_type=ptype, status="completed")
        for (role, ptype) in roles
    ]


__all__ = ["participants_for", "_FULL_REVIEW_ROLES"]
