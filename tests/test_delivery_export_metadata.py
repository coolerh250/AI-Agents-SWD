"""Stage 49 -- export metadata (no external delivery, no secrets)."""

from __future__ import annotations

from shared.sdk.delivery_package.export_metadata import build_export_metadata, render_markdown


class _Section:
    def __init__(self, key, status):
        self.section_key = key
        self.status = status


class _Handoff:
    def __init__(self, t):
        self.summary_type = t


def test_export_metadata_controlled_only() -> None:
    meta = build_export_metadata(
        package={
            "id": "pkg1",
            "package_key": "pkg-1",
            "package_type": "mini_project_delivery",
            "status": "ready_for_review",
            "project_id": "p1",
            "pilot_id": "pilot1",
            "human_acceptance_status": "pending",
        },
        gate={"status": "passed_with_findings", "decision": "ready_for_operator_review"},
        readiness={"readiness_status": "ready_for_operator_review"},
        sections=[_Section("executive_summary", "ready"), _Section("test_results", "ready")],
        handoff_summaries=[_Handoff("business_summary")],
    )
    assert meta["external_delivery_performed"] is False
    assert meta["production_executed"] is False
    assert meta["controlled_only"] is True
    assert meta["sections_ready_count"] == 2
    assert meta["human_acceptance_status"] == "pending"


def test_render_markdown_has_no_secret() -> None:
    meta = {
        "package_key": "pkg-1",
        "package_type": "mini_project_delivery",
        "package_status": "ready_for_review",
        "acceptance_gate_status": "passed_with_findings",
        "acceptance_gate_decision": "ready_for_operator_review",
        "readiness_status": "ready_for_operator_review",
        "human_acceptance_status": "pending",
        "sections_ready_count": 14,
        "sections_missing_count": 0,
    }
    md = render_markdown(meta)
    assert "pkg-1" in md
    assert "production_executed: false" in md
