"""Stage 46 -- Agent Discussion SDK."""

from __future__ import annotations

from shared.sdk.agent_discussion.audit_events import (
    AGENT_DISCUSSION_DECISION_TYPES,
    DECISION_AGENT_DISCUSSION_COMPLETED,
    DECISION_AGENT_DISCUSSION_CONTRIBUTION_RECORDED,
    DECISION_AGENT_DISCUSSION_STARTED,
)
from shared.sdk.agent_discussion.contribution_templates import build_contributions
from shared.sdk.agent_discussion.events import (
    DISCUSSION_NOTIFICATION_EVENTS,
    EVENT_DISCUSSION_SESSION_COMPLETED,
    EVENT_DISCUSSION_SESSION_STARTED,
    STREAM_AGENT_DISCUSSIONS,
)
from shared.sdk.agent_discussion.models import (
    DiscussionArtifact,
    DiscussionContribution,
    DiscussionOutput,
    DiscussionParticipant,
    DiscussionSession,
)
from shared.sdk.agent_discussion.participant_policy import participants_for
from shared.sdk.agent_discussion.safety import (
    assert_no_chain_of_thought,
    assert_no_secret,
    contains_secret,
    design_review_enabled,
    design_review_planning_only,
    design_review_real_llm_enabled,
    design_review_work_item_dispatch_enabled,
)
from shared.sdk.agent_discussion.session_builder import build_session
from shared.sdk.agent_discussion.store import AgentDiscussionStore

__all__ = [
    "DiscussionSession",
    "DiscussionParticipant",
    "DiscussionContribution",
    "DiscussionArtifact",
    "DiscussionOutput",
    "build_session",
    "participants_for",
    "build_contributions",
    "AgentDiscussionStore",
    "STREAM_AGENT_DISCUSSIONS",
    "EVENT_DISCUSSION_SESSION_STARTED",
    "EVENT_DISCUSSION_SESSION_COMPLETED",
    "DISCUSSION_NOTIFICATION_EVENTS",
    "AGENT_DISCUSSION_DECISION_TYPES",
    "DECISION_AGENT_DISCUSSION_STARTED",
    "DECISION_AGENT_DISCUSSION_COMPLETED",
    "DECISION_AGENT_DISCUSSION_CONTRIBUTION_RECORDED",
    "assert_no_chain_of_thought",
    "assert_no_secret",
    "contains_secret",
    "design_review_enabled",
    "design_review_planning_only",
    "design_review_real_llm_enabled",
    "design_review_work_item_dispatch_enabled",
]
