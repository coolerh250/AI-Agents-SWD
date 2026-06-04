"""Stage 31 -- flexible human approval policy + LLM proposal promotion SDK.

Public surface:

* :class:`HumanApprovalPolicy`, :class:`HumanApprovalDecision`,
  :class:`LLMProposalApproval`, :class:`LLMProposalPromotion` --
  dataclass snapshots of the Stage 31 tables.
* :class:`ApprovalPolicyStore` -- async asyncpg store for all four.
* :class:`ApprovalPolicyEvaluator`, :class:`EvaluationResult`,
  :func:`evaluate_action` -- deterministic evaluator.
* Constants:
  - :data:`APPROVAL_MODES`           -- per_action / per_feature / per_stage / delegated
  - :data:`SCOPE_TYPES`              -- action / feature / stage / workflow / task
  - :data:`POLICY_STATUSES`          -- pending / active / expired / revoked / rejected
  - :data:`PROMOTION_STATUSES`
  - :data:`HARD_SAFETY_ACTIONS`      -- actions that can NEVER be delegated
  - :data:`MIN_DELEGATED_CONSTRAINTS` -- required fields for delegated policies
"""

from shared.sdk.approval_policy.evaluator import (
    ApprovalPolicyEvaluator,
    EvaluationResult,
    HARD_SAFETY_ACTIONS,
    MIN_DELEGATED_CONSTRAINTS,
    evaluate_action,
)
from shared.sdk.approval_policy.models import (
    APPROVAL_MODES,
    HumanApprovalDecision,
    HumanApprovalPolicy,
    LLMProposalApproval,
    LLMProposalPromotion,
    POLICY_STATUSES,
    PROMOTION_STATUSES,
    SCOPE_TYPES,
)
from shared.sdk.approval_policy.store import ApprovalPolicyStore

__all__ = [
    "APPROVAL_MODES",
    "ApprovalPolicyEvaluator",
    "ApprovalPolicyStore",
    "EvaluationResult",
    "HARD_SAFETY_ACTIONS",
    "HumanApprovalDecision",
    "HumanApprovalPolicy",
    "LLMProposalApproval",
    "LLMProposalPromotion",
    "MIN_DELEGATED_CONSTRAINTS",
    "POLICY_STATUSES",
    "PROMOTION_STATUSES",
    "SCOPE_TYPES",
    "evaluate_action",
]
