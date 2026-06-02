"""Dataclasses mirroring the Stage 28 tables.

Plain dataclasses (not pydantic). ``to_dict`` powers /operations/* JSON
shape and the test fixtures' deep compares.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeWorkspace:
    """One row from ``code_workspaces``."""

    workspace_id: str
    task_id: str
    workflow_id: str | None = None
    work_item_id: str | None = None
    execution_mode: str = "simple_task"
    status: str = "created"
    base_commit: str = ""
    branch_name: str = ""
    workspace_path: str = ""
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    generator_mode: str = "deterministic_template"
    blocked_reason: str = ""
    created_by_agent: str = "development-agent"
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "work_item_id": self.work_item_id,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "base_commit": self.base_commit,
            "branch_name": self.branch_name,
            "workspace_path": self.workspace_path,
            "allowed_paths": list(self.allowed_paths),
            "denied_paths": list(self.denied_paths),
            "generator_mode": self.generator_mode,
            "blocked_reason": self.blocked_reason,
            "created_by_agent": self.created_by_agent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CodeChangeArtifact:
    """One row from ``code_change_artifacts`` — one file change."""

    artifact_id: str
    task_id: str
    workflow_id: str | None
    workspace_id: str
    file_path: str
    change_type: str = "create"
    before_sha: str | None = None
    after_sha: str | None = None
    diff_summary: str = ""
    diff_text: str = ""
    generated_content_preview: str = ""
    validation_status: str = "pending"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "file_path": self.file_path,
            "change_type": self.change_type,
            "before_sha": self.before_sha,
            "after_sha": self.after_sha,
            "diff_summary": self.diff_summary,
            "diff_text": self.diff_text,
            "generated_content_preview": self.generated_content_preview,
            "validation_status": self.validation_status,
            "created_at": self.created_at,
        }


@dataclass
class PRDraftArtifact:
    """One row from ``pr_draft_artifacts`` — the operator-facing package."""

    pr_draft_id: str
    task_id: str
    workflow_id: str | None
    workspace_id: str
    title: str = ""
    body: str = ""
    changed_files: list[Any] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    rollback_plan: str = ""
    github_dry_run_result: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_draft_id": self.pr_draft_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "body": self.body,
            "changed_files": list(self.changed_files),
            "test_results": dict(self.test_results),
            "risk_assessment": dict(self.risk_assessment),
            "rollback_plan": self.rollback_plan,
            "github_dry_run_result": dict(self.github_dry_run_result),
            "status": self.status,
            "created_at": self.created_at,
        }
