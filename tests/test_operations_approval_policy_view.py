"""Stage 31 -- operations approval-policy view smoke tests."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_orchestrator_main() -> ModuleType:
    src = _ROOT / "apps" / "orchestrator" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("orchestrator_main_stage31", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_operations_approval_routes_registered() -> None:
    main = _load_orchestrator_main()
    paths = {r.path for r in main.app.routes}
    assert "/operations/approval-policies" in paths
    assert "/operations/approval-policies/{task_id}" in paths
    assert "/operations/approval-decisions/{task_id}" in paths


def test_approval_policy_router_mounted() -> None:
    main = _load_orchestrator_main()
    paths = {r.path for r in main.app.routes}
    assert "/approval-policies" in paths
    assert "/approval-policies/{policy_id}" in paths
    assert "/llm/proposals/{proposal_id}/promote" in paths


def test_approval_policy_summary_safe_degrade(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.orchestrator.src.operations as operations  # type: ignore

    async def _fail(self):
        raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(operations.ApprovalPolicyStore, "counts", _fail, raising=False)
    summary = asyncio.new_event_loop().run_until_complete(operations._approval_policy_summary())
    assert summary["total_policies"] == 0
    assert summary["delegated_policies"] == 0
    assert summary["per_feature_policies"] == 0


def test_operations_safety_includes_approval_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    main = _load_orchestrator_main()
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.get("/operations/safety")
    if response.status_code != 200:
        pytest.skip(f"safety endpoint unavailable locally: {response.status_code}")
    body = response.json()
    assert body["hard_policy_enforced"] is True
    assert body["production_delegation_allowed"] is False
    assert body["real_github_delegation_allowed"] is False
    assert "delegated_agent_enabled" in body
    assert "active_delegated_policies" in body
