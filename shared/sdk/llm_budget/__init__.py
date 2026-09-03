"""Stage 35 -- LLM cost governance + budget policy SDK.

This package owns the per-scope cost / token caps that gate every
real-LLM call. The flow is:

    caller -> BudgetPolicyEvaluator.preflight(task_id, provider, model,
                                              estimated_tokens / cost)
        -> active policy lookup (BudgetPolicyStore)
        -> per-task / per-day / per-month checks
        -> decision: allowed | blocked | warning
        -> llm_budget_events INSERT (regardless of outcome)

After a real-LLM call lands, the caller records the actual usage:

    caller -> BudgetPolicyEvaluator.record_usage(actual_tokens / cost)
        -> llm_budget_events INSERT (event_type=recorded_usage)
        -> if cumulative usage breaches a cap: insert one
           budget_exceeded event so an operator sees the breach
           without scanning the whole ledger.

AT-M3.6B.1 adds a stricter path for callers that spend real money on a
retryable attempt -- RESERVE BEFORE THE WIRE:

    caller -> preflight (as above, and it now sees existing reservations)
        -> reserve(reservation_key)   durable, counted from this moment
        -> [provider call]
        -> settle(reservation_key)    reservation becomes actual usage

One ledger row per attempt carries it from reservation to settlement, so
the day and month totals count reservations and settlements together
without any risk of counting an attempt twice. The ordering is the
guarantee: a post-call accounting failure can leave a charge
conservative, but it can no longer leave it at zero. ``release`` gives a
reservation back only where the absence of an external call is provable.

Every public function in this package is safe to log: nothing returns
or carries an API key value. Pricing tables are conservative
defaults; an operator can override via the ``LLMCostEstimator``
constructor.
"""

from __future__ import annotations

from .estimator import (
    DEFAULT_PRICING,
    LLMCostEstimator,
    estimate_tokens,
)
from .models import (
    DECISION_ALLOWED,
    DECISION_BLOCKED,
    DECISION_RECORDED,
    DECISION_WARNING,
    ENFORCEMENT_BLOCK,
    ENFORCEMENT_WARN_ONLY,
    EVENT_TYPE_BUDGET_EXCEEDED,
    EVENT_TYPE_BUDGET_WARNING,
    COUNTED_EVENT_TYPES,
    EVENT_TYPE_PREFLIGHT,
    EVENT_TYPE_RECORDED_USAGE,
    EVENT_TYPE_RELEASED_RESERVATION,
    EVENT_TYPE_RESERVED_USAGE,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_EXPIRED,
    POLICY_STATUS_INACTIVE,
    SCOPE_GLOBAL,
    SCOPE_PROVIDER,
    SCOPE_TASK,
    SCOPE_USER,
    SCOPE_WORKFLOW,
    BudgetDecision,
    LLMBudgetEvent,
    LLMBudgetPolicy,
)
from .policy import BudgetPolicyEvaluator
from .store import BudgetPolicyStore

__all__ = [
    "DEFAULT_PRICING",
    "DECISION_ALLOWED",
    "DECISION_BLOCKED",
    "DECISION_RECORDED",
    "DECISION_WARNING",
    "ENFORCEMENT_BLOCK",
    "ENFORCEMENT_WARN_ONLY",
    "EVENT_TYPE_BUDGET_EXCEEDED",
    "EVENT_TYPE_BUDGET_WARNING",
    "COUNTED_EVENT_TYPES",
    "EVENT_TYPE_PREFLIGHT",
    "EVENT_TYPE_RECORDED_USAGE",
    "EVENT_TYPE_RELEASED_RESERVATION",
    "EVENT_TYPE_RESERVED_USAGE",
    "POLICY_STATUS_ACTIVE",
    "POLICY_STATUS_EXPIRED",
    "POLICY_STATUS_INACTIVE",
    "SCOPE_GLOBAL",
    "SCOPE_PROVIDER",
    "SCOPE_TASK",
    "SCOPE_USER",
    "SCOPE_WORKFLOW",
    "BudgetDecision",
    "BudgetPolicyEvaluator",
    "BudgetPolicyStore",
    "LLMBudgetEvent",
    "LLMBudgetPolicy",
    "LLMCostEstimator",
    "estimate_tokens",
]
