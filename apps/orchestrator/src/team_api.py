"""Step AT-M2-TEAM-CORE -- the minimal team surface needed to verify AT-M2.

Read-only views of the team, its conversation and its routing decisions, plus the two writes AT-M2
needs to be demonstrable: forming a team for a project, and changing a member's availability so a
reviewer can watch the routing decision move.

It runs no workflow, dispatches nothing, executes no production action, and returns summaries and
references only -- never a credential, never a reasoning trace. This is deliberately not the
Autonomous Team UX; that is AT-M5.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.agent_team.capabilities import KNOWN_CAPABILITIES
from shared.sdk.agent_team.service import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


def _service() -> TeamService:
    return TeamService()


class FormTeamRequest(BaseModel):
    goal_ref: str = Field(min_length=1, max_length=500)
    agent_keys: list[str] | None = None


class MembershipStateRequest(BaseModel):
    membership_state: str = Field(pattern="^(invited|active|paused|left)$")


def _member_view(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "principal_id": str(member["agent_principal_id"]),
        "agent_key": member["agent_key"],
        "functional_role": member["functional_role"],
        "membership_state": member["membership_state"],
        "capabilities": list(member["capabilities"]),
        "profile_status": member["profile_status"],
        "display_name": member.get("display_name"),
        "principal_type": member.get("principal_type"),
        "joined_at": member.get("joined_at"),
        "left_at": member.get("left_at"),
    }


@router.get("/capabilities")
async def list_capabilities() -> dict:
    """The capability vocabulary the router matches against."""
    return {"capabilities": sorted(KNOWN_CAPABILITIES)}


@router.post("/{project_id}/form")
async def form_team(project_id: str, payload: FormTeamRequest) -> dict:
    try:
        formed = await _service().form_team(
            project_id,
            payload.goal_ref,
            agent_keys=tuple(payload.agent_keys) if payload.agent_keys else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"team could not be formed: {exc}") from exc
    return {
        "project_id": formed["project_id"],
        "goal_ref": formed["goal_ref"],
        "thread_id": formed["thread_id"],
        "member_count": len(formed["members"]),
        "audit_ref": formed["audit_ref"],
    }


@router.get("/{project_id}")
async def get_team(project_id: str) -> dict:
    try:
        roster = await _service().roster(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"team is unavailable: {exc}") from exc
    return {
        "project_id": project_id,
        "member_count": sum(1 for m in roster if m["membership_state"] == "active"),
        "members": [_member_view(m) for m in roster],
    }


@router.patch("/{project_id}/members/{agent_key}")
async def set_membership_state(
    project_id: str, agent_key: str, payload: MembershipStateRequest
) -> dict:
    """Change a member's availability. The next routing decision follows from it."""
    try:
        member = await _service().set_membership_state(
            project_id, agent_key, payload.membership_state
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"membership unavailable: {exc}") from exc
    if member is None:
        raise HTTPException(status_code=404, detail=f"{agent_key} is not on this team")
    return {
        "project_id": project_id,
        "agent_key": agent_key,
        "membership_state": member["membership_state"],
    }


@router.get("/{project_id}/messages")
async def list_messages(project_id: str, thread_id: str | None = None, limit: int = 200) -> dict:
    try:
        messages = await _service().store.list_messages(
            project_id, thread_id=thread_id, limit=min(limit, 500)
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"messages are unavailable: {exc}") from exc
    return {
        "project_id": project_id,
        "count": len(messages),
        "messages": [
            {
                "message_id": str(m["message_id"]),
                "thread_id": str(m["thread_id"]),
                "sender_principal_id": str(m["sender_principal_id"]),
                "recipient_principal_id": (
                    str(m["recipient_principal_id"]) if m.get("recipient_principal_id") else None
                ),
                "recipient_role": m.get("recipient_role"),
                "recipient_team": bool(m.get("recipient_team")),
                "parent_message_id": (
                    str(m["parent_message_id"]) if m.get("parent_message_id") else None
                ),
                "message_type": m["message_type"],
                "summary": m["summary"],
                "artifact_refs": m.get("artifact_refs") or {},
                "audit_ref": m.get("audit_ref"),
                "created_at": m.get("created_at"),
            }
            for m in messages
        ],
    }


@router.get("/{project_id}/routing-decisions")
async def list_routing_decisions(project_id: str, limit: int = 100) -> dict:
    try:
        decisions = await _service().routing_history(project_id, limit=min(limit, 500))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"routing history unavailable: {exc}") from exc
    return {
        "project_id": project_id,
        "count": len(decisions),
        "routing_decisions": [
            {
                "routing_decision_id": str(d["routing_decision_id"]),
                "requested_capability": d["requested_capability"],
                "outcome": d["outcome"],
                "selected_role": d.get("selected_role"),
                "selected_stream": d.get("selected_stream"),
                "reason": d["reason"],
                "candidates_considered": d.get("candidates_considered") or [],
                "task_id": d.get("task_id"),
                "audit_ref": d.get("audit_ref"),
                "created_at": d.get("created_at"),
            }
            for d in decisions
        ],
    }
