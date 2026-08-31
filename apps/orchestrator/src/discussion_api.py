"""Step AT-M3.3 -- the minimal bounded-discussion surface later AT-M3 slices need.

Six routes: open one, read one, step one, and read what it produced. There is deliberately no
route that edits a TeamMessage, no route that accepts or rejects anything, and no PUT, PATCH or
DELETE at all -- a discussion is evidence of what a team said, and an endpoint that could rewrite
it would make the thread unciteable.

What is NOT here, and is not an oversight: accept, reject, decide, and anything that produces a
TeamDecision or a PlanRevision. Those are AT-M3.4's, and exposing them from the discussion surface
would let a deliberation appear to authorize its own outcome.

It runs no workflow, dispatches nothing, decomposes nothing, calls no external provider and
executes no production action.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_deliberation.models import (
    DiscussionBounds,
    DiscussionParticipantError,
    DiscussionStateError,
)
from shared.sdk.agent_deliberation.service import DiscussionService

router = APIRouter(prefix="/discussions", tags=["discussions"])


def _service() -> DiscussionService:
    return DiscussionService()


class StartDiscussionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    opened_by: str = Field(min_length=1)
    #: The explicit question. A discussion without one cannot converge, because nothing says what
    #: it would have converged on.
    topic: str = Field(min_length=1, max_length=2000)
    #: Explicit, never inferred from the whole roster: participants are selected against exactly
    #: these, and a capability nobody on the team declares fails the request closed.
    required_capabilities: list[str] = Field(min_length=1, max_length=10)
    #: Optional. When absent the CURRENT revision of the goal is resolved from lineage.
    plan_revision_id: str | None = None
    max_rounds: int | None = Field(default=None, ge=1, le=20)
    max_messages: int | None = Field(default=None, ge=1, le=200)
    max_invocations: int | None = Field(default=None, ge=1, le=200)
    max_turns_per_participant: int | None = Field(default=None, ge=1, le=20)
    #: The elapsed-time bound. Converted to an absolute deadline by the database at open, so it is
    #: enforced identically by every worker and survives the process that opened the discussion.
    timeout_seconds: float | None = Field(default=None, gt=0, le=86400)
    #: Supply to make a repeated start explicitly idempotent. Absent, a key is derived from the
    #: project, goal, revision and topic, so an accidental double start resolves to one discussion.
    idempotency_key: str | None = Field(default=None, max_length=200)

    def bounds(self) -> DiscussionBounds:
        supplied = {
            field: value
            for field, value in (
                ("max_rounds", self.max_rounds),
                ("max_messages", self.max_messages),
                ("max_invocations", self.max_invocations),
                ("max_turns_per_participant", self.max_turns_per_participant),
                ("timeout_seconds", self.timeout_seconds),
            )
            if value is not None
        }
        return DiscussionBounds(**supplied)


def _session_view(row: dict[str, Any], currency: dict[str, Any] | None = None) -> dict[str, Any]:
    """The discussion as a caller sees it.

    ``currency`` carries the two DERIVED plan-staleness fields. They are computed per read and
    stored nowhere, so they are passed in rather than looked up here -- a view function that
    quietly issued its own queries would make it much easier to start caching the answer.
    """
    view = {
        "discussion_id": str(row["discussion_id"]),
        "project_id": str(row["project_id"]),
        "goal_id": str(row["goal_id"]),
        "plan_revision_id": (str(row["plan_revision_id"]) if row.get("plan_revision_id") else None),
        "thread_id": str(row["thread_id"]),
        "opened_by": str(row["opened_by"]),
        "topic": row["topic"],
        "required_capabilities": list(row["required_capabilities"]),
        "bounds": {
            "max_rounds": row["max_rounds"],
            "max_messages": row["max_messages"],
            "max_invocations": row["max_invocations"],
            "max_turns_per_participant": row["max_turns_per_participant"],
            # An absolute instant, not a duration: the caller polling this discussion and the
            # worker advancing it must agree on when it expires.
            "deadline_at": row.get("deadline_at"),
        },
        "deadline_expired": row.get("deadline_expired", False),
        "current_round": row["current_round"],
        "turns_taken": row["turns_taken"],
        "messages_posted": row["messages_posted"],
        "invocations_started": row["invocations_started"],
        # Two separate facts, reported separately: WHAT the discussion is, and WHY it stopped.
        "state": row["state"],
        "stop_reason": row["stop_reason"],
        "is_terminal": row["state"] != "open",
        "result_message_id": (
            str(row["result_message_id"]) if row.get("result_message_id") else None
        ),
        "created_at": row.get("created_at"),
        "closed_at": row.get("closed_at"),
    }
    if currency is not None:
        view.update(currency)
    return view


def _participant_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "seat_index": row["seat_index"],
        "principal_id": str(row["principal_id"]),
        "agent_key": row["agent_key"],
        "functional_role": row["functional_role"],
        "matched_capabilities": list(row["matched_capabilities"]),
        "selection_reason": row["selection_reason"],
        "turns_taken": row["turns_taken"],
    }


def _turn_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "round_index": row["round_index"],
        "seat_index": row["seat_index"],
        "speaker_principal_id": str(row["speaker_principal_id"]),
        "addressed_principal_id": (
            str(row["addressed_principal_id"]) if row.get("addressed_principal_id") else None
        ),
        "addressed_team": row["addressed_team"],
        "intent": row["intent"],
        "reasoning_verb": row["reasoning_verb"],
        "reasoning_invocation_id": (
            str(row["reasoning_invocation_id"]) if row.get("reasoning_invocation_id") else None
        ),
        "message_id": str(row["message_id"]) if row.get("message_id") else None,
        "status": row["status"],
        "concern_count": row["concern_count"],
    }


def _message_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "message_id": str(row["message_id"]),
        "sender_principal_id": str(row["sender_principal_id"]),
        "recipient_principal_id": (
            str(row["recipient_principal_id"]) if row.get("recipient_principal_id") else None
        ),
        "recipient_team": row["recipient_team"],
        "message_type": row["message_type"],
        "summary": row["summary"],
        "content": row["content"],
        "artifact_refs": row["artifact_refs"],
        "created_at": row.get("created_at"),
    }


@router.post("")
async def start_discussion(payload: StartDiscussionRequest) -> dict:
    """Open one bounded deliberation.

    A repeated request with the same idempotency key returns the discussion that already exists
    rather than opening a second one. A team that cannot cover the required capabilities still
    produces a durable, terminal discussion saying so -- 201-shaped success, not a silent nothing.
    """
    service = _service()
    try:
        row = await service.start_discussion(
            project_id=payload.project_id,
            goal_id=payload.goal_id,
            topic=payload.topic,
            opened_by=payload.opened_by,
            required_capabilities=tuple(payload.required_capabilities),
            plan_revision_id=payload.plan_revision_id,
            bounds=payload.bounds(),
            idempotency_key=payload.idempotency_key,
        )
    except DiscussionParticipantError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DiscussionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncpg.PostgresError as exc:
        # An expected domain conflict is mapped above; anything left from the driver is an
        # upstream availability problem, not a bug the caller can act on and not a 500.
        raise HTTPException(
            status_code=503, detail=f"discussion could not be opened: {type(exc).__name__}"
        ) from exc
    return _session_view(row, await service.plan_currency(row))


@router.get("/{discussion_id}")
async def get_discussion(discussion_id: str) -> dict:
    service = _service()
    row = await service.get_discussion(discussion_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown discussion {discussion_id}")
    return _session_view(row, await service.plan_currency(row))


@router.get("/{discussion_id}/state")
async def get_discussion_state(discussion_id: str) -> dict:
    """The terminal/stop state alone, for a caller polling a discussion it started.

    Carries the two derived plan-currency fields as well, because they are what a future M3.4
    consumer must check before treating a convergence as evidence about the CURRENT plan --
    and having to join lineage by hand is how that check gets skipped. Derived here, never stored:
    ``plan_revision_is_current`` can change without this discussion changing at all.
    """
    service = _service()
    row = await service.get_discussion(discussion_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown discussion {discussion_id}")
    return {
        "discussion_id": str(row["discussion_id"]),
        "state": row["state"],
        "stop_reason": row["stop_reason"],
        "is_terminal": row["state"] != "open",
        "current_round": row["current_round"],
        "turns_taken": row["turns_taken"],
        "deadline_at": row.get("deadline_at"),
        "deadline_expired": row.get("deadline_expired", False),
        "plan_revision_id": (str(row["plan_revision_id"]) if row.get("plan_revision_id") else None),
        "result_message_id": (
            str(row["result_message_id"]) if row.get("result_message_id") else None
        ),
        **await service.plan_currency(row),
    }


@router.post("/{discussion_id}/advance")
async def advance_discussion(discussion_id: str) -> dict:
    """Take at most one step: one turn, one round boundary, or one closure.

    Safe to call concurrently and safe to retry. ``advanced=false`` means this call changed
    nothing -- because the discussion is already terminal, or because another worker holds the
    turn -- which is an outcome, not an error, and is reported as 200 with a reason.
    """
    service = _service()
    try:
        outcome = await service.advance(discussion_id)
    except DiscussionStateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=503, detail=f"discussion could not be advanced: {type(exc).__name__}"
        ) from exc
    return {
        "advanced": outcome["advanced"],
        "detail": outcome["detail"],
        "turn": _turn_view(outcome["turn"]) if outcome["turn"] else None,
        "discussion": _session_view(
            outcome["session"], await service.plan_currency(outcome["session"])
        ),
    }


@router.get("/{discussion_id}/participants")
async def list_participants(discussion_id: str) -> dict:
    service = _service()
    if await service.get_discussion(discussion_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown discussion {discussion_id}")
    rows = await service.get_participants(discussion_id)
    return {
        "discussion_id": discussion_id,
        "count": len(rows),
        "participants": [_participant_view(row) for row in rows],
    }


@router.get("/{discussion_id}/messages")
async def list_discussion_messages(discussion_id: str, limit: int = 200) -> dict:
    """The thread, oldest first, plus the turn ledger that says which turn produced what."""
    service = _service()
    if await service.get_discussion(discussion_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown discussion {discussion_id}")
    messages = await service.get_messages(discussion_id, limit=limit)
    turns = await service.get_turns(discussion_id)
    return {
        "discussion_id": discussion_id,
        "count": len(messages),
        "messages": [_message_view(row) for row in messages],
        "turns": [_turn_view(row) for row in turns],
    }
