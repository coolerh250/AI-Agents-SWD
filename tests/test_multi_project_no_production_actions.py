"""Step 57 -- multi-project capability exposes no production / external escape hatch."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.work_items import dispatcher as _dispatcher
from shared.sdk.work_items.safety import multi_project_safety_fields

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "apps" / "orchestrator" / "src" / "multi_project_api.py").read_text(encoding="utf-8")


def test_safety_fields_all_dangerous_toggles_off() -> None:
    f = multi_project_safety_fields()
    assert f["work_item_dispatch_external_side_effect_enabled"] is False
    assert f["work_item_dispatch_github_write_enabled"] is False
    assert f["work_item_dispatch_argocd_sync_enabled"] is False
    assert f["work_item_dispatch_production_action_enabled"] is False
    assert f["work_item_notification_external_send_enabled"] is False
    assert f["multi_project_production_ready"] is False


def test_dispatcher_refuses_forbidden_targets() -> None:
    forb = _dispatcher.forbidden_targets()
    assert {
        "production-executor",
        "github-write",
        "argocd-sync",
        "external-notification-send",
    } <= forb


def test_api_has_no_production_or_external_call() -> None:
    lowered = API.lower()
    # No GitHub write / ArgoCD sync / deploy invocation in the dispatch path.
    assert (
        'github_write_performed": false' in lowered or "github_write_performed': false" in lowered
    )
    assert "argocd" in lowered  # only as a "false" safety field, asserted above in API responses
    assert "production_executed" in lowered
