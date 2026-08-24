"""Step AT-M3.1 -- in-memory fake ReasoningInvocationStore for unit tests.

Implements the same async surface ReasoningService uses (try_begin_invocation /
complete_invocation), backed by a dict keyed on ``correlation_id``. No DB, no asyncpg. Follows the
existing ``tests/agent_team_fakes.py`` convention.

Mirrors the real store's ownership semantics: ``try_begin_invocation`` returns ``owned=True`` only
for the first caller to claim a given ``correlation_id`` (a 'started' row is inserted immediately,
matching the real store's INSERT-before-provider-call ordering); every later caller for the same
correlation_id gets ``owned=False`` and the row's CURRENT state. ``complete_invocation`` only
transitions a row that is still 'started' -- exactly like the real store's
``UPDATE ... WHERE status='started'`` guard -- and also runs the SAME
``sanitize_failure_reason`` defense-in-depth the real store applies, so a test exercising the fake
observes identical failure_reason sanitization behaviour.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from shared.sdk.agent_reasoning.models import sanitize_failure_reason


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryReasoningInvocationStore:
    def __init__(self) -> None:
        self.rows_by_correlation: dict[str, dict[str, Any]] = {}
        self.rows_by_invocation: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []

    async def try_begin_invocation(self, data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        correlation_id = str(data["correlation_id"])
        existing = self.rows_by_correlation.get(correlation_id)
        if existing is not None:
            return False, dict(existing)
        row = {
            "invocation_id": str(uuid.uuid4()),
            "project_id": data.get("project_id"),
            "thread_id": data.get("thread_id"),
            "requested_by_principal_id": data.get("requested_by_principal_id"),
            "reasoning_verb": data["reasoning_verb"],
            "requested_provider_name": data["requested_provider_name"],
            "provider_mode": data["provider_mode"],
            "model_name": data.get("model_name"),
            "round_number": data.get("round_number", 1),
            "status": "started",
            "failure_category": None,
            "failure_reason": None,
            "outcome_ref": None,
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost_usd": None,
            "latency_ms": None,
            "correlation_id": correlation_id,
            "audit_ref": None,
            "started_at": data.get("started_at") or _now(),
            "completed_at": None,
            "created_at": _now(),
        }
        self.rows_by_correlation[correlation_id] = row
        self.rows_by_invocation[row["invocation_id"]] = row
        self.order.append(correlation_id)
        return True, dict(row)

    async def complete_invocation(
        self, invocation_id: Any, *, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        row = self.rows_by_invocation.get(str(invocation_id))
        if row is None:
            return None
        if row["status"] != "started":
            # Already terminal -- the guard the real store's WHERE status='started' enforces.
            return dict(row)
        row["status"] = terminal["status"]
        row["failure_category"] = terminal.get("failure_category")
        row["failure_reason"] = sanitize_failure_reason(terminal.get("failure_reason"))
        row["latency_ms"] = terminal.get("latency_ms")
        row["audit_ref"] = terminal.get("audit_ref")
        row["completed_at"] = terminal.get("completed_at") or _now()
        return dict(row)

    async def get_by_correlation_id(self, correlation_id: str) -> dict[str, Any] | None:
        row = self.rows_by_correlation.get(str(correlation_id))
        return dict(row) if row is not None else None

    async def list_for_project(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = [
            dict(self.rows_by_correlation[cid])
            for cid in reversed(self.order)
            if str(self.rows_by_correlation[cid].get("project_id")) == str(project_id)
        ]
        return rows[:limit]


__all__ = ["InMemoryReasoningInvocationStore"]
