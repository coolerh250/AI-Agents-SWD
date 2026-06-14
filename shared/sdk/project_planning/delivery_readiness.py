"""Stage 45 -- project delivery-readiness evaluation.

Pure function over the persisted project state. A project is
delivery-ready only when:

* every required acceptance criterion is satisfied,
* every critical work item is completed,
* a QA report artifact exists,
* a delivery summary artifact exists.

This stage only *builds* the judgement; the foundation does not require
all conditions to be met (a freshly-planned project is not ready).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeliveryReadiness:
    ready: bool
    reasons: list[str] = field(default_factory=list)
    required_acceptance_total: int = 0
    required_acceptance_satisfied: int = 0
    critical_work_items_total: int = 0
    critical_work_items_completed: int = 0
    qa_report_present: bool = False
    delivery_summary_present: bool = False

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "reasons": list(self.reasons),
            "required_acceptance_total": self.required_acceptance_total,
            "required_acceptance_satisfied": self.required_acceptance_satisfied,
            "critical_work_items_total": self.critical_work_items_total,
            "critical_work_items_completed": self.critical_work_items_completed,
            "qa_report_present": self.qa_report_present,
            "delivery_summary_present": self.delivery_summary_present,
        }


def evaluate_delivery_readiness(
    *,
    acceptance_criteria: list[dict],
    work_items: list[dict],
    artifacts: list[dict],
) -> DeliveryReadiness:
    required = [c for c in acceptance_criteria if c.get("required")]
    required_satisfied = [c for c in required if c.get("status") == "satisfied"]
    critical = [w for w in work_items if w.get("priority") == "critical"]
    critical_done = [w for w in critical if w.get("status") == "completed"]
    artifact_types = {a.get("artifact_type") for a in artifacts}
    qa_present = "qa_report" in artifact_types
    delivery_present = "delivery_summary" in artifact_types

    reasons: list[str] = []
    if required and len(required_satisfied) < len(required):
        reasons.append("required_acceptance_criteria_not_satisfied")
    if critical and len(critical_done) < len(critical):
        reasons.append("critical_work_items_not_completed")
    if not qa_present:
        reasons.append("qa_report_missing")
    if not delivery_present:
        reasons.append("delivery_summary_missing")

    ready = not reasons
    return DeliveryReadiness(
        ready=ready,
        reasons=reasons,
        required_acceptance_total=len(required),
        required_acceptance_satisfied=len(required_satisfied),
        critical_work_items_total=len(critical),
        critical_work_items_completed=len(critical_done),
        qa_report_present=qa_present,
        delivery_summary_present=delivery_present,
    )


__all__ = ["DeliveryReadiness", "evaluate_delivery_readiness"]
