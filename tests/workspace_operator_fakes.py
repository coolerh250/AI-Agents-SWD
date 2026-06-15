"""Stage 47 -- in-memory fakes + helpers for workspace operator tests."""

from __future__ import annotations

import uuid


def _id() -> str:
    return str(uuid.uuid4())


async def setup_reviewed_project(*, graph_validation_status: str = "valid"):
    """Plan + design-review a FastAPI Todo project into fakes.

    Returns (project_id, project_store, review_store) where the design review
    decision is planning_only with no blocking findings (controlled workspace
    execution is allowed).
    """
    from design_review_fakes import (
        FakeDesignReviewStore,
        FakeDiscussionStore,
        populate_project_store,
    )
    from project_planning_fakes import FakeProjectStore

    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)
    # Force the project_type so the operator template resolves to FastAPI Todo.
    project_store.projects[project_id]["project_type"] = "fastapi_todo_service"
    if graph_validation_status != "valid":
        for snap in project_store.snapshots.get(project_id, []):
            snap["validation_status"] = graph_validation_status

    review_store = FakeDesignReviewStore()
    from shared.sdk.design_review import run_design_review

    await run_design_review(
        project_id=project_id,
        project_store=project_store,
        discussion_store=FakeDiscussionStore(),
        review_store=review_store,
        emit_events=False,
    )
    return project_id, project_store, review_store


class FakeWorkspaceStore:
    def __init__(self) -> None:
        self.workspaces: dict[str, dict] = {}
        self.files: dict[str, list] = {}
        self.operations: dict[str, list] = {}
        self.test_runs: dict[str, list] = {}
        self.diffs: dict[str, dict] = {}
        self.artifacts: dict[str, list] = {}
        self.links: dict[str, list] = {}  # project_id -> rows
        self._order: list[str] = []

    async def create_workspace(self, ws) -> str:
        wid = _id()
        self.workspaces[wid] = {
            "workspace_id": wid,
            "workspace_key": ws.workspace_key,
            "workspace_type": ws.workspace_type,
            "workspace_root": ws.workspace_root,
            "status": ws.status,
            "generation_mode": ws.generation_mode,
            "project_id": ws.project_id,
            "design_review_session_id": ws.design_review_session_id,
            "repo_write_enabled": ws.repo_write_enabled,
            "github_write_enabled": ws.github_write_enabled,
            "deployment_enabled": ws.deployment_enabled,
            "real_llm_enabled": ws.real_llm_enabled,
            "production_executed": ws.production_executed,
            "created_by_agent": ws.created_by_agent,
            "created_at": "2026-06-15T00:00:00+00:00",
            "completed_at": None,
            "metadata": dict(ws.metadata or {}),
        }
        self._order.insert(0, wid)
        return wid

    async def update_workspace_status(self, workspace_id, status, *, completed=False) -> None:
        if workspace_id in self.workspaces:
            self.workspaces[workspace_id]["status"] = status
            if completed:
                self.workspaces[workspace_id]["completed_at"] = "2026-06-15T00:00:01+00:00"

    async def record_workspace_file(self, workspace_id, f, *, project_id=None) -> str:
        self.files.setdefault(workspace_id, []).append(_file_dict(f))
        return _id()

    async def record_workspace_files(self, workspace_id, files, *, project_id=None) -> int:
        self.files.setdefault(workspace_id, []).extend(_file_dict(f) for f in files)
        return len(files)

    async def record_operation(self, workspace_id, op, *, project_id=None) -> str:
        oid = _id()
        self.operations.setdefault(workspace_id, []).append(
            {
                "operation_type": op.operation_type,
                "status": op.status,
                "command": op.command,
                "exit_code": op.exit_code,
                "output_summary": op.output_summary,
            }
        )
        return oid

    async def record_test_run(self, workspace_id, run, *, project_id=None) -> str:
        self.test_runs.setdefault(workspace_id, []).append(
            {
                "test_type": run.test_type,
                "command": run.command,
                "status": run.status,
                "exit_code": run.exit_code,
                "tests_total": run.tests_total,
                "tests_passed": run.tests_passed,
                "tests_failed": run.tests_failed,
                "duration_ms": run.duration_ms,
                "output_summary": run.output_summary,
                "report_path": run.report_path,
            }
        )
        return _id()

    async def record_diff_summary(self, workspace_id, diff, *, project_id=None) -> str:
        did = _id()
        self.diffs[workspace_id] = {
            "id": did,
            "changed_files_count": diff.changed_files_count,
            "created_files_count": diff.created_files_count,
            "modified_files_count": diff.modified_files_count,
            "deleted_files_count": diff.deleted_files_count,
            "diff_summary": diff.diff_summary,
            "risk_summary": diff.risk_summary,
            "test_summary": diff.test_summary,
            "generated_at": "2026-06-15T00:00:01+00:00",
        }
        return did

    async def record_artifact(self, workspace_id, artifact, *, project_id=None) -> str:
        aid = _id()
        self.artifacts.setdefault(workspace_id, []).append(
            {
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "uri": artifact.uri,
                "created_by_agent": artifact.created_by_agent,
                "content": artifact.content,
            }
        )
        return aid

    async def link_work_item_execution(self, project_id, workspace_id, link) -> str:
        lid = _id()
        self.links.setdefault(project_id, [])
        self.links[project_id] = [
            r
            for r in self.links[project_id]
            if not (r["work_item_id"] == link.work_item_id and r["workspace_id"] == workspace_id)
        ]
        self.links[project_id].append(
            {
                "work_item_id": link.work_item_id,
                "workspace_id": workspace_id,
                "execution_status": link.execution_status,
                "evidence_artifact_id": link.evidence_artifact_id,
                "work_item_key": link.work_item_key,
            }
        )
        return lid

    # ---- reads ----
    async def get_workspace(self, workspace_id):
        return self.workspaces.get(workspace_id)

    async def list_workspaces(self, *, project_id=None, limit=100):
        rows = [self.workspaces[w] for w in self._order]
        if project_id:
            rows = [r for r in rows if r["project_id"] == project_id]
        return rows[:limit]

    async def get_latest_workspace(self, project_id=None):
        rows = await self.list_workspaces(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def list_workspace_files(self, workspace_id):
        return sorted(self.files.get(workspace_id, []), key=lambda f: f["relative_path"])

    async def list_operations(self, workspace_id):
        return self.operations.get(workspace_id, [])

    async def list_test_runs(self, workspace_id):
        return self.test_runs.get(workspace_id, [])

    async def get_diff_summary(self, workspace_id):
        return self.diffs.get(workspace_id)

    async def list_artifacts(self, workspace_id):
        return [
            {k: v for k, v in a.items() if k != "content"}
            for a in self.artifacts.get(workspace_id, [])
        ]

    async def list_work_item_links(self, project_id):
        return self.links.get(project_id, [])

    async def get_workspace_report(self, workspace_id):
        ws = self.workspaces.get(workspace_id)
        links = []
        if ws and ws.get("project_id"):
            links = [
                link
                for link in self.links.get(ws["project_id"], [])
                if link["workspace_id"] == workspace_id
            ]
        return {
            "workspace": ws,
            "files": await self.list_workspace_files(workspace_id),
            "files_count": len(self.files.get(workspace_id, [])),
            "test_runs": await self.list_test_runs(workspace_id),
            "diff_summary": self.diffs.get(workspace_id),
            "artifacts": await self.list_artifacts(workspace_id),
            "work_item_links": links,
            "production_executed": False,
        }

    async def compute_workspace_summary(self, project_id):
        ws = await self.get_latest_workspace(project_id)
        if not ws:
            return {
                "project_id": project_id,
                "latest_workspace_id": None,
                "latest_workspace_status": None,
                "production_executed": False,
            }
        tests = await self.list_test_runs(ws["workspace_id"])
        pytest_run = next((t for t in tests if t["test_type"] == "pytest"), None)
        files = self.files.get(ws["workspace_id"], [])
        return {
            "project_id": project_id,
            "latest_workspace_id": ws["workspace_id"],
            "latest_workspace_status": ws["status"],
            "latest_workspace_tests_status": pytest_run["status"] if pytest_run else None,
            "latest_workspace_static_check_status": "passed",
            "latest_workspace_generated_files_count": len(files),
            "production_executed": False,
        }


def _file_dict(f) -> dict:
    return {
        "relative_path": f.relative_path,
        "file_type": f.file_type,
        "operation": f.operation,
        "content_hash": f.content_hash,
        "size_bytes": f.size_bytes,
        "summary": f.summary,
    }
