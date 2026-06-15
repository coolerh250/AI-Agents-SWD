"""Stage 47 -- no chain-of-thought / raw-prompt persistence anywhere."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.workspace_operator.artifact_builder import build_implementation_summary
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.file_manifest import build_manifest

_REPO = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("chain_of_thought", "raw_prompt", "transcript")


def _strip_sql_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def test_migration_has_no_chain_of_thought_columns() -> None:
    sql = (_REPO / "migrations" / "019_controlled_workspace_operator.sql").read_text(
        encoding="utf-8"
    )
    code = _strip_sql_comments(sql).lower()
    for term in _FORBIDDEN:
        assert term not in code, term


def test_models_have_no_chain_of_thought_fields() -> None:
    from shared.sdk.workspace_operator import models

    for cls_name in ("CodeWorkspace", "WorkspaceArtifact", "WorkspaceExecutionResult"):
        fields = getattr(models, cls_name).model_fields
        for term in _FORBIDDEN:
            assert term not in fields


def test_implementation_artifact_carries_only_summaries() -> None:
    manifest = build_manifest(build_fastapi_todo_files())
    art = build_implementation_summary(
        project_id="p1",
        workspace_key="ws-1",
        template="fastapi_todo_service",
        manifest=manifest,
        tests_status="passed",
        static_check_status="passed",
    )
    for term in _FORBIDDEN:
        assert term not in art.content
