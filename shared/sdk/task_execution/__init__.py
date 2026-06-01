"""Stage 27 — flexible task execution loop SDK.

Public surface:

* :class:`TaskWorkItem` — frozen-ish snapshot of one work item.
* :class:`AgentDiscussion` — one row in the inter-agent discussion log.
* :class:`ClarificationRequest` — one operator clarification round-trip.
* :class:`TaskExecutionStore` — async asyncpg store for all three.
* :func:`classify_execution_mode` — deterministic classifier (no LLM).
* :mod:`shared.sdk.task_execution.mode_classifier` — classifier
  internals + canonical mode names.
"""

from shared.sdk.task_execution.mode_classifier import (
    EXECUTION_MODES,
    SCRUM_KEYWORDS,
    WORK_ITEM_STATUSES,
    ClassificationResult,
    classify_execution_mode,
    needs_clarification_signals,
)
from shared.sdk.task_execution.models import (
    AgentDiscussion,
    ClarificationRequest,
    TaskWorkItem,
)
from shared.sdk.task_execution.store import TaskExecutionStore

__all__ = [
    "AgentDiscussion",
    "ClarificationRequest",
    "ClassificationResult",
    "EXECUTION_MODES",
    "SCRUM_KEYWORDS",
    "TaskExecutionStore",
    "TaskWorkItem",
    "WORK_ITEM_STATUSES",
    "classify_execution_mode",
    "needs_clarification_signals",
]
