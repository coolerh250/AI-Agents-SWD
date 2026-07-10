# Step 66B.2 — Task Assignment UI Safety Record

> **No workflow dispatch occurred. No external action occurred. No production action occurred.
> production_executed_true_count=0. Test-only role simulation is not production auth.**
>
> **Step 66B.3 update:** the role dropdown now shows readable labels ("PM / Engineering Lead", etc.
> — `TASK_ROLE_LABELS`) instead of raw role strings; a visible `current-identity` readout shows the
> active simulated actor/role; RBAC/auth errors now render a readable sentence alongside the raw
> detail code; a concise safety panel was added to `/tasks/{id}`. See
> `step66b3-rbac-audit-safety-hardening-report.md`.

## 1. Test-only role simulation (not production auth)

- Backend gate (Step 66B.1): `TASK_API_TEST_AUTH_ENABLED` must be exactly `"true"`, else every
  `/tasks` request is `403 task_api_test_auth_disabled` (fail-closed). There is **no production
  auth path** implemented for this API — this is a documented gap (see `step66b2-known-gaps.md`).
- UI side (`src/tasks/testRole.ts`): stores a plain `{actor, role}` label in
  `localStorage["aiagents.taskApi.testRole.v1"]` — **never** a token, session identifier, or
  credential of any kind (enforced by `taskApiGuard.test.ts`, which asserts the module never
  references a token/credential/csrf/cookie value).
- Visible on every task page via `TestRoleBanner` (`data-testid="test-role-banner"`): **"Test role
  simulation active — not production auth."**
- **Default role: Requester** (least-privilege default). Switchable to any of the 6 roles from the
  RBAC blueprint (`requester`, `pm_engineering_lead`, `reviewer_approver`, `platform_admin`,
  `agent_operator`, `security_compliance_reviewer`) for testing other capabilities.
- No production-mode variant exists or is planned in this stage; a real identity/session model is
  explicitly deferred (documented gap, carried over from `step66b1-known-gaps.md`).

## 2. RBAC is not weakened

The UI does not bypass or duplicate RBAC — it only sets the two headers the Step 66B.1 backend
already requires and enforces server-side (`shared/sdk/tasks/rbac.py`). Denied actions surface the
backend's exact error (`role_cannot_create_task`, `role_cannot_view_tasks`, `role_cannot_submit_task`,
`not_own_task`) via `ErrorState`/inline error text — the UI does not attempt to hide or downgrade
these.

## 3. `production_effect=true` UI behavior matches backend exactly

The UI never claims a `production_effect=true` task will run. Both `TaskNew` and `TaskDetail` render
a `.warn-banner` stating: **will NOT execute or dispatch a workflow; requires approval; recorded
blocked/waiting-approval, never run; no production action is allowed from this UI.** This mirrors the
Step 66B.1 backend behavior exactly (task forced to `blocked`, `requires_approval=true`, policy
decision audited, never dispatched).

## 4. No workflow dispatch

- `TaskDetail.tsx` always renders `dispatch_enabled: false` as a static fact (the `GET /tasks/{id}`
  response doesn't even carry this field — it's a system-wide invariant in this stage, not
  conditionally read from the API).
- `TaskNew`/`TaskDetail` only ever call `taskApi.create()` / `taskApi.submit()`, which map 1:1 to the
  Step 66B.1 `POST /tasks` / `POST /tasks/{id}/submit` endpoints — neither of which dispatches a
  workflow (confirmed in 66B.1; unchanged here).

## 5. No external action

`taskApiGuard.test.ts` asserts `src/tasks/` never references a GitHub/Discord/Slack/Telegram/
Anthropic/OpenAI endpoint or hostname, and never calls anything outside the `/tasks` API base.

## 6. No production action

- No production deploy, no production secret, no production data touched.
- `environment` is restricted to `test`/`staging` in both the UI dropdown and the backend (defense in
  depth — the backend's DB `CHECK` constraint already rejects `production`).
- `production_executed_true_count` verified `0` on the test runtime before and after UI validation
  (see `step66b2-task-assignment-ui-evidence.md`).

## 7. Plain statements (for verifier)

- No workflow dispatch occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.
- Test-only role simulation is not production auth.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
