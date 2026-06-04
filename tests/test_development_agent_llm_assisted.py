"""Stage 30 — development-agent LLM-assisted planning tests.

These tests drive the LLM planner pipeline (and indirectly the
development-agent's handle) against in-memory fakes. No DB, no Redis,
no real LLM.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeLLMStore:
    def __init__(self) -> None:
        self.interactions: list[dict] = []
        self.proposals: list[dict] = []
        self.usage: list[dict] = []
        self.status_updates: list[tuple[str, str, str | None]] = []

    async def record_interaction(self, **kwargs):
        self.interactions.append(kwargs)
        return _Box(interaction_id=f"i-{len(self.interactions)}", status="ok")

    async def record_proposal(self, **kwargs):
        self.proposals.append(kwargs)
        return _Box(
            proposal_id=f"p-{len(self.proposals)}",
            **{
                "status": kwargs.get("status"),
                "requires_human_review": True,
            },
        )

    async def update_proposal_status(self, proposal_id, *, status, linked_workspace_id=None):
        self.status_updates.append((proposal_id, status, linked_workspace_id))
        return _Box(proposal_id=proposal_id, status=status)

    async def record_usage(self, **kwargs):
        self.usage.append(kwargs)
        return _Box(usage_id=f"u-{len(self.usage)}")


@dataclass
class _Box:
    interaction_id: str = ""
    proposal_id: str = ""
    usage_id: str = ""
    status: str = ""
    requires_human_review: bool = True


class _FakeCodeStore:
    async def add_code_change_artifact(self, **kwargs):
        return _Box(proposal_id="art-1")


def _wire_planner(monkeypatch):
    """Build a planner pipeline wired against in-memory fakes."""
    import sys
    import importlib.util
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    src = ROOT / "agents" / "development-agent" / "src"

    def _load(name, p):
        if name in sys.modules:
            return sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    _load("code_generator", src / "code_generator.py")
    llm_planner = _load("llm_planner", src / "llm_planner.py")
    return llm_planner


def test_planner_pass_records_interaction_proposal_and_usage(monkeypatch):
    llm_planner = _wire_planner(monkeypatch)
    pipeline = llm_planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    pipeline._code_store = _FakeCodeStore()
    summary = _run(
        pipeline.run(
            task_id="t1",
            workflow_id="w1",
            description="please add a /healthz endpoint API",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=["healthz returns 200"],
        )
    )
    store = pipeline._llm_store
    assert summary["enabled"] is True
    assert summary["provider"] == "mock"
    assert summary["allowed"] is True
    assert summary["blocked"] is False
    assert summary["requires_human_review"] is True
    assert summary["usage"]["total_tokens"] == 0
    assert summary["usage"]["estimated_cost"] == 0.0
    # Two interactions: development_plan + patch_proposal.
    assert len(store.interactions) == 2
    types = {i["interaction_type"] for i in store.interactions}
    assert types == {"development_plan", "patch_proposal"}
    # One proposal artifact + status=policy_passed.
    assert len(store.proposals) == 1
    assert store.proposals[0]["status"] == "policy_passed"
    # One zero-token usage record.
    assert len(store.usage) == 1
    assert store.usage[0]["total_tokens"] == 0


def test_planner_blocks_on_denied_path_proposal(monkeypatch):
    llm_planner = _wire_planner(monkeypatch)
    pipeline = llm_planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    pipeline._code_store = _FakeCodeStore()
    summary = _run(
        pipeline.run(
            task_id="t-denied",
            workflow_id="w1",
            description="please denied path",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    assert summary["blocked"] is True
    assert summary["allowed"] is False
    store = pipeline._llm_store
    assert store.proposals[0]["status"] == "blocked"
    safety = summary["policy_result"]
    assert safety["allowed"] is False
    rules = {v["rule"] for v in safety["violations"]}
    assert "path_blocked" in rules


def test_planner_blocks_on_secret_like_proposal(monkeypatch):
    llm_planner = _wire_planner(monkeypatch)
    pipeline = llm_planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    pipeline._code_store = _FakeCodeStore()
    summary = _run(
        pipeline.run(
            task_id="t-secret",
            workflow_id="w1",
            description="please secret-token leak",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    assert summary["blocked"] is True
    rules = {v["rule"] for v in summary["policy_result"]["violations"]}
    assert "secret_like_content" in rules


def test_planner_records_redacted_prompt_preview(monkeypatch):
    llm_planner = _wire_planner(monkeypatch)
    pipeline = llm_planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    pipeline._code_store = _FakeCodeStore()
    leaky_descr = "please add api OPENAI_API_KEY=sk-" + "A" * 40
    _run(
        pipeline.run(
            task_id="t-leak",
            workflow_id="w1",
            description=leaky_descr,
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    store = pipeline._llm_store
    for i in store.interactions:
        # The full leaked key must NEVER appear in the persisted preview.
        assert "sk-" + "A" * 40 not in i["prompt_preview"]
        assert "sk-" + "A" * 40 not in i["response_preview"]
        # Hashes are deterministic SHA-256 hex strings.
        assert len(i["prompt_hash"]) == 64


def test_planner_disabled_when_env_off(monkeypatch):
    monkeypatch.delenv("ENABLE_LLM_ASSISTED_PLANNING", raising=False)
    llm_planner = _wire_planner(monkeypatch)
    assert llm_planner.llm_planning_enabled() is False


def test_planner_enabled_when_env_on(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_ASSISTED_PLANNING", "true")
    llm_planner = _wire_planner(monkeypatch)
    assert llm_planner.llm_planning_enabled() is True


def test_planner_records_real_test_skipped_for_external_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "external_openai_placeholder")
    llm_planner = _wire_planner(monkeypatch)
    pipeline = llm_planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    pipeline._code_store = _FakeCodeStore()
    summary = _run(
        pipeline.run(
            task_id="t-ext",
            workflow_id="w1",
            description="please add api",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    assert summary["provider"] == "external_openai_placeholder"
    # The proposal still goes through the policy and is auto-shrinked to
    # require human review. It can still be allowed because the mock-
    # backed external guard returns a clean response.
    assert summary["requires_human_review"] is True
