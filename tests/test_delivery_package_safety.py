"""Stage 49 -- delivery package controlled-only safety flags."""

from __future__ import annotations

from shared.sdk.delivery_package.safety import delivery_package_safety_flags


def test_default_controlled_only_posture() -> None:
    flags = delivery_package_safety_flags(env={})
    assert flags["delivery_package_enabled"] is True
    assert flags["delivery_package_controlled_only"] is True
    assert flags["delivery_package_real_llm_enabled"] is False
    assert flags["delivery_package_github_write_enabled"] is False
    assert flags["delivery_package_pr_creation_enabled"] is False
    assert flags["delivery_package_deploy_enabled"] is False
    assert flags["delivery_package_external_delivery_enabled"] is False
    assert flags["delivery_package_auto_accept_enabled"] is False
    assert flags["delivery_package_operator_actions_enabled"] is False


def test_flags_respect_env_override() -> None:
    flags = delivery_package_safety_flags(env={"ENABLE_DELIVERY_PACKAGE_REAL_LLM": "true"})
    assert flags["delivery_package_real_llm_enabled"] is True
