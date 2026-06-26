"""Step 58 -- operational metrics freshness helpers.

Computes availability + age for runtime report files. Missing files are explicitly
unavailable / stale -- never reported as clean.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# A report older than this is flagged stale (visibility hint only, not an SLA).
STALE_AFTER_SECONDS = 24 * 3600


def file_freshness(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"available": False, "fresh": False, "age_seconds": None, "reason": "missing"}
    age = time.time() - path.stat().st_mtime
    return {
        "available": True,
        "fresh": age <= STALE_AFTER_SECONDS,
        "age_seconds": int(age),
        "reason": "ok" if age <= STALE_AFTER_SECONDS else "stale",
    }


def load_json_if_fresh(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return (data_or_None, freshness). Data is returned even if stale (caller decides)."""
    fr = file_freshness(path)
    if not fr["available"]:
        return None, fr
    try:
        return json.loads(path.read_text(encoding="utf-8")), fr
    except (OSError, ValueError):
        return None, {
            "available": False,
            "fresh": False,
            "age_seconds": None,
            "reason": "unreadable",
        }
