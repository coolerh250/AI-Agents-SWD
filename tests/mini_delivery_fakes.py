"""Stage 48 -- in-memory fakes + helpers for mini delivery pilot tests."""

from __future__ import annotations

import uuid


def _id() -> str:
    return str(uuid.uuid4())


async def run_fake_pilot(tmp_path, monkeypatch, *, request=None):
    """Run a full controlled mini delivery pilot against in-memory fakes.

    Returns (result, stores) where stores is a dict of the fake stores used.
    """
    from design_review_fakes import FakeDesignReviewStore, FakeDiscussionStore
    from project_planning_fakes import FakeProjectStore
    from workspace_operator_fakes import FakeWorkspaceStore

    from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotRequest, run_mini_delivery_pilot

    root = tmp_path / "aiagents-workspaces"
    root.mkdir(exist_ok=True)
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))

    stores = {
        "project": FakeProjectStore(),
        "discussion": FakeDiscussionStore(),
        "review": FakeDesignReviewStore(),
        "workspace": FakeWorkspaceStore(),
        "pilot": FakeMiniDeliveryPilotStore(),
    }
    result = await run_mini_delivery_pilot(
        request=request or MiniDeliveryPilotRequest(),
        project_store=stores["project"],
        discussion_store=stores["discussion"],
        review_store=stores["review"],
        workspace_store=stores["workspace"],
        pilot_store=stores["pilot"],
        workspace_base_root=str(root),
        emit_events=False,
    )
    return result, stores


class FakeMiniDeliveryPilotStore:
    def __init__(self) -> None:
        self.pilots: dict[str, dict] = {}
        self.steps: dict[str, list] = {}
        self.acceptance: dict[str, list] = {}
        self.qa: dict[str, dict] = {}
        self.safety: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}
        self.artifacts: dict[str, list] = {}
        self._order: list[str] = []

    async def create_pilot(self, pilot) -> str:
        pid = _id()
        self.pilots[pid] = {
            "id": pid,
            "pilot_key": pilot.pilot_key,
            "pilot_type": pilot.pilot_type,
            "status": pilot.status,
            "project_id": pilot.project_id,
            "workspace_id": pilot.workspace_id,
            "design_review_session_id": pilot.design_review_session_id,
            "controlled_only": pilot.controlled_only,
            "production_executed": pilot.production_executed,
            "created_by_agent": pilot.created_by_agent,
            "created_at": "2026-06-15T00:00:00+00:00",
            "completed_at": None,
            "metadata": dict(pilot.metadata or {}),
        }
        self._order.insert(0, pid)
        return pid

    async def update_pilot_status(
        self,
        pilot_id,
        status,
        *,
        completed=False,
        project_id=None,
        workspace_id=None,
        design_review_session_id=None,
        graph_snapshot_id=None,
    ) -> None:
        p = self.pilots.get(pilot_id)
        if not p:
            return
        p["status"] = status
        if completed:
            p["completed_at"] = "2026-06-15T00:00:02+00:00"
        if project_id:
            p["project_id"] = project_id
        if workspace_id:
            p["workspace_id"] = workspace_id
        if design_review_session_id:
            p["design_review_session_id"] = design_review_session_id

    async def create_step(self, pilot_id, step, *, project_id=None) -> str:
        self.steps.setdefault(pilot_id, []).append(
            {
                "step_key": step.step_key,
                "step_type": step.step_type,
                "status": step.status,
                "evidence_refs": list(step.evidence_refs),
                "summary": step.summary,
                "started_at": "2026-06-15T00:00:01+00:00",
                "completed_at": "2026-06-15T00:00:01+00:00",
            }
        )
        return _id()

    async def create_acceptance_evaluations(self, pilot_id, project_id, evaluations) -> int:
        self.acceptance[pilot_id] = [
            {
                "acceptance_criterion_id": e.acceptance_criterion_id,
                "work_item_id": e.work_item_id,
                "evaluation_status": e.evaluation_status,
                "evidence_type": e.evidence_type,
                "evidence_ref": dict(e.evidence_ref),
                "rationale_summary": e.rationale_summary,
                "criterion_key": e.criterion_key,
            }
            for e in evaluations
        ]
        return len(evaluations)

    async def create_qa_report(self, pilot_id, project_id, workspace_id, qa) -> str:
        rid = _id()
        self.qa[pilot_id] = {
            "status": qa.status,
            "tests_total": qa.tests_total,
            "tests_passed": qa.tests_passed,
            "tests_failed": qa.tests_failed,
            "static_checks_status": qa.static_checks_status,
            "findings": list(qa.findings),
            "report_summary": qa.report_summary,
        }
        return rid

    async def create_safety_report(self, pilot_id, project_id, workspace_id, safety) -> str:
        rid = _id()
        self.safety[pilot_id] = {
            "status": safety.status,
            "production_executed_count": safety.production_executed_count,
            "github_write_performed": safety.github_write_performed,
            "pr_created": safety.pr_created,
            "deployment_performed": safety.deployment_performed,
            "real_llm_used": safety.real_llm_used,
            "real_external_delivery_performed": safety.real_external_delivery_performed,
            "repo_root_modified": safety.repo_root_modified,
            "secret_leak_detected": safety.secret_leak_detected,
            "chain_of_thought_persisted": safety.chain_of_thought_persisted,
            "findings": list(safety.findings),
            "report_summary": safety.report_summary,
        }
        return rid

    async def create_delivery_report(self, pilot_id, project_id, workspace_id, report) -> str:
        rid = _id()
        self.reports[pilot_id] = {
            "report_type": report.report_type,
            "status": report.status,
            "title": report.title,
            "executive_summary": report.executive_summary,
            "project_summary": dict(report.project_summary),
            "design_review_summary": dict(report.design_review_summary),
            "workspace_summary": dict(report.workspace_summary),
            "qa_summary": dict(report.qa_summary),
            "acceptance_summary": dict(report.acceptance_summary),
            "safety_summary": dict(report.safety_summary),
            "known_limitations": list(report.known_limitations),
            "next_steps": list(report.next_steps),
            "artifact_refs": list(report.artifact_refs),
        }
        return rid

    async def create_pilot_artifact(self, pilot_id, project_id, artifact) -> str:
        aid = _id()
        self.artifacts.setdefault(pilot_id, []).append(
            {
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "uri": artifact.uri,
                "created_by_agent": artifact.created_by_agent,
            }
        )
        return aid

    # ---- reads ----
    async def get_pilot(self, pilot_id):
        return self.pilots.get(pilot_id)

    async def list_pilots(self, *, project_id=None, limit=100):
        rows = [self.pilots[p] for p in self._order]
        if project_id:
            rows = [r for r in rows if r["project_id"] == project_id]
        return rows[:limit]

    async def get_latest_pilot(self, project_id=None):
        rows = await self.list_pilots(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def list_steps(self, pilot_id):
        return self.steps.get(pilot_id, [])

    async def list_acceptance_evaluations(self, pilot_id):
        return self.acceptance.get(pilot_id, [])

    async def get_acceptance_summary(self, pilot_id):
        rows = self.acceptance.get(pilot_id, [])
        return {
            "total": len(rows),
            "satisfied": sum(1 for r in rows if r["evaluation_status"] == "satisfied"),
            "failed": sum(1 for r in rows if r["evaluation_status"] == "failed"),
            "pending": sum(1 for r in rows if r["evaluation_status"] == "pending"),
            "waived": sum(1 for r in rows if r["evaluation_status"] == "waived"),
        }

    async def get_qa_report(self, pilot_id):
        return self.qa.get(pilot_id)

    async def get_safety_report(self, pilot_id):
        return self.safety.get(pilot_id)

    async def get_pilot_report(self, pilot_id):
        return self.reports.get(pilot_id)

    async def list_artifacts(self, pilot_id):
        return self.artifacts.get(pilot_id, [])

    async def get_pilot_timeline(self, pilot_id):
        return {
            "pilot": self.pilots.get(pilot_id),
            "steps": self.steps.get(pilot_id, []),
            "step_count": len(self.steps.get(pilot_id, [])),
            "production_executed": False,
        }
