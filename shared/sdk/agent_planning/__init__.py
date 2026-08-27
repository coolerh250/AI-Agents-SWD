"""Step AT-M3.2 -- Goal + immutable PlanRevision (AT-D04, authorized by AT-D14).

The durable planning foundation the autonomous team plans against: a Goal is the intent, and a
PlanRevision is one append-only, diffable, traceable version of the plan that serves it. Changing
a plan appends revision N+1 naming N; it never rewrites N, and that is enforced by a database
trigger, not only by this package.

This slice makes planning DATA durable. It does not decompose a Goal (AT-M3.4), does not dispatch
work (AT-M3.5), and makes no provider call of any kind (AT-M3.1 owns reasoning; AT-M3.6B, a real
external call, remains unauthorized).
"""

from __future__ import annotations

from shared.sdk.agent_planning.events import (
    AUDIT_GOAL_CREATED,
    AUDIT_PLAN_REVISION_ACCEPTED,
    AUDIT_PLAN_REVISION_CREATED,
    AUDIT_PLAN_REVISION_STALE_REJECTED,
    AUDIT_PLAN_REVISION_SUPERSEDED,
)
from shared.sdk.agent_planning.models import (
    REPLAN_REASONS,
    Goal,
    GoalStatus,
    PlanContent,
    PlanDiff,
    PlanLineageError,
    PlanRevision,
    PlanRevisionAllocationError,
    PlanRevisionLifecycleError,
    PlanRevisionReason,
    PlanRevisionStatus,
    PlanStep,
    PlanStepDraftError,
    StalePlanRevisionError,
    StepChange,
    compute_plan_diff,
    parse_plan,
)
from shared.sdk.agent_planning.service import PlanningService
from shared.sdk.agent_planning.store import DEFAULT_DATABASE_URL, PlanningStore

__all__ = [
    "AUDIT_GOAL_CREATED",
    "AUDIT_PLAN_REVISION_ACCEPTED",
    "AUDIT_PLAN_REVISION_CREATED",
    "AUDIT_PLAN_REVISION_STALE_REJECTED",
    "AUDIT_PLAN_REVISION_SUPERSEDED",
    "DEFAULT_DATABASE_URL",
    "Goal",
    "GoalStatus",
    "PlanContent",
    "PlanDiff",
    "PlanLineageError",
    "PlanRevision",
    "PlanRevisionAllocationError",
    "PlanRevisionLifecycleError",
    "PlanRevisionReason",
    "PlanRevisionStatus",
    "PlanStep",
    "PlanStepDraftError",
    "PlanningService",
    "PlanningStore",
    "REPLAN_REASONS",
    "StalePlanRevisionError",
    "StepChange",
    "compute_plan_diff",
    "parse_plan",
]
