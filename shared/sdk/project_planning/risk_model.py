"""Stage 45 -- deterministic project-risk builder."""

from __future__ import annotations

from shared.sdk.project_planning.brief_builder import TEMPLATE_FASTAPI_TODO
from shared.sdk.project_planning.models import ProjectBrief, ProjectRisk


def build_risks(brief: ProjectBrief, *, template: str) -> list[ProjectRisk]:
    if template == TEMPLATE_FASTAPI_TODO:
        return _fastapi_todo_risks()
    return _generic_risks(brief)


def _fastapi_todo_risks() -> list[ProjectRisk]:
    rows = [
        (
            "RISK-001",
            "Unclear persistence requirement",
            "medium",
            "medium",
            "Freeze the data model in ARCH-001 before implementation.",
            "architecture-capability",
        ),
        (
            "RISK-002",
            "Test coverage insufficient",
            "medium",
            "medium",
            "QA-001 must cover all CRUD paths and persistence.",
            "qa-agent",
        ),
        (
            "RISK-003",
            "Environment dependency mismatch",
            "medium",
            "low",
            "Pin Python/FastAPI/pytest versions in assumptions.",
            "devops-agent",
        ),
        (
            "RISK-004",
            "Scope creep into auth/frontend",
            "high",
            "medium",
            "Non-scope explicitly excludes auth and frontend; reject additions.",
            "requirement-agent",
        ),
    ]
    return [
        ProjectRisk(
            risk_key=k,
            title=t,
            severity=sev,
            likelihood=lik,
            mitigation=mit,
            owner_agent_role=owner,
        )
        for (k, t, sev, lik, mit, owner) in rows
    ]


def _generic_risks(brief: ProjectBrief) -> list[ProjectRisk]:
    return [
        ProjectRisk(
            risk_key="RISK-001",
            title="Requirement ambiguity",
            severity="medium",
            likelihood="medium",
            mitigation="Confirm scope before implementation.",
            owner_agent_role="requirement-agent",
        ),
        ProjectRisk(
            risk_key="RISK-002",
            title="Insufficient test coverage",
            severity="medium",
            likelihood="medium",
            mitigation="Author acceptance criteria as tests.",
            owner_agent_role="qa-agent",
        ),
    ]


__all__ = ["build_risks"]
