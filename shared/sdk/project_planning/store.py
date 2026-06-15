"""Stage 45 -- asyncpg store for the project planner & task graph tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.observability.tracing import start_span
from shared.sdk.project_planning.models import (
    AcceptanceCriterion,
    ProjectArtifact,
    ProjectBrief,
    ProjectCreate,
    ProjectMilestone,
    ProjectRisk,
    ProjectWorkItem,
    UserStory,
    WorkItemDependency,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _dec(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


class ProjectPlanningStore:
    """Wraps the ten Stage 45 project tables. Short-lived connections."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------
    async def create_project(self, project: ProjectCreate) -> dict:
        with start_span("project_planning.create_project", **{"db.table": "projects"}):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO projects "
                    "(source_task_id, title, summary, request_source, requester, "
                    " project_type, status, autonomy_level, risk_level, metadata) "
                    "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb) "
                    "RETURNING id, status, created_at",
                    project.source_task_id,
                    project.title,
                    project.summary,
                    project.request_source,
                    project.requester,
                    project.project_type,
                    project.status,
                    project.autonomy_level,
                    project.risk_level,
                    json.dumps(project.metadata or {}),
                )
            finally:
                await conn.close()
            return {
                "id": str(row["id"]),
                "status": row["status"],
                "created_at": _iso(row["created_at"]),
            }

    async def create_project_brief(self, project_id: str, brief: ProjectBrief) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO project_briefs "
                "(project_id, version, problem_statement, goal, scope, non_scope, "
                " assumptions, constraints, stakeholders, success_metrics, "
                " created_by_agent, metadata) "
                "VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, "
                " $8::jsonb, $9::jsonb, $10::jsonb, $11, $12::jsonb) RETURNING id",
                project_id,
                brief.version,
                brief.problem_statement,
                brief.goal,
                json.dumps(brief.scope),
                json.dumps(brief.non_scope),
                json.dumps(brief.assumptions),
                json.dumps(brief.constraints),
                json.dumps(brief.stakeholders),
                json.dumps(brief.success_metrics),
                brief.created_by_agent,
                json.dumps(
                    {
                        **(brief.metadata or {}),
                        "requires_clarification": brief.requires_clarification,
                    }
                ),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_user_stories(self, project_id: str, stories: list[UserStory]) -> int:
        if not stories:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for s in stories:
                    await conn.execute(
                        "INSERT INTO project_user_stories "
                        "(project_id, story_key, actor, need, benefit, priority, "
                        " status, metadata) "
                        "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb)",
                        project_id,
                        s.story_key,
                        s.actor,
                        s.need,
                        s.benefit,
                        s.priority,
                        s.status,
                        json.dumps(s.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(stories)

    async def create_milestones(
        self, project_id: str, milestones: list[ProjectMilestone]
    ) -> dict[str, str]:
        """Insert milestones, return {milestone_key: id}."""
        key_to_id: dict[str, str] = {}
        if not milestones:
            return key_to_id
        conn = await self._connect()
        try:
            async with conn.transaction():
                for m in milestones:
                    row = await conn.fetchrow(
                        "INSERT INTO project_milestones "
                        "(project_id, milestone_key, title, description, order_index, "
                        " status, metadata) "
                        "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb) RETURNING id",
                        project_id,
                        m.milestone_key,
                        m.title,
                        m.description,
                        m.order_index,
                        m.status,
                        json.dumps(m.metadata or {}),
                    )
                    key_to_id[m.milestone_key] = str(row["id"])
        finally:
            await conn.close()
        return key_to_id

    async def create_work_items(
        self,
        project_id: str,
        work_items: list[ProjectWorkItem],
        *,
        milestone_ids: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Insert work items, return {work_item_key: id}."""
        key_to_id: dict[str, str] = {}
        if not work_items:
            return key_to_id
        milestone_ids = milestone_ids or {}
        conn = await self._connect()
        try:
            async with conn.transaction():
                for w in work_items:
                    ms_id = milestone_ids.get(w.milestone_key) if w.milestone_key else None
                    row = await conn.fetchrow(
                        "INSERT INTO project_work_items "
                        "(project_id, milestone_id, work_item_key, title, description, "
                        " work_type, assigned_agent_role, status, priority, "
                        " estimated_effort, risk_level, dispatch_policy, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, "
                        " $10, $11, $12, $13::jsonb) RETURNING id",
                        project_id,
                        ms_id,
                        w.work_item_key,
                        w.title,
                        w.description,
                        w.work_type,
                        w.assigned_agent_role,
                        w.status,
                        w.priority,
                        w.estimated_effort,
                        w.risk_level,
                        w.dispatch_policy,
                        json.dumps(w.metadata or {}),
                    )
                    key_to_id[w.work_item_key] = str(row["id"])
        finally:
            await conn.close()
        return key_to_id

    async def create_dependencies(
        self,
        project_id: str,
        dependencies: list[WorkItemDependency],
        *,
        work_item_ids: dict[str, str],
    ) -> int:
        count = 0
        if not dependencies:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for d in dependencies:
                    a = work_item_ids.get(d.work_item_key)
                    b = work_item_ids.get(d.depends_on_work_item_key)
                    if not a or not b or a == b:
                        continue
                    await conn.execute(
                        "INSERT INTO project_work_item_dependencies "
                        "(project_id, work_item_id, depends_on_work_item_id, "
                        " dependency_type, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::jsonb) "
                        "ON CONFLICT (work_item_id, depends_on_work_item_id) DO NOTHING",
                        project_id,
                        a,
                        b,
                        d.dependency_type,
                        json.dumps(d.metadata or {}),
                    )
                    count += 1
        finally:
            await conn.close()
        return count

    async def create_acceptance_criteria(
        self,
        project_id: str,
        criteria: list[AcceptanceCriterion],
        *,
        work_item_ids: dict[str, str] | None = None,
    ) -> int:
        if not criteria:
            return 0
        work_item_ids = work_item_ids or {}
        conn = await self._connect()
        try:
            async with conn.transaction():
                for c in criteria:
                    wi_id = work_item_ids.get(c.work_item_key) if c.work_item_key else None
                    await conn.execute(
                        "INSERT INTO project_acceptance_criteria "
                        "(project_id, work_item_id, criterion_key, description, "
                        " verification_method, status, required, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::jsonb)",
                        project_id,
                        wi_id,
                        c.criterion_key,
                        c.description,
                        c.verification_method,
                        c.status,
                        c.required,
                        json.dumps(c.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(criteria)

    async def create_risks(self, project_id: str, risks: list[ProjectRisk]) -> int:
        if not risks:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for r in risks:
                    await conn.execute(
                        "INSERT INTO project_risks "
                        "(project_id, risk_key, title, description, severity, "
                        " likelihood, mitigation, owner_agent_role, status, metadata) "
                        "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)",
                        project_id,
                        r.risk_key,
                        r.title,
                        r.description,
                        r.severity,
                        r.likelihood,
                        r.mitigation,
                        r.owner_agent_role,
                        r.status,
                        json.dumps(r.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(risks)

    async def create_graph_snapshot(
        self,
        project_id: str,
        *,
        version: int,
        graph_hash: str,
        nodes: list[dict],
        edges: list[dict],
        validation_status: str,
        validation_errors: list[dict],
        created_by_agent: str = "project-planner-agent",
        metadata: dict | None = None,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO project_graph_snapshots "
                "(project_id, version, graph_hash, nodes, edges, "
                " validation_status, validation_errors, created_by_agent, metadata) "
                "VALUES ($1::uuid, $2, $3, $4::jsonb, $5::jsonb, $6, $7::jsonb, $8, $9::jsonb) "
                "RETURNING id",
                project_id,
                version,
                graph_hash,
                json.dumps(nodes),
                json.dumps(edges),
                validation_status,
                json.dumps(validation_errors),
                created_by_agent,
                json.dumps(metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_artifacts(
        self,
        project_id: str,
        artifacts: list[ProjectArtifact],
        *,
        work_item_ids: dict[str, str] | None = None,
    ) -> int:
        if not artifacts:
            return 0
        work_item_ids = work_item_ids or {}
        conn = await self._connect()
        try:
            async with conn.transaction():
                for a in artifacts:
                    wi_id = work_item_ids.get(a.work_item_key) if a.work_item_key else None
                    await conn.execute(
                        "INSERT INTO project_artifacts "
                        "(project_id, work_item_id, artifact_type, title, content, "
                        " uri, created_by_agent, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8::jsonb)",
                        project_id,
                        wi_id,
                        a.artifact_type,
                        a.title,
                        json.dumps(a.content) if a.content is not None else None,
                        a.uri,
                        a.created_by_agent,
                        json.dumps(a.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(artifacts)

    # ------------------------------------------------------------------
    # read
    # ------------------------------------------------------------------
    async def get_project(self, project_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, source_task_id, title, summary, request_source, requester, "
                " project_type, status, autonomy_level, risk_level, created_at, "
                " updated_at, completed_at, metadata FROM projects WHERE id = $1::uuid",
                project_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return self._project_row(row) if row else None

    @staticmethod
    def _project_row(row: asyncpg.Record) -> dict:
        return {
            "id": str(row["id"]),
            "source_task_id": str(row["source_task_id"]) if row["source_task_id"] else None,
            "title": row["title"],
            "summary": row["summary"],
            "request_source": row["request_source"],
            "requester": row["requester"],
            "project_type": row["project_type"],
            "status": row["status"],
            "autonomy_level": row["autonomy_level"],
            "risk_level": row["risk_level"],
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "completed_at": _iso(row["completed_at"]),
            "metadata": _dec(row["metadata"], {}),
        }

    async def list_projects(self, *, status: str | None = None, limit: int = 100) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, source_task_id, title, summary, request_source, requester, "
                " project_type, status, autonomy_level, risk_level, created_at, "
                " updated_at, completed_at, metadata FROM projects "
                "WHERE ($1::text IS NULL OR status = $1) "
                "ORDER BY created_at DESC LIMIT $2",
                status,
                max(1, min(int(limit), 500)),
            )
        finally:
            await conn.close()
        return [self._project_row(r) for r in rows]

    async def get_brief(self, project_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, version, problem_statement, goal, scope, non_scope, "
                " assumptions, constraints, stakeholders, success_metrics, "
                " created_by_agent, created_at, metadata FROM project_briefs "
                "WHERE project_id = $1::uuid ORDER BY version DESC LIMIT 1",
                project_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "version": row["version"],
            "problem_statement": row["problem_statement"],
            "goal": row["goal"],
            "scope": _dec(row["scope"], []),
            "non_scope": _dec(row["non_scope"], []),
            "assumptions": _dec(row["assumptions"], []),
            "constraints": _dec(row["constraints"], []),
            "stakeholders": _dec(row["stakeholders"], []),
            "success_metrics": _dec(row["success_metrics"], []),
            "created_by_agent": row["created_by_agent"],
            "created_at": _iso(row["created_at"]),
            "metadata": _dec(row["metadata"], {}),
        }

    async def list_user_stories(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT story_key, actor, need, benefit, priority, status, metadata "
                "FROM project_user_stories WHERE project_id = $1::uuid ORDER BY story_key",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "story_key": r["story_key"],
                "actor": r["actor"],
                "need": r["need"],
                "benefit": r["benefit"],
                "priority": r["priority"],
                "status": r["status"],
                "metadata": _dec(r["metadata"], {}),
            }
            for r in rows
        ]

    async def list_milestones(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, milestone_key, title, description, order_index, status "
                "FROM project_milestones WHERE project_id = $1::uuid ORDER BY order_index",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "milestone_key": r["milestone_key"],
                "title": r["title"],
                "description": r["description"],
                "order_index": r["order_index"],
                "status": r["status"],
            }
            for r in rows
        ]

    @staticmethod
    def _work_item_row(r: asyncpg.Record) -> dict:
        return {
            "id": str(r["id"]),
            "work_item_key": r["work_item_key"],
            "title": r["title"],
            "description": r["description"],
            "work_type": r["work_type"],
            "assigned_agent_role": r["assigned_agent_role"],
            "status": r["status"],
            "priority": r["priority"],
            "estimated_effort": r["estimated_effort"],
            "risk_level": r["risk_level"],
            "dispatch_policy": r["dispatch_policy"],
            "milestone_id": str(r["milestone_id"]) if r["milestone_id"] else None,
            "created_at": _iso(r["created_at"]),
            "updated_at": _iso(r["updated_at"]),
            "completed_at": _iso(r["completed_at"]),
        }

    _WORK_ITEM_COLS = (
        "id, work_item_key, title, description, work_type, assigned_agent_role, "
        "status, priority, estimated_effort, risk_level, dispatch_policy, "
        "milestone_id, created_at, updated_at, completed_at"
    )

    async def list_work_items(self, project_id: str, *, status: str | None = None) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {self._WORK_ITEM_COLS} FROM project_work_items "
                "WHERE project_id = $1::uuid AND ($2::text IS NULL OR status = $2) "
                "ORDER BY work_item_key",
                project_id,
                status,
            )
        finally:
            await conn.close()
        return [self._work_item_row(r) for r in rows]

    async def get_work_item(self, work_item_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {self._WORK_ITEM_COLS}, project_id FROM project_work_items "
                "WHERE id = $1::uuid",
                work_item_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        item = self._work_item_row(row)
        item["project_id"] = str(row["project_id"])
        return item

    async def list_ready_work_items(self, project_id: str) -> list[dict]:
        """Work items whose dependencies are all completed and which are
        themselves pending/ready (graph-aware readiness)."""
        items = await self.list_work_items(project_id)
        deps = await self.list_dependencies(project_id)
        status_by_id = {w["id"]: w["status"] for w in items}
        blocked_ids: set[str] = set()
        for d in deps:
            if status_by_id.get(d["depends_on_work_item_id"]) != "completed":
                blocked_ids.add(d["work_item_id"])
        return [
            w for w in items if w["status"] in ("pending", "ready") and w["id"] not in blocked_ids
        ]

    async def list_dependencies(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, work_item_id, depends_on_work_item_id, dependency_type "
                "FROM project_work_item_dependencies WHERE project_id = $1::uuid",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "work_item_id": str(r["work_item_id"]),
                "depends_on_work_item_id": str(r["depends_on_work_item_id"]),
                "dependency_type": r["dependency_type"],
            }
            for r in rows
        ]

    async def list_work_item_dependencies(self, work_item_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, work_item_id, depends_on_work_item_id, dependency_type "
                "FROM project_work_item_dependencies WHERE work_item_id = $1::uuid",
                work_item_id,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "work_item_id": str(r["work_item_id"]),
                "depends_on_work_item_id": str(r["depends_on_work_item_id"]),
                "dependency_type": r["dependency_type"],
            }
            for r in rows
        ]

    async def list_acceptance_criteria(
        self, project_id: str, *, work_item_id: str | None = None
    ) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, criterion_key, description, verification_method, status, "
                " required, work_item_id FROM project_acceptance_criteria "
                "WHERE project_id = $1::uuid "
                "AND ($2::uuid IS NULL OR work_item_id = $2::uuid) "
                "ORDER BY criterion_key",
                project_id,
                work_item_id,
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "criterion_key": r["criterion_key"],
                "description": r["description"],
                "verification_method": r["verification_method"],
                "status": r["status"],
                "required": r["required"],
                "work_item_id": str(r["work_item_id"]) if r["work_item_id"] else None,
            }
            for r in rows
        ]

    async def list_risks(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT risk_key, title, description, severity, likelihood, "
                " mitigation, owner_agent_role, status FROM project_risks "
                "WHERE project_id = $1::uuid ORDER BY risk_key",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "risk_key": r["risk_key"],
                "title": r["title"],
                "description": r["description"],
                "severity": r["severity"],
                "likelihood": r["likelihood"],
                "mitigation": r["mitigation"],
                "owner_agent_role": r["owner_agent_role"],
                "status": r["status"],
            }
            for r in rows
        ]

    async def list_artifacts(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT artifact_type, title, uri, created_by_agent, work_item_id "
                "FROM project_artifacts WHERE project_id = $1::uuid ORDER BY created_at",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "artifact_type": r["artifact_type"],
                "title": r["title"],
                "uri": r["uri"],
                "created_by_agent": r["created_by_agent"],
                "work_item_id": str(r["work_item_id"]) if r["work_item_id"] else None,
            }
            for r in rows
        ]

    async def get_latest_graph_snapshot(self, project_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, version, graph_hash, nodes, edges, validation_status, "
                " validation_errors, created_at FROM project_graph_snapshots "
                "WHERE project_id = $1::uuid ORDER BY version DESC LIMIT 1",
                project_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "version": row["version"],
            "graph_hash": row["graph_hash"],
            "nodes": _dec(row["nodes"], []),
            "edges": _dec(row["edges"], []),
            "validation_status": row["validation_status"],
            "validation_errors": _dec(row["validation_errors"], []),
            "created_at": _iso(row["created_at"]),
        }

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------
    async def update_work_item_status(self, work_item_id: str, status: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE project_work_items SET status = $2, updated_at = now(), "
                " completed_at = CASE WHEN $2 = 'completed' THEN now() ELSE completed_at END "
                f"WHERE id = $1::uuid RETURNING {self._WORK_ITEM_COLS}, project_id",
                work_item_id,
                status,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        item = self._work_item_row(row)
        item["project_id"] = str(row["project_id"])
        return item

    async def update_project_status(self, project_id: str, status: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE projects SET status = $2, updated_at = now(), "
                " completed_at = CASE WHEN $2 IN ('accepted','cancelled','failed') "
                "   THEN now() ELSE completed_at END "
                "WHERE id = $1::uuid RETURNING id, status",
                project_id,
                status,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return {"id": str(row["id"]), "status": row["status"]} if row else None

    async def compute_project_progress(self, project_id: str) -> dict:
        conn = await self._connect()
        try:
            wi = await conn.fetchrow(
                "SELECT count(*) AS total, "
                " count(*) FILTER (WHERE status = 'completed') AS completed, "
                " count(*) FILTER (WHERE status = 'blocked') AS blocked, "
                " count(*) FILTER (WHERE status IN ('in_progress','review')) AS active "
                "FROM project_work_items WHERE project_id = $1::uuid",
                project_id,
            )
            ac = await conn.fetchrow(
                "SELECT count(*) FILTER (WHERE required) AS required_total, "
                " count(*) FILTER (WHERE required AND status = 'satisfied') AS required_satisfied "
                "FROM project_acceptance_criteria WHERE project_id = $1::uuid",
                project_id,
            )
        finally:
            await conn.close()
        total = int(wi["total"] or 0)
        completed = int(wi["completed"] or 0)
        pct = round((completed / total) * 100, 1) if total else 0.0
        return {
            "work_items_total": total,
            "work_items_completed": completed,
            "work_items_blocked": int(wi["blocked"] or 0),
            "work_items_active": int(wi["active"] or 0),
            "completion_percent": pct,
            "required_acceptance_total": int(ac["required_total"] or 0),
            "required_acceptance_satisfied": int(ac["required_satisfied"] or 0),
        }

    async def counts(self) -> dict[str, int]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT count(*) AS total_projects, "
                " count(*) FILTER (WHERE status = 'planned') AS planned_count, "
                " count(*) FILTER (WHERE status = 'draft') AS draft_count "
                "FROM projects"
            )
        finally:
            await conn.close()
        return {k: int(row[k] or 0) for k in row.keys()}


__all__ = ["ProjectPlanningStore", "DEFAULT_DATABASE_URL"]
