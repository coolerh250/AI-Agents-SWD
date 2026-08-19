"""Step AT-M2-TEAM-CORE -- team formation, addressed messaging and routing, with evidence.

The layer that turns the pure router and the plain store into runtime behaviour: it forms a team
for a project, lets principals address one another, decides successors from capability, and makes
each of those acts durable and auditable.

Every side effect degrades gracefully, matching the rest of the platform: a missing audit service
or event bus must not stop the team from working, and it must not silently turn a routed decision
into an unrouted one either -- the routing record is written to the store first, and only then
announced.
"""

from __future__ import annotations

import contextlib
from typing import Any

from shared.sdk.agent_team import events as team_events
from shared.sdk.agent_team.capabilities import (
    AgentCapabilityDeclaration,
    seed_for,
)
from shared.sdk.agent_team.router import RoutingCandidate, RoutingDecision, RoutingRequest, route
from shared.sdk.agent_team.store import TeamStore


class TeamService:
    def __init__(
        self,
        store: Any | None = None,
        event_bus: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else TeamStore()
        self.event_bus = event_bus
        self.audit_client = audit_client

    # --- side channels -------------------------------------------------------------------------

    async def _publish(
        self, event: str, payload: dict[str, Any], stream: str | None = None
    ) -> None:
        if self.event_bus is None:
            return
        with contextlib.suppress(Exception):
            await self.event_bus.publish_event(
                stream or team_events.STREAM_TEAM, {"event": event, **payload}
            )

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="team-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- formation -----------------------------------------------------------------------------

    async def form_team(
        self,
        project_id: str,
        goal_ref: str,
        agent_keys: tuple[str, ...] | None = None,
        declarations: tuple[AgentCapabilityDeclaration, ...] | None = None,
    ) -> dict[str, Any]:
        """Recruit runtime agents onto a project and open the team's planning thread.

        Idempotent: forming twice re-registers the same principals and reactivates the same
        memberships rather than minting duplicates.
        """
        chosen = declarations if declarations is not None else seed_for(agent_keys)
        members: list[dict[str, Any]] = []
        for declaration in chosen:
            await self.store.register_agent(declaration)
            member = await self.store.add_member(project_id, declaration.agent_key)
            if member is None:
                continue
            members.append(member)
            await self._publish(
                team_events.EVENT_MEMBER_JOINED,
                {
                    "project_id": str(project_id),
                    "agent_key": declaration.agent_key,
                    "functional_role": declaration.role,
                    "capabilities": list(declaration.capabilities),
                },
            )
            await self._audit(
                team_events.AUDIT_MEMBER_JOINED,
                f"{declaration.agent_key} joined the team for project {project_id}",
                "joined",
                {
                    "project_id": str(project_id),
                    "agent_key": declaration.agent_key,
                    "capabilities": list(declaration.capabilities),
                },
            )

        thread = await self.store.open_thread(
            project_id=project_id, goal_ref=goal_ref, thread_type="planning"
        )
        audit_ref = await self._audit(
            team_events.AUDIT_TEAM_FORMED,
            f"team formed for project {project_id} with {len(members)} member(s)",
            "formed",
            {
                "project_id": str(project_id),
                "goal_ref": goal_ref,
                "members": [d.agent_key for d in chosen],
                "thread_id": str(thread["thread_id"]),
            },
        )
        await self._publish(
            team_events.EVENT_TEAM_FORMED,
            {
                "project_id": str(project_id),
                "goal_ref": goal_ref,
                "member_count": len(members),
                "thread_id": str(thread["thread_id"]),
                "audit_ref": audit_ref,
            },
        )
        return {
            "project_id": str(project_id),
            "goal_ref": goal_ref,
            "thread_id": str(thread["thread_id"]),
            "members": members,
            "audit_ref": audit_ref,
        }

    async def roster(self, project_id: str) -> list[dict[str, Any]]:
        return await self.store.list_team(project_id)

    async def principal_for_role(self, project_id: str, functional_role: str) -> str | None:
        for member in await self.store.list_team(project_id):
            if (
                member["functional_role"] == functional_role
                and member["membership_state"] == "active"
            ):
                return str(member["agent_principal_id"])
        return None

    async def principal_for_agent(self, project_id: str, agent_key: str) -> str | None:
        for member in await self.store.list_team(project_id):
            if member["agent_key"] == agent_key:
                return str(member["agent_principal_id"])
        return None

    async def set_membership_state(
        self, project_id: str, agent_key: str, state: str
    ) -> dict[str, Any] | None:
        member = await self.store.set_membership_state(project_id, agent_key, state)
        if member is None:
            return None
        await self._audit(
            team_events.AUDIT_MEMBER_CHANGED,
            f"{agent_key} membership on project {project_id} is now {state}",
            state,
            {"project_id": str(project_id), "agent_key": agent_key, "membership_state": state},
        )
        await self._publish(
            team_events.EVENT_MEMBER_CHANGED,
            {"project_id": str(project_id), "agent_key": agent_key, "membership_state": state},
        )
        return member

    async def set_agent_capabilities(
        self, agent_key: str, capabilities: tuple[str, ...]
    ) -> dict[str, Any] | None:
        profile = await self.store.set_agent_capabilities(agent_key, capabilities)
        if profile is None:
            return None
        await self._audit(
            team_events.AUDIT_MEMBER_CHANGED,
            f"{agent_key} now declares {len(capabilities)} capability/capabilities",
            "capabilities_changed",
            {"agent_key": agent_key, "capabilities": list(capabilities)},
        )
        return profile

    # --- collaboration -------------------------------------------------------------------------

    async def open_thread(
        self,
        project_id: str,
        goal_ref: str,
        thread_type: str = "execution",
        work_item_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.store.open_thread(
            project_id=project_id,
            goal_ref=goal_ref,
            thread_type=thread_type,
            work_item_id=work_item_id,
            run_id=run_id,
        )

    async def send_message(
        self,
        *,
        project_id: str,
        thread_id: str,
        sender_agent_key: str,
        summary: str,
        message_type: str = "message",
        to_role: str | None = None,
        to_agent_key: str | None = None,
        to_team: bool = False,
        parent_message_id: str | None = None,
        content: dict[str, Any] | None = None,
        artifact_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Post one addressed message from a runtime agent principal.

        The recipient is resolved to a PRINCIPAL where possible, so "requirement-agent addressed
        development-agent" is a fact about two identities rather than a string.
        """
        sender_principal_id = await self.principal_for_agent(project_id, sender_agent_key)
        if sender_principal_id is None:
            return None
        recipient_principal_id = None
        if to_agent_key:
            recipient_principal_id = await self.principal_for_agent(project_id, to_agent_key)
        elif to_role:
            recipient_principal_id = await self.principal_for_role(project_id, to_role)
        if not (recipient_principal_id or to_role or to_team):
            return None

        audit_ref = await self._audit(
            team_events.AUDIT_MESSAGE_POSTED,
            f"{sender_agent_key} posted a {message_type} on project {project_id}",
            message_type,
            {
                "project_id": str(project_id),
                "thread_id": str(thread_id),
                "sender": sender_agent_key,
                "recipient_role": to_role,
                "recipient_agent_key": to_agent_key,
            },
        )
        message = await self.store.post_message(
            {
                "thread_id": thread_id,
                "project_id": project_id,
                "sender_principal_id": sender_principal_id,
                "recipient_principal_id": recipient_principal_id,
                "recipient_role": to_role,
                "recipient_team": to_team,
                "parent_message_id": parent_message_id,
                "message_type": message_type,
                "summary": summary,
                "content": content or {},
                "artifact_refs": artifact_refs or {},
                "audit_ref": audit_ref,
            }
        )
        await self._publish(
            team_events.EVENT_MESSAGE_POSTED,
            {
                "project_id": str(project_id),
                "thread_id": str(thread_id),
                "message_id": str(message["message_id"]),
                "message_type": message_type,
                "sender": sender_agent_key,
                "recipient_role": to_role,
                "recipient_agent_key": to_agent_key,
            },
        )
        return message

    async def inbox(self, project_id: str, agent_key: str) -> list[dict[str, Any]]:
        """Messages addressed to this agent -- by principal, by its role, or to the whole team."""
        principal_id = await self.principal_for_agent(project_id, agent_key)
        roster = {m["agent_key"]: m for m in await self.store.list_team(project_id)}
        role = roster[agent_key]["functional_role"] if agent_key in roster else None
        received = []
        for message in await self.store.list_messages(project_id):
            if str(message.get("sender_principal_id")) == str(principal_id):
                continue
            addressed = (
                (principal_id and str(message.get("recipient_principal_id")) == str(principal_id))
                or (role and message.get("recipient_role") == role)
                or bool(message.get("recipient_team"))
            )
            if addressed:
                received.append(message)
        return received

    # --- routing -------------------------------------------------------------------------------

    async def decide_route(
        self,
        *,
        project_id: str,
        capability: str,
        workflow_stage: str = "",
        work_item_id: str | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
        preferred_role: str | None = None,
    ) -> tuple[RoutingDecision, dict[str, Any] | None]:
        """Decide who takes ``capability`` next on this team and record why.

        Returns the decision and its durable record. The decision is taken from the team as it is
        RIGHT NOW, which is what makes a membership or capability change move the work.
        """
        candidates: list[RoutingCandidate] = await self.store.routing_candidates(project_id)
        decision = route(
            RoutingRequest(
                requested_capability=capability,
                project_id=str(project_id),
                workflow_stage=workflow_stage,
                work_item_id=work_item_id,
                task_id=task_id,
                workflow_id=workflow_id,
                preferred_role=preferred_role,
            ),
            candidates,
        )
        audit_ref = await self._audit(
            team_events.AUDIT_ROUTING_DECIDED,
            f"routing {capability!r} on project {project_id}: {decision.outcome}",
            decision.outcome,
            {
                "project_id": str(project_id),
                "requested_capability": capability,
                "selected_role": decision.selected_role,
                "selected_agent_key": decision.selected_agent_key,
                "reason": decision.reason,
                "task_id": task_id,
            },
        )
        record = None
        with contextlib.suppress(Exception):
            record = await self.store.record_routing_decision(
                project_id=project_id,
                decision=decision,
                work_item_id=work_item_id,
                task_id=task_id,
                workflow_id=workflow_id,
                audit_ref=audit_ref,
            )
        await self._publish(
            (
                team_events.EVENT_ROUTING_DECIDED
                if decision.selected
                else team_events.EVENT_ROUTING_BLOCKED
            ),
            {
                "project_id": str(project_id),
                "requested_capability": capability,
                "outcome": decision.outcome,
                "selected_agent_key": decision.selected_agent_key,
                "selected_stream": decision.selected_stream,
                "reason": decision.reason,
                "task_id": task_id,
                "workflow_id": workflow_id,
                "audit_ref": audit_ref,
            },
        )
        return decision, record

    async def routing_history(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return await self.store.list_routing_decisions(project_id, limit=limit)


__all__ = ["TeamService"]
