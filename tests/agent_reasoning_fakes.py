"""Step AT-M3.1 -- in-memory fake ReasoningInvocationStore for unit tests.

Implements the same async surface ReasoningService uses, backed by a dict keyed on
``correlation_id``. No DB, no asyncpg. Follows the existing ``tests/agent_team_fakes.py``
convention, including its idempotency behaviour: inserting a second row under a correlation_id
already present returns the FIRST row, exactly as the real store's
``ON CONFLICT (correlation_id) DO NOTHING`` + re-fetch does.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryReasoningInvocationStore:
    def __init__(self) -> None:
        self.rows_by_correlation: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []

    async def record_invocation(self, data: dict[str, Any]) -> dict[str, Any]:
        correlation_id = str(data["correlation_id"])
        existing = self.rows_by_correlation.get(correlation_id)
        if existing is not None:
            return dict(existing)
        row = {
            "invocation_id": str(uuid.uuid4()),
            "created_at": _now(),
            **data,
            "correlation_id": correlation_id,
        }
        self.rows_by_correlation[correlation_id] = row
        self.order.append(correlation_id)
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
