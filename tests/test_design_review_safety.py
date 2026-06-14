"""Stage 46 -- design review planning-only safety tests."""

from __future__ import annotations

from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore

from shared.sdk.agent_discussion.safety import (
    design_review_enabled,
    design_review_planning_only,
    design_review_real_llm_enabled,
    design_review_work_item_dispatch_enabled,
)
from shared.sdk.design_review import run_design_review


def test_flag_defaults() -> None:
    assert design_review_enabled({}) is True
    assert design_review_planning_only({}) is True
    assert design_review_real_llm_enabled({}) is False
    assert design_review_work_item_dispatch_enabled({}) is False


async def test_review_is_planning_only_and_no_dispatch() -> None:
    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)
    out = await run_design_review(
        project_id=project_id,
        project_store=project_store,
        discussion_store=FakeDiscussionStore(),
        review_store=FakeDesignReviewStore(),
        planning_only=True,
        work_item_dispatch_enabled=False,
        emit_events=False,
    )
    assert out.planning_only is True
    assert out.work_item_dispatch_enabled is False
    assert out.production_executed is False
    # planning-only review never yields go/no-go that dispatches execution
    assert out.decision in ("planning_only", "no_go", "needs_clarification")


def test_operations_flag_helper() -> None:
    import operations

    assert operations._project_planning_flag("ENABLE_DESIGN_REVIEW", True) is True
    assert operations._project_planning_flag("ENABLE_DESIGN_REVIEW_REAL_LLM", False) is False
