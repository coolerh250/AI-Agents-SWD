"""Operations Control API — unified read-only operator view.

Stage 20 collapses the platform's scattered status surfaces
(workflow / agent_executions / audit_logs / incidents / DLQ /
deployment_records / Redis streams / trace / metrics) into one
``/operations/*`` namespace served from the orchestrator.

Design contract:

* **Read-only.** Every endpoint queries DB / Redis / sibling HTTP
  services; nothing is inserted, updated, deleted, ACKed, or
  replayed. There are no destructive paths in this module.
* **Safe degradation.** A failing data source NEVER fails the whole
  view — the relevant section returns its empty shape plus a
  ``warnings`` entry. The exception is ``/operations/workflows/
  {task_id}`` which returns 404 only when the workflow row itself
  doesn't exist (every other section degrades to empty + warning).
* **No secrets in response.** ``github_has_token`` is the only place
  the token is observed and it is reduced to a boolean; the token
  value never leaves the env var.
* **Metrics + spans.** Every endpoint records
  ``operations_requests_total{endpoint,result}``,
  ``operations_request_duration_seconds{endpoint}``, and an
  ``operations.<view>`` span carrying ``endpoint`` /  ``result`` /
  ``task_id`` / ``agent`` attributes as appropriate.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from progress import build_audit_timeline, build_progress, build_retry_timeline
from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.audit.store import AuditStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.incidents import IncidentStore
from shared.sdk.notifications.store import NotificationDeliveryStore
from shared.sdk.observability.metrics import (
    OPERATIONS_REQUEST_DURATION_SECONDS,
    OPERATIONS_REQUEST_FAILURES_TOTAL,
    OPERATIONS_REQUESTS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.code_workspace import CodeWorkspaceStore
from shared.sdk.qa import QAStore
from shared.sdk.task_execution import TaskExecutionStore
from shared.sdk.workflow_store.store import WorkflowStore

router = APIRouter(prefix="/operations", tags=["operations"])

# ---------------------------------------------------------------------------
# Platform topology (kept here so the operations view stays self-contained).
# ---------------------------------------------------------------------------

PIPELINE_AGENTS: list[dict[str, str]] = [
    {
        "name": "intake-agent",
        "host": "intake-agent",
        "port": "8010",
        "input_stream": "stream.tasks",
        "output_stream": "stream.requirements",
        "consumer_group": "intake-agent-group",
    },
    {
        "name": "requirement-agent",
        "host": "requirement-agent",
        "port": "8011",
        "input_stream": "stream.requirements",
        "output_stream": "stream.development",
        "consumer_group": "requirement-agent-group",
    },
    {
        "name": "development-agent",
        "host": "development-agent",
        "port": "8012",
        "input_stream": "stream.development",
        "output_stream": "stream.qa",
        "consumer_group": "development-agent-group",
    },
    {
        "name": "qa-agent",
        "host": "qa-agent",
        "port": "8013",
        "input_stream": "stream.qa",
        "output_stream": "stream.deployments",
        "consumer_group": "qa-agent-group",
    },
    {
        "name": "devops-agent",
        "host": "devops-agent",
        "port": "8014",
        "input_stream": "stream.deployments",
        "output_stream": "stream.devops",
        "consumer_group": "devops-agent-group",
    },
]
_AGENT_INDEX = {agent["name"]: agent for agent in PIPELINE_AGENTS}

# Streams the operations view inspects. Each row carries the canonical
# consumer-group name for that stream — surface it so an operator can
# correlate XINFO output without grepping init_redis_streams.sh.
PLATFORM_STREAMS: list[dict[str, str]] = [
    {"name": "stream.tasks", "primary_group": "orchestrator-group"},
    {"name": "stream.requirements", "primary_group": "requirement-agent-group"},
    {"name": "stream.development", "primary_group": "development-agent-group"},
    {"name": "stream.qa", "primary_group": "qa-agent-group"},
    {"name": "stream.deployments", "primary_group": "devops-agent-group"},
    {"name": "stream.devops", "primary_group": "orchestrator-workflow-group"},
    {"name": "stream.approvals", "primary_group": "approval-group"},
    {"name": "stream.audit", "primary_group": "audit-group"},
    {"name": "stream.notifications", "primary_group": "notification-group"},
    {"name": "stream.deadletter", "primary_group": "retry-scheduler-group"},
    {"name": "stream.deadletter.terminal", "primary_group": "terminal-failure-group"},
]

DEAD_LETTER_STREAM = "stream.deadletter"
TERMINAL_FAILURE_STREAM = "stream.deadletter.terminal"

GITHUB_AUTOMATION_URL = os.environ.get("GITHUB_AUTOMATION_URL", "http://github-automation:8005")

# Stage 23: audit decision_types emitted by the controlled-real GitHub
# validation flow. /operations/github/{task_id} and the workflow view
# both surface them under a dedicated ``real_test`` section.
REAL_TEST_DECISION_TYPES = (
    "github_real_test",
    "github_real_test_blocked",
    "github_real_test_failed",
)
ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "http://alertmanager:9093")

# Workflows considered "recent" by /operations/summary.
RECENT_WORKFLOW_WINDOW_SECONDS = 24 * 60 * 60


# ---------------------------------------------------------------------------
# Plumbing helpers.
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stream_status(consumers: int, pending: int, lag: int, group_present: bool) -> str:
    if not group_present:
        return "unknown"
    if pending > 0:
        return "warning"
    if lag > 0 and consumers >= 1:
        return "warning"
    if lag > 0 and consumers == 0:
        return "informational"
    return "ok"


async def _xinfo_stream(bus: RedisStreamEventBus, stream: str) -> dict[str, Any]:
    """Return a flat snapshot of one Redis stream + its primary group.

    Pure-read: no XGROUP CREATE, no XADD. If the stream does not exist
    (XINFO returns an error) the helper returns ``length=0`` with
    ``status=unknown``.
    """
    info: dict[str, Any] = {
        "name": stream,
        "length": 0,
        "groups": [],
        "consumers": 0,
        "pending": 0,
        "lag": 0,
        "last_delivered_id": "",
        "status": "unknown",
    }
    try:
        length = await bus.client.xlen(stream)
        info["length"] = _safe_int(length)
    except Exception:
        return info
    groups_raw: list[Any] = []
    try:
        groups_raw = await bus.client.xinfo_groups(stream)
    except Exception:
        groups_raw = []
    groups: list[dict[str, Any]] = []
    consumers_total = 0
    pending_total = 0
    lag_total = 0
    last_delivered_id = ""
    for entry in groups_raw or []:
        if not isinstance(entry, dict):
            continue
        consumers_total += _safe_int(entry.get("consumers"))
        pending_total += _safe_int(entry.get("pending"))
        lag_total += _safe_int(entry.get("lag"))
        gname = str(entry.get("name") or "")
        gdelivered = str(entry.get("last-delivered-id") or "")
        if not last_delivered_id and gdelivered:
            last_delivered_id = gdelivered
        groups.append(
            {
                "name": gname,
                "consumers": _safe_int(entry.get("consumers")),
                "pending": _safe_int(entry.get("pending")),
                "lag": _safe_int(entry.get("lag")),
                "last_delivered_id": gdelivered,
            }
        )
    info["groups"] = groups
    info["consumers"] = consumers_total
    info["pending"] = pending_total
    info["lag"] = lag_total
    info["last_delivered_id"] = last_delivered_id
    info["status"] = _stream_status(consumers_total, pending_total, lag_total, bool(groups))
    return info


async def _xrevrange_payloads(
    bus: RedisStreamEventBus, stream: str, count: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent ``count`` decoded events from a stream."""
    try:
        entries = await bus.client.xrevrange(stream, "+", "-", count=count)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for entry_id, fields in entries or []:
        raw = fields.get("data", "{}") if isinstance(fields, dict) else "{}"
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            payload = {"raw": raw}
        out.append({"id": entry_id, "payload": payload})
    return out


async def _http_get(url: str, timeout: float = 3.0) -> tuple[int, Any]:
    """GET ``url`` and return ``(status_code, body)``. Always swallows errors."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            try:
                body: Any = response.json()
            except Exception:
                body = {"raw": response.text[:512]}
            return response.status_code, body
    except Exception as exc:
        return 0, {"error": f"{exc.__class__.__name__}: {exc}"}


async def _connect(database_url: str | None = None) -> Any:
    """Open a short-lived asyncpg connection for ad-hoc counts."""
    import asyncpg

    dsn = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents"
    )
    return await asyncpg.connect(dsn=dsn, timeout=5)


async def _scalar(sql: str, *params: Any) -> int:
    """Best-effort scalar count query. Returns 0 on failure."""
    conn = None
    try:
        conn = await _connect()
        value = await conn.fetchval(sql, *params)
        return _safe_int(value)
    except Exception:
        return 0
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                await conn.close()


# ---------------------------------------------------------------------------
# Metrics + span instrumentation decorator.
# ---------------------------------------------------------------------------


def _instrument(
    endpoint: str,
    span_name: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Record request metrics + open an OTel span around an operations route.

    Uses ``functools.wraps`` so FastAPI keeps reading the wrapped function's
    signature (path params, query params, response model) through ``__wrapped__``
    — otherwise every route would 422 on its own path params.
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            span_attrs: dict[str, Any] = {
                "service.name": "orchestrator",
                "agent": "orchestrator",
                "endpoint": endpoint,
            }
            for key in ("task_id", "agent_name"):
                value = kwargs.get(key)
                if value:
                    span_attrs[key] = str(value)
            with start_span(span_name, **span_attrs) as span:
                try:
                    result = await func(*args, **kwargs)
                except HTTPException as exc:
                    OPERATIONS_REQUEST_FAILURES_TOTAL.labels(
                        endpoint=endpoint,
                        reason=("not_found" if exc.status_code == 404 else "store_error"),
                    ).inc()
                    OPERATIONS_REQUESTS_TOTAL.labels(
                        endpoint=endpoint,
                        result=("not_found" if exc.status_code == 404 else "error"),
                    ).inc()
                    OPERATIONS_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
                        time.perf_counter() - started
                    )
                    with contextlib.suppress(Exception):
                        span.set_attribute("result", "error")
                    raise
                except Exception:
                    OPERATIONS_REQUEST_FAILURES_TOTAL.labels(
                        endpoint=endpoint, reason="store_error"
                    ).inc()
                    OPERATIONS_REQUESTS_TOTAL.labels(endpoint=endpoint, result="error").inc()
                    OPERATIONS_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
                        time.perf_counter() - started
                    )
                    with contextlib.suppress(Exception):
                        span.set_attribute("result", "error")
                    raise
                OPERATIONS_REQUESTS_TOTAL.labels(endpoint=endpoint, result="ok").inc()
                OPERATIONS_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
                    time.perf_counter() - started
                )
                with contextlib.suppress(Exception):
                    span.set_attribute("result", "ok")
                return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# /operations/health
# ---------------------------------------------------------------------------


@router.get("/health")
def operations_health() -> dict:
    OPERATIONS_REQUESTS_TOTAL.labels(endpoint="/operations/health", result="ok").inc()
    return {"service": "operations", "status": "ok", "generated_at": _utcnow_iso()}


# ---------------------------------------------------------------------------
# /operations/summary
# ---------------------------------------------------------------------------


async def _services_summary() -> dict[str, Any]:
    services = [
        ("orchestrator", "http://orchestrator:8000/health"),
        ("policy-engine", "http://policy-engine:8001/health"),
        ("approval-engine", "http://approval-engine:8002/health"),
        ("audit-service", "http://audit-service:8003/health"),
        ("communication-gateway", "http://communication-gateway:8004/health"),
        ("github-automation", "http://github-automation:8005/health"),
        ("audit-worker", "http://audit-worker:8006/health"),
        ("discord-gateway", "http://discord-gateway:8007/health"),
        ("notification-worker", "http://notification-worker:8008/health"),
        ("intake-agent", "http://intake-agent:8010/health"),
        ("requirement-agent", "http://requirement-agent:8011/health"),
        ("development-agent", "http://development-agent:8012/health"),
        ("qa-agent", "http://qa-agent:8013/health"),
        ("devops-agent", "http://devops-agent:8014/health"),
        ("retry-scheduler", "http://retry-scheduler:8015/health"),
    ]
    out: dict[str, Any] = {"total": len(services), "healthy": 0, "services": []}
    for name, url in services:
        status, _ = await _http_get(url, timeout=2.0)
        ok = status == 200
        if ok:
            out["healthy"] += 1
        out["services"].append({"name": name, "url": url, "healthy": ok})
    return out


async def _workflows_summary() -> dict[str, Any]:
    summary = {
        "total": await _scalar("SELECT count(*) FROM workflow_states"),
        "completed": await _scalar("SELECT count(*) FROM workflow_states WHERE stage='completed'"),
        "failed": await _scalar("SELECT count(*) FROM workflow_states WHERE stage='failed'"),
        "waiting_approval": await _scalar(
            "SELECT count(*) FROM workflow_states WHERE stage='waiting_approval'"
        ),
        "canceled": await _scalar("SELECT count(*) FROM workflow_states WHERE stage='canceled'"),
        "aborted": await _scalar("SELECT count(*) FROM workflow_states WHERE stage='aborted'"),
        "in_progress": await _scalar(
            "SELECT count(*) FROM workflow_states WHERE stage='in_progress'"
        ),
        "recent_24h": await _scalar(
            "SELECT count(*) FROM workflow_states "
            "WHERE updated_at >= now() - interval '24 hours'"
        ),
    }
    return summary


async def _agents_summary() -> dict[str, Any]:
    total = await _scalar("SELECT count(*) FROM agent_executions")
    failed = await _scalar("SELECT count(*) FROM agent_executions WHERE status='failed'")
    completed = await _scalar("SELECT count(*) FROM agent_executions WHERE status='completed'")
    return {
        "count": len(PIPELINE_AGENTS),
        "agent_executions_total": total,
        "agent_executions_completed": completed,
        "agent_executions_failed": failed,
        "pipeline": [agent["name"] for agent in PIPELINE_AGENTS],
    }


async def _incidents_summary() -> dict[str, Any]:
    open_count = await _scalar("SELECT count(*) FROM incident_records WHERE status='open'")
    ack_count = await _scalar("SELECT count(*) FROM incident_records WHERE status='acknowledged'")
    resolved_count = await _scalar("SELECT count(*) FROM incident_records WHERE status='resolved'")
    return {
        "open": open_count,
        "acknowledged": ack_count,
        "resolved": resolved_count,
        "unresolved": open_count + ack_count,
    }


async def _dlq_summary(bus: RedisStreamEventBus) -> dict[str, Any]:
    deadletter = await _xinfo_stream(bus, DEAD_LETTER_STREAM)
    terminal = await _xinfo_stream(bus, TERMINAL_FAILURE_STREAM)
    return {
        "deadletter_length": deadletter["length"],
        "deadletter_terminal_length": terminal["length"],
    }


async def _github_summary() -> dict[str, Any]:
    return {
        "dry_run_pr_count": await _scalar(
            "SELECT count(*) FROM audit_logs WHERE decision_type='github_pr_integration'"
        ),
        "github_automation_audit_count": await _scalar(
            "SELECT count(*) FROM audit_logs WHERE decision_type='github_automation'"
        ),
        "default_dry_run": os.environ.get("GITHUB_DRY_RUN", "true").strip().lower() != "false",
        "has_token": bool(os.environ.get("GITHUB_TOKEN", "").strip()),
        "real_github_test_enabled": (
            os.environ.get("RUN_REAL_GITHUB_TEST", "false").strip().lower() == "true"
        ),
    }


async def _audit_summary() -> dict[str, Any]:
    return {
        "audit_logs_total": await _scalar("SELECT count(*) FROM audit_logs"),
        "audit_logs_recent_24h": await _scalar(
            "SELECT count(*) FROM audit_logs " "WHERE created_at >= now() - interval '24 hours'"
        ),
    }


async def _production_safety() -> dict[str, Any]:
    deployment_prod = await _scalar(
        "SELECT count(*) FROM deployment_records "
        "WHERE metadata->>'production_executed'='true' OR environment='production'"
    )
    deployment_env_prod = await _scalar(
        "SELECT count(*) FROM deployment_records WHERE environment='production'"
    )
    workflow_prod = await _scalar(
        "SELECT count(*) FROM workflow_states "
        "WHERE execution_result->>'production_executed'='true'"
    )
    unsafe = (deployment_prod > 0) or (deployment_env_prod > 0) or (workflow_prod > 0)
    return {
        "deployment_records_production_executed_true": deployment_prod,
        "deployment_records_environment_production": deployment_env_prod,
        "workflow_states_production_executed_true": workflow_prod,
        "result": "unsafe" if unsafe else "safe",
    }


async def _task_execution_summary() -> dict[str, Any]:
    """Stage 27 — aggregated counters for the work-item lifecycle."""
    try:
        counts = await TaskExecutionStore().counts()
    except Exception:
        counts = {
            "total_work_items": 0,
            "simple_task_count": 0,
            "delivery_task_count": 0,
            "scrum_project_count": 0,
            "needs_clarification_count": 0,
            "ready_for_development_count": 0,
            "blocked_count": 0,
        }
    return counts


async def _qa_summary() -> dict[str, Any]:
    """Stage 29 — aggregated counters for QA validation runs + auto-fix requests."""
    try:
        counts = await QAStore().counts()
    except Exception:
        counts = {
            "total_validation_runs": 0,
            "passed_runs": 0,
            "failed_runs": 0,
            "blocked_for_human_review_count": 0,
            "auto_fix_requested_count": 0,
            "total_findings": 0,
        }
    return counts


async def _code_generation_summary() -> dict[str, Any]:
    """Stage 28 — aggregated counters for the code workspace lifecycle."""
    try:
        counts = await CodeWorkspaceStore().counts()
    except Exception:
        counts = {
            "total_workspaces": 0,
            "ready_for_pr_draft": 0,
            "blocked_count": 0,
            "deterministic_count": 0,
            "total_artifacts": 0,
            "validated_artifacts": 0,
            "total_pr_drafts": 0,
        }
    return counts


async def _notification_delivery_summary() -> dict[str, Any]:
    """Aggregated Stage 22 notification delivery counters."""
    try:
        counts = await NotificationDeliveryStore().counts()
    except Exception:
        counts = {
            "total": 0,
            "simulated": 0,
            "delivered": 0,
            "failed": 0,
            "skipped": 0,
            "external_sent": 0,
        }
    return {
        "total_deliveries": counts["total"],
        "simulated_deliveries": counts["simulated"],
        "delivered_deliveries": counts["delivered"],
        "external_sent_deliveries": counts["external_sent"],
        "failed_deliveries": counts["failed"],
        "skipped_deliveries": counts["skipped"],
    }


@router.get("/summary")
@_instrument("/operations/summary", "operations.summary")
async def operations_summary() -> dict:
    bus = RedisStreamEventBus()
    try:
        services = await _services_summary()
        workflows = await _workflows_summary()
        agents = await _agents_summary()
        incidents = await _incidents_summary()
        dlq = await _dlq_summary(bus)
        github = await _github_summary()
        audit = await _audit_summary()
        safety = await _production_safety()
        notification_delivery = await _notification_delivery_summary()
        task_execution = await _task_execution_summary()
        code_generation = await _code_generation_summary()
        qa_summary = await _qa_summary()
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
    return {
        "generated_at": _utcnow_iso(),
        "services_summary": services,
        "workflows_summary": workflows,
        "agents_summary": agents,
        "incidents_summary": incidents,
        "dlq_summary": dlq,
        "github_summary": github,
        "audit_summary": audit,
        "notification_delivery_summary": notification_delivery,
        "task_execution_summary": task_execution,
        "code_generation_summary": code_generation,
        "qa_summary": qa_summary,
        "production_safety": safety,
    }


# ---------------------------------------------------------------------------
# /operations/workflows/{task_id}
# ---------------------------------------------------------------------------


def _build_github_section(
    workflow: dict[str, Any], deployment_metadata: dict[str, Any]
) -> dict[str, Any]:
    state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
    execution_result = (
        state.get("execution_result")
        if isinstance(state.get("execution_result"), dict)
        else (
            workflow.get("execution_result")
            if isinstance(workflow.get("execution_result"), dict)
            else {}
        )
    )
    github = execution_result.get("github") if isinstance(execution_result, dict) else None
    if not isinstance(github, dict):
        github = {}
    if not github and isinstance(deployment_metadata, dict):
        nested = deployment_metadata.get("github")
        if isinstance(nested, dict):
            github = nested
    return {
        "found": bool(github),
        "status": github.get("status", ""),
        "dry_run": github.get("dry_run") if isinstance(github, dict) else None,
        "issue_url": github.get("issue_url", ""),
        "branch": github.get("branch", ""),
        "pr_url": github.get("pr_url", ""),
        "pr_number": github.get("pr_number"),
        "checks_status": github.get("checks_status", ""),
        "event_type": github.get("event_type", ""),
        "error": github.get("error", ""),
    }


async def _deployment_record_for(task_id: str) -> dict[str, Any]:
    """Return the most-recent deployment_records row + decoded metadata."""
    conn = None
    try:
        conn = await _connect()
        row = await conn.fetchrow(
            "SELECT id, task_id, environment, status, metadata, "
            "created_at, updated_at FROM deployment_records "
            "WHERE task_id = $1 ORDER BY created_at DESC LIMIT 1",
            task_id,
        )
    except Exception:
        return {}
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                await conn.close()
    if row is None:
        return {}
    metadata = row["metadata"]
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            metadata = {}
    return {
        "deployment_record_id": str(row["id"]),
        "task_id": row["task_id"],
        "environment": row["environment"],
        "status": row["status"],
        "metadata": metadata if isinstance(metadata, dict) else {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def _dlq_events_for(
    bus: RedisStreamEventBus, task_id: str, limit: int = 50
) -> dict[str, Any]:
    deadletter: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []
    for entry in await _xrevrange_payloads(bus, DEAD_LETTER_STREAM, count=limit):
        payload = entry.get("payload") if isinstance(entry, dict) else None
        if isinstance(payload, dict) and payload.get("task_id") == task_id:
            deadletter.append(entry)
    for entry in await _xrevrange_payloads(bus, TERMINAL_FAILURE_STREAM, count=limit):
        payload = entry.get("payload") if isinstance(entry, dict) else None
        if isinstance(payload, dict) and payload.get("task_id") == task_id:
            terminal.append(entry)
    return {
        "deadletter": deadletter,
        "deadletter_count": len(deadletter),
        "terminal": terminal,
        "terminal_count": len(terminal),
    }


async def _notifications_for(bus: RedisStreamEventBus, task_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for entry in await _xrevrange_payloads(bus, "stream.notifications", count=200):
        payload = entry.get("payload") if isinstance(entry, dict) else None
        if isinstance(payload, dict) and payload.get("task_id") == task_id:
            matches.append(entry)
    return {"count": len(matches), "events": matches[:20]}


@router.get("/workflows/{task_id}")
@_instrument("/operations/workflows/{task_id}", "operations.workflow_view")
async def operations_workflow_view(task_id: str) -> dict:
    warnings: list[str] = []
    try:
        workflow = await WorkflowStore().get_workflow_state(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workflow store unavailable: {exc}") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")

    state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
    execution_result = (
        state.get("execution_result")
        if isinstance(state.get("execution_result"), dict)
        else (
            workflow.get("execution_result")
            if isinstance(workflow.get("execution_result"), dict)
            else {}
        )
    )

    executions: list[dict[str, Any]] = []
    try:
        executions = await AgentExecutionStore().list_executions(task_id=task_id)
    except Exception:
        warnings.append("agent_executions_unavailable")

    audit_events: list[dict[str, Any]] = []
    try:
        audit_events = await AuditStore().get_audit_logs(task_id)
    except Exception:
        warnings.append("audit_logs_unavailable")

    incidents: list[dict[str, Any]] = []
    try:
        incidents = [
            incident.to_dict() for incident in await IncidentStore().list_incidents(task_id=task_id)
        ]
    except Exception:
        warnings.append("incidents_unavailable")

    bus = RedisStreamEventBus()
    try:
        try:
            dlq_events = await _dlq_events_for(bus, task_id)
        except Exception:
            warnings.append("dlq_unavailable")
            dlq_events = {
                "deadletter": [],
                "deadletter_count": 0,
                "terminal": [],
                "terminal_count": 0,
            }
        try:
            notifications = await _notifications_for(bus, task_id)
        except Exception:
            warnings.append("notifications_unavailable")
            notifications = {"count": 0, "events": []}
    finally:
        with contextlib.suppress(Exception):
            await bus.close()

    deployment_record = await _deployment_record_for(task_id)
    progress = build_progress(
        workflow,
        executions,
        retry_timeline=build_retry_timeline(dlq_events.get("deadletter", [])),
    )

    production_executed = bool(execution_result.get("production_executed", False))
    github_section = _build_github_section(
        workflow,
        deployment_record.get("metadata") if isinstance(deployment_record, dict) else {},
    )
    # Stage 23: surface real-test events on the workflow view too. The
    # operator can see whether a controlled-real PR was attempted or
    # blocked without leaving /operations/workflows.
    real_test_rows = [
        row for row in audit_events if row.get("decision_type") in REAL_TEST_DECISION_TYPES
    ]
    real_test_summary = _summarise_real_test_events(real_test_rows)
    github_section = dict(github_section)
    github_section["real_test"] = {
        "found": bool(real_test_rows),
        "production_executed": False,
        "latest_success": real_test_summary.get("latest_success", {}),
        "latest_blocked": real_test_summary.get("latest_blocked", {}),
        "latest_failed": real_test_summary.get("latest_failed", {}),
    }

    # Stage 27 — task_execution section (work item + agent discussions +
    # clarifications). Safe-degrades the same way as the other sections
    # — a missing store just produces an empty section + warning.
    task_execution_section: dict[str, Any] = {
        "found": False,
        "work_item": None,
        "execution_mode": "",
        "status": "",
        "development_required": False,
        "github_required": False,
        "scrum_enabled": False,
        "acceptance_criteria": None,
        "definition_of_done": None,
        "execution_plan": {},
        "assumptions": [],
        "open_questions": [],
        "risks": [],
        "clarification_requests": [],
        "open_clarification_count": 0,
        "agent_discussions": [],
        "ready_for_development": False,
    }
    try:
        te_store = TaskExecutionStore()
        wi = await te_store.get_work_item(task_id)
        if wi is not None:
            discussions = await te_store.list_agent_discussions(task_id)
            clarifications = await te_store.list_clarification_requests(task_id)
            task_execution_section = {
                "found": True,
                "work_item": wi.to_dict(),
                "execution_mode": wi.execution_mode,
                "status": wi.status,
                "development_required": wi.development_required,
                "github_required": wi.github_required,
                "scrum_enabled": wi.scrum_enabled,
                "acceptance_criteria": wi.acceptance_criteria,
                "definition_of_done": wi.definition_of_done,
                "execution_plan": wi.execution_plan,
                "assumptions": wi.assumptions,
                "open_questions": wi.open_questions,
                "risks": wi.risks,
                "clarification_requests": [c.to_dict() for c in clarifications],
                "open_clarification_count": sum(1 for c in clarifications if c.status == "open"),
                "agent_discussions": [d.to_dict() for d in discussions],
                "ready_for_development": wi.status == "ready_for_development",
            }
    except Exception:
        warnings.append("task_execution_unavailable")

    # Stage 28 — code generation section (workspace + artifacts + PR
    # draft). Same safe-degradation rules: a missing store yields an
    # empty section + warning.
    code_generation_section: dict[str, Any] = {
        "found": False,
        "workspace": None,
        "status": "",
        "generator_mode": "",
        "changed_files": [],
        "code_change_artifacts": [],
        "pr_draft": None,
        "validation_result": {},
        "risk_assessment": {},
        "blocked_reason": "",
    }
    try:
        cw_store = CodeWorkspaceStore()
        ws = await cw_store.get_workspace(task_id)
        if ws is not None:
            artifacts = await cw_store.list_code_change_artifacts(task_id)
            pr_draft = await cw_store.get_pr_draft_artifact(task_id)
            code_generation_section = {
                "found": True,
                "workspace": ws.to_dict(),
                "status": ws.status,
                "generator_mode": ws.generator_mode,
                "changed_files": [a.file_path for a in artifacts],
                "code_change_artifacts": [a.to_dict() for a in artifacts],
                "pr_draft": pr_draft.to_dict() if pr_draft is not None else None,
                "validation_result": (pr_draft.test_results if pr_draft else {}),
                "risk_assessment": (pr_draft.risk_assessment if pr_draft else {}),
                "blocked_reason": ws.blocked_reason or "",
            }
    except Exception:
        warnings.append("code_generation_unavailable")

    # Stage 29 — qa_validation section (latest run + findings + auto-fix
    # requests). Safe-degrades the same way as the other sections.
    qa_validation_section: dict[str, Any] = {
        "found": False,
        "latest_run": None,
        "status": "",
        "final_result": "",
        "findings": [],
        "blocking_findings_count": 0,
        "auto_fix_requests": [],
        "auto_fix_attempts": 0,
        "max_auto_fix_attempts": 0,
        "blocked_for_human_review": False,
        "qa_passed": False,
    }
    try:
        qa_store = QAStore()
        latest_run = await qa_store.get_latest_validation_run(task_id)
        if latest_run is not None:
            findings = await qa_store.list_findings(task_id, qa_run_id=latest_run.qa_run_id)
            fix_requests = await qa_store.list_auto_fix_requests(task_id)
            qa_validation_section = {
                "found": True,
                "latest_run": latest_run.to_dict(),
                "status": latest_run.status,
                "final_result": latest_run.final_result,
                "findings": [f.to_dict() for f in findings],
                "blocking_findings_count": latest_run.blocking_findings,
                "auto_fix_requests": [r.to_dict() for r in fix_requests],
                "auto_fix_attempts": latest_run.auto_fix_attempts,
                "max_auto_fix_attempts": latest_run.max_auto_fix_attempts,
                "blocked_for_human_review": (
                    latest_run.status == "blocked_for_human_review"
                    or latest_run.final_result == "blocked"
                ),
                "qa_passed": latest_run.final_result == "pass",
            }
    except Exception:
        warnings.append("qa_validation_unavailable")

    # Stage 22: notification delivery section.
    delivery_rows: list[dict[str, Any]] = []
    try:
        delivery_rows = await NotificationDeliveryStore().list_deliveries(
            task_id=task_id, limit=100
        )
    except Exception:
        warnings.append("notification_deliveries_unavailable")
    latest_delivery = delivery_rows[0] if delivery_rows else None
    notification_deliveries_section = {
        "count": len(delivery_rows),
        "latest_status": (latest_delivery or {}).get("status", ""),
        "external_sent_count": sum(1 for d in delivery_rows if d.get("external_sent")),
        "simulated_count": sum(1 for d in delivery_rows if d.get("status") == "simulated"),
        "failed_count": sum(1 for d in delivery_rows if d.get("status") == "failed"),
        "deliveries": delivery_rows,
    }

    return {
        "task_id": task_id,
        "workflow_id": progress.get("workflow_id", ""),
        "stage": progress.get("current_stage", ""),
        "execution_status": progress.get("execution_status", ""),
        "approval_status": progress.get("approval_status", ""),
        "production_executed": production_executed,
        "workflow": workflow,
        "progress": progress,
        "agents": executions,
        "audit_timeline": build_audit_timeline(audit_events),
        "incidents": incidents,
        "deployment": deployment_record,
        "github": github_section,
        "dlq": dlq_events,
        "notifications": notifications,
        "notification_deliveries": notification_deliveries_section,
        "task_execution": task_execution_section,
        "code_generation": code_generation_section,
        "qa_validation": qa_validation_section,
        "trace": {
            "trace_id": progress.get("traces", {}).get("trace_id", ""),
            "workflow_id": progress.get("workflow_id", ""),
        },
        "safety": {
            "production_executed": production_executed,
            "environment": deployment_record.get("environment") if deployment_record else "",
        },
        "generated_at": _utcnow_iso(),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# /operations/agents and /operations/agents/{agent_name}
# ---------------------------------------------------------------------------


async def _agent_health(host: str, port: str) -> tuple[str, dict[str, Any]]:
    url = f"http://{host}:{port}/health"
    status, body = await _http_get(url, timeout=2.0)
    return ("ok" if status == 200 else "unhealthy"), {"url": url, "status_code": status}


async def _agent_status_body(host: str, port: str) -> tuple[dict[str, Any], dict[str, Any]]:
    url = f"http://{host}:{port}/status"
    status, body = await _http_get(url, timeout=2.0)
    return body if isinstance(body, dict) else {}, {"url": url, "status_code": status}


async def _agent_executions_counts(agent_name: str) -> tuple[int, int]:
    recent = await _scalar(
        "SELECT count(*) FROM agent_executions WHERE agent = $1 "
        "AND created_at >= now() - interval '24 hours'",
        agent_name,
    )
    failures = await _scalar(
        "SELECT count(*) FROM agent_executions WHERE agent = $1 AND status = 'failed' "
        "AND created_at >= now() - interval '24 hours'",
        agent_name,
    )
    return recent, failures


def _shape_agent_overview(
    base: dict[str, str],
    health_state: str,
    health_info: dict[str, Any],
    status_body: dict[str, Any],
    status_info: dict[str, Any],
    recent: int,
    failures: int,
) -> dict[str, Any]:
    return {
        "name": base["name"],
        "health_url": health_info["url"],
        "health_status": health_state,
        "status_url": status_info["url"],
        "processed_count": _safe_int(status_body.get("processed_count")),
        "failed_count": _safe_int(status_body.get("failed_count")),
        "last_task_id": status_body.get("last_task_id"),
        "last_error": status_body.get("last_error"),
        "input_stream": base["input_stream"],
        "output_stream": base["output_stream"],
        "consumer_group": base["consumer_group"],
        "recent_executions_count": recent,
        "recent_failures_count": failures,
    }


@router.get("/agents")
@_instrument("/operations/agents", "operations.agent_view")
async def operations_agents() -> dict:
    rows: list[dict[str, Any]] = []
    for base in PIPELINE_AGENTS:
        health_state, health_info = await _agent_health(base["host"], base["port"])
        status_body, status_info = await _agent_status_body(base["host"], base["port"])
        recent, failures = await _agent_executions_counts(base["name"])
        rows.append(
            _shape_agent_overview(
                base, health_state, health_info, status_body, status_info, recent, failures
            )
        )
    return {"count": len(rows), "agents": rows, "generated_at": _utcnow_iso()}


@router.get("/agents/{agent_name}")
@_instrument("/operations/agents/{agent_name}", "operations.agent_view")
async def operations_agent_detail(agent_name: str) -> dict:
    base = _AGENT_INDEX.get(agent_name)
    if base is None:
        raise HTTPException(status_code=404, detail=f"unknown agent: {agent_name}")
    health_state, health_info = await _agent_health(base["host"], base["port"])
    status_body, status_info = await _agent_status_body(base["host"], base["port"])
    recent, failures = await _agent_executions_counts(agent_name)
    try:
        recent_executions = await AgentExecutionStore().list_executions(agent=agent_name)
    except Exception:
        recent_executions = []
    recent_executions = recent_executions[:20]
    audit_events: list[dict[str, Any]] = []
    try:
        audit_events = await AuditStore().list_audit_logs(agent=agent_name, limit=20)
    except Exception:
        audit_events = []
    bus = RedisStreamEventBus()
    try:
        stream_info = await _xinfo_stream(bus, base["input_stream"])
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
    overview = _shape_agent_overview(
        base, health_state, health_info, status_body, status_info, recent, failures
    )
    return {
        **overview,
        "stream_info": stream_info,
        "recent_executions": recent_executions,
        "recent_audit_events": audit_events,
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/streams
# ---------------------------------------------------------------------------


@router.get("/streams")
@_instrument("/operations/streams", "operations.streams_view")
async def operations_streams() -> dict:
    bus = RedisStreamEventBus()
    streams: list[dict[str, Any]] = []
    try:
        for entry in PLATFORM_STREAMS:
            info = await _xinfo_stream(bus, entry["name"])
            info["primary_group"] = entry["primary_group"]
            # Documented design: stream.notifications has no consumer yet.
            # Mark it informational so a dashboard doesn't flap on a known gap.
            if entry["name"] == "stream.notifications" and info["consumers"] == 0:
                info["status"] = "not_unified_by_design"
            streams.append(info)
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
    return {"count": len(streams), "streams": streams, "generated_at": _utcnow_iso()}


# ---------------------------------------------------------------------------
# /operations/safety
# ---------------------------------------------------------------------------


async def _alertmanager_receivers() -> tuple[list[str], list[str], list[str]]:
    """Return (receivers, external_receivers, warnings)."""
    status, body = await _http_get(f"{ALERTMANAGER_URL}/api/v2/receivers", timeout=3.0)
    if status != 200 or not isinstance(body, list):
        return [], [], ["alertmanager_unavailable"]
    receivers: list[str] = []
    external: list[str] = []
    for entry in body:
        name = (entry.get("name") if isinstance(entry, dict) else "") or ""
        receivers.append(str(name))
        lowered = name.lower()
        if any(k in lowered for k in ("slack", "discord", "telegram", "pagerduty", "webhook")):
            external.append(name)
    return receivers, external, []


def _secret_provider_status() -> dict[str, Any]:
    """Stage 26: snapshot the active SecretProvider posture for /safety.

    Returns boolean/string fields only — never a secret value. The
    provider is constructed lazily so a failing Vault read never breaks
    the safety endpoint.
    """
    chosen = (os.environ.get("SECRET_PROVIDER") or "env").strip().lower()
    info: dict[str, Any] = {
        "secret_provider": chosen,
        "vault_configured": bool(os.environ.get("VAULT_ADDR", "").strip())
        and bool(os.environ.get("VAULT_TOKEN", "").strip()),
        "vault_reachable": False,
        "mock_vault_enabled": chosen == "mock-vault",
        "mock_vault_file_present": False,
        "secret_provider_status": "unknown",
        "missing_required_secrets": [],
    }
    try:
        from shared.sdk.secrets import provider_from_env  # type: ignore

        provider = provider_from_env()
        status = provider.status
        info["secret_provider_status"] = status.get("provider", chosen)
        info["vault_reachable"] = bool(status.get("reachable")) if chosen == "vault" else False
        info["mock_vault_file_present"] = bool(status.get("mock_file_present"))
        # Probe the canonical required secret list (boolean per name).
        required = ("POSTGRES_PASSWORD", "GITHUB_TOKEN", "DISCORD_BOT_TOKEN", "VAULT_TOKEN")
        info["missing_required_secrets"] = [
            name for name in required if not provider.has_secret(name)
        ]
    except Exception:
        info["secret_provider_status"] = "error"
    return info


@router.get("/safety")
@_instrument("/operations/safety", "operations.safety_view")
async def operations_safety() -> dict:
    safety = await _production_safety()
    receivers, external, recv_warnings = await _alertmanager_receivers()
    warnings = list(recv_warnings)
    if external:
        warnings.append(f"external_alert_receivers_present:{','.join(external)}")
    has_token = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    default_dry_run = os.environ.get("GITHUB_DRY_RUN", "true").strip().lower() != "false"
    real_test = os.environ.get("RUN_REAL_GITHUB_TEST", "false").strip().lower() == "true"
    test_repo_configured = bool(os.environ.get("GITHUB_TEST_REPO", "").strip())
    # Stage 23: external write only happens when token + opt-in + sandbox
    # repo are all set. Mirrors the discord_external_send_enabled gate.
    github_external_write_enabled = has_token and real_test and test_repo_configured
    if has_token and not default_dry_run:
        warnings.append("github_token_present_dry_run_false")
    if github_external_write_enabled:
        warnings.append("github_external_write_enabled")
    # Stage 22: surface Discord opt-in pre-conditions as booleans only.
    # The token value never leaves the env var.
    discord_has_token = bool(os.environ.get("DISCORD_BOT_TOKEN", "").strip())
    discord_test_channel_configured = bool(os.environ.get("DISCORD_TEST_CHANNEL_ID", "").strip())
    discord_real_test_enabled = (
        os.environ.get("RUN_REAL_DISCORD_TEST", "false").strip().lower() == "true"
    )
    discord_external_send_enabled = (
        discord_has_token and discord_test_channel_configured and discord_real_test_enabled
    )
    if discord_external_send_enabled:
        warnings.append("discord_external_send_enabled")
    secret_status = _secret_provider_status()
    # The missing-required-secrets list is exposed as a field, NOT
    # appended to `warnings`. Local mode legitimately runs without the
    # opt-in tokens, so a missing list is normal there. The verdict
    # only degrades for genuinely-unsafe postures below.
    if secret_status.get("secret_provider") == "vault" and not secret_status.get("vault_reachable"):
        warnings.append("vault_unreachable")
    if secret_status.get("secret_provider") == "mock-vault":
        warnings.append("mock_vault_provider_in_use")

    result = safety["result"]
    if warnings and result == "safe":
        # Warnings degrade the verdict to "warning" but only an actual
        # production count flips to "unsafe".
        result = "warning"
    return {
        "production_executed_true_count": safety["deployment_records_production_executed_true"],
        "deployment_environment_production_count": safety[
            "deployment_records_environment_production"
        ],
        "workflow_production_executed_true_count": safety[
            "workflow_states_production_executed_true"
        ],
        "github_has_token": has_token,
        "github_default_dry_run": default_dry_run,
        "real_github_test_enabled": real_test,
        "github_test_repo_configured": test_repo_configured,
        "github_external_write_enabled": github_external_write_enabled,
        "discord_has_token": discord_has_token,
        "discord_test_channel_configured": discord_test_channel_configured,
        "discord_real_test_enabled": discord_real_test_enabled,
        "discord_external_send_enabled": discord_external_send_enabled,
        "alertmanager_receivers": receivers,
        "external_alert_receivers_present": bool(external),
        "secret_provider": secret_status["secret_provider"],
        "secret_provider_status": secret_status["secret_provider_status"],
        "vault_configured": secret_status["vault_configured"],
        "vault_reachable": secret_status["vault_reachable"],
        "mock_vault_enabled": secret_status["mock_vault_enabled"],
        "mock_vault_file_present": secret_status["mock_vault_file_present"],
        "missing_required_secrets": secret_status["missing_required_secrets"],
        "vault_mode_note": "vault dev mode is local/test only — never repurpose for production",
        "postgres_auth_note": (
            "postgres trust auth is local/test only — production must use real auth + KMS"
        ),
        "result": result,
        "warnings": warnings,
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/incidents
# ---------------------------------------------------------------------------


@router.get("/incidents")
@_instrument("/operations/incidents", "operations.incidents_view")
async def operations_incidents(
    status: str | None = None,
    severity: str | None = None,
    task_id: str | None = None,
    limit: int = 100,
) -> dict:
    store = IncidentStore()
    try:
        rows = await store.list_incidents(
            status=status,
            severity=severity,
            task_id=task_id,
            limit=max(1, min(int(limit or 100), 500)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    incidents = [incident.to_dict() for incident in rows]
    open_count = sum(1 for r in incidents if r.get("status") == "open")
    ack_count = sum(1 for r in incidents if r.get("status") == "acknowledged")
    resolved_count = sum(1 for r in incidents if r.get("status") == "resolved")
    return {
        "count": len(incidents),
        "incidents": incidents,
        "open_count": open_count,
        "acknowledged_count": ack_count,
        "resolved_count": resolved_count,
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/dlq
# ---------------------------------------------------------------------------


@router.get("/dlq")
@_instrument("/operations/dlq", "operations.dlq_view")
async def operations_dlq(
    task_id: str | None = None,
    stream: str | None = None,
    terminal: bool = False,
    limit: int = 50,
) -> dict:
    bus = RedisStreamEventBus()
    capped_limit = max(1, min(int(limit or 50), 200))
    try:
        deadletter_info = await _xinfo_stream(bus, DEAD_LETTER_STREAM)
        terminal_info = await _xinfo_stream(bus, TERMINAL_FAILURE_STREAM)
        deadletter_events = await _xrevrange_payloads(bus, DEAD_LETTER_STREAM, count=capped_limit)
        terminal_events = await _xrevrange_payloads(
            bus, TERMINAL_FAILURE_STREAM, count=capped_limit
        )
    finally:
        with contextlib.suppress(Exception):
            await bus.close()

    def _filter(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if task_id is None and stream is None:
            return events
        out: list[dict[str, Any]] = []
        for entry in events:
            payload = entry.get("payload") if isinstance(entry, dict) else None
            if not isinstance(payload, dict):
                continue
            if task_id and payload.get("task_id") != task_id:
                continue
            if stream and (
                payload.get("original_stream") != stream and payload.get("source_stream") != stream
            ):
                continue
            out.append(entry)
        return out

    filtered_deadletter = _filter(deadletter_events)
    filtered_terminal = _filter(terminal_events)

    response: dict[str, Any] = {
        "deadletter_length": deadletter_info["length"],
        "deadletter_terminal_length": terminal_info["length"],
        "deadletter_events": filtered_deadletter,
        "terminal_events": filtered_terminal,
        "deadletter_count": len(filtered_deadletter),
        "terminal_count": len(filtered_terminal),
        "generated_at": _utcnow_iso(),
    }
    if terminal:
        # Convenience filter — the caller wants ONLY the terminal stream
        # contents (matches operator UX).
        response["events"] = filtered_terminal
    return response


# ---------------------------------------------------------------------------
# /operations/github/{task_id}
# ---------------------------------------------------------------------------


def _summarise_real_test_events(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Collapse Stage 23 audit events into one view-friendly summary.

    Returns the most-recent success / blocked / failure refs without
    leaking token-shaped fields. Empty dict when no Stage 23 events
    are present.
    """
    success: dict[str, Any] = {}
    blocked: dict[str, Any] = {}
    failed: dict[str, Any] = {}
    for row in events:
        decision = row.get("decision_type") or ""
        refs = row.get("artifact_refs") if isinstance(row.get("artifact_refs"), dict) else {}
        bucket = (
            success
            if decision == "github_real_test"
            else (
                blocked
                if decision == "github_real_test_blocked"
                else failed if decision == "github_real_test_failed" else None
            )
        )
        if bucket is None or bucket:
            # already captured the most-recent (audit query is newest-first)
            continue
        bucket.update(
            {
                "issue_url": refs.get("issue_url", ""),
                "branch": refs.get("branch", ""),
                "pr_url": refs.get("pr_url", ""),
                "checks_status": refs.get("checks_status", ""),
                "repo": refs.get("repo", ""),
                "dry_run": refs.get("dry_run"),
                "real_github_test": refs.get("real_github_test"),
                "production_executed": refs.get("production_executed"),
                "reason": refs.get("reason", ""),
                "error": refs.get("error", ""),
                "details": refs.get("details", {}),
                "summary": row.get("summary", ""),
                "created_at": row.get("created_at"),
            }
        )
    summary: dict[str, Any] = {}
    if success:
        summary["latest_success"] = success
    if blocked:
        summary["latest_blocked"] = blocked
    if failed:
        summary["latest_failed"] = failed
    return summary


@router.get("/github/{task_id}")
@_instrument("/operations/github/{task_id}", "operations.github_view")
async def operations_github(task_id: str) -> dict:
    try:
        workflow = await WorkflowStore().get_workflow_state(task_id)
    except Exception:
        workflow = None
    deployment_record = await _deployment_record_for(task_id)
    audit_events: list[dict[str, Any]] = []
    real_test_events: list[dict[str, Any]] = []
    try:
        rows = await AuditStore().get_audit_logs(task_id)
        for row in rows:
            decision = row.get("decision_type") or ""
            if decision in ("github_pr_integration", "github_automation"):
                audit_events.append(row)
            elif decision in REAL_TEST_DECISION_TYPES:
                real_test_events.append(row)
    except Exception:
        audit_events = []
        real_test_events = []

    github_section = _build_github_section(
        workflow or {},
        deployment_record.get("metadata") if isinstance(deployment_record, dict) else {},
    )
    found = bool(github_section.get("found")) or bool(audit_events) or bool(real_test_events)
    sources: list[str] = []
    if workflow and github_section.get("found"):
        sources.append("workflow_states.execution_result.github")
    if (
        deployment_record
        and isinstance(deployment_record.get("metadata"), dict)
        and isinstance(deployment_record["metadata"].get("github"), dict)
    ):
        sources.append("deployment_records.metadata.github")
    if audit_events:
        sources.append("audit_logs")
    if real_test_events:
        sources.append("audit_logs.real_test")

    real_test_summary = _summarise_real_test_events(real_test_events)
    real_test_section: dict[str, Any] = {
        "found": bool(real_test_events),
        "dry_run": False if real_test_summary.get("latest_success") else None,
        "real_github_test": bool(real_test_summary.get("latest_success")),
        "production_executed": False,
        "issue_url": (real_test_summary.get("latest_success") or {}).get("issue_url", ""),
        "branch": (real_test_summary.get("latest_success") or {}).get("branch", ""),
        "pr_url": (real_test_summary.get("latest_success") or {}).get("pr_url", ""),
        "checks_status": (real_test_summary.get("latest_success") or {}).get("checks_status", ""),
        "safety_guard_result": real_test_summary,
    }

    return {
        "task_id": task_id,
        "found": found,
        "dry_run": github_section.get("dry_run"),
        "status": github_section.get("status", ""),
        "issue_url": github_section.get("issue_url", ""),
        "branch": github_section.get("branch", ""),
        "pr_url": github_section.get("pr_url", ""),
        "pr_number": github_section.get("pr_number"),
        "checks_status": github_section.get("checks_status", ""),
        "event_type": github_section.get("event_type", ""),
        "error": github_section.get("error", ""),
        "related_audit_events": audit_events,
        "real_test": real_test_section,
        "source": sources,
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/tasks/work-items (Stage 27)
# ---------------------------------------------------------------------------


@router.get("/tasks/work-items")
@_instrument("/operations/tasks/work-items", "operations.work_item_list")
async def operations_list_work_items(
    status: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await TaskExecutionStore().list_work_items(
            status=status, execution_mode=execution_mode, limit=capped
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"task execution store unavailable: {exc}"
        ) from exc
    work_items = [r.to_dict() for r in rows]
    return {
        "count": len(work_items),
        "work_items": work_items,
        "filter": {"status": status, "execution_mode": execution_mode, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/tasks/work-items/{task_id}")
@_instrument("/operations/tasks/work-items/{task_id}", "operations.work_item_view")
async def operations_work_item_view(task_id: str) -> dict:
    store = TaskExecutionStore()
    try:
        wi = await store.get_work_item(task_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"task execution store unavailable: {exc}"
        ) from exc
    if wi is None:
        raise HTTPException(status_code=404, detail="work item not found")
    discussions = await store.list_agent_discussions(task_id)
    clarifications = await store.list_clarification_requests(task_id)
    return {
        "work_item": wi.to_dict(),
        "agent_discussions": [d.to_dict() for d in discussions],
        "clarification_requests": [c.to_dict() for c in clarifications],
        "open_clarification_count": sum(1 for c in clarifications if c.status == "open"),
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/code/* (Stage 28 — controlled code generation workspace)
# ---------------------------------------------------------------------------


@router.get("/code/workspaces")
@_instrument("/operations/code/workspaces", "operations.code_workspaces_list")
async def operations_list_code_workspaces(
    status: str | None = None,
    generator_mode: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await CodeWorkspaceStore().list_workspaces(
            status=status, generator_mode=generator_mode, limit=capped
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"code workspace store unavailable: {exc}"
        ) from exc
    return {
        "count": len(rows),
        "workspaces": [r.to_dict() for r in rows],
        "filter": {"status": status, "generator_mode": generator_mode, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/code/workspaces/{task_id}")
@_instrument("/operations/code/workspaces/{task_id}", "operations.code_workspace_view")
async def operations_code_workspace_view(task_id: str) -> dict:
    store = CodeWorkspaceStore()
    try:
        ws = await store.get_workspace(task_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"code workspace store unavailable: {exc}"
        ) from exc
    if ws is None:
        raise HTTPException(status_code=404, detail="code workspace not found")
    artifacts = await store.list_code_change_artifacts(task_id)
    pr_draft = await store.get_pr_draft_artifact(task_id)
    return {
        "workspace": ws.to_dict(),
        "code_change_artifacts": [a.to_dict() for a in artifacts],
        "pr_draft": pr_draft.to_dict() if pr_draft is not None else None,
        "generated_at": _utcnow_iso(),
    }


@router.get("/code/artifacts/{task_id}")
@_instrument("/operations/code/artifacts/{task_id}", "operations.code_artifacts_view")
async def operations_code_artifacts_view(task_id: str) -> dict:
    try:
        rows = await CodeWorkspaceStore().list_code_change_artifacts(task_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"code workspace store unavailable: {exc}"
        ) from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "code_change_artifacts": [r.to_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }


@router.get("/code/pr-drafts/{task_id}")
@_instrument("/operations/code/pr-drafts/{task_id}", "operations.pr_draft_view")
async def operations_pr_draft_view(task_id: str) -> dict:
    try:
        pr_draft = await CodeWorkspaceStore().get_pr_draft_artifact(task_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"code workspace store unavailable: {exc}"
        ) from exc
    if pr_draft is None:
        raise HTTPException(status_code=404, detail="pr draft not found")
    return {
        "pr_draft": pr_draft.to_dict(),
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/qa/* (Stage 29 — QA validation + auto-fix loop)
# ---------------------------------------------------------------------------


@router.get("/qa/runs")
@_instrument("/operations/qa/runs", "operations.qa_runs_list")
async def operations_list_qa_runs(
    task_id: str | None = None,
    status: str | None = None,
    final_result: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await QAStore().list_validation_runs(
            task_id=task_id, status=status, final_result=final_result, limit=capped
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"qa store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "validation_runs": [r.to_dict() for r in rows],
        "filter": {
            "task_id": task_id,
            "status": status,
            "final_result": final_result,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/qa/runs/{task_id}")
@_instrument("/operations/qa/runs/{task_id}", "operations.qa_run_view")
async def operations_qa_runs_for_task(task_id: str) -> dict:
    store = QAStore()
    try:
        rows = await store.list_validation_runs(task_id=task_id, limit=100)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"qa store unavailable: {exc}") from exc
    latest = rows[0] if rows else None
    return {
        "task_id": task_id,
        "latest_run": latest.to_dict() if latest else None,
        "validation_runs": [r.to_dict() for r in rows],
        "count": len(rows),
        "generated_at": _utcnow_iso(),
    }


@router.get("/qa/findings/{task_id}")
@_instrument("/operations/qa/findings/{task_id}", "operations.qa_findings_view")
async def operations_qa_findings_for_task(
    task_id: str,
    severity: str | None = None,
    status: str | None = None,
) -> dict:
    try:
        rows = await QAStore().list_findings(task_id, severity=severity, status=status)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"qa store unavailable: {exc}") from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "findings": [r.to_dict() for r in rows],
        "filter": {"severity": severity, "status": status},
        "generated_at": _utcnow_iso(),
    }


@router.get("/qa/auto-fix/{task_id}")
@_instrument("/operations/qa/auto-fix/{task_id}", "operations.qa_auto_fix_view")
async def operations_qa_auto_fix_for_task(task_id: str) -> dict:
    try:
        rows = await QAStore().list_auto_fix_requests(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"qa store unavailable: {exc}") from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "auto_fix_requests": [r.to_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }
