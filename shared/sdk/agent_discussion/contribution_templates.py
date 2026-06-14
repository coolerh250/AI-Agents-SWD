"""Stage 46 -- deterministic, role-based discussion contributions.

No real LLM. Given the project brief / work items / acceptance criteria /
risks, produce a fixed set of role contribution SUMMARIES. Never persists
chain-of-thought; ``summary`` and ``rationale_summary`` are short
conclusions only.
"""

from __future__ import annotations

from shared.sdk.agent_discussion.models import DiscussionContribution

TEMPLATE_FASTAPI_TODO = "fastapi_todo_service"


def _work_types(work_items: list[dict]) -> set[str]:
    return {str(w.get("work_type") or "") for w in work_items}


def build_contributions(
    *,
    template: str,
    brief: dict,
    work_items: list[dict],
    acceptance_criteria: list[dict],
    risks: list[dict],
    validation_status: str = "valid",
) -> list[DiscussionContribution]:
    """Deterministic role contributions for a full pre-execution review."""
    if template == TEMPLATE_FASTAPI_TODO:
        return _fastapi_todo_contributions(
            brief, work_items, acceptance_criteria, risks, validation_status
        )
    return _generic_contributions(brief, work_items, acceptance_criteria, validation_status)


def _c(role: str, ctype: str, summary: str, **kw) -> DiscussionContribution:
    return DiscussionContribution(agent_role=role, contribution_type=ctype, summary=summary, **kw)


def _fastapi_todo_contributions(
    brief: dict,
    work_items: list[dict],
    acceptance_criteria: list[dict],
    risks: list[dict],
    validation_status: str,
) -> list[DiscussionContribution]:
    wt = _work_types(work_items)
    return [
        _c(
            "requirement-agent",
            "scope_assessment",
            "Scope confirmed: CRUD Todo API, SQLite persistence, pytest tests, "
            "README, and API examples. Non-scope (auth, frontend, production "
            "deploy, multi-user) is explicitly excluded.",
            confidence="high",
        ),
        _c(
            "requirement-agent",
            "requirement_question",
            "API resource naming should follow /todos conventions; treated as "
            "a low-severity clarification only.",
            confidence="medium",
            severity="low",
        ),
        _c(
            "project-planner-agent",
            "recommendation",
            f"Task graph validation is '{validation_status}'. Dependencies are "
            "executable in planning-only mode; work-item dispatch is disabled.",
            confidence="high",
        ),
        _c(
            "architecture-capability",
            "architecture_option",
            "Recommend a simple FastAPI app module structure. Todo model fields: "
            "id, title, description, completed, created_at, updated_at. Endpoints: "
            "POST /todos, GET /todos, GET /todos/{id}, PUT /todos/{id}, "
            "DELETE /todos/{id}.",
            confidence="high",
        ),
        _c(
            "development-agent",
            "implementation_plan",
            "Implementation sequence: app scaffold -> model/persistence -> CRUD "
            "routes -> tests -> README.",
            confidence="high",
        ),
        _c(
            "qa-agent",
            "qa_strategy",
            "pytest tests for create/list/get/update/delete, plus negative tests "
            "for not-found and validation errors. Document the local test command "
            "in the README.",
            confidence="high",
        ),
        _c(
            "security-capability",
            "security_risk",
            "No secrets required and no production deployment. Lack of auth is an "
            "accepted non-scope item. Input validation is a low/medium residual "
            "risk to cover in tests.",
            confidence="medium",
            severity="low",
        ),
        _c(
            "devops-agent",
            "delivery_risk",
            "Local-only run path; no deployment this stage. Containerization is a "
            "later concern only if delivery scope expands.",
            confidence="high",
            severity="low",
        ),
        _c(
            "delivery-capability",
            "recommendation",
            "Delivery package should include: PR/diff summary, test result, README, "
            "acceptance checklist, and known limitations.",
            confidence="high",
        ),
        _c(
            "qa-agent" if "qa" in wt else "delivery-capability",
            "acceptance_coverage",
            f"{len(acceptance_criteria)} acceptance criteria authored; required "
            "criteria are mapped to CRUD/persistence/test/doc work items.",
            confidence="high",
        ),
    ]


def _generic_contributions(
    brief: dict,
    work_items: list[dict],
    acceptance_criteria: list[dict],
    validation_status: str,
) -> list[DiscussionContribution]:
    return [
        _c(
            "requirement-agent",
            "scope_assessment",
            f"Scope: {', '.join(brief.get('scope', [])[:5]) or 'see brief'}.",
            confidence="medium",
        ),
        _c(
            "project-planner-agent",
            "recommendation",
            f"Task graph validation is '{validation_status}'; planning-only.",
            confidence="high",
        ),
        _c(
            "development-agent",
            "implementation_plan",
            "Implement the requested capability following the work-item order.",
            confidence="medium",
        ),
        _c(
            "qa-agent",
            "qa_strategy",
            "Author tests for each acceptance criterion.",
            confidence="medium",
        ),
        _c(
            "security-capability",
            "security_risk",
            "Confirm no secrets are required and no production deployment is attempted.",
            confidence="medium",
            severity="low",
        ),
        _c(
            "devops-agent",
            "delivery_risk",
            "Local/test only; no deployment this stage.",
            confidence="high",
            severity="low",
        ),
        _c(
            "delivery-capability",
            "recommendation",
            "Delivery package should include test result, docs, and acceptance checklist.",
            confidence="medium",
        ),
    ]


__all__ = ["build_contributions", "TEMPLATE_FASTAPI_TODO"]
