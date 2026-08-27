"""Step AT-M3.3 -- bounded, capability-aware team discussion.

Composes AT-M2 (team, capability router, ConversationThread/TeamMessage), AT-M3.1 (reasoning
contract and provider abstraction) and AT-M3.2 (Goal, immutable PlanRevision) into a deliberation
that is bounded, resumable and concurrency-safe.

It produces a discussion and a durable summary of where the discussion got to. It records no
TeamDecision, accepts no PlanRevision, creates no successor revision, generates no work items and
dispatches nothing -- those are AT-M3.4 and AT-M3.5.

Named ``agent_deliberation`` rather than ``agent_discussion`` because the latter is the Stage 46
deterministic-template review fixture that the collaboration contract supersedes and forbids
describing as multi-agent participation.
"""

from shared.sdk.agent_deliberation.events import (
    AUDIT_DISCUSSION_CLOSED,
    AUDIT_DISCUSSION_OPENED,
    AUDIT_DISCUSSION_TURN_LOST,
    AUDIT_DISCUSSION_TURN_RECORDED,
)
from shared.sdk.agent_deliberation.models import (
    DISCUSSION_STATES,
    MESSAGE_TYPE_FOR_INTENT,
    MIN_PARTICIPANTS,
    STATE_FOR_STOP_REASON,
    UNRESOLVED_INTENTS,
    ConvergenceVerdict,
    DiscussionBounds,
    DiscussionBoundsError,
    DiscussionParticipant,
    DiscussionParticipantError,
    DiscussionSession,
    DiscussionState,
    DiscussionStateError,
    DiscussionTurn,
    DiscussionTurnLost,
    DiscussionTurnUnresolvable,
    StopReason,
    TurnIntent,
    TurnPlan,
    TurnStatus,
    build_turn_context,
    classify_intent,
    derive_correlation_id,
    derive_idempotency_key,
    evaluate_convergence,
    plan_turn,
    summary_seat,
)
from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore

__all__ = [
    "AUDIT_DISCUSSION_CLOSED",
    "AUDIT_DISCUSSION_OPENED",
    "AUDIT_DISCUSSION_TURN_LOST",
    "AUDIT_DISCUSSION_TURN_RECORDED",
    "DISCUSSION_STATES",
    "MESSAGE_TYPE_FOR_INTENT",
    "MIN_PARTICIPANTS",
    "STATE_FOR_STOP_REASON",
    "UNRESOLVED_INTENTS",
    "ConvergenceVerdict",
    "DeliberationStore",
    "DiscussionBounds",
    "DiscussionBoundsError",
    "DiscussionParticipant",
    "DiscussionParticipantError",
    "DiscussionService",
    "DiscussionSession",
    "DiscussionState",
    "DiscussionStateError",
    "DiscussionTurn",
    "DiscussionTurnLost",
    "DiscussionTurnUnresolvable",
    "StopReason",
    "TurnIntent",
    "TurnPlan",
    "TurnStatus",
    "build_turn_context",
    "classify_intent",
    "derive_correlation_id",
    "derive_idempotency_key",
    "evaluate_convergence",
    "plan_turn",
    "summary_seat",
]
