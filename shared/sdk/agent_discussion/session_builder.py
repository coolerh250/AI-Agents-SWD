"""Stage 46 -- build a discussion session + participants (deterministic)."""

from __future__ import annotations

from shared.sdk.agent_discussion.models import DiscussionParticipant, DiscussionSession
from shared.sdk.agent_discussion.participant_policy import participants_for


def build_session(
    *,
    project_id: str | None,
    session_type: str = "project_design_review",
    source_task_id: str | None = None,
    work_item_id: str | None = None,
    created_by_agent: str = "design-review-agent",
) -> tuple[DiscussionSession, list[DiscussionParticipant]]:
    session = DiscussionSession(
        project_id=project_id,
        session_type=session_type,
        source_task_id=source_task_id,
        work_item_id=work_item_id,
        status="in_progress",
        review_mode="deterministic_template",
        planning_only=True,
        created_by_agent=created_by_agent,
    )
    participants = participants_for(session_type)
    return session, participants


__all__ = ["build_session"]
