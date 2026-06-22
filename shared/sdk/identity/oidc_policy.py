"""Step 52.2 -- OIDC safety policy catalog loader (read-only).

Reads the committed ``oidc-safety-policy-catalog.yaml`` so the verifiers and
tests can assert the disabled-by-default invariants are present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]

REQUIRED_POLICY_KEYS = (
    "oidc_must_be_disabled_until_configured",
    "no_oidc_secret_in_repo",
    "no_oidc_discovery_network_call_in_step_52_2",
    "no_jwks_fetch_in_step_52_2",
    "no_test_local_fallback_in_production",
    "unknown_user_must_deny",
    "frontend_role_claim_not_authoritative",
    "platform_admin_requires_explicit_mapping",
    "callback_disabled_until_token_validation_ready",
)


def load_oidc_policies(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or ROOT
    data = yaml.safe_load(
        (base / "infra" / "identity" / "oidc-safety-policy-catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    return list(data.get("policies", []))


def policy_keys(root: Path | None = None) -> set[str]:
    return {p["key"] for p in load_oidc_policies(root)}


__all__ = ["REQUIRED_POLICY_KEYS", "load_oidc_policies", "policy_keys"]
