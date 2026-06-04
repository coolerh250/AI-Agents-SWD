"""Stage 31 -- ApprovalPolicyStore dataclass + URL sanity tests.

The full asyncpg integration runs on the test server; here we cover
the dataclasses and the env-var override behaviour.
"""

from __future__ import annotations

import pytest

from shared.sdk.approval_policy import (
    ApprovalPolicyStore,
    HumanApprovalDecision,
    HumanApprovalPolicy,
    LLMProposalApproval,
    LLMProposalPromotion,
)


def test_store_uses_default_url() -> None:
    store = ApprovalPolicyStore()
    assert store.database_url.startswith("postgresql://")


def test_store_accepts_url_override() -> None:
    store = ApprovalPolicyStore(database_url="postgresql://postgres@x:5432/override")
    assert "override" in store.database_url


def test_store_reads_database_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@y:5432/env-db")
    store = ApprovalPolicyStore()
    assert "env-db" in store.database_url


def test_policy_dataclass_round_trip() -> None:
    p = HumanApprovalPolicy(
        policy_id="p-1",
        task_id="t1",
        workflow_id="w1",
        approval_mode="delegated",
        status="active",
        granted_by="op",
        expires_at="2026-01-01T00:00:00+00:00",
        max_actions=5,
        max_files_changed=3,
        max_auto_fix_attempts=2,
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
        denied_paths=[".env"],
    )
    d = p.to_dict()
    assert d["policy_id"] == "p-1"
    assert d["approval_mode"] == "delegated"
    assert d["max_actions"] == 5
    assert d["allowed_actions"] == ["llm_proposal_promote"]


def test_decision_dataclass_round_trip() -> None:
    d = HumanApprovalDecision(
        decision_id="d-1",
        policy_id="p-1",
        task_id="t1",
        action_type="llm_proposal_promote",
        decision="approved",
        decided_by="op",
        safety_snapshot={"production_executed": False},
    )
    out = d.to_dict()
    assert out["decision"] == "approved"
    assert out["safety_snapshot"]["production_executed"] is False


def test_approval_dataclass_round_trip() -> None:
    a = LLMProposalApproval(
        approval_id="a-1",
        proposal_id="p-1",
        task_id="t1",
        approval_mode="per_action",
    )
    out = a.to_dict()
    assert out["approval_mode"] == "per_action"
    assert out["status"] == "pending"


def test_promotion_dataclass_round_trip() -> None:
    p = LLMProposalPromotion(
        promotion_id="pr-1",
        proposal_id="p-1",
        approval_id="a-1",
        policy_id=None,
        task_id="t1",
        promotion_mode="manual",
        status="requested",
    )
    out = p.to_dict()
    assert out["promotion_mode"] == "manual"
    assert out["status"] == "requested"
    assert out["promoted_files"] == []
