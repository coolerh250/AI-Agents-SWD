"""Step 56 -- non-production ArgoCD exposes no production/mutation escape hatch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_nonproduction_argocd_manual_sync.sh"
API = ROOT / "apps" / "orchestrator" / "src" / "gitops_argocd_api.py"


def test_runner_refuses_production_and_auto_sync() -> None:
    src = RUNNER.read_text(encoding="utf-8")
    # Refuses production-like context / namespace.
    assert "looks production" in src
    assert "forbidden namespace" in src
    # Refuses an Application configured with auto-sync.
    assert "must be manual-only" in src
    # Never creates Ingress / LoadBalancer / exposes the server.
    assert "ingress present" in src.lower() or "ingress" in src.lower()
    assert "ClusterIP" in src


def test_api_has_no_mutation_surface() -> None:
    src = API.read_text(encoding="utf-8")
    assert "@router.post" not in src
    assert "@router.delete" not in src
    assert "@router.put" not in src
    assert "@router.patch" not in src
