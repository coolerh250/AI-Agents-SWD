# Step 66C.3 — Message Visibility Evidence (G1)

> **Evidence only. No production action. No external action.**

## 1. Enforced matrix (actual, not the spec's illustrative table)

The 66C.3 spec's illustrative per-role table left several combinations ambiguous ("if currently
treated as...", "if currently documented..."). Rather than overclaim, `shared/sdk/tasks
/workroom_rbac.py::_VISIBILITY_ROLES` implements this deliberately conservative, fail-closed matrix:

| `visibility` value | Roles that can see it |
| --- | --- |
| `task_participants` | all six roles (unchanged from 66C.1/66C.2 — still subject to the existing Requester-to-own-task scoping check) |
| `operators` | `pm_engineering_lead`, `platform_admin`, `agent_operator` |
| `audit_only` | `security_compliance_reviewer` only (everyone else must use `GET .../audit-evidence`, if their role allows it) |
| `private_system` | `platform_admin`, `agent_operator` only |
| any other / unrecognized value | **nobody** — fail-closed, not an error |

Consequently:
- **Requester** sees only `task_participants` messages for its own task.
- **PM/Engineering Lead** sees `task_participants` + `operators`, not `audit_only`/`private_system`.
- **Reviewer/Approver** sees only `task_participants` (not `operators` — a deliberate choice, since
  the spec's own language for this role was "if currently documented" / "otherwise denied", and no
  prior stage documented Reviewer/Approver as operator-level staff).
- **Platform Admin** / **Agent Operator** see `task_participants` + `operators` + `private_system`,
  not `audit_only` (they can reach the same events plus additional non-visibility-scoped context via
  the audit-evidence endpoint instead).
- **Security/Compliance Reviewer** sees `task_participants` + `audit_only`, not
  `operators`/`private_system`.

## 2. Server-side enforcement (not frontend-only)

`GET /tasks/{task_id}/workroom` (`apps/orchestrator/src/workroom_api.py::get_workroom`) calls
`filter_messages_by_visibility(messages, ctx.role)` on every response, after fetching the full
unfiltered list from `WorkroomStore.list_messages`. The Workroom UI (`TaskWorkroom.tsx`) never
re-filters — it only ever renders `data.messages` exactly as returned. This is proven by
`test_filter_messages_by_visibility_is_server_side_not_frontend_only`
(`tests/test_step66c3_workroom_audit_visibility.py`), which asserts the raw store holds more messages
than a restricted role's API response returns.

## 3. Test evidence (backend, `tests/test_step66c3_workroom_audit_visibility.py`)

- `test_requester_sees_only_task_participants_messages`
- `test_platform_admin_sees_participants_operators_and_private_system`
- `test_agent_operator_sees_participants_operators_and_private_system`
- `test_pm_engineering_lead_sees_operators_but_not_audit_only_or_private_system`
- `test_security_compliance_reviewer_sees_audit_only_but_not_operators_or_private_system`
- `test_reviewer_approver_sees_only_task_participants`
- `test_unknown_visibility_value_is_fail_closed_even_for_platform_admin`
- `test_filter_messages_by_visibility_is_server_side_not_frontend_only`

## 4. Frontend evidence

`WorkroomAuditVisibility.test.tsx` confirms the Workroom page shows a visibility note ("Some
operator-only or audit-only messages may be hidden based on your role.") and renders exactly the
messages the (mocked) API response contains — no client-side filtering or addition.

## 5. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
