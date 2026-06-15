"""Stage 47 -- Pydantic models for the controlled workspace operator.

Strict validation. No chain-of-thought, no raw prompts, no large file blobs --
only file metadata, operation logs, test results, diff summaries, artifact
references, and work-item execution links.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

WORKSPACE_TYPES = ("generated_project", "repo_copy", "patch_workspace", "sandbox")
WORKSPACE_STATUSES = (
    "created",
    "prepared",
    "generating",
    "generated",
    "testing",
    "tests_passed",
    "tests_failed",
    "summarized",
    "failed",
    "cleaned",
)
GENERATION_MODES = ("deterministic_template", "llm_assisted_disabled", "manual_seed")
FILE_OPERATIONS = ("created", "modified", "deleted", "unchanged")
OPERATION_TYPES = (
    "prepare_workspace",
    "generate_files",
    "run_tests",
    "run_static_checks",
    "collect_diff",
    "summarize",
    "cleanup",
    "failed",
)
OPERATION_STATUSES = ("pending", "running", "completed", "failed", "skipped")
TEST_TYPES = ("pytest", "ruff", "mypy", "static_check", "smoke", "compileall")
TEST_STATUSES = ("passed", "failed", "skipped", "error")
EXECUTION_LINK_STATUSES = ("pending", "generated", "tested", "passed", "failed", "skipped")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodeWorkspace(_Strict):
    workspace_key: str
    workspace_type: str = "generated_project"
    workspace_root: str
    status: str = "created"
    generation_mode: str = "deterministic_template"
    project_id: str | None = None
    design_review_session_id: str | None = None
    source_task_id: str | None = None
    repo_write_enabled: bool = False
    github_write_enabled: bool = False
    deployment_enabled: bool = False
    real_llm_enabled: bool = False
    production_executed: bool = False
    created_by_agent: str = "workspace-operator-agent"
    metadata: dict = Field(default_factory=dict)


class WorkspaceFile(_Strict):
    relative_path: str
    file_type: str | None = None
    operation: str = "created"
    content_hash: str | None = None
    size_bytes: int | None = None
    summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspaceOperation(_Strict):
    operation_type: str
    status: str = "pending"
    command: str | None = None
    exit_code: int | None = None
    output_summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspaceTestRun(_Strict):
    test_type: str
    command: str
    status: str
    exit_code: int | None = None
    tests_total: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    duration_ms: int | None = None
    output_summary: str | None = None
    report_path: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspaceDiffSummary(_Strict):
    changed_files_count: int = 0
    created_files_count: int = 0
    modified_files_count: int = 0
    deleted_files_count: int = 0
    diff_summary: dict = Field(default_factory=dict)
    risk_summary: str | None = None
    test_summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspaceArtifact(_Strict):
    artifact_type: str
    title: str | None = None
    content: dict | None = None
    uri: str | None = None
    created_by_agent: str = "workspace-operator-agent"
    metadata: dict = Field(default_factory=dict)


class WorkItemExecutionLink(_Strict):
    work_item_id: str
    work_item_key: str | None = None
    execution_status: str = "pending"
    evidence_artifact_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspaceExecutionRequest(_Strict):
    project_id: str
    design_review_session_id: str | None = None
    graph_snapshot_id: str | None = None
    execution_type: str = "fastapi_todo_generation"
    workspace_type: str = "generated_project"
    requested_by_agent: str = "workspace-operator-agent"
    controlled_only: bool = True
    source_task_id: str | None = None


class WorkspaceExecutionResult(_Strict):
    project_id: str
    workspace_id: str | None = None
    workspace_key: str | None = None
    workspace_root: str | None = None
    status: str = "failed"
    blocked_reason: str | None = None
    generated_files_count: int = 0
    tests_status: str | None = None
    static_check_status: str | None = None
    diff_summary_id: str | None = None
    artifacts_count: int = 0
    work_item_links_count: int = 0
    # safety flags -- all controlled-only, never real.
    controlled_only: bool = True
    production_executed: bool = False
    github_write_performed: bool = False
    repo_write_performed: bool = False
    deployment_performed: bool = False
    real_llm_used: bool = False
    metadata: dict = Field(default_factory=dict)


__all__ = [
    "CodeWorkspace",
    "WorkspaceFile",
    "WorkspaceOperation",
    "WorkspaceTestRun",
    "WorkspaceDiffSummary",
    "WorkspaceArtifact",
    "WorkItemExecutionLink",
    "WorkspaceExecutionRequest",
    "WorkspaceExecutionResult",
    "WORKSPACE_TYPES",
    "WORKSPACE_STATUSES",
    "GENERATION_MODES",
    "FILE_OPERATIONS",
    "OPERATION_TYPES",
    "OPERATION_STATUSES",
    "TEST_TYPES",
    "TEST_STATUSES",
    "EXECUTION_LINK_STATUSES",
]
