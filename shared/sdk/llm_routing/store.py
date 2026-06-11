"""Stage 38 -- asyncpg-backed store for llm_model_registry +
agent_model_policies + llm_routing_decisions.

Every method opens a short-lived connection. No method reads,
returns, or logs an API key value.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import asyncpg

from .models import (
    AGENT_DEFAULT_TASK_TYPE,
    AgentModelPolicy,
    LLMModelEntry,
    MODEL_STATUS_ACTIVE,
    MODEL_TIER_DOCUMENTATION,
    RoutingDecisionRecord,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


def _row_to_model(row: asyncpg.Record) -> LLMModelEntry:
    return LLMModelEntry(
        model_id=str(row["model_id"]),
        provider=row["provider"],
        model_name=row["model_name"],
        model_alias=row["model_alias"],
        model_tier=row["model_tier"],
        capabilities=list(_decode_json(row["capabilities"]) or []),
        supported_schemas=list(_decode_json(row["supported_schemas"]) or []),
        max_context_tokens=row["max_context_tokens"],
        default_max_output_tokens=row["default_max_output_tokens"],
        cost_per_1k_input_tokens=float(row["cost_per_1k_input_tokens"] or 0.0),
        cost_per_1k_output_tokens=float(row["cost_per_1k_output_tokens"] or 0.0),
        latency_class=row["latency_class"],
        risk_level=row["risk_level"],
        status=row["status"],
        plan_only_allowed=bool(row["plan_only_allowed"]),
        patch_generation_allowed=bool(row["patch_generation_allowed"]),
        workspace_write_allowed=bool(row["workspace_write_allowed"]),
        production_use_allowed=bool(row["production_use_allowed"]),
        requires_human_review=bool(row["requires_human_review"]),
        metadata=dict(_decode_json(row["metadata"]) or {}),
    )


def _row_to_policy(row: asyncpg.Record) -> AgentModelPolicy:
    return AgentModelPolicy(
        policy_id=str(row["policy_id"]),
        agent_name=row["agent_name"],
        task_type=row["task_type"],
        capability=row["capability"],
        risk_level=row["risk_level"],
        preferred_model_alias=row["preferred_model_alias"],
        allowed_model_tiers=list(_decode_json(row["allowed_model_tiers"]) or []),
        allowed_providers=list(_decode_json(row["allowed_providers"]) or []),
        fallback_model_aliases=list(_decode_json(row["fallback_model_aliases"]) or []),
        max_cost_per_task_usd=(
            float(row["max_cost_per_task_usd"])
            if row["max_cost_per_task_usd"] is not None
            else None
        ),
        max_tokens_per_task=(
            int(row["max_tokens_per_task"]) if row["max_tokens_per_task"] is not None else None
        ),
        requires_human_review=bool(row["requires_human_review"]),
        allow_real_llm=bool(row["allow_real_llm"]),
        allow_patch_generation=bool(row["allow_patch_generation"]),
        allow_workspace_write=bool(row["allow_workspace_write"]),
        status=row["status"],
        created_by=row["created_by"],
        metadata=dict(_decode_json(row["metadata"]) or {}),
    )


def _row_to_decision(row: asyncpg.Record) -> RoutingDecisionRecord:
    return RoutingDecisionRecord(
        routing_decision_id=str(row["routing_decision_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        agent_name=row["agent_name"],
        capability=row["capability"],
        task_type=row["task_type"],
        risk_level=row["risk_level"],
        decision=row["decision"],
        reason=row["reason"],
        selected_provider=row["selected_provider"],
        selected_model_name=row["selected_model_name"],
        selected_model_alias=row["selected_model_alias"],
        selected_model_tier=row["selected_model_tier"],
        requested_schema=row["requested_schema"],
        requested_model_alias=row["requested_model_alias"],
        fallback_used=bool(row["fallback_used"]),
        estimated_input_tokens=row["estimated_input_tokens"],
        estimated_output_tokens=row["estimated_output_tokens"],
        estimated_cost_usd=(
            float(row["estimated_cost_usd"]) if row["estimated_cost_usd"] is not None else None
        ),
        requires_human_review=bool(row["requires_human_review"]),
        real_llm_allowed=bool(row["real_llm_allowed"]),
        patch_generation_allowed=bool(row["patch_generation_allowed"]),
        workspace_write_allowed=bool(row["workspace_write_allowed"]),
        budget_policy_id=(
            str(row["budget_policy_id"]) if row["budget_policy_id"] is not None else None
        ),
        policy_id=str(row["policy_id"]) if row["policy_id"] is not None else None,
        model_id=str(row["model_id"]) if row["model_id"] is not None else None,
        created_at=row["created_at"],
        metadata=dict(_decode_json(row["metadata"]) or {}),
    )


class ModelRouterStore:
    """Async asyncpg facade over the Stage 38 tables."""

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self._database_url)

    # ------------------------------------------------------------------
    # Model registry
    # ------------------------------------------------------------------

    async def upsert_model(self, entry: dict[str, Any]) -> LLMModelEntry:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO llm_model_registry (
                    provider, model_name, model_alias, model_tier,
                    capabilities, supported_schemas, max_context_tokens,
                    default_max_output_tokens, cost_per_1k_input_tokens,
                    cost_per_1k_output_tokens, latency_class, risk_level,
                    status, plan_only_allowed, patch_generation_allowed,
                    workspace_write_allowed, production_use_allowed,
                    requires_human_review, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19::jsonb
                )
                ON CONFLICT (model_alias) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    model_name = EXCLUDED.model_name,
                    model_tier = EXCLUDED.model_tier,
                    capabilities = EXCLUDED.capabilities,
                    supported_schemas = EXCLUDED.supported_schemas,
                    max_context_tokens = EXCLUDED.max_context_tokens,
                    default_max_output_tokens = EXCLUDED.default_max_output_tokens,
                    cost_per_1k_input_tokens = EXCLUDED.cost_per_1k_input_tokens,
                    cost_per_1k_output_tokens = EXCLUDED.cost_per_1k_output_tokens,
                    latency_class = EXCLUDED.latency_class,
                    risk_level = EXCLUDED.risk_level,
                    status = EXCLUDED.status,
                    plan_only_allowed = EXCLUDED.plan_only_allowed,
                    patch_generation_allowed = EXCLUDED.patch_generation_allowed,
                    workspace_write_allowed = EXCLUDED.workspace_write_allowed,
                    production_use_allowed = EXCLUDED.production_use_allowed,
                    requires_human_review = EXCLUDED.requires_human_review,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *
                """,
                entry["provider"],
                entry["model_name"],
                entry["model_alias"],
                entry.get("model_tier", MODEL_TIER_DOCUMENTATION),
                json.dumps(entry.get("capabilities", [])),
                json.dumps(entry.get("supported_schemas", [])),
                entry.get("max_context_tokens"),
                entry.get("default_max_output_tokens"),
                entry.get("cost_per_1k_input_tokens", 0.0),
                entry.get("cost_per_1k_output_tokens", 0.0),
                entry.get("latency_class", "standard"),
                entry.get("risk_level", "low"),
                entry.get("status", MODEL_STATUS_ACTIVE),
                bool(entry.get("plan_only_allowed", False)),
                # Hard safety: these three NEVER store True regardless
                # of caller intent.
                False,
                False,
                False,
                bool(entry.get("requires_human_review", True)),
                json.dumps(entry.get("metadata", {})),
            )
            assert row is not None
            return _row_to_model(row)
        finally:
            await conn.close()

    async def list_models(
        self,
        *,
        status: str | None = None,
        provider: str | None = None,
        limit: int = 200,
    ) -> list[LLMModelEntry]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM llm_model_registry
                WHERE ($1::text IS NULL OR status = $1)
                  AND ($2::text IS NULL OR provider = $2)
                ORDER BY model_tier, model_alias
                LIMIT $3
                """,
                status,
                provider,
                int(limit),
            )
            return [_row_to_model(r) for r in rows]
        finally:
            await conn.close()

    async def get_model_by_alias(self, alias: str) -> LLMModelEntry | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM llm_model_registry WHERE model_alias = $1",
                alias,
            )
            return _row_to_model(row) if row is not None else None
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Agent model policies
    # ------------------------------------------------------------------

    async def upsert_policy(self, entry: dict[str, Any]) -> AgentModelPolicy:
        conn = await self._connect()
        try:
            # Two-step: the partial unique index covers status=active.
            existing = await conn.fetchrow(
                """
                SELECT * FROM agent_model_policies
                WHERE agent_name = $1
                  AND task_type = $2
                  AND capability = $3
                  AND risk_level = $4
                  AND status = 'active'
                LIMIT 1
                """,
                entry["agent_name"],
                entry.get("task_type", AGENT_DEFAULT_TASK_TYPE),
                entry["capability"],
                entry.get("risk_level", "low"),
            )
            if existing is not None:
                row = await conn.fetchrow(
                    """
                    UPDATE agent_model_policies
                    SET preferred_model_alias = $2,
                        allowed_model_tiers = $3::jsonb,
                        allowed_providers = $4::jsonb,
                        fallback_model_aliases = $5::jsonb,
                        max_cost_per_task_usd = $6,
                        max_tokens_per_task = $7,
                        requires_human_review = $8,
                        allow_real_llm = $9,
                        allow_patch_generation = $10,
                        allow_workspace_write = $11,
                        metadata = $12::jsonb,
                        updated_at = NOW()
                    WHERE policy_id = $1
                    RETURNING *
                    """,
                    existing["policy_id"],
                    entry.get("preferred_model_alias"),
                    json.dumps(entry.get("allowed_model_tiers", [])),
                    json.dumps(entry.get("allowed_providers", [])),
                    json.dumps(entry.get("fallback_model_aliases", [])),
                    entry.get("max_cost_per_task_usd"),
                    entry.get("max_tokens_per_task"),
                    bool(entry.get("requires_human_review", False)),
                    bool(entry.get("allow_real_llm", False)),
                    # Hard safety again at the SQL boundary.
                    False,
                    False,
                    json.dumps(entry.get("metadata", {})),
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO agent_model_policies (
                        agent_name, task_type, capability, risk_level,
                        preferred_model_alias, allowed_model_tiers,
                        allowed_providers, fallback_model_aliases,
                        max_cost_per_task_usd, max_tokens_per_task,
                        requires_human_review, allow_real_llm,
                        allow_patch_generation, allow_workspace_write,
                        status, created_by, metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6::jsonb, $7::jsonb,
                        $8::jsonb, $9, $10, $11, $12, $13, $14, 'active',
                        $15, $16::jsonb
                    )
                    RETURNING *
                    """,
                    entry["agent_name"],
                    entry.get("task_type", AGENT_DEFAULT_TASK_TYPE),
                    entry["capability"],
                    entry.get("risk_level", "low"),
                    entry.get("preferred_model_alias"),
                    json.dumps(entry.get("allowed_model_tiers", [])),
                    json.dumps(entry.get("allowed_providers", [])),
                    json.dumps(entry.get("fallback_model_aliases", [])),
                    entry.get("max_cost_per_task_usd"),
                    entry.get("max_tokens_per_task"),
                    bool(entry.get("requires_human_review", False)),
                    bool(entry.get("allow_real_llm", False)),
                    False,
                    False,
                    entry.get("created_by", "system"),
                    json.dumps(entry.get("metadata", {})),
                )
            assert row is not None
            return _row_to_policy(row)
        finally:
            await conn.close()

    async def get_active_policy(
        self,
        *,
        agent_name: str,
        capability: str,
        task_type: str = AGENT_DEFAULT_TASK_TYPE,
        risk_level: str = "low",
    ) -> AgentModelPolicy | None:
        """Look up the most specific active policy for (agent, capability).

        Ordering preference:
          1. exact task_type AND exact risk_level
          2. exact task_type AND task_type=default risk fallback
          3. any active row for (agent, capability)
        Falling through to step 3 keeps an existing seeded policy from
        being missed when the caller's risk_level doesn't match. The
        policy itself still controls what's allowed -- the router does
        not relax safety just because the lookup widened.
        """

        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                SELECT * FROM agent_model_policies
                WHERE status = 'active'
                  AND agent_name = $1
                  AND capability = $2
                ORDER BY
                    (task_type = $3) DESC,
                    (task_type = 'default') DESC,
                    (risk_level = $4) DESC,
                    (risk_level = 'low') DESC
                LIMIT 1
                """,
                agent_name,
                capability,
                task_type,
                risk_level,
            )
            return _row_to_policy(row) if row is not None else None
        finally:
            await conn.close()

    async def list_policies(
        self,
        *,
        agent_name: str | None = None,
        status: str | None = "active",
        limit: int = 200,
    ) -> list[AgentModelPolicy]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM agent_model_policies
                WHERE ($1::text IS NULL OR agent_name = $1)
                  AND ($2::text IS NULL OR status = $2)
                ORDER BY agent_name, capability, risk_level
                LIMIT $3
                """,
                agent_name,
                status,
                int(limit),
            )
            return [_row_to_policy(r) for r in rows]
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Routing decisions
    # ------------------------------------------------------------------

    async def record_decision(self, decision: dict[str, Any]) -> RoutingDecisionRecord:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO llm_routing_decisions (
                    task_id, workflow_id, agent_name, capability,
                    task_type, risk_level, requested_schema,
                    requested_model_alias, selected_provider,
                    selected_model_name, selected_model_alias,
                    selected_model_tier, decision, reason, fallback_used,
                    budget_policy_id, estimated_input_tokens,
                    estimated_output_tokens, estimated_cost_usd,
                    requires_human_review, real_llm_allowed,
                    patch_generation_allowed, workspace_write_allowed,
                    policy_id, model_id, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,
                    $23, $24, $25, $26::jsonb
                )
                RETURNING *
                """,
                decision.get("task_id"),
                decision.get("workflow_id"),
                decision["agent_name"],
                decision["capability"],
                decision.get("task_type", AGENT_DEFAULT_TASK_TYPE),
                decision.get("risk_level", "low"),
                decision.get("requested_schema"),
                decision.get("requested_model_alias"),
                decision.get("selected_provider"),
                decision.get("selected_model_name"),
                decision.get("selected_model_alias"),
                decision.get("selected_model_tier"),
                decision["decision"],
                decision.get("reason"),
                bool(decision.get("fallback_used", False)),
                decision.get("budget_policy_id"),
                decision.get("estimated_input_tokens"),
                decision.get("estimated_output_tokens"),
                decision.get("estimated_cost_usd"),
                bool(decision.get("requires_human_review", False)),
                bool(decision.get("real_llm_allowed", False)),
                # Hard safety SQL boundary -- these never store true.
                False,
                False,
                decision.get("policy_id"),
                decision.get("model_id"),
                json.dumps(decision.get("metadata", {})),
            )
            assert row is not None
            return _row_to_decision(row)
        finally:
            await conn.close()

    async def list_decisions(
        self,
        *,
        task_id: str | None = None,
        agent_name: str | None = None,
        decision: str | None = None,
        limit: int = 100,
    ) -> list[RoutingDecisionRecord]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM llm_routing_decisions
                WHERE ($1::text IS NULL OR task_id = $1)
                  AND ($2::text IS NULL OR agent_name = $2)
                  AND ($3::text IS NULL OR decision = $3)
                ORDER BY created_at DESC
                LIMIT $4
                """,
                task_id,
                agent_name,
                decision,
                int(limit),
            )
            return [_row_to_decision(r) for r in rows]
        finally:
            await conn.close()

    async def get_decision(self, routing_decision_id: str) -> RoutingDecisionRecord | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM llm_routing_decisions WHERE routing_decision_id = $1::uuid",
                routing_decision_id,
            )
            return _row_to_decision(row) if row is not None else None
        finally:
            await conn.close()

    async def count_decisions_by(
        self,
        *,
        decision: str | None = None,
        since: datetime | None = None,
    ) -> int:
        conn = await self._connect()
        try:
            value = await conn.fetchval(
                """
                SELECT count(*) FROM llm_routing_decisions
                WHERE ($1::text IS NULL OR decision = $1)
                  AND ($2::timestamptz IS NULL OR created_at >= $2)
                """,
                decision,
                since,
            )
            return int(value or 0)
        finally:
            await conn.close()
