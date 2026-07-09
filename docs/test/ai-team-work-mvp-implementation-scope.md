# AI Agents Team Work — MVP Implementation Scope (Step 66A.3)

> **Blueprint / scope only. No implementation, no backend change, no runtime change, no external
> action, no production action.**

## 1. In-scope (MVP)

Multi-role RBAC (D1); task assignment + task-type selection (D2/D14); Console+API intake first (D3);
full chat-style Agent Workroom (D9) + clarification pause/notify/wait/resume with 24h/72h timeout
(D4); Delivery Inbox + Accept/Reject/Request-Changes(small/major, D11)/Re-run-QA(≤3, D12)/Escalate/
Archive (D5); fixed Software Delivery Team (D6); Operator Action Center with Approvals P0 + DLQ/Retry
P0 (D8) and replay restricted to Admin/Agent-Op (D13); Admin Console + Discord notifications (D7);
web-research whitelist v0.1 governance design (D10, not executed).

## 2. Out-of-scope (MVP)

Custom / AI-suggested team composition; specialized non-software pipelines; unrestricted web browsing;
unapproved web sources; Telegram P0; Slack P0; production deployment; production secret handling;
production-effect execution; automatic external writes without approval.

## 3. Backend service changes (summary)

New product/UX surfaces + endpoints (see api-blueprint) atop existing services (orchestrator,
approval-engine, policy-engine, retry-scheduler/DLQ, audit, Discord rail); new data models (see
data-model-blueprint); RBAC enforcement layer. No production-effect path; `prod_exec=0` preserved.

## 4. Testing strategy

- Unit/contract tests for each new API + state machine (clarification, acceptance, classification,
  Re-run-QA limit, RBAC gates, replay permission).
- Frontend component/integration (vitest) per page; role-visibility tests.
- E2E on test host `10.0.1.31` (`aiagents-test`): assign → work → workroom → clarification → delivery
  → accept/request-changes, mock/dry-run, `prod_exec=0`.
- Governance tests: unauthorized role blocked; non-admin replay blocked; Re-run-QA >3 blocked; timeout
  → expired.
- Per-stage verifier + pytest + ruff/black/mypy + secret scan.

## 5. Audit & evidence model

Every mutating action emits an audit event (actor role, capability, target, correlation id); workroom
messages carry correlation ids linking to audit; deliveries retain evidence (requirements/impl/QA/PR/
cost/risks); notifications/messages redact secrets. `production_executed_true_count=0` invariant held.

## 66B.1 status update (2026-07-09)

**66B — first slice implemented (66B.1).** Task data model (`operator_tasks`, migration 029),
task lifecycle enum, and `POST/GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/submit` are live on
the test runtime with RBAC + audit + `production_effect` safety. Admin Console UI (66B.2) not yet
built. See `step66b1-task-api-foundation-report.md`.

## 66B.2 status update (2026-07-09)

**66B — second slice implemented (66B.2).** Admin Console Task Assignment UI (`/tasks`,
`/tasks/new`, `/tasks/{id}`) is live on the test runtime, consuming the 66B.1 API via a new
write-capable frontend module `src/tasks/` (mirroring `src/operator/`'s pattern but for the
fail-closed test-only `/tasks` auth). Test-role simulation banner, production_effect safety
warnings, and `dispatch_enabled: false` cues are all rendered. Operator validation requested but not
yet confirmed. See `step66b2-task-assignment-ui-report.md`.

## Statement

66B.1 (task API foundation) and 66B.2 (task assignment UI) are implemented; the remaining scope
(66C onward through 66H) is still design-only — nothing else implemented; no runtime change beyond
66B.1/66B.2; no external action; no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
