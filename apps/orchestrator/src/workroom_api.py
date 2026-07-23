"""Step 66C.1 -- Agent Workroom & Clarification API foundation.

GET /tasks/{task_id}/workroom, POST /tasks/{task_id}/workroom/messages,
POST /tasks/{task_id}/clarifications, POST /tasks/{task_id}/clarifications/{id}/answer.
Step 66C.3 adds GET /tasks/{task_id}/audit-evidence (G3), server-side message
visibility filtering in GET .../workroom (G1), and an atomic answered-twice
guard in the answer endpoint (G5) -- see docs/test/step66c3-*.md.

Backend data/API foundation only -- no UI, no real-time/websocket, no agent
autonomy, no LLM-generated clarification, no workflow dispatch, no workflow
resume, no external call. Reuses the Step 66B.1/66B.3 fail-closed test-only auth
(`task_api._authenticate`) and audit publisher (`task_api._audit`) via the
`task_api` module reference (not a `from ... import` copy) so a single
monkeypatch of `task_api._store`/`task_api._audit` in tests affects both
routers consistently. Every response states `dispatch_enabled=false` /
`resume_dispatch_enabled=false` where applicable; message/question/answer
bodies are stored and returned as opaque plain text only (never rendered as
HTML, markdown, or a template) -- see shared/sdk/tasks/workroom_models.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

import task_api
from shared.sdk.audit.store import AuditStore
from shared.sdk.tasks.audit_events import (
    DECISION_AUDIT_EVIDENCE_RBAC_DENIED,
    DECISION_CLARIFICATION_ANSWERED,
    DECISION_CLARIFICATION_RBAC_DENIED,
    DECISION_CLARIFICATION_REQUESTED,
    DECISION_TASK_MESSAGE_CREATED,
    DECISION_TASK_WORKROOM_RBAC_DENIED,
    safe_workroom_refs,
)
from shared.sdk.tasks.workroom_models import (
    ClarificationAnswerCreate,
    ClarificationCreate,
    WorkroomMessageCreate,
)
from shared.sdk.tasks.workroom_rbac import (
    can_answer_clarification,
    can_create_clarification,
    can_post_message,
    can_view_audit_evidence,
    can_view_workroom,
    filter_messages_by_visibility,
)
from shared.sdk.tasks.workroom_store import WorkroomStore

router = APIRouter(prefix="/tasks", tags=["workroom"])

_workroom_store_singleton: WorkroomStore | None = None
_audit_store_singleton: AuditStore | None = None

# Step 66C.3 (G3) -- allowlist of fields projected from an audit_logs row into
# an audit-evidence entry. This is an ALLOWLIST, not a blocklist: any field on
# the underlying audit_logs.artifact_refs JSONB that is not named here is
# dropped, even if a future decision type were to add one. Raw message/answer
# bodies are never in artifact_refs to begin with (safe_workroom_refs only ever
# stores body_length/body_hash, see shared/sdk/tasks/audit_events.py), so this
# is defense in depth, not the only safeguard.
_AUDIT_EVIDENCE_REF_FIELDS: tuple[str, ...] = (
    "correlation_id",
    "actor",
    "role",
    "action",
    "status",
    "message_id",
    "clarification_id",
    "message_type",
    "visibility",
    "body_length",
    "body_hash",
)


def _workroom_store() -> WorkroomStore:
    global _workroom_store_singleton
    if _workroom_store_singleton is None:
        _workroom_store_singleton = WorkroomStore()
    return _workroom_store_singleton


def _audit_store() -> AuditStore:
    global _audit_store_singleton
    if _audit_store_singleton is None:
        _audit_store_singleton = AuditStore()
    return _audit_store_singleton


def _to_audit_evidence(row: dict[str, Any]) -> dict[str, Any]:
    refs = row.get("artifact_refs") or {}
    evidence: dict[str, Any] = {
        "audit_event_id": row.get("audit_id"),
        "task_id": row.get("task_id"),
        "event_type": row.get("decision_type"),
        "created_at": row.get("created_at"),
    }
    for key in _AUDIT_EVIDENCE_REF_FIELDS:
        if key in refs:
            evidence[key] = refs[key]
    return evidence


async def _get_task_or_404(task_id: str) -> dict[str, Any]:
    task = await task_api._store().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task


async def _deny_workroom(ctx: Any, action: str, reason: str, task_id: str | None = None) -> None:
    refs = safe_workroom_refs(
        task_id=task_id, actor=ctx.actor, role=ctx.role, action=action, status=reason
    )
    await task_api._audit(
        DECISION_TASK_WORKROOM_RBAC_DENIED, f"workroom rbac denied: {reason}", "denied", refs
    )
    raise HTTPException(status_code=403, detail=reason)


async def _deny_clarification(
    ctx: Any,
    action: str,
    reason: str,
    task_id: str | None = None,
    clarification_id: str | None = None,
) -> None:
    refs = safe_workroom_refs(
        task_id=task_id,
        clarification_id=clarification_id,
        actor=ctx.actor,
        role=ctx.role,
        action=action,
        status=reason,
    )
    await task_api._audit(
        DECISION_CLARIFICATION_RBAC_DENIED, f"clarification rbac denied: {reason}", "denied", refs
    )
    raise HTTPException(status_code=403, detail=reason)


async def _deny_audit_evidence(ctx: Any, reason: str, task_id: str | None = None) -> None:
    refs = safe_workroom_refs(
        task_id=task_id, actor=ctx.actor, role=ctx.role, action="view_audit_evidence", status=reason
    )
    await task_api._audit(
        DECISION_AUDIT_EVIDENCE_RBAC_DENIED, f"audit evidence rbac denied: {reason}", "denied", refs
    )
    raise HTTPException(status_code=403, detail=reason)


@router.get("/{task_id}/workroom")
async def get_workroom(task_id: str, request: Request) -> dict[str, Any]:
    ctx = task_api._authenticate(request)
    if not can_view_workroom(ctx.role):
        await _deny_workroom(ctx, "view", "role_cannot_view_workroom", task_id=task_id)
    task = await _get_task_or_404(task_id)
    if ctx.role == "requester" and task["created_by"] != ctx.actor:
        await _deny_workroom(ctx, "view", "not_own_task", task_id=task_id)
    # Step 66C.3 (G1) -- server-side visibility filter; the frontend only ever
    # renders what has already passed through this, it never re-filters.
    messages = filter_messages_by_visibility(
        await _workroom_store().list_messages(task_id), ctx.role
    )
    clarifications = await _workroom_store().list_clarifications(task_id)
    return {
        "task_id": task_id,
        "task_status": task["status"],
        "messages": messages,
        "clarification_requests": clarifications,
        "dispatch_enabled": False,
        "resume_dispatch_enabled": False,
    }


@router.post("/{task_id}/workroom/messages", status_code=201)
async def post_workroom_message(
    task_id: str, payload: WorkroomMessageCreate, request: Request
) -> dict[str, Any]:
    ctx = task_api._authenticate(request)
    if not can_post_message(ctx.role):
        await _deny_workroom(ctx, "post_message", "role_cannot_post_message", task_id=task_id)
    task = await _get_task_or_404(task_id)
    if ctx.role == "requester" and task["created_by"] != ctx.actor:
        await _deny_workroom(ctx, "post_message", "not_own_task", task_id=task_id)

    message = await _workroom_store().create_message(
        task_id=task_id,
        sender_type="human",
        sender_id=ctx.actor,
        sender_role=ctx.role,
        message_type="human_message",
        body=payload.body,
        visibility="task_participants",
    )
    refs = safe_workroom_refs(
        task_id=task_id,
        message_id=message["id"],
        correlation_id=message["correlation_id"],
        actor=ctx.actor,
        role=ctx.role,
        action="post_message",
        message_type=message["message_type"],
        visibility=message["visibility"],
        body=payload.body,
    )
    await task_api._audit(
        DECISION_TASK_MESSAGE_CREATED, "workroom message created", "completed", refs
    )
    return {**message, "dispatch_enabled": False}


@router.post("/{task_id}/clarifications", status_code=201)
async def create_clarification(
    task_id: str, payload: ClarificationCreate, request: Request
) -> dict[str, Any]:
    ctx = task_api._authenticate(request)
    if not can_create_clarification(ctx.role):
        await _deny_clarification(
            ctx, "create", "role_cannot_create_clarification", task_id=task_id
        )
    # Create-clarification roles (pm_engineering_lead/platform_admin/agent_operator)
    # never include "requester", so no own-task scoping check applies here
    # (documented in step66c1-rbac-audit-safety-record.md, not overclaimed).
    await _get_task_or_404(task_id)

    question_message = await _workroom_store().create_message(
        task_id=task_id,
        sender_type="human",
        sender_id=ctx.actor,
        sender_role=ctx.role,
        message_type="clarification_question",
        body=payload.question,
        visibility="task_participants",
    )
    clarification = await _workroom_store().create_clarification(
        task_id=task_id,
        question_message_id=question_message["id"],
        question=payload.question,
        requested_by_type="human",
        requested_by_id=ctx.actor,
        assigned_to=payload.assigned_to,
    )
    updated_task = await task_api._store().set_clarification_state(
        task_id, status="clarification_needed", clarification_status="open"
    )

    refs = safe_workroom_refs(
        task_id=task_id,
        message_id=question_message["id"],
        clarification_id=clarification["id"],
        correlation_id=question_message["correlation_id"],
        actor=ctx.actor,
        role=ctx.role,
        action="create_clarification",
        message_type="clarification_question",
        visibility="task_participants",
        body=payload.question,
        status=clarification["status"],
    )
    await task_api._audit(
        DECISION_CLARIFICATION_REQUESTED, "clarification requested", "completed", refs
    )

    return {
        **clarification,
        "task_status": updated_task["status"],
        "dispatch_enabled": False,
        "resume_dispatch_enabled": False,
    }


@router.post("/{task_id}/clarifications/{clarification_id}/answer")
async def answer_clarification(
    task_id: str, clarification_id: str, payload: ClarificationAnswerCreate, request: Request
) -> dict[str, Any]:
    ctx = task_api._authenticate(request)
    if not can_answer_clarification(ctx.role):
        await _deny_clarification(
            ctx,
            "answer",
            "role_cannot_answer_clarification",
            task_id=task_id,
            clarification_id=clarification_id,
        )
    task = await _get_task_or_404(task_id)
    if ctx.role == "requester" and task["created_by"] != ctx.actor:
        await _deny_clarification(
            ctx, "answer", "not_own_task", task_id=task_id, clarification_id=clarification_id
        )

    clarification = await _workroom_store().get_clarification(clarification_id)
    if clarification is None or clarification["task_id"] != task_id:
        raise HTTPException(status_code=404, detail="clarification_not_found")
    if clarification["status"] == "answered":
        raise HTTPException(status_code=409, detail="clarification_already_answered")
    if clarification["status"] != "open":
        raise HTTPException(
            status_code=409, detail=f"invalid_state_for_answer:{clarification['status']}"
        )

    # Step 66C.3 (G5) -- atomically claim the open->answered transition BEFORE
    # creating the answer message or emitting the audit event. A concurrent
    # second answer that raced past the pre-check above will lose this claim
    # (claimed is None) and gets clarification_already_answered here too --
    # crucially, with no answer message and no clarification_answered audit
    # event created, unlike the pre-check above which only prevents the common
    # sequential case.
    #
    # Step 66C.4-BE1 -- the claim CAS also enforces the authoritative deadline
    # (`due_at > now()` in PostgreSQL DB time). If the claim is lost, re-read the
    # authoritative row state to return the correct 409 reason (reusing the
    # existing response shapes -- no new shape is introduced): a lost race to a
    # concurrent answer -> clarification_already_answered; a row still 'open' means
    # the loss was specifically to the deadline predicate (DB time >= due_at), which
    # the future timeout worker has not yet materialized to 'expired' ->
    # invalid_state_for_answer:expired. This claim writes NO outbox row and triggers
    # NO scheduler/event/notification.
    claimed = await _workroom_store().claim_clarification_answer(clarification_id)
    if claimed is None:
        current = await _workroom_store().get_clarification(clarification_id)
        if current is not None and current["status"] == "open":
            raise HTTPException(status_code=409, detail="invalid_state_for_answer:expired")
        if current is not None and current["status"] not in ("answered", "open"):
            raise HTTPException(
                status_code=409, detail=f"invalid_state_for_answer:{current['status']}"
            )
        raise HTTPException(status_code=409, detail="clarification_already_answered")

    answer_message = await _workroom_store().create_message(
        task_id=task_id,
        sender_type="human",
        sender_id=ctx.actor,
        sender_role=ctx.role,
        message_type="clarification_answer",
        body=payload.answer,
        visibility="task_participants",
        reply_to_message_id=clarification["question_message_id"],
    )
    updated_clarification = await _workroom_store().set_answer_message(
        clarification_id, answer_message_id=answer_message["id"]
    )
    updated_task = await task_api._store().set_clarification_state(
        task_id, status="intake_review", clarification_status="answered"
    )

    refs = safe_workroom_refs(
        task_id=task_id,
        message_id=answer_message["id"],
        clarification_id=clarification_id,
        correlation_id=answer_message["correlation_id"],
        actor=ctx.actor,
        role=ctx.role,
        action="answer_clarification",
        message_type="clarification_answer",
        visibility="task_participants",
        body=payload.answer,
        status=updated_clarification["status"],
    )
    await task_api._audit(
        DECISION_CLARIFICATION_ANSWERED, "clarification answered", "completed", refs
    )

    return {
        **updated_clarification,
        "task_status": updated_task["status"],
        "dispatch_enabled": False,
        "resume_dispatch_enabled": False,
    }


@router.get("/{task_id}/audit-evidence")
async def get_audit_evidence(task_id: str, request: Request) -> dict[str, Any]:
    """Step 66C.3 (G3) -- task-scoped, safe audit evidence.

    Returns only the allowlisted fields in `_AUDIT_EVIDENCE_REF_FIELDS` (plus
    audit_event_id/task_id/event_type/created_at) -- never a raw message body,
    raw clarification answer, request payload, header, cookie, token, or
    secret. RBAC is stricter than workroom view access (see
    `can_view_audit_evidence`): Requester and Reviewer/Approver are denied by
    default.
    """
    ctx = task_api._authenticate(request)
    if not can_view_audit_evidence(ctx.role):
        await _deny_audit_evidence(ctx, "role_cannot_view_audit_evidence", task_id=task_id)
    await _get_task_or_404(task_id)
    rows = await _audit_store().get_audit_logs(task_id)
    return {
        "task_id": task_id,
        "events": [_to_audit_evidence(row) for row in rows],
        "dispatch_enabled": False,
        "resume_dispatch_enabled": False,
    }


__all__ = ["router"]
