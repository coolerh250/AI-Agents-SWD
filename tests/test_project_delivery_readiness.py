"""Stage 45 -- delivery readiness evaluation tests."""

from __future__ import annotations

from shared.sdk.project_planning.delivery_readiness import evaluate_delivery_readiness


def test_not_ready_when_nothing_done() -> None:
    r = evaluate_delivery_readiness(
        acceptance_criteria=[{"required": True, "status": "pending"}],
        work_items=[{"priority": "critical", "status": "pending"}],
        artifacts=[],
    )
    assert r.ready is False
    assert "required_acceptance_criteria_not_satisfied" in r.reasons
    assert "qa_report_missing" in r.reasons
    assert "delivery_summary_missing" in r.reasons


def test_ready_when_all_conditions_met() -> None:
    r = evaluate_delivery_readiness(
        acceptance_criteria=[{"required": True, "status": "satisfied"}],
        work_items=[{"priority": "critical", "status": "completed"}],
        artifacts=[{"artifact_type": "qa_report"}, {"artifact_type": "delivery_summary"}],
    )
    assert r.ready is True
    assert r.reasons == []


def test_waived_optional_criteria_ok() -> None:
    r = evaluate_delivery_readiness(
        acceptance_criteria=[
            {"required": True, "status": "satisfied"},
            {"required": False, "status": "pending"},
        ],
        work_items=[],
        artifacts=[{"artifact_type": "qa_report"}, {"artifact_type": "delivery_summary"}],
    )
    assert r.ready is True


def test_to_dict_shape() -> None:
    r = evaluate_delivery_readiness(acceptance_criteria=[], work_items=[], artifacts=[])
    d = r.to_dict()
    assert "ready" in d and "reasons" in d
