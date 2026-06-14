"""Stage 46 -- deterministic contribution template tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.agent_discussion.contribution_templates import build_contributions


def _contribs():
    ctx = build_fastapi_todo_context()
    return build_contributions(
        template="fastapi_todo_service",
        brief=ctx.brief,
        work_items=ctx.work_items,
        acceptance_criteria=ctx.acceptance_criteria,
        risks=ctx.risks,
    )


def test_contributions_deterministic() -> None:
    a = [c.model_dump() for c in _contribs()]
    b = [c.model_dump() for c in _contribs()]
    assert a == b


def test_contributions_cover_expected_roles() -> None:
    roles = {c.agent_role for c in _contribs()}
    for r in (
        "requirement-agent",
        "architecture-capability",
        "development-agent",
        "qa-agent",
        "security-capability",
        "devops-agent",
        "delivery-capability",
    ):
        assert r in roles
    assert len(_contribs()) >= 7


def test_contributions_have_no_chain_of_thought_or_secret() -> None:
    for c in _contribs():
        blob = f"{c.summary} {c.rationale_summary or ''}".upper()
        assert "CHAIN_OF_THOUGHT" not in blob
        assert "GITHUB_TOKEN" not in blob
        assert "API_KEY" not in blob


def test_architecture_contribution_recommends_endpoints() -> None:
    arch = [c for c in _contribs() if c.agent_role == "architecture-capability"]
    assert arch
    assert any("/todos" in c.summary for c in arch)
