"""asyncpg store for the Stage 30 LLM tables.

Tables (see ``migrations/010_llm_assisted_development.sql``):

* ``llm_interactions`` — one row per LLM call (prompt hash + redacted
  preview + response hash + redacted preview + safety_result).
* ``llm_proposal_artifacts`` — one row per patch proposal.
* ``llm_usage_records`` — one row per token / cost record (mock = 0).

Connection-per-call. Never stores a full prompt / response, never
stores an API key, never echoes a credential — even the previews are
pre-redacted by :func:`shared.sdk.llm.prompt_contract.redact_text`.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.llm.models import (
    LLMInteraction,
    LLMProposalArtifact,
    LLMUsageRecord,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_INTERACTION_COLUMNS = (
    "interaction_id, task_id, workflow_id, provider, model_name, "
    "interaction_type, prompt_hash, prompt_preview, response_hash, "
    "response_preview, status, token_usage, safety_result, created_at"
)

_PROPOSAL_COLUMNS = (
    "proposal_id, task_id, workflow_id, interaction_id, proposal_type, "
    "status, proposed_files, plan, safety_result, requires_human_review, "
    "linked_workspace_id, created_at, updated_at"
)

_USAGE_COLUMNS = (
    "usage_id, task_id, provider, model_name, prompt_tokens, "
    "completion_tokens, total_tokens, estimated_cost, created_at"
)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _decode_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


def _row_to_interaction(row: asyncpg.Record) -> LLMInteraction:
    return LLMInteraction(
        interaction_id=str(row["interaction_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        provider=row["provider"] or "mock",
        model_name=row["model_name"] or "mock-deterministic",
        interaction_type=row["interaction_type"] or "development_plan",
        prompt_hash=row["prompt_hash"] or "",
        prompt_preview=row["prompt_preview"] or "",
        response_hash=row["response_hash"] or "",
        response_preview=row["response_preview"] or "",
        status=row["status"] or "ok",
        token_usage=_decode_json(row["token_usage"], None),
        safety_result=_decode_json(row["safety_result"], {}) or {},
        created_at=_iso(row["created_at"]),
    )


def _row_to_proposal(row: asyncpg.Record) -> LLMProposalArtifact:
    return LLMProposalArtifact(
        proposal_id=str(row["proposal_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        interaction_id=str(row["interaction_id"]) if row["interaction_id"] is not None else None,
        proposal_type=row["proposal_type"] or "patch_proposal",
        status=row["status"] or "proposed",
        proposed_files=_decode_json(row["proposed_files"], []) or [],
        plan=_decode_json(row["plan"], {}) or {},
        safety_result=_decode_json(row["safety_result"], {}) or {},
        requires_human_review=bool(row["requires_human_review"]),
        linked_workspace_id=(
            str(row["linked_workspace_id"]) if row["linked_workspace_id"] is not None else None
        ),
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


def _row_to_usage(row: asyncpg.Record) -> LLMUsageRecord:
    return LLMUsageRecord(
        usage_id=str(row["usage_id"]),
        task_id=row["task_id"],
        provider=row["provider"] or "mock",
        model_name=row["model_name"] or "mock-deterministic",
        prompt_tokens=int(row["prompt_tokens"] or 0),
        completion_tokens=int(row["completion_tokens"] or 0),
        total_tokens=int(row["total_tokens"] or 0),
        estimated_cost=float(row["estimated_cost"] or 0.0),
        created_at=_iso(row["created_at"]),
    )


class LLMInteractionStore:
    """Persistence surface for the three Stage 30 tables."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # llm_interactions
    # ------------------------------------------------------------------

    async def record_interaction(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        provider: str,
        model_name: str,
        interaction_type: str,
        prompt_hash: str,
        prompt_preview: str,
        response_hash: str,
        response_preview: str,
        status: str = "ok",
        token_usage: dict[str, Any] | None = None,
        safety_result: dict[str, Any] | None = None,
    ) -> LLMInteraction:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_interactions "
                "(task_id, workflow_id, provider, model_name, interaction_type, "
                " prompt_hash, prompt_preview, response_hash, response_preview, "
                " status, token_usage, safety_result) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb) "
                f"RETURNING {_INTERACTION_COLUMNS}",
                task_id,
                workflow_id,
                provider,
                model_name,
                interaction_type,
                prompt_hash,
                prompt_preview,
                response_hash,
                response_preview,
                status,
                json.dumps(token_usage) if token_usage is not None else None,
                json.dumps(safety_result or {}),
            )
        finally:
            await conn.close()
        return _row_to_interaction(row)

    async def list_interactions(
        self,
        *,
        task_id: str | None = None,
        interaction_type: str | None = None,
        limit: int = 100,
    ) -> list[LLMInteraction]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_INTERACTION_COLUMNS} FROM llm_interactions "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR interaction_type = $2) "
                "ORDER BY created_at DESC LIMIT $3",
                task_id,
                interaction_type,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_interaction(r) for r in rows]

    # ------------------------------------------------------------------
    # llm_proposal_artifacts
    # ------------------------------------------------------------------

    async def record_proposal(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        interaction_id: str | None,
        proposal_type: str,
        status: str,
        proposed_files: list[dict[str, Any]],
        plan: dict[str, Any],
        safety_result: dict[str, Any],
        requires_human_review: bool = True,
        linked_workspace_id: str | None = None,
    ) -> LLMProposalArtifact:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_proposal_artifacts "
                "(task_id, workflow_id, interaction_id, proposal_type, status, "
                " proposed_files, plan, safety_result, requires_human_review, "
                " linked_workspace_id) "
                "VALUES ($1, $2, $3::uuid, $4, $5, $6::jsonb, $7::jsonb, "
                " $8::jsonb, $9, $10::uuid) "
                f"RETURNING {_PROPOSAL_COLUMNS}",
                task_id,
                workflow_id,
                interaction_id,
                proposal_type,
                status,
                json.dumps(proposed_files or []),
                json.dumps(plan or {}),
                json.dumps(safety_result or {}),
                requires_human_review,
                linked_workspace_id,
            )
        finally:
            await conn.close()
        return _row_to_proposal(row)

    async def update_proposal_status(
        self,
        proposal_id: str,
        *,
        status: str,
        linked_workspace_id: str | None = None,
    ) -> LLMProposalArtifact | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_proposal_artifacts SET "
                " status = $2, "
                " linked_workspace_id = COALESCE($3::uuid, linked_workspace_id), "
                " updated_at = now() "
                f"WHERE proposal_id = $1::uuid RETURNING {_PROPOSAL_COLUMNS}",
                proposal_id,
                status,
                linked_workspace_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_proposal(row) if row else None

    async def list_proposals(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[LLMProposalArtifact]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_PROPOSAL_COLUMNS} FROM llm_proposal_artifacts "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR status = $2) "
                "ORDER BY created_at DESC LIMIT $3",
                task_id,
                status,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_proposal(r) for r in rows]

    async def get_latest_proposal(self, task_id: str) -> LLMProposalArtifact | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_PROPOSAL_COLUMNS} FROM llm_proposal_artifacts "
                "WHERE task_id = $1 ORDER BY created_at DESC LIMIT 1",
                task_id,
            )
        finally:
            await conn.close()
        return _row_to_proposal(row) if row else None

    # ------------------------------------------------------------------
    # llm_usage_records
    # ------------------------------------------------------------------

    async def record_usage(
        self,
        *,
        task_id: str,
        provider: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> LLMUsageRecord:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_usage_records "
                "(task_id, provider, model_name, prompt_tokens, completion_tokens, "
                " total_tokens, estimated_cost) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                f"RETURNING {_USAGE_COLUMNS}",
                task_id,
                provider,
                model_name,
                int(prompt_tokens),
                int(completion_tokens),
                int(total_tokens),
                float(estimated_cost),
            )
        finally:
            await conn.close()
        return _row_to_usage(row)

    async def list_usage(
        self,
        *,
        task_id: str | None = None,
        provider: str | None = None,
        limit: int = 100,
    ) -> list[LLMUsageRecord]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_USAGE_COLUMNS} FROM llm_usage_records "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR provider = $2) "
                "ORDER BY created_at DESC LIMIT $3",
                task_id,
                provider,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_usage(r) for r in rows]

    async def usage_summary(self, *, task_id: str | None = None) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT "
                " COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
                " COALESCE(SUM(completion_tokens), 0) AS completion_tokens, "
                " COALESCE(SUM(total_tokens), 0) AS total_tokens, "
                " COALESCE(SUM(estimated_cost), 0) AS estimated_cost, "
                " COUNT(*) AS records "
                "FROM llm_usage_records "
                "WHERE ($1::text IS NULL OR task_id = $1)",
                task_id,
            )
        finally:
            await conn.close()
        return {
            "prompt_tokens": int(row["prompt_tokens"] or 0),
            "completion_tokens": int(row["completion_tokens"] or 0),
            "total_tokens": int(row["total_tokens"] or 0),
            "estimated_cost": float(row["estimated_cost"] or 0.0),
            "records": int(row["records"] or 0),
        }

    # ------------------------------------------------------------------
    # /operations/summary support
    # ------------------------------------------------------------------

    async def counts(self) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT "
                " (SELECT COUNT(*) FROM llm_interactions) AS total_interactions, "
                " (SELECT COUNT(*) FROM llm_proposal_artifacts) AS total_proposals, "
                " (SELECT COUNT(*) FROM llm_proposal_artifacts WHERE status='blocked') "
                "    AS blocked_proposals, "
                " (SELECT COUNT(*) FROM llm_proposal_artifacts WHERE status='policy_passed') "
                "    AS policy_passed_proposals, "
                " (SELECT COUNT(*) FROM llm_proposal_artifacts "
                "    WHERE status='accepted_for_workspace') AS accepted_proposals, "
                " (SELECT COALESCE(SUM(total_tokens), 0) FROM llm_usage_records) "
                "    AS total_tokens, "
                " (SELECT COALESCE(SUM(estimated_cost), 0) FROM llm_usage_records) "
                "    AS estimated_cost"
            )
        finally:
            await conn.close()
        return {
            "total_interactions": int(row["total_interactions"] or 0),
            "total_proposals": int(row["total_proposals"] or 0),
            "blocked_proposals": int(row["blocked_proposals"] or 0),
            "policy_passed_proposals": int(row["policy_passed_proposals"] or 0),
            "accepted_proposals": int(row["accepted_proposals"] or 0),
            "total_tokens": int(row["total_tokens"] or 0),
            "estimated_cost": float(row["estimated_cost"] or 0.0),
        }
