"""Stage 48 -- mini delivery pilot Redis stream + notification events.

All ``delivery_pilot.*`` / ``acceptance.*`` / ``qa_evidence.*`` notification
events are operator-internal and on the default real-delivery denylist (added
in Stage 48). They MUST NEVER reach a real Discord / Slack / Telegram channel.
"""

from __future__ import annotations

STREAM_DELIVERY_PILOT = "stream.delivery_pilot"
STREAM_DELIVERY_PILOT_EVENTS = "stream.delivery_pilot_events"

EVENT_DELIVERY_PILOT_STARTED = "delivery_pilot.started"
EVENT_DELIVERY_PILOT_STEP_STARTED = "delivery_pilot.step_started"
EVENT_DELIVERY_PILOT_STEP_COMPLETED = "delivery_pilot.step_completed"
EVENT_DELIVERY_PILOT_ACCEPTANCE_EVALUATED = "delivery_pilot.acceptance_evaluated"
EVENT_DELIVERY_PILOT_QA_EVALUATED = "delivery_pilot.qa_evaluated"
EVENT_DELIVERY_PILOT_SAFETY_EVALUATED = "delivery_pilot.safety_evaluated"
EVENT_DELIVERY_PILOT_REPORT_READY = "delivery_pilot.report_ready"
EVENT_DELIVERY_PILOT_COMPLETED = "delivery_pilot.completed"
EVENT_DELIVERY_PILOT_FAILED = "delivery_pilot.failed"
EVENT_ACCEPTANCE_CRITERIA_SATISFIED = "acceptance.criteria_satisfied"
EVENT_QA_EVIDENCE_REPORT_READY = "qa_evidence.report_ready"

# Internal pipeline event published by the orchestrator router.
EVENT_PROJECT_DELIVERY_PILOT_REQUESTED = "project.delivery_pilot_requested"

DELIVERY_PILOT_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_DELIVERY_PILOT_STARTED,
    EVENT_DELIVERY_PILOT_STEP_STARTED,
    EVENT_DELIVERY_PILOT_STEP_COMPLETED,
    EVENT_DELIVERY_PILOT_ACCEPTANCE_EVALUATED,
    EVENT_DELIVERY_PILOT_QA_EVALUATED,
    EVENT_DELIVERY_PILOT_SAFETY_EVALUATED,
    EVENT_DELIVERY_PILOT_REPORT_READY,
    EVENT_DELIVERY_PILOT_COMPLETED,
    EVENT_DELIVERY_PILOT_FAILED,
    EVENT_ACCEPTANCE_CRITERIA_SATISFIED,
    EVENT_QA_EVIDENCE_REPORT_READY,
)

__all__ = [
    "STREAM_DELIVERY_PILOT",
    "STREAM_DELIVERY_PILOT_EVENTS",
    "EVENT_DELIVERY_PILOT_STARTED",
    "EVENT_DELIVERY_PILOT_STEP_STARTED",
    "EVENT_DELIVERY_PILOT_STEP_COMPLETED",
    "EVENT_DELIVERY_PILOT_ACCEPTANCE_EVALUATED",
    "EVENT_DELIVERY_PILOT_QA_EVALUATED",
    "EVENT_DELIVERY_PILOT_SAFETY_EVALUATED",
    "EVENT_DELIVERY_PILOT_REPORT_READY",
    "EVENT_DELIVERY_PILOT_COMPLETED",
    "EVENT_DELIVERY_PILOT_FAILED",
    "EVENT_ACCEPTANCE_CRITERIA_SATISFIED",
    "EVENT_QA_EVIDENCE_REPORT_READY",
    "EVENT_PROJECT_DELIVERY_PILOT_REQUESTED",
    "DELIVERY_PILOT_NOTIFICATION_EVENTS",
]
