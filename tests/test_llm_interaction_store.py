"""Stage 30 — sanity tests for the LLM interaction store.

Live DB tests run on the test server. Here we only verify the dataclass
shape + that the constructor accepts a DATABASE_URL override.
"""

from __future__ import annotations

import pytest

from shared.sdk.llm import LLMInteractionStore
from shared.sdk.llm.models import (
    LLMInteraction,
    LLMProposalArtifact,
    LLMUsageRecord,
)


def test_store_constructor_accepts_url() -> None:
    store = LLMInteractionStore(database_url="postgresql://postgres@localhost:5432/test")
    assert store.database_url.endswith("/test")


def test_store_uses_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@localhost:5432/env-db")
    store = LLMInteractionStore()
    assert "env-db" in store.database_url


def test_interaction_dataclass_round_trips() -> None:
    i = LLMInteraction(
        interaction_id="i-1",
        task_id="t1",
        workflow_id="w1",
        provider="mock",
        model_name="mock-deterministic",
        interaction_type="development_plan",
        prompt_hash="h1",
        prompt_preview="p",
        response_hash="h2",
        response_preview="r",
        status="ok",
        token_usage={"total_tokens": 0},
        safety_result={"allowed": True},
    )
    d = i.to_dict()
    assert d["interaction_id"] == "i-1"
    assert d["token_usage"] == {"total_tokens": 0}
    assert d["safety_result"]["allowed"] is True


def test_proposal_dataclass_round_trips() -> None:
    p = LLMProposalArtifact(
        proposal_id="p-1",
        task_id="t1",
        workflow_id=None,
        interaction_id="i-1",
        proposal_type="patch_proposal",
        status="policy_passed",
        proposed_files=[{"file_path": "docs/generated/x.md"}],
        plan={"summary": "x"},
        safety_result={"allowed": True, "violations": []},
        requires_human_review=True,
        linked_workspace_id="w-1",
    )
    d = p.to_dict()
    assert d["status"] == "policy_passed"
    assert d["requires_human_review"] is True
    assert d["linked_workspace_id"] == "w-1"


def test_usage_dataclass_zero_for_mock_provider() -> None:
    u = LLMUsageRecord(
        usage_id="u-1",
        task_id="t1",
        provider="mock",
        model_name="mock-deterministic",
    )
    d = u.to_dict()
    assert d["total_tokens"] == 0
    assert d["estimated_cost"] == 0.0
    assert d["provider"] == "mock"
