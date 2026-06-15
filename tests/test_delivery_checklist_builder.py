"""Stage 49 -- acceptance checklist builder."""

from __future__ import annotations

from shared.sdk.delivery_package.checklist_builder import build_acceptance_checklist


def _evidence() -> dict:
    return {
        "acceptance_evaluations": [
            {
                "criterion_key": "AC-001",
                "evaluation_status": "satisfied",
                "evidence_type": "test_run",
                "rationale_summary": "pytest passed",
            },
            {
                "criterion_key": "AC-008",
                "evaluation_status": "satisfied",
                "evidence_type": "generated_file",
                "rationale_summary": "README",
            },
        ],
        "acceptance_summary": {"total": 2, "satisfied": 2, "failed": 0},
        "qa": {"status": "passed", "tests_passed": 5, "tests_failed": 0},
        "safety": {"status": "safe"},
    }


def test_checklist_has_categories() -> None:
    cl = build_acceptance_checklist(_evidence())
    cats = {i["category"] for i in cl["items"]}
    for expected in ("functional", "testing", "safety", "known_limitations", "human_review"):
        assert expected in cats


def test_human_review_items_pending() -> None:
    cl = build_acceptance_checklist(_evidence())
    human = [i for i in cl["items"] if i["human_review"]]
    assert human
    assert all(i["status"] == "pending" for i in human)
    assert cl["summary"]["human_review_pending"] == len(human)


def test_functional_items_reflect_evidence() -> None:
    cl = build_acceptance_checklist(_evidence())
    functional = [i for i in cl["items"] if i["category"] == "functional"]
    assert all(i["status"] == "checked" for i in functional)
