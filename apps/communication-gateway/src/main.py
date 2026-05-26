import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.notifications.client import NotificationClient
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")
TASKS_STREAM = "stream.tasks"

setup_tracing("communication-gateway")
instrument_asyncpg()
instrument_redis()
instrument_httpx()
app = FastAPI(title="communication-gateway")
instrument_fastapi(app, "communication-gateway")
install_metrics_endpoint(app)


class IntakeRequest(BaseModel):
    task_id: str | None = None
    request: dict = Field(default_factory=dict)
    publish_to_stream: bool = False


class TestNotification(BaseModel):
    task_id: str = "gateway-test"
    event_type: str = "test"
    message: str = "test notification"


@app.get("/health")
def health() -> dict:
    return {"service": "communication-gateway", "status": "ok"}


@app.post("/intake/mock")
async def intake_mock(payload: IntakeRequest) -> dict:
    task_id = payload.task_id or f"intake-{uuid.uuid4().hex[:12]}"
    if payload.publish_to_stream:
        # Stream mode: hand the task to stream.tasks for the intake-agent to consume.
        bus = RedisStreamEventBus()
        try:
            message = {
                "event": "task.created",
                "task_id": task_id,
                "source": "communication-gateway",
                "request": payload.request,
            }
            published_id = await bus.publish_event(TASKS_STREAM, message)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
        finally:
            await bus.close()
        return {
            "task_id": task_id,
            "mode": "stream",
            "stream": TASKS_STREAM,
            "published_id": published_id,
        }
    # Default mode: run the workflow directly through the orchestrator.
    body = {"task_id": task_id, "source": "communication-gateway", "request": payload.request}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/workflow/test", json=body)
            response.raise_for_status()
            result = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    return {
        "task_id": result.get("task_id", task_id),
        "mode": "orchestrator",
        "stage": result.get("stage"),
        "approval_required": result.get("approval_required"),
        "workflow_result": result,
    }


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/workflow/{task_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="task not found")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="orchestrator error")
    return response.json()


@app.post("/notifications/test")
async def notifications_test(payload: TestNotification) -> dict:
    client = NotificationClient()
    try:
        return await client.publish_notification(
            payload.task_id, payload.event_type, payload.message
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
    finally:
        await client.close()


@app.get("/notifications")
async def list_notifications(count: int = 20) -> dict:
    client = NotificationClient()
    try:
        notifications = await client.list_notifications(count=count)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
    finally:
        await client.close()
    return {"count": len(notifications), "notifications": notifications}


@app.get("/executions")
async def list_executions(
    task_id: str | None = None,
    agent: str | None = None,
    status: str | None = None,
) -> dict:
    try:
        executions = await AgentExecutionStore().list_executions(
            task_id=task_id, agent=agent, status=status
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    return {"count": len(executions), "executions": executions}
