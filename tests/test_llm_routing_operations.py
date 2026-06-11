"""Stage 38 -- structural assertions on the routing operations endpoints."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_routing_routes_registered():
    src = _read_operations()
    for path in (
        '@router.get("/llm/models")',
        '@router.get("/llm/model-policies")',
        '@router.get("/llm/routing-decisions")',
        '@router.get("/llm/routing-decisions/{task_id}")',
        '@router.post("/llm/routing/preview")',
        '@router.post("/llm/routing/seed-defaults")',
    ):
        assert path in src, f"missing route: {path}"


def test_safety_carries_stage38_routing_fields():
    src = _read_operations()
    for field in (
        '"llm_model_router_enabled"',
        '"agent_direct_model_selection_allowed": False',
        '"llm_routing_policy_enforced": True',
        '"llm_model_registry_active_count"',
        '"llm_routing_budget_enforced": True',
        '"llm_routing_human_review_enforced": True',
        '"llm_model_routing_active_policies"',
    ):
        assert field in src, f"missing safety field: {field}"


def test_summary_carries_routing_block():
    src = _read_operations()
    assert '"llm_model_routing_summary"' in src
    assert "_llm_routing_compact_summary" in src
    assert '"agent_direct_model_selection_allowed": False' in src
    assert '"patch_generation_hard_disabled": True' in src
    assert '"workspace_write_hard_disabled": True' in src


def test_workflow_view_exposes_routing_decisions():
    src = _read_operations()
    assert '"routing_decisions"' in src
    assert "ModelRouterStore()" in src
    assert '"selected_model"' in src
    assert '"routing_blocked"' in src


def test_no_secret_in_routing_handlers():
    """Stage 38 routing handlers must not read provider API keys.

    The check is scoped to the Stage 38 block so Stage 35's safety
    summary -- which DOES legitimately inspect ``OPENAI_API_KEY``
    presence -- is left alone.
    """

    src = _read_operations()
    marker = "Stage 38 -- LLM Model Routing & Agent Model Policy operations view"
    assert marker in src
    block = src[src.index(marker) :]
    for forbidden in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_API_KEY"):
        assert forbidden not in block, f"Stage 38 routing handlers must not read {forbidden}"
