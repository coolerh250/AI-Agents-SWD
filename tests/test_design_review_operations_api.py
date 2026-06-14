"""Stage 46 -- design review operations API tests (fakes, no DB)."""

from __future__ import annotations

import pytest
import design_review_api
from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore


@pytest.fixture
async def wired(monkeypatch: pytest.MonkeyPatch):
    project_store = FakeProjectStore()
    discussion = FakeDiscussionStore()
    review = FakeDesignReviewStore()
    project_id = await populate_project_store(project_store)
    monkeypatch.setattr(design_review_api, "_project_store", lambda: project_store)
    monkeypatch.setattr(design_review_api, "_discussion_store", lambda: discussion)
    monkeypatch.setattr(design_review_api, "_review_store", lambda: review)

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)
    return project_id


async def test_run_review_then_read(wired) -> None:
    project_id = wired
    out = await design_review_api.run_project_design_review(project_id, {})
    assert out["production_executed"] is False
    assert out["planning_only"] is True
    assert out["work_item_dispatch_enabled"] is False
    assert out["participants_count"] >= 7
    assert out["gates_count"] >= 6
    review_session_id = out["review_session_id"]
    discussion_session_id = out["discussion_session_id"]

    disc = await design_review_api.list_project_discussions(project_id)
    assert disc["count"] >= 1
    parts = await design_review_api.get_discussion_participants(discussion_session_id)
    assert parts["count"] >= 7
    contribs = await design_review_api.get_discussion_contributions(discussion_session_id)
    assert contribs["count"] >= 7
    findings = await design_review_api.get_design_review_findings(review_session_id)
    assert findings["count"] >= 1
    decisions = await design_review_api.get_design_review_decisions(review_session_id)
    assert decisions["count"] >= 1
    gates = await design_review_api.get_project_review_gates(project_id)
    assert gates["count"] >= 6
    gono = await design_review_api.get_project_go_no_go(project_id)
    assert gono["latest_review_decision"] in ("planning_only", "go_with_findings", "go")
    cov = await design_review_api.get_project_acceptance_coverage(project_id)
    assert cov["total"] >= 8


async def test_responses_have_no_secret_or_cot(wired) -> None:
    project_id = wired
    out = await design_review_api.run_project_design_review(project_id, {})
    contribs = await design_review_api.get_discussion_contributions(out["discussion_session_id"])
    blob = str(contribs).upper()
    assert "GITHUB_TOKEN" not in blob
    assert "API_KEY" not in blob
    assert "CHAIN_OF_THOUGHT" not in blob


async def test_unknown_project_404(wired) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await design_review_api.run_project_design_review(
            "00000000-0000-0000-0000-000000000000", {}
        )
    assert exc.value.status_code == 404
