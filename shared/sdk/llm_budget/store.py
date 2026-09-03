"""asyncpg-backed store for llm_budget_policies + llm_budget_events.

The store is intentionally small: every method opens a short-lived
connection. No method reads, returns, or logs an API key value.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .models import (
    COUNTED_EVENT_TYPES,
    DECISION_ALLOWED,
    DECISION_RECORDED,
    EVENT_TYPE_RECORDED_USAGE,
    EVENT_TYPE_RELEASED_RESERVATION,
    EVENT_TYPE_RESERVED_USAGE,
    POLICY_STATUS_ACTIVE,
    SCOPE_GLOBAL,
    BudgetDecision,
    LLMBudgetEvent,
    LLMBudgetPolicy,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_POLICY_RETURNING = (
    "policy_id, policy_name, scope_type, scope_id, provider, model_name, "
    "max_tokens_per_task, max_cost_per_task_usd, max_cost_per_day_usd, "
    "max_cost_per_month_usd, enforcement_mode, status, created_by, "
    "created_at, updated_at, metadata"
)

_EVENT_RETURNING = (
    "budget_event_id, task_id, workflow_id, policy_id, provider, model_name, "
    "event_type, estimated_prompt_tokens, estimated_completion_tokens, "
    "estimated_total_tokens, actual_prompt_tokens, actual_completion_tokens, "
    "actual_total_tokens, estimated_cost_usd, actual_cost_usd, "
    "budget_remaining_usd, decision, reason, created_at, metadata, reservation_key"
)


def _decode_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return {}


def _row_to_policy(row: asyncpg.Record) -> LLMBudgetPolicy:
    return LLMBudgetPolicy(
        policy_id=str(row["policy_id"]),
        policy_name=row["policy_name"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        provider=row["provider"],
        model_name=row["model_name"],
        max_tokens_per_task=(
            int(row["max_tokens_per_task"]) if row["max_tokens_per_task"] is not None else None
        ),
        max_cost_per_task_usd=(
            float(row["max_cost_per_task_usd"])
            if row["max_cost_per_task_usd"] is not None
            else None
        ),
        max_cost_per_day_usd=(
            float(row["max_cost_per_day_usd"]) if row["max_cost_per_day_usd"] is not None else None
        ),
        max_cost_per_month_usd=(
            float(row["max_cost_per_month_usd"])
            if row["max_cost_per_month_usd"] is not None
            else None
        ),
        enforcement_mode=row["enforcement_mode"],
        status=row["status"],
        created_by=row["created_by"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=_decode_metadata(row["metadata"]),
    )


def _row_to_event(row: asyncpg.Record) -> LLMBudgetEvent:
    return LLMBudgetEvent(
        budget_event_id=str(row["budget_event_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        policy_id=(str(row["policy_id"]) if row["policy_id"] is not None else None),
        provider=row["provider"],
        model_name=row["model_name"] or "",
        event_type=row["event_type"],
        estimated_prompt_tokens=int(row["estimated_prompt_tokens"] or 0),
        estimated_completion_tokens=int(row["estimated_completion_tokens"] or 0),
        estimated_total_tokens=int(row["estimated_total_tokens"] or 0),
        actual_prompt_tokens=(
            int(row["actual_prompt_tokens"]) if row["actual_prompt_tokens"] is not None else None
        ),
        actual_completion_tokens=(
            int(row["actual_completion_tokens"])
            if row["actual_completion_tokens"] is not None
            else None
        ),
        actual_total_tokens=(
            int(row["actual_total_tokens"]) if row["actual_total_tokens"] is not None else None
        ),
        estimated_cost_usd=float(row["estimated_cost_usd"] or 0.0),
        actual_cost_usd=(
            float(row["actual_cost_usd"]) if row["actual_cost_usd"] is not None else None
        ),
        budget_remaining_usd=(
            float(row["budget_remaining_usd"]) if row["budget_remaining_usd"] is not None else None
        ),
        decision=row["decision"],
        reason=row["reason"],
        created_at=row["created_at"],
        metadata=_decode_metadata(row["metadata"]),
        reservation_key=row["reservation_key"],
    )


class BudgetPolicyStore:
    """Reader + writer for the Stage 35 tables."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=5)

    async def create_policy(
        self,
        *,
        policy_name: str,
        provider: str = "mock",
        scope_type: str = SCOPE_GLOBAL,
        scope_id: str | None = None,
        model_name: str | None = None,
        max_tokens_per_task: int | None = None,
        max_cost_per_task_usd: float | None = None,
        max_cost_per_day_usd: float | None = None,
        max_cost_per_month_usd: float | None = None,
        enforcement_mode: str = "block",
        status: str = POLICY_STATUS_ACTIVE,
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LLMBudgetPolicy:
        meta_json = json.dumps(metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_budget_policies "
                "(policy_name, scope_type, scope_id, provider, model_name, "
                " max_tokens_per_task, max_cost_per_task_usd, "
                " max_cost_per_day_usd, max_cost_per_month_usd, "
                " enforcement_mode, status, created_by, metadata) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, "
                " $13::jsonb) "
                f"RETURNING {_POLICY_RETURNING}",
                policy_name,
                scope_type,
                scope_id,
                provider,
                model_name,
                max_tokens_per_task,
                max_cost_per_task_usd,
                max_cost_per_day_usd,
                max_cost_per_month_usd,
                enforcement_mode,
                status,
                created_by,
                meta_json,
            )
        finally:
            await conn.close()
        return _row_to_policy(row)

    async def get_active_policy(
        self,
        *,
        provider: str,
        task_id: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
    ) -> LLMBudgetPolicy | None:
        """Find the most-specific active policy for ``provider``.

        Precedence: task > workflow > user > provider > global.
        """
        conn = await self._connect()
        try:
            # We score the matches in SQL via a CASE so the most
            # specific scope wins.
            row = await conn.fetchrow(
                f"SELECT {_POLICY_RETURNING}, "
                "  CASE scope_type "
                "    WHEN 'task'     THEN 1 "
                "    WHEN 'workflow' THEN 2 "
                "    WHEN 'user'     THEN 3 "
                "    WHEN 'provider' THEN 4 "
                "    WHEN 'global'   THEN 5 "
                "    ELSE 9 END AS scope_rank "
                "FROM llm_budget_policies "
                "WHERE status = 'active' "
                "  AND ( "
                "    (scope_type = 'task'     AND scope_id IS NOT DISTINCT FROM $2 AND provider = $1) "
                "    OR (scope_type = 'workflow' AND scope_id IS NOT DISTINCT FROM $3 AND provider = $1) "
                "    OR (scope_type = 'user'     AND scope_id IS NOT DISTINCT FROM $4 AND provider = $1) "
                "    OR (scope_type = 'provider' AND provider = $1) "
                "    OR (scope_type = 'global') "
                "  ) "
                "  AND (provider = $1 OR scope_type = 'global') "
                "ORDER BY scope_rank ASC, created_at DESC "
                "LIMIT 1",
                provider,
                task_id,
                workflow_id,
                user_id,
            )
        finally:
            await conn.close()
        return _row_to_policy(row) if row else None

    async def list_policies(
        self,
        *,
        provider: str | None = None,
        scope_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[LLMBudgetPolicy]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_POLICY_RETURNING} FROM llm_budget_policies "
                "WHERE ($1::text IS NULL OR provider = $1) "
                "  AND ($2::text IS NULL OR scope_type = $2) "
                "  AND ($3::text IS NULL OR status = $3) "
                "ORDER BY created_at DESC "
                "LIMIT $4",
                provider,
                scope_type,
                status,
                max(1, min(int(limit or 100), 500)),
            )
        finally:
            await conn.close()
        return [_row_to_policy(r) for r in rows]

    async def record_budget_event(
        self,
        *,
        task_id: str | None,
        workflow_id: str | None,
        policy_id: str | None,
        provider: str,
        model_name: str,
        event_type: str,
        decision: str,
        estimated_prompt_tokens: int = 0,
        estimated_completion_tokens: int = 0,
        estimated_total_tokens: int = 0,
        actual_prompt_tokens: int | None = None,
        actual_completion_tokens: int | None = None,
        actual_total_tokens: int | None = None,
        estimated_cost_usd: float = 0.0,
        actual_cost_usd: float | None = None,
        budget_remaining_usd: float | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        reservation_key: str | None = None,
    ) -> LLMBudgetEvent:
        meta_json = json.dumps(metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_budget_events "
                "(task_id, workflow_id, policy_id, provider, model_name, "
                " event_type, estimated_prompt_tokens, "
                " estimated_completion_tokens, estimated_total_tokens, "
                " actual_prompt_tokens, actual_completion_tokens, "
                " actual_total_tokens, estimated_cost_usd, actual_cost_usd, "
                " budget_remaining_usd, decision, reason, metadata, "
                " reservation_key) "
                "VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, "
                " $12, $13, $14, $15, $16, $17, $18::jsonb, $19) "
                f"RETURNING {_EVENT_RETURNING}",
                task_id,
                workflow_id,
                policy_id,
                provider,
                model_name,
                event_type,
                int(estimated_prompt_tokens),
                int(estimated_completion_tokens),
                int(estimated_total_tokens),
                actual_prompt_tokens,
                actual_completion_tokens,
                actual_total_tokens,
                float(estimated_cost_usd),
                actual_cost_usd,
                budget_remaining_usd,
                decision,
                reason,
                meta_json,
                reservation_key,
            )
        finally:
            await conn.close()
        return _row_to_event(row)

    async def list_events(
        self,
        *,
        task_id: str | None = None,
        provider: str | None = None,
        event_type: str | None = None,
        decision: str | None = None,
        limit: int = 100,
    ) -> list[LLMBudgetEvent]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_EVENT_RETURNING} FROM llm_budget_events "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "  AND ($2::text IS NULL OR provider = $2) "
                "  AND ($3::text IS NULL OR event_type = $3) "
                "  AND ($4::text IS NULL OR decision = $4) "
                "ORDER BY created_at DESC LIMIT $5",
                task_id,
                provider,
                event_type,
                decision,
                max(1, min(int(limit or 100), 500)),
            )
        finally:
            await conn.close()
        return [_row_to_event(r) for r in rows]

    # --- attempt-scoped reservation / settlement -----------------------------------------------
    #
    # AT-M3.6B.1 Independent Validation 1 found that a provider call could land, `record_usage`
    # could fail, the failure could be swallowed, and the day and month totals would understate that
    # charge forever -- so the next preflight would authorize spend the account could not afford.
    #
    # The fix is ordering, not error handling: claim the budget BEFORE the wire. One ledger row
    # carries one attempt from reservation to settlement. While it is unsettled it counts at the
    # conservative estimate that gated the call; once settled it counts at the actual. Because it is
    # the SAME row throughout, "count reservations and settlements" cannot double-count -- there is
    # never a second row to add. And because the reservation is already durable, a settlement
    # failure can only leave the charge conservative; it can never leave it at zero.

    async def reserve_attempt_cost(
        self,
        *,
        reservation_key: str,
        provider: str,
        model_name: str,
        policy_id: str | None = None,
        estimated_prompt_tokens: int = 0,
        estimated_completion_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        task_id: str | None = None,
        workflow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMBudgetEvent:
        """Durably claim ``estimated_cost_usd`` for ONE provider attempt. Idempotent.

        ``reservation_key`` identifies the attempt -- invocation plus attempt number, never the
        attempt token, which is ownership-sensitive and rotates. A unique index makes the identity
        the database's answer rather than the application's, so eight concurrent callers racing for
        the same attempt produce exactly one reservation and exactly one charge; the losers are
        handed the winner's row instead of an error.
        """
        total = int(estimated_prompt_tokens) + int(estimated_completion_tokens)
        meta_json = json.dumps(metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_budget_events "
                "(task_id, workflow_id, policy_id, provider, model_name, event_type, "
                " estimated_prompt_tokens, estimated_completion_tokens, "
                " estimated_total_tokens, estimated_cost_usd, decision, metadata, "
                " reservation_key) "
                "VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13) "
                "ON CONFLICT (reservation_key) WHERE reservation_key IS NOT NULL DO NOTHING "
                f"RETURNING {_EVENT_RETURNING}",
                task_id,
                workflow_id,
                policy_id,
                provider,
                model_name,
                EVENT_TYPE_RESERVED_USAGE,
                int(estimated_prompt_tokens),
                int(estimated_completion_tokens),
                total,
                float(estimated_cost_usd),
                DECISION_ALLOWED,
                meta_json,
                reservation_key,
            )
            if row is None:
                # Somebody reserved this exact attempt first. Their row is the reservation.
                row = await conn.fetchrow(
                    f"SELECT {_EVENT_RETURNING} FROM llm_budget_events WHERE reservation_key = $1",
                    reservation_key,
                )
        finally:
            await conn.close()
        return _row_to_event(row)

    async def settle_attempt_cost(
        self,
        *,
        reservation_key: str,
        actual_prompt_tokens: int,
        actual_completion_tokens: int,
        actual_cost_usd: float,
        metadata: dict[str, Any] | None = None,
    ) -> LLMBudgetEvent | None:
        """Replace a reservation with what the call actually consumed. Idempotent.

        Guarded on ``event_type = 'reserved_usage'``, which is what makes repeating it safe: a
        second settlement of the same attempt matches no row, so nothing is added and nothing is
        charged twice. Returns the row's current state either way -- already-settled is an answer,
        not an error -- or ``None`` when the reservation does not exist at all.
        """
        total = int(actual_prompt_tokens) + int(actual_completion_tokens)
        meta_json = json.dumps(metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_budget_events SET "
                "  event_type = $2, decision = $3, "
                "  actual_prompt_tokens = $4, actual_completion_tokens = $5, "
                "  actual_total_tokens = $6, actual_cost_usd = $7, "
                "  metadata = metadata || $8::jsonb "
                "WHERE reservation_key = $1 AND event_type = $9 "
                f"RETURNING {_EVENT_RETURNING}",
                reservation_key,
                EVENT_TYPE_RECORDED_USAGE,
                DECISION_RECORDED,
                int(actual_prompt_tokens),
                int(actual_completion_tokens),
                total,
                float(actual_cost_usd),
                meta_json,
                EVENT_TYPE_RESERVED_USAGE,
            )
            if row is None:
                row = await conn.fetchrow(
                    f"SELECT {_EVENT_RETURNING} FROM llm_budget_events WHERE reservation_key = $1",
                    reservation_key,
                )
        finally:
            await conn.close()
        return _row_to_event(row) if row is not None else None

    async def release_attempt_reservation(
        self, *, reservation_key: str, reason: str | None = None
    ) -> LLMBudgetEvent | None:
        """Cancel a reservation for a call that PROVABLY never left this process.

        Called only where absence can be established -- a refusal reached before an HTTP client was
        ever built. Never called on an ambiguous failure: a timeout, a reset connection or a dead
        worker cannot prove that no request arrived, and releasing on a guess is how a real charge
        gets counted at zero. The row is relabelled rather than deleted, so the evidence that budget
        was claimed and given back survives.
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_budget_events SET event_type = $2, reason = $3 "
                "WHERE reservation_key = $1 AND event_type = $4 "
                f"RETURNING {_EVENT_RETURNING}",
                reservation_key,
                EVENT_TYPE_RELEASED_RESERVATION,
                reason,
                EVENT_TYPE_RESERVED_USAGE,
            )
        finally:
            await conn.close()
        return _row_to_event(row) if row is not None else None

    async def get_reservation(self, *, reservation_key: str) -> LLMBudgetEvent | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_EVENT_RETURNING} FROM llm_budget_events WHERE reservation_key = $1",
                reservation_key,
            )
        finally:
            await conn.close()
        return _row_to_event(row) if row is not None else None

    async def get_daily_usage_usd(
        self, *, provider: str | None = None, day: datetime | None = None
    ) -> float:
        day = day or datetime.now(timezone.utc)
        conn = await self._connect()
        try:
            value = await conn.fetchval(
                "SELECT COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) "
                "FROM llm_budget_events "
                "WHERE event_type = ANY($1::text[]) "
                "  AND ($2::text IS NULL OR provider = $2) "
                "  AND created_at >= date_trunc('day', $3::timestamptz) "
                "  AND created_at <  date_trunc('day', $3::timestamptz) + interval '1 day'",
                list(COUNTED_EVENT_TYPES),
                provider,
                day,
            )
        finally:
            await conn.close()
        return float(value or 0.0)

    async def get_monthly_usage_usd(
        self, *, provider: str | None = None, month: datetime | None = None
    ) -> float:
        month = month or datetime.now(timezone.utc)
        conn = await self._connect()
        try:
            value = await conn.fetchval(
                "SELECT COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) "
                "FROM llm_budget_events "
                "WHERE event_type = ANY($1::text[]) "
                "  AND ($2::text IS NULL OR provider = $2) "
                "  AND created_at >= date_trunc('month', $3::timestamptz) "
                "  AND created_at <  date_trunc('month', $3::timestamptz) + interval '1 month'",
                list(COUNTED_EVENT_TYPES),
                provider,
                month,
            )
        finally:
            await conn.close()
        return float(value or 0.0)

    async def get_task_usage(self, *, task_id: str) -> dict[str, float | int]:
        """Return aggregated per-task usage from recorded events."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT "
                "  COALESCE(SUM(COALESCE(actual_total_tokens, estimated_total_tokens, 0)), 0) AS tokens, "
                "  COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) AS cost "
                "FROM llm_budget_events "
                "WHERE event_type = ANY($1::text[]) AND task_id = $2",
                list(COUNTED_EVENT_TYPES),
                task_id,
            )
        finally:
            await conn.close()
        return {
            "tokens": int(row["tokens"] or 0),
            "cost_usd": float(row["cost"] or 0.0),
        }

    async def get_usage_summary(self, *, provider: str | None = None) -> dict[str, Any]:
        daily = await self.get_daily_usage_usd(provider=provider)
        monthly = await self.get_monthly_usage_usd(provider=provider)
        conn = await self._connect()
        try:
            counts = await conn.fetchrow(
                "SELECT "
                "  COUNT(*) FILTER (WHERE decision = 'allowed') AS allowed, "
                "  COUNT(*) FILTER (WHERE decision = 'blocked') AS blocked, "
                "  COUNT(*) FILTER (WHERE decision = 'warning') AS warning, "
                "  COUNT(*) FILTER (WHERE decision = 'recorded') AS recorded, "
                "  COUNT(*) AS total "
                "FROM llm_budget_events "
                "WHERE ($1::text IS NULL OR provider = $1)",
                provider,
            )
        finally:
            await conn.close()
        return {
            "daily_usage_usd": daily,
            "monthly_usage_usd": monthly,
            "allowed_events": int(counts["allowed"] or 0),
            "blocked_events": int(counts["blocked"] or 0),
            "warning_events": int(counts["warning"] or 0),
            "recorded_events": int(counts["recorded"] or 0),
            "total_events": int(counts["total"] or 0),
        }


# Keep the BudgetDecision type re-exported for convenience.
__all__ = ["BudgetPolicyStore", "BudgetDecision"]
