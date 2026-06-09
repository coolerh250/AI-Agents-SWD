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
    EVENT_TYPE_RECORDED_USAGE,
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
    "budget_remaining_usd, decision, reason, created_at, metadata"
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
                " budget_remaining_usd, decision, reason, metadata) "
                "VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, "
                " $12, $13, $14, $15, $16, $17, $18::jsonb) "
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

    async def get_daily_usage_usd(
        self, *, provider: str | None = None, day: datetime | None = None
    ) -> float:
        day = day or datetime.now(timezone.utc)
        conn = await self._connect()
        try:
            value = await conn.fetchval(
                "SELECT COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)), 0) "
                "FROM llm_budget_events "
                "WHERE event_type = $1 "
                "  AND ($2::text IS NULL OR provider = $2) "
                "  AND created_at >= date_trunc('day', $3::timestamptz) "
                "  AND created_at <  date_trunc('day', $3::timestamptz) + interval '1 day'",
                EVENT_TYPE_RECORDED_USAGE,
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
                "WHERE event_type = $1 "
                "  AND ($2::text IS NULL OR provider = $2) "
                "  AND created_at >= date_trunc('month', $3::timestamptz) "
                "  AND created_at <  date_trunc('month', $3::timestamptz) + interval '1 month'",
                EVENT_TYPE_RECORDED_USAGE,
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
                "WHERE event_type = $1 AND task_id = $2",
                EVENT_TYPE_RECORDED_USAGE,
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
