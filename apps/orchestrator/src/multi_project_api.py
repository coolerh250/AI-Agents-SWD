"""Step 57 (Stage 59A) -- multi-project delivery + work-item dispatch API.

Project / work-item READ endpoints are GET-only + redacted. WRITE endpoints
(create project / work item, dispatch) reuse the existing test-local auth + CSRF +
audit (operator_actions) and require a reason. Dispatch is policy-checked: it never
triggers GitHub write / ArgoCD sync / external notification / production action, and
a production_effect work item goes to waiting_approval -- never dispatched directly.
"""

from __future__ import annotations

import contextlib
import os
import uuid

from fastapi import APIRouter, Request

# Reuse the exact test-local auth / CSRF / audit used by the operator-actions API.
from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.projects import ProjectStore, compute_delivery_state
from shared.sdk.work_items import WorkItemStore, dispatcher, lifecycle
from shared.sdk.work_items.dispatcher import DispatchError
from shared.sdk.work_items.events import build_audit_metadata

router = APIRouter(prefix="/operations/delivery", tags=["multi-project"])

_projects = ProjectStore()
_items = WorkItemStore()


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_executed": False,
        "github_write_performed": False,
        "argocd_sync_performed": False,
        "external_notification_send_performed": False,
    }


async def _publish(stream: str, event: dict) -> None:
    """Best-effort internal stream publish. No external side effect."""
    with contextlib.suppress(Exception):
        from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

        await RedisStreamEventBus(os.environ.get("REDIS_URL")).publish_event(stream, event)


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted)
# ---------------------------------------------------------------------------
@router.get("/projects")
async def list_projects() -> dict:
    return {"projects": await _projects.list_projects()}


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    p = await _projects.get_project(project_id)
    return p or {"status": "not_found"}


@router.get("/projects/{project_id}/work-items")
async def list_work_items(project_id: str) -> dict:
    return {"work_items": await _items.list_work_items(project_id)}


@router.get("/work-items/{work_item_id}")
async def get_work_item(work_item_id: str) -> dict:
    wi = await _items.get_work_item(work_item_id)
    return wi or {"status": "not_found"}


@router.get("/work-items/{work_item_id}/events")
async def list_events(work_item_id: str) -> dict:
    return {"events": await _items.list_events(work_item_id)}


@router.get("/work-items/{work_item_id}/dispatches")
async def list_dispatches(work_item_id: str) -> dict:
    return {"dispatches": await _items.list_dispatches(work_item_id)}


@router.get("/projects/{project_id}/delivery-state")
async def project_delivery_state(project_id: str) -> dict:
    items = await _items.list_work_items(project_id)
    state = compute_delivery_state(items)
    persisted = await _projects.upsert_delivery_state(project_id, state)
    return {
        "project_id": project_id,
        "delivery_state": state,
        "production_ready": False,
        "persisted": persisted,
    }


# ---------------------------------------------------------------------------
# Write endpoints (auth + CSRF + reason + audit)
# ---------------------------------------------------------------------------
@router.post("/projects")
async def create_project(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    name = (body.get("name") or "").strip()
    if not name:
        return _err(400, "name_required")
    env = body.get("environment_scope", "dev")
    if env not in ("dev", "test", "nonprod"):
        return _err(400, "invalid_environment_scope")
    project = await _projects.create_project(
        name=name,
        description=body.get("description"),
        environment_scope=env,
        requester=ctx["identity_key"],
    )
    await _audit(
        "multi_project_create",
        f"project {project['project_key']} created",
        "created",
        {
            "project_id": project["project_id"],
            "actor": ctx["identity_key"],
            "reason": reason,
            "production_executed": False,
        },
    )
    return {"status": "created", "project": project, "production_executed": False}


@router.post("/projects/{project_id}/work-items")
async def create_work_item(project_id: str, request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    proj = await _projects.get_project(project_id)
    if not proj:
        return _err(404, "project_not_found")
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    title = (body.get("title") or "").strip()
    if not title:
        return _err(400, "title_required")
    # production_effect work items are allowed to be created, but cannot be dispatched
    # directly (lifecycle routes them to waiting_approval).
    production_effect = bool(body.get("production_effect", False))
    wi = await _items.create_work_item(
        project_id=project_id,
        title=title,
        description=body.get("description"),
        work_type=body.get("work_type", "task"),
        priority=body.get("priority", "medium"),
        item_source=body.get("source", "multi_project_api"),
        requested_by=ctx["identity_key"],
        requires_human_approval=bool(body.get("requires_human_approval", False)),
        production_effect=production_effect,
    )
    await _items.record_event(
        project_id=project_id,
        work_item_id=wi["id"],
        event_type="work_item_created",
        from_state=None,
        to_state="created",
        actor=ctx["identity_key"],
        role=ctx["role"],
        reason=reason,
        correlation_id=wi["id"],
        metadata=build_audit_metadata(
            event_type="work_item_created",
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            project_id=project_id,
            work_item_id=wi["id"],
            correlation_id=wi["id"],
        ),
    )
    await _audit(
        "multi_project_work_item_create",
        f"work item {wi['work_item_key']} created",
        "created",
        {
            "project_id": project_id,
            "work_item_id": wi["id"],
            "actor": ctx["identity_key"],
            "reason": reason,
            "production_executed": False,
        },
    )
    return {"status": "created", "work_item": wi, "production_executed": False}


@router.post("/work-items/{work_item_id}/dispatch")
async def dispatch_work_item(work_item_id: str, request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    wi = await _items.get_work_item(work_item_id)
    if not wi:
        return _err(404, "work_item_not_found")
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    project_id = wi["project_id"]
    proj = await _projects.get_project(project_id)
    if not proj:
        return _err(404, "project_not_found")
    correlation_id = work_item_id

    # production_effect: route to waiting_approval, NEVER dispatch directly.
    if wi["production_effect"]:
        await _advance(
            project_id,
            wi,
            target_state="waiting_approval",
            ctx=ctx,
            reason=reason,
            event_type="work_item_blocked",
        )
        await _audit(
            "multi_project_dispatch_blocked",
            f"work item {wi['work_item_key']} requires approval",
            "waiting_approval",
            {
                "project_id": project_id,
                "work_item_id": work_item_id,
                "actor": ctx["identity_key"],
                "reason": reason,
                "production_executed": False,
            },
        )
        return {
            "status": "waiting_approval",
            "dispatched": False,
            "production_executed": False,
            "reason": "production_effect requires human approval",
        }

    # Build the dispatch event (refuses forbidden targets / production effect).
    try:
        event = dispatcher.build_dispatch_event(
            project_id=project_id,
            project_key=proj["project_key"],
            work_item_id=work_item_id,
            work_item_key=wi["work_item_key"],
            dispatch_key=f"DSP-{uuid.uuid4().hex[:8]}",
            work_type=wi["work_type"] or "task",
            correlation_id=correlation_id,
            production_effect=False,
        )
    except DispatchError as e:
        await _advance(
            project_id,
            wi,
            target_state="blocked",
            ctx=ctx,
            reason=str(e),
            event_type="work_item_blocked",
        )
        return _err(409, f"dispatch_blocked: {e}")

    await _advance(
        project_id,
        wi,
        target_state="dispatched",
        ctx=ctx,
        reason=reason,
        event_type="work_item_dispatched",
    )
    await _items.set_assigned_agent(work_item_id, event["target_agent"])
    dispatch = await _items.create_dispatch(
        project_id=project_id,
        work_item_id=work_item_id,
        dispatch_key=event["dispatch_key"],
        target_agent=event["target_agent"],
        target_stream=event["target_stream"],
        correlation_id=correlation_id,
    )
    await _publish(event["target_stream"], {"event": "work_item_dispatched", **event})
    await _audit(
        "multi_project_dispatch",
        f"work item {wi['work_item_key']} dispatched",
        "dispatched",
        {
            "project_id": project_id,
            "work_item_id": work_item_id,
            "dispatch_id": dispatch["id"],
            "target_agent": event["target_agent"],
            "actor": ctx["identity_key"],
            "reason": reason,
            "production_executed": False,
        },
    )
    return {
        "status": "dispatched",
        "dispatched": True,
        "dispatch": dispatch,
        "production_executed": False,
        "github_write_performed": False,
        "argocd_sync_performed": False,
        "external_notification_send_performed": False,
    }


async def _advance(
    project_id: str, wi: dict, *, target_state: str, ctx: dict, reason: str, event_type: str
) -> None:
    """Advance a work item to target_state through the legal lifecycle path, recording
    one event per hop. production_effect routes ready_for_dispatch -> waiting_approval."""
    paths = {
        "dispatched": ["triaged", "ready_for_dispatch", "dispatched"],
        "waiting_approval": ["triaged", "ready_for_dispatch", "waiting_approval"],
        "blocked": ["blocked"],
    }
    current = wi["lifecycle_state"]
    for nxt in paths[target_state]:
        if current == nxt:
            continue
        if not lifecycle.can_transition(current, nxt):
            continue
        await _items.set_lifecycle_state(wi["id"], nxt)
        await _items.record_event(
            project_id=project_id,
            work_item_id=wi["id"],
            event_type=event_type if nxt == target_state else "work_item_triaged",
            from_state=current,
            to_state=nxt,
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            correlation_id=wi["id"],
            metadata=build_audit_metadata(
                event_type=event_type,
                actor=ctx["identity_key"],
                role=ctx["role"],
                reason=reason,
                project_id=project_id,
                work_item_id=wi["id"],
                correlation_id=wi["id"],
            ),
        )
        current = nxt


__all__ = ["router"]
