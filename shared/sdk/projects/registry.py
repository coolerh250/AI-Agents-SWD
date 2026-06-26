"""Step 57 -- project registry rules (deterministic; no DB).

Deterministic project_key generation + dispatch guards. No production action.
"""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def project_key_from_name(name: str, *, suffix: str = "") -> str:
    """Deterministic, URL-safe project key from a name (uppercased slug)."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    base = "-".join(slug.split("-")[:4]) or "project"
    key = f"PRJ-{base}"
    if suffix:
        key = f"{key}-{suffix}"
    return key.upper()


def can_dispatch_new_work_item(registry_status: str) -> bool:
    """Archived/completed projects cannot dispatch new work items."""
    return registry_status == "active"


def can_auto_dispatch(registry_status: str) -> bool:
    """Paused projects cannot auto-dispatch."""
    return registry_status == "active"


def can_add_active_work_item(registry_status: str) -> bool:
    """Completed/archived projects cannot add active work items."""
    return registry_status in ("active", "paused")


def production_allowed_default() -> bool:
    return False
