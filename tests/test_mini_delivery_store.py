"""Stage 48 -- mini delivery pilot store URL + full run-through (fakes)."""

from __future__ import annotations

import pytest
from mini_delivery_fakes import run_fake_pilot

from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotStore


def test_store_uses_default_url() -> None:
    assert MiniDeliveryPilotStore().database_url.startswith("postgresql://")


def test_store_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@y:5432/env-db")
    assert "env-db" in MiniDeliveryPilotStore().database_url


async def test_full_run_persists_into_fakes(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    pilot_store = stores["pilot"]
    qa = await pilot_store.get_qa_report(result.pilot_id)
    safety = await pilot_store.get_safety_report(result.pilot_id)
    acc = await pilot_store.get_acceptance_summary(result.pilot_id)
    timeline = await pilot_store.get_pilot_timeline(result.pilot_id)
    assert qa["status"] in ("passed", "passed_with_findings")
    assert safety["status"] == "safe"
    assert acc["total"] >= 8
    assert timeline["step_count"] >= 8
    assert timeline["production_executed"] is False
    latest = await pilot_store.get_latest_pilot(result.project_id)
    assert latest["id"] == result.pilot_id
