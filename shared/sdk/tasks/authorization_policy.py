"""Step 66C.4-BE3-A -- resume/replay authorization policy service (fail-closed).

Deterministic permission + separation + isolation + production-gate checks over the six canonical
`shared/sdk/tasks/rbac.py` TASK_ROLES. No second role system. No I/O. No resume/replay execution.

Per be3-rbac-permission-matrix.md:
  - Operator {pm_engineering_lead, platform_admin, agent_operator} requests resume/replay and
    decides resume.
  - Approver {reviewer_approver, platform_admin} authorizes replay, subject to requester != approver.
  - Service Identity may ONLY consume an already-authorized action; it can never request/decide.
  - Cross-team/cross-project access is denied and masked (not_found) so existence is not leaked.
  - A production-effect action requires the separate production approval reference before consume.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.sdk.tasks.rbac import TASK_ROLES

_OPERATOR_ROLES: frozenset[str] = frozenset(
    {"pm_engineering_lead", "platform_admin", "agent_operator"}
)
_REPLAY_APPROVER_ROLES: frozenset[str] = frozenset({"reviewer_approver", "platform_admin"})

# Human action -> the roles that may perform it (Service Identity is handled separately below).
_ACTION_ROLES: dict[str, frozenset[str]] = {
    "request_resume": _OPERATOR_ROLES,
    "authorize_resume": _OPERATOR_ROLES,  # resume's gate is the policy check; no separation needed
    "reject_resume": _OPERATOR_ROLES,
    "cancel_resume": _OPERATOR_ROLES,
    "request_replay": _OPERATOR_ROLES,
    "authorize_replay": _REPLAY_APPROVER_ROLES,  # + requester != approver (checked below)
    "reject_replay": _OPERATOR_ROLES | _REPLAY_APPROVER_ROLES,
    "cancel_replay": _OPERATOR_ROLES,
    "revoke": _OPERATOR_ROLES | _REPLAY_APPROVER_ROLES,
}

# Only these are consumable, and only by the Service Identity.
_CONSUME_ACTIONS: frozenset[str] = frozenset({"consume_resume", "consume_replay"})


@dataclass(frozen=True)
class Actor:
    """A human role principal, or the machine Service Identity (is_service_identity=True)."""

    principal_id: str
    role: str
    is_service_identity: bool = False


@dataclass(frozen=True)
class Scope:
    """Team/project scope of an actor or a resource (None = unscoped)."""

    team_id: str | None = None
    project_id: str | None = None


@dataclass(frozen=True)
class PolicyOutcome:
    allowed: bool
    result_kind: str
    reason_code: str
    policy_result: str  # allow | deny | not_applicable


def _isolation_ok(actor_scope: Scope, resource_scope: Scope) -> str | None:
    """Return None when the actor may see the resource, else the denial reason code. Cross-scope
    denial is reported so the caller can mask it as not_found (never leak existence)."""
    if resource_scope.team_id is not None and actor_scope.team_id is not None:
        if resource_scope.team_id != actor_scope.team_id:
            return "cross_team_denied"
    if resource_scope.project_id is not None and actor_scope.project_id is not None:
        if resource_scope.project_id != actor_scope.project_id:
            return "cross_project_denied"
    return None


def evaluate(
    *,
    action: str,
    actor: Actor,
    actor_scope: Scope,
    resource_scope: Scope,
    requested_by: str | None = None,
    production_effect: bool = False,
    production_approval_reference: str | None = None,
) -> PolicyOutcome:
    """Fail-closed permission evaluation for one authorization operation."""
    # Service Identity: consume-only.
    if actor.is_service_identity:
        if action not in _CONSUME_ACTIONS:
            return PolicyOutcome(False, "forbidden", "service_identity_cannot_decide", "deny")
        # Isolation still applies to a consume.
        iso = _isolation_ok(actor_scope, resource_scope)
        if iso is not None:
            return PolicyOutcome(False, "not_found_masked", iso, "deny")
        # Production-effect consume requires the separate production approval reference.
        if production_effect and not production_approval_reference:
            return PolicyOutcome(
                False, "production_approval_required", "production_approval_required", "deny"
            )
        return PolicyOutcome(True, "ok", "policy_allow", "allow")

    # A human may never consume.
    if action in _CONSUME_ACTIONS:
        return PolicyOutcome(False, "forbidden", "rbac_denied", "deny")

    if action not in _ACTION_ROLES:
        return PolicyOutcome(False, "forbidden", "unknown_action_type", "deny")
    if actor.role not in TASK_ROLES:
        return PolicyOutcome(False, "forbidden", "rbac_denied", "deny")
    if actor.role not in _ACTION_ROLES[action]:
        return PolicyOutcome(False, "forbidden", "rbac_denied", "deny")

    # Cross-team/project denial is masked as not_found.
    iso = _isolation_ok(actor_scope, resource_scope)
    if iso is not None:
        return PolicyOutcome(False, "not_found_masked", iso, "deny")

    # Two-person control for replay authorization: requester must differ from approver.
    if action == "authorize_replay" and requested_by is not None:
        if actor.principal_id == requested_by:
            return PolicyOutcome(False, "forbidden", "two_person_required", "deny")

    return PolicyOutcome(True, "ok", "policy_allow", "allow")
