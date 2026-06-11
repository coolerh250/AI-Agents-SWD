"""Discord Gateway sandbox service.

Stage 21: a thin FastAPI service that accepts Discord-like messages,
parses them into intake payloads, dispatches them via the existing
``communication-gateway /intake/mock`` orchestrator-mode path, and
publishes per-task notifications + audit events. **No real Discord
API is contacted** unless the opt-in pre-conditions in ``client.py``
are met; the default mode is ``sandbox``.

The service exposes:

* ``GET  /health``
* ``GET  /status``
* ``GET  /metrics``
* ``POST /discord/messages``
* ``POST /discord/events/mock``
* ``GET  /discord/messages``
* ``GET  /discord/tasks/{task_id}``  (proxies ``/operations/workflows/{task_id}``)
* ``POST /discord/notify/test``
"""

import contextlib
import json
import os
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from client import DiscordClient, DiscordSafetyError
from parser import ParseError, parse_discord_message
from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.notifications.client import NotificationClient
from shared.sdk.notifications.store import NotificationDeliveryStore
from shared.sdk.observability.metrics import (
    DISCORD_INTAKE_FAILURES_TOTAL,
    DISCORD_MESSAGES_RECEIVED_TOTAL,
    DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL,
    DISCORD_REQUEST_DURATION_SECONDS,
    DISCORD_TASKS_DISPATCHED_TOTAL,
    REAL_DISCORD_GUARD_BLOCKS_TOTAL,
    REAL_DISCORD_TASKS_TOTAL,
    REAL_DISCORD_TESTS_TOTAL,
    REAL_INTEGRATION_FAILURES_TOTAL,
    install_metrics_endpoint,
)
from shared.sdk.real_integration import (
    evaluate_real_discord_request,
    render_safe_discord_message,
)
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
    start_span,
)
from shared.sdk.task_execution import TaskExecutionStore

COMMUNICATION_GATEWAY_URL = os.environ.get(
    "COMMUNICATION_GATEWAY_URL", "http://communication-gateway:8004"
).rstrip("/")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000").rstrip("/")
DISCORD_GATEWAY_MODE = (
    os.environ.get("DISCORD_GATEWAY_MODE", "sandbox").strip().lower() or "sandbox"
)

setup_tracing("discord-gateway")
instrument_httpx()
instrument_redis()
instrument_asyncpg()


# ---------------------------------------------------------------------------
# In-process running counters surfaced via /status.
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "running": True,
    "received_count": 0,
    "dispatched_count": 0,
    "failed_count": 0,
    "last_task_id": None,
    "last_error": None,
}


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _state["running"] = True
    try:
        yield
    finally:
        _state["running"] = False


app = FastAPI(title="discord-gateway", lifespan=lifespan)
instrument_fastapi(app, "discord-gateway")
install_metrics_endpoint(app)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client() -> DiscordClient:
    return DiscordClient()


# ---------------------------------------------------------------------------
# Pydantic request models.
# ---------------------------------------------------------------------------


class DiscordMessageIn(BaseModel):
    """Simplified text payload — what an operator types into a Discord channel."""

    content: str = ""
    channel_id: str = ""
    user_id: str = ""
    message_id: str = ""
    task_id: str | None = None


class DiscordEventIn(BaseModel):
    """Discord-like INTERACTION_CREATE / MESSAGE_CREATE payload (sandbox)."""

    # ``type`` is left as a string so a Discord interaction integer (e.g. 1)
    # round-trips losslessly without forcing Pydantic to resolve a union
    # forward reference when the module is loaded outside the normal sys.path.
    type: Any = None
    content: str | None = None
    data: dict[str, Any] | None = None
    channel_id: str = ""
    author: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] = Field(default_factory=dict)
    id: str = ""
    task_id: str | None = None


class DiscordNotifyTestIn(BaseModel):
    task_id: str = ""
    channel_id: str = "sandbox-channel"
    user_id: str = "sandbox-operator"
    message: str = "discord sandbox notification test"


# ---------------------------------------------------------------------------
# Side-effect helpers.
# ---------------------------------------------------------------------------


async def _publish_notification(
    *,
    task_id: str,
    event_type: str,
    message: str,
    channel_id: str,
    user_id: str,
) -> None:
    """Best-effort publish on ``stream.notifications``. Sandbox-flagged."""
    payload: dict[str, Any] = {
        "task_id": task_id,
        "event_type": event_type,
        "message": message,
        "channel_id": channel_id,
        "user_id": user_id,
        "sandbox": True,
        "created_at": _utcnow_iso(),
    }
    with start_span(
        "discord.publish_notification",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "discord.channel_id": channel_id,
            "discord.user_id": user_id,
            "task_id": task_id,
            "event_type": event_type,
            "sandbox": True,
        },
    ):
        client = NotificationClient()
        try:
            await client.event_bus.publish_event(NotificationClient.STREAM, payload)
            DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL.labels(
                event_type=event_type, sandbox="true"
            ).inc()
        except Exception:
            DISCORD_INTAKE_FAILURES_TOTAL.labels(reason="gateway_error").inc()
        finally:
            with contextlib.suppress(Exception):
                await client.close()


async def _publish_audit(
    *,
    task_id: str,
    summary: str,
    result: str,
    decision_type: str,
    channel_id: str,
    user_id: str,
    message_id: str,
    operations_url: str,
) -> None:
    """Publish a ``discord_intake`` / ``discord_notification_test`` audit event."""
    refs: dict[str, Any] = {
        "channel_id": channel_id,
        "user_id": user_id,
        "message_id": message_id,
        "sandbox": True,
        "operations_url": operations_url,
    }
    with start_span(
        "discord.write_audit",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "discord.channel_id": channel_id,
            "discord.user_id": user_id,
            "task_id": task_id,
            "audit.decision_type": decision_type,
            "sandbox": True,
        },
    ):
        await publish_audit_event(
            task_id=task_id,
            agent="discord-gateway",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=refs,
        )


async def _dispatch_to_gateway(payload: dict[str, Any]) -> dict[str, Any]:
    """POST the parsed payload at communication-gateway /intake/mock."""
    body = {
        "task_id": payload["task_id"],
        "request": payload["request"],
        "publish_to_stream": False,
    }
    url = f"{COMMUNICATION_GATEWAY_URL}/intake/mock"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        DISCORD_INTAKE_FAILURES_TOTAL.labels(reason="dispatch_error").inc()
        raise HTTPException(
            status_code=502, detail=f"communication-gateway unavailable: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Recent-message buffer (in-memory, sandbox only).
# ---------------------------------------------------------------------------

_RECENT_MESSAGES: list[dict[str, Any]] = []
_MAX_RECENT = 200


def _remember_message(parsed: dict[str, Any], dispatch_result: dict[str, Any]) -> None:
    entry = {
        "task_id": parsed["task_id"],
        "command_type": parsed.get("command_type", "unknown"),
        "request_type": parsed["request"]["type"],
        "description": parsed["request"].get("description", ""),
        "channel_id": parsed["request"]["discord"]["channel_id"],
        "user_id": parsed["request"]["discord"]["user_id"],
        "message_id": parsed["request"]["discord"]["message_id"],
        "stage": dispatch_result.get("stage"),
        "approval_required": dispatch_result.get("approval_required"),
        "received_at": _utcnow_iso(),
    }
    _RECENT_MESSAGES.append(entry)
    if len(_RECENT_MESSAGES) > _MAX_RECENT:
        del _RECENT_MESSAGES[: len(_RECENT_MESSAGES) - _MAX_RECENT]


# ---------------------------------------------------------------------------
# Shared intake pipeline.
# ---------------------------------------------------------------------------


async def _intake(
    *,
    content: str,
    channel_id: str,
    user_id: str,
    message_id: str,
    task_id: str | None,
    endpoint: str,
) -> dict[str, Any]:
    """Parse + dispatch + notify + audit. Used by both POST endpoints."""
    started = time.perf_counter()
    _state["received_count"] += 1
    try:
        with start_span(
            "discord.parse_message",
            **{
                "service.name": "discord-gateway",
                "agent": "discord-gateway",
                "discord.channel_id": channel_id,
                "discord.user_id": user_id,
                "sandbox": True,
            },
        ):
            parsed = parse_discord_message(
                content,
                channel_id=channel_id,
                user_id=user_id,
                message_id=message_id,
                task_id=task_id,
            )
    except ParseError as exc:
        _state["failed_count"] += 1
        _state["last_error"] = str(exc)
        DISCORD_INTAKE_FAILURES_TOTAL.labels(reason="parse_error").inc()
        DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )
        raise HTTPException(status_code=400, detail=f"discord parse error: {exc}") from exc

    command_type = parsed.get("command_type", "unknown")
    DISCORD_MESSAGES_RECEIVED_TOTAL.labels(command_type=command_type, sandbox="true").inc()

    with start_span(
        "discord.dispatch_task",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "task_id": parsed["task_id"],
            "discord.channel_id": parsed["request"]["discord"]["channel_id"],
            "discord.user_id": parsed["request"]["discord"]["user_id"],
            "command_type": command_type,
            "sandbox": True,
        },
    ):
        try:
            dispatch_result = await _dispatch_to_gateway(parsed)
        except HTTPException:
            _state["failed_count"] += 1
            _state["last_error"] = "dispatch_error"
            DISCORD_TASKS_DISPATCHED_TOTAL.labels(
                command_type=command_type, result="error", sandbox="true"
            ).inc()
            DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
                time.perf_counter() - started
            )
            raise

    _state["dispatched_count"] += 1
    _state["last_task_id"] = parsed["task_id"]
    DISCORD_TASKS_DISPATCHED_TOTAL.labels(
        command_type=command_type,
        result="ok",
        sandbox="true",
    ).inc()
    _remember_message(parsed, dispatch_result)

    stage = str(dispatch_result.get("stage") or "")
    approval_required = bool(dispatch_result.get("approval_required") or False)
    if stage == "waiting_approval" or approval_required:
        event_type = "discord.task.waiting_approval"
    elif stage == "completed":
        event_type = "discord.task.completed"
    else:
        event_type = "discord.task.dispatched"

    operations_url = f"/operations/workflows/{parsed['task_id']}"
    summary = (
        f"discord sandbox intake ({parsed['request']['type']}) for "
        f"{parsed['task_id']} (stage={stage or 'unknown'})"
    )

    await _publish_notification(
        task_id=parsed["task_id"],
        event_type="discord.task.received",
        message=f"received: {parsed['request'].get('description', '')}",
        channel_id=parsed["request"]["discord"]["channel_id"],
        user_id=parsed["request"]["discord"]["user_id"],
    )
    await _publish_notification(
        task_id=parsed["task_id"],
        event_type=event_type,
        message=summary,
        channel_id=parsed["request"]["discord"]["channel_id"],
        user_id=parsed["request"]["discord"]["user_id"],
    )
    await _publish_audit(
        task_id=parsed["task_id"],
        summary=summary,
        result=stage or "dispatched",
        decision_type="discord_intake",
        channel_id=parsed["request"]["discord"]["channel_id"],
        user_id=parsed["request"]["discord"]["user_id"],
        message_id=parsed["request"]["discord"]["message_id"],
        operations_url=operations_url,
    )

    DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(
        time.perf_counter() - started
    )
    return {
        "task_id": parsed["task_id"],
        "stage": stage,
        "approval_required": approval_required,
        "operations_url": operations_url,
        "message": summary,
        "dry_run": True,
        "sandbox": True,
        "command_type": command_type,
        "request_type": parsed["request"]["type"],
        "event_type": event_type,
    }


# ---------------------------------------------------------------------------
# Routes.
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    client = _client()
    return {
        "service": "discord-gateway",
        "status": "ok",
        "mode": DISCORD_GATEWAY_MODE,
        "has_token": client.has_token,
    }


@app.get("/status")
def status() -> dict:
    client = _client()
    return {
        "service": "discord-gateway",
        "running": bool(_state["running"]),
        "mode": DISCORD_GATEWAY_MODE,
        "has_token": client.has_token,
        "real_test_enabled": client.real_test_enabled,
        "received_count": int(_state["received_count"]),
        "dispatched_count": int(_state["dispatched_count"]),
        "failed_count": int(_state["failed_count"]),
        "last_task_id": _state["last_task_id"],
        "last_error": _state["last_error"],
    }


@app.post("/discord/messages")
async def post_message(payload: DiscordMessageIn) -> dict:
    return await _intake(
        content=payload.content,
        channel_id=payload.channel_id,
        user_id=payload.user_id,
        message_id=payload.message_id,
        task_id=payload.task_id,
        endpoint="/discord/messages",
    )


def _extract_event_text(payload: DiscordEventIn) -> tuple[str, str, str, str]:
    """Pull (content, channel_id, user_id, message_id) from a Discord-like event."""
    content = payload.content or ""
    # Discord interactions carry the slash command under ``data.name`` and the
    # text under ``data.options[0].value``. We accept the simpler
    # ``data.content`` shape too so a sandbox client doesn't need to mimic the
    # full real API.
    if not content and isinstance(payload.data, dict):
        if isinstance(payload.data.get("content"), str):
            content = payload.data["content"]
        elif isinstance(payload.data.get("name"), str):
            tokens: list[str] = ["/" + payload.data["name"]]
            for option in payload.data.get("options") or []:
                if not isinstance(option, dict):
                    continue
                name = str(option.get("name") or "")
                value = option.get("value")
                if name and value is not None:
                    tokens.append(f"{name}={json.dumps(value)}")
            content = " ".join(tokens)
    channel_id = payload.channel_id or ""
    user_id = ""
    if isinstance(payload.author, dict):
        user_id = str(payload.author.get("id") or "")
    if not user_id and isinstance(payload.user, dict):
        user_id = str(payload.user.get("id") or "")
    message_id = payload.id or ""
    return content, channel_id, user_id, message_id


@app.post("/discord/events/mock")
async def post_event_mock(payload: DiscordEventIn) -> dict:
    content, channel_id, user_id, message_id = _extract_event_text(payload)
    return await _intake(
        content=content,
        channel_id=channel_id,
        user_id=user_id,
        message_id=message_id,
        task_id=payload.task_id,
        endpoint="/discord/events/mock",
    )


@app.get("/discord/messages")
def list_messages(limit: int = 20) -> dict:
    limit = max(1, min(int(limit or 20), 200))
    items = list(_RECENT_MESSAGES[-limit:][::-1])
    return {"count": len(items), "messages": items}


@app.get("/discord/tasks/{task_id}")
async def lookup_task(task_id: str) -> dict:
    started = time.perf_counter()
    url = f"{ORCHESTRATOR_URL}/operations/workflows/{task_id}"
    with start_span(
        "discord.operation_lookup",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "task_id": task_id,
            "sandbox": True,
        },
    ):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint="/discord/tasks/{task_id}").observe(
                time.perf_counter() - started
            )
            raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint="/discord/tasks/{task_id}").observe(
        time.perf_counter() - started
    )
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="task not found")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="operations view unavailable")
    body = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else {}
    )

    github = body.get("github") if isinstance(body.get("github"), dict) else {}
    audit_timeline = (
        body.get("audit_timeline") if isinstance(body.get("audit_timeline"), list) else []
    )
    incidents = body.get("incidents") if isinstance(body.get("incidents"), list) else []
    progress = body.get("progress") if isinstance(body.get("progress"), dict) else {}
    completed_agents = progress.get("completed_agents") if isinstance(progress, dict) else []

    # Stage 22: enrich the discord task lookup with notification delivery
    # bookkeeping so an operator can see whether the platform notified
    # them at all.
    deliveries: list[dict[str, Any]] = []
    with contextlib.suppress(Exception):
        deliveries = await NotificationDeliveryStore().list_deliveries(task_id=task_id, limit=50)
    external_sent = sum(1 for d in deliveries if d.get("external_sent"))
    simulated = sum(1 for d in deliveries if d.get("status") == "simulated")
    failed = sum(1 for d in deliveries if d.get("status") == "failed")
    latest = deliveries[0] if deliveries else None
    code_generation = (
        body.get("code_generation") if isinstance(body.get("code_generation"), dict) else {}
    )
    cg_workspace = (
        code_generation.get("workspace")
        if isinstance(code_generation.get("workspace"), dict)
        else {}
    )
    cg_pr_draft = (
        code_generation.get("pr_draft") if isinstance(code_generation.get("pr_draft"), dict) else {}
    )
    cg_validation = (
        code_generation.get("validation_result")
        if isinstance(code_generation.get("validation_result"), dict)
        else {}
    )
    cg_changed_files = (
        code_generation.get("changed_files")
        if isinstance(code_generation.get("changed_files"), list)
        else []
    )
    return {
        "task_id": task_id,
        "stage": body.get("stage", ""),
        "execution_status": body.get("execution_status", ""),
        "completed_agents": completed_agents or [],
        "github": {
            "pr_url": github.get("pr_url", ""),
            "dry_run": github.get("dry_run"),
            "status": github.get("status", ""),
        },
        "audit_timeline_count": len(audit_timeline),
        "incidents_count": len(incidents),
        "production_executed": bool(body.get("production_executed", False)),
        "operations_url": f"/operations/workflows/{task_id}",
        "operations_view": body,
        "notification_deliveries_count": len(deliveries),
        "latest_delivery_status": (latest or {}).get("status", ""),
        "latest_delivery_message_id": (latest or {}).get("message_id", "") or "",
        "external_sent": bool(external_sent),
        "delivery_breakdown": {
            "simulated": simulated,
            "external_sent": external_sent,
            "failed": failed,
        },
        # Stage 28 — controlled code generation status surfaces for the
        # Discord operator. Empty section if no workspace exists yet.
        "code_generation_status": code_generation.get("status", ""),
        "code_generation_template": cg_workspace.get("generator_mode", "") if cg_workspace else "",
        "changed_files_count": len(cg_changed_files),
        "pr_draft_status": cg_pr_draft.get("status", "") if cg_pr_draft else "",
        "github_dry_run_pr_url": github.get("pr_url", ""),
        "validation_status": cg_validation.get("status", "") if cg_validation else "",
        "code_generation_blocked_reason": code_generation.get("blocked_reason", ""),
        # Stage 29 — QA-guided validation + auto-fix surfaces.
        "qa_status": (
            (body.get("qa_validation") or {}).get("status", "")
            if isinstance(body.get("qa_validation"), dict)
            else ""
        ),
        "qa_final_result": (
            (body.get("qa_validation") or {}).get("final_result", "")
            if isinstance(body.get("qa_validation"), dict)
            else ""
        ),
        "qa_findings_count": (
            len((body.get("qa_validation") or {}).get("findings") or [])
            if isinstance(body.get("qa_validation"), dict)
            else 0
        ),
        "blocking_findings_count": (
            int((body.get("qa_validation") or {}).get("blocking_findings_count", 0) or 0)
            if isinstance(body.get("qa_validation"), dict)
            else 0
        ),
        "auto_fix_attempts": (
            int((body.get("qa_validation") or {}).get("auto_fix_attempts", 0) or 0)
            if isinstance(body.get("qa_validation"), dict)
            else 0
        ),
        "blocked_for_human_review": (
            bool((body.get("qa_validation") or {}).get("blocked_for_human_review", False))
            if isinstance(body.get("qa_validation"), dict)
            else False
        ),
        # Stage 30 — LLM-assisted development guardrails surfaces.
        "llm_provider": (
            str((body.get("llm_assistance") or {}).get("provider", ""))
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "llm_proposal_status": (
            str(((body.get("llm_assistance") or {}).get("latest_proposal") or {}).get("status", ""))
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "llm_requires_human_review": (
            bool((body.get("llm_assistance") or {}).get("requires_human_review", True))
            if isinstance(body.get("llm_assistance"), dict)
            else True
        ),
        "llm_policy_blocked": (
            bool((body.get("llm_assistance") or {}).get("blocked", False))
            if isinstance(body.get("llm_assistance"), dict)
            else False
        ),
        "llm_policy_violations_count": (
            len((body.get("llm_assistance") or {}).get("policy_violations") or [])
            if isinstance(body.get("llm_assistance"), dict)
            else 0
        ),
        "llm_usage_total_tokens": (
            int(
                ((body.get("llm_assistance") or {}).get("usage_summary") or {}).get(
                    "total_tokens", 0
                )
                or 0
            )
            if isinstance(body.get("llm_assistance"), dict)
            else 0
        ),
        # Stage 31 -- approval policy + LLM promotion surfaces.
        "approval_mode": (
            str((body.get("approval_policy") or {}).get("approval_mode", "per_action"))
            if isinstance(body.get("approval_policy"), dict)
            else "per_action"
        ),
        "active_approval_policy": (
            ((body.get("approval_policy") or {}).get("active_policies") or [None])[0]
            if isinstance(body.get("approval_policy"), dict)
            else None
        ),
        "delegated_actions_used": (
            int((body.get("approval_policy") or {}).get("delegated_actions_used", 0) or 0)
            if isinstance(body.get("approval_policy"), dict)
            else 0
        ),
        "delegated_actions_remaining": (
            int((body.get("approval_policy") or {}).get("delegated_actions_remaining", 0) or 0)
            if isinstance(body.get("approval_policy"), dict)
            else 0
        ),
        "latest_approval_decision": (
            ((body.get("approval_policy") or {}).get("decisions") or [None])[0]
            if isinstance(body.get("approval_policy"), dict)
            else None
        ),
        "llm_promotion_status": (
            (((body.get("approval_policy") or {}).get("promotions") or [None])[0] or {}).get(
                "status", ""
            )
            if isinstance(body.get("approval_policy"), dict)
            else ""
        ),
        # Stage 38 -- LLM Model Routing & Agent Model Policy.
        # Pulled from the orchestrator operations view; never exposes
        # API keys, provider secrets, or arbitrary model selection.
        "llm_model_router_enabled": True,
        "agent_direct_model_selection_allowed": False,
        "selected_model_alias": (
            (((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}).get(
                "selected_model_alias", ""
            )
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "selected_provider": (
            (((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}).get(
                "selected_provider", ""
            )
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "selected_model_tier": (
            (((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}).get(
                "selected_model_tier", ""
            )
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "routing_decision": (
            (((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}).get(
                "decision", ""
            )
            if isinstance(body.get("llm_assistance"), dict)
            else ""
        ),
        "routing_requires_human_review": (
            bool(
                (
                    ((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}
                ).get("requires_human_review", True)
            )
            if isinstance(body.get("llm_assistance"), dict)
            else True
        ),
        "routing_fallback_used": (
            bool(
                (
                    ((body.get("llm_assistance") or {}).get("routing_decisions") or [None])[0] or {}
                ).get("fallback_used", False)
            )
            if isinstance(body.get("llm_assistance"), dict)
            else False
        ),
        "sandbox": True,
    }


@app.get("/discord/deliveries")
async def list_deliveries(
    task_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    try:
        rows = await NotificationDeliveryStore().list_deliveries(
            task_id=task_id, status=status, limit=limit
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"notification store unavailable: {exc}"
        ) from exc
    return {"count": len(rows), "deliveries": rows, "generated_at": _utcnow_iso()}


@app.get("/discord/deliveries/{task_id}")
async def get_deliveries_for_task(task_id: str) -> dict:
    try:
        rows = await NotificationDeliveryStore().list_deliveries(task_id=task_id, limit=200)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"notification store unavailable: {exc}"
        ) from exc
    return {
        "task_id": task_id,
        "count": len(rows),
        "deliveries": rows,
        "external_sent_count": sum(1 for r in rows if r.get("external_sent")),
        "simulated_count": sum(1 for r in rows if r.get("status") == "simulated"),
        "failed_count": sum(1 for r in rows if r.get("status") == "failed"),
        "generated_at": _utcnow_iso(),
    }


@app.post("/discord/notify/test")
async def notify_test(payload: DiscordNotifyTestIn) -> dict:
    task_id = payload.task_id or f"discord-notify-test-{int(time.time())}"
    await _publish_notification(
        task_id=task_id,
        event_type="discord.notification.test",
        message=payload.message,
        channel_id=payload.channel_id,
        user_id=payload.user_id,
    )
    await _publish_audit(
        task_id=task_id,
        summary=f"discord sandbox notification test: {payload.message}",
        result="ok",
        decision_type="discord_notification_test",
        channel_id=payload.channel_id,
        user_id=payload.user_id,
        message_id="",
        operations_url=f"/operations/workflows/{task_id}",
    )
    return {
        "task_id": task_id,
        "event_type": "discord.notification.test",
        "sandbox": True,
        "delivered_to": "stream.notifications",
    }


# ---------------------------------------------------------------------------
# Stage 27 — clarification round-trip endpoints.
# ---------------------------------------------------------------------------


class ClarificationAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    user_id: str | None = None
    channel_id: str | None = None
    message_id: str | None = None


@app.get("/discord/clarifications/{task_id}")
async def list_clarifications_for_task(task_id: str) -> dict:
    """Return every clarification request for ``task_id`` (sandbox-only)."""
    store = TaskExecutionStore()
    try:
        rows = await store.list_clarification_requests(task_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"task execution store unavailable: {exc}"
        ) from exc
    work_item = None
    try:
        wi = await store.get_work_item(task_id)
        if wi is not None:
            work_item = wi.to_dict()
    except Exception:
        work_item = None
    open_count = sum(1 for r in rows if r.status == "open")
    return {
        "task_id": task_id,
        "count": len(rows),
        "open_count": open_count,
        "clarifications": [r.to_dict() for r in rows],
        "work_item": work_item,
        "generated_at": _utcnow_iso(),
    }


@app.post("/discord/clarifications/{clarification_id}/answer")
async def answer_clarification(clarification_id: str, payload: ClarificationAnswerIn) -> dict:
    """Record the operator's answer + trigger the workflow resume.

    Writes the answer into ``clarification_requests`` (status=answered),
    publishes a ``clarification.answered`` notification, an audit row,
    and calls the orchestrator's
    ``/workflow/resume-after-clarification/{task_id}`` so the work item
    can flip to ready_for_development without operator intervention.
    The route does NOT contact the real Discord API.
    """
    store = TaskExecutionStore()
    try:
        existing = await store.get_clarification_request(clarification_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"task execution store unavailable: {exc}"
        ) from exc
    if existing is None:
        raise HTTPException(status_code=404, detail="clarification not found")
    if existing.status != "open":
        return {
            "clarification_id": clarification_id,
            "status": existing.status,
            "sandbox": True,
            "operations_url": f"/operations/workflows/{existing.task_id}",
            "already_answered": True,
            "generated_at": _utcnow_iso(),
        }
    try:
        updated = await store.answer_clarification_request(
            clarification_id,
            user_response=payload.answer,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"failed to record answer: {exc}") from exc
    if updated is None:
        raise HTTPException(status_code=409, detail="clarification could not be answered")

    task_id = updated.task_id
    await _publish_notification(
        task_id=task_id,
        event_type="clarification.answered",
        message=(
            f"clarification {clarification_id} answered (length="
            f"{len(payload.answer)}); resuming workflow"
        ),
        channel_id=payload.channel_id,
        user_id=payload.user_id,
    )
    await _publish_audit(
        task_id=task_id,
        summary=f"clarification {clarification_id} answered by {payload.user_id or 'operator'}",
        result="ok",
        decision_type="clarification_answered",
        channel_id=payload.channel_id,
        user_id=payload.user_id,
        message_id=payload.message_id or "",
        operations_url=f"/operations/workflows/{task_id}",
    )

    # Best-effort: ask the orchestrator to resume the workflow. A
    # missing orchestrator must not break the answer write — the
    # operator can still call the resume endpoint manually.
    resume_status = "skipped"
    resume_url = f"{ORCHESTRATOR_URL}/workflow/resume-after-clarification/{task_id}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(resume_url)
            if response.status_code < 400:
                resume_status = "ok"
            else:
                resume_status = f"http_{response.status_code}"
    except Exception:
        resume_status = "error"

    return {
        "clarification_id": clarification_id,
        "task_id": task_id,
        "status": updated.status,
        "sandbox": True,
        "answer_length": len(payload.answer),
        "resume_status": resume_status,
        "operations_url": f"/operations/workflows/{task_id}",
        "generated_at": _utcnow_iso(),
    }


class DiscordRealTestMessageIn(BaseModel):
    """Stage 32 real-test message payload.

    The defaults are deliberately empty so a casual caller can't
    accidentally fire a real send -- ``channel_id`` MUST be supplied
    and MUST match ``DISCORD_TEST_CHANNEL_ID`` to pass the guard.
    """

    task_id: str = ""
    channel_id: str = ""
    guild_id: str = ""
    role_id: str = ""
    user_id: str = "sandbox-operator"
    mode: str = "controlled_test"
    summary: str = "discord controlled-test message"
    operations_url: str = ""
    approval_required: bool = False
    production_executed: bool = False


def _operations_url_for(task_id: str) -> str:
    return f"/operations/workflows/{task_id}" if task_id else ""


async def _record_real_discord_delivery(
    *,
    task_id: str,
    event_type: str,
    channel: str,
    target: str,
    status: str,
    external_sent: bool,
    message_id: str | None,
    error: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Best-effort write into ``notification_deliveries``.

    Returns the persisted row dict or ``None`` if the row could not be
    written (DB hiccup). Failure here MUST NOT raise -- the audit event
    is the source of truth.
    """
    try:
        store = NotificationDeliveryStore()
        return await store.create_delivery(
            task_id=task_id or None,
            event_type=event_type,
            channel=channel,
            target=target,
            status=status,
            sandbox=True,
            external_sent=external_sent,
            message_id=message_id,
            error=error,
            metadata=metadata or {},
        )
    except Exception:
        return None


@app.post("/discord/real/test-message")
async def real_test_message(payload: DiscordRealTestMessageIn) -> dict:
    """Stage 32 controlled-real Discord test message.

    Every Stage 32 guard pre-condition must hold (see
    ``shared.sdk.real_integration.discord.evaluate_real_discord_request``).
    On allow the gateway sends ONE redacted summary message through the
    real Discord API, records a ``notification_deliveries`` row with
    ``external_sent=true``, publishes a ``discord.real_test_sent``
    notification event, and emits a ``discord_real_test_sent`` audit
    event. The token value is never returned, never logged, never
    placed into the response or the audit ``artifact_refs``.
    """
    task_id = (payload.task_id or "").strip()
    channel_id = (payload.channel_id or "").strip()
    guild_id = (payload.guild_id or "").strip()
    target_label = channel_id or "real-channel"
    op_url = payload.operations_url or _operations_url_for(task_id)

    with start_span(
        "real_discord.guard",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "task_id": task_id,
            "discord.channel_id": channel_id,
            "discord.guild_id": guild_id,
            "sandbox": True,
            "production_executed": False,
        },
    ):
        guard = evaluate_real_discord_request(
            channel_id=channel_id,
            guild_id=guild_id,
            role_id=payload.role_id,
            mode=payload.mode,
            production_executed=payload.production_executed,
        )

    if not guard.allowed:
        REAL_DISCORD_GUARD_BLOCKS_TOTAL.labels(reason=guard.reason).inc()
        REAL_DISCORD_TESTS_TOTAL.labels(result="blocked").inc()
        await _publish_audit(
            task_id=task_id or "real-discord-blocked",
            summary=f"real Discord test blocked: {guard.reason}",
            result="blocked",
            decision_type="discord_real_test_blocked",
            channel_id=channel_id,
            user_id=payload.user_id,
            message_id="",
            operations_url=op_url,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "operation": "real_test_message",
                "safety_guard_result": guard.to_safe_dict(),
            },
        )

    body_text = render_safe_discord_message(
        summary=payload.summary,
        fields={
            "task_id": task_id,
            "status": "controlled_test",
            "operations_url": op_url,
            "approval_required": str(payload.approval_required).lower(),
            "production_executed": "false",
        },
    )

    client = _client()
    with start_span(
        "real_discord.send_test_message",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "task_id": task_id,
            "discord.channel_id": channel_id,
            "sandbox": True,
            "production_executed": False,
        },
    ):
        try:
            sent = await client.post_sandbox_test_message(channel_id, body_text)
        except DiscordSafetyError as exc:
            REAL_DISCORD_TESTS_TOTAL.labels(result="blocked").inc()
            REAL_INTEGRATION_FAILURES_TOTAL.labels(provider="discord", reason="safety_error").inc()
            await _publish_audit(
                task_id=task_id or "real-discord-blocked",
                summary=f"real Discord client refused: {exc}",
                result="blocked",
                decision_type="discord_real_test_blocked",
                channel_id=channel_id,
                user_id=payload.user_id,
                message_id="",
                operations_url=op_url,
            )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            REAL_DISCORD_TESTS_TOTAL.labels(result="error").inc()
            REAL_INTEGRATION_FAILURES_TOTAL.labels(
                provider="discord", reason=exc.__class__.__name__
            ).inc()
            await _publish_audit(
                task_id=task_id or "real-discord-failed",
                summary=f"real Discord send failed: {exc.__class__.__name__}",
                result="failed",
                decision_type="discord_real_test_blocked",
                channel_id=channel_id,
                user_id=payload.user_id,
                message_id="",
                operations_url=op_url,
            )
            raise HTTPException(status_code=502, detail="discord send failed") from exc

    message_id = sent.get("message_id", "")

    delivery_row = await _record_real_discord_delivery(
        task_id=task_id or None,
        event_type="discord.real_test_sent",
        channel="discord",
        target=target_label,
        status="delivered",
        external_sent=True,
        message_id=message_id,
        error=None,
        metadata={
            "guild_id": guild_id,
            "mode": payload.mode,
            "production_executed": False,
            "sandbox": True,
        },
    )

    await _publish_notification(
        task_id=task_id or "real-discord-test",
        event_type="discord.real_test_sent",
        message=f"real Discord controlled-test message dispatched (channel={channel_id})",
        channel_id=channel_id,
        user_id=payload.user_id,
    )
    await _publish_audit(
        task_id=task_id or "real-discord-test",
        summary=(
            f"real Discord test message sent (channel={channel_id}, " f"message_id={message_id})"
        ),
        result="ok",
        decision_type="discord_real_test_sent",
        channel_id=channel_id,
        user_id=payload.user_id,
        message_id=message_id,
        operations_url=op_url,
    )
    REAL_DISCORD_TESTS_TOTAL.labels(result="sent").inc()

    return {
        "sandbox": True,
        "test_mode": True,
        "external_sent": True,
        "production_executed": False,
        "message_id": message_id,
        "channel_id": sent.get("channel_id", channel_id),
        "guild_id": guild_id,
        "task_id": task_id,
        "operations_url": op_url,
        "delivery_id": (delivery_row or {}).get("delivery_id", ""),
        "safety_guard_result": guard.to_safe_dict(),
        "delivered_to": "discord.com",
        "generated_at": _utcnow_iso(),
    }


class DiscordRealEventIn(BaseModel):
    """Stage 32 controlled-real Discord event payload.

    Used to simulate an incoming Discord interaction/message from the
    operator's test channel WITHOUT running a long-lived Gateway Bot
    loop. The same guard as ``/discord/real/test-message`` is applied,
    so the same allowlist (token + opt-in + test guild + test channel +
    role) gates the path.
    """

    task_id: str = ""
    channel_id: str = ""
    guild_id: str = ""
    role_id: str = ""
    user_id: str = "sandbox-operator"
    mode: str = "controlled_test"
    content: str = ""
    message_id: str = ""
    production_executed: bool = False


@app.post("/discord/real/events/test")
async def real_event_test(payload: DiscordRealEventIn) -> dict:
    """Receive a controlled-real Discord event from the pinned test channel.

    The event is sent through the existing sandbox intake pipeline
    (``parser.parse_discord_message`` + ``communication-gateway
    /intake/mock``), tagged ``sandbox=True`` + ``test_mode=True``.
    Production-shaped requests (``production.deploy`` etc.) are NEVER
    accepted on this path: the request_type is forced through the
    parser which itself refuses unknown commands.
    """
    task_id = (payload.task_id or "").strip()
    channel_id = (payload.channel_id or "").strip()

    with start_span(
        "real_discord.receive_task",
        **{
            "service.name": "discord-gateway",
            "agent": "discord-gateway",
            "task_id": task_id,
            "discord.channel_id": channel_id,
            "sandbox": True,
            "production_executed": False,
        },
    ):
        guard = evaluate_real_discord_request(
            channel_id=channel_id,
            guild_id=payload.guild_id,
            role_id=payload.role_id,
            mode=payload.mode,
            production_executed=payload.production_executed,
        )

    if not guard.allowed:
        REAL_DISCORD_GUARD_BLOCKS_TOTAL.labels(reason=guard.reason).inc()
        REAL_DISCORD_TASKS_TOTAL.labels(result="blocked").inc()
        await _publish_audit(
            task_id=task_id or "real-discord-task-blocked",
            summary=f"real Discord task blocked: {guard.reason}",
            result="blocked",
            decision_type="discord_real_task_blocked",
            channel_id=channel_id,
            user_id=payload.user_id,
            message_id=payload.message_id,
            operations_url=_operations_url_for(task_id),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "operation": "real_event_test",
                "safety_guard_result": guard.to_safe_dict(),
            },
        )

    content = (payload.content or "").strip()
    if not content:
        REAL_DISCORD_TASKS_TOTAL.labels(result="blocked").inc()
        REAL_DISCORD_GUARD_BLOCKS_TOTAL.labels(reason="content_required").inc()
        raise HTTPException(status_code=400, detail="content is required")

    try:
        result = await _intake(
            content=content,
            channel_id=channel_id,
            user_id=payload.user_id,
            message_id=payload.message_id or f"real-test-{int(time.time() * 1000)}",
            task_id=task_id or None,
            endpoint="/discord/real/events/test",
        )
    except HTTPException:
        REAL_DISCORD_TASKS_TOTAL.labels(result="error").inc()
        raise

    REAL_DISCORD_TASKS_TOTAL.labels(result="received").inc()
    accepted_task_id = result.get("task_id") or task_id or ""
    await _publish_notification(
        task_id=accepted_task_id,
        event_type="discord.real_task_received",
        message=(
            f"real Discord controlled-test task accepted (channel={channel_id}, "
            f"task_id={accepted_task_id})"
        ),
        channel_id=channel_id,
        user_id=payload.user_id,
    )
    await _publish_audit(
        task_id=accepted_task_id,
        summary=(
            f"real Discord controlled-test task accepted (channel={channel_id}, "
            f"task_id={accepted_task_id})"
        ),
        result="ok",
        decision_type="discord_real_task_received",
        channel_id=channel_id,
        user_id=payload.user_id,
        message_id=payload.message_id,
        operations_url=_operations_url_for(accepted_task_id),
    )
    return {
        "sandbox": True,
        "test_mode": True,
        "external_sent": False,
        "production_executed": False,
        "channel_id": channel_id,
        "guild_id": payload.guild_id,
        "task_id": accepted_task_id,
        "intake_result": result,
        "safety_guard_result": guard.to_safe_dict(),
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# Stage 31 -- Discord approval-policy + LLM proposal promotion proxies
# ---------------------------------------------------------------------------


class DiscordApprovalPolicyIn(BaseModel):
    task_id: str
    workflow_id: str | None = None
    scope_type: str = "task"
    scope_id: str = ""
    approval_mode: str = "per_action"
    granted_by: str = "discord-operator"
    allowed_stages: list[str] = Field(default_factory=list)
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)
    max_actions: int | None = None
    max_files_changed: int | None = None
    max_auto_fix_attempts: int | None = None
    expires_at: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    activate: bool = True


class DiscordRevokeIn(BaseModel):
    revoked_by: str = "discord-operator"
    reason: str | None = None


class DiscordApproveIn(BaseModel):
    approved_by: str = "discord-operator"
    reason: str | None = None


class DiscordRejectIn(BaseModel):
    rejected_by: str = "discord-operator"
    reason: str | None = None


class DiscordPromoteIn(BaseModel):
    task_id: str
    workflow_id: str | None = None
    promoted_by: str = "discord-operator"
    approval_id: str | None = None
    policy_id: str | None = None
    promotion_mode: str = "manual"


async def _proxy_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST ``body`` at ``url`` and return the JSON envelope.

    The discord-gateway never owns Stage 31 state; it just forwards to
    the orchestrator. This keeps the gateway sandbox-shaped: no DB
    write, no Redis write, no LLM call.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    if response.status_code == 400:
        raise HTTPException(status_code=400, detail=response.text)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=response.text)
    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="orchestrator error")
    body_out = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    return body_out


async def _proxy_get(url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=response.text)
    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="orchestrator error")
    body_out = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    return body_out


@app.post("/discord/approval-policies")
async def discord_create_approval_policy(payload: DiscordApprovalPolicyIn) -> dict:
    body = payload.model_dump()
    body["granted_by"] = body.get("granted_by") or "discord-operator"
    result = await _proxy_post(f"{ORCHESTRATOR_URL}/approval-policies", body)
    return {"sandbox": True, **result}


@app.get("/discord/approval-policies/{task_id}")
async def discord_list_approval_policies(task_id: str) -> dict:
    result = await _proxy_get(f"{ORCHESTRATOR_URL}/operations/approval-policies/{task_id}")
    return {"sandbox": True, **result}


@app.post("/discord/approval-policies/{policy_id}/revoke")
async def discord_revoke_approval_policy(policy_id: str, payload: DiscordRevokeIn) -> dict:
    body = payload.model_dump()
    result = await _proxy_post(f"{ORCHESTRATOR_URL}/approval-policies/{policy_id}/revoke", body)
    return {"sandbox": True, **result}


@app.post("/discord/llm/proposals/{proposal_id}/approve")
async def discord_approve_llm_proposal(proposal_id: str, payload: DiscordApproveIn) -> dict:
    body = payload.model_dump()
    result = await _proxy_post(
        f"{ORCHESTRATOR_URL}/llm/proposals/{proposal_id}/approval/approve", body
    )
    return {"sandbox": True, **result}


@app.post("/discord/llm/proposals/{proposal_id}/reject")
async def discord_reject_llm_proposal(proposal_id: str, payload: DiscordRejectIn) -> dict:
    body = payload.model_dump()
    result = await _proxy_post(
        f"{ORCHESTRATOR_URL}/llm/proposals/{proposal_id}/approval/reject", body
    )
    return {"sandbox": True, **result}


@app.post("/discord/llm/proposals/{proposal_id}/promote")
async def discord_promote_llm_proposal(proposal_id: str, payload: DiscordPromoteIn) -> dict:
    body = payload.model_dump()
    body["promoted_by"] = body.get("promoted_by") or "discord-operator"
    result = await _proxy_post(f"{ORCHESTRATOR_URL}/llm/proposals/{proposal_id}/promote", body)
    return {"sandbox": True, **result}
