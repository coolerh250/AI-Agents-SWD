"""Step 51.4 -- runtime baseline SDK model shape."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.runtime_baseline import (
    RUNTIME_BASELINE_MARKERS,
    collect_runtime_baseline,
)

ROOT = Path(__file__).resolve().parents[1]


def test_marker_set_complete() -> None:
    assert len(RUNTIME_BASELINE_MARKERS) == 27
    for m in (
        "KUBERNETES_RUNTIME_INVENTORY_VERIFY",
        "GITOPS_ARGOCD_BASELINE_VERIFY",
        "RUNTIME_OPERATIONS_VISIBILITY_VERIFY",
        "ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY",
        "RUNTIME_SAFETY_FIELDS_VERIFY",
        "KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY",
    ):
        assert m in RUNTIME_BASELINE_MARKERS


def test_collect_has_required_keys() -> None:
    s = collect_runtime_baseline(ROOT)
    for k in (
        "status",
        "clusterConnected",
        "areaStatus",
        "markerSummary",
        "productionSafety",
        "safetyFacts",
        "environments",
        "limitations",
        "nextRequiredSteps",
    ):
        assert k in s, k


def test_status_enum_valid() -> None:
    s = collect_runtime_baseline(ROOT)
    assert s["status"] in (
        "validated_not_deployed",
        "passed_with_non_production_limitations",
        "failed",
        "unknown",
    )
    assert s["status"] != "production_ready"
