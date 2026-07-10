# Step 66B.3 — RBAC Validation Evidence

> **Validation evidence only. No workflow dispatch occurred. No external action occurred. No
> production action occurred. production_executed_true_count=0.**

## 1. Fail-closed auth (missing / invalid)

| Case | Header sent | Result |
| --- | --- | --- |
| Missing `X-Task-Actor` | `X-Task-Role` only | `401 missing_actor` |
| Missing `X-Task-Role` | `X-Task-Actor` only | `401 missing_role` (Step 66B.3: previously indistinguishable from `invalid_role`) |
| Invalid `X-Task-Role` (not one of the 6 roles) | both headers, bogus role value | `401 invalid_role` |
| `TASK_API_TEST_AUTH_ENABLED` unset/false | any headers | `403 task_api_test_auth_disabled` (unchanged from 66B.1) |

Verified by `tests/test_step66b3_rbac_audit_safety.py::test_missing_actor_denied`,
`::test_missing_role_denied`, `::test_invalid_role_denied`,
`::test_missing_role_distinct_from_invalid_role`.

## 2. Requester own-task scoping

| Case | Result |
| --- | --- |
| Requester creates own task | `201`, `created_by` = requesting actor |
| Requester views own task (`GET /tasks/{id}`) | `200`, full task, `dispatch_enabled: false` |
| **Requester views another actor's task** | `403 not_own_task`, audited as `task_rbac_denied` |
| Requester submits own draft (`POST /tasks/{id}/submit`) | `200`, `status: intake_review` |
| **Requester submits another actor's draft** | `403 not_own_task`, audited as `task_rbac_denied` |
| Requester lists tasks (`GET /tasks`) | scoped server-side to `created_by = ctx.actor` regardless of the `created_by` filter requested |

Verified by `test_requester_creates_own_task`, `test_requester_views_own_task`,
`test_requester_cannot_view_other_actor_task`, `test_requester_submits_own_draft`,
`test_requester_cannot_submit_other_actor_draft` (all in
`tests/test_step66b3_rbac_audit_safety.py`), plus the pre-existing
`test_list_tasks_requester_scoped_to_own` (66B.1 test file).

## 3. Platform Admin view-all

`Platform Admin` is **not** scoped by `created_by` — `GET /tasks` returns every task regardless of
who created it. Verified by `test_platform_admin_views_all_tasks` (creates tasks as two different
Requester actors, confirms Platform Admin's list returns both).

## 4. Reviewer / Approver cannot create task (documented, not overclaimed)

The current implementation's `_CREATE_ROLES` set is `{requester, pm_engineering_lead,
platform_admin}` — `reviewer_approver` is **not** included and is denied `403
role_cannot_create_task` (audited as `task_rbac_denied`). This matches the "Create task" row of
`ai-team-work-rbac-blueprint.md`. Verified by `test_reviewer_approver_cannot_create_task`.

## 5. `production_effect=true` — blocked / approval-required, never dispatched

Unchanged from 66B.1 (re-verified in this hardening pass): a `production_effect=true` task is
always forced to status `blocked`, `requires_approval=true`, `dispatch_enabled=false`, and audited
as `task_rejected_by_policy` — whether that happens at create-with-submit or at a later
`POST /tasks/{id}/submit`. Verified by `test_production_effect_true_blocked_and_not_dispatched`.

## 6. Submit permissions

Submit shares the same role set as create (`requester`, `pm_engineering_lead`, `platform_admin`);
`agent_operator`, `reviewer_approver`, `security_compliance_reviewer` are denied `403
role_cannot_submit_task` (audited). Requester is additionally scoped to own drafts (see §2).

## 7. Test-only auth boundary (not production auth)

`TASK_API_TEST_AUTH_ENABLED` gates every `/tasks` endpoint; there is **no production auth path**
implemented. This is a documented, deliberate stand-in (carried over from 66B.1/66B.2) — see
`step66b3-known-gaps.md` §"Real identity/session/CSRF (future work)". Real identity/session/CSRF
remains future work; it does not weaken production safety today because it fails closed and no
production deployment would ever set this flag to `true`.

## 8. Live test-runtime validation (10.0.1.31, `aiagents-test`)

See `step66b3-test-deployment-record.md` for the live curl-equivalent RBAC checks executed against
the deployed orchestrator (invalid role fails closed, Requester cannot view another actor's task,
Platform Admin views all, `production_effect=true` blocked, `dispatch_enabled=false`,
`production_executed_true_count=0`).

## 9. Statement

No workflow dispatch occurred. No external action occurred. No production action occurred.
production_executed_true_count=0. Test-only role simulation is not production auth. Real
identity/session/CSRF remains future work.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
