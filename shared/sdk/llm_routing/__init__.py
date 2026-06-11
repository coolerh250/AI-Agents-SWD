"""Stage 38 -- LLM Model Routing & Agent Model Policy SDK.

This package centralises every "which model do we use for this LLM
call?" decision. Agents do NOT pick models. Agents submit
:class:`LLMCapabilityRequest` describing **what capability** they need
(classification / requirement_analysis / development_plan / qa_review
/ ...), plus risk level + schema + estimated tokens. The
:class:`ModelRouter` consults:

* ``agent_model_policies`` -- per (agent, task_type, capability,
  risk_level) policy (default-deny: missing policy blocks).
* ``llm_model_registry`` -- catalogue of available models with
  capability list, schema support, status, and hard-safety flags.
* ``llm_budget`` (Stage 35) -- preflight budget gate.
* Stage 30 / 35 safety rails -- patch_generation + workspace_write
  remain hard-disabled regardless of registry / policy state.

Outputs are :class:`LLMRoutingDecision`, persisted to
``llm_routing_decisions``. The decision row never carries a prompt,
response, or API key value.
"""

from __future__ import annotations

from .evaluator import build_capability_request, schema_supported
from .models import (
    AGENT_DEFAULT_TASK_TYPE,
    DEFAULT_REAL_LLM_DISABLED,
    DECISION_BLOCKED,
    DECISION_BUDGET_BLOCKED,
    DECISION_DIRECT_MODEL_REJECTED,
    DECISION_FALLBACK_SELECTED,
    DECISION_HUMAN_APPROVAL_REQUIRED,
    DECISION_MOCK_SELECTED,
    DECISION_POLICY_NOT_FOUND,
    DECISION_PROVIDER_UNAVAILABLE,
    DECISION_SCHEMA_UNSUPPORTED,
    DECISION_SELECTED,
    MODEL_STATUS_ACTIVE,
    MODEL_STATUS_BLOCKED,
    MODEL_STATUS_DEPRECATED,
    MODEL_STATUS_INACTIVE,
    MODEL_TIER_CRITICAL,
    MODEL_TIER_DEVELOPMENT_QA,
    MODEL_TIER_DOCUMENTATION,
    MODEL_TIER_LIGHTWEIGHT,
    AgentModelPolicy,
    LLMCapabilityRequest,
    LLMModelEntry,
    LLMRoutingDecision,
    RoutingDecisionRecord,
)
from .registry import DEFAULT_MODEL_SEED, default_models, validate_model_entry
from .policy import DEFAULT_AGENT_POLICY_SEED, default_agent_policies
from .router import ModelRouter
from .store import ModelRouterStore

__all__ = [
    "AGENT_DEFAULT_TASK_TYPE",
    "AgentModelPolicy",
    "DECISION_BLOCKED",
    "DECISION_BUDGET_BLOCKED",
    "DECISION_DIRECT_MODEL_REJECTED",
    "DECISION_FALLBACK_SELECTED",
    "DECISION_HUMAN_APPROVAL_REQUIRED",
    "DECISION_MOCK_SELECTED",
    "DECISION_POLICY_NOT_FOUND",
    "DECISION_PROVIDER_UNAVAILABLE",
    "DECISION_SCHEMA_UNSUPPORTED",
    "DECISION_SELECTED",
    "DEFAULT_AGENT_POLICY_SEED",
    "DEFAULT_MODEL_SEED",
    "DEFAULT_REAL_LLM_DISABLED",
    "LLMCapabilityRequest",
    "LLMModelEntry",
    "LLMRoutingDecision",
    "MODEL_STATUS_ACTIVE",
    "MODEL_STATUS_BLOCKED",
    "MODEL_STATUS_DEPRECATED",
    "MODEL_STATUS_INACTIVE",
    "MODEL_TIER_CRITICAL",
    "MODEL_TIER_DEVELOPMENT_QA",
    "MODEL_TIER_DOCUMENTATION",
    "MODEL_TIER_LIGHTWEIGHT",
    "ModelRouter",
    "ModelRouterStore",
    "RoutingDecisionRecord",
    "build_capability_request",
    "default_agent_policies",
    "default_models",
    "schema_supported",
    "validate_model_entry",
]
