"""Dataclasses + constants for the LLM budget SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

SCOPE_GLOBAL = "global"
SCOPE_TASK = "task"
SCOPE_WORKFLOW = "workflow"
SCOPE_USER = "user"
SCOPE_PROVIDER = "provider"

ENFORCEMENT_BLOCK = "block"
ENFORCEMENT_WARN_ONLY = "warn_only"

POLICY_STATUS_ACTIVE = "active"
POLICY_STATUS_INACTIVE = "inactive"
POLICY_STATUS_EXPIRED = "expired"

EVENT_TYPE_PREFLIGHT = "preflight"
EVENT_TYPE_RECORDED_USAGE = "recorded_usage"
EVENT_TYPE_BUDGET_EXCEEDED = "budget_exceeded"
EVENT_TYPE_BUDGET_WARNING = "budget_warning"

DECISION_ALLOWED = "allowed"
DECISION_BLOCKED = "blocked"
DECISION_WARNING = "warning"
DECISION_RECORDED = "recorded"


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class LLMBudgetPolicy:
    policy_id: str
    policy_name: str
    scope_type: str
    scope_id: str | None
    provider: str
    model_name: str | None
    max_tokens_per_task: int | None
    max_cost_per_task_usd: float | None
    max_cost_per_day_usd: float | None
    max_cost_per_month_usd: float | None
    enforcement_mode: str
    status: str
    created_by: str
    created_at: datetime | None
    updated_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "max_tokens_per_task": self.max_tokens_per_task,
            "max_cost_per_task_usd": _f(self.max_cost_per_task_usd),
            "max_cost_per_day_usd": _f(self.max_cost_per_day_usd),
            "max_cost_per_month_usd": _f(self.max_cost_per_month_usd),
            "enforcement_mode": self.enforcement_mode,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": dict(self.metadata or {}),
        }


@dataclass
class LLMBudgetEvent:
    budget_event_id: str
    task_id: str | None
    workflow_id: str | None
    policy_id: str | None
    provider: str
    model_name: str
    event_type: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_total_tokens: int
    actual_prompt_tokens: int | None
    actual_completion_tokens: int | None
    actual_total_tokens: int | None
    estimated_cost_usd: float
    actual_cost_usd: float | None
    budget_remaining_usd: float | None
    decision: str
    reason: str | None
    created_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "budget_event_id": self.budget_event_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "policy_id": self.policy_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "event_type": self.event_type,
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            "estimated_completion_tokens": self.estimated_completion_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "actual_prompt_tokens": self.actual_prompt_tokens,
            "actual_completion_tokens": self.actual_completion_tokens,
            "actual_total_tokens": self.actual_total_tokens,
            "estimated_cost_usd": float(self.estimated_cost_usd or 0.0),
            "actual_cost_usd": _f(self.actual_cost_usd),
            "budget_remaining_usd": _f(self.budget_remaining_usd),
            "decision": self.decision,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": dict(self.metadata or {}),
        }


@dataclass
class BudgetDecision:
    """Result of :meth:`BudgetPolicyEvaluator.preflight`."""

    decision: str
    reason: str | None
    enforcement_mode: str
    policy_id: str | None
    policy_name: str | None
    provider: str
    model_name: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_total_tokens: int
    estimated_cost_usd: float
    budget_remaining_usd: float | None
    cap_breached: str | None = (
        None  # token_per_task | cost_per_task | cost_per_day | cost_per_month
    )
    used_today_usd: float | None = None
    used_month_usd: float | None = None
    used_task_tokens: int | None = None
    used_task_cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == DECISION_ALLOWED

    @property
    def warning(self) -> bool:
        return self.decision == DECISION_WARNING

    @property
    def blocked(self) -> bool:
        return self.decision == DECISION_BLOCKED

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "enforcement_mode": self.enforcement_mode,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "provider": self.provider,
            "model_name": self.model_name,
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            "estimated_completion_tokens": self.estimated_completion_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "estimated_cost_usd": float(self.estimated_cost_usd),
            "budget_remaining_usd": _f(self.budget_remaining_usd),
            "cap_breached": self.cap_breached,
            "used_today_usd": _f(self.used_today_usd),
            "used_month_usd": _f(self.used_month_usd),
            "used_task_tokens": self.used_task_tokens,
            "used_task_cost_usd": _f(self.used_task_cost_usd),
            "metadata": dict(self.metadata or {}),
        }
