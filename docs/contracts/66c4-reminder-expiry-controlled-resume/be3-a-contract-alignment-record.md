# Step 66C.4-BE3-A-C1 — Authorization Scope and Actor Contract Alignment

> **Targeted contract-alignment of BE3-A (same implementation session, no subagent). NOT FOR MERGE
> (Draft PR #20). No BE3-B, no public API, no resume/replay execution, no deployment.**

Three foundation alignment items were confirmed and minimally corrected.

## 1. Repository scope enforcement (dual-layer)

Before: repository transitions/reads keyed on `authorization_id` only and relied on the policy
layer for scope. Now: every actor-facing repository method (`get_authorization`, `approve`,
`reject`, `cancel`, `revoke`, `consume`) takes the actor's `scope_team_id`/`scope_project_id` and
binds them into the SQL predicate itself:

```text
(team_id IS NULL OR $t::uuid IS NULL OR team_id = $t::uuid)
AND (project_id IS NULL OR $p::uuid IS NULL OR project_id = $p::uuid)
```

A cross-scope call therefore reads nothing / affects 0 rows, and the service maps that to
`not_found_masked` (existence is never leaked). The policy service still performs the same
isolation check, so scope is enforced at BOTH layers. `expire_due_authorizations` is a
non-actor-facing maintenance op and is intentionally unscoped. Proven by
`test_pg_direct_repository_calls_cannot_bypass_scope` (direct repo calls with a mismatched scope
return None for read/approve/cancel/revoke/consume; the row is untouched).

## 2. Resume actor semantics

Before: `authorize_resume` was in the human `_ACTION_ROLES` map, so a plain Operator could
human-authorize a resume (including their own). Now: resume authorization is performed ONLY by the
automated policy/safety authority.

```text
request resume    -> Operator (human)              request_resume in _ACTION_ROLES
authorize/reject  -> policy/safety authority ONLY  _POLICY_AUTHORITY_ACTIONS (is_policy_authority)
consume           -> Service Identity ONLY         _CONSUME_ACTIONS (is_service_identity)
```

A plain Operator (incl. the requester) calling `authorize_resume` is denied
(`policy_authority_required`); a Service Identity is denied (`service_identity_cannot_decide`); the
policy authority may only authorize/reject resume, nothing else (`policy_authority_scope`).
`decided_by` is the authorizing principal (the policy authority), never the requester. Replay
authorization remains a human two-person control (Approver, requester != approver) — unchanged.
Production-effect resume still requires the separate production approval reference before consume.
Proven by `test_pg_resume_actor_model_operator_policy_authority_service` and
`test_pg_production_effect_resume_still_gated`.

## 3. Scope identifier types

`project_id` and `team_id` are now the canonical **UUID** type (migration 032 revised in place, as
it is unmerged/unapplied — no 033). `project_id` is the canonical `operator_tasks.project_id` (a
UUID); every identity in this system is a UUID, so a team scope key is a UUID too. Using the UUID
type removes all whitespace/case/spelling ambiguity at the storage layer (no TEXT normalization
code needed). No FK is declared: `operator_tasks.project_id` itself carries no FK and is nullable,
and an outbox_event resource's project scope is derived, so a FK would be unsound. The choice is
NOT justified by "operator_tasks has no team_id"; it is justified by the canonical UUID identity
convention.

## Verification

```text
STEP66C4_BE3_A_CONTRACT_ALIGNMENT_VERIFY: PASS
STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS
Tests: 17 passed / 0 skipped / 0 failed on isolated ephemeral PostgreSQL 16 (regression 85 passed).
ruff / black / mypy: PASS.  No public API, no replay_dead call, no resume/dispatch, no shared
migration/deployment, no BE3-B. production_executed_true_count = 0.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
