"""Deterministic canonicalisation of an audit_logs row.

The canonical payload is what we hash. It is built from the public,
business-meaning columns of ``audit_logs`` and intentionally excludes
volatile / integrity-only fields:

* ``id`` is included as ``audit_log_id`` -- the canonical record is
  pinned to a specific row.
* ``actor`` is omitted (not currently set by the Stage 19 writer; will
  be added when surfaced).
* ``created_at`` is included as an ISO-8601 UTC string with seconds
  precision so a re-read of the row produces the same string the
  writer used.
* ``artifact_refs`` is serialised via ``canonical_json`` so dict key
  order does not influence the hash.

Nothing in the canonical payload is a secret. The payload is intended
to be human-inspectable -- it is exactly the information an operator
needs to confirm the row was not tampered with.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

CANONICAL_FIELDS = (
    "audit_log_id",
    "task_id",
    "agent",
    "decision_type",
    "summary",
    "result",
    "artifact_refs",
    "created_at",
)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_created_at(value: Any) -> str:
    """Normalise a created_at value to UTC ISO-8601 with microseconds.

    Accepts ``datetime`` or ``str``. A naive datetime is treated as UTC.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _canonicalise_value(value: Any) -> Any:
    """Recursively normalise dicts (sorted keys) and lists."""
    if isinstance(value, dict):
        return {k: _canonicalise_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        return [_canonicalise_value(v) for v in value]
    return value


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialise ``payload`` to a deterministic JSON string.

    * dict keys are sorted (recursively),
    * separators omit incidental whitespace,
    * ``ensure_ascii=False`` so unicode is preserved without escapes,
    * floats / ints / bools / strings use the standard JSON encoding,
    * timestamps are expected to already be ISO strings.
    """
    return json.dumps(
        _canonicalise_value(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_canonical_payload(audit_log_row: dict[str, Any]) -> dict[str, Any]:
    """Project an ``audit_logs`` row into the canonical payload shape.

    Accepts both the worker's ``write_audit_log`` return dict
    (``audit_id`` / ``artifact_refs`` already parsed) and a raw asyncpg
    row mapped via ``dict()`` (``id`` instead of ``audit_id``,
    ``artifact_refs`` possibly still a JSON string).
    """
    audit_log_id = audit_log_row.get("audit_log_id") or audit_log_row.get("audit_id")
    if not audit_log_id:
        audit_log_id = audit_log_row.get("id")
    refs_raw = audit_log_row.get("artifact_refs") or {}
    if isinstance(refs_raw, str):
        try:
            refs = json.loads(refs_raw)
        except (TypeError, ValueError):
            refs = {}
    elif isinstance(refs_raw, dict):
        refs = refs_raw
    else:
        refs = {}
    return {
        "audit_log_id": _coerce_str(audit_log_id),
        "task_id": _coerce_str(audit_log_row.get("task_id")),
        "agent": _coerce_str(audit_log_row.get("agent")),
        "decision_type": _coerce_str(audit_log_row.get("decision_type")),
        "summary": _coerce_str(audit_log_row.get("summary")),
        "result": _coerce_str(audit_log_row.get("result")),
        "artifact_refs": _canonicalise_value(refs),
        "created_at": _coerce_created_at(audit_log_row.get("created_at")),
    }


__all__ = [
    "CANONICAL_FIELDS",
    "build_canonical_payload",
    "canonical_json",
]
