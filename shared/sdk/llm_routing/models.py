"""Stage 38 -- dataclasses + constants for the Model Router."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_DEFAULT_TASK_TYPE = "default"

# Model tier names (also enforced by migration 014).
MODEL_TIER_CRITICAL = "tier_1_critical_reasoning"
MODEL_TIER_DEVELOPMENT_QA = "tier_2_development_qa"
MODEL_TIER_DOCUMENTATION = "tier_3_documentation_classification"
MODEL_TIER_LIGHTWEIGHT = "tier_4_lightweight_embedding"

MODEL_TIERS: tuple[str, ...] = (
    MODEL_TIER_CRITICAL,
    MODEL_TIER_DEVELOPMENT_QA,
    MODEL_TIER_DOCUMENTATION,
    MODEL_TIER_LIGHTWEIGHT,
)

# Registry status values.
MODEL_STATUS_ACTIVE = "active"
MODEL_STATUS_INACTIVE = "inactive"
MODEL_STATUS_DEPRECATED = "deprecated"
MODEL_STATUS_BLOCKED = "blocked"

# Risk levels.
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")

# Routing decision values (also enforced by migration 014).
DECISION_SELECTED = "selected"
DECISION_MOCK_SELECTED = "mock_selected"
DECISION_FALLBACK_SELECTED = "fallback_selected"
DECISION_BLOCKED = "blocked"
DECISION_BUDGET_BLOCKED = "budget_blocked"
DECISION_SCHEMA_UNSUPPORTED = "schema_unsupported"
DECISION_PROVIDER_UNAVAILABLE = "provider_unavailable"
DECISION_POLICY_NOT_FOUND = "policy_not_found"
DECISION_HUMAN_APPROVAL_REQUIRED = "human_approval_required"
DECISION_DIRECT_MODEL_REJECTED = "direct_model_rejected"

DECISIONS: tuple[str, ...] = (
    DECISION_SELECTED,
    DECISION_MOCK_SELECTED,
    DECISION_FALLBACK_SELECTED,
    DECISION_BLOCKED,
    DECISION_BUDGET_BLOCKED,
    DECISION_SCHEMA_UNSUPPORTED,
    DECISION_PROVIDER_UNAVAILABLE,
    DECISION_POLICY_NOT_FOUND,
    DECISION_HUMAN_APPROVAL_REQUIRED,
    DECISION_DIRECT_MODEL_REJECTED,
)

#: Hard-coded global default. Agents may NOT flip this at runtime.
DEFAULT_REAL_LLM_DISABLED = False


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LLMCapabilityRequest:
    """Standardised request submitted by an agent.

    Agents do NOT pass a model_name. ``requested_model_alias`` is a
    *preference* only -- the router treats it as a hint and rejects
    the request with ``direct_model_rejected`` if the alias is not
    allowed by the active policy.
    """

    agent_name: str
    capability: str
    task_id: str | None = None
    workflow_id: str | None = None
    task_type: str = AGENT_DEFAULT_TASK_TYPE
    execution_mode: str | None = None
    risk_level: str = "low"
    data_sensitivity: str = "internal"
    requested_schema: str | None = None
    requested_model_alias: str | None = None
    estimated_input_tokens: int = 0
    max_output_tokens: int | None = None
    max_cost_usd: float | None = None
    human_review_context: str | None = None
    allow_real_llm_requested: bool = False
    allow_patch_generation_requested: bool = False
    allow_workspace_write_requested: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "capability": self.capability,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "task_type": self.task_type,
            "execution_mode": self.execution_mode,
            "risk_level": self.risk_level,
            "data_sensitivity": self.data_sensitivity,
            "requested_schema": self.requested_schema,
            "requested_model_alias": self.requested_model_alias,
            "estimated_input_tokens": int(self.estimated_input_tokens or 0),
            "max_output_tokens": self.max_output_tokens,
            "max_cost_usd": self.max_cost_usd,
            "human_review_context": self.human_review_context,
            "allow_real_llm_requested": bool(self.allow_real_llm_requested),
            "allow_patch_generation_requested": bool(self.allow_patch_generation_requested),
            "allow_workspace_write_requested": bool(self.allow_workspace_write_requested),
            "metadata": dict(self.metadata),
        }


@dataclass
class LLMModelEntry:
    """One row in ``llm_model_registry``."""

    model_id: str
    provider: str
    model_name: str
    model_alias: str
    model_tier: str = MODEL_TIER_DOCUMENTATION
    capabilities: list[str] = field(default_factory=list)
    supported_schemas: list[str] = field(default_factory=list)
    max_context_tokens: int | None = None
    default_max_output_tokens: int | None = None
    cost_per_1k_input_tokens: float = 0.0
    cost_per_1k_output_tokens: float = 0.0
    latency_class: str = "standard"
    risk_level: str = "low"
    status: str = MODEL_STATUS_ACTIVE
    plan_only_allowed: bool = False
    patch_generation_allowed: bool = False
    workspace_write_allowed: bool = False
    production_use_allowed: bool = False
    requires_human_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "model_alias": self.model_alias,
            "model_tier": self.model_tier,
            "capabilities": list(self.capabilities),
            "supported_schemas": list(self.supported_schemas),
            "max_context_tokens": self.max_context_tokens,
            "default_max_output_tokens": self.default_max_output_tokens,
            "cost_per_1k_input_tokens": float(self.cost_per_1k_input_tokens or 0),
            "cost_per_1k_output_tokens": float(self.cost_per_1k_output_tokens or 0),
            "latency_class": self.latency_class,
            "risk_level": self.risk_level,
            "status": self.status,
            "plan_only_allowed": bool(self.plan_only_allowed),
            "patch_generation_allowed": bool(self.patch_generation_allowed),
            "workspace_write_allowed": bool(self.workspace_write_allowed),
            "production_use_allowed": bool(self.production_use_allowed),
            "requires_human_review": bool(self.requires_human_review),
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentModelPolicy:
    """One row in ``agent_model_policies``."""

    policy_id: str
    agent_name: str
    capability: str
    task_type: str = AGENT_DEFAULT_TASK_TYPE
    risk_level: str = "low"
    preferred_model_alias: str | None = None
    allowed_model_tiers: list[str] = field(default_factory=list)
    allowed_providers: list[str] = field(default_factory=list)
    fallback_model_aliases: list[str] = field(default_factory=list)
    max_cost_per_task_usd: float | None = None
    max_tokens_per_task: int | None = None
    requires_human_review: bool = False
    allow_real_llm: bool = False
    allow_patch_generation: bool = False
    allow_workspace_write: bool = False
    status: str = "active"
    created_by: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "agent_name": self.agent_name,
            "capability": self.capability,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "preferred_model_alias": self.preferred_model_alias,
            "allowed_model_tiers": list(self.allowed_model_tiers),
            "allowed_providers": list(self.allowed_providers),
            "fallback_model_aliases": list(self.fallback_model_aliases),
            "max_cost_per_task_usd": self.max_cost_per_task_usd,
            "max_tokens_per_task": self.max_tokens_per_task,
            "requires_human_review": bool(self.requires_human_review),
            "allow_real_llm": bool(self.allow_real_llm),
            "allow_patch_generation": bool(self.allow_patch_generation),
            "allow_workspace_write": bool(self.allow_workspace_write),
            "status": self.status,
            "created_by": self.created_by,
            "metadata": dict(self.metadata),
        }


@dataclass
class LLMRoutingDecision:
    """ModelRouter output.

    ``model`` / ``policy`` are populated when the decision selected a
    model; ``violations`` carries the human-readable list of cap /
    capability / schema / provider issues that pushed the decision
    away from ``selected``.
    """

    decision: str
    reason: str
    agent_name: str
    capability: str
    task_type: str = AGENT_DEFAULT_TASK_TYPE
    risk_level: str = "low"
    selected_provider: str | None = None
    selected_model_name: str | None = None
    selected_model_alias: str | None = None
    selected_model_tier: str | None = None
    requested_schema: str | None = None
    requested_model_alias: str | None = None
    fallback_used: bool = False
    requires_human_review: bool = False
    real_llm_allowed: bool = False
    patch_generation_allowed: bool = False
    workspace_write_allowed: bool = False
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    budget_policy_id: str | None = None
    policy_id: str | None = None
    model_id: str | None = None
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_select(self) -> bool:
        return self.decision in (
            DECISION_SELECTED,
            DECISION_MOCK_SELECTED,
            DECISION_FALLBACK_SELECTED,
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "agent_name": self.agent_name,
            "capability": self.capability,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "selected_provider": self.selected_provider,
            "selected_model_name": self.selected_model_name,
            "selected_model_alias": self.selected_model_alias,
            "selected_model_tier": self.selected_model_tier,
            "requested_schema": self.requested_schema,
            "requested_model_alias": self.requested_model_alias,
            "fallback_used": bool(self.fallback_used),
            "requires_human_review": bool(self.requires_human_review),
            "real_llm_allowed": bool(self.real_llm_allowed),
            "patch_generation_allowed": bool(self.patch_generation_allowed),
            "workspace_write_allowed": bool(self.workspace_write_allowed),
            "estimated_input_tokens": int(self.estimated_input_tokens or 0),
            "estimated_output_tokens": int(self.estimated_output_tokens or 0),
            "estimated_cost_usd": float(self.estimated_cost_usd or 0.0),
            "budget_policy_id": self.budget_policy_id,
            "policy_id": self.policy_id,
            "model_id": self.model_id,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


@dataclass
class RoutingDecisionRecord:
    """Persisted ``llm_routing_decisions`` row."""

    routing_decision_id: str
    task_id: str | None
    workflow_id: str | None
    agent_name: str
    capability: str
    task_type: str
    risk_level: str
    decision: str
    reason: str | None
    selected_provider: str | None
    selected_model_name: str | None
    selected_model_alias: str | None
    selected_model_tier: str | None
    requested_schema: str | None
    requested_model_alias: str | None
    fallback_used: bool
    estimated_input_tokens: int | None
    estimated_output_tokens: int | None
    estimated_cost_usd: float | None
    requires_human_review: bool
    real_llm_allowed: bool
    patch_generation_allowed: bool
    workspace_write_allowed: bool
    budget_policy_id: str | None
    policy_id: str | None
    model_id: str | None
    created_at: datetime
    metadata: dict[str, Any]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "routing_decision_id": self.routing_decision_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "agent_name": self.agent_name,
            "capability": self.capability,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "selected_provider": self.selected_provider,
            "selected_model_name": self.selected_model_name,
            "selected_model_alias": self.selected_model_alias,
            "selected_model_tier": self.selected_model_tier,
            "requested_schema": self.requested_schema,
            "requested_model_alias": self.requested_model_alias,
            "fallback_used": bool(self.fallback_used),
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_cost_usd": (
                float(self.estimated_cost_usd) if self.estimated_cost_usd is not None else None
            ),
            "requires_human_review": bool(self.requires_human_review),
            "real_llm_allowed": bool(self.real_llm_allowed),
            "patch_generation_allowed": bool(self.patch_generation_allowed),
            "workspace_write_allowed": bool(self.workspace_write_allowed),
            "budget_policy_id": self.budget_policy_id,
            "policy_id": self.policy_id,
            "model_id": self.model_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": dict(self.metadata),
        }
