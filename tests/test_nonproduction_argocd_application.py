"""Step 56 -- non-production ArgoCD Application manifest."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "gitops" / "nonproduction" / "aiagents-smoke-application.yaml"


def _app() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def test_manual_sync_only() -> None:
    spec = _app()["spec"]
    sync = spec.get("syncPolicy", {}) or {}
    # No automated block => no auto-sync / prune / self-heal.
    assert "automated" not in sync
    assert "CreateNamespace=true" not in (sync.get("syncOptions") or [])


def test_targets_non_production_namespace() -> None:
    app = _app()
    spec = app["spec"]
    assert app["kind"] == "Application"
    assert app["metadata"]["namespace"] == "argocd-nonprod"
    assert spec["project"] == "aiagents-nonprod"
    assert spec["destination"]["namespace"] == "aiagents-smoke-dev"


def test_source_non_production_smoke_values() -> None:
    src = _app()["spec"]["source"]
    assert "*" not in src["repoURL"]
    assert "charts/ai-agents-platform" in src["path"]
    assert any("nonprod" in v for v in src["helm"]["valueFiles"])
    blob = MANIFEST.read_text(encoding="utf-8")
    assert "namespace: production" not in blob
    assert "values-prod" not in blob
