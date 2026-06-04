"""Stage 31 -- LLM proposal promotion + approval policy integration tests.

Drives the orchestrator's ``/llm/proposals/{id}/promote`` flow against
in-memory fakes for the LLM + approval-policy + code-workspace stores.
No DB, no Redis, no LLM.
"""

from __future__ import annotations

import asyncio
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _load_api_module():
    src = _ROOT / "apps" / "orchestrator" / "src" / "approval_policy_api.py"
    spec = importlib.util.spec_from_file_location("approval_policy_api_promo", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@dataclass
class _FakeProposal:
    proposal_id: str
    task_id: str
    workflow_id: str | None = None
    interaction_id: str | None = None
    proposal_type: str = "patch_proposal"
    status: str = "policy_passed"
    proposed_files: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    safety_result: dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = True
    linked_workspace_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"proposal_id": self.proposal_id, "task_id": self.task_id}


@dataclass
class _FakeWorkspace:
    workspace_id: str = "ws-1"
    execution_mode: str = "delivery_task"


class _FakeLLMStore:
    def __init__(self, proposals):
        self._proposals = list(proposals)
        self.updates: list[tuple] = []

    async def list_proposals(self, *, task_id=None, limit=100):
        return [p for p in self._proposals if (task_id is None or p.task_id == task_id)]

    async def update_proposal_status(self, proposal_id, *, status, linked_workspace_id=None):
        self.updates.append((proposal_id, status, linked_workspace_id))


class _FakeWorkspaceStore:
    def __init__(self, workspace=None):
        self._workspace = workspace
        self.artifacts: list[dict[str, Any]] = []

    async def get_workspace(self, _task_id):
        return self._workspace

    async def add_code_change_artifact(self, **kwargs):
        self.artifacts.append(kwargs)

        class _R:
            artifact_id = f"a-{len(self.artifacts)}"

        return _R()


class _FakeApprovalStore:
    def __init__(self, policies=None, approvals=None):
        self._policies = list(policies or [])
        self._approvals = list(approvals or [])
        self.promotions: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.policy_actions_used: dict[str, int] = {}

    async def get_policy(self, policy_id):
        return next((p for p in self._policies if p.policy_id == policy_id), None)

    async def list_active_policies_for(self, *, task_id):
        return [p for p in self._policies if p.task_id == task_id and p.status == "active"]

    async def list_approvals(self, *, task_id=None, proposal_id=None, limit=100):
        return list(self._approvals)

    async def get_latest_approval(self, proposal_id):
        items = [a for a in self._approvals if a.proposal_id == proposal_id]
        return items[-1] if items else None

    async def create_promotion(self, **kwargs):
        self.promotions.append(kwargs)
        from shared.sdk.approval_policy.models import LLMProposalPromotion

        return LLMProposalPromotion(
            promotion_id=f"prom-{len(self.promotions)}",
            proposal_id=kwargs["proposal_id"],
            approval_id=kwargs.get("approval_id"),
            policy_id=kwargs.get("policy_id"),
            task_id=kwargs["task_id"],
            workflow_id=kwargs.get("workflow_id"),
            workspace_id=kwargs.get("workspace_id"),
            status=kwargs.get("status", "requested"),
            promoted_by=kwargs.get("promoted_by", ""),
            promotion_mode=kwargs.get("promotion_mode", "manual"),
            promoted_files=kwargs.get("promoted_files") or [],
            validation_result=kwargs.get("validation_result") or {},
            error=kwargs.get("error"),
        )

    async def update_promotion(self, promotion_id, **kwargs):
        return None

    async def get_promotion(self, promotion_id):
        from shared.sdk.approval_policy.models import LLMProposalPromotion

        return LLMProposalPromotion(
            promotion_id=promotion_id,
            proposal_id="p-1",
            approval_id=None,
            policy_id=None,
            task_id="t1",
            status="promoted",
        )

    async def increment_actions_used(self, policy_id):
        self.policy_actions_used[policy_id] = self.policy_actions_used.get(policy_id, 0) + 1

    async def record_decision(self, **kwargs):
        self.decisions.append(kwargs)


def _patch(mod, monkeypatch, *, llm_store, approval_store, workspace_store):
    monkeypatch.setattr(mod, "LLMInteractionStore", lambda: llm_store)
    monkeypatch.setattr(mod, "ApprovalPolicyStore", lambda: approval_store)
    monkeypatch.setattr(mod, "CodeWorkspaceStore", lambda: workspace_store)

    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(mod, "publish_audit_event", _noop)
    monkeypatch.setattr(mod, "send_notification", _noop)


def _ok_proposal(*, task_id="t1", proposal_id="p-1", status="policy_passed"):
    return _FakeProposal(
        proposal_id=proposal_id,
        task_id=task_id,
        proposal_type="patch_proposal",
        status=status,
        proposed_files=[
            {
                "file_path": "docs/generated/x.md",
                "change_type": "create",
                "proposed_content": "# clean content\n",
            }
        ],
        plan={
            "rationale": "ok",
            "risk_level": "low",
            "confidence_proposal": 0.9,
            "patch_id": "patch-1",
            "rollback_plan": "revert",
            "safety_notes": [],
            "test_commands": [],
        },
        safety_result={"allowed": True, "violations": []},
    )


def _delegated_policy(task_id="t1"):
    from datetime import datetime, timedelta, timezone

    from shared.sdk.approval_policy import HumanApprovalPolicy

    return HumanApprovalPolicy(
        policy_id="pol-delegated",
        task_id=task_id,
        workflow_id="w1",
        scope_type="task",
        scope_id=task_id,
        approval_mode="delegated",
        status="active",
        granted_by="op",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        max_actions=10,
        max_files_changed=5,
        max_auto_fix_attempts=2,
        allowed_actions=["llm_proposal_promote"],
        allowed_stages=["code_generation"],
        allowed_agents=["development-agent", "operator"],
        allowed_paths=["docs/generated/", "apps/demo-generated/"],
        denied_paths=[".env", "*.pem"],
    )


def test_promotion_blocked_when_proposal_status_blocked(monkeypatch):
    mod = _load_api_module()
    proposal = _ok_proposal(status="blocked")
    llm = _FakeLLMStore([proposal])
    approval = _FakeApprovalStore()
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="op")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] == "blocked_by_policy"


def test_promotion_blocked_when_no_active_policy_and_no_approval(monkeypatch):
    mod = _load_api_module()
    proposal = _ok_proposal()
    llm = _FakeLLMStore([proposal])
    approval = _FakeApprovalStore()
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="op")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] == "blocked_by_policy"


def test_promotion_allowed_under_delegated_policy(monkeypatch):
    mod = _load_api_module()
    proposal = _ok_proposal()
    llm = _FakeLLMStore([proposal])
    approval = _FakeApprovalStore(policies=[_delegated_policy()])
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="operator")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] in ("promoted", "validation_failed")
    # delegated_agent attribution surfaced on the promotion.
    assert result["promotion"]["promotion_mode"] == "delegated_agent"
    assert result["decision_source"] == "policy_allows"
    # The actions_used counter on the delegated policy should bump.
    assert approval.policy_actions_used.get("pol-delegated") == 1


def test_promotion_allowed_when_explicit_approval_present(monkeypatch):
    mod = _load_api_module()
    proposal = _ok_proposal()
    from shared.sdk.approval_policy.models import LLMProposalApproval

    approved_row = LLMProposalApproval(
        approval_id="ap-1",
        proposal_id="p-1",
        task_id="t1",
        approval_mode="per_action",
        status="approved",
        approved_by="operator",
    )
    llm = _FakeLLMStore([proposal])
    approval = _FakeApprovalStore(approvals=[approved_row])
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="operator", approval_id="ap-1")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] in ("promoted", "validation_failed")
    assert result["decision_source"] == "explicit_approval"


def test_promotion_blocked_when_proposal_violates_safety_policy(monkeypatch):
    """A proposal whose content matches a secret pattern must be refused
    by the safety re-scan, regardless of any active policy."""
    mod = _load_api_module()
    proposal = _ok_proposal()
    proposal.proposed_files[0]["proposed_content"] = "token = ghp_" + "A" * 40 + "\n"
    llm = _FakeLLMStore([proposal])
    approval = _FakeApprovalStore(policies=[_delegated_policy()])
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="operator")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] == "blocked_by_policy"


def test_promotion_blocked_by_hard_safety_when_proposal_touches_denylist(monkeypatch):
    """A proposed file under ``infra/`` is refused even when a delegated
    policy claims to allow it."""
    mod = _load_api_module()
    proposal = _ok_proposal()
    proposal.proposed_files[0]["file_path"] = "infra/docker-compose/docker-compose.yml"
    proposal.proposed_files[0]["change_type"] = "update"
    llm = _FakeLLMStore([proposal])
    policy = _delegated_policy()
    policy.allowed_paths = ["infra/"]
    approval = _FakeApprovalStore(policies=[policy])
    workspace = _FakeWorkspaceStore(_FakeWorkspace())
    _patch(mod, monkeypatch, llm_store=llm, approval_store=approval, workspace_store=workspace)
    payload = mod.PromoteIn(task_id="t1", promoted_by="operator")
    result = _run(mod.promote_proposal("p-1", payload))
    assert result["promotion"]["status"] == "blocked_by_policy"
