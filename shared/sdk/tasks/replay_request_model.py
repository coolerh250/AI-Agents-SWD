"""Step 66C.4-BE3-C -- authorized dead-event replay request model.

Pure definitions + safe projections + feature-gate readers for the replay_requests table
(migration 034). No I/O, no HTTP, no dead-outbox replay execution, no scheduler. Backs the
two-person dead-event replay request/authorize/gated-execution flow in
be3-resume-replay-state-machine.md and be3-api-event-contract.md.

The durable authorization itself lives in authorization_model/authorization_repository (BE3-A, reused
unchanged with action_type='replay'); this model covers the REQUEST entity plus replay-specific
eligibility/rate-limit/readiness/audit-payload concerns.
"""

from __future__ import annotations

import os
from typing import Any

from shared.sdk.tasks.lifecycle_outbox import DESTINATION_AUDIT, DESTINATION_ORCHESTRATOR_COMMAND

# Request lifecycle states (mirrored by migration 034 chk_rpr_state).
REQUEST_STATES: frozenset[str] = frozenset(
    {
        "authorization_pending",
        "authorized",
        "executed",
        "rejected",
        "canceled",
        "expired",
        "failed",
    }
)

# States in which a replay request still holds the single active slot for its outbox event.
ACTIVE_STATES: frozenset[str] = frozenset({"authorization_pending", "authorized"})
TERMINAL_STATES: frozenset[str] = REQUEST_STATES - ACTIVE_STATES

# Destination readiness kinds (be3-b-c1-authority-routing-alignment-record.md classification).
READINESS_READY = "ready"
READINESS_NOT_CONFIGURED = "not_configured"
READINESS_UNHEALTHY = "unhealthy"
READINESS_DISABLED = "disabled"
READINESS_UNKNOWN_DESTINATION = "unknown_destination"
READINESS_KINDS: frozenset[str] = frozenset(
    {
        READINESS_READY,
        READINESS_NOT_CONFIGURED,
        READINESS_UNHEALTHY,
        READINESS_DISABLED,
        READINESS_UNKNOWN_DESTINATION,
    }
)

# Bounded, secret-free reason-code allowlist for replay request evidence (never free text).
REASON_CODES: frozenset[str] = frozenset(
    {
        "policy_allow",
        "policy_deny",
        "not_eligible",
        "not_dead",
        "already_published",
        "unknown_destination",
        "unknown_event_type",
        "active_request_exists",
        "already_authorized",
        "already_rejected",
        "already_canceled",
        "already_executed",
        "resource_not_found",
        "rbac_denied",
        "requester_cannot_approve",
        "two_person_required",
        "destination_unavailable",
        "production_approval_required",
        "rate_limited",
        "feature_disabled",
        "execution_gate_disabled",
        "stale_state",
        "invalid_transition",
        "conflict",
        "operator_requested",
        "operator_canceled",
    }
)

MAX_RATE_LIMIT_WINDOW_HOURS = 24 * 7  # one week: a sane outer bound on a configurable window


def assert_reason_code(code: str | None) -> str | None:
    if code is None:
        return None
    if code not in REASON_CODES:
        raise ValueError(f"unknown replay reason_code: {code}")
    return code


# ---- Feature gates (server-side only; NEVER read from a request body/query/header) --------------


def replay_api_enabled() -> bool:
    """Whether the replay request API may perform ANY DB mutation. Disabled-by-default,
    fail-closed: only the exact string 'true' enables it. Environment ONLY."""
    return os.environ.get("BE3_REPLAY_API_ENABLED", "false").strip().lower() == "true"


def replay_execution_enabled() -> bool:
    """Whether the internal execution path may consume an authorization and requeue the dead
    outbox row via the internal adapter. Disabled-by-default, fail-closed. Environment ONLY."""
    return os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false").strip().lower() == "true"


# ---- Rate-limit policy (server-side only; bounded, validated, fail-closed on invalid config) ----


def _bounded_int_env(name: str, *, default: int, minimum: int, maximum: int) -> int:
    """Read a bounded positive integer from the environment. Fail-closed: an unparsable or
    out-of-range value raises rather than silently clamping or falling back."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc
    if not (minimum <= value <= maximum):
        raise ValueError(f"{name} must be within [{minimum}, {maximum}], got: {value}")
    return value


def max_successful_replays_per_event() -> int:
    """Conservative server-side default: 3 successful manual replays per event. Not overridable by
    Platform Administrator role at the policy layer -- this is a hard safety cap; raising it is a
    separate, explicit, audited product decision (a new env value deployed by an operator)."""
    return _bounded_int_env(
        "BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", default=3, minimum=1, maximum=100
    )


def rate_limit_window_hours() -> int:
    """Conservative server-side default: a 24-hour rolling window."""
    return _bounded_int_env(
        "BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS",
        default=24,
        minimum=1,
        maximum=MAX_RATE_LIMIT_WINDOW_HOURS,
    )


def max_requests_per_actor_per_window() -> int:
    """Conservative server-side default: bounded requests per actor per rolling window (replay
    storm prevention independent of the per-event cap)."""
    return _bounded_int_env(
        "BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", default=10, minimum=1, maximum=1000
    )


# ---- Destination readiness (Step 66C.4-BE3-C) ---------------------------------------------------


def default_destination_readiness(destination: str) -> str:
    """The DEFAULT (no override) destination-readiness provider. Always reports the destination as
    NOT ready in any real deployment of this codebase, because neither destination has an activated
    consumer in ANY shared runtime:
      - 'audit': the BE2 audit relay exists but is NOT ACTIVATED anywhere (disabled-by-default
        foundation, per be2-*-record.md / be1-source-of-truth-record.md).
      - 'orchestrator_command': no consumer has been built at all (BE3-B-C1 destination routing
        classification, not yet an activation).
    An unrecognized destination is READINESS_UNKNOWN_DESTINATION (fail-closed). Tests that need to
    exercise the success path inject an explicit STUB readiness provider (never this default) --
    this function itself never claims a real consumer exists."""
    if destination == DESTINATION_AUDIT:
        return READINESS_NOT_CONFIGURED
    if destination == DESTINATION_ORCHESTRATOR_COMMAND:
        return READINESS_NOT_CONFIGURED
    return READINESS_UNKNOWN_DESTINATION


# ---- Authoritative projections -----------------------------------------------------------------


def dead_episode_state_version(*, dead_at: Any, attempts: int) -> str:
    """A deterministic version string for 'this exact dead episode' of an outbox row.

    dead_at is set exactly once per pending->dead transition (never touched while pending, cleared
    to NULL only on replay) and attempts is frozen the moment a row goes dead, so this composite
    uniquely identifies the episode without a new column. If the episode changes (the row is
    replayed and later dies again), the version changes and a stale authorization/request bound to
    the OLD episode is rejected (no side effect)."""
    if dead_at is None:
        raise ValueError("dead_episode_state_version requires a non-null dead_at")
    return f"{dead_at.isoformat()}:{attempts}"


def project_state(row: dict[str, Any]) -> str:
    """The authoritative state of a replay request row (already materialised in the `state`
    column; the single accessor so callers never re-derive it inconsistently)."""
    state = row.get("state")
    if state not in REQUEST_STATES:
        raise ValueError(f"unknown replay request state: {state}")
    return str(state)


# ---- Safe audit payload ------------------------------------------------------------------------

_FORBIDDEN_VALUE_MARKERS = ("password", "secret", "token", "dsn=", "postgres://", "redis://")

_SAFE_AUDIT_KEYS: frozenset[str] = frozenset(
    {
        "event",
        "replay_request_id",
        "authorization_id",
        "outbox_event_id",
        "event_type",
        "destination",
        "team_id",
        "project_id",
        "actor_id",
        "actor_role",
        "reason_code",
        "state",
        "resource_state_version",
        "attempts",
        "idempotency_key",
        "occurred_at",
    }
)


def build_replay_audit_payload(**fields: Any) -> dict[str, Any]:
    """Build a bounded, secret-free audit payload for a replay evidence event. Carries identifiers
    and bounded reason codes only -- NEVER a raw outbox payload, clarification/answer body, secret,
    or token."""
    payload = {k: v for k, v in fields.items() if v is not None}
    for key, value in payload.items():
        if key not in _SAFE_AUDIT_KEYS:
            raise ValueError(f"replay audit payload key not allowed: {key}")
        if isinstance(value, str):
            if len(value) > 500:
                raise ValueError(f"replay audit payload value too long: {key}")
            low = value.lower()
            if any(marker in low for marker in _FORBIDDEN_VALUE_MARKERS):
                raise ValueError(f"replay audit payload value looks unsafe: {key}")
    return payload
