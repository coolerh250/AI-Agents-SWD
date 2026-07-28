"""Step 66C.4-BE3-B -- internal operator-controlled resume service.

Ties eligibility (authoritative DB state under row locks) + the BE3-A durable authorization
(authorization_service/policy) + the resume_requests repository + the durable audit/command outbox
into one transaction per state change. Returns a safe, API-independent structured outcome.

FOUNDATION only: it NEVER calls the orchestrator, NEVER executes resume, NEVER publishes an event,
and exposes NO HTTP route. Consuming an authorization records a durable single-use CAS and creates a
GATED/DISABLED-BY-DEFAULT resume.execution_requested outbox row; the actual resume is a later,
separately-authorized activation. Every function takes the caller's asyncpg connection and runs
inside the caller's transaction, so a state change and its evidence commit atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from shared.sdk.tasks import authorization_service as authz
from shared.sdk.tasks import lifecycle_outbox, resume_request_model as model
from shared.sdk.tasks import resume_request_repository as repo
from shared.sdk.tasks.authorization_policy import Actor, Scope, evaluate


@dataclass(frozen=True)
class ResumeResult:
    ok: bool
    result_kind: str
    reason_code: str
    resume_request: dict[str, Any] | None = None
    command_id: str | None = None

    @property
    def state(self) -> str | None:
        return model.project_state(self.resume_request) if self.resume_request else None


def _deny(result_kind: str, reason_code: str) -> ResumeResult:
    return ResumeResult(False, result_kind, reason_code)


async def _emit(
    conn: asyncpg.Connection,
    *,
    clarification_id: str,
    task_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await lifecycle_outbox.insert_lifecycle_outbox_event(
        conn,
        clarification_id=clarification_id,
        task_id=task_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def _eligibility_denial(clar: dict[str, Any], task: dict[str, Any]) -> ResumeResult | None:
    """Authoritative eligibility gate (§7). Returns a denial ResumeResult or None if eligible."""
    if clar["status"] in model.BLOCKING_CLARIFICATION_STATUSES:
        return _deny("not_eligible", "clarification_blocked")
    if clar["status"] != "answered":
        return _deny("not_eligible", "clarification_not_answered")
    if clar.get("resume_eligible_at") is None:
        return _deny("not_eligible", "resume_not_eligible")
    if task["status"] in model.TERMINAL_TASK_STATUSES:
        return _deny("not_eligible", "resource_terminal")
    return None


async def request_resume(
    conn: asyncpg.Connection,
    *,
    actor: Actor,
    actor_scope: Scope,
    clarification_id: str,
    idempotency_key: str,
    expires_at: datetime,
    production_approval_reference: str | None = None,
) -> ResumeResult:
    """Operator creates a resume request + pending authorization (one transaction).

    Step 66C.4-BE3-R2 (finding R2-1 closure): production_effect is NEVER accepted from the caller --
    it is derived here, under the task row lock, from the owning task's OWN `production_effect`
    column (the same authoritative-derivation pattern replay already used). A client can neither
    upgrade nor downgrade this classification."""
    if not model.resume_api_enabled():
        return _deny("feature_disabled", "feature_disabled")

    # Idempotent re-confirm: the same request idempotency_key returns the same request (scoped).
    existing = await repo.get_request_by_idempotency_key(conn, idempotency_key)
    if existing is not None:
        if str(existing["team_id"]) != (actor_scope.team_id or "") or str(
            existing["project_id"]
        ) != (actor_scope.project_id or ""):
            return _deny("not_found_masked", "resource_not_found")
        return ResumeResult(True, "ok", "operator_requested", existing)

    # Pure RBAC pre-check BEFORE any mutation, so a denied caller never claims the clarification.
    pre = evaluate(
        action="request_resume", actor=actor, actor_scope=actor_scope, resource_scope=actor_scope
    )
    if not pre.allowed:
        return _deny(pre.result_kind, pre.reason_code)

    clar = await repo.lock_clarification(conn, clarification_id)
    if clar is None:
        return _deny("not_found_masked", "resource_not_found")
    task = await repo.lock_task(conn, str(clar["task_id"]))
    if task is None:
        return _deny("not_found_masked", "resource_not_found")
    # Cross-project isolation against the task's own project (if any); team scope is actor-declared.
    if task.get("project_id") is not None and str(task["project_id"]) != actor_scope.project_id:
        return _deny("not_found_masked", "resource_not_found")

    denial = _eligibility_denial(clar, task)
    if denial is not None:
        return denial

    # Server-side authoritative production-effect derivation (Step 66C.4-BE3-R2, finding R2-1):
    # from the owning task's OWN production_effect column, NEVER from request input. Folded into
    # the state version itself (below) so a LATER change to this classification invalidates any
    # outstanding request/authorization bound to the OLD classification.
    production_effect = model.authoritative_production_effect(task)
    state_version = model.resource_state_version(clar, task)

    # Claim the clarification-level active slot FIRST (atomic dedup, under the row lock). This gates
    # the authorization insert so its active-request unique index can never fire inside this
    # transaction (which would poison it). Loser -> active_request_exists.
    claimed = await repo.claim_clarification_resume_requested(
        conn, clarification_id, requested_by=actor.principal_id
    )
    if claimed is None:
        return _deny("conflict", "active_request_exists")

    # Create the durable authorization (single active per clarification, guaranteed by the claim).
    auth = await authz.request_authorization(
        conn,
        actor=actor,
        actor_scope=actor_scope,
        resource_scope=actor_scope,
        action_type="resume",
        resource_type="clarification",
        resource_id=clarification_id,
        resource_state_version=state_version,
        expires_at=expires_at,
        idempotency_key=f"resume-auth:{clarification_id}:{idempotency_key}",
        production_effect=production_effect,
        production_approval_reference=production_approval_reference,
    )
    if not auth.ok or auth.authorization is None:
        if auth.result_kind == "conflict":
            return _deny("conflict", "active_request_exists")
        return _deny(auth.result_kind, auth.reason_code)

    rr = await repo.insert_resume_request(
        conn,
        authorization_id=str(auth.authorization["authorization_id"]),
        clarification_id=clarification_id,
        task_id=str(clar["task_id"]),
        team_id=actor_scope.team_id or "",
        project_id=actor_scope.project_id or "",
        resource_state_version=state_version,
        requested_by=actor.principal_id,
        idempotency_key=idempotency_key,
    )

    await _emit(
        conn,
        clarification_id=clarification_id,
        task_id=str(clar["task_id"]),
        event_type="resume.requested",
        idempotency_key=f"{clarification_id}:resume_requested:{rr['resume_request_id']}",
        payload={
            "resume_request_id": str(rr["resume_request_id"]),
            "resource_state_version": state_version,
            "resume_requested_by": actor.principal_id,
            "reason": "operator_requested",
        },
    )
    return ResumeResult(True, "ok", "operator_requested", rr)


async def _load_visible(
    conn: asyncpg.Connection,
    resume_request_id: str,
    actor_scope: Scope,
    *,
    lock: bool = True,
) -> tuple[dict[str, Any] | None, ResumeResult | None]:
    fn = repo.lock_resume_request if lock else repo.get_resume_request
    rr = await fn(
        conn,
        resume_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if rr is None:
        return None, _deny("not_found_masked", "resource_not_found")
    return rr, None


async def get_resume_request(
    conn: asyncpg.Connection, resume_request_id: str, *, actor_scope: Scope
) -> ResumeResult:
    rr, masked = await _load_visible(conn, resume_request_id, actor_scope, lock=False)
    if masked is not None:
        return masked
    assert rr is not None
    return ResumeResult(True, "ok", "ok", rr)


async def authorize_resume(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    policy_version: str,
) -> ResumeResult:
    """Policy/safety authority authorizes a pending resume request (one transaction). A plain
    operator is denied by the authorization policy (policy_authority_required)."""
    if not model.resume_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    rr, masked = await _load_visible(conn, resume_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    # Re-validate authoritative state under locks (state-version-bound).
    clar = await repo.lock_clarification(conn, str(rr["clarification_id"]))
    task = await repo.lock_task(conn, str(rr["task_id"]))
    if clar is None or task is None:
        return _deny("not_found_masked", "resource_not_found")
    if task["status"] in model.TERMINAL_TASK_STATUSES:
        return _deny("conflict", "resource_terminal")
    if model.resource_state_version(clar, task) != rr["resource_state_version"]:
        return _deny("stale_state", "stale_state")

    outcome = await authz.authorize(
        conn,
        str(rr["authorization_id"]),
        actor=actor,
        actor_scope=actor_scope,
        policy_version=policy_version,
    )
    if not outcome.ok:
        return _deny(outcome.result_kind, outcome.reason_code)

    await repo.mark_clarification_resume_authorized(conn, str(rr["clarification_id"]))
    updated = await repo.transition_to_authorized(
        conn,
        resume_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await _emit(
        conn,
        clarification_id=str(rr["clarification_id"]),
        task_id=str(rr["task_id"]),
        event_type="resume.authorized",
        idempotency_key=f"{rr['clarification_id']}:resume_authorized:{resume_request_id}",
        payload={
            "resume_request_id": resume_request_id,
            "authorization_id": str(rr["authorization_id"]),
            "reason": "policy_allow",
        },
    )
    return ResumeResult(True, "ok", "policy_allow", updated)


async def reject_resume(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    reason_code: str = "policy_deny",
) -> ResumeResult:
    """Policy/safety authority rejects a pending resume request (one transaction)."""
    if not model.resume_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    model.assert_reason_code(reason_code)
    rr, masked = await _load_visible(conn, resume_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    outcome = await authz.reject(
        conn, str(rr["authorization_id"]), actor=actor, actor_scope=actor_scope
    )
    if not outcome.ok:
        return _deny(outcome.result_kind, outcome.reason_code)

    updated = await repo.transition_to_rejected(
        conn,
        resume_request_id,
        reason_code=reason_code,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await repo.release_clarification_resume_markers(conn, str(rr["clarification_id"]))
    await _emit(
        conn,
        clarification_id=str(rr["clarification_id"]),
        task_id=str(rr["task_id"]),
        event_type="resume.rejected",
        idempotency_key=f"{rr['clarification_id']}:resume_rejected:{resume_request_id}",
        payload={"resume_request_id": resume_request_id, "reason": reason_code},
    )
    return ResumeResult(True, "ok", reason_code, updated)


async def cancel_resume(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
) -> ResumeResult:
    """Operator cancels their own pending request; platform_admin may cancel any (one transaction)."""
    if not model.resume_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    rr, masked = await _load_visible(conn, resume_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if actor.role != "platform_admin" and rr["requested_by"] != actor.principal_id:
        return _deny("forbidden", "rbac_denied")
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    outcome = await authz.cancel(
        conn, str(rr["authorization_id"]), actor=actor, actor_scope=actor_scope
    )
    if not outcome.ok:
        return _deny(outcome.result_kind, outcome.reason_code)

    updated = await repo.transition_to_canceled(
        conn,
        resume_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await repo.release_clarification_resume_markers(conn, str(rr["clarification_id"]))
    await _emit(
        conn,
        clarification_id=str(rr["clarification_id"]),
        task_id=str(rr["task_id"]),
        event_type="resume.canceled",
        idempotency_key=f"{rr['clarification_id']}:resume_canceled:{resume_request_id}",
        payload={"resume_request_id": resume_request_id, "reason": "operator_canceled"},
    )
    return ResumeResult(True, "ok", "operator_canceled", updated)


async def prepare_execution(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
) -> ResumeResult:
    """Internal Service-Identity-only: consume the authorization and create the durable
    resume.execution_requested command (one transaction). GATED: does nothing when the command gate
    is disabled. Does NOT call the orchestrator and does NOT execute resume."""
    if not model.resume_command_enabled():
        return _deny("command_gate_disabled", "command_gate_disabled")
    rr, masked = await _load_visible(conn, resume_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorized":
        return _deny("invalid_transition", f"invalid_transition:{rr['state']}"[:64])

    clar = await repo.lock_clarification(conn, str(rr["clarification_id"]))
    task = await repo.lock_task(conn, str(rr["task_id"]))
    if clar is None or task is None:
        return _deny("not_found_masked", "resource_not_found")
    if task["status"] in model.TERMINAL_TASK_STATUSES:
        return _deny("conflict", "resource_terminal")
    if model.resource_state_version(clar, task) != rr["resource_state_version"]:
        return _deny("stale_state", "stale_state")

    # Consume the single-use authorization (service-identity-only + production gate + CAS). Any
    # failure returns here WITHOUT creating an outbox row.
    consumed = await authz.consume(
        conn,
        str(rr["authorization_id"]),
        actor=actor,
        actor_scope=actor_scope,
        resource_state_version=rr["resource_state_version"],
    )
    if not consumed.ok:
        return _deny(consumed.result_kind, consumed.reason_code)

    # Create the durable command row; its id is the stable command identity. If this insert fails,
    # the exception rolls back the whole transaction -- INCLUDING the consume above (no consumed
    # authorization is ever left without its command).
    command = await _emit(
        conn,
        clarification_id=str(rr["clarification_id"]),
        task_id=str(rr["task_id"]),
        event_type="resume.execution_requested",
        idempotency_key=f"{rr['clarification_id']}:resume_dispatched:{resume_request_id}",
        payload=model.build_resume_command_payload(
            resume_request_id=resume_request_id,
            authorization_id=str(rr["authorization_id"]),
            resource_state_version=str(rr["resource_state_version"]),
        ),
    )
    command_id = str(command["id"])
    updated = await repo.transition_to_execution_pending(
        conn,
        resume_request_id,
        command_id=command_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    return ResumeResult(True, "ok", "policy_allow", updated, command_id=command_id)


async def confirm_resumed(
    conn: asyncpg.Connection, resume_request_id: str, *, command_id: str
) -> ResumeResult:
    """Internal orchestrator-reconciliation confirmation: execution_pending -> resumed."""
    updated = await repo.confirm_resumed(conn, resume_request_id, command_id=command_id)
    if updated is None:
        return await _classify_confirm_failure(
            conn,
            resume_request_id,
            command_id,
            target="resumed",
            ok_reason="orchestrator_confirmed_resumed",
        )
    await _emit(
        conn,
        clarification_id=str(updated["clarification_id"]),
        task_id=str(updated["task_id"]),
        event_type="resume.resumed",
        idempotency_key=f"{updated['clarification_id']}:resume_resumed:{resume_request_id}",
        payload={"resume_request_id": resume_request_id, "command_id": command_id},
    )
    return ResumeResult(True, "ok", "orchestrator_confirmed_resumed", updated)


async def confirm_failed(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    command_id: str,
    reason_code: str = "policy_deny",
) -> ResumeResult:
    """Internal orchestrator-reconciliation confirmation: execution_pending -> failed."""
    model.assert_reason_code(reason_code)
    updated = await repo.confirm_failed(
        conn, resume_request_id, command_id=command_id, reason_code=reason_code
    )
    if updated is None:
        return await _classify_confirm_failure(
            conn,
            resume_request_id,
            command_id,
            target="failed",
            ok_reason="orchestrator_confirmed_failed",
        )
    await _emit(
        conn,
        clarification_id=str(updated["clarification_id"]),
        task_id=str(updated["task_id"]),
        event_type="resume.failed",
        idempotency_key=f"{updated['clarification_id']}:resume_failed:{resume_request_id}",
        payload={"resume_request_id": resume_request_id, "command_id": command_id},
    )
    return ResumeResult(True, "ok", "orchestrator_confirmed_failed", updated)


async def _classify_confirm_failure(
    conn: asyncpg.Connection,
    resume_request_id: str,
    command_id: str,
    *,
    target: str,
    ok_reason: str,
) -> ResumeResult:
    current = await repo.get_resume_request_internal(conn, resume_request_id)
    if current is None:
        return _deny("not_found_masked", "resource_not_found")
    # A mismatched command id is always a conflict (never confirm someone else's command).
    if current.get("command_id") is not None and str(current["command_id"]) != command_id:
        return _deny("conflict", "conflict")
    # Same terminal confirmation with a matching command -> idempotent success.
    if current["state"] == target:
        return ResumeResult(True, "ok", ok_reason, current)
    # A conflicting terminal confirmation (resumed<->failed) is rejected; a resumed request can
    # never become failed and vice versa without an explicit reconciliation contract.
    if current["state"] in ("resumed", "failed"):
        return _deny("conflict", "conflict")
    return _deny("invalid_transition", "invalid_transition")
