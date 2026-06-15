"""Stage 49 -- audit decision types + notification denylist."""

from __future__ import annotations

from shared.sdk.delivery_package.audit_events import DELIVERY_PACKAGE_DECISION_TYPES
from shared.sdk.delivery_package.events import DELIVERY_PACKAGE_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    _matches_pattern,
)


def test_all_decision_types_present() -> None:
    for expected in (
        "delivery_package_build_started",
        "delivery_package_sections_created",
        "delivery_package_acceptance_gate_evaluated",
        "delivery_package_ready_for_review",
        "delivery_package_build_failed",
        "operator_acceptance_review_created",
        "handoff_summary_created",
        "delivery_readiness_snapshot_created",
    ):
        assert expected in DELIVERY_PACKAGE_DECISION_TYPES


def test_notifications_default_denied() -> None:
    extra = ["acceptance_gate.ready_for_operator_review", "handoff.summary_created"]
    for ev in list(DELIVERY_PACKAGE_NOTIFICATION_EVENTS) + extra:
        assert any(_matches_pattern(ev, p) for p in DEFAULT_REAL_DELIVERY_DENYLIST), ev


def test_prior_denylist_patterns_preserved() -> None:
    for pat in (
        "delivery_pilot.*",
        "acceptance.*",
        "qa_evidence.*",
        "workspace.*",
        "codegen.*",
        "design_review.*",
        "discussion.*",
        "project.*",
        "audit.*",
        "verification.*",
    ):
        assert pat in DEFAULT_REAL_DELIVERY_DENYLIST


async def test_build_audits_and_notifies(tmp_path, monkeypatch) -> None:
    audits: list = []
    notifies: list = []

    async def _audit(*a, **k):
        audits.append(k.get("decision_type"))

    async def _notify(task_id, event_type, message):
        notifies.append(event_type)

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _audit)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _notify)

    # Re-run with events enabled.
    from mini_delivery_fakes import run_fake_pilot

    from shared.sdk.delivery_package import DeliveryPackageRequest, run_delivery_package_build

    pilot_result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    from delivery_package_fakes import FakeDeliveryPackageStore

    await run_delivery_package_build(
        request=DeliveryPackageRequest(pilot_id=pilot_result.pilot_id),
        pilot_store=stores["pilot"],
        project_store=stores["project"],
        review_store=stores["review"],
        workspace_store=stores["workspace"],
        package_store=FakeDeliveryPackageStore(),
        emit_events=True,
    )
    assert "delivery_package_build_started" in audits
    assert "delivery_package_ready_for_review" in audits
    assert "delivery_package.ready_for_review" in notifies
