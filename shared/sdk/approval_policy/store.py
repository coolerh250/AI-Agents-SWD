"""asyncpg store for the Stage 31 approval-policy tables.

Connection-per-call. Mirrors the pattern used by ``QAStore`` and
``LLMInteractionStore``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.approval_policy.models import (
    HumanApprovalDecision,
    HumanApprovalPolicy,
    LLMProposalApproval,
    LLMProposalPromotion,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_POLICY_COLUMNS = (
    "policy_id, task_id, workflow_id, scope_type, scope_id, "
    "approval_mode, status, granted_by, granted_at, expires_at, "
    "max_actions, max_files_changed, max_auto_fix_attempts, actions_used, "
    "allowed_stages, allowed_agents, allowed_actions, allowed_paths, "
    "denied_paths, constraints, reason, created_at, updated_at"
)

_DECISION_COLUMNS = (
    "decision_id, policy_id, task_id, workflow_id, proposal_id, "
    "promotion_id, action_type, decision, decided_by, decided_at, "
    "reason, safety_snapshot, created_at"
)

_APPROVAL_COLUMNS = (
    "approval_id, proposal_id, task_id, workflow_id, approval_mode, "
    "policy_id, requested_by, requested_at, approved_by, approved_at, "
    "rejected_by, rejected_at, status, reason, safety_snapshot, "
    "created_at, updated_at"
)

_PROMOTION_COLUMNS = (
    "promotion_id, proposal_id, approval_id, policy_id, task_id, "
    "workflow_id, workspace_id, status, promoted_by, promoted_at, "
    "promotion_mode, promoted_files, validation_result, qa_run_id, "
    "pr_draft_id, error, created_at, updated_at"
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


def _row_to_policy(row: asyncpg.Record) -> HumanApprovalPolicy:
    return HumanApprovalPolicy(
        policy_id=str(row["policy_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        scope_type=row["scope_type"] or "task",
        scope_id=row["scope_id"] or "",
        approval_mode=row["approval_mode"] or "per_action",
        status=row["status"] or "pending",
        granted_by=row["granted_by"] or "",
        granted_at=_iso(row["granted_at"]),
        expires_at=_iso(row["expires_at"]),
        max_actions=row["max_actions"],
        max_files_changed=row["max_files_changed"],
        max_auto_fix_attempts=row["max_auto_fix_attempts"],
        actions_used=int(row["actions_used"] or 0),
        allowed_stages=_decode_json(row["allowed_stages"], []) or [],
        allowed_agents=_decode_json(row["allowed_agents"], []) or [],
        allowed_actions=_decode_json(row["allowed_actions"], []) or [],
        allowed_paths=_decode_json(row["allowed_paths"], []) or [],
        denied_paths=_decode_json(row["denied_paths"], []) or [],
        constraints=_decode_json(row["constraints"], {}) or {},
        reason=row["reason"],
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


def _row_to_decision(row: asyncpg.Record) -> HumanApprovalDecision:
    return HumanApprovalDecision(
        decision_id=str(row["decision_id"]),
        policy_id=str(row["policy_id"]) if row["policy_id"] is not None else None,
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        proposal_id=str(row["proposal_id"]) if row["proposal_id"] is not None else None,
        promotion_id=str(row["promotion_id"]) if row["promotion_id"] is not None else None,
        action_type=row["action_type"] or "",
        decision=row["decision"] or "approved",
        decided_by=row["decided_by"] or "",
        decided_at=_iso(row["decided_at"]),
        reason=row["reason"],
        safety_snapshot=_decode_json(row["safety_snapshot"], {}) or {},
        created_at=_iso(row["created_at"]),
    )


def _row_to_approval(row: asyncpg.Record) -> LLMProposalApproval:
    return LLMProposalApproval(
        approval_id=str(row["approval_id"]),
        proposal_id=str(row["proposal_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        approval_mode=row["approval_mode"] or "per_action",
        policy_id=str(row["policy_id"]) if row["policy_id"] is not None else None,
        requested_by=row["requested_by"] or "",
        requested_at=_iso(row["requested_at"]),
        approved_by=row["approved_by"],
        approved_at=_iso(row["approved_at"]),
        rejected_by=row["rejected_by"],
        rejected_at=_iso(row["rejected_at"]),
        status=row["status"] or "pending",
        reason=row["reason"],
        safety_snapshot=_decode_json(row["safety_snapshot"], {}) or {},
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


def _row_to_promotion(row: asyncpg.Record) -> LLMProposalPromotion:
    return LLMProposalPromotion(
        promotion_id=str(row["promotion_id"]),
        proposal_id=str(row["proposal_id"]),
        approval_id=str(row["approval_id"]) if row["approval_id"] is not None else None,
        policy_id=str(row["policy_id"]) if row["policy_id"] is not None else None,
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]) if row["workspace_id"] is not None else None,
        status=row["status"] or "requested",
        promoted_by=row["promoted_by"] or "",
        promoted_at=_iso(row["promoted_at"]),
        promotion_mode=row["promotion_mode"] or "manual",
        promoted_files=_decode_json(row["promoted_files"], []) or [],
        validation_result=_decode_json(row["validation_result"], {}) or {},
        qa_run_id=str(row["qa_run_id"]) if row["qa_run_id"] is not None else None,
        pr_draft_id=str(row["pr_draft_id"]) if row["pr_draft_id"] is not None else None,
        error=row["error"],
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


class ApprovalPolicyStore:
    """Persistence surface for the four Stage 31 tables."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # human_approval_policies
    # ------------------------------------------------------------------

    async def create_policy(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        scope_type: str,
        scope_id: str,
        approval_mode: str,
        granted_by: str,
        status: str = "pending",
        expires_at: Any = None,
        max_actions: int | None = None,
        max_files_changed: int | None = None,
        max_auto_fix_attempts: int | None = None,
        allowed_stages: list[str] | None = None,
        allowed_agents: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
        constraints: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> HumanApprovalPolicy:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO human_approval_policies "
                "(task_id, workflow_id, scope_type, scope_id, approval_mode, "
                " status, granted_by, expires_at, max_actions, "
                " max_files_changed, max_auto_fix_attempts, allowed_stages, "
                " allowed_agents, allowed_actions, allowed_paths, denied_paths, "
                " constraints, reason) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8::timestamptz, $9, "
                "        $10, $11, $12::jsonb, $13::jsonb, $14::jsonb, "
                "        $15::jsonb, $16::jsonb, $17::jsonb, $18) "
                f"RETURNING {_POLICY_COLUMNS}",
                task_id,
                workflow_id,
                scope_type,
                scope_id,
                approval_mode,
                status,
                granted_by,
                expires_at,
                max_actions,
                max_files_changed,
                max_auto_fix_attempts,
                json.dumps(allowed_stages or []),
                json.dumps(allowed_agents or []),
                json.dumps(allowed_actions or []),
                json.dumps(allowed_paths or []),
                json.dumps(denied_paths or []),
                json.dumps(constraints or {}),
                reason,
            )
        finally:
            await conn.close()
        return _row_to_policy(row)

    async def get_policy(self, policy_id: str) -> HumanApprovalPolicy | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_POLICY_COLUMNS} FROM human_approval_policies "
                "WHERE policy_id = $1::uuid",
                policy_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_policy(row) if row else None

    async def list_policies(
        self,
        *,
        task_id: str | None = None,
        workflow_id: str | None = None,
        status: str | None = None,
        approval_mode: str | None = None,
        limit: int = 100,
    ) -> list[HumanApprovalPolicy]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_POLICY_COLUMNS} FROM human_approval_policies "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR workflow_id = $2) "
                "AND ($3::text IS NULL OR status = $3) "
                "AND ($4::text IS NULL OR approval_mode = $4) "
                "ORDER BY created_at DESC LIMIT $5",
                task_id,
                workflow_id,
                status,
                approval_mode,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_policy(r) for r in rows]

    async def list_active_policies_for(self, *, task_id: str) -> list[HumanApprovalPolicy]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_POLICY_COLUMNS} FROM human_approval_policies "
                "WHERE task_id = $1 AND status = 'active' "
                "AND (expires_at IS NULL OR expires_at > now()) "
                "ORDER BY created_at DESC",
                task_id,
            )
        finally:
            await conn.close()
        return [_row_to_policy(r) for r in rows]

    async def update_policy_status(
        self,
        policy_id: str,
        *,
        status: str,
    ) -> HumanApprovalPolicy | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE human_approval_policies SET "
                " status = $2, updated_at = now() "
                f"WHERE policy_id = $1::uuid RETURNING {_POLICY_COLUMNS}",
                policy_id,
                status,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_policy(row) if row else None

    async def increment_actions_used(self, policy_id: str) -> HumanApprovalPolicy | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE human_approval_policies SET "
                " actions_used = actions_used + 1, updated_at = now() "
                f"WHERE policy_id = $1::uuid RETURNING {_POLICY_COLUMNS}",
                policy_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_policy(row) if row else None

    # ------------------------------------------------------------------
    # human_approval_decisions
    # ------------------------------------------------------------------

    async def record_decision(
        self,
        *,
        policy_id: str | None,
        task_id: str,
        workflow_id: str | None,
        proposal_id: str | None = None,
        promotion_id: str | None = None,
        action_type: str,
        decision: str,
        decided_by: str,
        reason: str | None = None,
        safety_snapshot: dict[str, Any] | None = None,
    ) -> HumanApprovalDecision:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO human_approval_decisions "
                "(policy_id, task_id, workflow_id, proposal_id, promotion_id, "
                " action_type, decision, decided_by, reason, safety_snapshot) "
                "VALUES ($1::uuid, $2, $3, $4::uuid, $5::uuid, $6, $7, $8, "
                "        $9, $10::jsonb) "
                f"RETURNING {_DECISION_COLUMNS}",
                policy_id,
                task_id,
                workflow_id,
                proposal_id,
                promotion_id,
                action_type,
                decision,
                decided_by,
                reason,
                json.dumps(safety_snapshot or {}),
            )
        finally:
            await conn.close()
        return _row_to_decision(row)

    async def list_decisions(
        self,
        *,
        task_id: str | None = None,
        policy_id: str | None = None,
        limit: int = 200,
    ) -> list[HumanApprovalDecision]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_DECISION_COLUMNS} FROM human_approval_decisions "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::uuid IS NULL OR policy_id = $2::uuid) "
                "ORDER BY created_at DESC LIMIT $3",
                task_id,
                policy_id,
                limit,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_decision(r) for r in rows]

    # ------------------------------------------------------------------
    # llm_proposal_approvals
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        *,
        proposal_id: str,
        task_id: str,
        workflow_id: str | None,
        approval_mode: str = "per_action",
        policy_id: str | None = None,
        requested_by: str = "",
        safety_snapshot: dict[str, Any] | None = None,
    ) -> LLMProposalApproval:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_proposal_approvals "
                "(proposal_id, task_id, workflow_id, approval_mode, policy_id, "
                " requested_by, status, safety_snapshot) "
                "VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6, 'pending', "
                "        $7::jsonb) "
                f"RETURNING {_APPROVAL_COLUMNS}",
                proposal_id,
                task_id,
                workflow_id,
                approval_mode,
                policy_id,
                requested_by,
                json.dumps(safety_snapshot or {}),
            )
        finally:
            await conn.close()
        return _row_to_approval(row)

    async def approve_proposal(
        self,
        approval_id: str,
        *,
        approved_by: str,
        reason: str | None = None,
    ) -> LLMProposalApproval | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_proposal_approvals SET "
                " status = 'approved', approved_by = $2, approved_at = now(), "
                " reason = COALESCE($3, reason), updated_at = now() "
                f"WHERE approval_id = $1::uuid RETURNING {_APPROVAL_COLUMNS}",
                approval_id,
                approved_by,
                reason,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_approval(row) if row else None

    async def reject_proposal(
        self,
        approval_id: str,
        *,
        rejected_by: str,
        reason: str | None = None,
    ) -> LLMProposalApproval | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_proposal_approvals SET "
                " status = 'rejected', rejected_by = $2, rejected_at = now(), "
                " reason = COALESCE($3, reason), updated_at = now() "
                f"WHERE approval_id = $1::uuid RETURNING {_APPROVAL_COLUMNS}",
                approval_id,
                rejected_by,
                reason,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_approval(row) if row else None

    async def get_latest_approval(self, proposal_id: str) -> LLMProposalApproval | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_APPROVAL_COLUMNS} FROM llm_proposal_approvals "
                "WHERE proposal_id = $1::uuid "
                "ORDER BY created_at DESC LIMIT 1",
                proposal_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_approval(row) if row else None

    async def list_approvals(
        self,
        *,
        task_id: str | None = None,
        proposal_id: str | None = None,
        limit: int = 100,
    ) -> list[LLMProposalApproval]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_APPROVAL_COLUMNS} FROM llm_proposal_approvals "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::uuid IS NULL OR proposal_id = $2::uuid) "
                "ORDER BY created_at DESC LIMIT $3",
                task_id,
                proposal_id,
                limit,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_approval(r) for r in rows]

    # ------------------------------------------------------------------
    # llm_proposal_promotions
    # ------------------------------------------------------------------

    async def create_promotion(
        self,
        *,
        proposal_id: str,
        task_id: str,
        workflow_id: str | None,
        approval_id: str | None = None,
        policy_id: str | None = None,
        workspace_id: str | None = None,
        promotion_mode: str = "manual",
        promoted_by: str = "",
        status: str = "requested",
        promoted_files: list[dict[str, Any]] | None = None,
        validation_result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> LLMProposalPromotion:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO llm_proposal_promotions "
                "(proposal_id, approval_id, policy_id, task_id, workflow_id, "
                " workspace_id, status, promoted_by, promotion_mode, "
                " promoted_files, validation_result, error) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::uuid, $7, "
                "        $8, $9, $10::jsonb, $11::jsonb, $12) "
                f"RETURNING {_PROMOTION_COLUMNS}",
                proposal_id,
                approval_id,
                policy_id,
                task_id,
                workflow_id,
                workspace_id,
                status,
                promoted_by,
                promotion_mode,
                json.dumps(promoted_files or []),
                json.dumps(validation_result or {}),
                error,
            )
        finally:
            await conn.close()
        return _row_to_promotion(row)

    async def update_promotion(
        self,
        promotion_id: str,
        *,
        status: str | None = None,
        workspace_id: str | None = None,
        promoted_at_now: bool = False,
        promoted_files: list[dict[str, Any]] | None = None,
        validation_result: dict[str, Any] | None = None,
        qa_run_id: str | None = None,
        pr_draft_id: str | None = None,
        error: str | None = None,
    ) -> LLMProposalPromotion | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE llm_proposal_promotions SET "
                " status = COALESCE($2, status), "
                " workspace_id = COALESCE($3::uuid, workspace_id), "
                " promoted_at = CASE WHEN $4 THEN now() ELSE promoted_at END, "
                " promoted_files = COALESCE($5::jsonb, promoted_files), "
                " validation_result = COALESCE($6::jsonb, validation_result), "
                " qa_run_id = COALESCE($7::uuid, qa_run_id), "
                " pr_draft_id = COALESCE($8::uuid, pr_draft_id), "
                " error = COALESCE($9, error), "
                " updated_at = now() "
                f"WHERE promotion_id = $1::uuid RETURNING {_PROMOTION_COLUMNS}",
                promotion_id,
                status,
                workspace_id,
                promoted_at_now,
                json.dumps(promoted_files) if promoted_files is not None else None,
                (json.dumps(validation_result) if validation_result is not None else None),
                qa_run_id,
                pr_draft_id,
                error,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_promotion(row) if row else None

    async def get_promotion(self, promotion_id: str) -> LLMProposalPromotion | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_PROMOTION_COLUMNS} FROM llm_proposal_promotions "
                "WHERE promotion_id = $1::uuid",
                promotion_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_promotion(row) if row else None

    async def list_promotions(
        self,
        *,
        task_id: str | None = None,
        proposal_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[LLMProposalPromotion]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_PROMOTION_COLUMNS} FROM llm_proposal_promotions "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::uuid IS NULL OR proposal_id = $2::uuid) "
                "AND ($3::text IS NULL OR status = $3) "
                "ORDER BY created_at DESC LIMIT $4",
                task_id,
                proposal_id,
                status,
                limit,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_promotion(r) for r in rows]

    # ------------------------------------------------------------------
    # /operations/summary support
    # ------------------------------------------------------------------

    async def counts(self) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT "
                " (SELECT COUNT(*) FROM human_approval_policies) AS total_policies, "
                " (SELECT COUNT(*) FROM human_approval_policies "
                "    WHERE status='active') AS active_policies, "
                " (SELECT COUNT(*) FROM human_approval_policies "
                "    WHERE status='revoked') AS revoked_policies, "
                " (SELECT COUNT(*) FROM human_approval_policies "
                "    WHERE approval_mode='delegated') AS delegated_policies, "
                " (SELECT COUNT(*) FROM human_approval_policies "
                "    WHERE approval_mode='per_feature') AS per_feature_policies, "
                " (SELECT COUNT(*) FROM human_approval_policies "
                "    WHERE approval_mode='per_stage') AS per_stage_policies, "
                " (SELECT COUNT(*) FROM human_approval_decisions) AS total_decisions, "
                " (SELECT COUNT(*) FROM human_approval_decisions "
                "    WHERE decision='approved') AS approved_decisions, "
                " (SELECT COUNT(*) FROM human_approval_decisions "
                "    WHERE decision='rejected') AS rejected_decisions, "
                " (SELECT COUNT(*) FROM llm_proposal_promotions) AS total_promotions, "
                " (SELECT COUNT(*) FROM llm_proposal_promotions "
                "    WHERE status IN ('promoted','qa_passed')) AS promoted_count, "
                " (SELECT COUNT(*) FROM llm_proposal_promotions "
                "    WHERE status='blocked_by_policy') AS blocked_by_policy_count"
            )
        finally:
            await conn.close()
        return {
            "total_policies": int(row["total_policies"] or 0),
            "active_policies": int(row["active_policies"] or 0),
            "revoked_policies": int(row["revoked_policies"] or 0),
            "delegated_policies": int(row["delegated_policies"] or 0),
            "per_feature_policies": int(row["per_feature_policies"] or 0),
            "per_stage_policies": int(row["per_stage_policies"] or 0),
            "total_decisions": int(row["total_decisions"] or 0),
            "approved_decisions": int(row["approved_decisions"] or 0),
            "rejected_decisions": int(row["rejected_decisions"] or 0),
            "total_promotions": int(row["total_promotions"] or 0),
            "promoted_count": int(row["promoted_count"] or 0),
            "blocked_by_policy_count": int(row["blocked_by_policy_count"] or 0),
        }
