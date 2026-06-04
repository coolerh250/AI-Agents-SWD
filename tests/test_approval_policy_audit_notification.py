"""Stage 31 -- approval-policy audit + notification tests.

Drives create / activate / revoke / promote against in-memory fakes
and asserts the right ``decision_type`` + event_type combinations
land on the audit / notification publishers.
"""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _load_api_module():
    src = _ROOT / "apps" / "orchestrator" / "src" / "approval_policy_api.py"
    spec = importlib.util.spec_from_file_location("approval_policy_api_audit", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _CapturingApprovalStore:
    def __init__(self) -> None:
        self.policies: list[dict[str, Any]] = []
        self.created = []
        self.decisions = []
        self.promotions = []
        self.approvals = []

    async def create_policy(self, **kwargs):
        from shared.sdk.approval_policy.models import HumanApprovalPolicy

        self.created.append(kwargs)
        policy = HumanApprovalPolicy(
            policy_id=f"pol-{len(self.created)}",
            task_id=kwargs["task_id"],
            workflow_id=kwargs.get("workflow_id"),
            scope_type=kwargs.get("scope_type", "task"),
            scope_id=kwargs.get("scope_id", ""),
            approval_mode=kwargs.get("approval_mode", "per_action"),
            status=kwargs.get("status", "pending"),
            granted_by=kwargs.get("granted_by", ""),
            max_actions=kwargs.get("max_actions"),
            max_files_changed=kwargs.get("max_files_changed"),
            max_auto_fix_attempts=kwargs.get("max_auto_fix_attempts"),
            allowed_actions=kwargs.get("allowed_actions") or [],
            allowed_paths=kwargs.get("allowed_paths") or [],
            denied_paths=kwargs.get("denied_paths") or [],
        )
        self.policies.append(policy)
        return policy

    async def update_policy_status(self, policy_id, *, status):
        for p in self.policies:
            if p.policy_id == policy_id:
                p.status = status
                return p
        return None

    async def get_policy(self, policy_id):
        return next((p for p in self.policies if p.policy_id == policy_id), None)


def _patch_audit_notify(monkeypatch, mod):
    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[tuple[str, str, str]] = []

    async def _audit(**kwargs):
        audit_calls.append(kwargs)
        return "audit-1"

    async def _notify(task_id, event_type, message):
        notify_calls.append((task_id, event_type, message))

    monkeypatch.setattr(mod, "publish_audit_event", _audit)
    monkeypatch.setattr(mod, "send_notification", _notify)
    return audit_calls, notify_calls


def test_create_policy_emits_audit_and_notification(monkeypatch):
    mod = _load_api_module()
    store = _CapturingApprovalStore()
    monkeypatch.setattr(mod, "ApprovalPolicyStore", lambda: store)
    audit, notify = _patch_audit_notify(monkeypatch, mod)
    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="per_feature",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
        activate=True,
    )
    _run(mod.create_policy(payload))
    decision_types = {a["decision_type"] for a in audit}
    assert "approval_policy_activated" in decision_types
    event_types = {n[1] for n in notify}
    assert "approval.policy_activated" in event_types


def test_revoke_emits_audit_and_notification(monkeypatch):
    mod = _load_api_module()
    store = _CapturingApprovalStore()
    # Pre-create one policy.
    payload = mod.CreatePolicyIn(task_id="t1", approval_mode="per_action", activate=True)
    monkeypatch.setattr(mod, "ApprovalPolicyStore", lambda: store)
    audit, notify = _patch_audit_notify(monkeypatch, mod)
    _run(mod.create_policy(payload))
    policy_id = store.policies[0].policy_id
    audit.clear()
    notify.clear()
    _run(mod.revoke_policy(policy_id, mod.RevokeIn(revoked_by="op", reason="done")))
    decision_types = {a["decision_type"] for a in audit}
    assert "approval_policy_revoked" in decision_types
    assert any("approval.policy_revoked" in n[1] for n in notify)


def test_audit_payload_carries_production_executed_false(monkeypatch):
    mod = _load_api_module()
    store = _CapturingApprovalStore()
    monkeypatch.setattr(mod, "ApprovalPolicyStore", lambda: store)
    audit, _ = _patch_audit_notify(monkeypatch, mod)
    payload = mod.CreatePolicyIn(task_id="t1", approval_mode="per_action", activate=True)
    _run(mod.create_policy(payload))
    for call in audit:
        refs = call.get("artifact_refs") or {}
        assert refs.get("production_executed") is False


def test_delegated_policy_create_records_audit_with_constraints(monkeypatch):
    mod = _load_api_module()
    store = _CapturingApprovalStore()
    monkeypatch.setattr(mod, "ApprovalPolicyStore", lambda: store)
    audit, _ = _patch_audit_notify(monkeypatch, mod)
    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="delegated",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
        denied_paths=[".env"],
        max_actions=3,
        max_files_changed=2,
        max_auto_fix_attempts=1,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        activate=True,
    )
    _run(mod.create_policy(payload))
    refs = audit[0]["artifact_refs"]
    assert refs["approval_mode"] == "delegated"
    assert refs["max_actions"] == 3
