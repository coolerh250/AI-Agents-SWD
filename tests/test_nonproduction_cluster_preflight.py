"""Step 55 -- non-production cluster preflight."""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.lib.nonprod_cluster_detect import detect_cluster

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-cluster-smoke-plan.yaml"


def _plan() -> dict:
    return (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {})["nonProductionRuntimeSmoke"]


def test_plan_present_and_non_production() -> None:
    p = _plan()
    assert p["productionReady"] is False
    assert p["productionExecuted"] is False
    assert p["requiresSafeCluster"] is True


def test_plan_forbids_production_actions() -> None:
    forbidden = set(_plan()["forbiddenActions"])
    for must in (
        "production_deploy",
        "argocd_sync",
        "github_write",
        "image_push",
        "public_ingress",
    ):
        assert must in forbidden


def test_detect_cluster_returns_safe_tuple() -> None:
    available, safe, reason = detect_cluster()
    assert isinstance(available, bool) and isinstance(safe, bool)
    assert isinstance(reason, str) and reason
    # No kubeconfig/token/context name leaks through the reason token.
    assert "BEGIN" not in reason and "token" not in reason.lower()
