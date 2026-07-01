#!/usr/bin/env python3
"""Staging/demo only -- seed the Step 64D demo project + work item.

Non-production only. Creates (idempotently) the "SaaS User Management Module" project and a
"Create user CRUD API" work item using the existing project / work-item SDK -- the same code
path the communication-gateway mock intake uses -- with production_effect=False. No production
action, no external write, no secret. Intended to run inside the orchestrator container (which
has the SDK + PyYAML), e.g.:

    docker exec -i <orchestrator> python - < scripts/staging_seed_demo_workflow.py

Prints a JSON summary of the created/reused records and their safety fields.
"""

from __future__ import annotations

import asyncio
import json

PROJECT_NAME = "SaaS User Management Module"
WORK_ITEM_TITLE = "Create user CRUD API"
WORK_ITEM_DESC = (
    "Build a staging-only user management CRUD API module with create/read/update/delete user "
    "operations, basic validation, and non-production delivery evidence."
)


async def main() -> None:
    from shared.sdk.projects import ProjectStore
    from shared.sdk.work_items import WorkItemStore
    from shared.sdk.work_items.events import build_audit_metadata

    projects = ProjectStore()
    items = WorkItemStore()

    existing = await projects.list_projects()
    project = next((p for p in existing if p.get("title") == PROJECT_NAME), None)
    project_created = False
    if project is None:
        project = await projects.create_project(
            name=PROJECT_NAME,
            description="Staging demo project (non-production).",
            environment_scope="nonprod",
            requester="staging-demo",
        )
        project_created = True
    project_id = project["project_id"]

    existing_items = await items.list_work_items(project_id)
    wi = next((w for w in existing_items if w.get("title") == WORK_ITEM_TITLE), None)
    wi_created = False
    if wi is None:
        wi = await items.create_work_item(
            project_id=project_id,
            title=WORK_ITEM_TITLE,
            description=WORK_ITEM_DESC,
            work_type="task",
            priority="medium",
            item_source="staging_demo",
            requested_by="staging-demo",
            requires_human_approval=False,
            production_effect=False,
        )
        wi_created = True
        await items.record_event(
            project_id=project_id,
            work_item_id=wi["id"],
            event_type="work_item_created",
            from_state=None,
            to_state="created",
            actor="staging-demo",
            role="intake",
            reason="staging demo seed",
            correlation_id=wi["id"],
            metadata=build_audit_metadata(
                event_type="work_item_created",
                actor="staging-demo",
                role="intake",
                reason="staging demo seed",
                project_id=project_id,
                work_item_id=wi["id"],
                correlation_id=wi["id"],
            ),
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "staging-demo-seed",
                "project_created": project_created,
                "work_item_created": wi_created,
                "project_id": project_id,
                "project_key": project.get("project_key"),
                "project_title": project.get("title"),
                "environment_scope": project.get("environment_scope"),
                "production_allowed": project.get("production_allowed"),
                "work_item_id": wi["id"],
                "work_item_key": wi.get("work_item_key"),
                "work_item_title": wi.get("title"),
                "lifecycle_state": wi.get("lifecycle_state"),
                "production_effect": wi.get("production_effect"),
                "requires_human_approval": wi.get("requires_human_approval"),
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
