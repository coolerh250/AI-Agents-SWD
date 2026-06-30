"""Step 62 -- production environment prerequisites."""

from __future__ import annotations

from shared.sdk.production_readiness import prerequisites


def test_production_environment_not_claimed() -> None:
    assert prerequisites.production_environment_exists() is False


def test_prerequisites_missing_this_stage() -> None:
    missing = prerequisites.missing_prerequisites()
    assert len(missing) == 12
    for n in (
        "production_cluster_identified",
        "production_argocd_application_defined",
        "production_approval_channel_configured",
    ):
        assert n in missing
