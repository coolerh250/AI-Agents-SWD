"""Step AT-M3.4 -- formal planning decision: converged discussion -> TeamDecision -> decided plan.

Composes what already exists rather than adding a parallel stack. The plan is authored by the
team's own planner principal through the AT-M3.1 ``decompose_plan`` verb and stored as an AT-M2
``TeamMessage``; the decision is an AT-M2 ``TeamDecision``; the plan lands as an AT-M3.2
``PlanRevision`` moving draft -> accepted through that module's own guarded lifecycle; the evidence
is the AT-M3.3 discussion's own thread. What this package adds is the finalization: one
admissibility gate, one candidate plan, one transaction, one ledger row.

Nothing here takes a plan or an author from its caller. That was the AT-M3.4 Validation 1 defect --
an arbitrary payload could become "what the team selected", decided by commit ordering -- and the
fix was to remove the inputs rather than to check them.

It records a decision. It creates no WorkItem, routes nothing, dispatches nothing, executes nothing
and calls no external provider -- those begin in AT-M3.5 and AT-M4. It also creates no human
Approval and satisfies none: a TeamDecision is team planning consensus and nothing more.
"""

from __future__ import annotations

from shared.sdk.agent_planning_decision.models import (
    NO_CHANGE,
    OUTCOME_FOR_CASE,
    PLAN_ACCEPTED,
    PLANNER_CAPABILITY,
    PLANNER_VERB,
    DecisionEvidence,
    DiscussionNotAdmissibleError,
    PlannerUnavailableError,
    PlanningDecisionConflictError,
    PlanningDecisionStateError,
    build_decision_evidence,
    derive_candidate_correlation_id,
    derive_case,
    derive_idempotency_key,
    evaluate_admissibility,
    is_candidate_for,
    plan_from_candidate,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_planning_decision.store import (
    LedgerRaceLost,
    PlanningDecisionStore,
    RevisionAlreadyDecided,
)

__all__ = [
    "NO_CHANGE",
    "OUTCOME_FOR_CASE",
    "PLANNER_CAPABILITY",
    "PLANNER_VERB",
    "PLAN_ACCEPTED",
    "DecisionEvidence",
    "DiscussionNotAdmissibleError",
    "LedgerRaceLost",
    "PlannerUnavailableError",
    "PlanningDecisionConflictError",
    "PlanningDecisionService",
    "PlanningDecisionStateError",
    "PlanningDecisionStore",
    "RevisionAlreadyDecided",
    "build_decision_evidence",
    "derive_candidate_correlation_id",
    "derive_case",
    "derive_idempotency_key",
    "evaluate_admissibility",
    "is_candidate_for",
    "plan_from_candidate",
]
