"""Stage 49 -- delivery package build from a completed mini pilot."""

from __future__ import annotations

from delivery_package_fakes import FakeDeliveryPackageStore, build_fake_package

from shared.sdk.delivery_package import DeliveryPackageRequest, run_delivery_package_build
from shared.sdk.delivery_package.models import REQUIRED_SECTION_KEYS


async def test_build_from_completed_pilot(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    assert result.package_id
    assert result.package_status == "ready_for_review"
    assert result.human_acceptance_status == "pending"
    assert result.production_executed is False
    assert result.pr_created is False
    assert result.deployment_performed is False
    assert result.real_llm_used is False
    assert result.external_delivery_performed is False


async def test_sections_all_present_and_ready(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    sections = await stores["package"].get_package_sections(result.package_id)
    keys = {s["section_key"] for s in sections}
    assert keys == set(REQUIRED_SECTION_KEYS)
    assert all(s["status"] == "ready" for s in sections)
    assert result.sections_missing_count == 0


async def test_artifacts_link_all_sources(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    artifacts = await stores["package"].get_package_artifacts(result.package_id)
    types = {a["artifact_type"] for a in artifacts}
    for expected in (
        "project_brief",
        "design_review_summary",
        "workspace_report",
        "qa_evidence_report",
        "safety_evidence_report",
        "acceptance_evaluations",
        "mini_delivery_report",
    ):
        assert expected in types


async def test_build_requires_existing_pilot(tmp_path, monkeypatch) -> None:
    _, stores = await build_fake_package(tmp_path, monkeypatch)
    result = await run_delivery_package_build(
        request=DeliveryPackageRequest(pilot_id="00000000-0000-0000-0000-000000000000"),
        pilot_store=stores["pilot"],
        project_store=stores["project"],
        review_store=stores["review"],
        workspace_store=stores["workspace"],
        package_store=FakeDeliveryPackageStore(),
        emit_events=False,
    )
    assert result.package_status == "failed"
    assert result.blocked_reason == "pilot_not_found"
