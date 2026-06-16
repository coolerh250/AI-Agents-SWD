# Admin Console v1 — Operator Actions (Stage 52 / Step 50)

Upgrades the Admin Console from read-only visibility (v0) to a **controlled
Operator Console**: low-risk, reversible, audited operator actions with a clear
policy boundary. This is **not** an unrestricted admin console, **not** a
production control plane, and opens **no** arbitrary workflow manipulation.

## Enabled controlled actions

| Action                        | Roles                              | Confirmation |
| ----------------------------- | ---------------------------------- | ------------ |
| `operator_review.add_note`    | reviewer / operator / platform_admin | no         |
| `delivery_package.request_changes` | reviewer / operator / platform_admin | yes    |
| `delivery_package.accept`     | operator / platform_admin          | yes          |
| `delivery_package.reject`     | operator / platform_admin          | yes          |
| `verification.rerun` (allowlisted) | operator / platform_admin     | yes (full_regression: higher) |

## Disabled (display-only, never executable)

workflow pause/resume/dispatch, work_item.update_status, project.cancel,
github.create_pr/merge_pr, deployment.execute, backup.production_run/restore,
policy.update, model_policy.update, budget.update, incident.real_escalate.
Disabled endpoints return `403 policy_blocked` / `409 action_disabled`.

## Core principles

- UI actions never write the DB directly — they call governed backend action
  APIs.
- Every action requires: authenticated session, RBAC, CSRF, policy-engine
  check, a reason, a one-time confirmation (for medium-risk), idempotency key,
  and an audit event.
- **Delivery acceptance is a HUMAN REVIEW acceptance only.** It never triggers
  GitHub, PR, merge, deploy, external delivery, or production.
- Verification rerun executes only allowlisted scripts (static server-side
  map); never a user-supplied path / arg / shell string.

## Architecture

- Backend: `shared/sdk/operator_actions/` (auth, session, csrf, rbac,
  action_catalog, policy_gate, confirmation, idempotency, verification_runner,
  store, audit_events, events, safety) + `apps/orchestrator/src/operator_actions_api.py`.
- Frontend: `apps/admin-console/src/operator/` (a delineated, audited module
  with explicit typed action methods only — no generic request()) + the
  Operator Console page at `/operator`.
- Migration `023_admin_console_operator_actions.sql` (10 tables; no raw token /
  secret columns).

## Authentication

Test-local signed session (`ADMIN_CONSOLE_AUTH_MODE=test_local_signed_session`).
Production auth / OIDC are required-but-unconfigured and stay disabled; unknown
auth modes fail closed. See `docs/operations/admin-console-auth-session.md`.

## Verification

`scripts/verify_admin_console_v1_operator_actions.sh`
(`ADMIN_CONSOLE_V1_OPERATOR_ACTIONS_VERIFY: PASS`).

## Production caveat

Controlled test only. Claude Code does NOT declare production readiness;
production auth (OIDC), real secret store, and the rest of the carry-forward
substrate remain operator decisions.
