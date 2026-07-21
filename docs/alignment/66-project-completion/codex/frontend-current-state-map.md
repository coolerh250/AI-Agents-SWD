# Frontend Current-State Map

Step: 66ALIGN.1-CODEX

Marker: `STEP66ALIGN1_CODEX_VERIFY: PASS`

## Shared Context

- Latest main reviewed: `690b700`.
- Branch: `alignment/66-project-completion-codex`.
- Scope: analysis and documentation only.
- Runtime code changed: no.
- `source/progress.md` changed: no.
- Backend, API, database, workflow, merge, deployment: no.
- FE.1D-S2 status: useful polish, not critical path.
- SPA deep-link fallback: backend/platform gap; no frontend workaround should be presented as a fix.

## Admin Console Shape

The Admin Console is a React/Vite application with React Router routes declared in `App.tsx`. It has
three distinct frontend surfaces:

1. Core human-agent task loop: `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/tasks/:taskId/workroom`.
2. Delivery/operator/evidence surfaces: `/delivery-package`, `/delivery`, `/operator`,
   `/agent-executions`, `/audit-evidence`, `/safety`, and Platform Ops pages.
3. Placeholder future surfaces: `/notifications`, `/clarifications`, `/clarification-reminders`,
   `/delivery-inbox`, `/delivery-detail`, `/approvals`, `/dlq-retry`, `/settings/*`.

Navigation has the 7 approved groups: Overview, Team Work, Deliveries, Operator Center, Governance,
Platform Ops, Settings. Step 66UI.4-FE.1D-S1 is already merged to main, so current nav includes group
subtitles, `Soon`, `Read-only`, and `Evidence` badges, and compact Platform Ops treatment.

## Route Map

| Group | Existing routes | Current state |
| --- | --- | --- |
| Overview | `/`, `/notifications` | Overview is attention-first; Notifications is placeholder. |
| Team Work | `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/tasks/:taskId/workroom`, `/clarifications`, `/clarification-reminders` | Tasks and Workroom are real; Clarifications and Reminder/Expiry top-level routes are placeholders. |
| Deliveries | `/delivery-inbox`, `/delivery-detail` | Both placeholders requiring Step 66D. |
| Operator Center | `/operator`, `/incidents`, `/agent-executions`, `/approvals`, `/dlq-retry` | Operator Console and Agent Executions exist; Approvals and DLQ/Retry are placeholders. |
| Governance | `/safety`, `/audit-evidence` | Safety and audit/evidence review surfaces exist. |
| Platform Ops | `/projects`, `/projects/:projectId`, `/delivery`, `/task-graph`, `/qa-code`, `/design-review`, `/workspace`, `/mini-delivery`, `/delivery-package`, `/regression`, `/cost-llm`, `/runtime`, `/identity`, `/secrets`, `/security`, `/metrics`, `/sandbox-github`, `/release-governance`, `/backup-dr`, `/production-readiness`, `/controlled-rollout-review` | Mostly read-only operational/evidence views; `/delivery` has controlled project/work-item mutations. |
| Settings | `/settings/roles-permissions`, `/settings/identity-session`, `/settings/integrations`, `/settings/web-research-sources`, `/settings/approval-policy` | Placeholders requiring Step 66S or later. |

## API Client Map

| Client | Pattern | Current capabilities | Important constraints |
| --- | --- | --- | --- |
| `api/client.ts` | Generic GET-only wrapper | Read-only operations API access. | No write verbs; read-only guard tests enforce this. |
| `api/operations.ts` | Named GET functions | Overview, delivery state, safety, metrics, evidence, runtime, security, rollout, DR, release, and other operations reads. | Many responses are `Record<string, unknown>`, so frontend contracts are loose. |
| `tasks/taskClient.ts` | Named task methods | list, create, get, submit. | Sends test actor/role headers; no workflow dispatch; readable RBAC errors. |
| `tasks/workroomClient.ts` | Named workroom methods | get workroom, post message, create clarification, answer clarification, get audit evidence. | Plain text rendering; safe audit metadata only; no dispatch/resume. |
| `operator/actionClient.ts` | Named controlled action methods | operator session, CSRF, delivery package review, verification rerun, project/work-item create and dispatch. | Mutations require session cookie, CSRF, idempotency key; no generic mutation helper. |

## Component Map

| Component | Reuse value |
| --- | --- |
| `Layout`, `Nav`, `NavGroup` | Stable app shell and navigation. |
| `AsyncView`, `LoadingState`, `ErrorState`, `EmptyState` | Basic read-state pattern; good for simple GET pages, not enough for cross-page action center state. |
| `DataCard`, `StatusBadge`, `SafetyBadge`, `CalmSafetyPosture` | Reusable status/posture presentation. |
| `PlaceholderPanel` | Safe placeholder pattern: not available, required step, no workflow action. |
| `EvidenceTable`, `KeyValueTable`, `JsonPanel` | Useful for evidence/admin views; needs product-label layer before user-facing delivery review. |
| `TestRoleBanner`, `testRole` | Current task RBAC test simulation only; not production auth. |
| `SessionBanner`, `OperatorReviewPanel`, `ConfirmDialog`, `OperatorActionHistory`, `DisabledFutureActions` | Controlled operator action patterns with session/CSRF/idempotency. |

## State Handling Map

| Area | Current state handling | Alignment implication |
| --- | --- | --- |
| Read-only operations pages | `AsyncView` runs loader once per mount. | Fine for M0/M6 read views; insufficient for live Action Center or multi-tab workroom state. |
| TaskList | Local filters; valid URL `status` initializes once; manual filter does not update URL. | Good enough for M1; avoid expanding to two-way sync without explicit stage. |
| TaskDetail | Local refresh key after submit. | Works for simple task state refresh, but richer task workspace will need clearer state model. |
| TaskWorkroom | Local refresh key after message/clarification mutations; audit evidence has its own local loading/restricted/error state. | Reusable for M1; would benefit from extracted hooks before large M3/M4 features. |
| Operator Console | Local session/action state per component. | Good safety pattern, but M4 needs a shared action/notification model rather than isolated component state. |
| Overview | Aggregates multiple requests in one loader with per-source capture. | Useful precedent for read-only aggregation, but not a shared cache. |

## Current Frontend Readiness

| Milestone | Current frontend readiness |
| --- | --- |
| M0 | Partly ready. Source-of-truth records and known platform gap exist; frontend still lacks a formal runtime-contract inventory. |
| M1 | Mostly ready for incremental improvement. Task, Workroom, Clarification, RBAC, and audit-evidence basics exist. |
| M2 | Not ready for real delivery acceptance until Step 66D backend contracts freeze. |
| M3 | Partly ready for read-only activity from existing execution data; not ready for multi-role orchestration control assumptions. |
| M4 | Mostly placeholder. Needs contracts and likely new shared state/data-fetching pattern. |
| M5 | Partly ready as a pilot shell; needs M1-M4 contract closure and test-runtime validation choreography. |
| M6 | Many read-only Platform Ops pages exist; production hardening needs clearer frontend governance, auth, accessibility, and evidence contracts. |
| M7 | Not yet ready; adoption UX, onboarding, monitoring, and role-specific production workflows remain future work. |
