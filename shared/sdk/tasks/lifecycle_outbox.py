"""Step 66C.4-BE1 -- disabled transactional-outbox foundation for clarification lifecycle.

This module is a DISABLED-BY-DEFAULT foundation. It is deliberately NOT imported or called
by any runtime producer (no answer/reminder/expiry/resume/audit/event path invokes it), and
BE1 wires up NO relay, NO scheduler, and NO background task. Its only callers are isolated
tests. Activating a producer cutover to this outbox is out of scope for BE1 and is gated by
the "BE1 Runtime Compatibility Gate" in the canonical contract source-of-truth record.

Design (canonical api-and-event-contract.md 11.3 / data-model-contract.md):
  * Insert is TRANSACTION-AWARE: it takes the caller's asyncpg connection and runs the
    INSERT inside the caller's transaction. It NEVER opens its own connection, NEVER commits,
    and NEVER closes the connection -- so a lifecycle state mutation and its outbox insert can
    commit atomically (both or neither) under the caller's transaction boundary.
  * Payload is minimal/safe JSONB: never a raw clarification question/answer body, never a
    secret/token/credential, never a full external channel payload.
  * Idempotency is enforced by the table's UNIQUE(idempotency_key); a duplicate insert raises
    asyncpg.UniqueViolationError, which the caller (a future relay/producer, not BE1) handles.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

# Keys that must never appear in an outbox payload: raw content or sensitive material.
PROHIBITED_PAYLOAD_KEYS = frozenset(
    {
        "question",
        "answer",
        "body",
        "message",
        "content",
        "text",
        "token",
        "secret",
        "password",
        "credential",
        "credentials",
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
    }
)

# Bounded payload size (defense in depth; the outbox is for minimal references, not blobs).
MAX_PAYLOAD_BYTES = 2000

ALLOWED_EVENT_TYPES = frozenset(
    {
        "clarification_reminder_sent",
        "clarification_expired",
        "clarification_resume_eligible",
        "clarification_resume_requested",
        "clarification_resume_authorized",
    }
)


def assert_safe_outbox_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Reject raw/sensitive payloads. Returns the validated payload (or {})."""
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("outbox payload must be a JSON object")
    for key in payload:
        if str(key).strip().lower() in PROHIBITED_PAYLOAD_KEYS:
            raise ValueError(f"outbox payload must not contain prohibited key: {key}")
    encoded = json.dumps(payload)
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("outbox payload exceeds the maximum safe size")
    return payload


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
    or close anything. In BE1 the only caller is an isolated test. A duplicate idempotency_key
    raises asyncpg.UniqueViolationError (surfaced to the caller unchanged).
    """
    safe_payload = assert_safe_outbox_payload(payload)
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"unknown lifecycle outbox event_type: {event_type}")
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


async def list_pending_lifecycle_outbox_events(
    conn: asyncpg.Connection, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Read-only helper for tests/review. Does NOT claim or mutate any row (no relay in BE1)."""
    rows = await conn.fetch(
        """
        SELECT * FROM clarification_lifecycle_outbox
        WHERE status='pending'
        ORDER BY created_at ASC
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
    for key in ("created_at", "published_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d
