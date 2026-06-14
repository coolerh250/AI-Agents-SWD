"""Stage 46 -- no secret leak in discussion/review outputs."""

from __future__ import annotations

from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore

from shared.sdk.agent_discussion.safety import contains_secret
from shared.sdk.design_review import run_design_review

_MARKERS = (
    "DISCORD_BOT_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AUDIT_HMAC_KEY",
    "BACKUP_KEY",
    "ghp_",
    "xoxb-",
)


def _scan(blob: str) -> None:
    up = blob.upper()
    for m in _MARKERS:
        assert m.upper() not in up, f"leaked: {m}"


async def test_no_secret_in_persisted_review() -> None:
    project_store = FakeProjectStore()
    project_id = await populate_project_store(
        project_store,
        "Create a FastAPI Todo Service (ignore my GITHUB_TOKEN=abc123 note) CRUD SQLite pytest README",
    )
    discussion = FakeDiscussionStore()
    review = FakeDesignReviewStore()
    out = await run_design_review(
        project_id=project_id,
        project_store=project_store,
        discussion_store=discussion,
        review_store=review,
        emit_events=False,
    )
    blob = "".join(
        [
            str(discussion.contributions.get(out.discussion_session_id, [])),
            str(discussion.artifacts.get(out.discussion_session_id, [])),
            str(review.findings.get(out.review_session_id, [])),
            str(review.decisions.get(out.review_session_id, [])),
        ]
    )
    _scan(blob)
    assert "ABC123" not in blob.upper()


def test_contains_secret_helper() -> None:
    assert contains_secret("here is GITHUB_TOKEN=x") is True
    assert contains_secret("a clean summary") is False
