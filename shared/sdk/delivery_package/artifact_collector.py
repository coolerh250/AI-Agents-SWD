"""Stage 49 -- collect source artifact references for a delivery package.

Links project / design review / workspace / QA / safety / acceptance / mini
delivery report sources into ``DeliveryPackageArtifact`` rows. Stores refs,
hashes, and short summaries only -- never large raw code or secrets.
"""

from __future__ import annotations

from shared.sdk.delivery_package.models import DeliveryPackageArtifact


def build_package_artifacts(evidence: dict) -> list[DeliveryPackageArtifact]:
    """One DeliveryPackageArtifact per linked evidence source (refs only)."""
    project_id = evidence.get("project_id")
    pilot = evidence.get("pilot") or {}
    workspace_report = evidence.get("workspace_report") or {}
    files = workspace_report.get("files") or []
    artifacts: list[DeliveryPackageArtifact] = []

    def _add(atype: str, title: str, ref: dict, *, source_table=None, source_id=None) -> None:
        artifacts.append(
            DeliveryPackageArtifact(
                artifact_type=atype,
                source_table=source_table,
                source_id=str(source_id) if source_id else None,
                title=title,
                content=ref,
            )
        )

    if project_id:
        _add(
            "project_brief",
            "Project brief",
            {"project_id": project_id, "title": (evidence.get("project") or {}).get("title")},
            source_table="projects",
            source_id=project_id,
        )
        _add(
            "task_graph",
            "Task graph / work items",
            {"work_items_count": len(evidence.get("work_items") or [])},
            source_table="project_work_items",
        )
    if evidence.get("design_review_session_id"):
        _add(
            "design_review_summary",
            "Design review",
            {
                "design_review_session_id": evidence.get("design_review_session_id"),
                "decision": (evidence.get("review") or {}).get("decision"),
            },
            source_table="design_review_sessions",
            source_id=evidence.get("design_review_session_id"),
        )
    if evidence.get("workspace_id"):
        _add(
            "workspace_report",
            "Workspace report",
            {"workspace_id": evidence.get("workspace_id"), "files_count": len(files)},
            source_table="code_workspaces",
            source_id=evidence.get("workspace_id"),
        )
        # File manifest carries paths + hashes only -- never file bodies.
        _add(
            "generated_code_manifest",
            "Generated files manifest",
            {
                "files": [
                    {
                        "relative_path": f.get("relative_path"),
                        "content_hash": f.get("content_hash"),
                        "size_bytes": f.get("size_bytes"),
                    }
                    for f in files
                ]
            },
        )
        for test_run in workspace_report.get("test_runs") or []:
            _add(
                "test_result",
                f"Test run: {test_run.get('test_type')}",
                {
                    "test_type": test_run.get("test_type"),
                    "status": test_run.get("status"),
                    "tests_total": test_run.get("tests_total"),
                    "tests_passed": test_run.get("tests_passed"),
                    "tests_failed": test_run.get("tests_failed"),
                },
            )
    if evidence.get("qa"):
        _add(
            "qa_evidence_report",
            "QA evidence report",
            {"status": (evidence.get("qa") or {}).get("status")},
            source_table="qa_evidence_reports",
        )
    if evidence.get("safety"):
        _add(
            "safety_evidence_report",
            "Safety evidence report",
            {"status": (evidence.get("safety") or {}).get("status")},
            source_table="safety_evidence_reports",
        )
    _add(
        "acceptance_evaluations",
        "Acceptance evaluations",
        evidence.get("acceptance_summary") or {},
        source_table="acceptance_evaluations",
    )
    if pilot:
        _add(
            "mini_delivery_report",
            "Mini delivery pilot report",
            {"pilot_id": pilot.get("id"), "pilot_status": pilot.get("status")},
            source_table="mini_delivery_reports",
        )
    return artifacts


__all__ = ["build_package_artifacts"]
