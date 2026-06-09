"""Stage 35 -- structural tests for the LLM budget operations endpoints."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_budget_routes_registered():
    src = _read_operations()
    for path in (
        '@router.get("/llm/budget")',
        '@router.get("/llm/budget/policies")',
        '@router.get("/llm/budget/usage")',
        '@router.get("/llm/budget/events")',
        '@router.post("/llm/budget/policies")',
        '@router.get("/llm/plan-only/{task_id}")',
    ):
        assert path in src, f"missing route: {path}"


def test_safety_carries_stage35_llm_fields():
    src = _read_operations()
    for field in (
        '"real_llm_enabled_pilot"',
        '"llm_real_plan_only_enabled"',
        '"llm_patch_generation_enabled"',
        '"llm_workspace_write_enabled"',
        '"llm_cost_governance_enabled"',
        '"llm_budget_policy_active"',
        '"llm_budget_enforcement_mode"',
        '"llm_daily_budget_remaining"',
        '"llm_monthly_budget_remaining"',
        '"llm_budget_exceeded"',
    ):
        assert field in src, f"missing safety field: {field}"


def test_safety_fields_assert_patch_and_workspace_disabled():
    src = _read_operations()
    # These MUST be hard-coded to False.
    assert '"llm_patch_generation_enabled": False,' in src
    assert '"llm_workspace_write_enabled": False,' in src


def test_plan_only_endpoint_marks_requires_human_review_true():
    src = _read_operations()
    # Inside the plan-only endpoint body, requires_human_review MUST be True.
    block_start = src.index("async def operations_llm_plan_only_for_task")
    block_end = src.index("# ---", block_start + 1) if "# ---" in src[block_start:] else len(src)
    block = src[block_start:block_end]
    assert '"requires_human_review": True' in block
    assert '"plan_only": True' in block
    assert '"production_executed": False' in block
