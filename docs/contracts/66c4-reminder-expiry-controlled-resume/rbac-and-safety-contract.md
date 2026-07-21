# RBAC and Safety Contract — Step 66C.4-P

> **Planning document only. No RBAC code implemented. No safety-check code implemented. This
> document proposes the minimum RBAC needed for M1's Step 66C.4 scope only — full Team RBAC
> remains M3's responsibility.**

This contract reuses the existing 6-role `TASK_ROLES` vocabulary
(`shared/sdk/tasks/rbac.py`: `requester`, `pm_engineering_lead`, `reviewer_approver`,
`platform_admin`, `agent_operator`, `security_compliance_reviewer`) — it does not invent new role
names. The conceptual Member/Operator/Admin groupings below are a summary lens over these 6 real
roles for readability, not a second role system.

## Member-tier capabilities (maps to: requester)

```text
- view allowed task/workroom (existing, unchanged).
- answer clarification when authorized (existing, unchanged -- requester may answer own task's
  clarifications).
- CANNOT force resume: requester is deliberately excluded from `can_request_resume` (Option A) --
  matches the existing exclusion of requester from clarification-CREATION, which is an
  operator-decided precedent (Step 66C.1 spec §7) this contract extends by analogy, not by new
  decision.
- CANNOT retry a timeout transition: no such endpoint is proposed at all (see
  api-and-event-contract.md's "Explicitly NOT proposed" section) -- this is moot for every role.
```

## Operator-tier capabilities (maps to: pm_engineering_lead, platform_admin, agent_operator)

```text
- view operational state (existing -- these 3 roles already have audit-evidence access).
- request/authorize controlled resume, IF Option A is selected (new capability
  `can_request_resume` -- see controlled-resume-contract.md).
- retry safe failed transition: NOT applicable -- no retry-timeout-transition endpoint is
  proposed; the scheduler's own poll cycle already self-heals (see race-condition-and-failure-
  analysis.md scenario 14).
- CANNOT bypass production approval: a production-effect task remains blocked from resume
  regardless of role (rbac-and-safety-contract.md §"Safety invariants" below) -- no role,
  including platform_admin, may override this via the resume path proposed here.
```

## Admin-tier capabilities (maps to: platform_admin, with security_compliance_reviewer for
audit-only visibility)

```text
- operational recovery within policy: platform_admin already has the broadest existing operational
  role; no NEW admin-only capability beyond what's already listed under Operator-tier above is
  proposed for this stage's scope.
- audit visibility: security_compliance_reviewer already has audit-evidence read access
  (existing, unchanged) and would see the new event types (clarification_reminder_sent,
  clarification_expired, clarification_resume_*) through the SAME existing allowlist projection,
  no new grant needed.
- CANNOT bypass production governance: same invariant as above, no role exception.
```

## Proposed new RBAC capability functions (following the exact naming/shape convention of
`shared/sdk/tasks/workroom_rbac.py`)

```python
_REQUEST_RESUME_ROLES: frozenset[str] = frozenset(
    {"pm_engineering_lead", "platform_admin", "agent_operator"}
)

def can_request_resume(role: str) -> bool:
    return role in _REQUEST_RESUME_ROLES

def can_view_resume_eligibility(role: str) -> bool:
    return role in _REQUEST_RESUME_ROLES  # same 3 roles; no separate viewer-only tier proposed
```

No new capability function is proposed for the reminder/expiry transitions themselves — those are
performed exclusively by the backend scheduler process, never by any human-facing role, so there
is no RBAC surface to define for them (they are not reachable via any API endpoint a role could
call).

## What remains M3's responsibility (explicitly NOT redesigned here)

```text
- Full team/project role model (beyond the existing 6 TASK_ROLES).
- Full task assignment permissions (beyond the existing requester/assignee distinction already in
  the clarification model).
- Team/project visibility boundaries (cross-task visibility is explicitly M3 scope per
  team-visibility-model.md, absorbed into the Master Plan's canonical-milestone-manifest.md M3
  section).
- The full operator action permission matrix (this contract adds exactly 2 new capability checks,
  scoped narrowly to this stage's own resume-request/view-eligibility needs -- it does not attempt
  a general-purpose permission matrix).
- Approval/retry/replay/recovery permission MODEL (M3's job to design comprehensively; this
  contract only states that the existing DLQ/retry-scheduler's own established permission pattern
  is reused unchanged for any 66C.4 failure recovery, per scheduler-architecture-decision.md).
```

## Safety invariants (binding, non-negotiable, apply regardless of which resume option the
Product Owner selects)

```text
1. production_executed_true_count remains 0 throughout this stage and throughout any future
   implementation stage's test-runtime-only work -- no implementation authorized by this planning
   stage touches production in any way.
2. A production-effect task cannot resume without required approval -- this is not a NEW
   invariant, it is the EXISTING `production_effect`/`requires_approval` safety-field pattern
   already surfaced on TaskDetail, extended (not modified) to also gate the new resume path.
3. Cancelled/aborted/terminal workflows cannot resume -- enforced by the task-state check in
   controlled-resume-contract.md §2.3/§8, re-evaluated at both eligibility time and authorization
   time.
4. Duplicate scheduler execution is harmless -- guaranteed by the CAS-guard idiom applied
   uniformly to every new transition (reminder-claim, expiry-claim, resume-request,
   resume-authorization), the same mechanism already proven correct for the existing answer-claim.
5. Duplicate answer remains rejected -- UNCHANGED, this stage introduces no modification to the
   existing answer-claim logic at all.
6. External notifications remain disabled -- every event proposed in api-and-event-contract.md is
   INTERNAL only; no external channel integration is proposed or implied.
7. All state changes are auditable -- every new transition (reminder sent, expired, resume
   eligible/requested/authorized) has a corresponding new audit event type, following the existing
   `audit_events.py` allowlist-projection pattern with zero raw-content exposure.
```

## Statement

Planning document only. No RBAC code implemented. No safety-check code implemented. This document
proposes the minimum RBAC needed for M1's Step 66C.4 scope only — full Team RBAC remains M3's
responsibility.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
