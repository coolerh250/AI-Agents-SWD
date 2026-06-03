"""Dataclasses mirroring the Stage 29 tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QAValidationRun:
    """One row from ``qa_validation_runs``."""

    qa_run_id: str
    task_id: str
    workflow_id: str | None = None
    workspace_id: str | None = None
    pr_draft_id: str | None = None
    status: str = "started"
    validation_scope: str = "workspace"
    qa_agent: str = "qa-agent"
    total_findings: int = 0
    blocking_findings: int = 0
    non_blocking_findings: int = 0
    auto_fix_attempts: int = 0
    max_auto_fix_attempts: int = 2
    final_result: str = "not_applicable"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "qa_run_id": self.qa_run_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "pr_draft_id": self.pr_draft_id,
            "status": self.status,
            "validation_scope": self.validation_scope,
            "qa_agent": self.qa_agent,
            "total_findings": self.total_findings,
            "blocking_findings": self.blocking_findings,
            "non_blocking_findings": self.non_blocking_findings,
            "auto_fix_attempts": self.auto_fix_attempts,
            "max_auto_fix_attempts": self.max_auto_fix_attempts,
            "final_result": self.final_result,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class QAFinding:
    """One row from ``qa_findings``."""

    finding_id: str
    qa_run_id: str
    task_id: str
    workflow_id: str | None
    workspace_id: str | None
    severity: str = "warning"
    category: str = "unknown"
    file_path: str | None = None
    title: str = ""
    description: str = ""
    recommendation: str = ""
    auto_fixable: bool = False
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "qa_run_id": self.qa_run_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "auto_fixable": self.auto_fixable,
            "status": self.status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class AutoFixRequest:
    """One row from ``auto_fix_requests``."""

    fix_request_id: str
    task_id: str
    workflow_id: str | None
    workspace_id: str | None
    qa_run_id: str | None
    finding_ids: list[str] = field(default_factory=list)
    attempt_number: int = 1
    status: str = "requested"
    requested_by: str = "qa-agent"
    reason: str = ""
    fix_strategy: str = "deterministic"
    result: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fix_request_id": self.fix_request_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "qa_run_id": self.qa_run_id,
            "finding_ids": list(self.finding_ids),
            "attempt_number": self.attempt_number,
            "status": self.status,
            "requested_by": self.requested_by,
            "reason": self.reason,
            "fix_strategy": self.fix_strategy,
            "result": dict(self.result),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
