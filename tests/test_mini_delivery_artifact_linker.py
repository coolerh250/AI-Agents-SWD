"""Stage 48 -- pilot artifact linker."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.artifact_linker import build_pilot_artifacts


def test_links_all_sources() -> None:
    arts = build_pilot_artifacts(
        project_id="p1",
        design_review_session_id="r1",
        workspace_id="w1",
        qa_report_id="qa1",
        safety_report_id="s1",
        mini_delivery_report_id="rep1",
        acceptance_total=10,
    )
    types = {a.artifact_type for a in arts}
    assert {
        "project_plan_ref",
        "design_review_ref",
        "workspace_report_ref",
        "acceptance_evaluation_ref",
        "qa_evidence_ref",
        "safety_evidence_ref",
        "mini_delivery_report_ref",
    } <= types


def test_omits_missing_sources() -> None:
    arts = build_pilot_artifacts(
        project_id="p1",
        design_review_session_id=None,
        workspace_id=None,
        qa_report_id=None,
        safety_report_id=None,
        mini_delivery_report_id=None,
        acceptance_total=0,
    )
    types = {a.artifact_type for a in arts}
    assert "project_plan_ref" in types
    assert "design_review_ref" not in types
    assert "workspace_report_ref" not in types
