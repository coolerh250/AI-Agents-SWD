"""Stage 48 -- the pilot never deploys / executes production."""

from __future__ import annotations

from mini_delivery_fakes import run_fake_pilot


async def test_no_deploy_no_production(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    assert result.deployment_performed is False
    assert result.production_executed is False
    assert result.real_llm_used is False
    safety = await stores["pilot"].get_safety_report(result.pilot_id)
    assert safety["deployment_performed"] is False
    assert safety["real_llm_used"] is False
    assert safety["real_external_delivery_performed"] is False
    assert safety["production_executed_count"] == 0
