"""notification-worker — consumes ``stream.notifications`` and records deliveries.

Stage 22 introduces the platform's notification delivery surface:

    publisher -> stream.notifications -> notification-worker -> notification_deliveries

Default mode is **sandbox**: every event becomes a row in
``notification_deliveries`` with ``status='simulated'``,
``sandbox=true``, ``external_sent=false``. The Discord API is only
contacted when ALL of ``DISCORD_BOT_TOKEN`` /
``DISCORD_TEST_CHANNEL_ID`` / ``RUN_REAL_DISCORD_TEST=true`` are set,
and even then only one Discord message is ever sent per consumed event,
to ``DISCORD_TEST_CHANNEL_ID`` only, with a body prefix of
``[AI-Agents-SWD sandbox]``.

Audit events are published onto ``stream.audit`` via the Stage 19
publisher; the audit-worker persists them into ``audit_logs``.
Backlog policy: the worker consumes new events only (the group is
created with ``$``); historical entries are intentionally not back-
filled — the operator can drain on demand via ``XGROUP SETID``.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import Any

from discord_client import DiscordDeliverySafetyError, NotificationDiscordClient

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.event_bus.redis_streams import (
    DEAD_LETTER_STREAM,
    RedisStreamEventBus,
)
from shared.sdk.notifications.real_delivery_policy import (
    DELIVERY_DECISION_REAL_ALLOWED,
    DELIVERY_DECISION_REAL_BLOCKED,
    DELIVERY_DECISION_SKIPPED,
    RealDeliveryDecision,
    RealDeliveryPolicy,
    classify_real_delivery,
    load_policy_from_env,
)
from shared.sdk.notifications.store import NotificationDeliveryStore
from shared.sdk.observability.metrics import (
    NOTIFICATION_WORKER_DELIVERED_TOTAL,
    NOTIFICATION_WORKER_FAILURES_TOTAL,
    NOTIFICATION_WORKER_PROCESSED_TOTAL,
    NOTIFICATION_WORKER_PROCESSING_SECONDS,
    NOTIFICATION_WORKER_SIMULATED_TOTAL,
    NOTIFICATION_WORKER_SKIPPED_TOTAL,
    REAL_DISCORD_DELIVERY_ALLOWED_TOTAL,
    REAL_DISCORD_DELIVERY_BLOCKED_TOTAL,
    REAL_DISCORD_DELIVERY_POLICY_DECISIONS_TOTAL,
    REAL_DISCORD_DELIVERY_SKIPPED_TOTAL,
)
from shared.sdk.observability.tracing import start_span

NOTIFICATION_STREAM = "stream.notifications"
NOTIFICATION_GROUP = "notification-worker-group"
NOTIFICATION_CONSUMER = "notification-worker-1"
MAX_FAILURES_BEFORE_DEADLETTER = 3

ORCHESTRATOR_PUBLIC_URL = os.environ.get("ORCHESTRATOR_PUBLIC_URL", "")


def _safe_bool(value: Any) -> bool:
    return bool(value)


def render_discord_message(payload: dict[str, Any]) -> str:
    """Build a sandbox-safe summary line for a notification.

    Important: the payload is operator-side notification metadata. It is
    NOT a place where secrets live — but we still build a deterministic,
    explicit summary instead of dumping the dict so a future producer
    cannot accidentally smuggle a secret into a Discord message.
    """
    task_id = str(payload.get("task_id") or "unknown")
    event_type = str(payload.get("event_type") or payload.get("event") or "unknown")
    message = str(payload.get("message") or "")
    status = str(payload.get("status") or "")
    parts: list[str] = [f"[{event_type}]", task_id]
    if status:
        parts.append(f"status={status}")
    parts.append("production_executed=false")
    if ORCHESTRATOR_PUBLIC_URL:
        parts.append(f"ops={ORCHESTRATOR_PUBLIC_URL}/operations/workflows/{task_id}")
    else:
        parts.append(f"ops=/operations/workflows/{task_id}")
    # Some events come with an artifact_refs.github.pr_url or pr_url at
    # the top level — surface it if present without exposing anything
    # else.
    pr_url = (
        payload.get("pr_url") or (payload.get("github") or {}).get("pr_url")
        if isinstance(payload.get("github"), dict)
        else None
    )
    if pr_url:
        parts.append(f"pr={pr_url}")
    if message:
        truncated = message if len(message) <= 200 else message[:200] + "…"
        parts.append(f"msg={truncated}")
    return " | ".join(parts)


class NotificationWorker:
    """Consume ``stream.notifications`` and record deliveries."""

    def __init__(
        self,
        event_bus: RedisStreamEventBus | None = None,
        store: NotificationDeliveryStore | None = None,
        client: NotificationDiscordClient | None = None,
        policy: RealDeliveryPolicy | None = None,
    ) -> None:
        self.bus = event_bus or RedisStreamEventBus()
        self.store = store or NotificationDeliveryStore()
        self._client = client or NotificationDiscordClient()
        if policy is not None:
            self.policy = policy
        else:
            loaded = load_policy_from_env(real_mode_enabled=self._client.can_deliver())
            # If env didn't surface a test channel but the client has
            # one configured (the common test fixture case), prefer the
            # client's value so the policy can actually approve sends.
            client_channel = getattr(self._client, "test_channel_id", "") or ""
            if not loaded.test_channel_id and client_channel:
                loaded.test_channel_id = client_channel
            self.policy = loaded
        self.processed_count = 0
        self.delivered_count = 0
        self.simulated_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.real_delivery_allowed_count = 0
        self.real_delivery_blocked_count = 0
        self.real_delivery_skipped_count = 0
        self.last_real_delivery_decision: str | None = None
        self.last_real_delivery_block_reason: str | None = None
        self.last_message_id: str | None = None
        self.last_task_id: str | None = None
        self.last_error: str | None = None
        self.running = False
        self._retry_counts: dict[str, int] = {}

    def status(self) -> dict[str, Any]:
        return {
            "service": "notification-worker",
            "running": self.running,
            "input_stream": NOTIFICATION_STREAM,
            "group": NOTIFICATION_GROUP,
            "consumer": NOTIFICATION_CONSUMER,
            "mode": "sandbox" if not self._client.can_deliver() else "controlled-real",
            "has_discord_token": self._client.has_token,
            "real_discord_enabled": self._client.real_enabled,
            "test_channel_configured": self._client.has_test_channel,
            "external_send_enabled": self._client.can_deliver(),
            "processed_count": self.processed_count,
            "delivered_count": self.delivered_count,
            "simulated_count": self.simulated_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "real_delivery_enabled": self.policy.real_mode_enabled,
            "real_delivery_allowlist": list(self.policy.allowlist),
            "real_delivery_denylist": list(self.policy.denylist),
            "real_delivery_allow_marker": self.policy.allow_marker,
            "real_delivery_allowed_count": self.real_delivery_allowed_count,
            "real_delivery_blocked_count": self.real_delivery_blocked_count,
            "real_delivery_skipped_count": self.real_delivery_skipped_count,
            "last_real_delivery_decision": self.last_real_delivery_decision,
            "last_real_delivery_block_reason": self.last_real_delivery_block_reason,
            "last_message_id": self.last_message_id,
            "last_task_id": self.last_task_id,
            "last_error": self.last_error,
        }

    async def _publish_audit(
        self,
        *,
        task_id: str | None,
        decision_type: str,
        summary: str,
        result: str,
        delivery_id: str | None,
        source_message_id: str,
        event_type: str,
        sandbox: bool,
        external_sent: bool,
        extra_refs: dict[str, Any] | None = None,
    ) -> None:
        refs: dict[str, Any] = {
            "delivery_id": delivery_id or "",
            "source_message_id": source_message_id,
            "event_type": event_type,
            "sandbox": sandbox,
            "external_sent": external_sent,
        }
        if extra_refs:
            refs.update(extra_refs)
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id or "unknown",
                agent="notification-worker",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )

    async def _deliver_via_discord(
        self,
        *,
        delivery_id: str,
        rendered: str,
    ) -> tuple[bool, str, str]:
        """Send the rendered message to Discord. Returns (ok, message_id, error)."""
        try:
            with start_span(
                "notification.real_discord_send",
                **{
                    "service.name": "notification-worker",
                    "agent": "notification-worker",
                    "sandbox": False,
                    "external_sent": True,
                },
            ):
                result = await self._client.send_test_message(rendered)
            return True, str(result.get("message_id", "")), ""
        except DiscordDeliverySafetyError as exc:
            return False, "", f"safety: {exc}"
        except Exception as exc:
            return False, "", f"discord: {exc.__class__.__name__}: {exc}"

    async def handle(self, message_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Process one stream.notifications event.

        Returns one of:

        * ``{action: simulated, delivery_id, ack: True}``
        * ``{action: delivered, delivery_id, message_id, ack: True}``
        * ``{action: skipped, reason, ack: True}``
        * ``{action: deadlettered, reason, ack: True}``
        * ``{action: retry, reason, ack: False}``
        """
        started = time.perf_counter()
        self.last_message_id = message_id
        try:
            if not isinstance(payload, dict):
                self.skipped_count += 1
                NOTIFICATION_WORKER_SKIPPED_TOTAL.labels(reason="empty").inc()
                return {"action": "skipped", "reason": "non-dict payload", "ack": True}

            task_id_raw = payload.get("task_id")
            task_id = str(task_id_raw).strip() if task_id_raw is not None else ""
            self.last_task_id = task_id or None
            event_type = str(payload.get("event_type") or payload.get("event") or "unknown")
            NOTIFICATION_WORKER_PROCESSED_TOTAL.labels(event_type=event_type).inc()

            with start_span(
                "notification.consume",
                **{
                    "service.name": "notification-worker",
                    "agent": "notification-worker",
                    "task_id": task_id,
                    "event_type": event_type,
                    "redis.message_id": message_id,
                    "stream": NOTIFICATION_STREAM,
                },
            ):
                with start_span(
                    "notification.render_discord_message",
                    **{
                        "service.name": "notification-worker",
                        "agent": "notification-worker",
                        "task_id": task_id,
                        "event_type": event_type,
                    },
                ):
                    try:
                        rendered = render_discord_message(payload)
                    except Exception as exc:
                        self.failed_count += 1
                        self.last_error = f"render: {exc}"
                        NOTIFICATION_WORKER_FAILURES_TOTAL.labels(reason="render_error").inc()
                        return {
                            "action": "deadlettered",
                            "reason": str(exc),
                            "ack": True,
                        }
                # Stage 33 -- evaluate the real-delivery policy BEFORE we
                # touch the store, so an internal stream event with real
                # env live can be downgraded to simulated/skipped without
                # ever attempting an external API call.
                with start_span(
                    "notification.real_delivery_policy",
                    **{
                        "service.name": "notification-worker",
                        "agent": "notification-worker",
                        "task_id": task_id,
                        "event_type": event_type,
                    },
                ):
                    decision = classify_real_delivery(payload, self.policy)
                self.last_real_delivery_decision = decision.decision
                self.last_real_delivery_block_reason = decision.reason or None
                REAL_DISCORD_DELIVERY_POLICY_DECISIONS_TOTAL.labels(
                    event_type=event_type,
                    decision=decision.decision,
                    reason=decision.reason or "none",
                ).inc()

                metadata: dict[str, Any] = {
                    "rendered_message": rendered,
                    "original_event": payload,
                    "delivery_decision": decision.decision,
                    "blocked_reason": decision.reason,
                    "event_type": event_type,
                    "sandbox": decision.sandbox,
                    "external_sent": False,
                }
                sandbox_input = _safe_bool(payload.get("sandbox", True))

                external_send_enabled = (
                    decision.decision == DELIVERY_DECISION_REAL_ALLOWED
                    and self._client.can_deliver()
                )
                if (
                    decision.decision == DELIVERY_DECISION_REAL_ALLOWED
                    and not self._client.can_deliver()
                ):
                    # Policy said yes but client disagrees -- treat as
                    # skipped so we never attempt the external call.
                    decision = RealDeliveryDecision(
                        decision=DELIVERY_DECISION_SKIPPED,
                        reason="client_cannot_deliver",
                        event_type=event_type,
                        sandbox=True,
                        external_sent=False,
                        target_channel=decision.target_channel,
                    )
                    metadata["delivery_decision"] = decision.decision
                    metadata["blocked_reason"] = decision.reason
                    self.last_real_delivery_decision = decision.decision
                    self.last_real_delivery_block_reason = decision.reason

                with start_span(
                    "notification.persist_delivery",
                    **{
                        "service.name": "notification-worker",
                        "agent": "notification-worker",
                        "task_id": task_id,
                        "event_type": event_type,
                        "channel": "discord",
                    },
                ):
                    if external_send_enabled:
                        target = self._client.test_channel_id
                        initial_status = "pending"
                        sandbox_flag = False
                    elif decision.decision == DELIVERY_DECISION_REAL_BLOCKED:
                        target = self.policy.test_channel_id or "sandbox-channel"
                        initial_status = "skipped"
                        sandbox_flag = False
                    elif decision.decision == DELIVERY_DECISION_SKIPPED:
                        target = self.policy.test_channel_id or "sandbox-channel"
                        initial_status = "skipped"
                        sandbox_flag = True
                    else:  # simulated
                        target = "sandbox-channel"
                        initial_status = "simulated"
                        sandbox_flag = True

                    delivery = await self.store.create_delivery(
                        task_id=task_id or None,
                        event_type=event_type,
                        channel="discord",
                        target=target,
                        status=initial_status,
                        sandbox=sandbox_flag,
                        external_sent=False,
                        source_message_id=message_id,
                        metadata=metadata,
                    )
                if delivery is None:
                    # Source_message_id already recorded — dedup.
                    self.skipped_count += 1
                    NOTIFICATION_WORKER_SKIPPED_TOTAL.labels(reason="duplicate").inc()
                    return {
                        "action": "skipped",
                        "reason": "duplicate source_message_id",
                        "ack": True,
                    }
                delivery_id = str(delivery["delivery_id"])

                if decision.decision == DELIVERY_DECISION_REAL_BLOCKED:
                    self.real_delivery_blocked_count += 1
                    REAL_DISCORD_DELIVERY_BLOCKED_TOTAL.labels(
                        event_type=event_type, reason=decision.reason or "unknown"
                    ).inc()
                    with start_span(
                        "notification.real_delivery_block",
                        **{
                            "service.name": "notification-worker",
                            "agent": "notification-worker",
                            "task_id": task_id,
                            "event_type": event_type,
                            "reason": decision.reason or "unknown",
                        },
                    ):
                        await self._publish_audit(
                            task_id=task_id or None,
                            decision_type="discord_real_delivery_blocked",
                            summary=(
                                f"real discord delivery blocked "
                                f"(event={event_type}, reason={decision.reason})"
                            ),
                            result="blocked",
                            delivery_id=delivery_id,
                            source_message_id=message_id,
                            event_type=event_type,
                            sandbox=False,
                            external_sent=False,
                            extra_refs={
                                "delivery_decision": decision.decision,
                                "blocked_reason": decision.reason,
                                "production_executed": False,
                            },
                        )
                    self.processed_count += 1
                    return {
                        "action": "real_blocked",
                        "delivery_id": delivery_id,
                        "reason": decision.reason,
                        "ack": True,
                    }

                if decision.decision == DELIVERY_DECISION_SKIPPED:
                    self.real_delivery_skipped_count += 1
                    REAL_DISCORD_DELIVERY_SKIPPED_TOTAL.labels(
                        event_type=event_type, reason=decision.reason or "unknown"
                    ).inc()
                    await self._publish_audit(
                        task_id=task_id or None,
                        decision_type="discord_real_delivery_skipped",
                        summary=(
                            f"real discord delivery skipped "
                            f"(event={event_type}, reason={decision.reason})"
                        ),
                        result="skipped",
                        delivery_id=delivery_id,
                        source_message_id=message_id,
                        event_type=event_type,
                        sandbox=True,
                        external_sent=False,
                        extra_refs={
                            "delivery_decision": decision.decision,
                            "blocked_reason": decision.reason,
                            "production_executed": False,
                        },
                    )
                    self.processed_count += 1
                    return {
                        "action": "skipped",
                        "delivery_id": delivery_id,
                        "reason": decision.reason,
                        "ack": True,
                    }

                if external_send_enabled:
                    self.real_delivery_allowed_count += 1
                    REAL_DISCORD_DELIVERY_ALLOWED_TOTAL.labels(event_type=event_type).inc()
                    with start_span(
                        "notification.real_delivery_send",
                        **{
                            "service.name": "notification-worker",
                            "agent": "notification-worker",
                            "task_id": task_id,
                            "event_type": event_type,
                            "channel": "discord",
                        },
                    ):
                        ok, discord_message_id, error = await self._deliver_via_discord(
                            delivery_id=delivery_id, rendered=rendered
                        )
                    if ok:
                        await self.store.mark_delivered(
                            delivery_id,
                            message_id=discord_message_id,
                            external_sent=True,
                        )
                        self.delivered_count += 1
                        NOTIFICATION_WORKER_DELIVERED_TOTAL.labels(
                            event_type=event_type, channel="discord"
                        ).inc()
                        await self._publish_audit(
                            task_id=task_id or None,
                            decision_type="discord_real_test_sent",
                            summary=(
                                f"discord delivery ok (event={event_type}, "
                                f"task={task_id or 'unknown'})"
                            ),
                            result="delivered",
                            delivery_id=delivery_id,
                            source_message_id=message_id,
                            event_type=event_type,
                            sandbox=False,
                            external_sent=True,
                            extra_refs={
                                "delivery_decision": DELIVERY_DECISION_REAL_ALLOWED,
                                "production_executed": False,
                            },
                        )
                        return {
                            "action": "delivered",
                            "delivery_id": delivery_id,
                            "message_id": discord_message_id,
                            "ack": True,
                        }
                    self.failed_count += 1
                    self.last_error = error
                    NOTIFICATION_WORKER_FAILURES_TOTAL.labels(reason="discord_error").inc()
                    await self.store.mark_failed(delivery_id, error=error)
                    await self._publish_audit(
                        task_id=task_id or None,
                        decision_type="notification_delivery_failed",
                        summary=(
                            f"discord delivery failed (event={event_type}, "
                            f"task={task_id or 'unknown'}): {error}"
                        ),
                        result="failed",
                        delivery_id=delivery_id,
                        source_message_id=message_id,
                        event_type=event_type,
                        sandbox=False,
                        external_sent=False,
                    )
                    attempts = self._retry_counts.get(message_id, 0) + 1
                    self._retry_counts[message_id] = attempts
                    if attempts >= MAX_FAILURES_BEFORE_DEADLETTER:
                        await self._publish_deadletter(message_id, payload, error)
                        self._retry_counts.pop(message_id, None)
                        return {"action": "deadlettered", "reason": error, "ack": True}
                    return {"action": "retry", "reason": error, "ack": False}

                # Sandbox path — record the simulation + audit.
                with start_span(
                    "notification.simulate_delivery",
                    **{
                        "service.name": "notification-worker",
                        "agent": "notification-worker",
                        "task_id": task_id,
                        "event_type": event_type,
                        "channel": "discord",
                        "sandbox": True,
                    },
                ):
                    self.simulated_count += 1
                    NOTIFICATION_WORKER_SIMULATED_TOTAL.labels(
                        event_type=event_type, channel="discord"
                    ).inc()
                    sandbox_marker = (
                        "sandbox=true" if sandbox_input else "sandbox=true(forced; no opt-in)"
                    )
                    await self._publish_audit(
                        task_id=task_id or None,
                        decision_type="notification_delivery",
                        summary=(
                            f"notification simulated (event={event_type}, "
                            f"task={task_id or 'unknown'}, {sandbox_marker})"
                        ),
                        result="simulated",
                        delivery_id=delivery_id,
                        source_message_id=message_id,
                        event_type=event_type,
                        sandbox=True,
                        external_sent=False,
                    )
                self.processed_count += 1
                return {
                    "action": "simulated",
                    "delivery_id": delivery_id,
                    "ack": True,
                }
        except Exception as exc:
            self.failed_count += 1
            self.last_error = f"unexpected: {exc}"
            NOTIFICATION_WORKER_FAILURES_TOTAL.labels(reason="store_error").inc()
            attempts = self._retry_counts.get(message_id, 0) + 1
            self._retry_counts[message_id] = attempts
            if attempts >= MAX_FAILURES_BEFORE_DEADLETTER:
                await self._publish_deadletter(message_id, payload, str(exc))
                self._retry_counts.pop(message_id, None)
                return {"action": "deadlettered", "reason": str(exc), "ack": True}
            return {"action": "retry", "reason": str(exc), "ack": False}
        finally:
            NOTIFICATION_WORKER_PROCESSING_SECONDS.observe(time.perf_counter() - started)

    async def _publish_deadletter(
        self, message_id: str, payload: dict[str, Any], reason: str
    ) -> None:
        envelope = {
            "event": "notification.deadlettered",
            "event_type": "notification.deadlettered",
            "task_id": payload.get("task_id") if isinstance(payload, dict) else "unknown",
            "workflow_id": payload.get("workflow_id", "") if isinstance(payload, dict) else "",
            "original_stream": NOTIFICATION_STREAM,
            "original_message_id": message_id,
            "failure_reason": reason,
            "original_event": payload,
            "retry_count": self._retry_counts.get(message_id, 0),
            "max_retries": MAX_FAILURES_BEFORE_DEADLETTER,
        }
        with contextlib.suppress(Exception):
            with start_span(
                "notification.deadletter",
                **{
                    "service.name": "notification-worker",
                    "agent": "notification-worker",
                    "redis.message_id": message_id,
                    "stream": NOTIFICATION_STREAM,
                },
            ):
                await self.bus.publish_event(DEAD_LETTER_STREAM, envelope)

    async def _ensure_group(self) -> None:
        with contextlib.suppress(Exception):
            await self.bus.ensure_group(NOTIFICATION_STREAM, NOTIFICATION_GROUP)

    async def run(self, stop_event: asyncio.Event) -> None:
        self.running = True
        await self._ensure_group()
        try:
            while not stop_event.is_set():
                try:
                    events = await self.bus.consume_events(
                        NOTIFICATION_STREAM,
                        NOTIFICATION_GROUP,
                        NOTIFICATION_CONSUMER,
                        count=20,
                        block_ms=2000,
                    )
                    for event in events:
                        message_id = event["id"]
                        payload = event["event"]
                        try:
                            outcome = await self.handle(message_id, payload)
                        except Exception as exc:
                            self.last_error = f"handler crashed: {exc}"
                            outcome = {"action": "retry", "ack": False}
                        if outcome.get("ack", True):
                            with contextlib.suppress(Exception):
                                await self.bus.ack_event(
                                    NOTIFICATION_STREAM, NOTIFICATION_GROUP, message_id
                                )
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        finally:
            self.running = False

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.bus.close()
