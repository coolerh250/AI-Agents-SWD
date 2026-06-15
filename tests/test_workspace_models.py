"""Stage 47 -- workspace operator Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.workspace_operator.models import (
    CodeWorkspace,
    WorkspaceExecutionRequest,
    WorkspaceExecutionResult,
    WorkspaceFile,
)


def test_code_workspace_defaults_are_controlled_only() -> None:
    ws = CodeWorkspace(workspace_key="ws-1", workspace_root="/tmp/aiagents-workspaces/ws-1")
    assert ws.repo_write_enabled is False
    assert ws.github_write_enabled is False
    assert ws.deployment_enabled is False
    assert ws.real_llm_enabled is False
    assert ws.production_executed is False
    assert ws.generation_mode == "deterministic_template"


def test_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        WorkspaceFile(relative_path="a.py", unexpected="x")


def test_execution_request_and_result_defaults() -> None:
    req = WorkspaceExecutionRequest(project_id="p1")
    assert req.controlled_only is True
    assert req.execution_type == "fastapi_todo_generation"
    res = WorkspaceExecutionResult(project_id="p1")
    assert res.production_executed is False
    assert res.github_write_performed is False
    assert res.repo_write_performed is False
    assert res.deployment_performed is False
    assert res.real_llm_used is False
