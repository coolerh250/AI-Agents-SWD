import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from alert_receiver import router as alert_receiver_router
from approval_policy_api import router as approval_policy_router
from incidents_api import (
    ack_incident_with_side_effects,
    create_incident_with_side_effects,
    resolve_incident_with_side_effects,
)
from operations import router as operations_router
from progress import build_audit_timeline, build_progress, build_retry_timeline
from resume_engine import ResumeEngine, ResumeError
from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.audit.store import AuditStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.http_clients.policy_http_client import PolicyHttpClient
from shared.sdk.incidents import IncidentStore
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import WORKFLOW_FAILED_TOTAL, install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
    start_span,
)
from shared.sdk.task_execution import TaskExecutionStore, classify_execution_mode
from shared.sdk.workflow_store.store import WorkflowStore
from workflow import run_mock_workflow, workflow_state_schema
from workflow_events import WorkflowEventConsumer

setup_tracing("orchestrator")
instrument_asyncpg()
instrument_redis()
instrument_httpx()

TERMINAL_STAGES = {"completed", "canceled", "aborted", "rejected"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _terminate_workflow(task_id: str, new_stage: str, reason: str) -> dict:
    """Move a workflow to ``canceled`` or ``aborted`` and persist the reason.

    Only a non-terminal workflow can be terminated. Mock-safe: it records
    bookkeeping only — no production action runs.
    """
    with start_span(
        "workflow.failed",
        **{
            "service.name": "orchestrator",
            "task_id": task_id,
            "agent": "orchestrator",
            "event_type": "workflow_failed",
            "workflow.terminal_stage": new_stage,
            "workflow.reason": reason,
        },
    ):
        store = WorkflowStore()
        try:
            workflow = await store.get_workflow_state(task_id)
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"workflow store unavailable: {exc}"
            ) from exc
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        current = workflow["stage"]
        if current in TERMINAL_STAGES:
            raise HTTPException(
                status_code=409,
                detail=f"workflow {task_id} is {current}; cannot {new_stage}",
            )
        state = dict(workflow["state"]) if isinstance(workflow["state"], dict) else {}
        execution_result = (
            dict(workflow["execution_result"])
            if isinstance(workflow["execution_result"], dict)
            else {}
        )
        timestamp_key = "canceled_at" if new_stage == "canceled" else "aborted_at"
        reason_key = "cancel_reason" if new_stage == "canceled" else "abort_reason"
        timestamp = _utcnow_iso()
        state["stage"] = new_stage
        state[timestamp_key] = timestamp
        state[reason_key] = reason
        execution_result["status"] = new_stage
        execution_result[timestamp_key] = timestamp
        execution_result[reason_key] = reason
        execution_result["production_executed"] = False
        state["execution_result"] = execution_result
        try:
            updated = await store.update_workflow_state(
                task_id,
                stage=new_stage,
                state=state,
                approval_required=bool(workflow["approval_required"]),
                approval_status=str(workflow["approval_status"] or "none"),
                risk_level=str(workflow["risk_level"] or "unknown"),
                execution_result=execution_result,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"workflow store unavailable: {exc}"
            ) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        message = f"workflow {task_id} {new_stage}"
        if reason:
            message = f"{message}: {reason}"
        WORKFLOW_FAILED_TOTAL.labels(reason=new_stage).inc()
        await send_notification(task_id, f"workflow.{new_stage}", message)
        return updated


APPROVALS_STREAM = "stream.approvals"
RESUME_GROUP = "orchestrator-resume-group"
RESUME_CONSUMER = "orchestrator-1"


async def _approval_listener(stop_event: asyncio.Event) -> None:
    """Consume approval.* events from stream.approvals and resume workflows.

    Uses a Redis consumer group (XREADGROUP BLOCK) — no application polling.
    """
    bus = RedisStreamEventBus()
    engine = ResumeEngine()
    while not stop_event.is_set():
        try:
            events = await bus.consume_events(
                APPROVALS_STREAM, RESUME_GROUP, RESUME_CONSUMER, block_ms=2000
            )
            for event in events:
                payload = event.get("event", {})
                name = payload.get("event")
                task_id = payload.get("task_id")
                if task_id and name in ("approval.approved", "approval.rejected"):
                    decision = "approved" if name == "approval.approved" else "rejected"
                    with contextlib.suppress(Exception):
                        await engine.on_approval_event(task_id, decision)
                await bus.ack_event(APPROVALS_STREAM, RESUME_GROUP, event["id"])
        except asyncio.CancelledError:
            break
        except Exception:  # transient Redis error: back off and retry
            await asyncio.sleep(1)
    with contextlib.suppress(Exception):
        await bus.close()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runtime recovery: reconcile waiting_approval workflows that were approved
    # while the orchestrator was down.
    with contextlib.suppress(Exception):
        await ResumeEngine().resume_approved_workflows()
    stop_event = asyncio.Event()
    listener = asyncio.create_task(_approval_listener(stop_event))
    events_consumer = WorkflowEventConsumer()
    events_task = asyncio.create_task(events_consumer.run(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        listener.cancel()
        events_task.cancel()
        await asyncio.gather(listener, events_task, return_exceptions=True)


app = FastAPI(title="orchestrator", lifespan=lifespan)
instrument_fastapi(app, "orchestrator")
install_metrics_endpoint(app)
# Stage 20: unified read-only operator view. Mounted on /operations/*.
app.include_router(operations_router)
app.include_router(approval_policy_router)
# Stage 40: external alert receiver. Mounted on /alerts/*.
app.include_router(alert_receiver_router)


@app.get("/health")
def health():
    return {"service": "orchestrator", "status": "ok"}


@app.post("/workflow/test")
async def workflow_test(payload: dict):
    return await run_mock_workflow(payload)


@app.post("/workflow/policy-test")
async def workflow_policy_test(action: dict):
    return await PolicyHttpClient().evaluate(action.get("type", ""))


@app.get("/workflow/schema")
def workflow_schema():
    return workflow_state_schema()


@app.get("/workflow")
async def list_workflows(status: str | None = None):
    try:
        workflows = await WorkflowStore().list_workflows(status)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    return {"count": len(workflows), "workflows": workflows}


@app.post("/workflow/resume/{task_id}")
async def resume_workflow(task_id: str):
    try:
        return await ResumeEngine().resume_workflow(task_id)
    except ResumeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc


@app.post("/workflow/resume-after-clarification/{task_id}")
async def resume_after_clarification(task_id: str) -> dict:
    """Stage 27 — drive the workflow forward after a clarification answer.

    If every clarification request for the task is now ``answered``, the
    work item is re-classified and (when sufficient) marked
    ``ready_for_development``. The orchestrator then re-publishes the
    intake event so the existing agent pipeline can run. The endpoint
    is safe to call repeatedly: if there is still an open clarification,
    the work item stays at ``needs_clarification`` and the response
    reports the open count.
    """
    store = TaskExecutionStore()
    work_item = await store.get_work_item(task_id)
    if work_item is None:
        raise HTTPException(status_code=404, detail="task_work_item not found")
    open_clarifications = await store.list_clarification_requests(task_id, status="open")
    if open_clarifications:
        return {
            "task_id": task_id,
            "status": work_item.status,
            "resumed": False,
            "open_clarifications": len(open_clarifications),
            "reason": "open_clarifications_pending",
            "generated_at": _utcnow_iso(),
        }
    answered = await store.list_clarification_requests(task_id, status="answered")
    # Reclassify using ONLY the user-provided answers. The original
    # description likely still contains the trigger token ("TBD",
    # "?", "請再確認" …) that put the work item into
    # needs_clarification in the first place; if we re-fed it to the
    # classifier the work item would never escape the loop. Falling
    # back to the original description only when no answer is recorded
    # keeps the behaviour deterministic when an operator force-calls
    # the endpoint without an answer.
    answer_text = " ".join((c.user_response or "").strip() for c in answered).strip()
    combined_description = answer_text or work_item.description
    classification = classify_execution_mode(
        request_type=work_item.request_type,
        description=combined_description,
        explicit_mode=work_item.execution_mode,
    )
    new_status = (
        "needs_clarification" if classification.clarification_required else "ready_for_development"
    )
    await store.update_work_item_status(task_id, new_status)
    if new_status == "needs_clarification":
        # Still not enough info — keep the work item in clarification.
        return {
            "task_id": task_id,
            "status": new_status,
            "resumed": False,
            "reason": classification.reason,
            "generated_at": _utcnow_iso(),
        }
    # Re-publish the task on stream.tasks so the agent pipeline restarts.
    workflow = await WorkflowStore().get_workflow_state(task_id)
    request_payload: dict = {}
    workflow_id = work_item.workflow_id or ""
    if workflow is not None:
        state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
        if isinstance(state, dict):
            request_payload = (
                dict(state.get("request") or {}) if isinstance(state.get("request"), dict) else {}
            )
            workflow_id = workflow_id or str(state.get("workflow_id") or "")
    if not request_payload:
        request_payload = {"type": work_item.request_type, "description": combined_description}
    # Override the description so the agents see the clarified version on
    # restart (mock — the request object kept its original description on
    # disk, so we patch it here).
    request_payload["description"] = combined_description
    from dispatch import dispatch_task as _dispatch

    dispatched = await _dispatch(
        task_id,
        workflow_id,
        request_payload,
        "discord-clarification",
        trace_id="",
    )
    await send_notification(
        task_id,
        "task.ready_for_development",
        f"task {task_id} ready for development after clarification",
    )
    return {
        "task_id": task_id,
        "status": new_status,
        "resumed": dispatched,
        "execution_mode": classification.execution_mode,
        "generated_at": _utcnow_iso(),
    }


@app.post("/workflow/cancel/{task_id}")
async def cancel_workflow(task_id: str, payload: dict | None = None):
    reason = str((payload or {}).get("reason", ""))
    return await _terminate_workflow(task_id, "canceled", reason)


@app.post("/workflow/abort/{task_id}")
async def abort_workflow(task_id: str, payload: dict | None = None):
    reason = str((payload or {}).get("reason", ""))
    return await _terminate_workflow(task_id, "aborted", reason)


async def _retry_timeline_for(task_id: str, limit: int = 200) -> list[dict]:
    """Best-effort DLQ scan for a task_id, ready for the progress / timeline API."""
    import json

    bus = RedisStreamEventBus()
    try:
        entries = await bus.client.xrevrange("stream.deadletter", "+", "-", count=limit)
    except Exception:
        return []
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
    matches: list[dict] = []
    for entry_id, fields in entries:
        try:
            payload = json.loads(fields.get("data", "{}"))
        except (ValueError, TypeError):
            continue
        if payload.get("task_id") == task_id:
            matches.append({"id": entry_id, "payload": payload})
    return build_retry_timeline(matches)


@app.get("/workflow/progress/{task_id}")
async def workflow_progress(task_id: str):
    try:
        workflow = await WorkflowStore().get_workflow_state(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        executions = await AgentExecutionStore().list_executions(task_id=task_id)
    except Exception:  # progress is still useful without the execution detail
        executions = []
    retry_timeline = await _retry_timeline_for(task_id)
    return build_progress(workflow, executions, retry_timeline=retry_timeline)


@app.get("/workflow/timeline/{task_id}")
async def workflow_timeline(task_id: str):
    """Return a richer chronological timeline for a workflow.

    This collapses workflow_states, agent_executions, and DLQ entries into one
    ordered list so an operator (or a dashboard) can see the workflow's full
    distributed timeline — dispatch -> intake -> requirement -> development ->
    qa -> devops -> retry -> approval -> completion — without joining the
    underlying tables themselves.
    """
    try:
        workflow = await WorkflowStore().get_workflow_state(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        executions = await AgentExecutionStore().list_executions(task_id=task_id)
    except Exception:
        executions = []
    retry_timeline = await _retry_timeline_for(task_id)
    progress = build_progress(workflow, executions, retry_timeline=retry_timeline)
    audit_events: list[dict] = []
    try:
        audit_events = await AuditStore().get_audit_logs(task_id)
    except Exception:  # audit_logs is best-effort — timeline is still useful without it
        audit_events = []
    return {
        "task_id": progress["task_id"],
        "workflow_id": progress["workflow_id"],
        "traces": progress["traces"],
        "current_stage": progress["current_stage"],
        "execution_status": progress["execution_status"],
        "approval_status": progress["approval_status"],
        "agent_timeline": progress["agent_timeline"],
        "retry_timeline": progress["retry_timeline"],
        "audit_timeline": build_audit_timeline(audit_events),
        "github": progress.get("github"),
        "pr_url": progress.get("pr_url", ""),
        "github_status": progress.get("github_status", ""),
        "github_dry_run": progress.get("github_dry_run"),
        "timestamps": progress["timestamps"],
    }


@app.get("/workflow/replay/{task_id}")
async def replay_workflow(task_id: str):
    try:
        workflow = await ResumeEngine().replay_workflow_state(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return {"task_id": task_id, "executed": False, "replay": workflow}


@app.get("/workflow/{task_id}")
async def get_workflow(task_id: str):
    try:
        workflow = await WorkflowStore().get_workflow_state(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@app.get("/incidents")
async def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    task_id: str | None = None,
    workflow_id: str | None = None,
) -> dict:
    try:
        incidents = await IncidentStore().list_incidents(
            status=status,
            severity=severity,
            task_id=task_id,
            workflow_id=workflow_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    return {
        "count": len(incidents),
        "incidents": [incident.to_dict() for incident in incidents],
    }


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    try:
        incident = await IncidentStore().get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident.to_dict()


@app.post("/incidents")
async def create_incident(payload: dict) -> dict:
    summary = str((payload or {}).get("summary", "")).strip()
    if not summary:
        raise HTTPException(status_code=400, detail="summary is required")
    severity = str((payload or {}).get("severity", "sev3"))
    source = str((payload or {}).get("source", "operator"))
    task_id = (payload or {}).get("task_id")
    workflow_id = (payload or {}).get("workflow_id")
    details = (payload or {}).get("details") or {}
    if not isinstance(details, dict):
        raise HTTPException(status_code=400, detail="details must be an object")
    try:
        incident = await create_incident_with_side_effects(
            IncidentStore(),
            severity=severity,
            source=source,
            summary=summary,
            task_id=task_id,
            workflow_id=workflow_id,
            details=details,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    return incident.to_dict()


@app.post("/incidents/{incident_id}/ack")
async def acknowledge_incident(incident_id: str) -> dict:
    try:
        incident = await ack_incident_with_side_effects(IncidentStore(), incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident.to_dict()


@app.post("/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str) -> dict:
    try:
        incident = await resolve_incident_with_side_effects(IncidentStore(), incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident.to_dict()
