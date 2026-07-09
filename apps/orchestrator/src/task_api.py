"""Step 66B.1 -- AI Agents Team Work task API foundation.

POST /tasks, GET /tasks, GET /tasks/{id}, POST /tasks/{id}/submit.

Fail-closed test-only auth (TASK_API_TEST_AUTH_ENABLED + X-Task-Actor/X-Task-Role
headers) stands in for a real identity/session model -- documented gap, see
docs/test/step66b1-known-gaps.md. No workflow dispatch, no external write, no
production action; production_effect defaults false and is never executed on.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from shared.sdk.tasks.audit_events import (
    DECISION_TASK_CREATED,
    DECISION_TASK_REJECTED_BY_POLICY,
    DECISION_TASK_SUBMITTED,
    safe_task_refs,
)
from shared.sdk.tasks.models import FIRST_CLASS_TASK_TYPES, TaskCreate
from shared.sdk.tasks.rbac import TASK_ROLES, can_create, can_submit, can_view
from shared.sdk.tasks.store import TaskStore

router = APIRouter(prefix="/tasks", tags=["tasks"])

_store_singleton: TaskStore | None = None


def _store() -> TaskStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = TaskStore()
    return _store_singleton


async def _audit(decision_type: str, summary: str, result: str, refs: dict[str, Any]) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=refs.get("task_id", "task-api"),
            agent="task-api",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=refs,
        )


class _AuthContext:
    def __init__(self, actor: str, role: str) -> None:
        self.actor = actor
        self.role = role


def _authenticate(request: Request) -> _AuthContext:
    """Fail-closed: TASK_API_TEST_AUTH_ENABLED must be exactly 'true'. There is no
    non-test auth path yet -- unset/false rejects every request (403)."""
    enabled = os.environ.get("TASK_API_TEST_AUTH_ENABLED", "false").strip().lower() == "true"
    if not enabled:
        raise HTTPException(status_code=403, detail="task_api_test_auth_disabled")
    actor = request.headers.get("X-Task-Actor", "").strip()
    role = request.headers.get("X-Task-Role", "").strip()
    if not actor:
        raise HTTPException(status_code=401, detail="missing_actor")
    if role not in TASK_ROLES:
        raise HTTPException(status_code=401, detail="invalid_role")
    return _AuthContext(actor=actor, role=role)


@router.post("", status_code=201)
async def create_task(payload: TaskCreate, request: Request) -> dict[str, Any]:
    ctx = _authenticate(request)
    if not can_create(ctx.role):
        raise HTTPException(status_code=403, detail="role_cannot_create_task")

    intake_planning_only = payload.task_type not in FIRST_CLASS_TASK_TYPES
    requires_approval = payload.requires_approval or payload.production_effect

    # production_effect=true is accepted but neutralized: forced into a
    # non-dispatchable status and audited as a policy decision. Never executed.
    initial_status: str = payload.initial_status
    policy_blocked = False
    if payload.production_effect and initial_status == "submitted":
        initial_status = "blocked"
        policy_blocked = True

    task = await _store().create_task(
        title=payload.title,
        description=payload.description,
        task_type=payload.task_type,
        priority=payload.priority,
        created_by=ctx.actor,
        owner=payload.owner or ctx.actor,
        project_id=str(payload.project_id) if payload.project_id else None,
        environment=payload.environment,
        production_effect=payload.production_effect,
        requires_approval=requires_approval,
        intake_planning_only=intake_planning_only,
        status=initial_status,
        metadata=payload.metadata,
    )

    refs = safe_task_refs(
        task_id=task["id"],
        correlation_id=task["correlation_id"],
        actor=ctx.actor,
        role=ctx.role,
        action="create",
        production_effect=task["production_effect"],
        environment=task["environment"],
        status=task["status"],
    )
    await _audit(DECISION_TASK_CREATED, "task created", "completed", refs)
    if policy_blocked:
        await _audit(
            DECISION_TASK_REJECTED_BY_POLICY,
            "production-effect task blocked pending approval",
            "blocked",
            refs,
        )

    return {**task, "dispatch_enabled": False}


@router.get("")
async def list_tasks(
    request: Request,
    status: str | None = None,
    task_type: str | None = None,
    owner: str | None = None,
    created_by: str | None = None,
    priority: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    ctx = _authenticate(request)
    if not can_view(ctx.role):
        raise HTTPException(status_code=403, detail="role_cannot_view_tasks")
    # Requester is scoped to own tasks regardless of the created_by filter requested.
    scope_created_by = ctx.actor if ctx.role == "requester" else created_by
    tasks = await _store().list_tasks(
        status=status,
        task_type=task_type,
        owner=owner,
        created_by=scope_created_by,
        priority=priority,
        environment=environment,
    )
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> dict[str, Any]:
    ctx = _authenticate(request)
    if not can_view(ctx.role):
        raise HTTPException(status_code=403, detail="role_cannot_view_tasks")
    task = await _store().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if ctx.role == "requester" and task["created_by"] != ctx.actor:
        raise HTTPException(status_code=403, detail="not_own_task")
    return task


@router.post("/{task_id}/submit")
async def submit_task(task_id: str, request: Request) -> dict[str, Any]:
    ctx = _authenticate(request)
    if not can_submit(ctx.role):
        raise HTTPException(status_code=403, detail="role_cannot_submit_task")
    task = await _store().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if ctx.role == "requester" and task["created_by"] != ctx.actor:
        raise HTTPException(status_code=403, detail="not_own_task")
    if task["status"] not in ("draft", "submitted"):
        raise HTTPException(status_code=409, detail=f"invalid_state_for_submit:{task['status']}")

    # production_effect=true never advances to intake_review -- forced blocked,
    # never dispatched. See docs/test/step66b1-task-rbac-safety-record.md.
    new_status = "blocked" if task["production_effect"] else "intake_review"
    updated = await _store().update_status(task_id, new_status)

    refs = safe_task_refs(
        task_id=task_id,
        correlation_id=updated["correlation_id"],
        actor=ctx.actor,
        role=ctx.role,
        action="submit",
        production_effect=updated["production_effect"],
        environment=updated["environment"],
        status=updated["status"],
    )
    await _audit(DECISION_TASK_SUBMITTED, "task submitted", "completed", refs)
    if new_status == "blocked":
        await _audit(
            DECISION_TASK_REJECTED_BY_POLICY,
            "production-effect task blocked at submit",
            "blocked",
            refs,
        )

    return {**updated, "dispatch_enabled": False}


__all__ = ["router"]
