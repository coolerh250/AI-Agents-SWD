import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException

from resume_engine import ResumeEngine, ResumeError
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.http_clients.policy_http_client import PolicyHttpClient
from shared.sdk.workflow_store.store import WorkflowStore
from workflow import run_mock_workflow, workflow_state_schema

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
    try:
        yield
    finally:
        stop_event.set()
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)


app = FastAPI(title="orchestrator", lifespan=lifespan)


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
