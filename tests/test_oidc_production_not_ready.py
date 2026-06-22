"""Step 52.2 -- production OIDC is not ready; Step 52.1 posture maintained."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.identity import load_oidc_config
from shared.sdk.operator_actions.auth import resolve_auth_config

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"


def test_production_oidc_not_ready() -> None:
    res = load_oidc_config()
    assert res.ready is False
    assert res.production_enabled is False


def test_resolve_auth_config_default_fail_closed() -> None:
    # No env -> disabled mode, no production auth, no oidc, no operator actions.
    cfg = resolve_auth_config({})
    assert cfg.auth_mode == "disabled"
    assert cfg.production_auth_enabled is False
    assert cfg.oidc_enabled is False
    assert cfg.operator_actions_enabled is False


def test_oidc_enabled_env_does_not_enable_production_auth() -> None:
    # Turning the OIDC flag on must NOT grant a production auth path on its own.
    cfg = resolve_auth_config(
        {"ADMIN_CONSOLE_AUTH_MODE": "oidc", "ADMIN_CONSOLE_OIDC_ENABLED": "true"}
    )
    assert cfg.production_auth_enabled is False
    assert cfg.operator_actions_enabled is False


def test_step_52_1_prerequisites_still_unconfigured() -> None:
    oidc = yaml.safe_load(
        (IDENT / "production-oidc-prerequisites.yaml").read_text(encoding="utf-8")
    )
    prov = oidc["oidcPrerequisites"]["provider"]
    assert all(
        prov[k]["configured"] is False
        for k in ("issuerUrl", "jwksUri", "clientId", "clientSecret", "redirectUris")
    )
