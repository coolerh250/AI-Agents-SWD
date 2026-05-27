"""Normalize heterogeneous stream.audit events into a single audit_logs row shape.

The platform has multiple producers that publish audit events to
``stream.audit``:

* ``StreamAgent`` -> writes ``AuditEvent.model_dump(mode='json')`` (no ``event``
  field; carries ``agent`` / ``decision_type`` / ``summary`` / ``result`` /
  ``artifact_refs`` / ``created_at``).
* ``audit-service`` echoes every ``POST /audit/events`` back on the stream as
  ``{"event": "audit.recorded", ...}``. The worker MUST skip these or it would
  create a circular write-loop.
* ``devops-agent`` (Stage 19+) publishes ``github_pr_integration`` directly on
  stream.audit so it no longer needs the direct HTTP path.
* ``retry-scheduler`` (Stage 19+) publishes ``workflow_failed`` the same way.
* ``github-automation`` (Stage 19+) publishes ``github_automation`` the same way.
* Generic stream events may arrive with ``event`` / ``event_type`` keys and
  nested payload dicts (e.g. ``{"event": "x", "payload": {...}}``) or a JSON
  string payload.

The normalizer produces a dict the AuditStore can insert into ``audit_logs``:

``{task_id, agent, decision_type, summary, result, artifact_refs, created_at}``

Fallbacks:
* ``agent`` -> ``unknown`` when not derivable.
* ``decision_type`` -> ``event_type`` -> ``event`` -> ``unknown``.
* ``result`` -> ``recorded`` (best-effort; the agent has already taken its
  decision by the time we persist).
* ``summary`` -> never empty; falls back to the decision_type when absent.
* ``created_at`` -> uses the source event's value if present, else ``now``.
* ``artifact_refs`` -> always a dict; preserves the original event for
  forensic replay under ``original_event``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# Decision_type / event values that mean "audit-service already persisted this
# row; do not re-insert it" — skipping these prevents a circular write loop.
AUDIT_RECORDED_EVENTS = frozenset(
    {
        "audit.recorded",
        "audit_recorded",
    }
)
AUDIT_RECORDED_DECISION_TYPES = frozenset({"audit_recorded"})
AUDIT_SERVICE_NAMES = frozenset({"audit-service"})


def _as_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` unchanged when it is a dict; otherwise return ``{}``."""
    return value if isinstance(value, dict) else {}


def _coerce_payload(payload: Any) -> dict[str, Any]:
    """Accept dicts or JSON-string payloads; everything else becomes ``{}``."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_created_at(value: Any) -> str:
    """Best-effort normalize a created_at value to an ISO-8601 string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _utcnow_iso()


def _pick(*candidates: Any) -> str:
    """Return the first non-empty string from a series of candidates."""
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return ""


def is_audit_recorded_echo(event: dict[str, Any]) -> bool:
    """Detect the ``audit.recorded`` echo audit-service publishes after a write.

    The audit-service POST handler publishes ``{"event": "audit.recorded", ...}``
    on stream.audit so other components can observe persistence. The audit-worker
    MUST NOT re-persist that envelope or it would create one new audit_logs row
    for every row already written (and trigger an infinite cascade).
    """
    if not isinstance(event, dict):
        return False
    event_value = str(event.get("event") or "").strip().lower()
    event_type = str(event.get("event_type") or "").strip().lower()
    decision_type = str(event.get("decision_type") or "").strip().lower()
    agent = str(event.get("agent") or "").strip().lower()
    source = str(event.get("source") or "").strip().lower()
    service = str(event.get("service") or "").strip().lower()
    if event_value in AUDIT_RECORDED_EVENTS or event_type in AUDIT_RECORDED_EVENTS:
        return True
    if decision_type in AUDIT_RECORDED_DECISION_TYPES:
        return True
    # An explicit identity match — audit-service self-tagging itself as the
    # author. We don't broadly skip everything tagged audit-service because a
    # human could push a row via that name; instead we require the row to look
    # like an echo (carry an audit_id field the audit-service handler emits).
    if agent in AUDIT_SERVICE_NAMES and event.get("audit_id"):
        return True
    if (source in AUDIT_SERVICE_NAMES or service in AUDIT_SERVICE_NAMES) and event.get("audit_id"):
        return True
    return False


def _merge_nested_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Merge a single level of nested ``payload`` / ``data`` into the event.

    Some publishers wrap the audit dict under ``payload`` (e.g. the workflow
    event consumers) or under ``data`` (string-encoded). We surface those
    fields so the normalizer can read agent / decision_type from the same
    flat dict regardless of who published it.
    """
    merged: dict[str, Any] = dict(event)
    for key in ("payload", "data"):
        nested = _coerce_payload(event.get(key))
        if not nested:
            continue
        for k, v in nested.items():
            if k not in merged or merged.get(k) in (None, ""):
                merged[k] = v
    return merged


def normalize_audit_event(
    event: dict[str, Any],
    *,
    source_message_id: str = "",
    source_stream: str = "stream.audit",
) -> dict[str, Any]:
    """Normalize one stream.audit event into an audit_logs-ready dict.

    Returns the persisted shape:

    ``{task_id, agent, decision_type, summary, result, artifact_refs,
       created_at}``

    ``artifact_refs`` is enriched with the source provenance so an operator can
    correlate the row back to its Redis message — ``source_message_id``,
    ``source_stream``, ``normalized_by``, and (when meaningfully different)
    ``original_event``.
    """
    raw = event if isinstance(event, dict) else {}
    merged = _merge_nested_payload(raw)

    event_name = _pick(merged.get("event"), merged.get("event_type"))
    decision_type = _pick(
        merged.get("decision_type"),
        event_name,
        "unknown",
    )
    agent = _pick(merged.get("agent"), merged.get("source"), merged.get("service"), "unknown")
    task_id = _pick(
        merged.get("task_id"),
        merged.get("workflow_id"),
        merged.get("incident_id"),
        "unknown",
    )
    summary = _pick(
        merged.get("summary"),
        merged.get("message"),
        decision_type,
    )
    result = _pick(merged.get("result"), merged.get("status"), "recorded")
    created_at = _normalize_created_at(
        merged.get("created_at") or merged.get("timestamp") or merged.get("failed_at")
    )
    artifact_refs = _as_dict(merged.get("artifact_refs"))
    # Provenance — never overwritten by the producer; allows dedup and forensic
    # replay from the worker's perspective.
    artifact_refs = dict(artifact_refs)
    artifact_refs.setdefault("source_message_id", source_message_id)
    artifact_refs.setdefault("source_stream", source_stream)
    artifact_refs.setdefault("normalized_by", "audit-worker")
    # Preserve the verbatim envelope when the producer didn't already supply it.
    # We only carry the raw envelope when it isn't the trivial echo we just
    # consumed (keeps row size sane for the common path).
    if "original_event" not in artifact_refs:
        artifact_refs["original_event"] = raw

    return {
        "task_id": task_id,
        "agent": agent,
        "decision_type": decision_type,
        "summary": summary,
        "result": result,
        "artifact_refs": artifact_refs,
        "created_at": created_at,
    }
