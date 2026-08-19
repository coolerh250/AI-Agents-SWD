"""Step AT-M2-TEAM-CORE -- in-memory fake TeamStore for unit tests and the demo scenario.

Implements the same async surface TeamService uses, backed by dicts. No DB, no asyncpg, no Redis.
Follows the existing tests/project_planning_fakes.py convention.

It enforces the two constraints the real schema enforces and the tests depend on -- a message must
be addressed, and a routing decision may only name a principal when it actually selected one -- so
a test cannot pass here on a row the database would have rejected.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from shared.sdk.agent_team.capabilities import AgentCapabilityDeclaration
from shared.sdk.agent_team.router import RoutingCandidate, RoutingDecision


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryTeamStore:
    def __init__(self) -> None:
        self.principals: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}  # agent_key -> profile
        self.memberships: dict[tuple[str, str], dict] = {}  # (project_id, principal_id)
        self.threads: dict[str, dict] = {}
        self.messages: list[dict] = []
        self.decisions: list[dict] = []
        self.handoffs: dict[str, dict] = {}
        self.routing_decisions: list[dict] = []

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    # --- identity ------------------------------------------------------------------------------

    async def register_agent(self, declaration: AgentCapabilityDeclaration) -> dict[str, Any]:
        existing = self.profiles.get(declaration.agent_key)
        principal_id = existing["principal_id"] if existing else self._id()
        if not existing:
            self.principals[principal_id] = {
                "principal_id": principal_id,
                "principal_type": "runtime_agent",
                "display_name": declaration.agent_key,
                "status": "active",
            }
        profile = {
            "agent_id": existing["agent_id"] if existing else self._id(),
            "principal_id": principal_id,
            "agent_key": declaration.agent_key,
            "role": declaration.role,
            "capabilities": tuple(declaration.capabilities),
            "transport_stream": declaration.transport_stream,
            "tool_policy_profile": declaration.tool_policy_profile,
            "model_provider_ref": declaration.model_provider_ref,
            "status": existing["status"] if existing else "active",
        }
        self.profiles[declaration.agent_key] = profile
        return dict(profile)

    async def set_agent_capabilities(
        self, agent_key: str, capabilities: tuple[str, ...]
    ) -> dict[str, Any] | None:
        profile = self.profiles.get(agent_key)
        if profile is None:
            return None
        profile["capabilities"] = tuple(capabilities)
        return dict(profile)

    def set_profile_status(self, agent_key: str, status: str) -> None:
        """Test affordance: disable a profile without touching its membership."""
        self.profiles[agent_key]["status"] = status

    # --- membership ----------------------------------------------------------------------------

    async def add_member(
        self, project_id: str, agent_key: str, functional_role: str | None = None
    ) -> dict[str, Any] | None:
        profile = self.profiles.get(agent_key)
        if profile is None:
            return None
        key = (str(project_id), profile["principal_id"])
        existing = self.memberships.get(key)
        member = {
            "membership_id": existing["membership_id"] if existing else self._id(),
            "project_id": str(project_id),
            "agent_principal_id": profile["principal_id"],
            "functional_role": functional_role or profile["role"],
            "membership_state": "active",
            "joined_at": existing["joined_at"] if existing else _now(),
            "left_at": None,
        }
        self.memberships[key] = member
        return dict(member)

    async def set_membership_state(
        self, project_id: str, agent_key: str, state: str
    ) -> dict[str, Any] | None:
        profile = self.profiles.get(agent_key)
        if profile is None:
            return None
        member = self.memberships.get((str(project_id), profile["principal_id"]))
        if member is None:
            return None
        member["membership_state"] = state
        member["left_at"] = _now() if state == "left" else None
        return dict(member)

    async def list_team(self, project_id: str) -> list[dict[str, Any]]:
        rows = []
        for (pid, principal_id), member in self.memberships.items():
            if pid != str(project_id):
                continue
            profile = next(p for p in self.profiles.values() if p["principal_id"] == principal_id)
            principal = self.principals[principal_id]
            rows.append(
                {
                    **member,
                    "agent_key": profile["agent_key"],
                    "role": profile["role"],
                    "capabilities": tuple(profile["capabilities"]),
                    "transport_stream": profile["transport_stream"],
                    "profile_status": profile["status"],
                    "display_name": principal["display_name"],
                    "principal_type": principal["principal_type"],
                }
            )
        return sorted(rows, key=lambda r: r["agent_key"])

    async def routing_candidates(self, project_id: str) -> list[RoutingCandidate]:
        return [
            RoutingCandidate(
                principal_id=str(m["agent_principal_id"]),
                agent_key=m["agent_key"],
                role=m["functional_role"],
                capabilities=frozenset(m["capabilities"]),
                transport_stream=m["transport_stream"],
                membership_state=m["membership_state"],
                profile_status=m["profile_status"],
            )
            for m in await self.list_team(project_id)
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
        thread = {
            "thread_id": self._id(),
            "project_id": str(project_id),
            "goal_ref": goal_ref,
            "thread_type": thread_type,
            "work_item_id": work_item_id,
            "run_id": run_id,
            "state": "open",
            "created_at": _now(),
        }
        self.threads[thread["thread_id"]] = thread
        return dict(thread)

    async def post_message(self, message: dict[str, Any]) -> dict[str, Any]:
        # The schema's chk_team_messages_addressed constraint, enforced here too.
        if not (
            message.get("recipient_principal_id")
            or message.get("recipient_role")
            or message.get("recipient_team")
        ):
            raise ValueError("a team message must be addressed")
        row = {
            "message_id": self._id(),
            "correlation_id": self._id(),
            "created_at": _now(),
            **message,
        }
        self.messages.append(row)
        return dict(row)

    async def list_messages(
        self, project_id: str, thread_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = [m for m in self.messages if str(m["project_id"]) == str(project_id)]
        if thread_id:
            rows = [m for m in rows if str(m["thread_id"]) == str(thread_id)]
        return [dict(m) for m in rows[:limit]]

    async def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        row = {"decision_id": self._id(), "created_at": _now(), **decision}
        self.decisions.append(row)
        return dict(row)

    async def offer_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        row = {
            "handoff_id": self._id(),
            "state": "offered",
            "created_at": _now(),
            "accepted_at": None,
            **handoff,
        }
        self.handoffs[row["handoff_id"]] = row
        return dict(row)

    async def accept_handoff(self, handoff_id: str) -> dict[str, Any] | None:
        row = self.handoffs.get(str(handoff_id))
        if row is None or row["state"] != "offered":
            return None
        row["state"] = "accepted"
        row["accepted_at"] = _now()
        return dict(row)

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
        # The schema's chk_routing_selected_consistency constraint, enforced here too.
        selected = decision.selected_principal_id
        if (decision.outcome == "selected") != (selected is not None):
            raise ValueError("routing outcome and selected principal disagree")
        row = {
            "routing_decision_id": self._id(),
            "project_id": str(project_id),
            "work_item_id": work_item_id,
            "task_id": task_id,
            "workflow_id": workflow_id,
            "requested_capability": decision.requested_capability,
            "outcome": decision.outcome,
            "selected_principal_id": selected,
            "selected_role": decision.selected_role,
            "selected_stream": decision.selected_stream,
            "reason": decision.reason,
            "candidates_considered": list(decision.candidates_considered),
            "audit_ref": audit_ref,
            "correlation_id": self._id(),
            "created_at": _now(),
        }
        self.routing_decisions.append(row)
        return dict(row)

    async def list_routing_decisions(
        self, project_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self.routing_decisions if str(r["project_id"]) == str(project_id)]
        return list(reversed(rows))[:limit]


class RecordingEventBus:
    """Captures published events instead of reaching Redis."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, stream: str, event: dict) -> str:
        self.published.append((stream, dict(event)))
        return f"{stream}-{len(self.published)}"

    def streams(self) -> list[str]:
        return [stream for stream, _ in self.published]

    def events_on(self, stream: str) -> list[dict]:
        return [event for published_stream, event in self.published if published_stream == stream]

    async def close(self) -> None:
        return None


class RecordingAuditClient:
    """Captures audit events instead of publishing them to the audit stream."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def build_audit_event(self, **kwargs) -> dict:
        return dict(kwargs)

    async def write_audit_event(self, event: dict) -> str:
        self.events.append(dict(event))
        return f"audit-{len(self.events)}"

    def decision_types(self) -> list[str]:
        return [e.get("decision_type", "") for e in self.events]


__all__ = ["InMemoryTeamStore", "RecordingAuditClient", "RecordingEventBus"]
