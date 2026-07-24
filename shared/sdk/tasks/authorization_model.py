"""Step 66C.4-BE3-A -- durable resume/replay authorization model.

Pure definitions + safe projections for the resume_replay_authorizations table (migration 032).
No I/O, no HTTP, no resume/replay execution, no dead-outbox replay adapter call. Backs the operator-controlled resume
and authorized dead-event replay AUTHORIZATION contract (be3-api-event-contract.md). Consuming an
authorization is a durable single-use CAS; it does NOT itself execute resume or replay.
"""

from __future__ import annotations

from typing import Any

# Action / decision / policy allowlists (mirrored by migration 032 CHECK constraints).
ACTION_TYPES: frozenset[str] = frozenset({"resume", "replay"})
RESOURCE_TYPES: frozenset[str] = frozenset({"clarification", "outbox_event"})
DECISIONS: frozenset[str] = frozenset({"pending", "authorized", "rejected", "canceled"})
POLICY_RESULTS: frozenset[str] = frozenset({"allow", "deny", "not_applicable"})

# The single authoritative state projection the repository exposes to callers.
STATES: frozenset[str] = frozenset(
    {"pending", "authorized", "rejected", "canceled", "expired", "revoked", "consumed"}
)

# Bounded, secret-free reason-code allowlist (never free text). Decision + result-model reasons.
REASON_CODES: frozenset[str] = frozenset(
    {
        "ok",
        "policy_allow",
        "policy_deny",
        "rbac_denied",
        "unknown_action_type",
        "cross_team_denied",
        "cross_project_denied",
        "resource_not_found",
        "two_person_required",
        "service_identity_cannot_request",
        "service_identity_cannot_decide",
        "production_approval_required",
        "invalid_transition",
        "already_decided",
        "already_consumed",
        "already_revoked",
        "expired",
        "stale_state",
        "conflict",
        "revoked",
        "operator_revoked",
        "operator_canceled",
    }
)

# API-independent result kinds (support a later HTTP mapping without leaking existence).
RESULT_KINDS: frozenset[str] = frozenset(
    {
        "ok",
        "forbidden",
        "not_found_masked",
        "conflict",
        "expired",
        "stale_state",
        "already_decided",
        "already_consumed",
        "revoked",
        "production_approval_required",
        "invalid_transition",
    }
)

MAX_REASON_CODE_CHARS = 64
MAX_ACTOR_CHARS = 128

# Keys allowed in a safe audit payload. Anything else is rejected -- never raw content or a secret.
_SAFE_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "authorization_id",
        "action_type",
        "resource_type",
        "resource_id",
        "team_id",
        "project_id",
        "request_id",
        "actor_id",
        "actor_role",
        "decision",
        "state",
        "reason_code",
        "policy_result",
        "policy_version",
        "resource_state_version",
        "production_effect",
        "event",
        "occurred_at",
        "idempotency_key",
    }
)

# Substrings that must never appear in an audit payload value (defense in depth).
_FORBIDDEN_VALUE_MARKERS = ("password", "secret", "token", "dsn=", "postgres://", "redis://")


def assert_reason_code(code: str | None) -> str | None:
    """Reject a reason code that is not on the bounded allowlist."""
    if code is None:
        return None
    if code not in REASON_CODES:
        raise ValueError(f"unknown authorization reason_code: {code}")
    return code


def project_state(row: dict[str, Any], *, now: Any) -> str:
    """The single authoritative state for a row, given the DB 'now' (statement_timestamp()).

    Precedence: consumed > revoked > expired > rejected > canceled > authorized > pending. `now`
    must be a DB-sourced timestamp (never a Python local clock) so validity is DB-authoritative.
    """
    if row.get("consumed_at") is not None:
        return "consumed"
    if row.get("revoked_at") is not None:
        return "revoked"
    decision = row.get("decision")
    if row.get("expired_at") is not None:
        return "expired"
    if decision in ("pending", "authorized") and row.get("expires_at") is not None:
        if row["expires_at"] <= now:
            return "expired"
    if decision == "rejected":
        return "rejected"
    if decision == "canceled":
        return "canceled"
    if decision == "authorized":
        return "authorized"
    return "pending"


def build_audit_payload(
    *,
    event: str,
    authorization_id: str,
    action_type: str,
    resource_type: str,
    resource_id: str,
    actor_id: str,
    reason_code: str | None,
    state: str,
    team_id: str | None = None,
    project_id: str | None = None,
    request_id: str | None = None,
    actor_role: str | None = None,
    policy_result: str | None = None,
    policy_version: str | None = None,
    resource_state_version: str | None = None,
    production_effect: bool | None = None,
    idempotency_key: str | None = None,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Build a bounded, secret-free audit payload. Rejects any value that looks like a secret/DSN
    or an over-long string. NEVER carries a raw clarification/answer/replay body."""
    raw: dict[str, Any] = {
        "event": event,
        "authorization_id": authorization_id,
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "reason_code": assert_reason_code(reason_code),
        "state": state,
        "team_id": team_id,
        "project_id": project_id,
        "request_id": request_id,
        "policy_result": policy_result,
        "policy_version": policy_version,
        "resource_state_version": resource_state_version,
        "production_effect": production_effect,
        "idempotency_key": idempotency_key,
        "occurred_at": occurred_at,
    }
    payload = {k: v for k, v in raw.items() if v is not None}
    for key, value in payload.items():
        if key not in _SAFE_PAYLOAD_KEYS:
            raise ValueError(f"audit payload key not allowed: {key}")
        if isinstance(value, str):
            if len(value) > 500:
                raise ValueError(f"audit payload value too long: {key}")
            low = value.lower()
            if any(marker in low for marker in _FORBIDDEN_VALUE_MARKERS):
                raise ValueError(f"audit payload value looks unsafe: {key}")
    return payload
