"""Stage 48 -- mini delivery pilot report builder (redacted, no raw code)."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import (
    MiniDeliveryReport,
    QAEvidenceReport,
    SafetyEvidenceReport,
)

KNOWN_LIMITATIONS = [
    "No authentication / authorization (out of scope).",
    "Local SQLite only; not multi-user / not horizontally scalable.",
    "No production deployment configuration.",
    "No real GitHub PR in this stage (controlled-only).",
]

NEXT_STEPS = [
    "Step 47 Delivery Package & Acceptance Gate.",
    "Optionally Admin Console v0 after the delivery-package foundation.",
]


def build_mini_delivery_report(
    *,
    pilot_type: str,
    project_summary: dict,
    design_review_summary: dict,
    workspace_summary: dict,
    qa: QAEvidenceReport,
    acceptance_summary: dict,
    safety: SafetyEvidenceReport,
    artifact_refs: list | None = None,
) -> MiniDeliveryReport:
    ready = (
        qa.status in ("passed", "passed_with_findings")
        and safety.status in ("safe", "safe_with_findings")
        and acceptance_summary.get("failed", 0) == 0
    )
    exec_summary = (
        f"Controlled mini delivery pilot for {pilot_type}: project planned, design "
        f"reviewed, controlled workspace generated + tested. QA={qa.status}, "
        f"safety={safety.status}, acceptance "
        f"{acceptance_summary.get('satisfied', 0)}/{acceptance_summary.get('total', 0)} "
        f"satisfied. No PR, no deploy, no real LLM; production_executed=false."
    )
    return MiniDeliveryReport(
        report_type="mini_delivery_pilot_report",
        status="ready" if ready else "draft",
        title=f"Mini delivery pilot report — {pilot_type}",
        executive_summary=exec_summary,
        project_summary=project_summary,
        design_review_summary=design_review_summary,
        workspace_summary=workspace_summary,
        qa_summary={
            "status": qa.status,
            "tests_total": qa.tests_total,
            "tests_passed": qa.tests_passed,
            "tests_failed": qa.tests_failed,
            "static_checks_status": qa.static_checks_status,
        },
        acceptance_summary=acceptance_summary,
        safety_summary={
            "status": safety.status,
            "production_executed_count": safety.production_executed_count,
            "github_write_performed": safety.github_write_performed,
            "pr_created": safety.pr_created,
            "deployment_performed": safety.deployment_performed,
            "real_llm_used": safety.real_llm_used,
            "repo_root_modified": safety.repo_root_modified,
            "secret_leak_detected": safety.secret_leak_detected,
            "chain_of_thought_persisted": safety.chain_of_thought_persisted,
        },
        known_limitations=list(KNOWN_LIMITATIONS),
        next_steps=list(NEXT_STEPS),
        artifact_refs=artifact_refs or [],
    )


__all__ = ["build_mini_delivery_report", "KNOWN_LIMITATIONS", "NEXT_STEPS"]
