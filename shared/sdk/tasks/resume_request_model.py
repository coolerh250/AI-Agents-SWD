"""Step 66C.4-BE3-B -- operator-controlled resume request model.

Pure definitions + safe projections + feature-gate readers for the resume_requests table
(migration 033). No I/O, no HTTP, no orchestrator call, no resume execution. Backs the
operator-controlled resume request/authorize/gated-execution flow in
be3-resume-replay-state-machine.md and be3-api-event-contract.md.

The durable authorization itself lives in authorization_model/authorization_repository (BE3-A);
this model covers the REQUEST entity that carries it plus the gated execution command shape.
"""

from __future__ import annotations

import os
from typing import Any

# Request lifecycle states (mirrored by migration 033 chk_rr_state).
REQUEST_STATES: frozenset[str] = frozenset(
    {
        "authorization_pending",
        "authorized",
        "execution_pending",
        "resumed",
        "rejected",
        "canceled",
        "failed",
        "expired",
    }
)

# States in which a resume request still holds the single active slot for its clarification.
ACTIVE_STATES: frozenset[str] = frozenset(
    {"authorization_pending", "authorized", "execution_pending"}
)

TERMINAL_STATES: frozenset[str] = REQUEST_STATES - ACTIVE_STATES

# operator_tasks.status values that make a task ineligible for resume (terminal / not-runnable).
TERMINAL_TASK_STATUSES: frozenset[str] = frozenset(
    {"canceled", "rejected", "archived", "failed", "accepted", "clarification_expired"}
)

# operator_clarification_requests.status values that block a resume request.
BLOCKING_CLARIFICATION_STATUSES: frozenset[str] = frozenset({"expired", "canceled"})

# Bounded, secret-free reason-code allowlist for resume request evidence (never free text).
REASON_CODES: frozenset[str] = frozenset(
    {
        "policy_allow",
        "policy_deny",
        "not_eligible",
        "clarification_not_answered",
        "resume_not_eligible",
        "clarification_blocked",
        "resource_terminal",
        "stale_state",
        "active_request_exists",
        "already_authorized",
        "already_rejected",
        "already_canceled",
        "already_resumed",
        "already_failed",
        "resource_not_found",
        "rbac_denied",
        "policy_authority_required",
        "production_approval_required",
        "feature_disabled",
        "command_gate_disabled",
        "operator_canceled",
        "operator_requested",
        "orchestrator_confirmed_resumed",
        "orchestrator_confirmed_failed",
        "invalid_transition",
        "conflict",
    }
)

# Result kinds returned to the API layer (support HTTP mapping without leaking existence).
RESULT_KINDS: frozenset[str] = frozenset(
    {
        "ok",
        "forbidden",
        "not_found_masked",
        "conflict",
        "not_eligible",
        "stale_state",
        "already_authorized",
        "already_rejected",
        "already_canceled",
        "production_approval_required",
        "feature_disabled",
        "command_gate_disabled",
        "invalid_transition",
    }
)


def assert_reason_code(code: str | None) -> str | None:
    if code is None:
        return None
    if code not in REASON_CODES:
        raise ValueError(f"unknown resume reason_code: {code}")
    return code


# ---- Feature gates (server-side only; NEVER read from a request body/query/header) --------------


def resume_api_enabled() -> bool:
    """Whether the resume request API may perform ANY DB mutation. Disabled-by-default, fail-closed:
    only the exact string 'true' enables it. Read from the process environment ONLY."""
    return os.environ.get("BE3_RESUME_API_ENABLED", "false").strip().lower() == "true"


def resume_command_enabled() -> bool:
    """Whether the internal execution-preparation path may consume an authorization and create the
    durable resume.execution_requested command. Disabled-by-default, fail-closed. Environment ONLY.
    """
    return os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false").strip().lower() == "true"


# ---- Authoritative projections -----------------------------------------------------------------


def resource_state_version(clarification_row: dict[str, Any]) -> str:
    """A deterministic version string for the clarification the resume is bound to.

    Composed from the clarification's authoritative, stable fields; if the clarification's state
    changes (e.g. it is later expired/canceled or re-answered) the version changes and any
    outstanding authorization becomes stale (consume aborts, no side effect)."""
    status = clarification_row.get("status")
    answer_ref = clarification_row.get("answer_message_id")
    return f"{status}:{answer_ref if answer_ref is not None else '-'}"


def project_state(row: dict[str, Any]) -> str:
    """The authoritative state of a resume request row (already materialised in the `state`
    column; this is the single accessor so callers never re-derive it inconsistently)."""
    state = row.get("state")
    if state not in REQUEST_STATES:
        raise ValueError(f"unknown resume request state: {state}")
    return str(state)


# ---- Safe command payload ----------------------------------------------------------------------

# Substrings that must never appear in a command payload value (defense in depth).
_FORBIDDEN_VALUE_MARKERS = ("password", "secret", "token", "dsn=", "postgres://", "redis://")

# Keys allowed in the resume.execution_requested command payload. NEVER a raw clarification/answer
# body, never a secret. All identifiers only.
_SAFE_COMMAND_KEYS: frozenset[str] = frozenset(
    {"resume_request_id", "authorization_id", "resource_state_version"}
)


def build_resume_command_payload(
    *,
    resume_request_id: str,
    authorization_id: str,
    resource_state_version: str,
) -> dict[str, Any]:
    """Build the bounded, secret-free payload for the durable resume.execution_requested command.

    Carries identifiers only. Rejects any value that looks like a secret/DSN or is over-long.
    The command NEVER carries a raw clarification question/answer body."""
    payload = {
        "resume_request_id": resume_request_id,
        "authorization_id": authorization_id,
        "resource_state_version": resource_state_version,
    }
    for key, value in payload.items():
        if key not in _SAFE_COMMAND_KEYS:
            raise ValueError(f"resume command payload key not allowed: {key}")
        if not isinstance(value, str) or not value:
            raise ValueError(f"resume command payload value must be a non-empty string: {key}")
        if len(value) > 200:
            raise ValueError(f"resume command payload value too long: {key}")
        low = value.lower()
        if any(marker in low for marker in _FORBIDDEN_VALUE_MARKERS):
            raise ValueError(f"resume command payload value looks unsafe: {key}")
    return payload
