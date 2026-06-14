"""Stage 45 -- orchestrator routing decision for project planning.

Pure decision function. Decides whether a requirement that just
completed should be routed to the project-planner-agent instead of the
legacy development-agent pipeline. Backward-compatible: only explicit
project request types (or recognised project template text) route to the
planner. Everything else stays on the legacy path.
"""

from __future__ import annotations

import os

# Request types that signal a project-scale request.
PROJECT_REQUEST_TYPES = frozenset(
    {
        "software_project",
        "feature_request",
        "build_request",
    }
)


def _flag_enabled(env: dict | None, name: str, default: bool) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def project_planner_enabled(env: dict | None = None) -> bool:
    return _flag_enabled(env, "ENABLE_PROJECT_PLANNER", True)


def planning_only_enabled(env: dict | None = None) -> bool:
    return _flag_enabled(env, "PROJECT_PLANNER_PLANNING_ONLY", True)


def work_item_dispatch_enabled(env: dict | None = None) -> bool:
    return _flag_enabled(env, "ENABLE_PROJECT_WORK_ITEM_DISPATCH", False)


def should_route_to_project_planner(
    *,
    request_type: str | None,
    request_text: str = "",
    skip_project_planning: bool = False,
    env: dict | None = None,
) -> bool:
    """True iff a requirement should go to the project planner.

    Routing happens only when the feature flag is on, the caller did not
    opt out, and the request is an explicit project type. (Template text
    alone does not force routing for non-project request types, so the
    legacy smoke pipeline -- which uses dev.test / production.deploy -- is
    never re-routed.)
    """
    if skip_project_planning:
        return False
    if not project_planner_enabled(env):
        return False
    rtype = (request_type or "").strip().lower()
    return rtype in PROJECT_REQUEST_TYPES


__all__ = [
    "PROJECT_REQUEST_TYPES",
    "project_planner_enabled",
    "planning_only_enabled",
    "work_item_dispatch_enabled",
    "should_route_to_project_planner",
]
