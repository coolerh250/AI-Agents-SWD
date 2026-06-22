"""Step 52.2 -- OIDC safety policy catalog: required invariants present."""

from __future__ import annotations

from shared.sdk.identity import REQUIRED_POLICY_KEYS, load_oidc_policies, policy_keys


def test_all_required_policies_present() -> None:
    assert set(REQUIRED_POLICY_KEYS) <= policy_keys()


def test_critical_policies_marked_critical() -> None:
    by_key = {p["key"]: p for p in load_oidc_policies()}
    for key in (
        "oidc_must_be_disabled_until_configured",
        "no_oidc_secret_in_repo",
        "no_test_local_fallback_in_production",
        "unknown_user_must_deny",
        "callback_disabled_until_token_validation_ready",
    ):
        assert by_key[key]["severity"] == "critical"


def test_policies_have_statements() -> None:
    for p in load_oidc_policies():
        assert p.get("statement")
