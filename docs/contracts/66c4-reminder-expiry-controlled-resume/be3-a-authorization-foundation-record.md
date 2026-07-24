# Step 66C.4-BE3-A — Authorization Foundation Implementation Record

> **Implementation record. Durable authorization FOUNDATION only. NOT FOR MERGE (Draft PR). NO
> resume/replay execution, NO public endpoint, NO dead-outbox replay adapter call, NO shared
> activation, NO deployment, NO shared DB migration. BE3-B and BE3-C are NOT implemented. The
> combined independent BE3-R review over BE3-A+B+C is still required before merge.**

## Scope

Built the durable authorization model, repository, policy service and internal service that back the
operator-controlled resume and authorized dead-event replay AUTHORIZATION contract
(be3-api-event-contract.md). Consuming an authorization is a durable single-use CAS; it does NOT
itself execute resume or replay.

## Files added

```text
migrations/032_be3_resume_replay_authorization.sql          -- durable authorization table (additive)
migrations/032_be3_resume_replay_authorization_down.sql     -- reverse
shared/sdk/tasks/authorization_model.py       -- enums, reason-code allowlist, state projection, safe audit payload
shared/sdk/tasks/authorization_repository.py  -- transaction-aware asyncpg CAS repository
shared/sdk/tasks/authorization_policy.py      -- RBAC + isolation + separation + production gate (fail-closed)
shared/sdk/tasks/authorization_service.py     -- internal orchestration; safe structured outcomes
tests/test_step66c4_be3_a_authorization_foundation.py
scripts/verify_step66c4_be3_a_authorization_foundation.py
```

No existing table is altered; migration 032 is additive (one new table). No existing runtime file is
modified.

## Authorization semantics

```text
resource-bound / action-bound / team+project-bound : resource_id, action_type, team_id, project_id.
single-use     : consumed_at (atomic CAS), chk_rra_consume_requires_authorized.
time-bounded   : expires_at (CHECK expires_at > requested_at); consume guards expires_at > statement_timestamp().
state-version-bound : resource_state_version; consume CAS requires it to still match.
revocable      : revoke() sets revoked_at only while authorized+unconsumed; a consumed row cannot be revoked.
durable decision / consumption : all persisted; a single authoritative state projection is exposed.
States: pending, authorized, rejected, canceled, expired, revoked, consumed.
Allowed transitions: pending->authorized/rejected/canceled/expired; authorized->consumed/revoked/expired.
```

Every transition uses PostgreSQL statement_timestamp() (never a Python local clock) and a guarded
CAS UPDATE ... RETURNING whose affected row is verified (None => CAS lost).

## RBAC and safety (reuses the six canonical TASK_ROLES; no second RBAC)

```text
- Operator {pm_engineering_lead, platform_admin, agent_operator} requests resume/replay; decides resume.
- Approver {reviewer_approver, platform_admin} authorizes replay; requester != approver (two-person),
  enforced by the policy service AND the chk_rra_replay_two_person DB constraint.
- Service Identity may ONLY consume an already-authorized action; it can never request/approve/reject/
  cancel/revoke.
- Team/project/resource isolation enforced in the policy service; cross-scope access is masked as
  not_found (existence not leaked). Nonexistent and cross-scope both return not_found_masked.
- Production-effect consume requires a separate production_approval_reference; a general authorization
  can never turn "production approval required" into "production approved". BE3-A neither creates nor
  validates production approval itself.
```

## Result model (API-independent, for a later HTTP mapping)

```text
ok, forbidden, not_found_masked, conflict, expired, stale_state, already_decided, already_consumed,
revoked, production_approval_required, invalid_transition.  Reason codes are a bounded allowlist.
```

## Audit evidence

A safe payload builder produces bounded, secret-free evidence
(authorization.requested/authorized/rejected/canceled/revoked/expired/consumed/consume_rejected).
It carries only identifiers, decision/reason codes, policy/state versions and idempotency identity —
NEVER a raw clarification/answer/replay body, secret, token, or DSN. No new runtime producer and no
external notification is enabled.

## Authorization posture

```text
Public HTTP endpoint:            NONE
Dead-outbox replay adapter call: NONE (no replay_dead invocation)
Resume execution / dispatch:     NONE
Shared DB migration applied:     NO (032 applied only to isolated ephemeral test DBs)
Worker/relay activation:         NO
Deployment:                      NO
BE3-B / BE3-C:                    NOT implemented
PR:                              Draft / NOT FOR MERGE
Combined independent BE3-R:      REQUIRED before merge
Codex / Claude Design:           NOT authorized
production_executed_true_count:  0
```

## Marker

```text
STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS   (BE3-A self-verification only)
```

## Statement

Implementation record only. Foundation, not activated. No resume/replay execution, no public
endpoint, no shared migration, no deployment. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
