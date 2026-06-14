"""Stage 46 -- in-memory fake discussion + design review stores for tests."""

from __future__ import annotations

import uuid


def _id() -> str:
    return str(uuid.uuid4())


def build_fastapi_todo_context(graph_validation_status: str = "valid"):
    """Build a ReviewContext from the real FastAPI Todo project template."""
    from shared.sdk.design_review.models import ReviewContext
    from shared.sdk.project_planning import build_brief, build_task_graph

    brief = build_brief(
        "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
    )
    g = build_task_graph(brief, project_type="fastapi_todo_service")
    keyid = {w.work_item_key: f"id-{w.work_item_key}" for w in g.work_items}
    work_items = [
        {
            "id": keyid[w.work_item_key],
            "work_item_key": w.work_item_key,
            "title": w.title,
            "work_type": w.work_type,
            "assigned_agent_role": w.assigned_agent_role,
            "dispatch_policy": w.dispatch_policy,
        }
        for w in g.work_items
    ]
    acceptance = [
        {
            "description": c.description,
            "verification_method": c.verification_method,
            "required": c.required,
            "work_item_id": keyid.get(c.work_item_key),
        }
        for c in g.acceptance_criteria
    ]
    deps = [
        {
            "work_item_id": keyid[d.work_item_key],
            "depends_on_work_item_id": keyid[d.depends_on_work_item_key],
        }
        for d in g.dependencies
    ]
    return ReviewContext(
        project_id="p-todo",
        template="fastapi_todo_service",
        brief={
            "scope": brief.scope,
            "non_scope": brief.non_scope,
            "assumptions": brief.assumptions,
            "constraints": brief.constraints,
            "success_metrics": brief.success_metrics,
            "metadata": brief.metadata,
        },
        user_stories=[{"story_key": "US-1"}],
        work_items=work_items,
        dependencies=deps,
        acceptance_criteria=acceptance,
        risks=[],
        graph_validation_status=graph_validation_status,
    )


async def populate_project_store(store, request_text: str | None = None) -> str:
    """Plan a FastAPI Todo project into a FakeProjectStore, return project_id."""
    from shared.sdk.project_planning import PlannerInput, plan_project

    out = await plan_project(
        PlannerInput(
            request_text=request_text
            or "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README"
        ),
        store,
        emit_events=False,
    )
    return out.project_id


class FakeDiscussionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.participants: dict[str, list] = {}
        self.contributions: dict[str, list] = {}
        self.artifacts: dict[str, list] = {}

    async def create_discussion_session(self, session) -> str:
        sid = _id()
        self.sessions[sid] = {
            "id": sid,
            "project_id": session.project_id,
            "session_type": session.session_type,
            "status": session.status,
            "review_mode": session.review_mode,
            "planning_only": session.planning_only,
            "created_by_agent": session.created_by_agent,
            "created_at": "2026-06-14T00:00:00+00:00",
            "completed_at": None,
            "metadata": {},
        }
        return sid

    async def add_participants(self, session_id, participants) -> int:
        self.participants[session_id] = [
            {
                "agent_role": p.agent_role,
                "participation_type": p.participation_type,
                "status": p.status,
            }
            for p in participants
        ]
        return len(participants)

    async def add_contributions(self, session_id, contributions, *, project_id=None) -> int:
        self.contributions[session_id] = [
            {
                "agent_role": c.agent_role,
                "contribution_type": c.contribution_type,
                "summary": c.summary,
                "rationale_summary": c.rationale_summary,
                "confidence": c.confidence,
                "severity": c.severity,
                "related_artifact_refs": list(c.related_artifact_refs),
            }
            for c in contributions
        ]
        return len(contributions)

    async def add_discussion_artifact(self, session_id, artifact, *, project_id=None) -> str:
        aid = _id()
        self.artifacts.setdefault(session_id, []).append(
            {
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "uri": artifact.uri,
                "created_by_agent": artifact.created_by_agent,
                "content": artifact.content,
            }
        )
        return aid

    async def complete_session(self, session_id, status="completed") -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = status
            self.sessions[session_id]["completed_at"] = "2026-06-14T00:00:01+00:00"

    async def get_session(self, session_id):
        return self.sessions.get(session_id)

    async def list_project_discussions(self, project_id):
        return [s for s in self.sessions.values() if s["project_id"] == project_id]

    async def list_participants(self, session_id):
        return self.participants.get(session_id, [])

    async def list_contributions(self, session_id):
        return self.contributions.get(session_id, [])

    async def list_artifacts(self, session_id):
        return [
            {k: v for k, v in a.items() if k != "content"}
            for a in self.artifacts.get(session_id, [])
        ]


class FakeDesignReviewStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.findings: dict[str, list] = {}
        self.decisions: dict[str, list] = {}
        self.gates: dict[str, dict] = {}  # project_id -> {gate_type: row}

    async def create_design_review_session(self, session) -> str:
        sid = _id()
        self.sessions[sid] = {
            "id": sid,
            "project_id": session.project_id,
            "discussion_session_id": session.discussion_session_id,
            "graph_snapshot_id": session.graph_snapshot_id,
            "review_type": session.review_type,
            "status": session.status,
            "decision": session.decision,
            "created_at": "2026-06-14T00:00:00+00:00",
            "completed_at": None,
            "metadata": {},
        }
        return sid

    async def finalize_review_session(self, review_session_id, *, status, decision) -> None:
        if review_session_id in self.sessions:
            self.sessions[review_session_id]["status"] = status
            self.sessions[review_session_id]["decision"] = decision
            self.sessions[review_session_id]["completed_at"] = "2026-06-14T00:00:01+00:00"

    async def add_findings(self, review_session_id, project_id, findings) -> int:
        self.findings[review_session_id] = [
            {
                "finding_key": f.finding_key,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "recommendation": f.recommendation,
                "status": f.status,
                "created_by_agent": f.created_by_agent,
            }
            for f in findings
        ]
        return len(findings)

    async def add_decisions(self, review_session_id, project_id, decisions) -> int:
        self.decisions[review_session_id] = [
            {
                "decision_type": d.decision_type,
                "decision": d.decision,
                "rationale_summary": d.rationale_summary,
                "decided_by": d.decided_by,
                "approval_required": d.approval_required,
                "approval_status": d.approval_status,
            }
            for d in decisions
        ]
        return len(decisions)

    async def upsert_review_gates(self, project_id, review_session_id, gates) -> int:
        self.gates.setdefault(project_id, {})
        for g in gates:
            self.gates[project_id][g.gate_type] = {
                "gate_type": g.gate_type,
                "status": g.status,
                "required": g.required,
                "blocking": g.blocking,
            }
        return len(gates)

    async def get_review(self, review_session_id):
        return self.sessions.get(review_session_id)

    async def list_project_reviews(self, project_id):
        return [s for s in self.sessions.values() if s["project_id"] == project_id]

    async def get_latest_review(self, project_id):
        rows = await self.list_project_reviews(project_id)
        return rows[-1] if rows else None

    async def list_findings(self, review_session_id):
        return self.findings.get(review_session_id, [])

    async def list_decisions(self, review_session_id):
        return self.decisions.get(review_session_id, [])

    async def list_gates(self, project_id):
        return list(self.gates.get(project_id, {}).values())

    async def compute_review_summary(self, project_id):
        review = await self.get_latest_review(project_id)
        gates = await self.list_gates(project_id)
        gates_passed = sum(1 for g in gates if g["status"] in ("passed", "passed_with_findings"))
        findings = await self.list_findings(review["id"]) if review else []
        blocking = len(
            [f for f in findings if f["severity"] in ("high", "critical") and f["status"] == "open"]
        )
        return {
            "project_id": project_id,
            "latest_review_status": review["status"] if review else None,
            "latest_review_decision": review["decision"] if review else None,
            "review_session_id": review["id"] if review else None,
            "findings_count": len(findings),
            "blocking_findings_count": blocking,
            "gates_total": len(gates),
            "gates_passed": gates_passed,
            "gates": gates,
            "planning_only": True,
            "production_executed": False,
        }
