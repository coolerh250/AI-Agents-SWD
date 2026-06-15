"""Stage 49 -- build the Delivery Package Report (redacted, no raw code).

Aggregates package status, acceptance gate decision, human review status,
section summaries, artifact refs, warnings, limitations, and next steps into a
single operator-facing report. No secrets, no chain-of-thought, no full raw
code dump.
"""

from __future__ import annotations

from shared.sdk.delivery_package.section_builder import KNOWN_LIMITATIONS, NEXT_STEPS


def build_delivery_package_report(
    *,
    package_id: str | None,
    project_id: str | None,
    pilot_id: str | None,
    package_status: str,
    gate,
    human_acceptance_status: str,
    readiness_status: str | None,
    sections: list,
    artifact_refs: list | None = None,
) -> dict:
    """Assemble the delivery package report dict (safe for persistence + API)."""
    section_summaries = [
        {
            "section_key": getattr(s, "section_key", None),
            "title": getattr(s, "title", None),
            "status": getattr(s, "status", None),
            "content_summary": getattr(s, "content_summary", None),
        }
        for s in sections
    ]
    warnings = [
        c.summary for c in getattr(gate, "checks", []) if getattr(c, "status", None) == "warning"
    ]
    return {
        "report_type": "delivery_package_report",
        "package_id": package_id,
        "project_id": project_id,
        "pilot_id": pilot_id,
        "package_status": package_status,
        "acceptance_gate_status": getattr(gate, "status", None),
        "acceptance_gate_decision": getattr(gate, "decision", None),
        "blocking_findings_count": getattr(gate, "blocking_findings_count", 0),
        "total_checks": getattr(gate, "total_checks", 0),
        "passed_checks": getattr(gate, "passed_checks", 0),
        "failed_checks": getattr(gate, "failed_checks", 0),
        "warning_checks": getattr(gate, "warning_checks", 0),
        "human_acceptance_status": human_acceptance_status,
        "human_acceptance_required": True,
        "readiness_status": readiness_status,
        "section_summaries": section_summaries,
        "sections_ready_count": sum(1 for s in sections if getattr(s, "status", None) == "ready"),
        "sections_missing_count": sum(
            1 for s in sections if getattr(s, "status", None) == "missing"
        ),
        "artifact_refs": artifact_refs or [],
        "warnings": warnings,
        "known_limitations": list(KNOWN_LIMITATIONS),
        "next_steps": list(NEXT_STEPS),
        "controlled_only": True,
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "real_llm_used": False,
        "external_delivery_performed": False,
    }


__all__ = ["build_delivery_package_report"]
