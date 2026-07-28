"""Step 66C.4-BE3-R1 (finding M-1 closure) -- production-action approval model.

Pure definitions + safe projections for the production_action_approvals table (migration 035). No
I/O, no HTTP, no resume/replay execution. This is the AUTHORITATIVE registry that
resume_replay_authorizations.production_approval_reference resolves against at consume time (BE3-R
combined review finding M-1: the reference was previously checked only for non-emptiness).

Design (be3-r1-m1-production-approval-contract.md, operator decisions 2026-07-28): RESOURCE-scoped
(same resource_type/resource_id as the resume/replay authorization it backs -- not task-scoped),
SINGLE-USE (consumed exactly once, alongside exactly one authorization consume), the same 1s-24h
validity bound used everywhere else in BE3. Approver ("granter") roles are the canonical TASK_ROLES
{reviewer_approver, platform_admin} -- the "Approve / reject gated action" row of
docs/test/ai-team-work-rbac-blueprint.md §3, the SAME pair already used for replay's Approver role.
No second RBAC system.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.tasks.rbac import TASK_ROLES

# Same action-type vocabulary as resume_replay_authorizations (migration 032).
ACTION_TYPES: frozenset[str] = frozenset({"resume", "replay"})
RESOURCE_TYPES: frozenset[str] = frozenset({"clarification", "outbox_event"})

# Lifecycle states (mirrored by migration 035 chk_paa_state). No pending/rejected state: an approval
# is granted directly by an already-privileged Approver (there is no separate request step in this
# stage -- see contract §2.8, no public grant/revoke HTTP endpoint yet).
STATES: frozenset[str] = frozenset({"granted", "revoked", "consumed"})

# Who may grant/revoke a production approval -- the canonical "Approve / reject gated action"
# capability (docs/test/ai-team-work-rbac-blueprint.md §3), the SAME role pair as replay's Approver.
GRANTER_ROLES: frozenset[str] = frozenset({"reviewer_approver", "platform_admin"})

# Bounded, secret-free reason-code allowlist (never free text).
REASON_CODES: frozenset[str] = frozenset(
    {
        "ok",
        "granted",
        "rbac_denied",
        "cross_team_denied",
        "cross_project_denied",
        "unknown_action_type",
        "unknown_resource_type",
        "invalid_reference",
        "not_found",
        "already_revoked",
        "already_consumed",
        "expired",
        "stale_state",
        "wrong_action",
        "wrong_resource",
        "wrong_scope",
        "invalid_transition",
        "operator_revoked",
    }
)

MAX_APPROVAL_VALIDITY_SECONDS = 86400  # 24h -- same conservative bound as every other BE3 request.

_SAFE_AUDIT_KEYS: frozenset[str] = frozenset(
    {
        "event",
        "approval_id",
        "action_type",
        "resource_type",
        "resource_id",
        "team_id",
        "project_id",
        "actor_id",
        "actor_role",
        "state",
        "reason_code",
        "resource_state_version",
        "authorization_id",
        "idempotency_key",
        "occurred_at",
    }
)

_FORBIDDEN_VALUE_MARKERS = ("password", "secret", "token", "dsn=", "postgres://", "redis://")


def can_grant(role: str) -> bool:
    """Whether ROLE may grant/revoke a production approval. Canonical TASK_ROLES only."""
    return role in TASK_ROLES and role in GRANTER_ROLES


def assert_reason_code(code: str | None) -> str | None:
    if code is None:
        return None
    if code not in REASON_CODES:
        raise ValueError(f"unknown production-approval reason_code: {code}")
    return code


def project_state(row: dict[str, Any], *, now: Any) -> str:
    """The single authoritative state for a row, given the DB 'now' (statement_timestamp()).
    Precedence: consumed > revoked > expired > granted. `now` must be a DB-sourced timestamp."""
    if row.get("consumed_at") is not None:
        return "consumed"
    if row.get("revoked_at") is not None:
        return "revoked"
    if row.get("expires_at") is not None and row["expires_at"] <= now:
        return "expired"
    return "granted"


def build_production_approval_audit_payload(
    *,
    event: str,
    approval_id: str,
    action_type: str,
    resource_type: str,
    resource_id: str,
    actor_id: str,
    reason_code: str | None,
    state: str,
    team_id: str | None = None,
    project_id: str | None = None,
    actor_role: str | None = None,
    resource_state_version: str | None = None,
    authorization_id: str | None = None,
    idempotency_key: str | None = None,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Build a bounded, secret-free audit payload. NEVER carries approval decision content,
    rationale text, a token, or a credential -- only identifiers, state, and a bounded reason code
    (be3-r1-m1-production-approval-contract.md §2.6)."""
    raw: dict[str, Any] = {
        "event": event,
        "approval_id": approval_id,
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "reason_code": assert_reason_code(reason_code),
        "state": state,
        "team_id": team_id,
        "project_id": project_id,
        "resource_state_version": resource_state_version,
        "authorization_id": authorization_id,
        "idempotency_key": idempotency_key,
        "occurred_at": occurred_at,
    }
    payload = {k: v for k, v in raw.items() if v is not None}
    for key, value in payload.items():
        if key not in _SAFE_AUDIT_KEYS:
            raise ValueError(f"production-approval audit payload key not allowed: {key}")
        if isinstance(value, str):
            if len(value) > 500:
                raise ValueError(f"production-approval audit payload value too long: {key}")
            low = value.lower()
            if any(marker in low for marker in _FORBIDDEN_VALUE_MARKERS):
                raise ValueError(f"production-approval audit payload value looks unsafe: {key}")
    return payload
