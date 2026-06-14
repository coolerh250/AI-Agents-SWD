"""Stage 46 -- design review store URL + full run-through (fakes)."""

from __future__ import annotations

import pytest
from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore

from shared.sdk.design_review import DesignReviewStore, run_design_review


def test_store_uses_default_url() -> None:
    assert DesignReviewStore().database_url.startswith("postgresql://")


def test_store_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@y:5432/env-db")
    assert "env-db" in DesignReviewStore().database_url


async def test_full_review_persists_into_fakes() -> None:
    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)
    discussion = FakeDiscussionStore()
    review = FakeDesignReviewStore()
    out = await run_design_review(
        project_id=project_id,
        project_store=project_store,
        discussion_store=discussion,
        review_store=review,
        emit_events=False,
    )
    assert out.participants_count >= 7
    assert out.contributions_count >= 7
    assert out.gates_count >= 6
    assert out.findings_count >= 1
    assert out.decisions_count >= 1
    assert out.decision in ("planning_only", "go_with_findings", "go")
    assert out.production_executed is False
    # persisted
    assert discussion.contributions[out.discussion_session_id]
    assert review.findings[out.review_session_id]
    summary = await review.compute_review_summary(project_id)
    assert summary["gates_total"] >= 6
