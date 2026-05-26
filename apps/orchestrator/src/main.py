import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from incidents_api import (
    ack_incident_with_side_effects,
    create_incident_with_side_effects,
    resolve_incident_with_side_effects,
)
from progress import build_progress, build_retry_timeline
from resume_engine import ResumeEngine, ResumeError
from shared.sdk.agent_execution.store import AgentExecutionStore
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
    return {
        "task_id": progress["task_id"],
        "workflow_id": progress["workflow_id"],
        "traces": progress["traces"],
        "current_stage": progress["current_stage"],
        "execution_status": progress["execution_status"],
        "approval_status": progress["approval_status"],
        "agent_timeline": progress["agent_timeline"],
        "retry_timeline": progress["retry_timeline"],
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
