"""Stage 46 -- no chain-of-thought persistence guarantee."""

from __future__ import annotations

from pathlib import Path

import pytest
from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore

from shared.sdk.agent_discussion.safety import assert_no_chain_of_thought
from shared.sdk.design_review import run_design_review

_FORBIDDEN_KEYS = ("chain_of_thought", "raw_prompt", "transcript", "reasoning_trace")
_MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "018_agent_discussion_design_review.sql"
)


def test_migration_has_no_chain_of_thought_columns() -> None:
    # Strip SQL comment lines (the header comment legitimately mentions the
    # forbidden names while explaining they are deliberately absent).
    raw = _MIGRATION.read_text(encoding="utf-8").lower()
    code = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("--"))
    assert "chain_of_thought" not in code
    assert "raw_prompt" not in code
    assert "transcript" not in code


def test_assert_no_chain_of_thought_helper() -> None:
    assert_no_chain_of_thought({"summary": "ok", "confidence": "high"})
    with pytest.raises(ValueError):
        assert_no_chain_of_thought({"chain_of_thought": "secret reasoning"})


async def test_persisted_contributions_have_no_forbidden_keys() -> None:
    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)
    discussion = FakeDiscussionStore()
    out = await run_design_review(
        project_id=project_id,
        project_store=project_store,
        discussion_store=discussion,
        review_store=FakeDesignReviewStore(),
        emit_events=False,
    )
    for contrib in discussion.contributions[out.discussion_session_id]:
        for key in contrib:
            assert key.lower() not in _FORBIDDEN_KEYS
