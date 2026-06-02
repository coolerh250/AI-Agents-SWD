"""Stage 28 — deterministic code generator unit tests."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GEN_PATH = _REPO_ROOT / "agents" / "development-agent" / "src" / "code_generator.py"


def _load():
    spec = importlib.util.spec_from_file_location("code_generator", _GEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_keyword_routes_to_documentation_template():
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-1",
        description="please write documentation for the new module",
        request_type="dev.doc",
        work_item_status="ready_for_development",
    )
    assert plan.template == "documentation"
    assert plan.status == "ready"
    assert any(f.relative_path.startswith("docs/generated/") for f in plan.files)


def test_api_keyword_routes_to_demo_api_with_app_and_test_files():
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-2",
        description="add a /healthz endpoint API for the service",
        request_type="dev.api",
        work_item_status="ready_for_development",
    )
    assert plan.template == "demo_api"
    paths = plan.file_paths()
    assert any(p.startswith("apps/demo-generated/") for p in paths)
    assert any(p.startswith("tests/generated/") for p in paths)


def test_utility_keyword_routes_to_simple_utility():
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-3",
        description="please write a utility helper function for parsing",
        request_type="dev.util",
        work_item_status="ready_for_development",
    )
    assert plan.template == "simple_utility"
    assert len(plan.files) == 2


def test_unclassifiable_returns_blocked():
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-4",
        description="qwoeiruqwer",
        request_type="dev.test",
        work_item_status="ready_for_development",
    )
    assert plan.template == "blocked"
    assert plan.status == "blocked"
    assert plan.files == []


def test_work_item_not_ready_returns_blocked():
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-5",
        description="please add docs",
        request_type="dev.doc",
        work_item_status="needs_clarification",
    )
    assert plan.status == "blocked"
    assert plan.reason.startswith("work_item_status:")


def test_priority_documentation_over_api(monkeypatch):
    gen = _load()
    # Description mentions both docs and api — documentation wins.
    plan = gen.plan_generation(
        task_id="task-6",
        description="document the new API endpoint",
        request_type="dev.test",
        work_item_status="ready_for_development",
    )
    assert plan.template == "documentation"


def test_write_plan_writes_files_into_workspace(tmp_path):
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-7",
        description="please write a utility helper function",
        request_type="dev.util",
        work_item_status="ready_for_development",
    )
    written, refused = gen.write_plan(plan, workspace_root=str(tmp_path))
    assert refused == []
    assert len(written) == 2
    for w in written:
        assert os.path.isfile(w.full_path)
        assert w.diff_text  # non-empty diff


def test_write_plan_refuses_denylist_paths(monkeypatch, tmp_path):
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-8",
        description="please write documentation",
        request_type="dev.doc",
        work_item_status="ready_for_development",
    )
    # Manually corrupt the path so it lands on the denylist.
    plan.files[0].relative_path = "infra/forbidden.md"
    written, refused = gen.write_plan(plan, workspace_root=str(tmp_path))
    assert written == []
    assert refused and refused[0][1].startswith(("denied:", "not_in_allowlist"))


def test_generated_python_module_compiles(tmp_path):
    """py_compile must accept the deterministic API template output."""
    import py_compile

    gen = _load()
    plan = gen.plan_generation(
        task_id="task-9",
        description="add an endpoint API for the helper",
        request_type="dev.api",
        work_item_status="ready_for_development",
    )
    written, _ = gen.write_plan(plan, workspace_root=str(tmp_path))
    py_paths = [w.full_path for w in written if w.full_path.endswith(".py")]
    assert py_paths
    for p in py_paths:
        py_compile.compile(p, doraise=True)


def test_generated_content_contains_safety_metadata(tmp_path):
    gen = _load()
    plan = gen.plan_generation(
        task_id="task-10",
        description="utility helper",
        request_type="dev.util",
        work_item_status="ready_for_development",
    )
    written, _ = gen.write_plan(plan, workspace_root=str(tmp_path))
    for w in written:
        with open(w.full_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        # Every generated file declares the Stage 28 safety metadata.
        assert "production_executed" in content.lower() or "production_executed" in content
        if w.full_path.endswith(".py"):
            assert "deterministic_template" in content
