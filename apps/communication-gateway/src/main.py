import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.http_clients.github_http_client import GitHubAutomationHttpClient
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


class ProjectWorkItemIntake(BaseModel):
    project_key: str | None = None
    project_name: str | None = None
    title: str
    description: str | None = None
    work_type: str = "task"
    environment_scope: str = "dev"
    create_project_if_missing: bool = True


class TestNotification(BaseModel):
    task_id: str = "gateway-test"
    event_type: str = "test"
    message: str = "test notification"


# Step 57 -- MOCK project-scoped work-item intake. Creates a non-production project
# (if allowed) + a work item in the delivery domain. No Slack/email real send, no
# production action, no GitHub write. The work item starts at lifecycle `created`.
@app.post("/intake/mock/project-work-item")
async def intake_mock_project_work_item(payload: ProjectWorkItemIntake) -> dict:
    from shared.sdk.projects import ProjectStore
    from shared.sdk.work_items import WorkItemStore
    from shared.sdk.work_items.events import build_audit_metadata

    projects = ProjectStore()
    items = WorkItemStore()
    existing = await projects.list_projects()
    match = next((p for p in existing if p["project_key"] == payload.project_key), None)
    if match is None:
        if not payload.create_project_if_missing:
            raise HTTPException(status_code=404, detail="project_not_found")
        env = (
            payload.environment_scope
            if payload.environment_scope in ("dev", "test", "nonprod")
            else "dev"
        )
        match = await projects.create_project(
            name=payload.project_name or payload.project_key or "Mock Project",
            description="mock intake project",
            environment_scope=env,
            requester="mock-intake",
        )
    wi = await items.create_work_item(
        project_id=match["project_id"],
        title=payload.title,
        description=payload.description,
        work_type=payload.work_type,
        priority="medium",
        item_source="mock_intake",
        requested_by="mock-intake",
        requires_human_approval=False,
        production_effect=False,
    )
    await items.record_event(
        project_id=match["project_id"],
        work_item_id=wi["id"],
        event_type="work_item_created",
        from_state=None,
        to_state="created",
        actor="mock-intake",
        role="intake",
        reason="mock intake",
        correlation_id=wi["id"],
        metadata=build_audit_metadata(
            event_type="work_item_created",
            actor="mock-intake",
            role="intake",
            reason="mock intake",
            project_id=match["project_id"],
            work_item_id=wi["id"],
            correlation_id=wi["id"],
        ),
    )
    return {
        "status": "created",
        "mode": "mock",
        "project": match,
        "work_item": wi,
        "production_executed": False,
        "external_send_performed": False,
    }


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


class GitHubDemoPRRequest(BaseModel):
    task_id: str = "gateway-github-demo"
    workflow_id: str = ""
    repo: str | None = None
    base_branch: str = "main"
    branch_name: str = ""
    title: str = "[AI-Agents-SWD Test] gateway github-automation demo PR"
    body_summary: str = "Dispatched from communication-gateway dry-run."
    file_path: str = "docs/automation-demo.md"
    file_content: str = "# AI Agents SWD demo file (gateway)\n"
    dry_run: bool | None = True


@app.post("/github/demo-pr")
async def github_demo_pr(payload: GitHubDemoPRRequest) -> dict:
    client = GitHubAutomationHttpClient()
    try:
        return await client.demo_pr(
            payload.model_dump(exclude_none=False),
            task_id=payload.task_id,
            workflow_id=payload.workflow_id,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail=f"github-automation unavailable: {exc}"
        ) from exc
