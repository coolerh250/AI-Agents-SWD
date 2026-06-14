"""Stage 45 -- deterministic acceptance-criteria builder."""

from __future__ import annotations

from shared.sdk.project_planning.brief_builder import TEMPLATE_FASTAPI_TODO
from shared.sdk.project_planning.models import AcceptanceCriterion, ProjectBrief


def build_acceptance_criteria(brief: ProjectBrief, *, template: str) -> list[AcceptanceCriterion]:
    if template == TEMPLATE_FASTAPI_TODO:
        return _fastapi_todo_acceptance()
    return _generic_acceptance(brief)


def _fastapi_todo_acceptance() -> list[AcceptanceCriterion]:
    rows = [
        ("AC-001", "Can create a todo.", "integration_test", "BE-002", True),
        ("AC-002", "Can list todos.", "integration_test", "BE-002", True),
        ("AC-003", "Can get a todo by id.", "integration_test", "BE-002", True),
        ("AC-004", "Can update a todo.", "integration_test", "BE-002", True),
        ("AC-005", "Can delete a todo.", "integration_test", "BE-002", True),
        ("AC-006", "SQLite persistence works locally.", "integration_test", "DB-001", True),
        ("AC-007", "pytest suite passes.", "unit_test", "QA-002", True),
        (
            "AC-008",
            "README explains setup, run, test, and API examples.",
            "documentation_review",
            "DOC-001",
            True,
        ),
        ("AC-009", "No production deployment attempted.", "static_check", None, True),
        ("AC-010", "No secret required.", "static_check", None, True),
    ]
    return [
        AcceptanceCriterion(
            criterion_key=k,
            description=d,
            verification_method=m,
            work_item_key=wi,
            required=req,
        )
        for (k, d, m, wi, req) in rows
    ]


def _generic_acceptance(brief: ProjectBrief) -> list[AcceptanceCriterion]:
    return [
        AcceptanceCriterion(
            criterion_key="AC-001",
            description="The requested capability is implemented.",
            verification_method="manual_review",
            required=True,
        ),
        AcceptanceCriterion(
            criterion_key="AC-002",
            description="Tests for the capability pass.",
            verification_method="unit_test",
            required=True,
        ),
        AcceptanceCriterion(
            criterion_key="AC-003",
            description="No production deployment attempted.",
            verification_method="static_check",
            required=True,
        ),
    ]


__all__ = ["build_acceptance_criteria"]
