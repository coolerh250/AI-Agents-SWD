"""Stage 52 -- Admin Console v1 Operator Actions SDK (Step 50).

Controlled, governed operator actions on top of the Admin Console v0 read-only
visibility and the Delivery Package / Acceptance Gate. Every action passes
authentication, RBAC, CSRF, policy, confirmation, idempotency, and audit. Only
low-risk, reversible, allowlisted actions are executable; high-risk actions are
disabled-only catalog entries.
"""

from __future__ import annotations

from shared.sdk.operator_actions.audit_events import (
    OPERATOR_ACTION_DECISION_TYPES,
    safe_operator_action_refs,
)
from shared.sdk.operator_actions.auth import AuthConfig, resolve_auth_config, test_login_allowed
from shared.sdk.operator_actions.events import (
    OPERATOR_ACTION_DENY_PATTERNS,
    OPERATOR_ACTION_EVENTS,
)
from shared.sdk.operator_actions.models import (
    OperatorActionExecution,
    OperatorActionRequest,
    OperatorIdentity,
    OperatorReviewNote,
    VerificationRerunRequest,
)
from shared.sdk.operator_actions.safety import operator_action_safety_flags
from shared.sdk.operator_actions.store import DEFAULT_DATABASE_URL, OperatorActionStore

__all__ = [
    "AuthConfig",
    "resolve_auth_config",
    "test_login_allowed",
    "OperatorIdentity",
    "OperatorActionRequest",
    "OperatorActionExecution",
    "OperatorReviewNote",
    "VerificationRerunRequest",
    "OperatorActionStore",
    "DEFAULT_DATABASE_URL",
    "OPERATOR_ACTION_DECISION_TYPES",
    "safe_operator_action_refs",
    "OPERATOR_ACTION_EVENTS",
    "OPERATOR_ACTION_DENY_PATTERNS",
    "operator_action_safety_flags",
]
