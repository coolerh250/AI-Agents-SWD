"""Stage 40 -- alert deduplication key computation.

dedupe_key = SHA-256(source + alert_name + fingerprint + sorted(labels))
A matching key on an open/acknowledged/investigating incident → link the
alert rather than opening a new incident.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_dedupe_key(
    *,
    source: str,
    alert_name: str,
    fingerprint: str | None,
    labels: dict[str, Any] | None = None,
) -> str:
    """Return a stable hex digest used as the incident deduplication key."""
    canonical = json.dumps(
        {
            "source": str(source).strip(),
            "alert_name": str(alert_name).strip(),
            "fingerprint": str(fingerprint or "").strip(),
            "labels": dict(sorted((labels or {}).items())),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


_OPEN_STATUSES = frozenset({"open", "acknowledged", "investigating"})


def is_incident_open(status: str | None) -> bool:
    return (status or "").lower() in _OPEN_STATUSES


__all__ = ["compute_dedupe_key", "is_incident_open"]
