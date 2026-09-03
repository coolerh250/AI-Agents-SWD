"""Step AT-M3.1 -- in-memory fake ReasoningInvocationStore for unit tests.

Implements the same async surface ReasoningService uses, backed by a dict keyed on
``correlation_id``. No DB, no asyncpg. Follows the existing ``tests/agent_team_fakes.py``
convention.

Mirrors the real store's ownership semantics: ``try_begin_invocation`` returns ``owned=True`` only
for the first caller to claim a given ``correlation_id`` (a 'started' row is inserted immediately,
matching the real store's INSERT-before-provider-call ordering); every later caller for the same
correlation_id gets ``owned=False`` and the row's CURRENT state. ``complete_invocation`` only
transitions a row that is still 'started' -- exactly like the real store's
``UPDATE ... WHERE status='started'`` guard -- and also runs the SAME
``sanitize_failure_reason`` defense-in-depth the real store applies, so a test exercising the fake
observes identical failure_reason sanitization behaviour.

AT-M3.4 (rebaselined) added three behaviours this fake has to mirror or it would let a test pass
against semantics the database would refuse:

* a succeeded row CARRIES ITS ARTIFACT, written in the same transition as the status. The real
  schema makes the alternative unrepresentable (migration 040's success-artifact CHECK), so the
  fake refuses it too rather than quietly permitting a state no real database would hold;
* ownership is LEASED, and an expired lease is takeable exactly once per takeover;
* ``complete_invocation`` is guarded on ``attempt_token``, so a superseded attempt cannot write.

The lease clock here is ``expire_lease()``, driven by the test rather than by wall time. Sleeping
through a real TTL would make the suite slow and flaky, and what these tests need to establish is
the BEHAVIOUR at expiry, not that a timer works. The real timing is exercised against PostgreSQL's
own clock in the store tests, which is the only place it can be exercised honestly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.sdk.agent_reasoning.models import sanitize_failure_reason
from shared.sdk.agent_reasoning.store import DEFAULT_LEASE_TTL_SECONDS, DEFAULT_MAX_ATTEMPTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryReasoningInvocationStore:
    def __init__(
        self,
        *,
        lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.rows_by_correlation: dict[str, dict[str, Any]] = {}
        self.rows_by_invocation: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.lease_ttl_seconds = lease_ttl_seconds
        self.max_attempts = max_attempts

    # --- test control ---------------------------------------------------------------------

    def expire_lease(self, correlation_id: str) -> None:
        """Make the current owner's lease expired, as if the worker holding it had died."""
        row = self.rows_by_correlation[str(correlation_id)]
        row["lease_expires_at"] = _now() - timedelta(seconds=1)

    # --- lifecycle -------------------------------------------------------------------------

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
            "artifact_type": None,
            "artifact": None,
            "attempt": 1,
            "attempt_token": str(uuid.uuid4()),
            "lease_expires_at": _now() + timedelta(seconds=self.lease_ttl_seconds),
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

    async def try_take_over_invocation(self, correlation_id: Any) -> dict[str, Any] | None:
        row = self.rows_by_correlation.get(str(correlation_id))
        if row is None or row["status"] != "started":
            return None
        lease = row.get("lease_expires_at")
        if lease is not None and _now() < lease:
            return None
        if row["attempt"] >= self.max_attempts:
            return None
        row["attempt"] += 1
        row["attempt_token"] = str(uuid.uuid4())
        row["started_at"] = _now()
        row["lease_expires_at"] = _now() + timedelta(seconds=self.lease_ttl_seconds)
        return dict(row)

    async def advance_retryable_attempt(
        self, invocation_id: Any, *, attempt_token: Any, failure_category: str
    ) -> dict[str, Any] | None:
        """Mirror of the real compare-and-swap: current owner, still started, budget remaining.

        Note what is NOT mirrored, because the database refuses it: no failure_category or
        failure_reason is written onto the still-'started' row. Migration 037's
        ``chk_reasoning_invocations_status_consistency`` makes that state unrepresentable, so a
        fake that allowed it would let a test pass against semantics PostgreSQL would reject.
        """
        from shared.sdk.agent_reasoning.models import RETRYABLE_FAILURE_CATEGORIES

        if failure_category not in RETRYABLE_FAILURE_CATEGORIES:
            return None
        row = self.rows_by_invocation.get(str(invocation_id))
        if row is None or row["status"] != "started":
            return None
        if str(row["attempt_token"]) != str(attempt_token):
            return None
        if row["attempt"] >= self.max_attempts:
            return None
        row["attempt"] += 1
        row["attempt_token"] = str(uuid.uuid4())
        row["started_at"] = _now()
        row["lease_expires_at"] = _now() + timedelta(seconds=self.lease_ttl_seconds)
        return dict(row)

    async def complete_invocation(
        self, invocation_id: Any, *, attempt_token: Any, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        row = self.rows_by_invocation.get(str(invocation_id))
        if row is None:
            return None
        if row["status"] != "started":
            # Already terminal -- the guard the real store's WHERE status='started' enforces.
            return dict(row)
        if str(row["attempt_token"]) != str(attempt_token):
            # Superseded: this attempt lost its lease while the provider was running.
            return dict(row)
        status = terminal["status"]
        artifact = terminal.get("artifact")
        if status == "succeeded" and (artifact is None or terminal.get("artifact_type") is None):
            raise AssertionError(
                "a succeeded invocation must carry its artifact and artifact_type -- migration "
                "040's chk_reasoning_invocations_success_artifact makes the alternative "
                "unrepresentable, so this fake refuses it too"
            )
        row["status"] = status
        row["failure_category"] = terminal.get("failure_category")
        row["failure_reason"] = sanitize_failure_reason(terminal.get("failure_reason"))
        row["artifact_type"] = terminal.get("artifact_type") if status == "succeeded" else None
        row["artifact"] = artifact if status == "succeeded" else None
        row["latency_ms"] = terminal.get("latency_ms")
        row["audit_ref"] = terminal.get("audit_ref")
        row["completed_at"] = terminal.get("completed_at") or _now()
        row["lease_expires_at"] = None
        # AT-M3.6B.1: the real store writes these in the same terminal UPDATE, on BOTH outcomes --
        # a call that reached a provider consumed tokens whether or not its output was usable. The
        # fake mirrors that or a test could observe usage accounting the database would not keep.
        row["input_tokens"] = terminal.get("input_tokens")
        row["output_tokens"] = terminal.get("output_tokens")
        row["estimated_cost_usd"] = terminal.get("estimated_cost_usd")
        return dict(row)

    async def fail_exhausted_invocation(
        self, invocation_id: Any, *, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        row = self.rows_by_invocation.get(str(invocation_id))
        if row is None:
            return None
        if row["status"] != "started":
            return dict(row)
        lease = row.get("lease_expires_at")
        if lease is not None and _now() < lease:
            return dict(row)
        row["status"] = "failed"
        row["failure_category"] = terminal.get("failure_category", "provider_unavailable")
        row["failure_reason"] = sanitize_failure_reason(terminal.get("failure_reason"))
        row["completed_at"] = terminal.get("completed_at") or _now()
        row["lease_expires_at"] = None
        return dict(row)

    # --- read-only -------------------------------------------------------------------------

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
