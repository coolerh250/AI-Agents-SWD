"""Step AT-M2-TEAM-CORE -- the team context carried on an autonomous-path message.

A message belongs to the autonomous path when it names the project whose team owns the work. That
one fact is what tells a runtime agent to ask the router who comes next instead of publishing to
its compile-time successor, so it is kept explicit rather than inferred.
"""

from __future__ import annotations

from typing import Any

TEAM_CONTEXT_KEY = "team_context"


def team_context_of(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """The team context on ``payload``, or None when this is not an autonomous-path message."""
    if not payload:
        return None
    context = payload.get(TEAM_CONTEXT_KEY)
    if not isinstance(context, dict):
        return None
    project_id = str(context.get("project_id") or "").strip()
    if not project_id:
        return None
    return {
        "project_id": project_id,
        "goal_ref": str(context.get("goal_ref") or ""),
        "thread_id": str(context.get("thread_id") or "") or None,
        "work_item_id": str(context.get("work_item_id") or "") or None,
        "workflow_stage": str(context.get("workflow_stage") or ""),
    }


def with_team_context(payload: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    """``payload`` carrying ``context`` forward, so the whole run stays on the autonomous path."""
    if not context:
        return payload
    return {**payload, TEAM_CONTEXT_KEY: dict(context)}


def build_team_context(
    project_id: str,
    goal_ref: str = "",
    thread_id: str | None = None,
    work_item_id: str | None = None,
    workflow_stage: str = "",
) -> dict[str, Any]:
    return {
        "project_id": str(project_id),
        "goal_ref": goal_ref,
        "thread_id": thread_id,
        "work_item_id": work_item_id,
        "workflow_stage": workflow_stage,
    }


__all__ = ["TEAM_CONTEXT_KEY", "build_team_context", "team_context_of", "with_team_context"]
