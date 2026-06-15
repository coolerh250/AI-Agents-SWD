"""Stage 49 -- delivery package store contract (DB-free, via fakes).

Validates the create/read round-trip contract the package builder relies on.
The real asyncpg store mirrors these method signatures + return shapes.
"""

from __future__ import annotations

from delivery_package_fakes import build_fake_package


async def test_store_roundtrip(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    store = stores["package"]
    pid = result.package_id

    pkg = await store.get_delivery_package(pid)
    assert pkg["status"] == "ready_for_review"
    assert pkg["human_acceptance_status"] == "pending"

    assert len(await store.get_package_sections(pid)) == 14
    assert len(await store.get_package_artifacts(pid)) >= 7
    assert (await store.get_acceptance_gate(pid))["decision"] == "ready_for_operator_review"
    assert len(await store.get_gate_check_results(pid)) >= 15
    assert len(await store.get_handoff_summaries(pid)) == 3
    assert (await store.get_readiness_snapshot(pid))[
        "readiness_status"
    ] == "ready_for_operator_review"
    assert (await store.get_operator_review(pid))["review_status"] == "pending"
    assert (await store.get_delivery_package_report(pid))["controlled_only"] is True


async def test_latest_package_lookup(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    latest = await stores["package"].get_latest_package()
    assert latest["id"] == result.package_id
