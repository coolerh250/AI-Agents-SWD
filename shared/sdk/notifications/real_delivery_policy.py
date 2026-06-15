"""Stage 33 -- real Discord delivery policy.

The notification-worker stream consumer (``stream.notifications`` ->
``NotificationWorker.handle``) used to route every payload to the real
Discord API whenever ``DISCORD_BOT_TOKEN`` + ``DISCORD_TEST_CHANNEL_ID``
+ ``RUN_REAL_DISCORD_TEST=true`` were set in its container. During the
Step 31R pilot this caused 128 internal events to land on the test
channel in one hour ("autospam"). Stage 32 fixed the per-endpoint guard
on ``/discord/real/test-message`` but never reached the stream-consumer
path.

This module is the canonical policy: given a stream payload, the worker
calls :func:`classify_real_delivery` to decide whether the event may be
sent to the real Discord channel, or simulated like before.

Defaults (denylist beats allowlist):

* ``simulated`` -- when real mode is disabled (sandbox).
* ``real_blocked``/``skipped`` -- real mode is enabled but the event
  isn't in the allowlist, hits the denylist, lacks a real_delivery
  marker, or targets the wrong channel.
* ``real_allowed`` -- explicit opt-in via allowlist OR per-event
  ``metadata.real_delivery`` / ``payload.real_delivery`` markers AND
  the event is not denied.

The module is pure: no I/O, no env mutation, no audit publish. It is
the cheapest possible thing to unit-test, replay in audit, and inspect
through ``/operations/safety`` + ``/operations/real-integrations``.
The result never contains a token value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_REAL_DELIVERY_ALLOWLIST: tuple[str, ...] = (
    "discord.real_test_sent",
    "discord.real_task_received",
)

DEFAULT_REAL_DELIVERY_DENYLIST: tuple[str, ...] = (
    "workflow.*",
    "qa.*",
    "code.*",
    "github.*",
    "task.*",
    "llm.*",
    "approval.*",
    "audit.*",
    "incident.*",
    "retry.*",
    # Stage 36 -- backup / restore / DR drill events are operator
    # internals and must NEVER land on a real Discord channel by
    # default. An operator who wants them externalised must add a
    # specific event_type to the allowlist.
    "backup.*",
    "restore_drill.*",
    # Stage 38 -- routing decisions land on ``llm.routing_*``; they
    # are already covered by the broader ``llm.*`` pattern above.
    # Listed here as documentation only.
    # Stage 41 -- verification environment + regression runner events are
    # operator-internal and must NEVER land on a real Discord channel.
    "verification.*",
    # Stage 45 -- project planner / task graph events are operator-internal
    # and must NEVER land on a real Discord channel by default.
    "project.*",
    # Stage 46 -- agent discussion + design review events are operator-internal
    # and must NEVER land on a real Discord channel by default.
    "discussion.*",
    "design_review.*",
    # Stage 47 -- controlled workspace operator events are operator-internal
    # and must NEVER land on a real Discord channel by default.
    "workspace.*",
    "codegen.*",
    # Stage 48 -- mini delivery pilot events are operator-internal and must
    # NEVER land on a real Discord channel by default.
    "delivery_pilot.*",
    "acceptance.*",
    "qa_evidence.*",
)

DELIVERY_DECISION_SIMULATED = "simulated"
DELIVERY_DECISION_REAL_ALLOWED = "real_allowed"
DELIVERY_DECISION_REAL_BLOCKED = "real_blocked"
DELIVERY_DECISION_SKIPPED = "skipped"
DELIVERY_DECISION_FAILED = "failed"

REASON_REAL_MODE_DISABLED = "real_mode_disabled"
REASON_MISSING_MARKER = "missing_real_delivery_marker"
REASON_EVENT_NOT_ALLOWED = "event_type_not_allowed"
REASON_EVENT_DENIED = "event_type_denied"
REASON_WRONG_CHANNEL = "wrong_channel"
REASON_PRODUCTION_EXECUTED = "production_executed_not_false"
REASON_TOKEN_MISSING = "token_missing"


def _split_env_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return _split_env_list(value)
    return []


def _matches_pattern(event_type: str, pattern: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern == event_type:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-1]  # keep trailing dot
        return event_type.startswith(prefix)
    if pattern.endswith("*"):
        return event_type.startswith(pattern[:-1])
    return False


def _list_match(event_type: str, patterns: list[str]) -> bool:
    return any(_matches_pattern(event_type, pat) for pat in patterns)


@dataclass
class RealDeliveryPolicy:
    """Per-worker policy snapshot. Built once from env at startup.

    Knobs (all env-backed, all optional except ``real_mode_enabled``):

    * ``real_mode_enabled`` -- equivalent to ``client.can_deliver()``.
      When false every event resolves to ``simulated``.
    * ``allowlist`` / ``denylist`` -- event_type patterns. Denylist
      strictly wins; an event matching both is blocked.
    * ``allow_marker`` -- when true, an event without a matching
      allowlist entry can still be promoted to real if it carries
      ``metadata.real_delivery=true`` or ``real_delivery=true`` at the
      top level. Denylist still wins.
    * ``test_channel_id`` -- mirror of ``DISCORD_TEST_CHANNEL_ID`` used
      only to surface the configured target on /status; no payload may
      override it.
    """

    real_mode_enabled: bool
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    allow_marker: bool = True
    test_channel_id: str = ""

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "real_mode_enabled": self.real_mode_enabled,
            "allowlist": list(self.allowlist),
            "denylist": list(self.denylist),
            "allow_marker": self.allow_marker,
            "test_channel_id_configured": bool(self.test_channel_id),
        }


def load_policy_from_env(
    env: dict[str, str] | None = None,
    *,
    real_mode_enabled: bool | None = None,
) -> RealDeliveryPolicy:
    """Read the policy from env. Never reads a token value."""
    source = env if env is not None else os.environ
    allowlist_env = source.get("REAL_DISCORD_ALLOWLIST", "")
    denylist_env = source.get("REAL_DISCORD_DENYLIST", "")
    marker_env = source.get("REAL_DISCORD_ALLOW_MARKER", "true").strip().lower()
    test_channel = (source.get("DISCORD_TEST_CHANNEL_ID", "") or "").strip()

    allowlist = _split_env_list(allowlist_env) or list(DEFAULT_REAL_DELIVERY_ALLOWLIST)
    denylist = _split_env_list(denylist_env) or list(DEFAULT_REAL_DELIVERY_DENYLIST)
    allow_marker = marker_env != "false"

    if real_mode_enabled is None:
        token_present = bool((source.get("DISCORD_BOT_TOKEN", "") or "").strip())
        opt_in = (source.get("RUN_REAL_DISCORD_TEST", "false") or "false").strip().lower() == "true"
        real_mode_enabled = bool(token_present and test_channel and opt_in)

    return RealDeliveryPolicy(
        real_mode_enabled=bool(real_mode_enabled),
        allowlist=allowlist,
        denylist=denylist,
        allow_marker=allow_marker,
        test_channel_id=test_channel,
    )


@dataclass
class RealDeliveryDecision:
    decision: str
    reason: str = ""
    event_type: str = ""
    target_channel: str = ""
    sandbox: bool = True
    external_sent: bool = False

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "delivery_decision": self.decision,
            "blocked_reason": self.reason,
            "event_type": self.event_type,
            "sandbox": self.sandbox,
            "external_sent": self.external_sent,
            "target_channel": self.target_channel,
        }


def _has_marker(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("real_delivery") is True:
        return True
    return payload.get("real_delivery") is True


def _production_executed_is_false(payload: dict[str, Any]) -> bool:
    """``production_executed`` MUST be the literal ``False`` if present.

    Missing/None is treated as "not asserted" and we default to False so
    legacy producers don't fail the gate. An explicit ``True`` blocks.
    """
    metadata = payload.get("metadata")
    candidates: list[Any] = []
    if isinstance(metadata, dict) and "production_executed" in metadata:
        candidates.append(metadata.get("production_executed"))
    if "production_executed" in payload:
        candidates.append(payload.get("production_executed"))
    for value in candidates:
        if value is True:
            return False
        if isinstance(value, str) and value.strip().lower() == "true":
            return False
    return True


def classify_real_delivery(
    payload: dict[str, Any],
    policy: RealDeliveryPolicy,
) -> RealDeliveryDecision:
    """Decide what to do with one stream.notifications payload.

    Order of checks (first match wins):

    1. sandbox mode -> simulated
    2. token missing in policy -> skipped
    3. denylist match -> real_blocked
    4. allowlist OR (allow_marker AND real_delivery marker) -> proceed
       to channel + production_executed checks
    5. otherwise -> real_blocked with ``missing_real_delivery_marker``
       or ``event_type_not_allowed``
    """
    event_type = str(payload.get("event_type") or payload.get("event") or "").strip()

    if not policy.real_mode_enabled:
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_SIMULATED,
            reason=REASON_REAL_MODE_DISABLED,
            event_type=event_type,
            sandbox=True,
            external_sent=False,
            target_channel="sandbox-channel",
        )

    if not policy.test_channel_id:
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_SKIPPED,
            reason=REASON_TOKEN_MISSING,
            event_type=event_type,
            sandbox=True,
            external_sent=False,
            target_channel="sandbox-channel",
        )

    target_channel_raw = payload.get("target_channel") or payload.get("channel_id") or ""
    target_channel = (str(target_channel_raw) or "").strip()
    if target_channel and target_channel != policy.test_channel_id:
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_REAL_BLOCKED,
            reason=REASON_WRONG_CHANNEL,
            event_type=event_type,
            sandbox=False,
            external_sent=False,
            target_channel=policy.test_channel_id,
        )

    if not _production_executed_is_false(payload):
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_REAL_BLOCKED,
            reason=REASON_PRODUCTION_EXECUTED,
            event_type=event_type,
            sandbox=False,
            external_sent=False,
            target_channel=policy.test_channel_id,
        )

    if _list_match(event_type, policy.denylist):
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_REAL_BLOCKED,
            reason=REASON_EVENT_DENIED,
            event_type=event_type,
            sandbox=False,
            external_sent=False,
            target_channel=policy.test_channel_id,
        )

    in_allowlist = _list_match(event_type, policy.allowlist)
    marker_set = policy.allow_marker and _has_marker(payload)

    if in_allowlist or marker_set:
        return RealDeliveryDecision(
            decision=DELIVERY_DECISION_REAL_ALLOWED,
            event_type=event_type,
            sandbox=False,
            external_sent=False,
            target_channel=policy.test_channel_id,
        )

    reason = REASON_MISSING_MARKER if policy.allow_marker else REASON_EVENT_NOT_ALLOWED
    return RealDeliveryDecision(
        decision=DELIVERY_DECISION_REAL_BLOCKED,
        reason=reason,
        event_type=event_type,
        sandbox=False,
        external_sent=False,
        target_channel=policy.test_channel_id,
    )


__all__ = [
    "DEFAULT_REAL_DELIVERY_ALLOWLIST",
    "DEFAULT_REAL_DELIVERY_DENYLIST",
    "DELIVERY_DECISION_SIMULATED",
    "DELIVERY_DECISION_REAL_ALLOWED",
    "DELIVERY_DECISION_REAL_BLOCKED",
    "DELIVERY_DECISION_SKIPPED",
    "DELIVERY_DECISION_FAILED",
    "REASON_REAL_MODE_DISABLED",
    "REASON_MISSING_MARKER",
    "REASON_EVENT_NOT_ALLOWED",
    "REASON_EVENT_DENIED",
    "REASON_WRONG_CHANNEL",
    "REASON_PRODUCTION_EXECUTED",
    "REASON_TOKEN_MISSING",
    "RealDeliveryPolicy",
    "RealDeliveryDecision",
    "classify_real_delivery",
    "load_policy_from_env",
]
