"""Stage 49 -- build business / technical / operator handoff summaries.

Three audiences, three summaries. No secrets, no chain-of-thought, no raw
code -- only readable prose, highlights, limitations, next steps, and refs.
"""

from __future__ import annotations

from shared.sdk.delivery_package.models import HandoffSummary
from shared.sdk.delivery_package.section_builder import KNOWN_LIMITATIONS, NEXT_STEPS


def build_handoff_summaries(evidence: dict, gate) -> list[HandoffSummary]:
    pilot = evidence.get("pilot") or {}
    project = evidence.get("project") or {}
    qa = evidence.get("qa") or {}
    safety = evidence.get("safety") or {}
    acc = evidence.get("acceptance_summary") or {}
    workspace_report = evidence.get("workspace_report") or {}
    files = workspace_report.get("files") or []
    pilot_type = pilot.get("pilot_type") or "fastapi_todo_service"
    title = project.get("title") or pilot_type

    refs = {
        "package_pilot_id": pilot.get("id"),
        "project_id": evidence.get("project_id"),
        "workspace_id": evidence.get("workspace_id"),
    }

    business = HandoffSummary(
        summary_type="business_summary",
        title=f"Delivery summary — {title}",
        summary=(
            f"A controlled prototype of '{title}' was generated and verified automatically. "
            f"{acc.get('satisfied', 0)} of {acc.get('total', 0)} acceptance criteria are met, "
            f"automated tests are {qa.get('status', 'unknown')}, and no unsafe action was taken. "
            "The delivery is awaiting your acceptance; it has not been deployed or released."
        ),
        highlights=[
            f"{acc.get('satisfied', 0)}/{acc.get('total', 0)} acceptance criteria satisfied",
            "Automated tests executed against the generated code",
            "No production deployment, no external release",
        ],
        limitations=list(KNOWN_LIMITATIONS),
        next_steps=["Review the acceptance checklist", "Accept or request changes"],
        artifact_refs=[refs],
    )

    technical = HandoffSummary(
        summary_type="technical_summary",
        title=f"Technical handoff — {pilot_type}",
        summary=(
            f"{len(files)} files were generated in a controlled workspace. QA="
            f"{qa.get('status')} (tests_total={qa.get('tests_total')}, "
            f"tests_passed={qa.get('tests_passed')}, tests_failed={qa.get('tests_failed')}, "
            f"static_checks={qa.get('static_checks_status')}). Safety={safety.get('status')}; "
            "no GitHub write, no PR, no deploy, no real LLM, no chain-of-thought persisted."
        ),
        highlights=[
            f"{len(files)} generated files (manifest with hashes attached)",
            f"QA status: {qa.get('status')}",
            f"Safety status: {safety.get('status')}",
        ],
        limitations=list(KNOWN_LIMITATIONS),
        next_steps=list(NEXT_STEPS),
        artifact_refs=[refs],
    )

    operator = HandoffSummary(
        summary_type="operator_summary",
        title=f"Operator review — {title}",
        summary=(
            f"Acceptance gate decision={getattr(gate, 'decision', None)} "
            f"(status={getattr(gate, 'status', None)}, "
            f"blocking_findings={getattr(gate, 'blocking_findings_count', 0)}). "
            "Human acceptance is pending. Review the acceptance checklist and either accept "
            "the delivery or request changes. Operator action endpoints are disabled by "
            "default in this stage."
        ),
        highlights=[
            f"Gate decision: {getattr(gate, 'decision', None)}",
            f"Checks: {getattr(gate, 'passed_checks', 0)} passed / "
            f"{getattr(gate, 'failed_checks', 0)} failed / "
            f"{getattr(gate, 'warning_checks', 0)} warning",
            "Human acceptance pending (not auto-accepted)",
        ],
        limitations=["Operator accept/reject/request-changes disabled by default this stage"],
        next_steps=[
            "Inspect acceptance checklist",
            "Confirm controlled-only safety posture",
            "Accept or request changes (when operator actions are enabled)",
        ],
        artifact_refs=[refs],
    )
    return [business, technical, operator]


__all__ = ["build_handoff_summaries"]
