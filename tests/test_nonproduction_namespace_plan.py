"""Step 55 -- non-production namespace plan."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-namespace-plan.yaml"


def _plan() -> dict:
    return (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {})["nonProductionNamespacePlan"]


def test_namespace_non_production() -> None:
    ns = _plan()["namespace"]
    assert ns.startswith("aiagents-smoke")
    assert "prod" not in ns.lower()


def test_labels_mark_non_production() -> None:
    labels = _plan()["labels"]
    assert labels["aiagents.openai.local/environment"] == "non-production"
    assert labels["aiagents.openai.local/production"] == "false"


def test_forbidden_namespaces_listed() -> None:
    forbidden = set(_plan()["forbiddenNamespaces"])
    assert {"default", "kube-system", "argocd", "production", "prod"} <= forbidden
