"""Stage 52 -- asyncpg store for operator-action governance tables.

Persists identities, role assignments, sessions (hash only), action requests /
executions / confirmations (nonce hash only), review notes, verification reruns,
and the delivery-package acceptance mutations. No raw token / secret stored.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def _dec(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


class OperatorActionStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ----------------------------------------------------------- identities
    async def upsert_identity(
        self,
        identity_key: str,
        *,
        display_name: str | None = None,
        identity_source: str = "test_local",
        roles: list[str] | None = None,
        environment_scope: str = "test",
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_identities (identity_key, display_name, identity_source) "
                "VALUES ($1,$2,$3) ON CONFLICT (identity_key) DO UPDATE SET "
                " display_name=EXCLUDED.display_name, identity_source=EXCLUDED.identity_source "
                "RETURNING id",
                identity_key,
                display_name or identity_key,
                identity_source,
            )
            iid = str(row["id"])
            for role in roles or []:
                await conn.execute(
                    "INSERT INTO operator_role_assignments (identity_id, role, environment_scope) "
                    "VALUES ($1::uuid,$2,$3) ON CONFLICT (identity_id, role, environment_scope) "
                    "DO UPDATE SET active=true",
                    iid,
                    role,
                    environment_scope,
                )
        finally:
            await conn.close()
        return iid

    async def get_identity(self, identity_key: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, identity_key, display_name, identity_source, status "
                "FROM operator_identities WHERE identity_key=$1",
                identity_key,
            )
            if not row:
                return None
            roles = await conn.fetch(
                "SELECT role FROM operator_role_assignments "
                "WHERE identity_id=$1::uuid AND active=true",
                str(row["id"]),
            )
        finally:
            await conn.close()
        return {
            "id": str(row["id"]),
            "identity_key": row["identity_key"],
            "display_name": row["display_name"],
            "identity_source": row["identity_source"],
            "status": row["status"],
            "roles": [r["role"] for r in roles],
        }

    # -------------------------------------------------------------- sessions
    async def create_session(
        self,
        identity_key: str,
        session_hash: str,
        expires_at_iso: str,
    ) -> str:
        conn = await self._connect()
        try:
            # Idempotent on session_hash: a same-identity re-login within the same second
            # yields an identical signed token (and thus hash) -- that is the same logical
            # session, so refresh its expiry instead of raising a UniqueViolation 500.
            row = await conn.fetchrow(
                "INSERT INTO admin_console_sessions (identity_id, session_hash, expires_at) "
                "SELECT id, $2, $3::text::timestamptz FROM operator_identities "
                "WHERE identity_key=$1 "
                "ON CONFLICT (session_hash) DO UPDATE "
                "SET expires_at=EXCLUDED.expires_at, status='active', revoked_at=NULL "
                "RETURNING id",
                identity_key,
                session_hash,
                expires_at_iso,
            )
        finally:
            await conn.close()
        return str(row["id"]) if row else ""

    async def get_session_by_hash(self, session_hash: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT s.id, s.status, s.expires_at, i.identity_key, i.status AS identity_status "
                "FROM admin_console_sessions s JOIN operator_identities i ON i.id=s.identity_id "
                "WHERE s.session_hash=$1",
                session_hash,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "status": row["status"],
            "expires_at": _iso(row["expires_at"]),
            "identity_key": row["identity_key"],
            "identity_status": row["identity_status"],
        }

    async def revoke_session(self, session_hash: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE admin_console_sessions SET status='revoked', revoked_at=now() "
                "WHERE session_hash=$1",
                session_hash,
            )
        finally:
            await conn.close()

    # -------------------------------------------------------- action requests
    async def find_action_by_idempotency(self, idempotency_key: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, action_key, action_type, status, policy_status, confirmation_status "
                "FROM operator_action_requests WHERE idempotency_key=$1",
                idempotency_key,
            )
        finally:
            await conn.close()
        return self._action_row(row) if row else None

    async def create_action_request(self, req, *, identity_id: str | None) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_action_requests "
                "(action_key, identity_id, action_type, target_type, target_id, reason, "
                " requested_payload, risk_level, policy_status, approval_status, "
                " confirmation_status, idempotency_key, status, metadata) "
                "VALUES ($1,$2::uuid,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14::jsonb) "
                "RETURNING id",
                req.action_key,
                identity_id,
                req.action_type,
                req.target_type,
                req.target_id,
                req.reason,
                json.dumps(req.requested_payload or {}),
                req.risk_level,
                req.policy_status,
                req.approval_status,
                req.confirmation_status,
                req.idempotency_key,
                req.status,
                json.dumps(req.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def update_action_status(
        self,
        action_id: str,
        *,
        status: str,
        policy_status: str | None = None,
        confirmation_status: str | None = None,
        completed: bool = False,
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE operator_action_requests SET status=$2, "
                " policy_status=COALESCE($3, policy_status), "
                " confirmation_status=COALESCE($4, confirmation_status), "
                " completed_at=CASE WHEN $5 THEN now() ELSE completed_at END "
                "WHERE id=$1::uuid",
                action_id,
                status,
                policy_status,
                confirmation_status,
                completed,
            )
        finally:
            await conn.close()

    async def get_action(self, action_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, action_key, action_type, target_type, target_id, reason, risk_level, "
                " policy_status, approval_status, confirmation_status, status, requested_at, "
                " completed_at FROM operator_action_requests WHERE id=$1::uuid",
                action_id,
            )
        finally:
            await conn.close()
        return self._action_row(row) if row else None

    @staticmethod
    def _action_row(r) -> dict:
        d = {
            "id": str(r["id"]),
            "action_key": r["action_key"],
            "action_type": r["action_type"],
            "status": r["status"],
            "policy_status": r["policy_status"],
            "confirmation_status": r["confirmation_status"],
        }
        for k in ("target_type", "target_id", "reason", "risk_level", "approval_status"):
            if k in r.keys():
                d[k] = r[k]
        if "requested_at" in r.keys():
            d["requested_at"] = _iso(r["requested_at"])
        if "completed_at" in r.keys():
            d["completed_at"] = _iso(r["completed_at"])
        return d

    async def list_actions(self, *, limit: int = 50) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT r.id, r.action_key, r.action_type, r.target_type, r.target_id, r.reason, "
                " r.policy_status, r.status, r.requested_at, r.completed_at, i.identity_key "
                "FROM operator_action_requests r "
                "LEFT JOIN operator_identities i ON i.id=r.identity_id "
                "ORDER BY r.requested_at DESC LIMIT $1",
                max(1, min(int(limit), 200)),
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "action_key": r["action_key"],
                "action_type": r["action_type"],
                "target_type": r["target_type"],
                "target_id": r["target_id"],
                "reason": r["reason"],
                "policy_status": r["policy_status"],
                "status": r["status"],
                "identity_key": r["identity_key"],
                "requested_at": _iso(r["requested_at"]),
                "completed_at": _iso(r["completed_at"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------ executions
    async def create_execution(self, action_id: str, ex) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_action_executions "
                "(action_request_id, execution_type, status, result_summary, error_summary, "
                " completed_at, production_executed, metadata) "
                "VALUES ($1::uuid,$2,$3,$4,$5, now(), $6, $7::jsonb) RETURNING id",
                action_id,
                ex.execution_type,
                ex.status,
                ex.result_summary,
                ex.error_summary,
                ex.production_executed,
                json.dumps(ex.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    # --------------------------------------------------------- confirmations
    async def create_confirmation(
        self,
        action_id: str,
        identity_id: str | None,
        nonce_hash: str,
        expires_at_iso: str,
        confirmation_type: str = "second_confirmation",
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_action_confirmations "
                "(action_request_id, identity_id, confirmation_type, nonce_hash, expires_at) "
                "VALUES ($1::uuid,$2::uuid,$3,$4,$5::text::timestamptz) RETURNING id",
                action_id,
                identity_id,
                confirmation_type,
                nonce_hash,
                expires_at_iso,
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def get_latest_confirmation(self, action_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT c.id, c.nonce_hash, c.used, c.expires_at, i.identity_key "
                "FROM operator_action_confirmations c "
                "LEFT JOIN operator_identities i ON i.id=c.identity_id "
                "WHERE c.action_request_id=$1::uuid ORDER BY c.id DESC LIMIT 1",
                action_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "nonce_hash": row["nonce_hash"],
            "used": row["used"],
            "expires_at": _iso(row["expires_at"]),
            "identity_key": row["identity_key"],
        }

    async def mark_confirmation_used(self, confirmation_id: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE operator_action_confirmations SET used=true, confirmed_at=now() "
                "WHERE id=$1::uuid",
                confirmation_id,
            )
        finally:
            await conn.close()

    # ---------------------------------------------------------- review notes
    async def add_review_note(self, note, *, identity_id: str | None) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_review_notes "
                "(package_id, project_id, identity_id, note_type, summary, metadata) "
                "VALUES ($1::uuid,$2::uuid,$3::uuid,$4,$5,$6::jsonb) RETURNING id",
                note.package_id,
                note.project_id,
                identity_id,
                note.note_type,
                note.summary,
                json.dumps(note.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def list_review_notes(self, package_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT n.note_type, n.summary, n.created_at, i.identity_key "
                "FROM operator_review_notes n "
                "LEFT JOIN operator_identities i ON i.id=n.identity_id "
                "WHERE n.package_id=$1::uuid ORDER BY n.created_at",
                package_id,
            )
        finally:
            await conn.close()
        return [
            {
                "note_type": r["note_type"],
                "summary": r["summary"],
                "identity_key": r["identity_key"],
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]

    # ----------------------------------------------------- verification rerun
    async def create_rerun(self, action_id: str | None, rerun) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO verification_rerun_requests "
                "(action_request_id, verification_key, script_key, status, report_path, "
                " result_marker, exit_code, completed_at, metadata) "
                "VALUES ($1::uuid,$2,$3,$4,$5,$6,$7, now(), $8::jsonb) RETURNING id",
                action_id,
                rerun.verification_key,
                rerun.script_key,
                rerun.status,
                rerun.report_path,
                rerun.result_marker,
                rerun.exit_code,
                json.dumps(rerun.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def list_reruns(self, *, limit: int = 50) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, verification_key, script_key, status, result_marker, exit_code, "
                " started_at, completed_at FROM verification_rerun_requests "
                "ORDER BY started_at DESC LIMIT $1",
                max(1, min(int(limit), 200)),
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "verification_key": r["verification_key"],
                "script_key": r["script_key"],
                "status": r["status"],
                "result_marker": r["result_marker"],
                "exit_code": r["exit_code"],
                "started_at": _iso(r["started_at"]),
                "completed_at": _iso(r["completed_at"]),
            }
            for r in rows
        ]

    async def get_rerun(self, rerun_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, verification_key, script_key, status, result_marker, exit_code, "
                " report_path, started_at, completed_at FROM verification_rerun_requests "
                "WHERE id=$1::uuid",
                rerun_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "verification_key": row["verification_key"],
            "script_key": row["script_key"],
            "status": row["status"],
            "result_marker": row["result_marker"],
            "exit_code": row["exit_code"],
            "report_path": row["report_path"],
            "started_at": _iso(row["started_at"]),
            "completed_at": _iso(row["completed_at"]),
        }

    # ----------------------------------------------------- audit link + dp ops
    async def link_audit(
        self, action_id: str, decision_type: str, audit_log_id: str | None = None
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO operator_action_audit_links "
                "(action_request_id, audit_log_id, decision_type) VALUES ($1::uuid,$2::uuid,$3)",
                action_id,
                audit_log_id,
                decision_type,
            )
        finally:
            await conn.close()

    async def apply_delivery_decision(
        self,
        package_id: str,
        *,
        review_status: str,
        human_acceptance_status: str,
        package_status: str,
        summary: str,
        requested_changes: list | None = None,
    ) -> None:
        """Transactionally update operator_acceptance_reviews + delivery_packages."""
        conn = await self._connect()
        try:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE operator_acceptance_reviews SET review_status=$2, "
                    " review_summary=$3, requested_changes=$4::jsonb, reviewed_at=now() "
                    "WHERE package_id=$1::uuid",
                    package_id,
                    review_status,
                    summary,
                    json.dumps(requested_changes or []),
                )
                await conn.execute(
                    "UPDATE delivery_packages SET human_acceptance_status=$2, status=$3, "
                    " updated_at=now() WHERE id=$1::uuid",
                    package_id,
                    human_acceptance_status,
                    package_status,
                )
        finally:
            await conn.close()


__all__ = ["OperatorActionStore", "DEFAULT_DATABASE_URL"]
