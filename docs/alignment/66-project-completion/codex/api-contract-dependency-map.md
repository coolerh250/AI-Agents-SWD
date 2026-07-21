# API Contract Dependency Map

Step: 66ALIGN.1-CODEX

## Current Contract Classes

| Class | Frontend files | Contract maturity | Notes |
| --- | --- | --- | --- |
| Read-only operations GET | `api/client.ts`, `api/operations.ts` | Medium | Guarded as GET-only, but many response types are loose `Record<string, unknown>`. |
| Task API | `tasks/taskClient.ts`, `tasks/taskTypes.ts` | Medium-high for M1 | Typed task create/list/get/submit. Test-role headers are current simulation, not production auth. |
| Workroom/Clarification API | `tasks/workroomClient.ts`, `tasks/workroomTypes.ts` | Medium-high for M1 | Typed messages, clarifications, safe audit evidence. No dispatch/resume. |
| Operator action API | `operator/actionClient.ts` | Medium for controlled non-production/operator actions | Named mutations with session/CSRF/idempotency. Needs careful product-stage gating. |
| Placeholder future APIs | routes for notifications, delivery inbox/detail, approvals, DLQ, settings | Low | No real frontend contract should be inferred from placeholders. |

## Milestone Dependencies

| Milestone | Existing APIs usable now | Missing or blocking contracts |
| --- | --- | --- |
| M0 | All current route/API files as inventory source. | Formal frontend contract registry. |
| M1 | `/tasks`, `/tasks/{id}`, `/tasks/{id}/workroom`, `/tasks/{id}/clarifications`, `/tasks/{id}/audit-evidence`. | Step 66C.4 reminders/expiry; cross-task clarification queue; post-answer transition/resume policy. |
| M2 | `latest-delivery-state`, delivery package operator review endpoints, project/work-item delivery endpoints. | Step 66D delivery inbox/detail, acceptance state machine, reviewer capability flags, delivery evidence package. |
| M3 | `/operations/agent-executions`, `/operations/workflows`, task/workroom data. | Agent identity/status taxonomy, assignment state, execution detail, safe reassign/retry/pause controls if ever authorized. |
| M4 | Existing task status filters and operator history can inform prototypes only. | Unified action item schema, notification/channel contracts, read/unread/ack/resolve/snooze, preferences, audit trail. |
| M5 | Combined M1-M4 APIs after contract freeze. | Pilot run/scenario/evidence package and validation checkpoint contract. |
| M6 | Existing Platform Ops read-only endpoints. | Typed readiness/evidence/finding/access-review contracts; stale-data and audit export contracts. |
| M7 | Existing shell and auth-adjacent operator session patterns. | Production auth/session, durable preferences, adoption metrics, support/runbook/channel contracts. |

## Blocking Contract Questions

1. Does Step 66D define Delivery as task-linked, project/work-item-linked, delivery-package-linked,
   or a combined model?
2. What is the canonical Delivery item ID and route parameter?
3. What states can a delivery item enter: ready, reviewed, accepted, rejected, changes requested,
   archived, expired?
4. Which roles can view, request changes, accept, reject, or add notes?
5. What fields constitute safe delivery evidence versus technical-only detail?
6. What is the backend source for cross-task clarifications and reminders in Step 66C.4?
7. What is an "action item" in M4: task status, clarification, delivery review, approval, DLQ,
   notification, or a normalized backend object?
8. Are notification channels read-only status first, or do they include outbound send/subscribe
   mutations? External sends require separate authorization.
9. What agent execution statuses are canonical, and which statuses imply human attention?
10. Which pilot checkpoints are machine-verifiable versus Product Owner validation checkpoints?

## Frontend Dependency Rules

- Do not infer missing backend state from labels, route names, or placeholders.
- Do not fabricate delivery counts, approvals, notifications, or agent activity.
- Do not create frontend-only RBAC. Use backend capability flags and server-filtered data.
- Do not add frontend routes before a Product Owner/Claude Code contract says the route exists.
- Do not represent the SPA deep-link fallback as frontend-fixable. It is a backend/platform gap.
- Keep task/workroom content plain text. No HTML/Markdown rendering or raw body exposure.
- Use typed contracts before turning Platform Ops evidence into operator decision UI.

## Suggested Contract Freeze Order

1. M1 clarification/reminder contract.
2. M2 delivery inbox/detail/decision contract.
3. M3 agent activity identity/status contract.
4. M4 action item and notification/channel contract.
5. M5 pilot scenario/evidence contract.
6. M6 production readiness/evidence/access-review contract.
7. M7 production auth/preferences/adoption contract.
