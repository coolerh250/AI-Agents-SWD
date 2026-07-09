# AI Agents Team Work — API Blueprint (Step 66A.3)

> **Blueprint / scope only. Proposed API — NOT implemented. No endpoint built, no runtime change, no
> external action, no production action.**

Each endpoint: purpose · required role · request/response summary · audit event · risk · stage.

| Endpoint | Purpose | Required role | Req / Resp summary | Audit event | Risk | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /tasks` | create task | Requester/PM/Lead/Admin | {title,type,project} → {task_id,state:draft} | task.created | low | 66B |
| `GET /tasks` | list tasks (role-scoped) | any (own for Requester) | filters → [task] | task.viewed | low | 66B |
| `GET /tasks/{id}` | task detail | participant | — → {task,state,participants} | task.viewed | low | 66B |
| `POST /tasks/{id}/submit` | submit task | Requester/PM/Lead | — → {state:submitted} | task.submitted | low | 66B |
| `POST /tasks/{id}/clarifications/{cid}/answer` | answer clarification | participant | {answer} → {state} | task.clarification_answered | low | 66C |
| `GET /tasks/{id}/workroom` | workroom messages | participant | — → [message] | workroom.viewed | low | 66C |
| `POST /tasks/{id}/workroom/messages` | post message | participant (RBAC by type) | {type,body} → {message_id,correlation_id} | workroom.message_posted | low | 66C |
| `GET /deliveries` | delivery inbox | PM/Lead/Reviewer | — → [delivery] | delivery.viewed | low | 66D |
| `GET /deliveries/{id}` | delivery detail | PM/Lead/Reviewer | — → {package} | delivery.viewed | low | 66D |
| `POST /deliveries/{id}/accept` | accept | PM/Lead/Reviewer/Admin | — → {state:accepted} | delivery.accepted | med | 66D |
| `POST /deliveries/{id}/reject` | reject | PM/Lead/Reviewer/Admin | {reason} → {state:rejected} | delivery.rejected | med | 66D |
| `POST /deliveries/{id}/request-changes` | request changes | PM/Lead/Reviewer/Admin | {note,size} → {state} | delivery.changes_requested | med | 66D |
| `POST /deliveries/{id}/rerun-qa` | re-run QA (≤3) | PM/Lead/Reviewer | — → {state:qa_rerun,seq} | delivery.qa_rerun | med | 66D |
| `POST /deliveries/{id}/escalate` | escalate | any review role | {reason} → {state:escalated} | delivery.escalated | med | 66D |
| `GET /operator/actions` | action-center queues | Admin/Agent-Op/Reviewer | — → {queues} | operator.viewed | low | 66G |
| `GET /operator/approvals` | pending approvals | Reviewer/Approver/Admin | — → [approval] | approval.viewed | med | 66D/66G |
| `POST /operator/approvals/{id}/approve` | approve | Reviewer/Approver/Admin | — → {approved} | approval.granted | high | 66D/66G |
| `POST /operator/approvals/{id}/reject` | reject | Reviewer/Approver/Admin | {reason} → {rejected} | approval.denied | high | 66D/66G |
| `GET /operator/dlq-retry` | DLQ/retry queue | Admin/Agent-Op | — → [dlq_entry] | dlq.viewed | high | 66D/66G |
| `POST /operator/dlq-retry/{id}/replay` | manual replay (D13) | **Admin/Agent-Op only** | — → {replayed} | dlq.replayed | **high** | 66D/66G |
| `GET /notifications` | notification feed | any (own) | — → [notification] | notification.viewed | low | 66G |
| `GET /settings/web-research-sources` | list whitelist | Admin/Sec review | — → [source] | source.viewed | low | future |
| `POST /settings/web-research-sources` | manage whitelist | Admin | {source} → {status} | source.changed | med | future |

## Cross-cutting

- All mutating endpoints are role-checked server-side (rbac blueprint) and emit audit events.
- Replay (D13) and Re-run-QA limit (D12) enforced at the endpoint.
- Existing read-only `/operations/*` reused where possible; no endpoint performs production effect
  (`production_executed_true_count=0`).
- `web-research-sources` endpoints are design-only; the connector is future work.

## 66B.1 implementation status (2026-07-09)

`POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/submit` are **implemented and
deployed** on the test runtime (`apps/orchestrator/src/task_api.py`), matching the paths specified
above exactly (the deliberate `/tasks` vs. `/operations/*` deviation noted in the original blueprint).
Auth is a fail-closed test-only header simulation (`TASK_API_TEST_AUTH_ENABLED` +
`X-Task-Actor`/`X-Task-Role`), not a real session — documented gap, see
`step66b1-known-gaps.md`. All other endpoints in the table above remain design-only, staged for
66C–66G.

## Statement

API blueprint only — no endpoint implemented; no runtime change; no external action; no production
action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
