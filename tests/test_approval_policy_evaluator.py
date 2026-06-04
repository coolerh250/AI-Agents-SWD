"""Stage 31 -- approval policy evaluator unit tests.

Pure dataclass + function tests; no DB, no Redis, no LLM.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.sdk.approval_policy import (
    APPROVAL_MODES,
    HARD_SAFETY_ACTIONS,
    MIN_DELEGATED_CONSTRAINTS,
    HumanApprovalPolicy,
    evaluate_action,
)


def _future(hours: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past(hours: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _delegated(**overrides) -> HumanApprovalPolicy:
    """Build a fully-constrained delegated policy."""
    defaults = dict(
        policy_id="p-1",
        task_id="t1",
        workflow_id="w1",
        scope_type="task",
        scope_id="t1",
        approval_mode="delegated",
        status="active",
        granted_by="op",
        expires_at=_future(),
        max_actions=5,
        max_files_changed=3,
        max_auto_fix_attempts=2,
        allowed_actions=["llm_proposal_promote"],
        allowed_stages=["code_generation"],
        allowed_agents=["development-agent"],
        allowed_paths=[
            "docs/generated/",
            "apps/demo-generated/",
            "tests/generated/",
        ],
        denied_paths=[".env", "*.pem"],
    )
    defaults.update(overrides)
    return HumanApprovalPolicy(**defaults)


def test_approval_modes_constant_locked() -> None:
    assert APPROVAL_MODES == ("per_action", "per_feature", "per_stage", "delegated")


def test_hard_safety_actions_locked() -> None:
    for required in (
        "production_deploy",
        "real_github_write",
        "real_llm_network_call",
        "delete_file",
        "branch_protection_modification",
        "secret_write",
        "destructive_command",
    ):
        assert required in HARD_SAFETY_ACTIONS


def test_min_delegated_constraints_locked() -> None:
    assert set(MIN_DELEGATED_CONSTRAINTS) == {
        "allowed_actions",
        "allowed_paths",
        "denied_paths",
        "max_actions",
        "max_files_changed",
        "max_auto_fix_attempts",
        "expires_at",
    }


def test_hard_safety_blocks_production_deploy_even_with_delegated_policy() -> None:
    policy = _delegated(allowed_actions=["production_deploy", "llm_proposal_promote"])
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="production_deploy",
        stage="deploy",
        agent="devops-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.hard_policy_block is True
    assert "hard_safety:production_deploy" in res.reason


def test_hard_safety_blocks_real_github_write() -> None:
    policy = _delegated(allowed_actions=["real_github_write"])
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="real_github_write",
        stage="github_pr",
        agent="github-automation",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.hard_policy_block is True


def test_hard_safety_blocks_denylist_path_under_delegated_policy() -> None:
    policy = _delegated(allowed_paths=["infra/"])
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["infra/docker-compose/docker-compose.yml"],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.hard_policy_block is True
    assert "denylist_path" in res.reason


def test_hard_safety_blocks_secret_content_in_delegated_policy() -> None:
    policy = _delegated()
    secret = "token = ghp_" + "A" * 40
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        content_samples=[secret],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.hard_policy_block is True


def test_per_action_returns_requires_explicit_approval() -> None:
    policy = HumanApprovalPolicy(
        policy_id="p-pa",
        task_id="t1",
        approval_mode="per_action",
        status="active",
        granted_by="op",
    )
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.requires_explicit_approval is True


def test_per_feature_policy_authorises_same_task() -> None:
    policy = HumanApprovalPolicy(
        policy_id="p-feat",
        task_id="t1",
        approval_mode="per_feature",
        status="active",
        granted_by="op",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
    )
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert res.allowed is True
    assert res.approval_mode == "per_feature"


def test_per_feature_policy_refuses_other_task() -> None:
    policy = HumanApprovalPolicy(
        policy_id="p-feat",
        task_id="t1",
        approval_mode="per_feature",
        status="active",
        granted_by="op",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
    )
    res = evaluate_action(
        task_id="other-task",
        workflow_id="w2",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "task_mismatch" in res.reason


def test_per_stage_policy_authorises_allowed_stage_only() -> None:
    policy = HumanApprovalPolicy(
        policy_id="p-stage",
        task_id="t1",
        approval_mode="per_stage",
        status="active",
        granted_by="op",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
        allowed_stages=["code_generation"],
    )
    ok = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert ok.allowed is True
    blocked = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="deployment",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        candidate_policies=[policy],
    )
    assert blocked.allowed is False
    assert "stage_not_allowed" in blocked.reason


def test_delegated_policy_authorises_inside_constraints() -> None:
    policy = _delegated()
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/notes.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is True
    assert res.approval_mode == "delegated"


def test_delegated_policy_blocks_when_constraints_missing() -> None:
    bad = HumanApprovalPolicy(
        policy_id="p-bad",
        task_id="t1",
        approval_mode="delegated",
        status="active",
        granted_by="op",
    )
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[bad],
    )
    assert res.allowed is False
    assert res.reason.startswith("delegated_missing:")


def test_expired_policy_blocks() -> None:
    policy = _delegated(expires_at=_past())
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert res.reason == "policy_expired"


def test_revoked_policy_blocks() -> None:
    policy = _delegated(status="revoked")
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "policy_not_active" in res.reason


def test_max_actions_exceeded_blocks() -> None:
    policy = _delegated(max_actions=2)
    policy.actions_used = 2
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "max_actions_exceeded" in res.reason


def test_max_files_changed_exceeded_blocks() -> None:
    policy = _delegated(max_files_changed=1)
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md", "docs/generated/y.md"],
        files_changed=2,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "max_files_changed_exceeded" in res.reason


def test_action_not_allowed_blocks() -> None:
    policy = _delegated(allowed_actions=["qa_auto_fix"])
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "action_not_allowed" in res.reason


def test_agent_not_allowed_blocks() -> None:
    policy = _delegated(allowed_agents=["qa-agent"])
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.allowed is False
    assert "agent_not_allowed" in res.reason


def test_policy_authorising_id_matches_chosen_policy() -> None:
    policy = _delegated()
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.policy_id == policy.policy_id


def test_safety_snapshot_records_production_executed_false() -> None:
    policy = _delegated()
    res = evaluate_action(
        task_id="t1",
        workflow_id="w1",
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent="development-agent",
        paths=["docs/generated/x.md"],
        files_changed=1,
        candidate_policies=[policy],
    )
    assert res.safety_snapshot["production_executed"] is False
    assert res.safety_snapshot["real_call"] is False
