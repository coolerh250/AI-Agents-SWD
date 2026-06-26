"""Step 57 -- multi-project / work-item dispatch safety fields.

Derived from the committed dispatch + notification policies (no DB, no cluster).
The dangerous side-effect toggles read straight from the policy so they cannot
silently drift true.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DISPATCH_YAML = ROOT / "infra" / "delivery" / "work-item-dispatch-policy.yaml"
NOTIFY_YAML = ROOT / "infra" / "delivery" / "project-notification-model.yaml"


@lru_cache(maxsize=1)
def _dispatch_side_effects() -> dict[str, Any]:
    data = yaml.safe_load(DISPATCH_YAML.read_text(encoding="utf-8")) or {}
    return (data.get("workItemDispatchPolicy", {}) or {}).get("externalSideEffect", {})


@lru_cache(maxsize=1)
def _notify_external() -> bool:
    data = yaml.safe_load(NOTIFY_YAML.read_text(encoding="utf-8")) or {}
    return bool((data.get("projectNotificationModel", {}) or {}).get("externalSendEnabled", False))


def multi_project_safety_fields() -> dict[str, Any]:
    se = _dispatch_side_effects()
    any_external = any(
        bool(se.get(k, False))
        for k in ("githubWrite", "argocdSync", "externalNotificationSend", "productionAction")
    )
    return {
        "multi_project_enabled": True,
        "multi_project_write_api_enabled": True,
        "work_item_dispatch_enabled": True,
        "work_item_dispatch_external_side_effect_enabled": bool(any_external),
        "work_item_dispatch_github_write_enabled": bool(se.get("githubWrite", False)),
        "work_item_dispatch_argocd_sync_enabled": bool(se.get("argocdSync", False)),
        "work_item_dispatch_production_action_enabled": bool(se.get("productionAction", False)),
        "work_item_delivery_package_linkage_enabled": True,
        "work_item_project_audit_enabled": True,
        "work_item_notification_external_send_enabled": _notify_external(),
        "multi_project_production_ready": False,
    }
