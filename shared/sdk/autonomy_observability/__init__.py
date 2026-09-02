"""Step AT-M3.6A -- the read-only observability projection over the autonomous runtime.

READ ONLY, WITHOUT AN EXCEPTION. This package exposes no command, no mutation and no scheduler
entry point. It adds no table, no lifecycle and no authority: every answer it gives is either a
canonical row passed through or a value derived from canonical rows at read time. Where it derives
something -- the autonomy phase, progress, blockers, plan currency, dispatch state -- that value is
recomputed on every read and stored nowhere, because a persisted copy would become a second
authority over a question the runtime tables already answer.

PostgreSQL is the only source. Redis is not consulted, not required, and not importable from this
package's read path: AT-M3.5 states plainly that stream delivery is at-least-once and that
``plan_execution_dispatches`` is the canonical exactly-once boundary, so a message's presence or
absence on a stream proves nothing about whether a dispatch happened.
"""

from shared.sdk.autonomy_observability.models import (
    AUTONOMY_PHASES,
    BLOCKER_CODES,
    DISPATCH_STATE_NOT_DISPATCHED,
    DISPATCH_STATE_RECORDED_UNPUBLISHED,
    DISPATCH_STATE_TO_CONTROL_STREAM,
    DISPATCH_TRUTH_NOTE,
    EXECUTION_MODE_INTERNAL,
    autonomy_phase,
    goal_blockers,
    graph_progress,
    next_ready_work,
    unit_blockers,
    unit_dispatch_state,
    unit_has_been_routed,
)
from shared.sdk.autonomy_observability.service import (
    AutonomyObservabilityService,
    EntityNotFound,
    GoalNotFound,
)
from shared.sdk.autonomy_observability.store import (
    DEFAULT_PAGE,
    MAX_PAGE,
    AutonomyReadStore,
)

__all__ = [
    "AUTONOMY_PHASES",
    "BLOCKER_CODES",
    "DEFAULT_PAGE",
    "DISPATCH_STATE_NOT_DISPATCHED",
    "DISPATCH_STATE_RECORDED_UNPUBLISHED",
    "DISPATCH_STATE_TO_CONTROL_STREAM",
    "DISPATCH_TRUTH_NOTE",
    "EXECUTION_MODE_INTERNAL",
    "MAX_PAGE",
    "AutonomyObservabilityService",
    "AutonomyReadStore",
    "EntityNotFound",
    "GoalNotFound",
    "autonomy_phase",
    "goal_blockers",
    "graph_progress",
    "next_ready_work",
    "unit_blockers",
    "unit_dispatch_state",
    "unit_has_been_routed",
]
