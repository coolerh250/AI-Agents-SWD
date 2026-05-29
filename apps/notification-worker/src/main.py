"""notification-worker FastAPI service.

Default mode is **sandbox**: stream.notifications events are persisted as
``notification_deliveries`` rows with ``status='simulated'``,
``sandbox=true``, ``external_sent=false``. The real Discord API is
contacted ONLY when ``DISCORD_BOT_TOKEN`` /
``DISCORD_TEST_CHANNEL_ID`` / ``RUN_REAL_DISCORD_TEST=true`` are all
set. The token never leaves the env var.
"""

import asyncio
import contextlib
import os
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from discord_client import DiscordDeliverySafetyError, NotificationDiscordClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.notifications.store import NotificationDeliveryStore
from shared.sdk.observability.metrics import (
    NOTIFICATION_WORKER_DELIVERED_TOTAL,
    NOTIFICATION_WORKER_PROCESSING_SECONDS,
    NOTIFICATION_WORKER_SKIPPED_TOTAL,
    install_metrics_endpoint,
)
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
    start_span,
)
from worker import NotificationWorker

setup_tracing("notification-worker")
instrument_asyncpg()
instrument_httpx()
instrument_redis()

_worker = NotificationWorker()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    consumer = asyncio.create_task(_worker.run(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _worker.close()


app = FastAPI(title="notification-worker", lifespan=lifespan)
instrument_fastapi(app, "notification-worker")
install_metrics_endpoint(app)


def _client() -> NotificationDiscordClient:
    return NotificationDiscordClient()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/health")
def health() -> dict:
    client = _client()
    return {
        "service": "notification-worker",
        "status": "ok",
        "mode": "sandbox" if not client.can_deliver() else "controlled-real",
        "has_discord_token": client.has_token,
        "real_discord_enabled": client.real_enabled,
    }


@app.get("/status")
def status() -> dict:
    return _worker.status()


@app.get("/deliveries")
async def list_deliveries(
    task_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
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


class RealTestMessageIn(BaseModel):
    content: str = "controlled Discord delivery test"


@app.post("/discord/real/test-message")
async def real_test_message(payload: RealTestMessageIn) -> dict:
    """Send ONE controlled-real Discord message. Default refused with 409.

    Audit is published for both the skipped and the sent path so an
    operator inspecting ``audit_logs`` for
    ``decision_type=discord_real_test_*`` always sees the contract was
    enforced.
    """
    started = time.perf_counter()
    client = _client()
    NOTIFICATION_WORKER_PROCESSING_SECONDS.observe(0)  # touch the histogram once
    if not client.can_deliver():
        NOTIFICATION_WORKER_SKIPPED_TOTAL.labels(reason="sandbox_self_test").inc()
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id="discord-real-test",
                agent="notification-worker",
                decision_type="discord_real_test_skipped",
                summary=("real Discord test refused (sandbox by default; opt-in env " "missing)"),
                result="skipped",
                artifact_refs={
                    "sandbox": True,
                    "external_sent": False,
                    "has_token": client.has_token,
                    "has_test_channel": client.has_test_channel,
                    "real_enabled": client.real_enabled,
                },
            )
        raise HTTPException(
            status_code=409,
            detail=(
                "real Discord test is not enabled — set DISCORD_BOT_TOKEN, "
                "DISCORD_TEST_CHANNEL_ID, and RUN_REAL_DISCORD_TEST=true to "
                "opt in"
            ),
        )

    store = NotificationDeliveryStore()
    delivery: dict[str, Any] = {}
    with start_span(
        "notification.real_discord_send",
        **{
            "service.name": "notification-worker",
            "agent": "notification-worker",
            "event_type": "discord.real.test",
            "channel": "discord",
            "sandbox": False,
            "external_sent": True,
        },
    ):
        try:
            result = await client.send_test_message(payload.content)
        except DiscordDeliverySafetyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            with contextlib.suppress(Exception):
                await publish_audit_event(
                    task_id="discord-real-test",
                    agent="notification-worker",
                    decision_type="notification_delivery_failed",
                    summary=f"discord real test failed: {exc.__class__.__name__}",
                    result="failed",
                    artifact_refs={"sandbox": False, "external_sent": False},
                )
            raise HTTPException(status_code=502, detail=f"discord error: {exc}") from exc
        delivery_row = await store.create_delivery(
            task_id="discord-real-test",
            event_type="discord.real.test",
            channel="discord",
            target=client.test_channel_id,
            status="delivered",
            sandbox=False,
            external_sent=True,
            message_id=result.get("message_id"),
            source_message_id=f"discord-real-test-{int(time.time()*1000)}",
            metadata={"content_summary": payload.content[:200]},
        )
        if delivery_row is None:
            delivery = {"delivery_id": "", "external_sent": True}
        else:
            delivery = delivery_row
        NOTIFICATION_WORKER_DELIVERED_TOTAL.labels(
            event_type="discord.real.test", channel="discord"
        ).inc()
    NOTIFICATION_WORKER_PROCESSING_SECONDS.observe(time.perf_counter() - started)
    with contextlib.suppress(Exception):
        await publish_audit_event(
            task_id="discord-real-test",
            agent="notification-worker",
            decision_type="discord_real_test_sent",
            summary=f"discord real test delivered (message_id={result.get('message_id', '')})",
            result="delivered",
            artifact_refs={
                "sandbox": False,
                "external_sent": True,
                "message_id": result.get("message_id"),
                "delivery_id": delivery.get("delivery_id", ""),
            },
        )
    return {
        "message_id": result.get("message_id"),
        "channel_id": result.get("channel_id"),
        "delivery_id": delivery.get("delivery_id", ""),
        "sandbox": False,
        "external_sent": True,
        "delivered_to": "discord.com",
    }


# Surface a richer summary alongside the worker /status.
@app.get("/summary")
async def summary() -> dict:
    base = _worker.status()
    counts: dict[str, int] = {
        "total": 0,
        "simulated": 0,
        "delivered": 0,
        "failed": 0,
        "skipped": 0,
        "external_sent": 0,
    }
    with contextlib.suppress(Exception):
        counts = await NotificationDeliveryStore().counts()
    base["delivery_counts"] = counts
    base["orchestrator_public_url"] = os.environ.get("ORCHESTRATOR_PUBLIC_URL", "")
    return base
