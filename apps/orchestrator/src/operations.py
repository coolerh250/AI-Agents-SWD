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
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from progress import build_audit_timeline, build_progress, build_retry_timeline
from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.audit.store import AuditStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.incidents import (
    AlertStore,
    IncidentStore,
    LifecycleStore,
    PostmortemStore,
)
from shared.sdk.incidents.audit_events import (
    DECISION_INCIDENT_ACKNOWLEDGED,
    DECISION_INCIDENT_CLOSED,
    DECISION_INCIDENT_POSTMORTEM_CREATED,
    DECISION_INCIDENT_REOPENED,
    DECISION_INCIDENT_RESOLVED,
    EVENT_INCIDENT_ACKNOWLEDGED,
    EVENT_INCIDENT_CLOSED,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    EVENT_INCIDENT_RESOLVED,
    safe_incident_artifact_refs,
)
from shared.sdk.incidents.lifecycle import (
    EVENT_INCIDENT_ACKNOWLEDGED as LC_ACKNOWLEDGED,
    EVENT_INCIDENT_CLOSED as LC_CLOSED,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED as LC_PM_REQUIRED,
    EVENT_INCIDENT_REOPENED as LC_REOPENED,
    EVENT_INCIDENT_RESOLVED as LC_RESOLVED,
)
from shared.sdk.notifications.store import NotificationDeliveryStore
from shared.sdk.observability.metrics import (
    INCIDENT_ACKNOWLEDGED_TOTAL,
    INCIDENT_CLOSED_TOTAL,
    INCIDENT_RESOLVED_TOTAL,
    OPERATIONS_REQUEST_DURATION_SECONDS,
    OPERATIONS_REQUEST_FAILURES_TOTAL,
    OPERATIONS_REQUESTS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.approval_policy import ApprovalPolicyStore
from shared.sdk.audit_integrity import (
    CHAIN_VERSION as AUDIT_CHAIN_VERSION,
    AuditChainVerifier,
    AuditIntegrityStore,
    AuditSigner,
    VERIFICATION_STATUS_ERROR,
    resolve_verify_mode,
)
from shared.sdk.code_workspace import CodeWorkspaceStore
from shared.sdk.llm import LLMInteractionStore
from shared.sdk.llm_budget import (
    BudgetPolicyStore,
    SCOPE_GLOBAL,
)
from shared.sdk.llm_routing import (
    AGENT_DEFAULT_TASK_TYPE,
    ModelRouter,
    ModelRouterStore,
    build_capability_request,
    default_agent_policies,
    default_models,
)
from shared.sdk.backup import (
    BackupStorage,
    encryption_status,
    load_manifest,
    storage_status,
)
from shared.sdk.qa import QAStore
from shared.sdk.real_integration import collect_real_integration_inputs
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


def _incident_receiver_authenticated() -> bool:
    from alert_receiver import receiver_authenticated

    return receiver_authenticated()


async def _count_open_incidents() -> int:
    try:
        return int(
            await _scalar(
                "SELECT count(*) FROM incident_records WHERE status NOT IN ('resolved','closed')"
            )
        )
    except Exception:
        return -1


async def _count_open_incidents_by_sev(normalized_severity: str) -> int:
    try:
        conn = await _connect()
        try:
            val = await conn.fetchval(
                "SELECT count(*) FROM incident_records "
                "WHERE normalized_severity = $1 AND status NOT IN ('resolved','closed')",
                normalized_severity,
            )
        finally:
            await conn.close()
        return int(val or 0)
    except Exception:
        return -1


async def _count_postmortem_required() -> int:
    try:
        return int(await PostmortemStore().count_required())
    except Exception:
        return -1


async def _alert_receiver_last_event_at() -> str | None:
    try:
        return await AlertStore().last_received_at()
    except Exception:
        return None


async def _alert_receiver_rejected_total() -> int:
    try:
        return await AlertStore().count_rejected()
    except Exception:
        return -1


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


async def _approval_policy_summary() -> dict[str, Any]:
    """Stage 31 -- aggregated counters for the approval policy lifecycle."""
    try:
        counts = await ApprovalPolicyStore().counts()
    except Exception:
        counts = {
            "total_policies": 0,
            "active_policies": 0,
            "revoked_policies": 0,
            "delegated_policies": 0,
            "per_feature_policies": 0,
            "per_stage_policies": 0,
            "total_decisions": 0,
            "approved_decisions": 0,
            "rejected_decisions": 0,
            "total_promotions": 0,
            "promoted_count": 0,
            "blocked_by_policy_count": 0,
        }
    return counts


async def _llm_summary() -> dict[str, Any]:
    """Stage 30 — aggregated counters for the LLM proposal lifecycle."""
    try:
        counts = await LLMInteractionStore().counts()
    except Exception:
        counts = {
            "total_interactions": 0,
            "total_proposals": 0,
            "blocked_proposals": 0,
            "policy_passed_proposals": 0,
            "accepted_proposals": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
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


async def _real_integration_summary() -> dict[str, Any]:
    """Stage 32 -- aggregated counters for the real-integration pilot.

    Best-effort: every data source degrades silently so a failing audit
    or notification store cannot break /operations/summary.
    """
    inputs = collect_real_integration_inputs()
    summary: dict[str, Any] = {
        "real_discord_inputs_present": inputs["discord_required_present"],
        "real_discord_guard_active": inputs["discord_ready"],
        "real_github_inputs_present": inputs["github_required_present"],
        "real_github_guard_active": inputs["github_ready"],
        "real_discord_tests_sent": 0,
        "real_discord_tasks_received": 0,
        "real_github_sandbox_prs_created": 0,
        "real_github_sandbox_failures": 0,
        "real_llm_calls": 0,
        "production_deploy_enabled": False,
    }
    try:
        audit_store = AuditStore()
        for decision in ("discord_real_test_sent",):
            rows = await audit_store.list_audit_logs(decision_type=decision, limit=500)
            summary["real_discord_tests_sent"] = len(rows)
        rows = await audit_store.list_audit_logs(
            decision_type="discord_real_task_received", limit=500
        )
        summary["real_discord_tasks_received"] = len(rows)
        rows = await audit_store.list_audit_logs(
            decision_type="github_sandbox_pr_created", limit=500
        )
        summary["real_github_sandbox_prs_created"] = len(rows)
        rows_blocked = await audit_store.list_audit_logs(
            decision_type="github_sandbox_pr_blocked", limit=500
        )
        rows_failed = await audit_store.list_audit_logs(
            decision_type="github_sandbox_guard_failed", limit=500
        )
        summary["real_github_sandbox_failures"] = len(rows_blocked) + len(rows_failed)
    except Exception:
        # Degrade silently -- caller still gets the inputs snapshot.
        pass
    return summary


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
        llm_summary = await _llm_summary()
        approval_policy_summary = await _approval_policy_summary()
        real_integration_summary = await _real_integration_summary()
        audit_integrity_summary = await _audit_integrity_summary()
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
        "llm_summary": llm_summary,
        "approval_policy_summary": approval_policy_summary,
        "real_integration_summary": real_integration_summary,
        "audit_integrity_summary": audit_integrity_summary,
        "backup_summary": _backup_compact_summary(),
        "llm_model_routing_summary": await _llm_routing_compact_summary(),
        "production_safety": safety,
    }


async def _llm_routing_compact_summary() -> dict[str, Any]:
    summary = await _llm_routing_safety_summary()
    return {
        "model_router_enabled": summary["enabled"],
        "registry_active_count": summary["registry_active_count"],
        "policy_active_count": summary["policy_active_count"],
        "agent_direct_model_selection_allowed": False,
        "patch_generation_hard_disabled": True,
        "workspace_write_hard_disabled": True,
    }


def _backup_compact_summary() -> dict[str, Any]:
    """Compact snapshot wired into /operations/summary."""

    latest_manifest = _latest_backup_manifest()
    latest_report = _read_dr_report_latest()
    enc = encryption_status()
    sto = storage_status()
    return {
        "latest_backup_at": latest_manifest.get("created_at") if latest_manifest else None,
        "latest_backup_id": latest_manifest.get("backup_id") if latest_manifest else None,
        "latest_restore_drill_status": (
            latest_report.get("status") if latest_report else "not_run"
        ),
        "rto_seconds": (
            float(latest_report.get("estimated_rto_seconds") or 0.0) if latest_report else None
        ),
        "rpo_seconds": latest_report.get("estimated_rpo_seconds") if latest_report else None,
        "off_host_uploaded": (
            bool(latest_manifest.get("off_host_uploaded")) if latest_manifest else False
        ),
        "encryption_enabled": enc["enabled"],
        "encryption_production_ready": enc["production_ready"],
        "storage_mode": sto["mode"],
        "production_executed": False,
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

    # Stage 30 — llm_assistance section (latest proposal + interactions
    # + usage summary). Safe-degrades to an empty/empty shape when the
    # LLM store is unreachable or no LLM call has been made yet.
    llm_assistance_section: dict[str, Any] = {
        "found": False,
        "enabled": (
            os.environ.get("ENABLE_LLM_ASSISTED_PLANNING", "false").strip().lower() == "true"
        ),
        "provider": (os.environ.get("LLM_PROVIDER", "mock") or "mock").strip().lower(),
        "interactions": [],
        "proposals": [],
        "latest_proposal": None,
        "latest_safety_result": {},
        "requires_human_review": True,
        "blocked": False,
        "usage_summary": {
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "records": 0,
        },
        "policy_violations": [],
        # Stage 38 -- per-task routing decisions (most recent first).
        "routing_decisions": [],
        "selected_model": None,
        "selected_provider": None,
        "model_policy": None,
        "fallback_used": False,
        "routing_blocked": False,
        "routing_reason": None,
        "model_cost_estimate": 0.0,
        "model_requires_human_review": True,
    }
    try:
        llm_store = LLMInteractionStore()
        interactions = await llm_store.list_interactions(task_id=task_id, limit=20)
        proposals = await llm_store.list_proposals(task_id=task_id, limit=20)
        usage = await llm_store.usage_summary(task_id=task_id)
        latest_proposal = proposals[0] if proposals else None
        latest_safety = latest_proposal.safety_result if latest_proposal is not None else {}
        llm_assistance_section.update(
            {
                "found": bool(interactions or proposals),
                "interactions": [i.to_dict() for i in interactions],
                "proposals": [p.to_dict() for p in proposals],
                "latest_proposal": latest_proposal.to_dict() if latest_proposal else None,
                "latest_safety_result": dict(latest_safety),
                "requires_human_review": (
                    bool(latest_proposal.requires_human_review)
                    if latest_proposal is not None
                    else True
                ),
                "blocked": bool(
                    latest_proposal is not None and latest_proposal.status == "blocked"
                ),
                "usage_summary": {
                    "total_tokens": int(usage.get("total_tokens", 0) or 0),
                    "estimated_cost": float(usage.get("estimated_cost", 0.0) or 0.0),
                    "records": int(usage.get("records", 0) or 0),
                },
                "policy_violations": list((latest_safety or {}).get("violations") or []),
            }
        )
    except Exception:
        warnings.append("llm_assistance_unavailable")

    # Stage 38 -- fold routing decisions into llm_assistance so the
    # Discord status + operations workflow view both see them.
    try:
        routing_store = ModelRouterStore()
        routing_rows = await routing_store.list_decisions(task_id=task_id, limit=50)
        if routing_rows:
            latest_routing = routing_rows[0]
            llm_assistance_section["routing_decisions"] = [r.to_safe_dict() for r in routing_rows]
            llm_assistance_section["selected_model"] = latest_routing.selected_model_alias
            llm_assistance_section["selected_provider"] = latest_routing.selected_provider
            llm_assistance_section["model_policy"] = latest_routing.policy_id
            llm_assistance_section["fallback_used"] = bool(latest_routing.fallback_used)
            llm_assistance_section["routing_blocked"] = latest_routing.decision in {
                "blocked",
                "budget_blocked",
                "schema_unsupported",
                "provider_unavailable",
                "policy_not_found",
                "human_approval_required",
                "direct_model_rejected",
            }
            llm_assistance_section["routing_reason"] = latest_routing.reason
            llm_assistance_section["model_cost_estimate"] = float(
                latest_routing.estimated_cost_usd or 0.0
            )
            llm_assistance_section["model_requires_human_review"] = bool(
                latest_routing.requires_human_review
            )
    except Exception:
        warnings.append("llm_routing_unavailable")

    # Stage 31 -- approval policy section (active policies + recent
    # decisions + delegated usage). Safe-degrades to an empty shape when
    # the store is unreachable.
    approval_policy_section: dict[str, Any] = {
        "found": False,
        "active_policies": [],
        "approval_mode": "per_action",
        "decisions": [],
        "delegated_actions_used": 0,
        "delegated_actions_remaining": 0,
        "revoked_policies": [],
        "expired_policies": [],
        "hard_policy_blocks": [],
        "promotions": [],
    }
    try:
        ap_store = ApprovalPolicyStore()
        policies = await ap_store.list_policies(task_id=task_id, limit=100)
        decisions = await ap_store.list_decisions(task_id=task_id, limit=100)
        promotions = await ap_store.list_promotions(task_id=task_id, limit=100)
        active = [p for p in policies if p.status == "active"]
        revoked = [p for p in policies if p.status == "revoked"]
        expired = [p for p in policies if p.status == "expired"]
        hard_blocks = [d for d in decisions if "hard_safety" in str(d.safety_snapshot or "")]
        if active:
            latest = active[0]
            primary_mode = latest.approval_mode
            used = sum(p.actions_used for p in active)
            max_actions = sum((p.max_actions or 0) for p in active)
            remaining = max(0, max_actions - used)
        else:
            primary_mode = "per_action"
            used = 0
            remaining = 0
        approval_policy_section = {
            "found": bool(policies or decisions or promotions),
            "active_policies": [p.to_dict() for p in active],
            "approval_mode": primary_mode,
            "decisions": [d.to_dict() for d in decisions],
            "delegated_actions_used": used,
            "delegated_actions_remaining": remaining,
            "revoked_policies": [p.to_dict() for p in revoked],
            "expired_policies": [p.to_dict() for p in expired],
            "hard_policy_blocks": [d.to_dict() for d in hard_blocks],
            "promotions": [p.to_dict() for p in promotions],
        }
    except Exception:
        warnings.append("approval_policy_unavailable")

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
        "llm_assistance": llm_assistance_section,
        "approval_policy": approval_policy_section,
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

    # Stage 30 — LLM-assisted development guardrails. Booleans + the
    # provider name only — never the API key value.
    llm_provider = (os.environ.get("LLM_PROVIDER", "mock") or "mock").strip().lower()
    llm_real_enabled = os.environ.get("RUN_REAL_LLM_TEST", "false").strip().lower() == "true"
    llm_network_call_enabled = (
        os.environ.get("ENABLE_REAL_LLM_NETWORK_CALL", "false").strip().lower() == "true"
    )
    # External call only happens if RUN_REAL_LLM_TEST=true, network gate
    # is on, and the provider-specific key is present. Stage 30 ships
    # with the network gate OFF.
    has_llm_api_key = (
        bool(os.environ.get("LLM_API_KEY", "").strip())
        or bool(os.environ.get("OPENAI_API_KEY", "").strip())
        or bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    )
    llm_external_call_enabled = llm_real_enabled and llm_network_call_enabled and has_llm_api_key
    if llm_external_call_enabled:
        warnings.append("llm_external_call_enabled")

    # Stage 31 -- approval-policy safety surface. Booleans + counts
    # only; the policy values themselves never leave the API key
    # boundary set by the env reader.
    delegated_active_count = 0
    try:
        ap_store_safety = ApprovalPolicyStore()
        ap_counts = await ap_store_safety.counts()
        delegated_active_count = int(ap_counts.get("delegated_policies", 0) or 0)
    except Exception:
        delegated_active_count = 0
    delegated_agent_enabled = delegated_active_count > 0

    # Stage 32 -- real integration safety surface. Booleans + lengths
    # only, never a token value. The same inputs snapshot is reused by
    # /operations/real-integrations.
    inputs = collect_real_integration_inputs()
    discord_test_guild_configured = bool(os.environ.get("DISCORD_TEST_GUILD_ID", "").strip())
    real_discord_test_channel_configured = bool(
        os.environ.get("DISCORD_TEST_CHANNEL_ID", "").strip()
    )
    real_discord_guard_active = bool(inputs["discord_ready"])
    real_github_guard_active = bool(inputs["github_ready"])
    github_test_repo = (os.environ.get("GITHUB_TEST_REPO", "") or "").strip()

    # Stage 34 -- pull the integrity summary (booleans + counts only).
    audit_integrity = await _audit_integrity_summary()

    # Stage 35 -- LLM cost governance + real-LLM plan-only pilot.
    # Read presence + caps; never reads the API key value.
    llm_budget_summary = await _llm_budget_safety_summary(llm_provider=llm_provider)

    # Stage 36 -- backup / restore / DR drill safety snapshot.
    backup_safety = _backup_safety_summary()

    # Stage 51 -- backup / DR gap closure readiness snapshot.
    backup_dr_safety = _backup_dr_safety_summary()

    # Stage 52 -- Admin Console v1 operator-action safety snapshot.
    operator_action_safety = await _operator_action_safety_summary()

    # Stage 38 -- LLM Model Routing & Agent Model Policy safety snapshot.
    routing_safety = await _llm_routing_safety_summary()

    # Stage 41 -- verification environment hygiene snapshot. Reads the
    # latest regression summary file; booleans + paths only, no secrets.
    verification_summary = _verification_environment_summary()

    # Stage 42 -- audit chain forensics + repair snapshot. Reads the latest
    # forensic/repair report files; booleans + opaque ids only, no secrets.
    forensic_summary = _audit_forensic_summary()

    # Stage 43 -- audit_log restore exception snapshot. Reads the latest
    # restore report file; booleans + opaque ids only, no secrets.
    log_restore_summary = _audit_log_restore_summary()

    # Stage 44 -- audit-touching regression serialization + tamper isolation.
    serialization_summary = _audit_serialization_summary()

    # Stage 45 -- project planner & task graph snapshot.
    project_planning_summary = await _project_planning_safety_summary()

    # Stage 46 -- agent discussion & design review snapshot.
    design_review_summary = await _design_review_safety_summary()

    # Stage 47 -- real repo workspace operator snapshot.
    workspace_operator_summary = await _workspace_operator_safety_summary()

    # Stage 48 -- mini project delivery pilot snapshot.
    mini_delivery_summary = await _mini_delivery_safety_summary()

    # Stage 49 -- delivery package & acceptance gate snapshot.
    delivery_package_summary = await _delivery_package_safety_summary()

    # Stage 53G (Step 51.4) -- read-only Kubernetes/Helm/GitOps runtime baseline.
    runtime_baseline_safety = _runtime_baseline_safety_summary()

    # Stage 54D (Step 52.4) -- read-only identity posture fields.
    identity_posture_safety = _identity_posture_safety_summary()

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
        "llm_provider": llm_provider,
        "llm_real_enabled": llm_real_enabled,
        "llm_external_call_enabled": llm_external_call_enabled,
        "llm_policy_enforced": True,
        "llm_requires_human_review": True,
        # Stage 35 -- LLM cost governance + real-LLM plan-only pilot.
        # Booleans + counts only; no API key, no cost dollars derived
        # from secrets.
        "real_llm_enabled_pilot": llm_external_call_enabled,
        "llm_real_plan_only_enabled": llm_external_call_enabled,
        "llm_patch_generation_enabled": False,
        "llm_workspace_write_enabled": False,
        "llm_cost_governance_enabled": llm_budget_summary["enabled"],
        "llm_budget_policy_active": llm_budget_summary["policy_active"],
        "llm_budget_enforcement_mode": llm_budget_summary["enforcement_mode"],
        "llm_daily_budget_remaining": llm_budget_summary["daily_budget_remaining"],
        "llm_monthly_budget_remaining": llm_budget_summary["monthly_budget_remaining"],
        "llm_budget_exceeded": llm_budget_summary["budget_exceeded"],
        # Stage 38 -- LLM Model Routing & Agent Model Policy.
        # Booleans + counts only; never carries an API key.
        "llm_model_router_enabled": routing_safety["enabled"],
        "agent_direct_model_selection_allowed": False,
        "llm_routing_policy_enforced": True,
        "llm_model_registry_active_count": routing_safety["registry_active_count"],
        "llm_routing_budget_enforced": True,
        "llm_routing_human_review_enforced": True,
        "llm_model_routing_active_policies": routing_safety["policy_active_count"],
        "delegated_agent_enabled": delegated_agent_enabled,
        "active_delegated_policies": delegated_active_count,
        "hard_policy_enforced": True,
        "production_delegation_allowed": False,
        "real_github_delegation_allowed": False,
        "real_discord_inputs_present": bool(inputs["discord_required_present"]),
        "real_discord_test_enabled": discord_real_test_enabled,
        "real_discord_target_channel_configured": real_discord_test_channel_configured,
        "real_discord_test_guild_configured": discord_test_guild_configured,
        "real_discord_guard_active": real_discord_guard_active,
        "real_discord_stream_delivery_default_blocked": True,
        "real_discord_stream_delivery_policy_enforced": True,
        # Stage 34 -- tamper-evident audit chain. Booleans + names only.
        "audit_integrity_enabled": audit_integrity["audit_integrity_enabled"],
        "audit_chain_latest_status": audit_integrity["latest_verification_status"],
        "audit_integrity_degraded": audit_integrity["audit_integrity_degraded"],
        "audit_hmac_enabled": audit_integrity["hmac_enabled"],
        "audit_last_verification_at": audit_integrity["latest_verification_at"],
        "audit_missing_integrity_records": audit_integrity["missing_integrity_records"],
        "audit_tamper_detected": bool(
            audit_integrity.get("latest_verification_status") == "failed"
            and audit_integrity.get("latest_verification_failure_reason")
        ),
        # Stage 39 -- HMAC keyring + direct POST integrity closure.
        # Booleans + counts + opaque key_id only; never carries key bytes.
        "audit_hmac_keyring_configured": audit_integrity["hmac_keyring_configured"],
        "audit_hmac_keyring_valid": audit_integrity["hmac_keyring_valid"],
        "audit_hmac_keyring_mode": audit_integrity["hmac_keyring_mode"],
        "audit_hmac_active_signing_key_id": audit_integrity["active_signing_key_id"],
        "audit_hmac_rotation_supported": True,
        "audit_direct_post_integrity_enabled": audit_integrity["direct_post_integrity_enabled"],
        "audit_direct_post_integrity_gap_closed": (
            audit_integrity["direct_post_integrity_enabled"]
            and audit_integrity["direct_post_missing_integrity_records"] == 0
        ),
        "audit_integrity_concurrency_lock_enabled": audit_integrity[
            "audit_integrity_writer_locking_enabled"
        ],
        "audit_integrity_strict_verify_ready": bool(
            audit_integrity["hmac_keyring_valid"]
            and audit_integrity["hmac_keyring_configured"]
            and audit_integrity["signature_failed_records"] == 0
        ),
        "audit_signature_key_missing_count": audit_integrity["key_missing_records"],
        "real_github_inputs_present": bool(inputs["github_required_present"]),
        "real_github_test_enabled_pilot": real_test,
        "github_test_repo": github_test_repo,
        "github_sandbox_guard_active": real_github_guard_active,
        "real_llm_enabled": llm_external_call_enabled,
        # Stage 36 -- backup / restore / DR safety snapshot. Booleans
        # + opaque key_id only; never carries credentials.
        "backup_encryption_enabled": backup_safety["encryption_enabled"],
        "backup_encryption_production_ready": backup_safety["encryption_production_ready"],
        "backup_off_host_enabled": backup_safety["off_host_enabled"],
        "backup_storage_mode": backup_safety["storage_mode"],
        "latest_restore_drill_status": backup_safety["latest_restore_drill_status"],
        "backup_production_ready": backup_safety["backup_production_ready"],
        "backup_gaps": backup_safety["backup_gaps"],
        "migration_down_scripts_complete": backup_safety["migration_down_scripts_complete"],
        "dr_runbook_present": backup_safety["dr_runbook_present"],
        # Stage 51 -- Backup / DR Gap Closure readiness snapshot. Booleans +
        # opaque key_id / labels only; never carries a raw key or DB password.
        **backup_dr_safety,
        # Stage 40 -- Incident Response & External Alert Receiver safety snapshot.
        "incident_response_enabled": True,
        "external_alert_receiver_enabled": True,
        "external_alert_receiver_authenticated": _incident_receiver_authenticated(),
        "incident_escalation_dry_run": True,
        "real_incident_escalation_enabled": False,
        "incident_auto_remediation_enabled": False,
        "incident_sev1_open_count": await _count_open_incidents_by_sev("SEV1_CRITICAL"),
        "incident_open_count": await _count_open_incidents(),
        "incident_postmortem_required_count": await _count_postmortem_required(),
        "alert_receiver_last_event_at": await _alert_receiver_last_event_at(),
        "alert_receiver_rejected_total": await _alert_receiver_rejected_total(),
        # Stage 41 -- verification environment hygiene.
        # Booleans + paths only; no package names or secret values.
        "verification_environment_ready": verification_summary["verification_environment_ready"],
        "verification_runner_available": verification_summary["verification_runner_available"],
        "latest_full_regression_status": verification_summary["latest_full_regression_status"],
        "latest_full_regression_at": verification_summary["latest_full_regression_at"],
        "latest_full_regression_report_path": verification_summary[
            "latest_full_regression_report_path"
        ],
        "verification_dependency_failures": verification_summary[
            "verification_dependency_failures"
        ],
        "verification_known_gaps": verification_summary["verification_known_gaps"],
        "verification_environment_caveats": verification_summary[
            "verification_environment_caveats"
        ],
        "verification_host_dependency_caveat_closed": verification_summary[
            "verification_host_dependency_caveat_closed"
        ],
        # Stage 42 -- audit chain forensics + controlled repair.
        # Booleans + opaque ids only; never carries payload or key bytes.
        "audit_chain_forensics_available": forensic_summary["audit_chain_forensics_available"],
        "audit_chain_first_failed_sequence": forensic_summary["audit_chain_first_failed_sequence"],
        "audit_chain_failed_verifications_count": audit_integrity["failed_verifications_count"],
        "audit_chain_root_cause_classified": forensic_summary["audit_chain_root_cause_classified"],
        "audit_chain_repair_required": forensic_summary["audit_chain_repair_required"],
        "audit_chain_repair_allowed": forensic_summary["audit_chain_repair_allowed"],
        "audit_chain_repair_last_status": forensic_summary["audit_chain_repair_last_status"],
        # Stage 43 -- controlled audit_log restore exception. The chain is
        # considered restored when either path (integrity repair OR audit_log
        # restore) cleared the mismatch and the verifier passed.
        "audit_log_restore_exception_available": log_restore_summary[
            "audit_log_restore_exception_available"
        ],
        "audit_log_restore_required": log_restore_summary["audit_log_restore_required"],
        "audit_log_restore_allowed": log_restore_summary["audit_log_restore_allowed"],
        "audit_log_restore_last_status": log_restore_summary["audit_log_restore_last_status"],
        "audit_log_restore_last_audit_log_id": log_restore_summary[
            "audit_log_restore_last_audit_log_id"
        ],
        "audit_chain_integrity_restored": bool(
            (
                audit_integrity.get("latest_verification_status") == "passed"
                and not audit_integrity.get("audit_integrity_degraded")
            )
            or forensic_summary["audit_chain_integrity_restored"]
            or log_restore_summary["audit_log_restore_integrity_restored"]
        ),
        # Stage 44 -- audit-touching regression serialization + tamper isolation.
        "audit_touching_regression_serialized": serialization_summary[
            "audit_touching_regression_serialized"
        ],
        "audit_verification_lock_enabled": serialization_summary["audit_verification_lock_enabled"],
        "audit_verification_lock_last_status": serialization_summary[
            "audit_verification_lock_last_status"
        ],
        "audit_tamper_simulation_isolated": serialization_summary[
            "audit_tamper_simulation_isolated"
        ],
        "audit_tamper_residue_detected": serialization_summary["audit_tamper_residue_detected"],
        "audit_tamper_residue_count": serialization_summary["audit_tamper_residue_count"],
        "latest_full_regression_audit_lock_used": serialization_summary[
            "latest_full_regression_audit_lock_used"
        ],
        "latest_full_regression_audit_touching_serialized": serialization_summary[
            "latest_full_regression_audit_touching_serialized"
        ],
        # Stage 45 -- project planner & task graph. Booleans + opaque ids +
        # counts only; planning-only, never carries secrets or chain-of-thought.
        "project_planner_enabled": project_planning_summary["project_planner_enabled"],
        "project_planner_planning_only": project_planning_summary["project_planner_planning_only"],
        "project_task_graph_enabled": project_planning_summary["project_task_graph_enabled"],
        "project_work_item_dispatch_enabled": project_planning_summary[
            "project_work_item_dispatch_enabled"
        ],
        "project_planner_real_llm_enabled": project_planning_summary[
            "project_planner_real_llm_enabled"
        ],
        "project_planner_production_execution_enabled": False,
        "latest_project_planning_status": project_planning_summary[
            "latest_project_planning_status"
        ],
        "latest_project_id": project_planning_summary["latest_project_id"],
        "latest_project_graph_validation_status": project_planning_summary[
            "latest_project_graph_validation_status"
        ],
        "project_delivery_pilot_ready": False,
        # Stage 46 -- agent discussion & design review. Review-only; booleans +
        # opaque ids + status strings only, never secrets or chain-of-thought.
        "design_review_enabled": design_review_summary["design_review_enabled"],
        "design_review_planning_only": design_review_summary["design_review_planning_only"],
        "design_review_real_llm_enabled": design_review_summary["design_review_real_llm_enabled"],
        "design_review_work_item_dispatch_enabled": design_review_summary[
            "design_review_work_item_dispatch_enabled"
        ],
        "agent_discussion_enabled": design_review_summary["agent_discussion_enabled"],
        "agent_discussion_chain_of_thought_persistence_enabled": design_review_summary[
            "agent_discussion_chain_of_thought_persistence_enabled"
        ],
        "latest_design_review_status": design_review_summary["latest_design_review_status"],
        "latest_design_review_decision": design_review_summary["latest_design_review_decision"],
        "latest_design_review_project_id": design_review_summary["latest_design_review_project_id"],
        "latest_design_review_findings_count": design_review_summary[
            "latest_design_review_findings_count"
        ],
        "latest_design_review_blocking_findings_count": design_review_summary[
            "latest_design_review_blocking_findings_count"
        ],
        "latest_project_review_gates_status": design_review_summary[
            "latest_project_review_gates_status"
        ],
        "project_pre_execution_gate_passed": design_review_summary[
            "project_pre_execution_gate_passed"
        ],
        # Stage 47 -- real repo workspace operator. Controlled-only; booleans +
        # opaque ids + status strings only, never secrets or chain-of-thought.
        "workspace_operator_enabled": workspace_operator_summary["workspace_operator_enabled"],
        "workspace_operator_controlled_only": workspace_operator_summary[
            "workspace_operator_controlled_only"
        ],
        "workspace_operator_real_llm_enabled": workspace_operator_summary[
            "workspace_operator_real_llm_enabled"
        ],
        "workspace_operator_github_write_enabled": workspace_operator_summary[
            "workspace_operator_github_write_enabled"
        ],
        "workspace_operator_repo_write_enabled": workspace_operator_summary[
            "workspace_operator_repo_write_enabled"
        ],
        "workspace_operator_deploy_enabled": workspace_operator_summary[
            "workspace_operator_deploy_enabled"
        ],
        "latest_workspace_execution_status": workspace_operator_summary[
            "latest_workspace_execution_status"
        ],
        "latest_workspace_id": workspace_operator_summary["latest_workspace_id"],
        "latest_workspace_tests_status": workspace_operator_summary[
            "latest_workspace_tests_status"
        ],
        "latest_workspace_static_check_status": workspace_operator_summary[
            "latest_workspace_static_check_status"
        ],
        "latest_workspace_generated_files_count": workspace_operator_summary[
            "latest_workspace_generated_files_count"
        ],
        "latest_workspace_safety_status": workspace_operator_summary[
            "latest_workspace_safety_status"
        ],
        "workspace_generation_pilot_ready": workspace_operator_summary[
            "workspace_generation_pilot_ready"
        ],
        # Stage 48 -- mini project delivery pilot. Controlled-only; booleans +
        # opaque ids + status strings only, never secrets or chain-of-thought.
        "mini_delivery_pilot_enabled": mini_delivery_summary["mini_delivery_pilot_enabled"],
        "mini_delivery_pilot_controlled_only": mini_delivery_summary[
            "mini_delivery_pilot_controlled_only"
        ],
        "mini_delivery_real_llm_enabled": mini_delivery_summary["mini_delivery_real_llm_enabled"],
        "mini_delivery_github_write_enabled": mini_delivery_summary[
            "mini_delivery_github_write_enabled"
        ],
        "mini_delivery_pr_creation_enabled": mini_delivery_summary[
            "mini_delivery_pr_creation_enabled"
        ],
        "mini_delivery_deploy_enabled": mini_delivery_summary["mini_delivery_deploy_enabled"],
        "mini_delivery_external_delivery_enabled": mini_delivery_summary[
            "mini_delivery_external_delivery_enabled"
        ],
        "latest_mini_delivery_pilot_status": mini_delivery_summary[
            "latest_mini_delivery_pilot_status"
        ],
        "latest_mini_delivery_pilot_id": mini_delivery_summary["latest_mini_delivery_pilot_id"],
        "latest_mini_delivery_acceptance_total": mini_delivery_summary[
            "latest_mini_delivery_acceptance_total"
        ],
        "latest_mini_delivery_acceptance_satisfied": mini_delivery_summary[
            "latest_mini_delivery_acceptance_satisfied"
        ],
        "latest_mini_delivery_acceptance_failed": mini_delivery_summary[
            "latest_mini_delivery_acceptance_failed"
        ],
        "latest_mini_delivery_acceptance_pending": mini_delivery_summary[
            "latest_mini_delivery_acceptance_pending"
        ],
        "latest_mini_delivery_qa_status": mini_delivery_summary["latest_mini_delivery_qa_status"],
        "latest_mini_delivery_safety_status": mini_delivery_summary[
            "latest_mini_delivery_safety_status"
        ],
        "mini_delivery_pilot_ready_for_delivery_package": mini_delivery_summary[
            "mini_delivery_pilot_ready_for_delivery_package"
        ],
        # Stage 49 -- delivery package & acceptance gate. Controlled-only;
        # booleans + opaque ids + status strings only, never secrets / CoT.
        "delivery_package_enabled": delivery_package_summary["delivery_package_enabled"],
        "delivery_package_controlled_only": delivery_package_summary[
            "delivery_package_controlled_only"
        ],
        "delivery_package_real_llm_enabled": delivery_package_summary[
            "delivery_package_real_llm_enabled"
        ],
        "delivery_package_github_write_enabled": delivery_package_summary[
            "delivery_package_github_write_enabled"
        ],
        "delivery_package_pr_creation_enabled": delivery_package_summary[
            "delivery_package_pr_creation_enabled"
        ],
        "delivery_package_deploy_enabled": delivery_package_summary[
            "delivery_package_deploy_enabled"
        ],
        "delivery_package_external_delivery_enabled": delivery_package_summary[
            "delivery_package_external_delivery_enabled"
        ],
        "delivery_package_auto_accept_enabled": delivery_package_summary[
            "delivery_package_auto_accept_enabled"
        ],
        "delivery_package_operator_actions_enabled": delivery_package_summary[
            "delivery_package_operator_actions_enabled"
        ],
        "latest_delivery_package_status": delivery_package_summary[
            "latest_delivery_package_status"
        ],
        "latest_delivery_package_id": delivery_package_summary["latest_delivery_package_id"],
        "latest_acceptance_gate_status": delivery_package_summary["latest_acceptance_gate_status"],
        "latest_acceptance_gate_decision": delivery_package_summary[
            "latest_acceptance_gate_decision"
        ],
        "latest_acceptance_gate_blocking_findings_count": delivery_package_summary[
            "latest_acceptance_gate_blocking_findings_count"
        ],
        "latest_delivery_readiness_status": delivery_package_summary[
            "latest_delivery_readiness_status"
        ],
        "latest_human_acceptance_status": delivery_package_summary[
            "latest_human_acceptance_status"
        ],
        "latest_delivery_package_sections_ready_count": delivery_package_summary[
            "latest_delivery_package_sections_ready_count"
        ],
        "latest_delivery_package_sections_missing_count": delivery_package_summary[
            "latest_delivery_package_sections_missing_count"
        ],
        "delivery_package_ready_for_admin_console": delivery_package_summary[
            "delivery_package_ready_for_admin_console"
        ],
        # Stage 50 -- Admin Console v0 read-only visibility. The v0 aggregate
        # views/API remain read-only (GET-only, no write API). Stage 52 adds a
        # SEPARATE governed v1 operator-actions surface; its flags come from
        # ``operator_action_safety`` spread below.
        "admin_console_enabled": os.environ.get("ENABLE_ADMIN_CONSOLE", "true").strip().lower()
        != "false",
        "admin_console_read_only": True,
        "admin_console_write_api_enabled": False,
        "admin_console_secret_redaction_enabled": True,
        # Stage 52 -- Admin Console v1 governed operator actions (auth/RBAC/CSRF/
        # policy/confirmation/idempotency/audit). High-risk actions hard-disabled.
        **operator_action_safety,
        # Stage 53G (Step 51.4) -- read-only Kubernetes/Helm/GitOps runtime
        # baseline. Booleans/enums/counts only; no cluster, no deploy, no secret.
        **runtime_baseline_safety,
        # Stage 54D (Step 52.4) -- read-only identity posture. Booleans/enums only;
        # production identity NOT enabled; no IdP, no secret, no raw email/group.
        **identity_posture_safety,
        "production_deploy_enabled": False,
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
# Stage 40 -- Incident Response lifecycle endpoints
# ---------------------------------------------------------------------------


async def _incident_audit_and_notify(
    *,
    incident_id: str,
    severity: str,
    decision_type: str,
    result: str,
    summary: str,
    event_type: str | None = None,
    event_message: str | None = None,
) -> None:
    from shared.sdk.http_clients.audit_http_client import AuditHttpClient
    from shared.sdk.notifications.client import send_notification

    audit = AuditHttpClient()
    with contextlib.suppress(Exception):
        await audit.record_event(
            task_id=incident_id,
            agent="operations",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=safe_incident_artifact_refs(
                incident_id=incident_id,
                severity=severity,
                production_executed=False,
            ),
            workflow_id="",
        )
    if event_type:
        with contextlib.suppress(Exception):
            await send_notification(incident_id, event_type, event_message or summary)


@router.get("/incidents/{incident_id}")
@_instrument("/operations/incidents/{incident_id}", "operations.incident_detail")
async def operations_incident_detail(incident_id: str) -> dict:
    store = IncidentStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return {**incident.to_dict(), "generated_at": _utcnow_iso()}


@router.get("/incidents/{incident_id}/timeline")
@_instrument("/operations/incidents/{incident_id}/timeline", "operations.incident_timeline")
async def operations_incident_timeline(incident_id: str) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    events: list[dict] = []
    with contextlib.suppress(Exception):
        events = await lc_store.list_events(incident_id)
    return {
        "incident_id": incident_id,
        "incident_summary": incident.summary,
        "severity": incident.normalized_severity or incident.severity,
        "status": incident.status,
        "event_count": len(events),
        "events": events,
        "generated_at": _utcnow_iso(),
    }


@router.get("/incidents/{incident_id}/alerts")
@_instrument("/operations/incidents/{incident_id}/alerts", "operations.incident_alerts")
async def operations_incident_alerts(incident_id: str) -> dict:
    store = IncidentStore()
    alert_store = AlertStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    alerts: list[dict] = []
    with contextlib.suppress(Exception):
        alerts = await alert_store.list_alerts_for_incident(incident_id)
    return {
        "incident_id": incident_id,
        "alert_count": len(alerts),
        "alerts": alerts,
        "generated_at": _utcnow_iso(),
    }


@router.post("/incidents/{incident_id}/acknowledge")
@_instrument("/operations/incidents/{incident_id}/acknowledge", "operations.incident_acknowledge")
async def operations_incident_acknowledge(incident_id: str) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    prev_status = incident.status
    try:
        updated = await store.ack_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    severity = updated.normalized_severity or updated.severity
    with contextlib.suppress(Exception):
        await lc_store.record_event(
            incident_id=incident_id,
            event_type=LC_ACKNOWLEDGED,
            previous_status=prev_status,
            new_status="acknowledged",
        )
    INCIDENT_ACKNOWLEDGED_TOTAL.labels(severity=severity).inc()
    await _incident_audit_and_notify(
        incident_id=incident_id,
        severity=severity,
        decision_type=DECISION_INCIDENT_ACKNOWLEDGED,
        result="acknowledged",
        summary=f"Incident {incident_id} acknowledged",
        event_type=EVENT_INCIDENT_ACKNOWLEDGED,
    )
    return {**updated.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/incidents/{incident_id}/resolve")
@_instrument("/operations/incidents/{incident_id}/resolve", "operations.incident_resolve")
async def operations_incident_resolve(incident_id: str) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    prev_status = incident.status
    try:
        updated = await store.resolve_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    severity = updated.normalized_severity or updated.severity
    with contextlib.suppress(Exception):
        await lc_store.record_event(
            incident_id=incident_id,
            event_type=LC_RESOLVED,
            previous_status=prev_status,
            new_status="resolved",
        )
    INCIDENT_RESOLVED_TOTAL.labels(severity=severity).inc()
    await _incident_audit_and_notify(
        incident_id=incident_id,
        severity=severity,
        decision_type=DECISION_INCIDENT_RESOLVED,
        result="resolved",
        summary=f"Incident {incident_id} resolved",
        event_type=EVENT_INCIDENT_RESOLVED,
    )
    return {**updated.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/incidents/{incident_id}/close")
@_instrument("/operations/incidents/{incident_id}/close", "operations.incident_close")
async def operations_incident_close(incident_id: str, payload: dict | None = None) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if incident.status not in ("resolved", "mitigated"):
        reason = str((payload or {}).get("reason", "")).strip()
        if not reason:
            raise HTTPException(
                status_code=409,
                detail="incident must be resolved before closing, or provide an explicit reason",
            )
    prev_status = incident.status
    try:
        updated = await store.close_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    severity = updated.normalized_severity or updated.severity
    with contextlib.suppress(Exception):
        await lc_store.record_event(
            incident_id=incident_id,
            event_type=LC_CLOSED,
            previous_status=prev_status,
            new_status="closed",
            reason=str((payload or {}).get("reason", "")),
        )
    INCIDENT_CLOSED_TOTAL.labels(severity=severity).inc()
    await _incident_audit_and_notify(
        incident_id=incident_id,
        severity=severity,
        decision_type=DECISION_INCIDENT_CLOSED,
        result="closed",
        summary=f"Incident {incident_id} closed",
        event_type=EVENT_INCIDENT_CLOSED,
    )
    return {**updated.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/incidents/{incident_id}/reopen")
@_instrument("/operations/incidents/{incident_id}/reopen", "operations.incident_reopen")
async def operations_incident_reopen(incident_id: str, payload: dict | None = None) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    prev_status = incident.status
    try:
        updated = await store.reopen_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    severity = updated.normalized_severity or updated.severity
    with contextlib.suppress(Exception):
        await lc_store.record_event(
            incident_id=incident_id,
            event_type=LC_REOPENED,
            previous_status=prev_status,
            new_status="open",
            reason=str((payload or {}).get("reason", "")),
        )
    with contextlib.suppress(Exception):
        await _incident_audit_and_notify(
            incident_id=incident_id,
            severity=severity,
            decision_type=DECISION_INCIDENT_REOPENED,
            result="reopened",
            summary=f"Incident {incident_id} reopened",
        )
    return {**updated.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/incidents/{incident_id}/postmortem")
@_instrument("/operations/incidents/{incident_id}/postmortem", "operations.incident_postmortem")
async def operations_incident_postmortem(incident_id: str, payload: dict | None = None) -> dict:
    store = IncidentStore()
    lc_store = LifecycleStore()
    pm_store = PostmortemStore()
    try:
        incident = await store.get_incident(incident_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"incident store unavailable: {exc}") from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    summary_text = str((payload or {}).get("summary", "")).strip() or None
    owner = str((payload or {}).get("owner", "")).strip() or None
    try:
        postmortem = await pm_store.create_postmortem(
            incident_id=incident_id,
            summary=summary_text,
            owner=owner,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"postmortem store unavailable: {exc}") from exc
    severity = incident.normalized_severity or incident.severity
    with contextlib.suppress(Exception):
        await lc_store.record_event(
            incident_id=incident_id,
            event_type=LC_PM_REQUIRED,
            metadata={"postmortem_id": postmortem["postmortem_id"]},
        )
    with contextlib.suppress(Exception):
        await _incident_audit_and_notify(
            incident_id=incident_id,
            severity=severity,
            decision_type=DECISION_INCIDENT_POSTMORTEM_CREATED,
            result="postmortem_draft_created",
            summary=f"Postmortem draft created for incident {incident_id}",
            event_type=EVENT_INCIDENT_POSTMORTEM_REQUIRED,
        )
    return {
        "postmortem": postmortem,
        "incident_id": incident_id,
        "severity": severity,
        "generated_at": _utcnow_iso(),
    }


@router.get("/incidents/postmortems")
@_instrument("/operations/incidents/postmortems", "operations.incident_postmortems_list")
async def operations_postmortems_list(limit: int = 100) -> dict:
    pm_store = PostmortemStore()
    try:
        postmortems = await pm_store.list_postmortems(limit=max(1, min(int(limit or 100), 500)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"postmortem store unavailable: {exc}") from exc
    return {
        "count": len(postmortems),
        "postmortems": postmortems,
        "generated_at": _utcnow_iso(),
    }


@router.get("/incidents/postmortems/{postmortem_id}")
@_instrument(
    "/operations/incidents/postmortems/{postmortem_id}",
    "operations.incident_postmortem_detail",
)
async def operations_postmortem_detail(postmortem_id: str) -> dict:
    pm_store = PostmortemStore()
    try:
        pm = await pm_store.get_postmortem(postmortem_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"postmortem store unavailable: {exc}") from exc
    if pm is None:
        raise HTTPException(status_code=404, detail="postmortem not found")
    return {**pm, "generated_at": _utcnow_iso()}


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


# ---------------------------------------------------------------------------
# /operations/llm/* (Stage 30 -- LLM-assisted development guardrails)
# ---------------------------------------------------------------------------


@router.get("/llm/interactions")
@_instrument("/operations/llm/interactions", "operations.llm_interactions_list")
async def operations_list_llm_interactions(
    task_id: str | None = None,
    interaction_type: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await LLMInteractionStore().list_interactions(
            task_id=task_id, interaction_type=interaction_type, limit=capped
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"llm store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "interactions": [r.to_dict() for r in rows],
        "filter": {
            "task_id": task_id,
            "interaction_type": interaction_type,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/interactions/{task_id}")
@_instrument("/operations/llm/interactions/{task_id}", "operations.llm_interactions_view")
async def operations_llm_interactions_for_task(task_id: str) -> dict:
    try:
        rows = await LLMInteractionStore().list_interactions(task_id=task_id, limit=200)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"llm store unavailable: {exc}") from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "interactions": [r.to_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/proposals/{task_id}")
@_instrument("/operations/llm/proposals/{task_id}", "operations.llm_proposals_view")
async def operations_llm_proposals_for_task(task_id: str) -> dict:
    try:
        rows = await LLMInteractionStore().list_proposals(task_id=task_id, limit=200)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"llm store unavailable: {exc}") from exc
    latest = rows[0] if rows else None
    return {
        "task_id": task_id,
        "count": len(rows),
        "proposals": [r.to_dict() for r in rows],
        "latest_proposal": latest.to_dict() if latest else None,
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/usage")
@_instrument("/operations/llm/usage", "operations.llm_usage_view")
async def operations_llm_usage(
    task_id: str | None = None,
    provider: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = LLMInteractionStore()
    try:
        rows = await store.list_usage(task_id=task_id, provider=provider, limit=capped)
        totals = await store.usage_summary(task_id=task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"llm store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "records": [r.to_dict() for r in rows],
        "summary": totals,
        "filter": {"task_id": task_id, "provider": provider, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# /operations/approval-policies (Stage 31 -- approval policy view)
# ---------------------------------------------------------------------------


@router.get("/approval-policies")
@_instrument("/operations/approval-policies", "operations.approval_policies_list")
async def operations_list_approval_policies(
    task_id: str | None = None,
    workflow_id: str | None = None,
    status: str | None = None,
    approval_mode: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await ApprovalPolicyStore().list_policies(
            task_id=task_id,
            workflow_id=workflow_id,
            status=status,
            approval_mode=approval_mode,
            limit=capped,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    return {
        "count": len(rows),
        "policies": [r.to_dict() for r in rows],
        "filter": {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": status,
            "approval_mode": approval_mode,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/approval-policies/{task_id}")
@_instrument("/operations/approval-policies/{task_id}", "operations.approval_policies_for_task")
async def operations_approval_policies_for_task(task_id: str) -> dict:
    store = ApprovalPolicyStore()
    try:
        rows = await store.list_policies(task_id=task_id, limit=200)
        promotions = await store.list_promotions(task_id=task_id, limit=200)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "policies": [r.to_dict() for r in rows],
        "active_count": sum(1 for r in rows if r.status == "active"),
        "revoked_count": sum(1 for r in rows if r.status == "revoked"),
        "promotions": [p.to_dict() for p in promotions],
        "generated_at": _utcnow_iso(),
    }


@router.get("/approval-decisions/{task_id}")
@_instrument("/operations/approval-decisions/{task_id}", "operations.approval_decisions_for_task")
async def operations_approval_decisions_for_task(task_id: str, limit: int = 200) -> dict:
    capped = max(1, min(int(limit or 200), 500))
    try:
        rows = await ApprovalPolicyStore().list_decisions(task_id=task_id, limit=capped)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "decisions": [r.to_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# Stage 32 -- real integration pilot operations view
# ---------------------------------------------------------------------------


REAL_DISCORD_DECISION_TYPES = (
    "discord_real_test_sent",
    "discord_real_test_blocked",
    "discord_real_task_received",
    "discord_real_task_blocked",
    "discord_real_delivery_blocked",
    "discord_real_delivery_skipped",
)
REAL_GITHUB_DECISION_TYPES = (
    "github_sandbox_pr_created",
    "github_sandbox_pr_blocked",
    "github_sandbox_guard_failed",
    "github_real_test",
    "github_real_test_blocked",
    "github_real_test_failed",
)
REAL_DISCORD_EVENT_TYPES = (
    "discord.real_test_sent",
    "discord.real_task_received",
)
REAL_GITHUB_EVENT_TYPES = (
    "github.sandbox_pr.created",
    "github.sandbox_pr.blocked",
    "github.real_test_pr.created",
)


async def _real_integration_payload() -> dict[str, Any]:
    inputs = collect_real_integration_inputs()
    warnings: list[str] = []

    # Discord counters via audit_logs (best-effort, degrade silently).
    discord_audit = {t: 0 for t in REAL_DISCORD_DECISION_TYPES}
    github_audit = {t: 0 for t in REAL_GITHUB_DECISION_TYPES}
    try:
        audit_store = AuditStore()
        for decision in REAL_DISCORD_DECISION_TYPES:
            rows = await audit_store.list_audit_logs(decision_type=decision, limit=500)
            discord_audit[decision] = len(rows)
        for decision in REAL_GITHUB_DECISION_TYPES:
            rows = await audit_store.list_audit_logs(decision_type=decision, limit=500)
            github_audit[decision] = len(rows)
    except Exception:
        warnings.append("audit_store_unavailable")

    # Notification delivery counters (best-effort).
    notif_counts: dict[str, int] = {}
    try:
        notif_store = NotificationDeliveryStore()
        rows = await notif_store.list_deliveries(limit=500)
        for row in rows:
            ev = (row.get("event_type") or "").strip()
            if ev in REAL_DISCORD_EVENT_TYPES or ev in REAL_GITHUB_EVENT_TYPES:
                notif_counts[ev] = notif_counts.get(ev, 0) + 1
    except Exception:
        warnings.append("notification_store_unavailable")

    # Stage 33 -- notification-worker real-delivery policy snapshot.
    # Best-effort fetch from the worker's /status; if the worker is
    # unreachable we fall back to the env-derived defaults so the API
    # contract is still satisfied (and a warning is surfaced).
    notif_worker_policy: dict[str, Any] = {
        "real_delivery_enabled": False,
        "real_delivery_allowlist": [],
        "real_delivery_denylist": [],
        "real_delivery_allow_marker": True,
        "real_delivery_allowed_count": 0,
        "real_delivery_blocked_count": 0,
        "real_delivery_skipped_count": 0,
        "last_real_delivery_decision": None,
        "last_real_delivery_block_reason": None,
        "stream_delivery_default_blocked": True,
        "stream_delivery_policy_enforced": True,
    }
    nw_status_code, nw_status_body = await _http_get(
        "http://notification-worker:8008/status", timeout=2.0
    )
    if nw_status_code == 200 and isinstance(nw_status_body, dict):
        for key in (
            "real_delivery_enabled",
            "real_delivery_allowlist",
            "real_delivery_denylist",
            "real_delivery_allow_marker",
            "real_delivery_allowed_count",
            "real_delivery_blocked_count",
            "real_delivery_skipped_count",
            "last_real_delivery_decision",
            "last_real_delivery_block_reason",
        ):
            if key in nw_status_body:
                notif_worker_policy[key] = nw_status_body[key]
    else:
        warnings.append("notification_worker_unavailable")

    discord_summary = {
        "inputs_present": inputs["discord_required_present"],
        "opt_in_active": inputs["discord_opt_in_active"],
        "guard_active": inputs["discord_ready"],
        "test_channel_configured": bool(os.environ.get("DISCORD_TEST_CHANNEL_ID", "").strip()),
        "test_guild_configured": bool(os.environ.get("DISCORD_TEST_GUILD_ID", "").strip()),
        "audit_counts": discord_audit,
        "notification_counts": {ev: notif_counts.get(ev, 0) for ev in REAL_DISCORD_EVENT_TYPES},
        "tests_sent_total": discord_audit.get("discord_real_test_sent", 0),
        "tasks_received_total": discord_audit.get("discord_real_task_received", 0),
        "blocks_total": (
            discord_audit.get("discord_real_test_blocked", 0)
            + discord_audit.get("discord_real_task_blocked", 0)
        ),
    }
    github_summary = {
        "inputs_present": inputs["github_required_present"],
        "opt_in_active": inputs["github_opt_in_active"],
        "guard_active": inputs["github_ready"],
        "test_repo": (os.environ.get("GITHUB_TEST_REPO", "") or "").strip(),
        "audit_counts": github_audit,
        "notification_counts": {ev: notif_counts.get(ev, 0) for ev in REAL_GITHUB_EVENT_TYPES},
        "sandbox_prs_created_total": (
            github_audit.get("github_sandbox_pr_created", 0)
            + github_audit.get("github_real_test", 0)
        ),
        "sandbox_failures_total": (
            github_audit.get("github_sandbox_pr_blocked", 0)
            + github_audit.get("github_sandbox_guard_failed", 0)
            + github_audit.get("github_real_test_failed", 0)
        ),
    }
    return {
        "discord": discord_summary,
        "github": github_summary,
        "notification_worker_real_delivery_policy": notif_worker_policy,
        "real_delivery_allowlist": notif_worker_policy["real_delivery_allowlist"],
        "real_delivery_denylist": notif_worker_policy["real_delivery_denylist"],
        "real_delivery_allowed_count": notif_worker_policy["real_delivery_allowed_count"],
        "real_delivery_blocked_count": notif_worker_policy["real_delivery_blocked_count"],
        "last_real_delivery_block_reason": notif_worker_policy["last_real_delivery_block_reason"],
        "real_llm_calls": 0,
        "real_llm_enabled": False,
        "production_deploy_enabled": False,
        "warnings": warnings,
        "inputs_snapshot": {
            "discord": inputs["discord"],
            "github": inputs["github"],
            "no_token_leak": True,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/real-integrations")
@_instrument("/operations/real-integrations", "operations.real_integrations_view")
async def operations_real_integrations() -> dict:
    return await _real_integration_payload()


@router.get("/real-integrations/discord")
@_instrument("/operations/real-integrations/discord", "operations.real_integrations_discord")
async def operations_real_integrations_discord() -> dict:
    payload = await _real_integration_payload()
    return {
        "discord": payload["discord"],
        "real_llm_enabled": payload["real_llm_enabled"],
        "production_deploy_enabled": payload["production_deploy_enabled"],
        "warnings": payload["warnings"],
        "generated_at": payload["generated_at"],
    }


@router.get("/real-integrations/github")
@_instrument("/operations/real-integrations/github", "operations.real_integrations_github")
async def operations_real_integrations_github() -> dict:
    payload = await _real_integration_payload()
    return {
        "github": payload["github"],
        "real_llm_enabled": payload["real_llm_enabled"],
        "production_deploy_enabled": payload["production_deploy_enabled"],
        "warnings": payload["warnings"],
        "generated_at": payload["generated_at"],
    }


# ---------------------------------------------------------------------------
# Stage 34 + Stage 39 -- tamper-evident audit chain operations view.
# Stage 39 -- Audit Integrity Remediation operations view
#   (HMAC keyring + rotation, direct-POST integrity closure,
#    advisory-lock-backed concurrent writer, verification modes).
# ---------------------------------------------------------------------------


async def _audit_integrity_summary() -> dict[str, Any]:
    store = AuditIntegrityStore()
    keyring = store.signer.keyring
    snapshot = keyring.snapshot()
    summary: dict[str, Any] = {
        "chain_version": AUDIT_CHAIN_VERSION,
        "total_audit_logs": 0,
        "total_integrity_records": 0,
        "missing_integrity_records": 0,
        "latest_sequence_number": None,
        "latest_row_hash": None,
        "latest_signing_key_id": store.signer.key_id,
        "hmac_enabled": store.signer.configured,
        "audit_integrity_enabled": True,
        "audit_integrity_degraded": False,
        "latest_verification_status": None,
        "latest_verification_at": None,
        "latest_verification_failure_reason": None,
        "failed_verifications_count": 0,
        # Stage 39 -- keyring + rotation + direct POST closure.
        "hmac_keyring_configured": snapshot.configured,
        "hmac_keyring_mode": snapshot.mode,
        "hmac_keyring_valid": snapshot.valid,
        "active_signing_key_id": snapshot.active_key_id,
        "known_key_ids": list(snapshot.known_key_ids),
        "signed_records": 0,
        "unsigned_records": 0,
        "key_missing_records": 0,
        "signature_failed_records": 0,
        "latest_verification_mode": None,
        "direct_post_integrity_enabled": True,
        "direct_post_missing_integrity_records": 0,
        "audit_integrity_writer_locking_enabled": True,
    }
    try:
        summary["total_audit_logs"] = await store.count_audit_logs()
        summary["total_integrity_records"] = await store.count_integrity_records()
        summary["missing_integrity_records"] = max(
            0,
            summary["total_audit_logs"] - summary["total_integrity_records"],
        )
        # direct_post_missing tracks rows still lacking integrity. It is
        # the same count as missing_integrity_records and is surfaced
        # under both names so an operator can grep either form.
        summary["direct_post_missing_integrity_records"] = summary["missing_integrity_records"]
        latest = await store.get_latest_integrity_record()
        if latest is not None:
            summary["latest_sequence_number"] = latest.sequence_number
            summary["latest_row_hash"] = latest.row_hash
            summary["latest_signing_key_id"] = latest.signing_key_id
        last_run = await store.get_latest_verification_run()
        if last_run is not None:
            summary["latest_verification_status"] = last_run.status
            summary["latest_verification_at"] = (
                last_run.completed_at.isoformat() if last_run.completed_at else None
            )
            summary["latest_verification_failure_reason"] = last_run.failure_reason
            meta = last_run.metadata or {}
            summary["latest_verification_mode"] = meta.get("verification_mode")
            summary["signed_records"] = int(meta.get("signed_records") or 0)
            summary["unsigned_records"] = int(meta.get("unsigned_records") or 0)
            summary["key_missing_records"] = int(meta.get("key_missing_records") or 0)
            summary["signature_failed_records"] = int(meta.get("signature_failed_records") or 0)
        summary["failed_verifications_count"] = await store.count_failed_verifications()
        summary["audit_integrity_degraded"] = bool(
            summary["missing_integrity_records"] > 0
            or summary["latest_verification_status"] in ("failed", "error")
            or not snapshot.valid
        )
    except Exception as exc:
        summary["audit_integrity_enabled"] = False
        summary["audit_integrity_degraded"] = True
        summary["error"] = f"{exc.__class__.__name__}: {exc}"

    # Stage 42 -- merge forensic + repair findings (read-only file reads).
    forensic = _audit_forensic_summary()
    summary["first_failed_sequence"] = forensic["audit_chain_first_failed_sequence"]
    summary["latest_forensic_report_id"] = forensic["latest_forensic_report_id"]
    summary["latest_forensic_root_cause"] = forensic["latest_forensic_root_cause"]
    summary["latest_repair_status"] = forensic["audit_chain_repair_last_status"]
    summary["repair_required"] = forensic["audit_chain_repair_required"]
    summary["repair_allowed"] = forensic["audit_chain_repair_allowed"]
    summary["repair_risk"] = forensic["audit_chain_repair_risk"]

    # Stage 43 -- merge audit_log restore exception findings.
    restore = _audit_log_restore_summary()
    summary["latest_log_restore_status"] = restore["audit_log_restore_last_status"]
    summary["latest_log_restore_id"] = restore["latest_log_restore_id"]
    summary["latest_log_restore_type"] = restore["latest_log_restore_type"]
    summary["audit_log_restore_required"] = restore["audit_log_restore_required"]
    summary["audit_log_restore_allowed"] = restore["audit_log_restore_allowed"]
    summary["audit_log_restore_approved"] = restore["audit_log_restore_approved"]
    summary["audit_log_restore_last_result"] = restore["audit_log_restore_last_result"]
    # The chain is restored when it currently verifies cleanly -- the live
    # verifier status is the source of truth (a later no-op restore/repair
    # report must not flip this back to false). Either remediation path having
    # completed also counts.
    summary["audit_chain_integrity_restored"] = bool(
        (
            summary.get("latest_verification_status") == "passed"
            and not summary.get("audit_integrity_degraded")
        )
        or forensic["audit_chain_integrity_restored"]
        or restore["audit_log_restore_integrity_restored"]
    )
    return summary


@router.get("/audit/integrity")
@_instrument("/operations/audit/integrity", "operations.audit_integrity_view")
async def operations_audit_integrity() -> dict:
    summary = await _audit_integrity_summary()
    return {**summary, "generated_at": _utcnow_iso()}


@router.get("/audit/keyring")
@_instrument("/operations/audit/keyring", "operations.audit_keyring_view")
async def operations_audit_keyring() -> dict:
    """Stage 39 -- read-only view of the HMAC keyring.

    Never returns key bytes. Returns the keyring mode, the active
    key_id, the list of known key_ids, the invalid_reason (when the
    config is malformed), and the per-key metadata rows recorded in
    ``audit_hmac_key_metadata``.
    """
    signer = AuditSigner()
    snapshot = signer.keyring.snapshot()
    store = AuditIntegrityStore(signer=signer)
    metadata: list[dict[str, Any]] = []
    signed_by_key: dict[str, int] = {}
    try:
        # Best-effort: keep the keyring metadata table up to date with
        # what this process sees, so an operator's read of the table
        # matches what the running service thinks.
        await store.upsert_keyring_metadata(snapshot)
        metadata = await store.list_key_metadata()
        signed_by_key = await store.count_signed_records_by_key()
    except Exception as exc:
        return {
            **snapshot.to_safe_dict(),
            "metadata_rows": [],
            "signed_records_by_key_id": {},
            "error": f"{exc.__class__.__name__}: {exc}",
            "generated_at": _utcnow_iso(),
        }
    return {
        **snapshot.to_safe_dict(),
        "metadata_rows": metadata,
        "signed_records_by_key_id": signed_by_key,
        "generated_at": _utcnow_iso(),
    }


class _VerifyChainRequest(BaseModel):
    mode: str | None = Field(default=None)


@router.post("/audit/verify-chain")
@_instrument("/operations/audit/verify-chain", "operations.audit_verify_chain")
async def operations_audit_verify_chain(
    payload: _VerifyChainRequest | None = None,
    mode: str | None = None,
) -> dict:
    """Stage 39 -- run a chain verification.

    Accepts the verification mode either as a JSON body (``{"mode":...}``)
    or as a query parameter (``?mode=strict``). Defaults to permissive
    unless ``AUDIT_VERIFY_SIGNATURE_MODE`` is set.
    """
    requested = (payload.mode if payload else None) or mode
    effective_mode = resolve_verify_mode(requested)
    verifier = AuditChainVerifier(mode=effective_mode)
    store = AuditIntegrityStore()
    with start_span(
        "audit_integrity.verify_chain",
        **{
            "service.name": "orchestrator",
            "agent": "orchestrator",
            "chain_version": str(AUDIT_CHAIN_VERSION),
            "mode": effective_mode,
        },
    ):
        try:
            result = await verifier.verify_chain()
        except Exception as exc:
            return {
                "status": VERIFICATION_STATUS_ERROR,
                "chain_version": AUDIT_CHAIN_VERSION,
                "mode": effective_mode,
                "error": f"{exc.__class__.__name__}: {exc}",
                "generated_at": _utcnow_iso(),
            }
    try:
        await store.record_verification_run(run=verifier.to_run(result))
    except Exception:
        # Recording the run is best-effort -- the verification itself
        # already returned the authoritative result.
        pass
    return {**result.to_dict(), "generated_at": _utcnow_iso()}


@router.get("/audit/verify-chain/latest")
@_instrument("/operations/audit/verify-chain/latest", "operations.audit_verify_chain_latest")
async def operations_audit_verify_chain_latest() -> dict:
    store = AuditIntegrityStore()
    last_run = await store.get_latest_verification_run()
    if last_run is None:
        return {
            "status": "not_run",
            "chain_version": AUDIT_CHAIN_VERSION,
            "generated_at": _utcnow_iso(),
        }
    return {**last_run.to_dict(), "generated_at": _utcnow_iso()}


@router.get("/audit/receipt/{audit_log_id}")
@_instrument("/operations/audit/receipt", "operations.audit_receipt")
async def operations_audit_receipt(audit_log_id: str) -> dict:
    store = AuditIntegrityStore()
    record = await store.get_integrity_record(audit_log_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"no integrity record for audit_log_id={audit_log_id}",
        )
    body = record.to_safe_dict(include_signature_preview=True)
    # Stage 39 -- expose rotation-aware fields on the receipt. The
    # keyring is read once per request; the key value is never surfaced.
    snapshot = store.signer.keyring.snapshot()
    body["signing_key_id"] = record.signing_key_id
    body["signature_status"] = record.signature_status
    body["key_available"] = bool(
        record.signing_key_id and record.signing_key_id in snapshot.known_key_ids
    )
    if record.signature_status == "signed":
        ok, outcome = store.signer.verify_with(
            row_hash=record.row_hash,
            signature=record.hmac_signature,
            signing_key_id=record.signing_key_id,
        )
        body["signature_verification_status"] = (
            "ok" if ok else outcome  # ok / key_missing / signature_failed / no_keyring
        )
    else:
        body["signature_verification_status"] = "n/a"
    body["verification_status"] = "valid_locally"
    body["keyring_mode"] = snapshot.mode
    body["generated_at"] = _utcnow_iso()
    return body


# ---------------------------------------------------------------------------
# Stage 42 -- audit chain forensics + controlled repair (read-only views).
# These endpoints NEVER run a forensic scan or a repair; they read the
# latest redacted report files written by the offline scripts.
# ---------------------------------------------------------------------------


@router.get("/audit/forensics/latest")
@_instrument("/operations/audit/forensics/latest", "operations.audit_forensics_latest")
async def operations_audit_forensics_latest() -> dict:
    report = _read_json_file(_AUDIT_FORENSIC_LATEST)
    if report is None:
        return {"status": "unknown", "available": False, "generated_at": _utcnow_iso()}
    return {**report, "available": True, "generated_at": _utcnow_iso()}


@router.get("/audit/forensics/reports")
@_instrument("/operations/audit/forensics/reports", "operations.audit_forensics_reports")
async def operations_audit_forensics_reports(limit: int = 25) -> dict:
    return {
        "reports": _list_audit_forensic_reports(limit=limit),
        "generated_at": _utcnow_iso(),
    }


@router.get("/audit/repair/latest")
@_instrument("/operations/audit/repair/latest", "operations.audit_repair_latest")
async def operations_audit_repair_latest() -> dict:
    report = _read_json_file(_AUDIT_REPAIR_LATEST)
    if report is None:
        return {"status": "unknown", "available": False, "generated_at": _utcnow_iso()}
    return {**report, "available": True, "generated_at": _utcnow_iso()}


@router.get("/audit/repair/reports")
@_instrument("/operations/audit/repair/reports", "operations.audit_repair_reports")
async def operations_audit_repair_reports(limit: int = 25) -> dict:
    return {
        "reports": _list_audit_repair_reports(limit=limit),
        "generated_at": _utcnow_iso(),
    }


@router.get("/audit/log-restore/latest")
@_instrument("/operations/audit/log-restore/latest", "operations.audit_log_restore_latest")
async def operations_audit_log_restore_latest() -> dict:
    report = _read_json_file(_AUDIT_LOG_RESTORE_LATEST)
    if report is None:
        return {"status": "unknown", "available": False, "generated_at": _utcnow_iso()}
    return {**report, "available": True, "generated_at": _utcnow_iso()}


@router.get("/audit/log-restore/reports")
@_instrument("/operations/audit/log-restore/reports", "operations.audit_log_restore_reports")
async def operations_audit_log_restore_reports(limit: int = 25) -> dict:
    return {
        "reports": _list_audit_log_restore_reports(limit=limit),
        "generated_at": _utcnow_iso(),
    }


@router.get("/audit/tamper-residue")
@_instrument("/operations/audit/tamper-residue", "operations.audit_tamper_residue")
async def operations_audit_tamper_residue() -> dict:
    report = _read_json_file(_AUDIT_TAMPER_RESIDUE_LATEST)
    if report is None:
        return {"status": "unknown", "available": False, "generated_at": _utcnow_iso()}
    # Expose count + safe identifiers only (the detector already redacts).
    return {
        "available": True,
        "residue_count": report.get("residue_count"),
        "residues": report.get("residues", []),
        "created_at": report.get("created_at"),
        "generated_at": _utcnow_iso(),
    }


@router.get("/audit/verification-lock/latest")
@_instrument("/operations/audit/verification-lock/latest", "operations.audit_verification_lock")
async def operations_audit_verification_lock_latest() -> dict:
    report = _read_json_file(_AUDIT_VERIFICATION_LOCK_LATEST)
    if report is None:
        return {"status": "unknown", "available": False, "generated_at": _utcnow_iso()}
    return {**report, "available": True, "generated_at": _utcnow_iso()}


# ---------------------------------------------------------------------------
# Stage 35 -- LLM cost governance + real-LLM plan-only pilot operations view.
# ---------------------------------------------------------------------------


async def _llm_budget_safety_summary(*, llm_provider: str) -> dict[str, Any]:
    """Return a small budget snapshot for /operations/safety.

    Booleans + counts only; never reads an API key value. The
    function is safe to call even when the budget tables are
    unreachable (returns ``enabled=False`` + ``policy_active=False``).
    """
    summary: dict[str, Any] = {
        "enabled": True,
        "policy_active": False,
        "enforcement_mode": None,
        "daily_budget_remaining": None,
        "monthly_budget_remaining": None,
        "budget_exceeded": False,
        "policy_id": None,
        "policy_name": None,
        "max_cost_per_task_usd": None,
        "max_tokens_per_task": None,
    }
    store = BudgetPolicyStore()
    try:
        policy = await store.get_active_policy(provider=llm_provider)
        if policy is not None:
            summary.update(
                policy_active=True,
                policy_id=policy.policy_id,
                policy_name=policy.policy_name,
                enforcement_mode=policy.enforcement_mode,
                max_cost_per_task_usd=policy.max_cost_per_task_usd,
                max_tokens_per_task=policy.max_tokens_per_task,
            )
            if policy.max_cost_per_day_usd:
                daily = await store.get_daily_usage_usd(provider=policy.provider)
                summary["daily_budget_remaining"] = max(
                    0.0, float(policy.max_cost_per_day_usd) - daily
                )
            if policy.max_cost_per_month_usd:
                monthly = await store.get_monthly_usage_usd(provider=policy.provider)
                summary["monthly_budget_remaining"] = max(
                    0.0, float(policy.max_cost_per_month_usd) - monthly
                )
            from shared.sdk.llm_budget import DECISION_BLOCKED, EVENT_TYPE_BUDGET_EXCEEDED

            blocked = await store.list_events(
                provider=policy.provider,
                event_type=EVENT_TYPE_BUDGET_EXCEEDED,
                decision=DECISION_BLOCKED,
                limit=1,
            )
            summary["budget_exceeded"] = bool(blocked)
    except Exception:
        summary["enabled"] = False
    return summary


async def _llm_budget_payload(*, provider: str | None = None) -> dict[str, Any]:
    store = BudgetPolicyStore()
    policies_active: list[dict[str, Any]] = []
    summary_block: dict[str, Any] = {}
    warnings: list[str] = []
    try:
        if provider:
            policy = await store.get_active_policy(provider=provider)
            policies_active = [policy.to_safe_dict()] if policy else []
        else:
            rows = await store.list_policies(status="active", limit=50)
            policies_active = [p.to_safe_dict() for p in rows]
        summary_block = await store.get_usage_summary(provider=provider)
    except Exception as exc:
        warnings.append(f"budget_store_unavailable:{exc.__class__.__name__}")
    return {
        "provider_filter": provider,
        "active_policies": policies_active,
        "usage_summary": summary_block,
        "warnings": warnings,
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/budget")
@_instrument("/operations/llm/budget", "operations.llm_budget_view")
async def operations_llm_budget(provider: str | None = None) -> dict:
    return await _llm_budget_payload(provider=provider)


@router.get("/llm/budget/policies")
@_instrument("/operations/llm/budget/policies", "operations.llm_budget_policies")
async def operations_llm_budget_policies(
    provider: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = BudgetPolicyStore()
    try:
        rows = await store.list_policies(provider=provider, status=status, limit=capped)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"budget store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "policies": [r.to_safe_dict() for r in rows],
        "filter": {"provider": provider, "status": status, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/budget/usage")
@_instrument("/operations/llm/budget/usage", "operations.llm_budget_usage")
async def operations_llm_budget_usage(
    provider: str | None = None,
    task_id: str | None = None,
) -> dict:
    store = BudgetPolicyStore()
    out: dict[str, Any] = {
        "provider": provider,
        "task_id": task_id,
        "generated_at": _utcnow_iso(),
    }
    try:
        out["summary"] = await store.get_usage_summary(provider=provider)
        if task_id:
            out["task_usage"] = await store.get_task_usage(task_id=task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"budget store unavailable: {exc}") from exc
    return out


@router.get("/llm/budget/events")
@_instrument("/operations/llm/budget/events", "operations.llm_budget_events")
async def operations_llm_budget_events(
    provider: str | None = None,
    task_id: str | None = None,
    event_type: str | None = None,
    decision: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = BudgetPolicyStore()
    try:
        rows = await store.list_events(
            task_id=task_id,
            provider=provider,
            event_type=event_type,
            decision=decision,
            limit=capped,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"budget store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "events": [r.to_safe_dict() for r in rows],
        "filter": {
            "provider": provider,
            "task_id": task_id,
            "event_type": event_type,
            "decision": decision,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


class _BudgetPolicyIn(BaseModel):
    policy_name: str
    provider: str = "mock"
    scope_type: str = SCOPE_GLOBAL
    scope_id: str | None = None
    model_name: str | None = None
    max_tokens_per_task: int | None = None
    max_cost_per_task_usd: float | None = None
    max_cost_per_day_usd: float | None = None
    max_cost_per_month_usd: float | None = None
    enforcement_mode: str = "block"
    status: str = "active"
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/llm/budget/policies")
@_instrument("/operations/llm/budget/policies", "operations.llm_budget_policy_create")
async def operations_llm_budget_policy_create(payload: _BudgetPolicyIn) -> dict:
    store = BudgetPolicyStore()
    try:
        policy = await store.create_policy(
            policy_name=payload.policy_name,
            provider=payload.provider,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            model_name=payload.model_name,
            max_tokens_per_task=payload.max_tokens_per_task,
            max_cost_per_task_usd=payload.max_cost_per_task_usd,
            max_cost_per_day_usd=payload.max_cost_per_day_usd,
            max_cost_per_month_usd=payload.max_cost_per_month_usd,
            enforcement_mode=payload.enforcement_mode,
            status=payload.status,
            created_by=payload.created_by,
            metadata=payload.metadata or {},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {**policy.to_safe_dict(), "generated_at": _utcnow_iso()}


@router.get("/llm/plan-only/{task_id}")
@_instrument("/operations/llm/plan-only/{task_id}", "operations.llm_plan_only_view")
async def operations_llm_plan_only_for_task(task_id: str) -> dict:
    """Return a Stage-35-specific summary for a task's real-LLM plan-only run.

    Joins llm_interactions (interaction_type=development_plan) +
    llm_proposal_artifacts + llm_usage_records + llm_budget_events.
    The endpoint never returns prompts / responses verbatim -- it
    reuses the existing redacted previews from the underlying stores.
    """
    interactions_store = LLMInteractionStore()
    budget_store = BudgetPolicyStore()
    try:
        interactions = await interactions_store.list_interactions(
            task_id=task_id, interaction_type="development_plan", limit=20
        )
        proposals = await interactions_store.list_proposals(task_id=task_id, limit=20)
        usage = await interactions_store.list_usage(task_id=task_id, limit=20)
        budget_events = await budget_store.list_events(task_id=task_id, limit=50)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"llm store unavailable: {exc}") from exc

    plan_only_proposals = [
        p.to_dict()
        for p in proposals
        if p.proposal_type in ("development_plan_only", "development_plan")
    ]
    real_llm_used = any((i.provider or "").startswith("external_") for i in interactions)
    return {
        "task_id": task_id,
        "real_llm_used": real_llm_used,
        "plan_only": True,
        "interactions": [i.to_dict() for i in interactions],
        "plan_only_proposals": plan_only_proposals,
        "usage_records": [u.to_dict() for u in usage],
        "budget_events": [e.to_safe_dict() for e in budget_events],
        "requires_human_review": True,
        "production_executed": False,
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# Stage 36 -- backup / restore / DR drill operations view.
# Read-only. Never returns an encryption key value, a storage
# credential value, or a database password. Manifest files + DR
# reports are returned verbatim because they are designed to be
# safe to share (the on-disk format strips secrets at write time).
# ---------------------------------------------------------------------------


_BACKUP_DR_REPORTS_DIR = os.environ.get("DR_REPORTS_DIR", "source/dr-reports")
_BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
_DR_RUNBOOK_PATHS = (
    "docs/operations/backup-restore-dr.md",
    "docs/operations/restore-drill-runbook.md",
    "docs/operations/backup-schedule.md",
)


def _backup_safety_summary() -> dict[str, Any]:
    """Booleans-only snapshot wired into /operations/safety."""

    enc = encryption_status()
    sto = storage_status()
    latest_report = _read_dr_report_latest()
    runbook_present = all(os.path.isfile(p) for p in _DR_RUNBOOK_PATHS)
    migration_gaps = _migration_down_inventory()["gaps"]
    gaps: list[str] = []
    if not enc["enabled"]:
        gaps.append("encryption_no_key")
    elif not enc["production_ready"]:
        gaps.append("encryption_test_only")
    if sto["mode"] != "s3-compatible-placeholder" or not sto.get("production_ready"):
        gaps.append("off_host_not_production")
    if latest_report is None:
        gaps.append("no_dr_report")
    elif latest_report.get("status") != "passed":
        gaps.append(f"dr_report_{latest_report.get('status', 'unknown')}")
    if migration_gaps > 0:
        gaps.append("migration_down_gaps")
    if not runbook_present:
        gaps.append("dr_runbook_missing")
    return {
        "encryption_enabled": enc["enabled"],
        "encryption_production_ready": enc["production_ready"],
        "off_host_enabled": sto["mode"] != "disabled" and sto.get("credential_complete", False),
        "storage_mode": sto["mode"],
        "latest_restore_drill_status": (
            latest_report.get("status") if latest_report else "not_run"
        ),
        "backup_production_ready": not gaps,
        "backup_gaps": gaps,
        "migration_down_scripts_complete": migration_gaps == 0,
        "dr_runbook_present": runbook_present,
    }


_BACKUP_DR_READINESS_SNAPSHOT = Path("source/dr-reports/backup_dr_readiness_latest.json")
_BACKUP_DR_ORIGINAL_GAPS = (
    "encryption_no_key",
    "storage_not_off_host",
    "schedule_dry_run_only",
    "migration_down_gaps",
)


def _backup_dr_readiness_snapshot() -> dict[str, Any] | None:
    """Read the Stage 51 readiness snapshot written by the gap-closure run."""
    if not _BACKUP_DR_READINESS_SNAPSHOT.is_file():
        return None
    try:
        with open(_BACKUP_DR_READINESS_SNAPSHOT, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _runtime_baseline_safety_summary() -> dict[str, Any]:
    """Step 51.4 -- read-only Kubernetes/Helm/GitOps runtime baseline safety
    fields. File-based (reads the committed runtime-baseline-summary.yaml copied
    into the image); never connects to a cluster, runs a verifier, or carries a
    secret. Absent summary -> safe `unknown` posture, never a fake PASS.
    """
    from shared.sdk.runtime_baseline import (
        load_runtime_baseline_summary,
        runtime_baseline_safety_fields,
    )

    summary = load_runtime_baseline_summary(
        Path("infra/kubernetes/runtime-baseline-summary.yaml")
    )
    return runtime_baseline_safety_fields(summary)


def _identity_posture_safety_summary() -> dict[str, Any]:
    """Step 52.4 -- read-only identity posture safety fields. File-based (reads
    the committed identity-posture-summary.yaml copied into the image); never
    connects to an IdP, fetches discovery/JWKS, reads a secret, or enables
    production auth. Absent summary -> safe `unknown` posture, never a fake PASS.
    """
    from shared.sdk.identity_posture import (
        identity_posture_safety_fields,
        load_identity_posture_summary,
    )

    summary = load_identity_posture_summary(Path("infra/identity/identity-posture-summary.yaml"))
    return identity_posture_safety_fields(summary)


def _backup_dr_safety_summary() -> dict[str, Any]:
    """Stage 51 -- booleans-only backup / DR readiness snapshot for
    /operations/safety. File-based (no DB dependency) so the safety endpoint
    always responds. Defaults reflect "gaps still open" until a gap-closure run
    writes the readiness snapshot. Never carries a raw key / secret / password.
    """
    enabled = str(os.environ.get("ENABLE_BACKUP_DR", "true")).strip().lower() != "false"
    snap = _backup_dr_readiness_snapshot()
    if snap is None:
        return {
            "backup_dr_enabled": enabled,
            "backup_encryption_configured": False,
            "backup_encryption_key_source": "disabled",
            "backup_encryption_raw_key_persisted": False,
            "backup_latest_encrypted": False,
            "backup_offhost_target_configured": False,
            "backup_offhost_readback_verified": False,
            "backup_restore_drill_status": "not_run",
            "backup_restore_drill_rto_seconds": None,
            "backup_schedule_defined": False,
            "backup_schedule_dry_run_validated": False,
            "backup_production_schedule_enabled": False,
            "backup_retention_policy_configured": False,
            "backup_retention_delete_enabled": False,
            "migration_rollback_catalog_complete": False,
            "migration_rollback_unknown_count": 0,
            "backup_readiness_status": "passed_with_gaps",
            "backup_readiness_gaps": list(_BACKUP_DR_ORIGINAL_GAPS),
            "backup_readiness_limitations": [],
            "backup_real_cloud_write_enabled": False,
            "backup_real_cloud_write_performed": False,
            "backup_production_backup_performed": False,
            "backup_production_restore_performed": False,
        }

    report = snap.get("report") if isinstance(snap.get("report"), dict) else {}
    enc = report.get("encryption", {}) if isinstance(report, dict) else {}
    bk = report.get("backup", {}) if isinstance(report, dict) else {}
    off = report.get("offhost", {}) if isinstance(report, dict) else {}
    rd = report.get("restore_drill", {}) if isinstance(report, dict) else {}
    sch = report.get("schedule", {}) if isinstance(report, dict) else {}
    ret = report.get("retention", {}) if isinstance(report, dict) else {}
    mig = report.get("migration_rollback_catalog", {}) if isinstance(report, dict) else {}
    return {
        "backup_dr_enabled": enabled,
        "backup_encryption_configured": enc.get("status") == "configured",
        "backup_encryption_key_source": enc.get("key_source", "disabled"),
        "backup_encryption_raw_key_persisted": False,
        "backup_latest_encrypted": bool(bk.get("encrypted")),
        "backup_offhost_target_configured": off.get("status") in ("verified", "copied"),
        "backup_offhost_readback_verified": bool(off.get("readback_verified")),
        "backup_restore_drill_status": rd.get("status", "not_run"),
        "backup_restore_drill_rto_seconds": rd.get("rto_seconds"),
        "backup_schedule_defined": bool(sch.get("schedule_type")),
        "backup_schedule_dry_run_validated": bool(sch.get("dry_run_validated")),
        "backup_production_schedule_enabled": bool(sch.get("production_schedule_enabled")),
        "backup_retention_policy_configured": bool(ret.get("policy_key")),
        "backup_retention_delete_enabled": bool(ret.get("delete_enabled")),
        "migration_rollback_catalog_complete": bool(mig.get("complete")),
        "migration_rollback_unknown_count": int(mig.get("unknown", 0)),
        "backup_readiness_status": snap.get("status", "passed_with_gaps"),
        "backup_readiness_gaps": list(snap.get("remaining_gaps", [])),
        "backup_readiness_limitations": list(snap.get("limitations", [])),
        "backup_real_cloud_write_enabled": bool(off.get("real_cloud_write_enabled")),
        "backup_real_cloud_write_performed": bool(off.get("real_cloud_write_performed")),
        "backup_production_backup_performed": False,
        "backup_production_restore_performed": bool(rd.get("production_restore_performed")),
    }


async def _operator_action_safety_summary() -> dict[str, Any]:
    """Stage 52 -- Admin Console v1 operator-action safety snapshot.

    Booleans-only (no raw token / secret). High-risk capabilities are hard
    false. Latest action / rerun status is read from the store (resilient).
    """
    from shared.sdk.operator_actions.safety import operator_action_safety_flags

    flags = operator_action_safety_flags()
    summary: dict[str, Any] = dict(flags)
    summary["latest_operator_action_status"] = None
    summary["latest_operator_action_type"] = None
    summary["latest_operator_identity"] = None
    summary["latest_verification_rerun_status"] = None
    summary["operator_action_policy_block_count"] = 0
    try:
        from shared.sdk.operator_actions import OperatorActionStore

        store = OperatorActionStore()
        actions = await store.list_actions(limit=50)
        if actions:
            summary["latest_operator_action_status"] = actions[0].get("status")
            summary["latest_operator_action_type"] = actions[0].get("action_type")
            summary["latest_operator_identity"] = actions[0].get("identity_key")
            summary["operator_action_policy_block_count"] = sum(
                1 for a in actions if a.get("status") == "policy_blocked"
            )
        reruns = await store.list_reruns(limit=1)
        if reruns:
            summary["latest_verification_rerun_status"] = reruns[0].get("status")
    except Exception:
        pass
    return summary


def _read_dr_report_latest() -> dict[str, Any] | None:
    """Return ``source/dr-reports/dr_report_latest.json`` or None."""

    latest = os.path.join(_BACKUP_DR_REPORTS_DIR, "dr_report_latest.json")
    if not os.path.isfile(latest):
        return None
    try:
        with open(latest, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


_REGRESSION_SUMMARY_PATH = Path("source/regression-reports/regression_latest_summary.json")


def _verification_environment_summary() -> dict[str, Any]:
    """Stage 41: read latest regression summary for /operations/safety."""

    runner_available = Path("scripts/run_full_regression.sh").is_file()
    if not _REGRESSION_SUMMARY_PATH.is_file():
        return {
            "verification_environment_ready": False,
            "verification_runner_available": runner_available,
            "latest_full_regression_status": "unknown",
            "latest_full_regression_at": None,
            "latest_full_regression_report_path": None,
            "verification_dependency_failures": [],
            "verification_known_gaps": [],
            "verification_environment_caveats": [],
            "verification_host_dependency_caveat_closed": False,
        }
    try:
        with open(_REGRESSION_SUMMARY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result_class = data.get("result_class", "unknown")
        env_ready = bool(data.get("environment_ready", False))
        caveat_closed = bool(data.get("host_dependency_caveat_closed", False))
        return {
            "verification_environment_ready": env_ready,
            "verification_runner_available": runner_available,
            "latest_full_regression_status": result_class,
            "latest_full_regression_at": data.get("completed_at"),
            "latest_full_regression_report_path": data.get("report_path"),
            "verification_dependency_failures": data.get("dependency_failures", []),
            "verification_known_gaps": data.get("known_gaps", []),
            "verification_environment_caveats": data.get("caveats", []),
            "verification_host_dependency_caveat_closed": caveat_closed,
        }
    except (OSError, ValueError, KeyError):
        return {
            "verification_environment_ready": False,
            "verification_runner_available": runner_available,
            "latest_full_regression_status": "error_reading_report",
            "latest_full_regression_at": None,
            "latest_full_regression_report_path": None,
            "verification_dependency_failures": [],
            "verification_known_gaps": [],
            "verification_environment_caveats": [],
            "verification_host_dependency_caveat_closed": False,
        }


_AUDIT_FORENSICS_DIR = os.environ.get("AUDIT_FORENSICS_DIR", "source/audit-forensics")
_AUDIT_FORENSIC_LATEST = Path(_AUDIT_FORENSICS_DIR) / "audit_forensic_latest.json"
_AUDIT_REPAIR_LATEST = Path(_AUDIT_FORENSICS_DIR) / "audit_repair_latest.json"


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _audit_forensic_summary() -> dict[str, Any]:
    """Stage 42: read latest forensic + repair reports (read-only).

    Returns booleans + opaque ids only. When no report exists the fields
    report ``unknown`` / ``None`` rather than pretending the chain is safe.
    """
    forensic = _read_json_file(_AUDIT_FORENSIC_LATEST)
    repair = _read_json_file(_AUDIT_REPAIR_LATEST)

    summary: dict[str, Any] = {
        "audit_chain_forensics_available": forensic is not None,
        "audit_chain_first_failed_sequence": None,
        "audit_chain_failed_records_count": None,
        "latest_forensic_report_id": None,
        "latest_forensic_root_cause": None,
        "audit_chain_root_cause_classified": False,
        "audit_chain_repair_required": None,
        "audit_chain_repair_allowed": None,
        "audit_chain_repair_risk": None,
        "audit_chain_repair_last_status": None,
        "latest_repair_report_id": None,
        "audit_chain_integrity_restored": False,
    }

    if forensic is not None:
        first_failed = forensic.get("first_failed_sequence")
        root_cause = forensic.get("root_cause_classification")
        summary.update(
            audit_chain_first_failed_sequence=first_failed,
            audit_chain_failed_records_count=forensic.get("failed_records_count"),
            latest_forensic_report_id=forensic.get("report_id"),
            latest_forensic_root_cause=root_cause,
            # "classified" means a forensic verdict exists -- including the
            # explicit "unknown" verdict (which forces repair_allowed=false).
            audit_chain_root_cause_classified=bool(
                forensic.get("root_cause_classification") is not None
                or forensic.get("failed_records_count") == 0
            ),
            audit_chain_repair_required=bool(forensic.get("failed_records_count")),
            audit_chain_repair_allowed=bool(forensic.get("repair_allowed")),
            audit_chain_repair_risk=forensic.get("repair_risk"),
        )

    if repair is not None:
        status = repair.get("status")
        verification = repair.get("verification_after_repair") or {}
        summary.update(
            audit_chain_repair_last_status=status,
            latest_repair_report_id=repair.get("repair_id"),
            audit_chain_integrity_restored=bool(
                status == "completed" and verification.get("passed") is True
            ),
        )
    return summary


def _list_audit_forensic_reports(limit: int = 25) -> list[dict[str, Any]]:
    base = Path(_AUDIT_FORENSICS_DIR)
    if not base.is_dir():
        return []
    out: list[tuple[float, dict[str, Any]]] = []
    for p in base.glob("audit_forensic_*.json"):
        if p.name == "audit_forensic_latest.json":
            continue
        data = _read_json_file(p)
        if data is None:
            continue
        out.append(
            (
                p.stat().st_mtime,
                {
                    "report_id": data.get("report_id"),
                    "created_at": data.get("created_at"),
                    "root_cause_classification": data.get("root_cause_classification"),
                    "first_failed_sequence": data.get("first_failed_sequence"),
                    "failed_records_count": data.get("failed_records_count"),
                    "repair_allowed": data.get("repair_allowed"),
                },
            )
        )
    out.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in out[: max(1, min(int(limit or 25), 200))]]


def _list_audit_repair_reports(limit: int = 25) -> list[dict[str, Any]]:
    base = Path(_AUDIT_FORENSICS_DIR)
    if not base.is_dir():
        return []
    out: list[tuple[float, dict[str, Any]]] = []
    for p in base.glob("audit_repair_*.json"):
        if p.name == "audit_repair_latest.json":
            continue
        data = _read_json_file(p)
        if data is None:
            continue
        out.append(
            (
                p.stat().st_mtime,
                {
                    "repair_id": data.get("repair_id"),
                    "started_at": data.get("started_at"),
                    "status": data.get("status"),
                    "root_cause": data.get("root_cause"),
                    "dry_run": data.get("dry_run"),
                    "approved": data.get("approved"),
                    "audit_logs_modified": data.get("audit_logs_modified"),
                    "changed_records_count": data.get("changed_records_count"),
                },
            )
        )
    out.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in out[: max(1, min(int(limit or 25), 200))]]


# Stage 43 -- controlled audit_log restore exception (test-tamper residue).
_AUDIT_LOG_RESTORE_LATEST = Path(_AUDIT_FORENSICS_DIR) / "audit_log_restore_latest.json"


def _audit_log_restore_summary() -> dict[str, Any]:
    """Stage 43: read latest audit_log restore report (read-only).

    Booleans + opaque ids only. Absent report -> unknown / None (never
    pretends the chain is restored).
    """
    restore = _read_json_file(_AUDIT_LOG_RESTORE_LATEST)
    summary: dict[str, Any] = {
        "audit_log_restore_exception_available": restore is not None,
        "audit_log_restore_required": None,
        "audit_log_restore_allowed": None,
        "audit_log_restore_approved": None,
        "audit_log_restore_last_status": None,
        "audit_log_restore_last_result": None,
        "audit_log_restore_last_audit_log_id": None,
        "latest_log_restore_id": None,
        "latest_log_restore_type": None,
        "audit_log_restore_integrity_restored": False,
    }
    if restore is not None:
        status = restore.get("status")
        precheck = restore.get("precheck") or {}
        verifier = restore.get("verifier_after_restore") or {}
        restored = bool(status == "completed" and verifier.get("status") in ("passed", "partial"))
        summary.update(
            audit_log_restore_required=bool(precheck.get("before_contains_tamper_marker")),
            audit_log_restore_allowed=bool(precheck.get("ok")),
            audit_log_restore_approved=bool(restore.get("approved")),
            audit_log_restore_last_status=status,
            audit_log_restore_last_result=status,
            audit_log_restore_last_audit_log_id=restore.get("affected_audit_log_id"),
            latest_log_restore_id=restore.get("restore_id"),
            latest_log_restore_type=restore.get("restore_type"),
            audit_log_restore_integrity_restored=restored,
        )
    return summary


def _list_audit_log_restore_reports(limit: int = 25) -> list[dict[str, Any]]:
    base = Path(_AUDIT_FORENSICS_DIR)
    if not base.is_dir():
        return []
    out: list[tuple[float, dict[str, Any]]] = []
    for p in base.glob("audit_log_restore_*.json"):
        if p.name == "audit_log_restore_latest.json":
            continue
        data = _read_json_file(p)
        if data is None:
            continue
        out.append(
            (
                p.stat().st_mtime,
                {
                    "restore_id": data.get("restore_id"),
                    "created_at": data.get("created_at"),
                    "status": data.get("status"),
                    "restore_type": data.get("restore_type"),
                    "affected_audit_log_id": data.get("affected_audit_log_id"),
                    "affected_sequence_number": data.get("affected_sequence_number"),
                    "dry_run": data.get("dry_run"),
                    "approved": data.get("approved"),
                    "audit_logs_modified_count": data.get("audit_logs_modified_count"),
                    "audit_integrity_records_modified_count": data.get(
                        "audit_integrity_records_modified_count"
                    ),
                },
            )
        )
    out.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in out[: max(1, min(int(limit or 25), 200))]]


# Stage 44 -- audit-touching regression serialization + tamper sim isolation.
_AUDIT_VERIFICATION_LOCK_LATEST = Path(_AUDIT_FORENSICS_DIR) / "audit_verification_lock_latest.json"
_AUDIT_TAMPER_RESIDUE_LATEST = Path(_AUDIT_FORENSICS_DIR) / "audit_tamper_residue_latest.json"


def _audit_serialization_summary() -> dict[str, Any]:
    """Stage 44: read lock + residue + regression reports (read-only).

    Booleans + counts only. Absent reports -> unknown / None, never a false
    "safe". The residue count is authoritative for tamper isolation health.
    """
    lock = _read_json_file(_AUDIT_VERIFICATION_LOCK_LATEST)
    residue = _read_json_file(_AUDIT_TAMPER_RESIDUE_LATEST)
    regression = _read_json_file(_REGRESSION_SUMMARY_PATH)

    summary: dict[str, Any] = {
        "audit_verification_lock_enabled": lock is not None,
        "audit_verification_lock_last_status": None,
        "audit_tamper_residue_detected": None,
        "audit_tamper_residue_count": None,
        "audit_tamper_simulation_isolated": None,
        "audit_touching_regression_serialized": None,
        "latest_full_regression_audit_lock_used": None,
        "latest_full_regression_audit_touching_serialized": None,
    }
    if lock is not None:
        summary["audit_verification_lock_last_status"] = lock.get("status")
        summary["audit_verification_lock_enabled"] = bool(lock.get("enabled", True))
    if residue is not None:
        count = residue.get("residue_count")
        summary["audit_tamper_residue_count"] = count
        summary["audit_tamper_residue_detected"] = bool(count) if count is not None else None
        # Isolation holds when the lock is enabled and no residue remains.
        if count is not None:
            summary["audit_tamper_simulation_isolated"] = (
                count == 0 and summary["audit_verification_lock_enabled"]
            )
    if regression is not None:
        summary["latest_full_regression_audit_lock_used"] = regression.get("audit_lock_used")
        summary["latest_full_regression_audit_touching_serialized"] = regression.get(
            "audit_touching_scripts_serialized"
        )
        summary["audit_touching_regression_serialized"] = bool(
            regression.get("audit_touching_scripts_serialized")
        )
    return summary


# Stage 45 -- project planner & task graph safety snapshot.
def _project_planning_flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


async def _project_planning_safety_summary() -> dict[str, Any]:
    """Stage 45: project planner posture (flags + latest project snapshot).

    Booleans + opaque ids + status strings only. A failing store NEVER fails
    the safety view -- the latest-project fields degrade to None.
    """
    summary: dict[str, Any] = {
        "project_planner_enabled": _project_planning_flag("ENABLE_PROJECT_PLANNER", True),
        "project_planner_planning_only": _project_planning_flag(
            "PROJECT_PLANNER_PLANNING_ONLY", True
        ),
        "project_task_graph_enabled": True,
        "project_work_item_dispatch_enabled": _project_planning_flag(
            "ENABLE_PROJECT_WORK_ITEM_DISPATCH", False
        ),
        "project_planner_real_llm_enabled": _project_planning_flag(
            "ENABLE_PROJECT_PLANNER_REAL_LLM", False
        ),
        "latest_project_planning_status": None,
        "latest_project_id": None,
        "latest_project_graph_validation_status": None,
    }
    try:
        from shared.sdk.project_planning import ProjectPlanningStore

        store = ProjectPlanningStore()
        projects = await store.list_projects(limit=1)
        if projects:
            latest = projects[0]
            summary["latest_project_id"] = latest["id"]
            summary["latest_project_planning_status"] = latest["status"]
            snapshot = await store.get_latest_graph_snapshot(latest["id"])
            if snapshot is not None:
                summary["latest_project_graph_validation_status"] = snapshot["validation_status"]
    except Exception:
        pass
    return summary


# Stage 46 -- agent discussion & design review safety snapshot.
async def _design_review_safety_summary() -> dict[str, Any]:
    """Stage 46: design-review posture (flags + latest review snapshot).

    Booleans + opaque ids + status strings only. A failing store NEVER fails
    the safety view -- the latest-review fields degrade to None.
    """
    summary: dict[str, Any] = {
        "design_review_enabled": _project_planning_flag("ENABLE_DESIGN_REVIEW", True),
        "design_review_planning_only": _project_planning_flag("DESIGN_REVIEW_PLANNING_ONLY", True),
        "design_review_real_llm_enabled": _project_planning_flag(
            "ENABLE_DESIGN_REVIEW_REAL_LLM", False
        ),
        "design_review_work_item_dispatch_enabled": _project_planning_flag(
            "ENABLE_DESIGN_REVIEW_WORK_ITEM_DISPATCH", False
        ),
        "agent_discussion_enabled": _project_planning_flag("ENABLE_DESIGN_REVIEW", True),
        "agent_discussion_chain_of_thought_persistence_enabled": False,
        "latest_design_review_status": None,
        "latest_design_review_decision": None,
        "latest_design_review_project_id": None,
        "latest_design_review_findings_count": None,
        "latest_design_review_blocking_findings_count": None,
        "latest_project_review_gates_status": None,
        "project_pre_execution_gate_passed": None,
    }
    try:
        from shared.sdk.design_review import DesignReviewStore
        from shared.sdk.project_planning import ProjectPlanningStore

        projects = await ProjectPlanningStore().list_projects(limit=1)
        if projects:
            project_id = projects[0]["id"]
            review_store = DesignReviewStore()
            review = await review_store.get_latest_review(project_id)
            gates = await review_store.list_gates(project_id)
            if review is not None:
                summary["latest_design_review_project_id"] = project_id
                summary["latest_design_review_status"] = review["status"]
                summary["latest_design_review_decision"] = review["decision"]
                findings = await review_store.list_findings(review["id"])
                summary["latest_design_review_findings_count"] = len(findings)
                summary["latest_design_review_blocking_findings_count"] = len(
                    [
                        f
                        for f in findings
                        if f["severity"] in ("high", "critical") and f["status"] == "open"
                    ]
                )
            if gates:
                statuses = {g["status"] for g in gates}
                if "blocked" in statuses or "failed" in statuses:
                    summary["latest_project_review_gates_status"] = "blocked"
                elif "passed_with_findings" in statuses:
                    summary["latest_project_review_gates_status"] = "passed_with_findings"
                else:
                    summary["latest_project_review_gates_status"] = "passed"
                pre = next((g for g in gates if g["gate_type"] == "pre_execution_gate"), None)
                if pre is not None:
                    summary["project_pre_execution_gate_passed"] = pre["status"] in (
                        "passed",
                        "passed_with_findings",
                    )
    except Exception:
        pass
    return summary


# Stage 47 -- real repo workspace operator safety snapshot.
async def _workspace_operator_safety_summary() -> dict[str, Any]:
    """Stage 47: workspace operator posture (flags + latest workspace snapshot).

    Booleans + opaque ids + status strings only. A failing store NEVER fails
    the safety view -- the latest-workspace fields degrade to None.
    """
    from shared.sdk.workspace_operator.safety import workspace_safety_flags

    flags = workspace_safety_flags()
    summary: dict[str, Any] = {
        "workspace_operator_enabled": flags["workspace_operator_enabled"],
        "workspace_operator_controlled_only": flags["workspace_operator_controlled_only"],
        "workspace_operator_real_llm_enabled": flags["workspace_operator_real_llm_enabled"],
        "workspace_operator_github_write_enabled": flags["workspace_operator_github_write_enabled"],
        "workspace_operator_repo_write_enabled": flags["workspace_operator_repo_write_enabled"],
        "workspace_operator_deploy_enabled": flags["workspace_operator_deploy_enabled"],
        "latest_workspace_execution_status": None,
        "latest_workspace_id": None,
        "latest_workspace_tests_status": None,
        "latest_workspace_static_check_status": None,
        "latest_workspace_generated_files_count": None,
        "latest_workspace_safety_status": "safe",
        "workspace_generation_pilot_ready": False,
    }
    try:
        from shared.sdk.workspace_operator import WorkspaceOperatorStore

        store = WorkspaceOperatorStore()
        ws = await store.get_latest_workspace()
        if ws is not None:
            summary["latest_workspace_id"] = ws["workspace_id"]
            summary["latest_workspace_execution_status"] = ws["status"]
            ws_summary = (
                await store.compute_workspace_summary(ws["project_id"])
                if ws.get("project_id")
                else {}
            )
            summary["latest_workspace_tests_status"] = ws_summary.get(
                "latest_workspace_tests_status"
            )
            summary["latest_workspace_static_check_status"] = ws_summary.get(
                "latest_workspace_static_check_status"
            )
            summary["latest_workspace_generated_files_count"] = ws_summary.get(
                "latest_workspace_generated_files_count"
            )
            # controlled-only is "safe" unless any real-write flag flipped true.
            if (
                ws.get("repo_write_enabled")
                or ws.get("github_write_enabled")
                or ws.get("deployment_enabled")
                or ws.get("real_llm_enabled")
                or ws.get("production_executed")
            ):
                summary["latest_workspace_safety_status"] = "unsafe"
            summary["workspace_generation_pilot_ready"] = ws["status"] == "tests_passed"
    except Exception:
        pass
    return summary


# Stage 48 -- mini project delivery pilot safety snapshot.
async def _mini_delivery_safety_summary() -> dict[str, Any]:
    """Stage 48: mini delivery pilot posture (flags + latest pilot snapshot).

    Booleans + opaque ids + status strings only. A failing store NEVER fails
    the safety view -- the latest-pilot fields degrade to None.
    """
    from shared.sdk.mini_delivery_pilot.safety import mini_delivery_safety_flags

    flags = mini_delivery_safety_flags()
    summary: dict[str, Any] = {
        **flags,
        "latest_mini_delivery_pilot_status": None,
        "latest_mini_delivery_pilot_id": None,
        "latest_mini_delivery_acceptance_total": None,
        "latest_mini_delivery_acceptance_satisfied": None,
        "latest_mini_delivery_acceptance_failed": None,
        "latest_mini_delivery_acceptance_pending": None,
        "latest_mini_delivery_qa_status": None,
        "latest_mini_delivery_safety_status": None,
        "mini_delivery_pilot_ready_for_delivery_package": False,
    }
    try:
        from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotStore

        store = MiniDeliveryPilotStore()
        pilot = await store.get_latest_pilot()
        if pilot is not None:
            pid = pilot["id"]
            summary["latest_mini_delivery_pilot_id"] = pid
            summary["latest_mini_delivery_pilot_status"] = pilot["status"]
            acc = await store.get_acceptance_summary(pid)
            summary["latest_mini_delivery_acceptance_total"] = acc["total"]
            summary["latest_mini_delivery_acceptance_satisfied"] = acc["satisfied"]
            summary["latest_mini_delivery_acceptance_failed"] = acc["failed"]
            summary["latest_mini_delivery_acceptance_pending"] = acc["pending"]
            qa = await store.get_qa_report(pid)
            if qa is not None:
                summary["latest_mini_delivery_qa_status"] = qa["status"]
            safety = await store.get_safety_report(pid)
            if safety is not None:
                summary["latest_mini_delivery_safety_status"] = safety["status"]
            summary["mini_delivery_pilot_ready_for_delivery_package"] = bool(
                pilot["status"] in ("completed", "report_ready")
                and acc["failed"] == 0
                and (qa or {}).get("status") in ("passed", "passed_with_findings")
                and (safety or {}).get("status") in ("safe", "safe_with_findings")
            )
    except Exception:
        pass
    return summary


# Stage 49 -- delivery package & acceptance gate safety snapshot.
async def _delivery_package_safety_summary() -> dict[str, Any]:
    """Stage 49: delivery package posture (flags + latest package snapshot).

    Booleans + opaque ids + status strings only. A failing store NEVER fails
    the safety view -- the latest-package fields degrade to None.
    """
    from shared.sdk.delivery_package.safety import delivery_package_safety_flags

    flags = delivery_package_safety_flags()
    summary: dict[str, Any] = {
        **flags,
        "latest_delivery_package_status": None,
        "latest_delivery_package_id": None,
        "latest_acceptance_gate_status": None,
        "latest_acceptance_gate_decision": None,
        "latest_acceptance_gate_blocking_findings_count": None,
        "latest_delivery_readiness_status": None,
        "latest_human_acceptance_status": None,
        "latest_delivery_package_sections_ready_count": None,
        "latest_delivery_package_sections_missing_count": None,
        "delivery_package_ready_for_admin_console": False,
    }
    try:
        from shared.sdk.delivery_package import DeliveryPackageStore

        store = DeliveryPackageStore()
        package = await store.get_latest_package()
        if package is not None:
            pkg_id = package["id"]
            summary["latest_delivery_package_id"] = pkg_id
            summary["latest_delivery_package_status"] = package["status"]
            summary["latest_human_acceptance_status"] = package["human_acceptance_status"]
            gate = await store.get_acceptance_gate(pkg_id)
            if gate is not None:
                summary["latest_acceptance_gate_status"] = gate["status"]
                summary["latest_acceptance_gate_decision"] = gate["decision"]
                summary["latest_acceptance_gate_blocking_findings_count"] = gate[
                    "blocking_findings_count"
                ]
            readiness = await store.get_readiness_snapshot(pkg_id)
            if readiness is not None:
                summary["latest_delivery_readiness_status"] = readiness["readiness_status"]
            sections = await store.get_package_sections(pkg_id)
            ready = sum(1 for s in sections if s["status"] == "ready")
            missing = sum(1 for s in sections if s["status"] == "missing")
            summary["latest_delivery_package_sections_ready_count"] = ready
            summary["latest_delivery_package_sections_missing_count"] = missing
            summary["delivery_package_ready_for_admin_console"] = bool(
                package["status"] == "ready_for_review"
                and (gate or {}).get("status") in ("passed", "passed_with_findings")
                and (gate or {}).get("decision")
                in ("ready_for_operator_review", "controlled_only_complete")
                and package["human_acceptance_status"] == "pending"
                and (readiness or {}).get("readiness_status") == "ready_for_operator_review"
            )
    except Exception:
        pass
    return summary


def _list_dr_reports(limit: int = 25) -> list[dict[str, Any]]:
    if not os.path.isdir(_BACKUP_DR_REPORTS_DIR):
        return []
    paths: list[tuple[float, str]] = []
    for name in os.listdir(_BACKUP_DR_REPORTS_DIR):
        if not name.startswith("dr_report_"):
            continue
        if name == "dr_report_latest.json":
            continue
        full = os.path.join(_BACKUP_DR_REPORTS_DIR, name)
        try:
            paths.append((os.path.getmtime(full), full))
        except OSError:
            continue
    paths.sort(reverse=True)
    out: list[dict[str, Any]] = []
    for _, p in paths[:limit]:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            out.append(payload)
        except (OSError, ValueError):
            continue
    return out


def _latest_backup_manifest() -> dict[str, Any] | None:
    if not os.path.isdir(_BACKUP_DIR):
        return None
    candidates: list[tuple[float, str]] = []
    for name in os.listdir(_BACKUP_DIR):
        if not name.startswith("backup_manifest_") or not name.endswith(".json"):
            continue
        full = os.path.join(_BACKUP_DIR, name)
        try:
            candidates.append((os.path.getmtime(full), full))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    try:
        manifest = load_manifest(candidates[0][1])
    except Exception:
        return None
    payload = json.loads(manifest.to_canonical_json())
    payload["manifest_path"] = candidates[0][1]
    return payload


def _migration_down_inventory() -> dict[str, Any]:
    migrations_dir = os.environ.get("MIGRATIONS_DIR", "migrations")
    if not os.path.isdir(migrations_dir):
        return {"total": 0, "with_down": 0, "gaps": 0, "missing": []}
    total = 0
    with_down = 0
    missing: list[str] = []
    for name in sorted(os.listdir(migrations_dir)):
        if not name.endswith(".sql") or name.endswith("_down.sql"):
            continue
        total += 1
        stem = name[: -len(".sql")]
        down_path = os.path.join(migrations_dir, f"{stem}_down.sql")
        if os.path.isfile(down_path):
            with_down += 1
        else:
            missing.append(name)
    return {
        "total": total,
        "with_down": with_down,
        "gaps": len(missing),
        "missing": missing,
    }


@router.get("/backup/status")
@_instrument("/operations/backup/status", "operations.backup_status")
async def operations_backup_status() -> dict:
    enc = encryption_status()
    sto = storage_status()
    latest_report = _read_dr_report_latest()
    latest_manifest = _latest_backup_manifest()
    migration_inv = _migration_down_inventory()
    safety = _backup_safety_summary()
    # Use BackupStorage just to confirm the mode is wired (no IO).
    BackupStorage()
    rto_seconds = (
        float(latest_report.get("estimated_rto_seconds") or 0.0) if latest_report else None
    )
    rpo_seconds = latest_report.get("estimated_rpo_seconds") if latest_report else None
    return {
        "latest_backup_manifest": latest_manifest,
        "latest_dr_report": latest_report,
        "backup_schedule_configured": _backup_schedule_installed(),
        "off_host_storage_configured": sto.get("credential_complete", False),
        "encryption_configured": enc["enabled"],
        "encryption_production_ready": enc["production_ready"],
        "encryption_mode": enc["mode"],
        "encryption_key_id": enc["key_id"],
        "storage_mode": sto["mode"],
        "last_restore_drill_status": (latest_report.get("status") if latest_report else "not_run"),
        "rto_seconds": rto_seconds,
        "rpo_seconds": rpo_seconds,
        "migration_down_inventory": migration_inv,
        "production_ready": safety["backup_production_ready"],
        "gaps": safety["backup_gaps"],
        "production_executed": False,
        "generated_at": _utcnow_iso(),
    }


@router.get("/backup/reports")
@_instrument("/operations/backup/reports", "operations.backup_reports")
async def operations_backup_reports(limit: int = 25) -> dict:
    capped = max(1, min(int(limit or 25), 100))
    reports = _list_dr_reports(limit=capped)
    return {
        "count": len(reports),
        "reports": reports,
        "filter": {"limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/backup/reports/latest")
@_instrument("/operations/backup/reports/latest", "operations.backup_reports_latest")
async def operations_backup_reports_latest() -> dict:
    latest = _read_dr_report_latest()
    if latest is None:
        return {
            "available": False,
            "report": None,
            "generated_at": _utcnow_iso(),
        }
    return {
        "available": True,
        "report": latest,
        "generated_at": _utcnow_iso(),
    }


def _backup_schedule_installed() -> bool:
    """Best-effort check for whether the operator installed the cron line."""

    try:
        import subprocess

        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return "backup_postgres_encrypted.sh" in (result.stdout or "")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Stage 38 -- LLM Model Routing & Agent Model Policy operations view.
# Read-only. Never returns an API key, prompt body, or response body.
# ---------------------------------------------------------------------------


async def _llm_routing_safety_summary() -> dict[str, Any]:
    """Counts-only snapshot used by /operations/safety.

    Falls back to ``enabled=False`` when the routing tables are
    unreachable so a fresh stack still answers the endpoint.
    """

    summary: dict[str, Any] = {
        "enabled": True,
        "registry_active_count": 0,
        "policy_active_count": 0,
    }
    store = ModelRouterStore()
    try:
        models = await store.list_models(status="active", limit=500)
        policies = await store.list_policies(status="active", limit=500)
        summary["registry_active_count"] = len(models)
        summary["policy_active_count"] = len(policies)
    except Exception:
        summary["enabled"] = False
    return summary


@router.get("/llm/models")
@_instrument("/operations/llm/models", "operations.llm_models")
async def operations_llm_models(
    status: str | None = "active",
    provider: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = ModelRouterStore()
    try:
        rows = await store.list_models(status=status, provider=provider, limit=capped)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"model registry unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "models": [r.to_safe_dict() for r in rows],
        "filter": {"status": status, "provider": provider, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/model-policies")
@_instrument("/operations/llm/model-policies", "operations.llm_model_policies")
async def operations_llm_model_policies(
    agent_name: str | None = None,
    status: str | None = "active",
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = ModelRouterStore()
    try:
        rows = await store.list_policies(agent_name=agent_name, status=status, limit=capped)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"policy store unavailable: {exc}") from exc
    return {
        "count": len(rows),
        "policies": [r.to_safe_dict() for r in rows],
        "filter": {"agent_name": agent_name, "status": status, "limit": capped},
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/routing-decisions")
@_instrument("/operations/llm/routing-decisions", "operations.llm_routing_decisions")
async def operations_llm_routing_decisions(
    task_id: str | None = None,
    agent_name: str | None = None,
    decision: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    store = ModelRouterStore()
    try:
        rows = await store.list_decisions(
            task_id=task_id, agent_name=agent_name, decision=decision, limit=capped
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"routing decisions store unavailable: {exc}"
        ) from exc
    return {
        "count": len(rows),
        "decisions": [r.to_safe_dict() for r in rows],
        "filter": {
            "task_id": task_id,
            "agent_name": agent_name,
            "decision": decision,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/llm/routing-decisions/{task_id}")
@_instrument(
    "/operations/llm/routing-decisions/{task_id}",
    "operations.llm_routing_decisions_for_task",
)
async def operations_llm_routing_decisions_for_task(task_id: str) -> dict:
    store = ModelRouterStore()
    try:
        rows = await store.list_decisions(task_id=task_id, limit=200)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"routing decisions store unavailable: {exc}"
        ) from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "decisions": [r.to_safe_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }


class _RoutingPreviewIn(BaseModel):
    agent_name: str
    capability: str
    task_id: str | None = None
    workflow_id: str | None = None
    task_type: str = AGENT_DEFAULT_TASK_TYPE
    risk_level: str = "low"
    requested_schema: str | None = None
    requested_model_alias: str | None = None
    estimated_input_tokens: int = 0
    max_output_tokens: int | None = None
    allow_real_llm_requested: bool = False
    persist: bool = False


@router.post("/llm/routing/preview")
@_instrument("/operations/llm/routing/preview", "operations.llm_routing_preview")
async def operations_llm_routing_preview(payload: _RoutingPreviewIn) -> dict:
    store = ModelRouterStore()
    request = build_capability_request(
        agent_name=payload.agent_name,
        capability=payload.capability,
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        task_type=payload.task_type,
        risk_level=payload.risk_level,
        requested_schema=payload.requested_schema,
        requested_model_alias=payload.requested_model_alias,
        estimated_input_tokens=int(payload.estimated_input_tokens or 0),
        max_output_tokens=payload.max_output_tokens,
        allow_real_llm_requested=bool(payload.allow_real_llm_requested),
    )
    router_instance = ModelRouter(store=store)
    try:
        decision = await router_instance.route(request, persist=bool(payload.persist))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"routing failed: {exc}") from exc
    return {
        "request": request.to_dict(),
        "decision": decision.to_safe_dict(),
        "persisted": bool(payload.persist),
        "generated_at": _utcnow_iso(),
    }


@router.post("/llm/routing/seed-defaults")
@_instrument("/operations/llm/routing/seed-defaults", "operations.llm_routing_seed_defaults")
async def operations_llm_routing_seed_defaults() -> dict:
    """Idempotent seed for the default registry + agent policies.

    Useful in test clusters: re-run after a migration to ensure the
    expected baseline is in place. Never overwrites operator-set
    flags beyond what the seed declares.
    """

    store = ModelRouterStore()
    seeded_models: list[str] = []
    seeded_policies: list[str] = []
    try:
        for entry in default_models():
            model = await store.upsert_model(entry)
            seeded_models.append(model.model_alias)
        for entry in default_agent_policies():
            policy = await store.upsert_policy(entry)
            seeded_policies.append(f"{policy.agent_name}/{policy.capability}[{policy.risk_level}]")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"seed failed: {exc}") from exc
    return {
        "seeded_models": seeded_models,
        "seeded_policies": seeded_policies,
        "generated_at": _utcnow_iso(),
    }
