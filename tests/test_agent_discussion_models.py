"""Stage 46 -- agent discussion model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.agent_discussion.models import (
    DiscussionContribution,
    DiscussionParticipant,
    DiscussionSession,
)


def test_session_defaults() -> None:
    s = DiscussionSession(project_id="p1")
    assert s.planning_only is True
    assert s.review_mode == "deterministic_template"
    assert s.session_type == "project_design_review"


def test_contribution_requires_summary() -> None:
    c = DiscussionContribution(
        agent_role="qa-agent", contribution_type="qa_strategy", summary="run pytest"
    )
    assert c.confidence == "medium"


def test_models_reject_unknown_field() -> None:
    with pytest.raises(ValidationError):
        DiscussionParticipant(agent_role="x", bogus=1)  # type: ignore[call-arg]


def test_no_chain_of_thought_field() -> None:
    # the model must not accept a chain_of_thought field
    with pytest.raises(ValidationError):
        DiscussionContribution(
            agent_role="x",
            contribution_type="recommendation",
            summary="ok",
            chain_of_thought="secret reasoning",  # type: ignore[call-arg]
        )
