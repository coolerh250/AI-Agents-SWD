# Incremental PR Slicing Plan

Step: 66ALIGN.1-CODEX

## Slicing Principles

- Ship by milestone dependency, not by cosmetic preference.
- Freeze API contracts before building real UI over placeholder routes.
- Keep each PR reviewable by Product Owner and Claude Code.
- Pair every runtime PR with tests, safety statement, and validation checklist.
- Do not make FE.1D-S2 a critical path item.

## Recommended Sequence

| Slice | Milestone | Frontend scope | Required before start |
| --- | --- | --- | --- |
| 1 | M0 | Frontend route/API contract inventory and source-of-truth reconciliation docs/tooling. | Agreement on inventory format. |
| 2 | M1 | Extract Workroom subcomponents without behavior change; preserve tests. | Claude Code boundary for extraction-only frontend work. |
| 3 | M1 | Clarification queue improvements inside Workroom; readable empty/error/focus states. | Confirm no Step 66C.4 reminder contract is needed. |
| 4 | M1 | Top-level Clarifications route, only if cross-task contract exists. | Step 66C.4 or equivalent API contract. |
| 5 | M2 | Delivery contract fixture tests and read-only Delivery Inbox shell. | Step 66D list/detail contract frozen. |
| 6 | M2 | Delivery Detail with evidence/readiness sections. | Step 66D detail/evidence contract frozen. |
| 7 | M2 | Acceptance decision controls with reason, confirmation, audit refresh. | Step 66D mutation/capability/idempotency contract frozen. |
| 8 | M3 | Read-only agent activity detail using existing execution data. | Agent identity/status contract. |
| 9 | M3 | Multi-role orchestration visibility. | Role capability and server-filtered data contract. |
| 10 | M4 | Read-only Action Center aggregation. | Unified action item read contract. |
| 11 | M4 | Acknowledge/resolve/snooze actions. | Mutation/audit/channel contract. |
| 12 | M5 | Guided non-production pilot checklist and evidence package. | M1-M4 pass and pilot scenario contract. |
| 13 | M6 | Typed Platform Ops/readiness evidence hardening. | Readiness/evidence/access-review contracts. |
| 14 | M7 | Production auth/settings/adoption shell. | Production auth/session/preferences contracts. |

## FE.1D-S2 Placement

FE.1D-S2 should be split and absorbed into runtime slices:

- Status-label map: combine with M1 TaskList or Workroom extraction.
- Relative time and task microcopy: combine with M1 TaskList/TaskDetail work.
- TaskDetail technical details: combine with M1 or M2 task-delivery context work.
- Placeholder wording: combine when M2/M4 placeholders are replaced.
- Safety wording cosmetic: combine with M6 safety hardening.

Do not run a standalone FE.1D-S2 polish PR ahead of M1/M2 contracts unless Product Owner explicitly
wants polish-only work. It would consume review capacity without unlocking production completion.

## Paused Work

- Platform Ops optional visual sub-headers.
- Broad raw field relabeling across audit/evidence tables without a map.
- Workroom `body_hash` relabel without a Workroom slice.
- Notifications/channel controls before M4 contract.
- Delivery Inbox/Detail real UI before Step 66D.
- SPA deep-link fallback workaround in frontend.
- Two-way URL sync.
- Production-like settings pages before M7 auth/settings contracts.

## PR Review Checklist

Every runtime PR should answer:

1. Which milestone does this unblock?
2. Which backend contract does it depend on?
3. Which routes changed, if any, and was that authorized?
4. Which components were reused or extracted?
5. Which RBAC states are server-authoritative?
6. Which tests were added and which full-suite checks passed?
7. What Product Owner preview should validate?
8. What remains deferred?
