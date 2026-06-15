"""Stage 47 -- Real Repo Workspace Operator SDK (controlled-only)."""

from __future__ import annotations

from shared.sdk.workspace_operator.audit_events import (
    WORKSPACE_DECISION_TYPES,
    safe_workspace_artifact_refs,
)
from shared.sdk.workspace_operator.diff_summary import build_diff_summary
from shared.sdk.workspace_operator.events import (
    EVENT_PROJECT_WORKSPACE_EXECUTION_REQUESTED,
    EVENT_WORKSPACE_EXECUTION_COMPLETED,
    EVENT_WORKSPACE_EXECUTION_FAILED,
    STREAM_WORKSPACE_EVENTS,
    STREAM_WORKSPACE_EXECUTION,
    WORKSPACE_NOTIFICATION_EVENTS,
)
from shared.sdk.workspace_operator.fastapi_todo_generator import (
    EXECUTION_TYPE,
    build_fastapi_todo_files,
)
from shared.sdk.workspace_operator.file_manifest import build_manifest
from shared.sdk.workspace_operator.models import (
    CodeWorkspace,
    WorkItemExecutionLink,
    WorkspaceArtifact,
    WorkspaceDiffSummary,
    WorkspaceExecutionRequest,
    WorkspaceExecutionResult,
    WorkspaceFile,
    WorkspaceOperation,
    WorkspaceTestRun,
)
from shared.sdk.workspace_operator.path_safety import (
    WorkspacePathError,
    allowed_roots,
    safe_join,
    validate_workspace_root,
)
from shared.sdk.workspace_operator.report_builder import build_workspace_report
from shared.sdk.workspace_operator.runner import (
    OPERATOR_AGENT,
    check_preconditions,
    run_workspace_execution,
)
from shared.sdk.workspace_operator.safety import (
    contains_secret,
    redact,
    workspace_safety_flags,
)
from shared.sdk.workspace_operator.store import WorkspaceOperatorStore
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager

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
    "WorkspacePathError",
    "allowed_roots",
    "validate_workspace_root",
    "safe_join",
    "WorkspaceManager",
    "build_fastapi_todo_files",
    "EXECUTION_TYPE",
    "build_manifest",
    "build_diff_summary",
    "build_workspace_report",
    "WorkspaceOperatorStore",
    "run_workspace_execution",
    "check_preconditions",
    "OPERATOR_AGENT",
    "contains_secret",
    "redact",
    "workspace_safety_flags",
    "WORKSPACE_DECISION_TYPES",
    "safe_workspace_artifact_refs",
    "WORKSPACE_NOTIFICATION_EVENTS",
    "STREAM_WORKSPACE_EXECUTION",
    "STREAM_WORKSPACE_EVENTS",
    "EVENT_WORKSPACE_EXECUTION_COMPLETED",
    "EVENT_WORKSPACE_EXECUTION_FAILED",
    "EVENT_PROJECT_WORKSPACE_EXECUTION_REQUESTED",
]
