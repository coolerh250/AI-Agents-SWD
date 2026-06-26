"""Step 59 -- sandbox draft PR dry-run planner."""

from __future__ import annotations

import pytest

from shared.sdk.sandbox_github.dry_run import PlanError, build_plan


def _plan(**over):
    kw = dict(
        repository_key="ai-agents-sandbox",
        project_key="DEMO",
        project_id="pid",
        work_item_key="WI-0001",
        work_item_title="Add a thing",
        work_item_id="wid",
        correlation_id="corr12345678",
    )
    kw.update(over)
    return build_plan(**kw)


def test_plan_for_allowlisted_repo() -> None:
    plan = _plan()
    assert plan.base_branch == "main"
    assert plan.head_branch.startswith("sandbox/ai-agents/")
    d = plan.to_dict()
    assert d["draft"] is True
    assert d["ready_for_review"] is False
    assert d["production_executed"] is False


def test_unknown_repo_raises() -> None:
    with pytest.raises(PlanError) as e:
        _plan(repository_key="nope")
    assert e.value.reason == "repository_not_allowlisted"


def test_disallowed_base_branch_raises() -> None:
    with pytest.raises(PlanError) as e:
        _plan(base_branch="production")
    assert e.value.reason in ("base_branch_not_allowed", "base_branch_forbidden")
