"""Step AT-M3.4 -- formal planning decision: converged discussion -> TeamDecision -> accepted plan.

Composes what already exists rather than adding a parallel stack. The decision is an AT-M2
``TeamDecision``; the plan is an AT-M3.2 ``PlanRevision`` moving draft -> accepted through that
module's own guarded lifecycle; the evidence is the AT-M3.3 discussion's own thread. What this
package adds is the finalization: one admissibility gate, one transaction, one ledger row.

It records a decision. It creates no WorkItem, routes nothing, dispatches nothing, executes nothing
and calls no external provider -- those begin in AT-M3.5 and AT-M4. It also creates no human
Approval and satisfies none: a TeamDecision is team planning consensus and nothing more.
"""

from __future__ import annotations

from shared.sdk.agent_planning_decision.models import (
    PLAN_ACCEPTED,
    DecisionEvidence,
    DiscussionNotAdmissibleError,
    PlanningDecisionStateError,
    build_decision_evidence,
    derive_idempotency_key,
    evaluate_admissibility,
    validate_plan,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_planning_decision.store import LedgerRaceLost, PlanningDecisionStore

__all__ = [
    "PLAN_ACCEPTED",
    "DecisionEvidence",
    "DiscussionNotAdmissibleError",
    "LedgerRaceLost",
    "PlanningDecisionService",
    "PlanningDecisionStateError",
    "PlanningDecisionStore",
    "build_decision_evidence",
    "derive_idempotency_key",
    "evaluate_admissibility",
    "validate_plan",
]
