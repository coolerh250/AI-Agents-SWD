"""Stage 52 -- Pydantic models for Admin Console v1 operator actions.

Strict, secret-free models. NO raw password / raw session token / raw
confirmation token fields. ``production_executed`` is always false. Operator
actions are low-risk, reversible, audited, and policy-bounded.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ROLES = ("viewer", "reviewer", "operator", "platform_admin")
IDENTITY_SOURCES = ("test_local", "oidc", "service")
IDENTITY_STATUSES = ("active", "disabled")
SESSION_STATUSES = ("active", "expired", "revoked")
ACTION_STATUSES = (
    "requested",
    "policy_blocked",
    "confirmation_required",
    "approved",
    "executing",
    "completed",
    "failed",
    "cancelled",
)
NOTE_TYPES = (
    "general",
    "finding",
    "requested_change",
    "acceptance_note",
    "rejection_note",
)
RISK_LEVELS = ("low", "medium", "high", "critical")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OperatorIdentity(_Strict):
    identity_key: str
    display_name: str | None = None
    identity_source: str = "test_local"
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoleAssignment(_Strict):
    identity_key: str
    role: str
    environment_scope: str = "test"
    active: bool = True


class SessionRecord(_Strict):
    identity_key: str
    session_hash: str
    status: str = "active"
    issued_at: str | None = None
    expires_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorActionRequest(_Strict):
    action_key: str
    identity_key: str
    action_type: str
    target_type: str | None = None
    target_id: str | None = None
    reason: str = Field(min_length=1)
    requested_payload: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    policy_status: str = "pending"
    approval_status: str = "not_required"
    confirmation_status: str = "not_required"
    idempotency_key: str
    status: str = "requested"
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorActionExecution(_Strict):
    execution_type: str
    status: str
    result_summary: str | None = None
    error_summary: str | None = None
    production_executed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorReviewNote(_Strict):
    package_id: str | None = None
    project_id: str | None = None
    identity_key: str
    note_type: str = "general"
    summary: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationRerunRequest(_Strict):
    verification_key: str
    script_key: str
    status: str = "requested"
    report_path: str | None = None
    result_marker: str | None = None
    exit_code: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionPolicyEntry(_Strict):
    action_type: str
    allowed_roles: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    requires_reason: bool = True
    requires_confirmation: bool = False
    requires_approval_engine: bool = False
    execution_enabled: bool = False


__all__ = [
    "ROLES",
    "IDENTITY_SOURCES",
    "IDENTITY_STATUSES",
    "SESSION_STATUSES",
    "ACTION_STATUSES",
    "NOTE_TYPES",
    "RISK_LEVELS",
    "OperatorIdentity",
    "RoleAssignment",
    "SessionRecord",
    "OperatorActionRequest",
    "OperatorActionExecution",
    "OperatorReviewNote",
    "VerificationRerunRequest",
    "ActionPolicyEntry",
]
