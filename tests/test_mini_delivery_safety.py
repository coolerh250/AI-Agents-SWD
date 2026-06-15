"""Stage 48 -- mini delivery pilot safety flags + controlled-only result."""

from __future__ import annotations

from mini_delivery_fakes import run_fake_pilot

from shared.sdk.mini_delivery_pilot.safety import mini_delivery_safety_flags


def test_default_flags_controlled_only(monkeypatch) -> None:
    for var in (
        "ENABLE_MINI_DELIVERY_REAL_LLM",
        "ENABLE_MINI_DELIVERY_GITHUB_WRITE",
        "ENABLE_MINI_DELIVERY_PR_CREATION",
        "ENABLE_MINI_DELIVERY_DEPLOY",
        "ENABLE_MINI_DELIVERY_EXTERNAL_DELIVERY",
    ):
        monkeypatch.delenv(var, raising=False)
    flags = mini_delivery_safety_flags()
    assert flags["mini_delivery_pilot_controlled_only"] is True
    assert flags["mini_delivery_real_llm_enabled"] is False
    assert flags["mini_delivery_github_write_enabled"] is False
    assert flags["mini_delivery_pr_creation_enabled"] is False
    assert flags["mini_delivery_deploy_enabled"] is False
    assert flags["mini_delivery_external_delivery_enabled"] is False


async def test_pilot_result_is_controlled_only(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    assert result.controlled_only is True
    assert result.production_executed is False
    safety = await stores["pilot"].get_safety_report(result.pilot_id)
    assert safety["status"] == "safe"
    assert safety["production_executed_count"] == 0
    assert safety["github_write_performed"] is False
    assert safety["pr_created"] is False
    assert safety["deployment_performed"] is False
    assert safety["real_llm_used"] is False
    assert safety["repo_root_modified"] is False
    assert safety["chain_of_thought_persisted"] is False
