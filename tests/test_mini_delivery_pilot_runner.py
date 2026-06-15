"""Stage 48 -- end-to-end mini delivery pilot runner (fakes + tmp workspace)."""

from __future__ import annotations

from mini_delivery_fakes import run_fake_pilot


async def test_full_pilot_end_to_end(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    assert result.pilot_id
    assert result.project_id
    assert result.design_review_session_id
    assert result.workspace_id
    assert result.pilot_status in ("completed", "report_ready")
    assert result.production_executed is False
    assert result.github_write_performed is False
    assert result.pr_created is False
    assert result.deployment_performed is False
    assert result.real_llm_used is False
    # acceptance: >= 8 satisfied, 0 failed for the FastAPI Todo template
    assert result.acceptance_total >= 8
    assert result.acceptance_satisfied >= 8
    assert result.acceptance_failed == 0
    assert result.qa_status in ("passed", "passed_with_findings")
    assert result.safety_status == "safe"


async def test_pilot_records_ordered_steps(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    steps = await stores["pilot"].list_steps(result.pilot_id)
    keys = [s["step_key"] for s in steps]
    assert "project_plan" in keys
    assert "design_review" in keys
    assert "workspace_execution" in keys
    assert "test_execution" in keys
    assert "acceptance_evaluation" in keys
    assert "qa_summary" in keys
    assert "safety_summary" in keys
    assert "pilot_report" in keys
    assert keys.index("project_plan") < keys.index("workspace_execution")


async def test_pilot_links_evidence(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    artifacts = await stores["pilot"].list_artifacts(result.pilot_id)
    types = {a["artifact_type"] for a in artifacts}
    assert "project_plan_ref" in types
    assert "design_review_ref" in types
    assert "workspace_report_ref" in types
    assert "mini_delivery_report_ref" in types
    report = await stores["pilot"].get_pilot_report(result.pilot_id)
    assert report["status"] in ("ready", "draft")
    assert report["executive_summary"]
