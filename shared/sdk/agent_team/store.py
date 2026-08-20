"""Step AT-M2-TEAM-CORE -- asyncpg store for runtime team identity, collaboration and routing.

Persistence only: no audit, no events, no routing logic. Follows the existing store convention
(connect per call, ``DATABASE_URL`` from the environment, plain dict rows).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_team.capabilities import AgentCapabilityDeclaration
from shared.sdk.agent_team.models import assert_content_is_safe
from shared.sdk.agent_team.router import RoutingCandidate, RoutingDecision

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _json(value: Any) -> Any:
    """asyncpg returns JSONB as a string unless a codec is registered."""
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value


class TeamStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- identity ------------------------------------------------------------------------------

    async def register_agent(self, declaration: AgentCapabilityDeclaration) -> dict[str, Any]:
        """Idempotently give one runtime agent a principal and a profile.

        Keyed on ``agent_key``: re-registering an agent updates its declared capabilities rather
        than minting a second principal for the same worker.
        """
        conn = await self._connect()
        try:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT agent_id, principal_id FROM agent_profiles WHERE agent_key=$1",
                    declaration.agent_key,
                )
                if existing is None:
                    principal_id = await conn.fetchval(
                        """
                        INSERT INTO actor_principals (principal_type, display_name)
                        VALUES ('runtime_agent', $1)
                        RETURNING principal_id
                        """,
                        declaration.agent_key,
                    )
                else:
                    principal_id = existing["principal_id"]
                row = await conn.fetchrow(
                    """
                    INSERT INTO agent_profiles
                      (principal_id, agent_key, role, capabilities, transport_stream,
                       tool_policy_profile, model_provider_ref)
                    VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7)
                    ON CONFLICT (agent_key) DO UPDATE SET
                      role=EXCLUDED.role,
                      capabilities=EXCLUDED.capabilities,
                      transport_stream=EXCLUDED.transport_stream,
                      tool_policy_profile=EXCLUDED.tool_policy_profile,
                      model_provider_ref=EXCLUDED.model_provider_ref,
                      updated_at=now()
                    RETURNING agent_id, principal_id, agent_key, role, capabilities,
                              transport_stream, status
                    """,
                    principal_id,
                    declaration.agent_key,
                    declaration.role,
                    json.dumps(list(declaration.capabilities)),
                    declaration.transport_stream,
                    declaration.tool_policy_profile,
                    declaration.model_provider_ref,
                )
            return self._profile_row(row)
        finally:
            await conn.close()

    async def set_agent_capabilities(
        self, agent_key: str, capabilities: tuple[str, ...]
    ) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE agent_profiles SET capabilities=$2::jsonb, updated_at=now()
                WHERE agent_key=$1
                RETURNING agent_id, principal_id, agent_key, role, capabilities,
                          transport_stream, status
                """,
                agent_key,
                json.dumps(list(capabilities)),
            )
            return self._profile_row(row) if row else None
        finally:
            await conn.close()

    # --- team membership -----------------------------------------------------------------------

    async def add_member(
        self, project_id: str, agent_key: str, functional_role: str | None = None
    ) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            profile = await conn.fetchrow(
                "SELECT principal_id, role FROM agent_profiles WHERE agent_key=$1", agent_key
            )
            if profile is None:
                return None
            row = await conn.fetchrow(
                """
                INSERT INTO project_team_memberships
                  (project_id, agent_principal_id, functional_role)
                VALUES ($1,$2,$3)
                ON CONFLICT (project_id, agent_principal_id) DO UPDATE SET
                  functional_role=EXCLUDED.functional_role,
                  membership_state='active',
                  left_at=NULL
                RETURNING membership_id, project_id, agent_principal_id, functional_role,
                          membership_state, joined_at, left_at
                """,
                _uuid(project_id),
                profile["principal_id"],
                functional_role or profile["role"],
            )
            return dict(row)
        finally:
            await conn.close()

    async def set_membership_state(
        self, project_id: str, agent_key: str, state: str
    ) -> dict[str, Any] | None:
        """Move a member's state. Leaving stamps ``left_at`` rather than deleting the row."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE project_team_memberships m
                SET membership_state=$3,
                    left_at = CASE WHEN $3 = 'left' THEN now() ELSE NULL END
                FROM agent_profiles p
                WHERE m.agent_principal_id = p.principal_id
                  AND m.project_id=$1 AND p.agent_key=$2
                RETURNING m.membership_id, m.project_id, m.agent_principal_id, m.functional_role,
                          m.membership_state, m.joined_at, m.left_at
                """,
                _uuid(project_id),
                agent_key,
                state,
            )
            return dict(row) if row else None
        finally:
            await conn.close()

    async def list_team(self, project_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT m.membership_id, m.project_id, m.agent_principal_id, m.functional_role,
                       m.membership_state, m.joined_at, m.left_at,
                       p.agent_key, p.role, p.capabilities, p.transport_stream,
                       p.status AS profile_status, a.display_name, a.principal_type
                FROM project_team_memberships m
                JOIN agent_profiles p ON p.principal_id = m.agent_principal_id
                JOIN actor_principals a ON a.principal_id = m.agent_principal_id
                WHERE m.project_id=$1
                ORDER BY p.agent_key
                """,
                _uuid(project_id),
            )
            return [self._member_row(row) for row in rows]
        finally:
            await conn.close()

    async def routing_candidates(self, project_id: str) -> list[RoutingCandidate]:
        """The team as the router sees it."""
        return [
            RoutingCandidate(
                principal_id=str(member["agent_principal_id"]),
                agent_key=member["agent_key"],
                role=member["functional_role"],
                capabilities=frozenset(member["capabilities"]),
                transport_stream=member["transport_stream"],
                membership_state=member["membership_state"],
                profile_status=member["profile_status"],
            )
            for member in await self.list_team(project_id)
        ]

    # --- collaboration -------------------------------------------------------------------------

    async def open_thread(
        self,
        *,
        project_id: str,
        goal_ref: str,
        thread_type: str,
        work_item_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO conversation_threads
                  (project_id, goal_ref, thread_type, work_item_id, run_id)
                VALUES ($1,$2,$3,$4,$5)
                RETURNING thread_id, project_id, goal_ref, thread_type, work_item_id, run_id,
                          state, created_at
                """,
                _uuid(project_id),
                goal_ref,
                thread_type,
                _uuid(work_item_id) if work_item_id else None,
                run_id,
            )
            return dict(row)
        finally:
            await conn.close()

    async def post_message(self, message: dict[str, Any]) -> dict[str, Any]:
        # Enforced here too, not just in the DTO: callers build a plain dict, so the model
        # validator alone would leave the prohibition bypassable by construction.
        assert_content_is_safe(message.get("content"), "content")
        assert_content_is_safe(message.get("artifact_refs"), "artifact_refs")
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO team_messages
                  (thread_id, project_id, sender_principal_id, recipient_principal_id,
                   recipient_role, recipient_team, parent_message_id, message_type, summary,
                   content, artifact_refs, audit_ref)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12)
                RETURNING message_id, thread_id, project_id, sender_principal_id,
                          recipient_principal_id, recipient_role, recipient_team,
                          parent_message_id, message_type, summary, content, artifact_refs,
                          audit_ref, correlation_id, created_at
                """,
                _uuid(message["thread_id"]),
                _uuid(message["project_id"]),
                _uuid(message["sender_principal_id"]),
                (
                    _uuid(message["recipient_principal_id"])
                    if message.get("recipient_principal_id")
                    else None
                ),
                message.get("recipient_role"),
                bool(message.get("recipient_team", False)),
                _uuid(message["parent_message_id"]) if message.get("parent_message_id") else None,
                message["message_type"],
                message["summary"],
                json.dumps(message.get("content") or {}),
                json.dumps(message.get("artifact_refs") or {}),
                message.get("audit_ref"),
            )
            return self._message_row(row)
        finally:
            await conn.close()

    async def list_messages(
        self, project_id: str, thread_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            if thread_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM team_messages
                    WHERE project_id=$1 AND thread_id=$2
                    ORDER BY created_at LIMIT $3
                    """,
                    _uuid(project_id),
                    _uuid(thread_id),
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM team_messages WHERE project_id=$1 ORDER BY created_at LIMIT $2",
                    _uuid(project_id),
                    limit,
                )
            return [self._message_row(row) for row in rows]
        finally:
            await conn.close()

    async def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO team_decisions
                  (project_id, thread_id, proposed_by, options_considered, selected_option,
                   rationale_summary, dissent_summary, audit_ref)
                VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8)
                RETURNING decision_id, project_id, thread_id, proposed_by, options_considered,
                          selected_option, rationale_summary, dissent_summary, audit_ref,
                          created_at
                """,
                _uuid(decision["project_id"]),
                _uuid(decision["thread_id"]),
                _uuid(decision["proposed_by"]),
                json.dumps(decision.get("options_considered") or []),
                decision["selected_option"],
                decision["rationale_summary"],
                decision.get("dissent_summary"),
                decision.get("audit_ref"),
            )
            record = dict(row)
            record["options_considered"] = _json(record.get("options_considered"))
            return record
        finally:
            await conn.close()

    async def offer_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_handoffs
                  (project_id, work_item_id, from_principal_id, to_principal_id, reason,
                   context_refs, audit_ref)
                VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)
                RETURNING handoff_id, project_id, work_item_id, from_principal_id,
                          to_principal_id, reason, context_refs, state, audit_ref, created_at,
                          accepted_at
                """,
                _uuid(handoff["project_id"]),
                _uuid(handoff["work_item_id"]) if handoff.get("work_item_id") else None,
                _uuid(handoff["from_principal_id"]),
                _uuid(handoff["to_principal_id"]),
                handoff["reason"],
                json.dumps(handoff.get("context_refs") or {}),
                handoff.get("audit_ref"),
            )
            record = dict(row)
            record["context_refs"] = _json(record.get("context_refs"))
            return record
        finally:
            await conn.close()

    async def accept_handoff(self, handoff_id: str) -> dict[str, Any] | None:
        """Ownership transfers here, and only here."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE agent_handoffs SET state='accepted', accepted_at=now()
                WHERE handoff_id=$1 AND state='offered'
                RETURNING handoff_id, project_id, work_item_id, from_principal_id,
                          to_principal_id, reason, state, accepted_at
                """,
                _uuid(handoff_id),
            )
            return dict(row) if row else None
        finally:
            await conn.close()

    # --- routing evidence ----------------------------------------------------------------------

    async def record_routing_decision(
        self,
        *,
        project_id: str,
        decision: RoutingDecision,
        work_item_id: str | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_routing_decisions
                  (project_id, work_item_id, task_id, workflow_id, requested_capability, outcome,
                   selected_principal_id, selected_role, selected_stream, reason,
                   candidates_considered, audit_ref)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
                RETURNING routing_decision_id, project_id, work_item_id, task_id, workflow_id,
                          requested_capability, outcome, selected_principal_id, selected_role,
                          selected_stream, reason, candidates_considered, audit_ref,
                          correlation_id, created_at
                """,
                _uuid(project_id),
                _uuid(work_item_id) if work_item_id else None,
                task_id,
                workflow_id,
                decision.requested_capability,
                decision.outcome,
                _uuid(decision.selected_principal_id) if decision.selected_principal_id else None,
                decision.selected_role,
                decision.selected_stream,
                decision.reason,
                json.dumps(list(decision.candidates_considered)),
                audit_ref,
            )
            record = dict(row)
            record["candidates_considered"] = _json(record.get("candidates_considered"))
            return record
        finally:
            await conn.close()

    async def list_routing_decisions(
        self, project_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM agent_routing_decisions
                WHERE project_id=$1 ORDER BY created_at DESC LIMIT $2
                """,
                _uuid(project_id),
                limit,
            )
            records = []
            for row in rows:
                record = dict(row)
                record["candidates_considered"] = _json(record.get("candidates_considered"))
                records.append(record)
            return records
        finally:
            await conn.close()

    # --- row shaping ---------------------------------------------------------------------------

    @staticmethod
    def _profile_row(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["capabilities"] = tuple(_json(record.get("capabilities")) or ())
        return record

    @staticmethod
    def _member_row(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["capabilities"] = tuple(_json(record.get("capabilities")) or ())
        return record

    @staticmethod
    def _message_row(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["content"] = _json(record.get("content"))
        record["artifact_refs"] = _json(record.get("artifact_refs"))
        return record


__all__ = ["TeamStore"]
