"""Step 63A -- production credential readiness."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_no_credential_value_handling() -> None:
    c = loaders.load("credentials")
    assert c.get("reads_credential_values") is False
    assert c.get("creates_credentials") is False
    assert c.get("exposes_secret") is False


def test_references_carry_only_name_and_configured() -> None:
    for ref in loaders.load("credentials").get("references", []):
        assert set(ref.keys()) == {"name", "configured"}


def test_credentials_missing() -> None:
    assert len(loaders.missing_credential_refs()) == 5
