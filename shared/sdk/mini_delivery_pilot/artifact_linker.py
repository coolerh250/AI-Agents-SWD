"""Stage 48 -- link project/review/workspace/QA/safety/report into pilot artifacts."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import PilotArtifact


def build_pilot_artifacts(
    *,
    project_id: str | None,
    design_review_session_id: str | None,
    workspace_id: str | None,
    qa_report_id: str | None,
    safety_report_id: str | None,
    mini_delivery_report_id: str | None,
    acceptance_total: int,
) -> list[PilotArtifact]:
    """One PilotArtifact per linked evidence source (refs only, no content)."""
    artifacts: list[PilotArtifact] = []

    def _add(atype: str, title: str, ref: dict) -> None:
        artifacts.append(PilotArtifact(artifact_type=atype, title=title, content=ref))

    if project_id:
        _add("project_plan_ref", "Project plan", {"project_id": project_id})
    if design_review_session_id:
        _add(
            "design_review_ref",
            "Design review",
            {"design_review_session_id": design_review_session_id},
        )
    if workspace_id:
        _add("workspace_report_ref", "Workspace report", {"workspace_id": workspace_id})
    _add("acceptance_evaluation_ref", "Acceptance evaluations", {"count": acceptance_total})
    if qa_report_id:
        _add("qa_evidence_ref", "QA evidence", {"qa_report_id": qa_report_id})
    if safety_report_id:
        _add("safety_evidence_ref", "Safety evidence", {"safety_report_id": safety_report_id})
    if mini_delivery_report_id:
        _add(
            "mini_delivery_report_ref",
            "Mini delivery report",
            {"mini_delivery_report_id": mini_delivery_report_id},
        )
    return artifacts


__all__ = ["build_pilot_artifacts"]
