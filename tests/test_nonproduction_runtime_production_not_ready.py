"""Step 55 -- nothing in the runtime smoke layer claims production readiness."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.runtime_smoke import nonprod_runtime_safety_fields, readiness_view

ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "infra" / "kubernetes"

PLAN_FILES = [
    ("nonproduction-cluster-smoke-plan.yaml", "nonProductionRuntimeSmoke"),
    ("nonproduction-namespace-plan.yaml", "nonProductionNamespacePlan"),
    ("nonproduction-runtime-smoke-report-schema.yaml", "nonProductionRuntimeSmokeReportSchema"),
]


def test_all_plans_production_ready_false() -> None:
    for name, key in PLAN_FILES:
        data = yaml.safe_load((K8S / name).read_text(encoding="utf-8")) or {}
        assert data[key]["productionReady"] is False, name


def test_safety_and_readiness_not_production_ready() -> None:
    f = nonprod_runtime_safety_fields(ROOT)
    assert f["nonprod_runtime_smoke_production_ready"] is False
    assert f["kubernetes_production_deploy_performed"] is False
    assert f["argocd_sync_performed"] is False
    assert readiness_view()["productionReady"] is False
