"""Step 63A -- production target assessment."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_production_target_not_faked() -> None:
    t = loaders.load("target")
    assert t.get("productionTargetExists") is False
    assert t.get("kindNonprodIsProductionCluster") is False
    assert t.get("nonprodArgocdIsProductionArgocd") is False


def test_target_items_missing() -> None:
    missing = loaders.missing_target_items()
    assert len(missing) == 9
    assert "production_cluster" in missing
    assert "production_argocd_app" in missing
