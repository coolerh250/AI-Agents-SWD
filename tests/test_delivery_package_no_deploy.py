"""Stage 49 -- delivery package build never deploys or executes production."""

from __future__ import annotations

from delivery_package_fakes import build_fake_package


async def test_no_deploy_no_production(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    assert result.deployment_performed is False
    assert result.production_executed is False
    assert result.real_llm_used is False
    assert result.external_delivery_performed is False

    report = await stores["package"].get_delivery_package_report(result.package_id)
    assert report["deployment_performed"] is False
    assert report["production_executed"] is False
    assert report["real_llm_used"] is False
    assert report["external_delivery_performed"] is False

    checks = await stores["package"].get_gate_check_results(result.package_id)
    by_key = {c["check_key"]: c for c in checks}
    assert by_key["no_deploy"]["status"] == "passed"
    assert by_key["no_production_execution"]["status"] == "passed"
