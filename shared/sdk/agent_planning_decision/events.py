"""Step AT-M3.4 -- audit decision types for the formal planning decision.

Identifiers, outcomes and dispositions only. What the team said lives in ``team_messages`` and
``team_decisions.rationale_summary``, both of which AT-M2 already screens; nothing here carries a
message body, a plan, a prompt, a completion or a secret.
"""

from __future__ import annotations

AUDIT_PLANNING_DECISION_RECORDED = "planning_decision_recorded"
AUDIT_PLANNING_DECISION_REPLAYED = "planning_decision_replayed"
AUDIT_PLANNING_DECISION_REJECTED = "planning_decision_rejected"

__all__ = [
    "AUDIT_PLANNING_DECISION_RECORDED",
    "AUDIT_PLANNING_DECISION_REJECTED",
    "AUDIT_PLANNING_DECISION_REPLAYED",
]
