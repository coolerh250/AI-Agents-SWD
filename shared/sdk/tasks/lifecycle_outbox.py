"""Step 66C.4-BE1 -- disabled transactional-outbox foundation for clarification lifecycle.

Step 66C.4-BE1-R1 extends this module with the durability columns required by the canonical
contract (available_at / dead_at / last_error), a positive-allowlist payload guard, and pure
state-mapping helpers for retry / dead / operator-replay semantics.

This module is a DISABLED-BY-DEFAULT foundation. It is deliberately NOT imported or called
by any runtime producer (no answer/reminder/expiry/resume/audit/event path invokes it), and
neither BE1 nor BE1-R1 wires up a relay, a scheduler, a claim loop, or a background task. Its
only callers are isolated tests. Activating a producer cutover to this outbox is out of scope
and is gated by the "BE1 Runtime Compatibility Gate" in the canonical source-of-truth record.

Design (canonical api-and-event-contract.md 11.3 / data-model-contract.md):
  * Insert is TRANSACTION-AWARE: it takes the caller's asyncpg connection and runs the
    INSERT inside the caller's transaction. It NEVER opens its own connection, NEVER commits,
    and NEVER closes the connection -- so a lifecycle state mutation and its outbox insert can
    commit atomically (both or neither) under the caller's transaction boundary.
  * Payload is minimal/safe JSONB, enforced by a POSITIVE per-event-type key allowlist and a
    scalar-only value rule: never a raw clarification question/answer body, never a
    secret/token/credential, never a nested structure, never a full external channel payload.
  * Durability: available_at persists the retry schedule, dead_at records terminal death, and
    last_error carries a bounded, secret-free failure reason. Without a PERSISTED backoff the
    binding 11.3 failure modes 1 ("no loss during an outage") and 7 ("bounded retries end in
    dead") are mutually unsatisfiable -- Step 66C.4-BE1-R blocking finding B-2.
  * Idempotency is enforced by the table's UNIQUE(idempotency_key); a duplicate insert raises
    asyncpg.UniqueViolationError, which the caller (a future relay/producer) handles.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

# Bounded payload size (defense in depth; the outbox is for minimal references, not blobs).
MAX_PAYLOAD_BYTES = 2000

# Bounded scalar string length inside a payload value.
MAX_PAYLOAD_VALUE_CHARS = 500

# Bounded last_error length. Mirrored by the chk_clo_last_error_bounded DB CHECK constraint.
MAX_LAST_ERROR_CHARS = 500

# Keys carried by dedicated outbox COLUMNS. They must not be duplicated into the payload.
COLUMN_OWNED_PAYLOAD_KEYS = frozenset(
    {"clarification_id", "task_id", "event_type", "idempotency_key", "status", "attempts"}
)

# Keys every lifecycle event may carry (canonical api-and-event-contract.md event payload).
_COMMON_PAYLOAD_KEYS = frozenset({"event_id", "occurred_at", "reason"})

# POSITIVE allowlist: event_type -> the exact set of payload keys that event may carry.
# Anything not listed here is rejected. This replaces the Step 66C.4-BE1 deny-list guard, which
# the Step 66C.4-BE1-R security review (finding M-1) showed could be bypassed by nesting
# ({'meta': {'answer': ...}}) or by a near-miss key name ('answer_body', 'question_text').
# Names follow the canonical event naming in api-and-event-contract.md 11.2.
ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE: dict[str, frozenset[str]] = {
    "clarification.reminder_due": _COMMON_PAYLOAD_KEYS | {"reminder_at"},
    "clarification.reminder_recorded": _COMMON_PAYLOAD_KEYS | {"reminder_at", "reminder_sent_at"},
    "clarification.expired": _COMMON_PAYLOAD_KEYS | {"due_at", "expired_at"},
    "clarification.resume_eligible": _COMMON_PAYLOAD_KEYS | {"resume_eligible_at"},
    "clarification.resume_requested": _COMMON_PAYLOAD_KEYS
    | {"resume_requested_at", "resume_requested_by"},
    "clarification.resume_authorized": _COMMON_PAYLOAD_KEYS | {"resume_authorized_at"},
    # Step 66C.4-BE3-B resume request AUDIT-stream events (durable outbox evidence; identifiers
    # only, never a raw clarification/answer body, never a secret). Each is written in the SAME
    # transaction as its resume_requests state change.
    "resume.requested": _COMMON_PAYLOAD_KEYS
    | {"resume_request_id", "resource_state_version", "resume_requested_by"},
    "resume.authorized": _COMMON_PAYLOAD_KEYS | {"resume_request_id", "authorization_id"},
    "resume.rejected": _COMMON_PAYLOAD_KEYS | {"resume_request_id"},
    "resume.canceled": _COMMON_PAYLOAD_KEYS | {"resume_request_id"},
    "resume.resumed": _COMMON_PAYLOAD_KEYS | {"resume_request_id", "command_id"},
    "resume.failed": _COMMON_PAYLOAD_KEYS | {"resume_request_id", "command_id"},
    # The durable resume execution COMMAND (single destination -> orchestrator). GATED/DISABLED-BY-
    # DEFAULT: BE3-B creates the row only and does NOT publish it or start a consumer.
    "resume.execution_requested": _COMMON_PAYLOAD_KEYS
    | {"resume_request_id", "authorization_id", "resource_state_version"},
    # Step 66C.4-BE3-C dead-event replay AUDIT-stream evidence (identifiers only, never a raw
    # outbox payload/clarification/answer body, never a secret). Each is written in the SAME
    # transaction as its replay_requests state change. There is no replay "command" destination --
    # replay execution is a synchronous internal DB mutation (dead -> pending) on the ORIGINAL
    # business-event row itself; these rows are audit evidence ABOUT that mutation, never a second
    # copy of the business event.
    "replay.requested": _COMMON_PAYLOAD_KEYS
    | {"replay_request_id", "outbox_event_id", "destination"},
    "replay.authorized": _COMMON_PAYLOAD_KEYS | {"replay_request_id", "authorization_id"},
    "replay.rejected": _COMMON_PAYLOAD_KEYS | {"replay_request_id"},
    "replay.canceled": _COMMON_PAYLOAD_KEYS | {"replay_request_id"},
    "replay.execution_blocked": _COMMON_PAYLOAD_KEYS | {"replay_request_id"},
    "replay.executed": _COMMON_PAYLOAD_KEYS | {"replay_request_id", "outbox_event_id"},
    "replay.failed": _COMMON_PAYLOAD_KEYS | {"replay_request_id"},
}

ALLOWED_EVENT_TYPES = frozenset(ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE)

# Durable destination classification (Step 66C.4-BE3-B-C1). One outbox row -> exactly ONE durable
# destination, decided by event_type -- never guessed, never left to a relay's discretion.
# 'audit' rows are the ONLY rows the existing BE2 audit relay (ClarificationOutboxRelay) may
# claim/publish, via publish_audit_event, to the canonical stream.audit destination. Its downstream
# audit-worker projects stream.audit into audit_logs -- that is the ONE durable destination with a
# downstream projection for every audit-classified event type; no row is ever fanned out to two
# destinations. 'orchestrator_command' rows (currently only resume.execution_requested) are for a
# SEPARATE, DEDICATED orchestrator-command consumer that no stage has built or activated yet -- the
# existing audit relay's claim query explicitly excludes them (audit_relay_claimable_event_types
# below), so it can never claim one, publish it to the wrong stream, or mark it 'published' when it
# never reached its real destination. Today these rows simply accumulate as 'pending' (in practice
# zero, since BE3_RESUME_COMMAND_ENABLED defaults false) until a real command consumer exists and
# the runtime activation gate (be3-runtime-activation-gate.md) is separately satisfied; this module
# builds NO such consumer, starts NO loop, and activates nothing.
DESTINATION_AUDIT = "audit"
DESTINATION_ORCHESTRATOR_COMMAND = "orchestrator_command"

EVENT_DESTINATIONS: dict[str, str] = {
    "clarification.reminder_due": DESTINATION_AUDIT,
    "clarification.reminder_recorded": DESTINATION_AUDIT,
    "clarification.expired": DESTINATION_AUDIT,
    "clarification.resume_eligible": DESTINATION_AUDIT,
    "clarification.resume_requested": DESTINATION_AUDIT,
    "clarification.resume_authorized": DESTINATION_AUDIT,
    "resume.requested": DESTINATION_AUDIT,
    "resume.authorized": DESTINATION_AUDIT,
    "resume.rejected": DESTINATION_AUDIT,
    "resume.canceled": DESTINATION_AUDIT,
    "resume.resumed": DESTINATION_AUDIT,
    "resume.failed": DESTINATION_AUDIT,
    "resume.execution_requested": DESTINATION_ORCHESTRATOR_COMMAND,
    "replay.requested": DESTINATION_AUDIT,
    "replay.authorized": DESTINATION_AUDIT,
    "replay.rejected": DESTINATION_AUDIT,
    "replay.canceled": DESTINATION_AUDIT,
    "replay.execution_blocked": DESTINATION_AUDIT,
    "replay.executed": DESTINATION_AUDIT,
    "replay.failed": DESTINATION_AUDIT,
}

# Structural guarantee (import-time, not just a test): every allowlisted event_type has EXACTLY one
# destination classification. A new event type added to ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE without
# a matching EVENT_DESTINATIONS entry fails the module import outright -- there is no unclassified/
# NULL/"unknown" destination that could silently fall through to the audit relay.
assert (
    set(EVENT_DESTINATIONS) == ALLOWED_EVENT_TYPES
), "every lifecycle_outbox event_type must have an explicit destination classification"


def destination_for_event_type(event_type: str) -> str:
    """The single durable destination for an event_type. Raises for anything not on the allowlist
    -- there is no guessed/default destination for an unknown event_type."""
    if event_type not in EVENT_DESTINATIONS:
        raise ValueError(f"unknown lifecycle outbox event_type: {event_type}")
    return EVENT_DESTINATIONS[event_type]


def audit_relay_claimable_event_types() -> frozenset[str]:
    """The event types the AUDIT relay (ClarificationOutboxRelay) may claim/publish. Derived from
    EVENT_DESTINATIONS so it can never include an orchestrator-command (or any future non-audit)
    row -- membership is fail-closed by construction, not by a denylist that must be kept in sync.
    """
    return frozenset(t for t, d in EVENT_DESTINATIONS.items() if d == DESTINATION_AUDIT)


async def count_pending_by_destination(conn: asyncpg.Connection, destination: str) -> int:
    """Read-only visibility helper (NOT a consumer, NOT a claim): count pending rows for a
    destination. Performs no claim, no publish, no state mutation -- for tests/ops visibility of
    orchestrator-command backlog while no dedicated consumer exists."""
    event_types = [t for t, d in EVENT_DESTINATIONS.items() if d == destination]
    if not event_types:
        return 0
    return await conn.fetchval(
        "SELECT count(*) FROM clarification_lifecycle_outbox "
        "WHERE status='pending' AND event_type = ANY($1::text[])",
        event_types,
    )


# Persisted backoff schedule (seconds). Every entry is REACHED: after the Nth publish attempt
# fails the row waits RETRY_BACKOFF_SECONDS[N-1] before the next attempt. Step 66C.4-BE2-R1 PO
# decision 1.2 makes the semantics exact (the previous code never reached the 3600 entry):
#   attempt 1 fails -> attempts=1, +30s     attempt 2 fails -> attempts=2, +120s
#   attempt 3 fails -> attempts=3, +600s     attempt 4 fails -> attempts=4, +3600s
#   attempt 5 fails -> attempts=5, dead
# So there are MAX_RETRIES=4 scheduled retries across MAX_PUBLISH_ATTEMPTS=5 total attempts.
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (30, 120, 600, 3600)
MAX_RETRIES = len(RETRY_BACKOFF_SECONDS)  # 4 scheduled retries (each backoff is reached)
MAX_PUBLISH_ATTEMPTS = MAX_RETRIES + 1  # 5 total attempts; the 5th failure is terminal (dead)


def assert_safe_last_error(text: str | None) -> str | None:
    """Reject an unbounded failure reason. Returns the validated bounded reason (or None).

    The caller is responsible for passing a reason class/label rather than a raw exception
    payload; this boundary enforces only the bound, which the DB CHECK enforces again.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("outbox last_error must be a string")
    if len(text) > MAX_LAST_ERROR_CHARS:
        raise ValueError(
            f"outbox last_error exceeds the maximum safe length of {MAX_LAST_ERROR_CHARS}"
        )
    return text


def assert_safe_outbox_payload(
    payload: dict[str, Any] | None, *, event_type: str
) -> dict[str, Any]:
    """Validate a payload against the POSITIVE allowlist for `event_type`.

    Rejects: an unknown event type, an unknown key, a key owned by a dedicated column, any
    nested dict or list, any non-scalar value, an over-long string value, and an oversized
    payload. Error messages name the offending KEY only, never the value.
    """
    if event_type not in ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE:
        raise ValueError(f"unknown lifecycle outbox event_type: {event_type}")
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("outbox payload must be a JSON object")

    allowed = ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE[event_type]
    for raw_key, value in payload.items():
        if not isinstance(raw_key, str):
            raise ValueError("outbox payload keys must be strings")
        key = raw_key.strip().lower()
        if key in COLUMN_OWNED_PAYLOAD_KEYS:
            raise ValueError(f"outbox payload must not duplicate the column-owned key: {raw_key}")
        if key not in allowed:
            raise ValueError(f"outbox payload key is not allowed for {event_type}: {raw_key}")
        _assert_safe_payload_value(raw_key, value)

    encoded = json.dumps(payload)
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("outbox payload exceeds the maximum safe size")
    return payload


def _assert_safe_payload_value(key: str, value: Any) -> None:
    """Only bounded scalars are allowed. Nesting is how a raw body would smuggle itself in."""
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, str):
        if len(value) > MAX_PAYLOAD_VALUE_CHARS:
            raise ValueError(f"outbox payload value exceeds the maximum safe length: {key}")
        return
    raise ValueError(f"outbox payload value must be a bounded scalar: {key}")


def plan_retry_state(*, attempts: int, error: str | None) -> dict[str, Any]:
    """Pure mapping: given the attempts already made, describe the next persisted state.

    This is the MODEL for the retry semantics in data-model-contract.md; it performs no I/O and
    starts no loop. A relay (BE2, not authorized here) would apply the returned values to the row.

    `backoff_seconds` is how far available_at must be pushed forward from statement time; it is
    None for a terminal transition.
    """
    if attempts < 0:
        raise ValueError("attempts must not be negative")
    next_attempts = attempts + 1
    bounded_error = assert_safe_last_error(error)
    # Dead only after the MAX_PUBLISH_ATTEMPTS-th attempt fails. Every failure -- transient or
    # poison -- consumes exactly one attempt; there is no immediate-dead classification, so a
    # persistently failing (poison) row cannot tight-loop, it dies after the bounded schedule.
    if next_attempts >= MAX_PUBLISH_ATTEMPTS:
        return {
            "status": "dead",
            "attempts": next_attempts,
            "backoff_seconds": None,
            "last_error": bounded_error,
            "set_dead_at": True,
        }
    return {
        "status": "pending",
        "attempts": next_attempts,
        "backoff_seconds": RETRY_BACKOFF_SECONDS[next_attempts - 1],
        "last_error": bounded_error,
        "set_dead_at": False,
    }


def plan_replay_state(*, attempts: int) -> dict[str, Any]:
    """Pure mapping for the operator replay transition dead -> pending.

    id and idempotency_key are preserved by the caller (they are not touched here). attempts is
    deliberately NOT reset, so the full delivery-attempt history survives as evidence. No replay
    endpoint and no runtime replay path exist in BE1/BE1-R1 -- this is the contract's semantics
    made executable for tests.
    """
    return {
        "status": "pending",
        "attempts": attempts,
        "reset_available_at": True,
        "clear_dead_at": True,
        "clear_last_error": True,
    }


async def insert_lifecycle_outbox_event(
    conn: asyncpg.Connection,
    *,
    clarification_id: str,
    task_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert one outbox row within the CALLER'S transaction.

    The connection/transaction is owned by the caller: this function does not begin, commit,
    or close anything. The only callers are isolated tests. A duplicate idempotency_key raises
    asyncpg.UniqueViolationError (surfaced to the caller unchanged). available_at defaults to
    PostgreSQL statement time, so the row is immediately claim-eligible by a future relay.
    """
    safe_payload = assert_safe_outbox_payload(payload, event_type=event_type)
    row = await conn.fetchrow(
        """
        INSERT INTO clarification_lifecycle_outbox
          (clarification_id, task_id, event_type, idempotency_key, payload)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING *
        """,
        clarification_id,
        task_id,
        event_type,
        idempotency_key,
        json.dumps(safe_payload),
    )
    return _outbox_row(row)


async def get_lifecycle_outbox_event(
    conn: asyncpg.Connection, event_id: str
) -> dict[str, Any] | None:
    """Read-only helper for tests/review. Uses the caller's connection."""
    row = await conn.fetchrow(
        "SELECT * FROM clarification_lifecycle_outbox WHERE id=$1",
        event_id,
    )
    return _outbox_row(row) if row else None


async def list_claimable_lifecycle_outbox_events(
    conn: asyncpg.Connection, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Read-only helper for tests/review: rows a relay would be ELIGIBLE to claim right now.

    Honors the persisted backoff schedule (available_at <= statement_timestamp()). This does NOT
    claim, lock, or mutate any row, and it is not a relay: there is no loop, no retry, and no
    publication. It exists so tests can assert that a deferred row is correctly not yet eligible.
    """
    rows = await conn.fetch(
        """
        SELECT * FROM clarification_lifecycle_outbox
        WHERE status='pending' AND available_at <= statement_timestamp()
        ORDER BY available_at ASC, created_at ASC
        LIMIT $1
        """,
        limit,
    )
    return [_outbox_row(r) for r in rows]


def _outbox_row(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    for key in ("id", "clarification_id", "task_id"):
        if d.get(key) is not None:
            d[key] = str(d[key])
    for key in ("created_at", "available_at", "published_at", "dead_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d
