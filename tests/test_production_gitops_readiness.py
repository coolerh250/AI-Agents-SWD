"""Step 63A -- production GitOps readiness."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_no_gitops_side_effects() -> None:
    g = loaders.load("gitops")
    assert g.get("nonprodArgocdIsProductionReady") is False
    assert g.get("creates_production_argocd_app") is False
    assert g.get("triggers_sync") is False
    assert g.get("applies_manifest") is False


def test_gitops_items_missing() -> None:
    assert len(loaders.missing_gitops_items()) == 5
