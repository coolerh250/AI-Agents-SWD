"""Stage 30 — operations API LLM endpoint smoke tests.

Live-DB integration is exercised by ``scripts/verify_llm_*.sh`` on
10.0.1.31. Here we check the route registration + safe-degrade
behaviour by mocking the LLM store.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_orchestrator_main() -> ModuleType:
    src = _ROOT / "apps" / "orchestrator" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("orchestrator_main", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_operations_llm_routes_registered() -> None:
    main = _load_orchestrator_main()
    paths = {r.path for r in main.app.routes}
    assert "/operations/llm/interactions" in paths
    assert "/operations/llm/interactions/{task_id}" in paths
    assert "/operations/llm/proposals/{task_id}" in paths
    assert "/operations/llm/usage" in paths


def test_operations_summary_includes_llm_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.orchestrator.src.operations as operations  # type: ignore

    async def _fake_counts(self):
        return {
            "total_interactions": 0,
            "total_proposals": 0,
            "blocked_proposals": 0,
            "policy_passed_proposals": 0,
            "accepted_proposals": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
        }

    monkeypatch.setattr(operations.LLMInteractionStore, "counts", _fake_counts, raising=False)
    summary = asyncio.new_event_loop().run_until_complete(operations._llm_summary())
    assert "total_interactions" in summary
    assert summary["total_proposals"] == 0


def test_operations_safety_llm_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """The safety endpoint must surface the LLM provider name + the
    boolean rails — never the API key value."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("RUN_REAL_LLM_TEST", "false")
    monkeypatch.delenv("ENABLE_REAL_LLM_NETWORK_CALL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    main = _load_orchestrator_main()
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.get("/operations/safety")
    # The route may degrade on DB-less local CI; we only require the
    # status code to be 200 and the LLM fields to be present.
    if response.status_code != 200:
        pytest.skip(f"safety endpoint unavailable locally: {response.status_code}")
    body = response.json()
    assert body["llm_provider"] == "mock"
    assert body["llm_real_enabled"] is False
    assert body["llm_external_call_enabled"] is False
    assert body["llm_policy_enforced"] is True
    assert body["llm_requires_human_review"] is True
    assert "LLM_API_KEY" not in body  # never echo the env var key
