"""Stage 45 -- in-memory fake ProjectPlanningStore for unit tests.

Implements the same async surface that ``plan_project`` and the
operations API use, backed by dicts. No DB, no asyncpg.
"""

from __future__ import annotations

import uuid


class FakeProjectStore:
    def __init__(self) -> None:
        self.projects: dict[str, dict] = {}
        self.briefs: dict[str, dict] = {}
        self.stories: dict[str, list] = {}
        self.milestones: dict[str, list] = {}
        self.work_items: dict[str, list] = {}
        self.dependencies: dict[str, list] = {}
        self.acceptance: dict[str, list] = {}
        self.risks: dict[str, list] = {}
        self.snapshots: dict[str, list] = {}
        self.artifacts: dict[str, list] = {}
        self._wi_by_id: dict[str, dict] = {}

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    async def create_project(self, project) -> dict:
        pid = self._id()
        self.projects[pid] = {
            "id": pid,
            "title": project.title,
            "summary": project.summary,
            "source_task_id": project.source_task_id,
            "request_source": project.request_source,
            "requester": project.requester,
            "project_type": project.project_type,
            "status": project.status,
            "autonomy_level": project.autonomy_level,
            "risk_level": project.risk_level,
            "created_at": "2026-06-14T00:00:00+00:00",
            "updated_at": "2026-06-14T00:00:00+00:00",
            "completed_at": None,
            "metadata": dict(project.metadata or {}),
        }
        return {"id": pid, "status": project.status, "created_at": "2026-06-14T00:00:00+00:00"}

    async def create_project_brief(self, project_id, brief) -> str:
        bid = self._id()
        self.briefs[project_id] = {
            "id": bid,
            "version": brief.version,
            "problem_statement": brief.problem_statement,
            "goal": brief.goal,
            "scope": list(brief.scope),
            "non_scope": list(brief.non_scope),
            "assumptions": list(brief.assumptions),
            "constraints": list(brief.constraints),
            "stakeholders": list(brief.stakeholders),
            "success_metrics": list(brief.success_metrics),
            "created_by_agent": brief.created_by_agent,
            "created_at": "2026-06-14T00:00:00+00:00",
            "metadata": dict(brief.metadata or {}),
        }
        return bid

    async def create_user_stories(self, project_id, stories) -> int:
        self.stories[project_id] = [
            {
                "story_key": s.story_key,
                "actor": s.actor,
                "need": s.need,
                "benefit": s.benefit,
                "priority": s.priority,
                "status": s.status,
                "metadata": {},
            }
            for s in stories
        ]
        return len(stories)

    async def create_milestones(self, project_id, milestones) -> dict:
        out = {}
        rows = []
        for m in milestones:
            mid = self._id()
            out[m.milestone_key] = mid
            rows.append(
                {
                    "id": mid,
                    "milestone_key": m.milestone_key,
                    "title": m.title,
                    "description": m.description,
                    "order_index": m.order_index,
                    "status": m.status,
                }
            )
        self.milestones[project_id] = rows
        return out

    async def create_work_items(self, project_id, work_items, *, milestone_ids=None) -> dict:
        out = {}
        rows = []
        for w in work_items:
            wid = self._id()
            out[w.work_item_key] = wid
            row = {
                "id": wid,
                "work_item_key": w.work_item_key,
                "title": w.title,
                "description": w.description,
                "work_type": w.work_type,
                "assigned_agent_role": w.assigned_agent_role,
                "status": w.status,
                "priority": w.priority,
                "estimated_effort": w.estimated_effort,
                "risk_level": w.risk_level,
                "dispatch_policy": w.dispatch_policy,
                "milestone_id": (milestone_ids or {}).get(w.milestone_key),
                "created_at": "2026-06-14T00:00:00+00:00",
                "updated_at": "2026-06-14T00:00:00+00:00",
                "completed_at": None,
                "project_id": project_id,
            }
            rows.append(row)
            self._wi_by_id[wid] = row
        self.work_items[project_id] = rows
        return out

    async def create_dependencies(self, project_id, dependencies, *, work_item_ids) -> int:
        rows = []
        seen = set()
        for d in dependencies:
            a = work_item_ids.get(d.work_item_key)
            b = work_item_ids.get(d.depends_on_work_item_key)
            if not a or not b or a == b or (a, b) in seen:
                continue
            seen.add((a, b))
            rows.append(
                {
                    "id": self._id(),
                    "work_item_id": a,
                    "depends_on_work_item_id": b,
                    "dependency_type": d.dependency_type,
                }
            )
        self.dependencies[project_id] = rows
        return len(rows)

    async def create_acceptance_criteria(self, project_id, criteria, *, work_item_ids=None) -> int:
        work_item_ids = work_item_ids or {}
        self.acceptance[project_id] = [
            {
                "id": self._id(),
                "criterion_key": c.criterion_key,
                "description": c.description,
                "verification_method": c.verification_method,
                "status": c.status,
                "required": c.required,
                "work_item_id": work_item_ids.get(c.work_item_key) if c.work_item_key else None,
            }
            for c in criteria
        ]
        return len(criteria)

    async def create_risks(self, project_id, risks) -> int:
        self.risks[project_id] = [
            {
                "risk_key": r.risk_key,
                "title": r.title,
                "description": r.description,
                "severity": r.severity,
                "likelihood": r.likelihood,
                "mitigation": r.mitigation,
                "owner_agent_role": r.owner_agent_role,
                "status": r.status,
            }
            for r in risks
        ]
        return len(risks)

    async def create_graph_snapshot(
        self,
        project_id,
        *,
        version,
        graph_hash,
        nodes,
        edges,
        validation_status,
        validation_errors,
        created_by_agent="project-planner-agent",
        metadata=None,
    ) -> str:
        sid = self._id()
        self.snapshots.setdefault(project_id, []).append(
            {
                "id": sid,
                "version": version,
                "graph_hash": graph_hash,
                "nodes": nodes,
                "edges": edges,
                "validation_status": validation_status,
                "validation_errors": validation_errors,
                "created_at": "2026-06-14T00:00:00+00:00",
            }
        )
        return sid

    async def create_artifacts(self, project_id, artifacts, *, work_item_ids=None) -> int:
        work_item_ids = work_item_ids or {}
        self.artifacts.setdefault(project_id, []).extend(
            {
                "artifact_type": a.artifact_type,
                "title": a.title,
                "uri": a.uri,
                "created_by_agent": a.created_by_agent,
                "work_item_id": work_item_ids.get(a.work_item_key) if a.work_item_key else None,
            }
            for a in artifacts
        )
        return len(artifacts)

    async def update_project_status(self, project_id, status) -> dict | None:
        if project_id in self.projects:
            self.projects[project_id]["status"] = status
            return {"id": project_id, "status": status}
        return None

    # ---- read ----
    async def get_project(self, project_id):
        return self.projects.get(project_id)

    async def list_projects(self, *, status=None, limit=100):
        rows = list(self.projects.values())
        if status:
            rows = [r for r in rows if r["status"] == status]
        return rows[:limit]

    async def get_brief(self, project_id):
        return self.briefs.get(project_id)

    async def list_user_stories(self, project_id):
        return self.stories.get(project_id, [])

    async def list_milestones(self, project_id):
        return self.milestones.get(project_id, [])

    async def list_work_items(self, project_id, *, status=None):
        rows = self.work_items.get(project_id, [])
        if status:
            rows = [r for r in rows if r["status"] == status]
        return rows

    async def get_work_item(self, work_item_id):
        return self._wi_by_id.get(work_item_id)

    async def list_dependencies(self, project_id):
        return self.dependencies.get(project_id, [])

    async def list_work_item_dependencies(self, work_item_id):
        for rows in self.dependencies.values():
            matches = [r for r in rows if r["work_item_id"] == work_item_id]
            if matches:
                return matches
        return []

    async def list_acceptance_criteria(self, project_id, *, work_item_id=None):
        rows = self.acceptance.get(project_id, [])
        if work_item_id:
            rows = [r for r in rows if r["work_item_id"] == work_item_id]
        return rows

    async def list_risks(self, project_id):
        return self.risks.get(project_id, [])

    async def list_artifacts(self, project_id):
        return self.artifacts.get(project_id, [])

    async def get_latest_graph_snapshot(self, project_id):
        rows = self.snapshots.get(project_id, [])
        return rows[-1] if rows else None

    async def update_work_item_status(self, work_item_id, status):
        row = self._wi_by_id.get(work_item_id)
        if row is None:
            return None
        row["status"] = status
        return row

    async def compute_project_progress(self, project_id):
        rows = self.work_items.get(project_id, [])
        total = len(rows)
        completed = len([r for r in rows if r["status"] == "completed"])
        return {
            "work_items_total": total,
            "work_items_completed": completed,
            "work_items_blocked": 0,
            "work_items_active": 0,
            "completion_percent": round((completed / total) * 100, 1) if total else 0.0,
            "required_acceptance_total": 0,
            "required_acceptance_satisfied": 0,
        }
