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
    EVENT_TYPE_PREFLIGHT,
    EVENT_TYPE_RECORDED_USAGE,
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
    "EVENT_TYPE_PREFLIGHT",
    "EVENT_TYPE_RECORDED_USAGE",
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
