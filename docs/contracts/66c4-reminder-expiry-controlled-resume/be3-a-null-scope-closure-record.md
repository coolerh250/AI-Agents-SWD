# Step 66C.4-BE3-A-C2 — NULL-Scope Wildcard Closure

> **Targeted closure of the repository scope predicate's NULL wildcard on BE3-A (same
> implementation session, no subagent). NOT FOR MERGE (Draft PR #20). No BE3-B, no public API, no
> resume/replay execution, no deployment.**

The BE3-A-C1 predicate treated a NULL as a wildcard
(`team_id IS NULL OR $t::uuid IS NULL OR team_id = $t::uuid`), so a NULL caller scope — or a NULL
row scope — could match across teams/projects. This stage closes that.

## 1. Scope model decision

`resume_replay_authorizations.team_id` and `.project_id` are now **UUID NOT NULL**. A resume/replay
authorization is always resource-bound to a team AND a project, so there is no legitimate
global/system scope here. If one is ever needed it must be modelled **explicitly** (e.g. a
`scope_type` column or a dedicated Service-Identity capability), never by leaving a scope NULL. The
migration (032) was revised in place — it is unmerged/unapplied, so no 033 was added.

## 2. Exact null-safe predicate

Every actor-facing repository read/transition now uses EXACT null-safe equality:

```sql
team_id IS NOT DISTINCT FROM $scope_team::uuid
AND project_id IS NOT DISTINCT FROM $scope_project::uuid
```

Because the row columns are NOT NULL, a NULL caller scope matches no row (fail-closed) and a
mismatched UUID matches no row. NULL is never a widening wildcard. The `$provided IS NULL` relaxation
is gone. `expire_due_authorizations` remains the only unscoped operation: it is a non-actor-facing
maintenance scan, not an actor read/transition.

## 3. Repository methods

`get_authorization`, `get_active_by_resource`, `approve`, `reject`, `cancel`, `revoke`, `consume`
all bind `authorization_id`/`resource_id`, `team_id`, and `project_id` (plus resource_type/id where
applicable) via the shared exact predicate. A 0-row result is surfaced as `not_found_masked` with no
row mutation and no metadata leak.

## 4. Policy layer (dual-layer preserved)

`_isolation_ok` is now fail-closed: a missing (None) scope on EITHER the actor or the resource is a
denial (`cross_team_denied` / `cross_project_denied` → masked as `not_found`). Scope is therefore
enforced at BOTH the policy layer and the repository SQL, and neither treats NULL as a wildcard.

## 5. Tests (isolated ephemeral PostgreSQL 16)

```text
tests/test_step66c4_be3_a_authorization_foundation.py -> 20 passed / 0 skipped / 0 failed
```

New in C2:
- `test_pg_null_caller_scope_is_not_wildcard` — a NULL caller team OR project reads nothing and
  cannot approve/cancel/revoke/consume; exact scope still reads/transitions; a mismatched UUID stays
  masked; `get_active_by_resource` is scoped the same way.
- `test_pg_null_row_scope_rejected_by_not_null_schema` — a NULL team_id/project_id insert is rejected
  by the NOT NULL schema (so no NULL-scope row can ever exist to be matched by an arbitrary caller).
- `test_pg_service_null_scope_fail_closed` — a service request with a NULL scope is denied and
  creates no row; a NULL-scope actor cannot even see an existing row; a direct NULL-scope repository
  CAS is a no-op.

Backend DB regression (shared migration chain 029–031 + operator/RBAC/BE1/BE2 + BE3-A):
`186 passed / 5 skipped / 0 failed`. The 5 skips are pre-existing Redis-dependent BE2 relay tests
(no isolated ephemeral Redis configured for this run); they are non-mandatory and unrelated to this
change. All PostgreSQL work ran on an isolated ephemeral PostgreSQL 16 container on a spare local
port, destroyed afterward; the shared internal test stack was NOT touched.

## Verification

```text
STEP66C4_BE3_A_NULL_SCOPE_CLOSURE_VERIFY: PASS
STEP66C4_BE3_A_CONTRACT_ALIGNMENT_VERIFY: PASS
STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS
ruff / black / mypy: PASS. No public API, no replay_dead call, no resume/dispatch, no shared
migration/deployment, no BE3-B. production_executed_true_count = 0.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
