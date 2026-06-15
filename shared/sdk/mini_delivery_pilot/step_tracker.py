"""Stage 48 -- pilot step helpers (deterministic step model construction)."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import MiniDeliveryPilotStep

# step_key -> step_type.
STEP_TYPES_BY_KEY = {
    "project_plan": "planning",
    "design_review": "review",
    "workspace_execution": "implementation",
    "test_execution": "testing",
    "acceptance_evaluation": "acceptance",
    "qa_summary": "qa",
    "safety_summary": "safety",
    "pilot_report": "reporting",
}

PILOT_STEP_ORDER = (
    "project_plan",
    "design_review",
    "workspace_execution",
    "test_execution",
    "acceptance_evaluation",
    "qa_summary",
    "safety_summary",
    "pilot_report",
)


def make_step(
    step_key: str, status: str, *, summary: str | None = None, evidence_refs: list | None = None
) -> MiniDeliveryPilotStep:
    return MiniDeliveryPilotStep(
        step_key=step_key,
        step_type=STEP_TYPES_BY_KEY.get(step_key, "reporting"),
        status=status,
        summary=summary,
        evidence_refs=evidence_refs or [],
    )


__all__ = ["make_step", "STEP_TYPES_BY_KEY", "PILOT_STEP_ORDER"]
