"""Stage 31 -- deterministic approval policy evaluator.

The evaluator answers a single question per action:

    Given an action_type (with stage / agent / paths / risk hints), is
    there an *active*, *non-expired*, *non-revoked*, *constraint-conformant*
    HumanApprovalPolicy that authorises it, AND does the action survive
    the hard safety rails?

Hard safety rails ALWAYS win. A delegated policy that would otherwise
permit a production deploy / real GitHub write / branch protection
change / denylist path mutation / file deletion / secret-content
embedding / destructive command is REFUSED with ``hard_policy_block``.

The evaluator does not load policies on its own -- the caller supplies
the candidate policy set so the evaluator stays pure + testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from shared.sdk.approval_policy.models import (
    APPROVAL_MODES,
    HumanApprovalPolicy,
)
from shared.sdk.code_workspace.policy import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    validate_allowed_path,
    validate_no_destructive_change,
    validate_no_secret_content,
)

#: Action types that are NEVER delegatable, no matter what the policy says.
HARD_SAFETY_ACTIONS: tuple[str, ...] = (
    "production_deploy",
    "real_github_write",
    "real_github_pr_merge",
    "branch_protection_modification",
    "force_push",
    "delete_file",
    "secret_write",
    "destructive_command",
    "real_llm_network_call",
    "denylist_path_mutation",
)

#: Constraint fields a delegated policy MUST set (per Step 30 spec 3.D).
MIN_DELEGATED_CONSTRAINTS: tuple[str, ...] = (
    "allowed_actions",
    "allowed_paths",
    "denied_paths",
    "max_actions",
    "max_files_changed",
    "max_auto_fix_attempts",
    "expires_at",
)


@dataclass
class EvaluationResult:
    """Result of one evaluate_action call.

    ``allowed`` is the final verdict. ``reason`` is a short slug
    explaining why; ``policy_id`` is the id of the policy that
    authorised the action (empty for ``per_action`` paths that still
    need explicit approval). ``hard_policy_block`` is True when the
    refusal came from the hard safety rails.
    """

    allowed: bool = False
    reason: str = ""
    policy_id: str = ""
    approval_mode: str = ""
    hard_policy_block: bool = False
    requires_explicit_approval: bool = False
    safety_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "approval_mode": self.approval_mode,
            "hard_policy_block": self.hard_policy_block,
            "requires_explicit_approval": self.requires_explicit_approval,
            "safety_snapshot": dict(self.safety_snapshot),
        }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _policy_expired(policy: HumanApprovalPolicy, now: datetime | None = None) -> bool:
    expires = _parse_dt(policy.expires_at)
    if expires is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now >= expires


def _path_blocked_by_denylist(path: str, denylist: Iterable[str]) -> tuple[bool, str]:
    ok, why = validate_allowed_path(
        path,
        allowed=DEFAULT_ALLOWED_PATHS,
        denied=list(DEFAULT_DENIED_PATHS) + list(denylist or []),
    )
    if not ok and why.startswith("denied:"):
        return True, why
    if not ok:
        return False, why
    return False, ""


def _hard_safety_check(
    *,
    action_type: str,
    paths: list[str],
    content_samples: list[str],
) -> tuple[bool, str]:
    """Return ``(blocked, reason)``. Hard rails -- never bypassable."""
    if action_type in HARD_SAFETY_ACTIONS:
        return True, f"hard_safety:{action_type}"
    # Path-level rails: denylist match is a hard block regardless of policy.
    for path in paths or []:
        ok, why = validate_allowed_path(path)
        if not ok and why.startswith("denied:"):
            return True, f"hard_safety:denylist_path:{path}"
        if not ok and why == "path_traversal":
            return True, f"hard_safety:path_traversal:{path}"
    # Content rails -- a delegated policy MUST NOT permit a write that
    # carries a secret-like literal or a destructive command.
    for sample in content_samples or []:
        ok, why = validate_no_secret_content(sample)
        if not ok:
            return True, f"hard_safety:{why}"
        ok, why = validate_no_destructive_change(sample)
        if not ok:
            return True, f"hard_safety:{why}"
    return False, ""


def _policy_constraints_ok(policy: HumanApprovalPolicy) -> tuple[bool, str]:
    """For delegated policies, verify the minimum constraint set is present."""
    if policy.approval_mode != "delegated":
        return True, "n/a"
    if policy.expires_at is None:
        return False, "delegated_missing:expires_at"
    if not policy.allowed_actions:
        return False, "delegated_missing:allowed_actions"
    if not policy.allowed_paths:
        return False, "delegated_missing:allowed_paths"
    if not policy.denied_paths:
        return False, "delegated_missing:denied_paths"
    if policy.max_actions is None or policy.max_actions <= 0:
        return False, "delegated_missing:max_actions"
    if policy.max_files_changed is None or policy.max_files_changed <= 0:
        return False, "delegated_missing:max_files_changed"
    if policy.max_auto_fix_attempts is None or policy.max_auto_fix_attempts < 0:
        return False, "delegated_missing:max_auto_fix_attempts"
    return True, "ok"


def _policy_authorises(
    policy: HumanApprovalPolicy,
    *,
    task_id: str,
    workflow_id: str | None,
    action_type: str,
    stage: str,
    agent: str,
    paths: list[str],
    files_changed: int,
) -> tuple[bool, str]:
    """Return ``(authorises, reason)`` for one candidate policy.

    Pure scoping + constraint check. Does NOT call the hard rails (the
    caller layers those on top).
    """
    if policy.status != "active":
        return False, f"policy_not_active:{policy.status}"
    if _policy_expired(policy):
        return False, "policy_expired"
    constraints_ok, why = _policy_constraints_ok(policy)
    if not constraints_ok:
        return False, why
    # Scope binding -- per_feature / per_stage carry a task_id; the
    # evaluator refuses to honour a policy belonging to a different task.
    if policy.task_id and policy.task_id != task_id:
        return False, "policy_task_mismatch"
    if (
        policy.approval_mode == "per_stage"
        and policy.allowed_stages
        and stage
        and stage not in policy.allowed_stages
    ):
        return False, f"stage_not_allowed:{stage}"
    if policy.allowed_actions and action_type not in policy.allowed_actions:
        return False, f"action_not_allowed:{action_type}"
    if policy.allowed_agents and agent and agent not in policy.allowed_agents:
        return False, f"agent_not_allowed:{agent}"
    # Path scoping -- every supplied path must be inside the policy's
    # allowed_paths AND not match the policy's denied_paths.
    for path in paths or []:
        is_denied, why_denied = _path_blocked_by_denylist(path, policy.denied_paths)
        if is_denied:
            return False, f"policy_denied_path:{path}:{why_denied}"
        if policy.allowed_paths:
            normalised_path = (path or "").replace("\\", "/").lstrip("./")
            if not any(
                normalised_path.startswith(str(prefix).replace("\\", "/").lstrip("./"))
                for prefix in policy.allowed_paths
            ):
                return False, f"path_not_in_policy_allowlist:{path}"
    if policy.max_files_changed is not None and files_changed > policy.max_files_changed:
        return False, (f"max_files_changed_exceeded:{files_changed}>{policy.max_files_changed}")
    if policy.max_actions is not None and policy.actions_used >= policy.max_actions:
        return False, "max_actions_exceeded"
    return True, "ok"


def evaluate_action(
    *,
    task_id: str,
    workflow_id: str | None,
    action_type: str,
    stage: str,
    agent: str,
    paths: list[str] | None = None,
    files_changed: int = 0,
    content_samples: list[str] | None = None,
    risk_level: str = "low",
    candidate_policies: Iterable[HumanApprovalPolicy] = (),
) -> EvaluationResult:
    """Decide whether ``action_type`` is allowed.

    Returns ``allowed=True`` only when:

    1. The hard-safety rails do not refuse it.
    2. At least one candidate policy authorises it (per the
       scoping / constraint checks).

    ``per_action`` policies NEVER auto-authorise -- they always require
    explicit approval. In that case the result is ``allowed=False`` with
    ``requires_explicit_approval=True`` and ``reason='per_action'``.
    """
    paths = list(paths or [])
    content_samples = list(content_samples or [])
    snapshot: dict[str, Any] = {
        "task_id": task_id,
        "workflow_id": workflow_id,
        "action_type": action_type,
        "stage": stage,
        "agent": agent,
        "paths": list(paths),
        "files_changed": files_changed,
        "risk_level": risk_level,
        "production_executed": False,
        "real_call": False,
    }
    # Hard safety FIRST -- nothing the policy says can bypass this.
    blocked, why = _hard_safety_check(
        action_type=action_type,
        paths=paths,
        content_samples=content_samples,
    )
    if blocked:
        return EvaluationResult(
            allowed=False,
            reason=why,
            policy_id="",
            approval_mode="",
            hard_policy_block=True,
            requires_explicit_approval=False,
            safety_snapshot=snapshot,
        )
    # Try every candidate policy until one authorises (or all refuse).
    last_refusal = "no_active_policy"
    for policy in candidate_policies or ():
        if policy.approval_mode == "per_action":
            # per_action policies MUST yield to explicit approval -- they
            # never auto-authorise.  Mark them so the caller surfaces
            # `requires_explicit_approval`.
            last_refusal = "per_action_requires_explicit_approval"
            continue
        authorises, reason = _policy_authorises(
            policy,
            task_id=task_id,
            workflow_id=workflow_id,
            action_type=action_type,
            stage=stage,
            agent=agent,
            paths=paths,
            files_changed=files_changed,
        )
        if authorises:
            return EvaluationResult(
                allowed=True,
                reason="policy_allows",
                policy_id=policy.policy_id,
                approval_mode=policy.approval_mode,
                hard_policy_block=False,
                requires_explicit_approval=False,
                safety_snapshot=snapshot,
            )
        last_refusal = reason
    requires_explicit = last_refusal == "per_action_requires_explicit_approval"
    return EvaluationResult(
        allowed=False,
        reason=last_refusal,
        policy_id="",
        approval_mode="per_action" if requires_explicit else "",
        hard_policy_block=False,
        requires_explicit_approval=requires_explicit,
        safety_snapshot=snapshot,
    )


class ApprovalPolicyEvaluator:
    """Thin OO wrapper for callers that prefer an evaluator instance."""

    def __init__(self, candidate_policies: Iterable[HumanApprovalPolicy] = ()) -> None:
        self._policies: list[HumanApprovalPolicy] = list(candidate_policies)

    def update_candidate_policies(self, policies: Iterable[HumanApprovalPolicy]) -> None:
        self._policies = list(policies)

    def evaluate(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        action_type: str,
        stage: str = "",
        agent: str = "",
        paths: list[str] | None = None,
        files_changed: int = 0,
        content_samples: list[str] | None = None,
        risk_level: str = "low",
    ) -> EvaluationResult:
        return evaluate_action(
            task_id=task_id,
            workflow_id=workflow_id,
            action_type=action_type,
            stage=stage,
            agent=agent,
            paths=paths,
            files_changed=files_changed,
            content_samples=content_samples,
            risk_level=risk_level,
            candidate_policies=self._policies,
        )

    def is_action_allowed_by_policy(
        self,
        *,
        task_id: str,
        action_type: str,
        stage: str = "",
        agent: str = "",
        paths: list[str] | None = None,
        files_changed: int = 0,
    ) -> bool:
        return self.evaluate(
            task_id=task_id,
            workflow_id=None,
            action_type=action_type,
            stage=stage,
            agent=agent,
            paths=paths,
            files_changed=files_changed,
        ).allowed

    def requires_manual_approval(
        self,
        *,
        task_id: str,
        action_type: str,
        stage: str = "",
        agent: str = "",
        paths: list[str] | None = None,
        files_changed: int = 0,
    ) -> bool:
        result = self.evaluate(
            task_id=task_id,
            workflow_id=None,
            action_type=action_type,
            stage=stage,
            agent=agent,
            paths=paths,
            files_changed=files_changed,
        )
        return result.requires_explicit_approval or (
            not result.allowed and not result.hard_policy_block
        )

    def explain_decision(
        self,
        *,
        task_id: str,
        action_type: str,
        stage: str = "",
        agent: str = "",
        paths: list[str] | None = None,
        files_changed: int = 0,
    ) -> dict[str, Any]:
        return self.evaluate(
            task_id=task_id,
            workflow_id=None,
            action_type=action_type,
            stage=stage,
            agent=agent,
            paths=paths,
            files_changed=files_changed,
        ).to_dict()


def _ensure_known_modes() -> None:
    """Module-load guard so a refactor doesn't drift the mode list."""
    assert set(APPROVAL_MODES) == {
        "per_action",
        "per_feature",
        "per_stage",
        "delegated",
    }


_ensure_known_modes()
