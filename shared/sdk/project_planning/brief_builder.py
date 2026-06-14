"""Stage 45 -- deterministic, rule-based project brief builder.

No LLM. Given a raw user request (and optional requirement summary), it
detects a known project template and produces a deterministic
``ProjectBrief``. If the request is too vague to plan, it returns a
brief with ``requires_clarification=true`` and an empty scope.
"""

from __future__ import annotations

from shared.sdk.project_planning.models import ProjectBrief

TEMPLATE_FASTAPI_TODO = "fastapi_todo_service"
TEMPLATE_GENERIC = "generic_software_project"

# Lowercased trigger substrings -> template.
_FASTAPI_TODO_TRIGGERS = (
    "fastapi todo",
    "todo api",
    "todo crud",
    "todo service",
    "todo 服務",
    "todo crud",
    "fastapi + sqlite",
)
# Looser signal: both a todo word and an api/fastapi word present.
_TODO_WORDS = ("todo", "to-do", "待辦")
_API_WORDS = ("fastapi", "api", "crud")

_MIN_MEANINGFUL_LEN = 12
_VAGUE_MARKERS = ("tbd", "???", "not sure", "看不懂", "再說", "隨便")


def detect_template(request_text: str) -> str:
    """Return the template key for a request (deterministic)."""
    text = (request_text or "").lower()
    if any(trigger in text for trigger in _FASTAPI_TODO_TRIGGERS):
        return TEMPLATE_FASTAPI_TODO
    has_todo = any(word in text for word in _TODO_WORDS)
    has_api = any(word in text for word in _API_WORDS)
    if has_todo and has_api:
        return TEMPLATE_FASTAPI_TODO
    return TEMPLATE_GENERIC


def _is_vague(request_text: str, requirement_summary: str | None) -> bool:
    combined = f"{request_text or ''} {requirement_summary or ''}".strip()
    if len(combined) < _MIN_MEANINGFUL_LEN:
        return True
    lowered = combined.lower()
    # A request that is *only* a vague marker is unclear; a longer request
    # that merely mentions one is fine.
    if len(combined) < 40 and any(marker in lowered for marker in _VAGUE_MARKERS):
        return True
    return False


def build_brief(
    request_text: str,
    *,
    requirement_summary: str | None = None,
    created_by_agent: str = "project-planner-agent",
) -> ProjectBrief:
    """Build a deterministic project brief from a raw request."""
    if _is_vague(request_text, requirement_summary):
        return ProjectBrief(
            problem_statement=(request_text or "").strip()[:500],
            goal="",
            requires_clarification=True,
            created_by_agent=created_by_agent,
            metadata={"template": TEMPLATE_GENERIC, "reason": "request_too_vague"},
        )

    template = detect_template(request_text)
    if template == TEMPLATE_FASTAPI_TODO:
        return _fastapi_todo_brief(request_text, requirement_summary, created_by_agent)
    return _generic_brief(request_text, requirement_summary, created_by_agent)


def _fastapi_todo_brief(
    request_text: str,
    requirement_summary: str | None,
    created_by_agent: str,
) -> ProjectBrief:
    return ProjectBrief(
        problem_statement=(
            "The user needs a small, locally-runnable FastAPI Todo service "
            "with CRUD endpoints, SQLite persistence, tests, and documentation."
        ),
        goal="Build a small FastAPI Todo service.",
        scope=[
            "CRUD Todo API",
            "SQLite persistence",
            "pytest tests",
            "README",
            "API examples",
        ],
        non_scope=[
            "authentication",
            "production deployment",
            "frontend UI",
            "multi-user permissions",
        ],
        assumptions=[
            "Python 3.11+",
            "FastAPI",
            "SQLite",
            "pytest",
            "local dev only",
        ],
        constraints=[
            "No real production deployment",
            "No secret required",
        ],
        stakeholders=["requester", "development-agent", "qa-agent"],
        success_metrics=[
            "tests pass",
            "README includes run/test instructions",
            "CRUD endpoints documented",
        ],
        requires_clarification=False,
        created_by_agent=created_by_agent,
        metadata={
            "template": TEMPLATE_FASTAPI_TODO,
            "request_excerpt": (request_text or "").strip()[:200],
        },
    )


def _generic_brief(
    request_text: str,
    requirement_summary: str | None,
    created_by_agent: str,
) -> ProjectBrief:
    goal = (requirement_summary or request_text or "").strip()[:200]
    return ProjectBrief(
        problem_statement=(request_text or "").strip()[:500],
        goal=goal or "Deliver the requested software capability.",
        scope=[
            "Clarify and freeze the requirement",
            "Implement the requested capability",
            "Test the implementation",
            "Document the result",
        ],
        non_scope=[
            "production deployment",
            "features beyond the stated request",
        ],
        assumptions=[
            "local dev / test only",
            "no real production credentials",
        ],
        constraints=["No real production deployment"],
        stakeholders=["requester", "development-agent", "qa-agent"],
        success_metrics=[
            "requested capability implemented",
            "tests pass",
            "documentation present",
        ],
        requires_clarification=False,
        created_by_agent=created_by_agent,
        metadata={"template": TEMPLATE_GENERIC},
    )


__all__ = [
    "TEMPLATE_FASTAPI_TODO",
    "TEMPLATE_GENERIC",
    "detect_template",
    "build_brief",
]
