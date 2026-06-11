"""Stage 38 -- agent model policy seed."""

from __future__ import annotations

from shared.sdk.llm_routing import default_agent_policies


def test_default_policies_cover_pipeline_agents():
    policies = default_agent_policies()
    agents = {p["agent_name"] for p in policies}
    assert "intake-agent" in agents
    assert "requirement-agent" in agents
    assert "development-agent" in agents
    assert "qa-agent" in agents
    assert "devops-agent" in agents


def test_default_policies_block_real_llm_patch_workspace():
    for p in default_agent_policies():
        assert p["allow_real_llm"] is False
        assert p["allow_patch_generation"] is False
        assert p["allow_workspace_write"] is False


def test_development_agent_requires_human_review_for_plan():
    by_capability = {(p["agent_name"], p["capability"]): p for p in default_agent_policies()}
    plan = by_capability[("development-agent", "development_plan")]
    assert plan["requires_human_review"] is True
    assert "mock-default" == plan["preferred_model_alias"]


def test_devops_agent_high_risk_requires_human_review():
    for p in default_agent_policies():
        if p["agent_name"] == "devops-agent":
            assert p["requires_human_review"] is True
            assert p["risk_level"] in ("high", "critical")


def test_qa_agent_advisory_only_requires_review():
    qa_policies = [p for p in default_agent_policies() if p["agent_name"] == "qa-agent"]
    assert qa_policies
    for p in qa_policies:
        assert p["requires_human_review"] is True


def test_intake_agent_max_cost_is_small():
    for p in default_agent_policies():
        if p["agent_name"] == "intake-agent":
            assert p["max_cost_per_task_usd"] is not None
            assert float(p["max_cost_per_task_usd"]) <= 0.02


def test_all_policies_active_status():
    for p in default_agent_policies():
        assert p["status"] == "active"
