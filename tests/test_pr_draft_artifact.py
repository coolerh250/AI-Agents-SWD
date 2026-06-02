"""Stage 28 — PR draft body / risk / rollback shape tests.

These tests exercise the deterministic generator + the dev-agent PR body
builder so we catch any regression in the operator-facing PR draft text
(must contain Summary / Changed Files / Generated Diff Summary /
Validation Result / Risk Assessment / Rollback Plan / Safety Notes).
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_SRC = _REPO_ROOT / "agents" / "development-agent" / "src"


def _load(module_name: str, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _agent_module():
    # code_generator must be importable as ``code_generator`` for the
    # agent module's ``from code_generator import …`` line to succeed.
    import sys

    if "code_generator" not in sys.modules:
        sys.modules["code_generator"] = _load("code_generator", _AGENT_SRC / "code_generator.py")
    return _load("development_agent_module", _AGENT_SRC / "agent.py")


def test_pr_body_contains_required_sections():
    agent_mod = _agent_module()
    gen = __import__("code_generator")
    plan = gen.plan_generation(
        task_id="pr-body-1",
        description="please write a utility helper function",
        request_type="dev.util",
        work_item_status="ready_for_development",
    )
    body = agent_mod._build_pr_body(
        task_id="pr-body-1",
        plan=plan,
        changed_files=[
            {
                "file_path": f.relative_path,
                "change_type": f.change_type,
                "diff_summary": "+10/-0 across 1 hunk(s)",
            }
            for f in plan.files
        ],
        validation={"py_compile": "pass", "diff_not_empty": "pass", "status": "passed"},
        risk={"risk_level": "low", "files_count": 2, "reason": "tests_only"},
    )
    for marker in (
        "## Summary",
        "## Changed Files",
        "## Generated Diff Summary",
        "## Validation Result",
        "## Risk Assessment",
        "## Rollback Plan",
        "## Safety Notes",
        "production_executed: false",
    ):
        assert marker in body, f"missing section: {marker}"


def test_pr_body_lists_each_changed_file():
    agent_mod = _agent_module()
    body = agent_mod._build_pr_body(
        task_id="pr-body-2",
        plan=__import__("code_generator").GenerationPlan(
            template="documentation",
            status="ready",
            reason="ok",
            summary="docs",
            title="t",
            rollback_plan="rollback",
        ),
        changed_files=[
            {"file_path": "docs/generated/a.md", "change_type": "create", "diff_summary": "+1"},
            {"file_path": "docs/generated/b.md", "change_type": "update", "diff_summary": "+2"},
        ],
        validation={"status": "passed"},
        risk={"risk_level": "low", "files_count": 2},
    )
    assert "docs/generated/a.md" in body
    assert "docs/generated/b.md" in body


def test_pr_body_records_blocked_validation():
    agent_mod = _agent_module()
    body = agent_mod._build_pr_body(
        task_id="pr-body-3",
        plan=__import__("code_generator").GenerationPlan(
            template="demo_api",
            status="ready",
            reason="ok",
            summary="api",
            title="t",
            rollback_plan="rb",
        ),
        changed_files=[
            {
                "file_path": "apps/demo-generated/x.py",
                "change_type": "create",
                "diff_summary": "+5",
            },
        ],
        validation={"status": "failed", "py_compile": "fail", "diff_not_empty": "pass"},
        risk={"risk_level": "medium", "files_count": 1, "reason": "app_code:1"},
    )
    assert "overall: failed" in body
    assert "py_compile: fail" in body
