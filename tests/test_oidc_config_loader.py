"""Step 52.2 -- OIDC config loader: parses files, reports disabled_unconfigured."""

from __future__ import annotations

from shared.sdk.identity import load_oidc_config


def test_loader_status_disabled_unconfigured() -> None:
    res = load_oidc_config()
    assert res.status == "disabled_unconfigured"
    assert res.errors == []


def test_loader_not_ready_not_production() -> None:
    res = load_oidc_config()
    assert res.ready is False
    assert res.production_enabled is False
    assert res.enabled is False


def test_loader_is_valid() -> None:
    assert load_oidc_config().is_valid is True
