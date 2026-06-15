# Real Repo Workspace Operator v1 (Stage 47)

## Purpose

Turn a reviewed project graph into a **controlled, executable, testable**
software project inside an allowlisted workspace — without touching the real
repo, GitHub, or any deployment target. This is the bridge from
"reviewed project plan" (Steps 43–44) to "controlled code generation
workspace".

It is **controlled-only / planning-only**:

* no real LLM, no real GitHub, no PR, no merge, no deploy, no production write;
* no real Slack / Discord / Telegram delivery;
* `production_executed` is always `false`.

## Controlled workspace model

A `code_workspaces` row (extended from the Stage 28 table) represents one
controlled execution. Each execution:

1. validates the design-review preconditions (graph valid, decision in
   `planning_only` / `go_with_findings` / `go`, no blocking/critical findings,
   pre-execution gate not failed);
2. creates a clean workspace directory **under an allowlisted root**
   (`/tmp/aiagents-workspaces` by default, or `.generated-workspaces/`);
3. generates a deterministic FastAPI Todo project;
4. runs `pytest` and static checks (`ruff` if available, `compileall`);
5. collects a diff summary, builds artifacts, and maps work-item execution
   links.

## Execution input / output

Input (`WorkspaceExecutionRequest`): `project_id`,
`design_review_session_id?`, `graph_snapshot_id?`, `execution_type`
(`fastapi_todo_generation`), `workspace_type` (`generated_project`),
`controlled_only=true`.

Output (`WorkspaceExecutionResult`): `workspace_id`, `workspace_root`,
`status`, `generated_files_count`, `tests_status`, `static_check_status`,
`diff_summary_id`, `artifacts_count`, `work_item_links_count`, and the safety
flags `controlled_only=true`, `production_executed=false`,
`github_write_performed=false`, `repo_write_performed=false`,
`deployment_performed=false`, `real_llm_used=false`.

## Supported template

`fastapi_todo_service` — see
[fastapi-todo-workspace-template.md](fastapi-todo-workspace-template.md).

## Generated files

At least eight files: `pyproject.toml`, `README.md`, `app/__init__.py`,
`app/main.py`, `app/database.py`, `app/models.py`, `app/schemas.py`,
`app/crud.py`, `tests/test_todos.py` (plus `requirements.txt`, `.gitignore`,
`tests/__init__.py`).

## Test execution

`pytest -q` runs in the workspace. If the FastAPI/httpx/pytest test
dependencies are not importable by the operator's interpreter, the run is
classified `skipped` with a documented reason rather than `failed`.
`compileall` always runs as an offline fallback; `ruff` runs when available.

## Diff summary & work-item execution links

The diff summary counts created/modified/deleted files (everything is
`created` for a fresh `generated_project`). Work-item execution links map each
`project_work_items` row to a status: requirement/architecture/documentation →
`generated`; backend/database → `tested` (when tests pass); QA-001 → `tested`;
QA-002 → `passed`/`failed`; delivery (DEL-*) → `pending` (Step 47).

## Limitations

* One template (`fastapi_todo_service`); no general-purpose code generation.
* No auto-fix loop this stage (failing tests are reported, not fixed).
* Generated workspaces are operator review artifacts only — never committed.

## Safety constraints

See [controlled-workspace-safety.md](controlled-workspace-safety.md).
