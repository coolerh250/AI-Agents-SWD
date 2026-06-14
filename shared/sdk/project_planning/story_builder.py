"""Stage 45 -- deterministic user-story builder."""

from __future__ import annotations

from shared.sdk.project_planning.brief_builder import TEMPLATE_FASTAPI_TODO
from shared.sdk.project_planning.models import ProjectBrief, UserStory


def build_user_stories(brief: ProjectBrief, *, template: str) -> list[UserStory]:
    """Build deterministic user stories for a brief/template."""
    if template == TEMPLATE_FASTAPI_TODO:
        return _fastapi_todo_stories()
    return _generic_stories(brief)


def _fastapi_todo_stories() -> list[UserStory]:
    rows = [
        ("US-001", "API user", "create a todo", "I can track a new task", "high"),
        ("US-002", "API user", "list todos", "I can see all my tasks", "high"),
        ("US-003", "API user", "get a todo by id", "I can inspect one task", "medium"),
        ("US-004", "API user", "update a todo", "I can change a task", "high"),
        ("US-005", "API user", "delete a todo", "I can remove a task", "medium"),
        (
            "US-006",
            "developer",
            "run the test suite",
            "I can trust the service works",
            "high",
        ),
    ]
    return [
        UserStory(story_key=k, actor=a, need=n, benefit=b, priority=p) for (k, a, n, b, p) in rows
    ]


def _generic_stories(brief: ProjectBrief) -> list[UserStory]:
    return [
        UserStory(
            story_key="US-001",
            actor="user",
            need=brief.goal or "the requested capability",
            benefit="the stated goal is achieved",
            priority="high",
        ),
        UserStory(
            story_key="US-002",
            actor="developer",
            need="run the tests",
            benefit="I can trust the implementation",
            priority="high",
        ),
    ]


__all__ = ["build_user_stories"]
