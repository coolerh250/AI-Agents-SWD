# Milestone Frontend Backlog

Step: 66ALIGN.1-CODEX

Canonical order:

```text
M0 - Source of Truth and Runtime Reconciliation
M1 - Core Human-Agent Interaction Loop
M2 - Delivery and Acceptance Loop
M3 - AI Team Orchestration and Multi-role Control
M4 - Notifications, Action Center and Channels
M5 - Controlled End-to-End Pilot
M6 - Production Readiness and Platform Hardening
M7 - Production Rollout and Adoption
```

FE.1D-S2 is not critical path. It should be folded into core work only where it naturally reduces
confusion on a touched surface.

## M0 - Source of Truth and Runtime Reconciliation

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | Nav route snapshot tests, `NAV_GROUPS`, `App.tsx`, `AsyncView`, read-only API guards, existing stage reports. |
| New components likely required | None for documentation-only reconciliation; optional generated route/API inventory doc tooling in a later authorized stage. |
| Existing routes | All current routes remain source-of-truth candidates; placeholders must stay explicitly marked. |
| New routes requiring authorization | None. New reconciliation routes are not recommended. |
| API dependencies | Existing operations and task APIs only, used for inventory verification. |
| Missing API contracts | A consolidated frontend contract registry that maps each page to endpoint, method, role, mutation risk, and backend owner. |
| State and error handling | Current `AsyncView` error handling is basic; M0 should document, not change, current behavior. |
| RBAC visibility requirements | Document which pages rely on server-side RBAC and which only show placeholders. |
| Accessibility requirements | Inventory keyboard/focus/heading gaps; do not implement in M0. |
| Test strategy | Static route/API inventory checks, no runtime code tests required unless tooling is added. |
| Preview/PO validation strategy | PM/PO reviews docs only; no deployment. |
| Risk of frontend getting ahead of backend | Low if M0 stays documentation-only; high if it tries to "normalize" contracts before backend ownership agrees. |

## M1 - Core Human-Agent Interaction Loop

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | `TaskList`, `TaskNew`, `TaskDetail`, `TaskWorkroom`, `MessageList`, `MessageComposer`, `ClarificationList`, `CreateClarificationForm`, `AnswerForm`, `AuditEvidenceSection`, `TestRoleBanner`, `StatusBadge`, `AsyncView`, `EmptyState`, `ErrorState`. |
| New components likely required | Extracted workroom panels: `WorkroomMessages`, `ClarificationQueue`, `ClarificationComposer`, `TaskSafetyPanel`, `TaskTechnicalDetails`, reusable mutation form state helper. |
| Existing routes | `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/tasks/:taskId/workroom`, `/clarifications` placeholder, `/clarification-reminders` placeholder. |
| New routes requiring authorization | A real top-level clarification inbox route, if Product Owner wants cross-task decisions outside Workroom; reminder/expiry real route for Step 66C.4. |
| API dependencies | `/tasks`, `/tasks/{id}`, `/tasks/{id}/submit`, `/tasks/{id}/workroom`, `/tasks/{id}/workroom/messages`, `/tasks/{id}/clarifications`, `/tasks/{id}/clarifications/{id}/answer`, `/tasks/{id}/audit-evidence`. |
| Missing API contracts | Step 66C.4 reminder/expiry lifecycle; cross-task clarification queue contract; task transition contract after clarification answer; production-safe resume policy. |
| State and error handling | Current refresh-key pattern works for M1 MVP; needs extracted local mutation state and stable error copy before larger workroom expansion. |
| RBAC visibility requirements | Server-side RBAC remains authority. UI must show readable 403/restricted states, never client-filter messages, and never expose raw hidden audit bodies. |
| Accessibility requirements | Labels for textareas/inputs, focus after mutation/error, keyboard-operable forms, clear button disabled states, status text not color-only. |
| Test strategy | Extend `WorkroomUI` and `WorkroomAuditVisibility` tests; add cross-task clarification inbox tests only after route/API authorization. Keep no `dangerouslySetInnerHTML` and plain-text tests. |
| Preview/PO validation strategy | Use real test-runtime task records: create task, open Workroom, post message, create clarification, answer, verify audit evidence and no dispatch/resume. |
| Risk of frontend getting ahead of backend | Medium. Existing Workroom is real, but reminders, cross-task queues, and workflow resume semantics are not frontend-decidable. |

### M1 reuse confirmation

Workroom and Clarification can reuse the current `TaskWorkroom` subcomponents and `workroomClient`.
The safest next step is extraction and polish around the existing behavior, not a rewrite. The
component boundaries already encode the correct safety model: plain-text messages, separated normal
messages versus clarifications, safe audit metadata, 403 restricted state, and no dispatch/resume.

## M2 - Delivery and Acceptance Loop

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | `DeliveryPackage`, `OperatorReviewPanel`, `ConfirmDialog`, `SessionBanner`, `OperatorActionHistory`, `PlaceholderPanel`, `StatusBadge`, `KeyValueTable`, `EvidenceTable`. |
| New components likely required | `DeliveryInbox`, `DeliveryDetail`, `AcceptanceDecisionPanel`, `DeliveryEvidenceSummary`, `PackageReadinessChecklist`, `AcceptanceTimeline`, `RequestChangesComposer`. |
| Existing routes | `/delivery-package`, `/delivery-inbox` placeholder, `/delivery-detail` placeholder, `/operator`, `/delivery`. |
| New routes requiring authorization | Parameterized delivery detail route, for example `/delivery/:deliveryId` or `/delivery-packages/:packageId`, if Step 66D chooses that shape. |
| API dependencies | Existing latest delivery state and operator review endpoints; future Step 66D delivery inbox/detail/readiness/acceptance contracts. |
| Missing API contracts | Delivery inbox list shape, delivery detail shape, package ID source, acceptance decision states, request-changes payload, evidence package fields, reviewer RBAC, idempotency/audit response, post-decision refresh contract. |
| State and error handling | Must use explicit mutation state with confirmation/idempotency and post-action refresh. `AsyncView` alone is insufficient. |
| RBAC visibility requirements | Server controls who can accept/reject/request changes; UI can disable or hide by returned capabilities but must not invent authority. |
| Accessibility requirements | Decision controls need clear labels, confirmation dialog focus management, reason field validation, status updates announced. |
| Test strategy | Contract fixtures for inbox/detail/decision states; mutation tests for CSRF/idempotency; no fake controls; restricted role tests; no raw audit/body exposure. |
| Preview/PO validation strategy | Test-runtime delivery package with known IDs; validate inbox, detail, request changes, acceptance path, audit evidence, and non-production safety. |
| Risk of frontend getting ahead of backend | High. Delivery semantics are product-critical and must wait for Step 66D contract freeze. |

### M2 backend contracts that must freeze first

Step 66D must freeze list/detail schemas, accepted/rejected/request-changes state machine, reviewer
capability flags, audit evidence fields, package identity and routing, optimistic refresh behavior,
and explicit safety flags (`production_executed`, external-write flags, approval requirements).
Frontend should not merge Delivery Inbox or Delivery Detail real UI before those contracts exist.

## M3 - AI Team Orchestration and Multi-role Control

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | `ExecutiveOverview` AI team activity strip, `AgentExecutions`, `TaskGraph`, `WorkspaceExecution`, `TestRoleBanner`, `SessionBanner`, `EvidenceTable`. |
| New components likely required | `AgentActivityTimeline`, `AgentRolePanel`, `AssignmentMatrix`, `ExecutionDetailDrawer`, `RoleScopedActivityFilter`, `OrchestrationEvidencePanel`. |
| Existing routes | `/agent-executions`, `/task-graph`, `/workspace`, `/tasks/:taskId/workroom`, `/operator`. |
| New routes requiring authorization | Agent execution detail, team orchestration board, role-control workspace if product wants first-class pages. |
| API dependencies | `/operations/agent-executions`, `/operations/workflows`, task/workroom endpoints, operator action catalog/history. |
| Missing API contracts | Agent identity taxonomy, execution status enum, task-to-agent assignment state, role capabilities, discussion/thread relationship between agents, safe controls for pause/retry/reassign if ever authorized. |
| State and error handling | Existing Overview uses snapshots; M3 needs normalized execution/task state and consistent per-row error/retry. |
| RBAC visibility requirements | Multi-role visibility must be server-filtered; UI must not infer hidden agent messages or show controls based only on client role. |
| Accessibility requirements | Timelines need semantic ordering, status text, keyboard detail panels, no color-only agent state. |
| Test strategy | Fixture tests for observed execution statuses only; fallback for unknown statuses; RBAC restricted views; no fake pause/resume controls. |
| Preview/PO validation strategy | Use real execution data from test runtime; validate "No active agent runs" when no data, and never fabricated activity. |
| Risk of frontend getting ahead of backend | High for controls, medium for read-only activity. Read-only execution data can be reused; orchestration control cannot be assumed. |

### M3 agent activity boundary

Existing execution data can support read-only recent activity and status display. It cannot safely
support assumptions about live agent availability, agent-to-agent discussion state, pause/resume,
reassign, retry, queue ownership, or production readiness unless backend contracts explicitly expose
those concepts.

## M4 - Notifications, Action Center and Channels

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | `PlaceholderPanel`, `ExecutiveOverview` attention tiles, `TaskList` status deep links, `OperatorActionHistory`, `DisabledFutureActions`, `EmptyState`, `ErrorState`. |
| New components likely required | `ActionCenter`, `ActionInbox`, `NotificationFeed`, `ChannelPreferences`, `ActionItemCard`, `Snooze/Resolve` controls if authorized, shared query/cache hook. |
| Existing routes | `/notifications` placeholder, `/approvals` placeholder, `/dlq-retry` placeholder, Overview future capability placeholder. |
| New routes requiring authorization | `/action-center`, notification detail, channel settings detail, action item detail, if Product Owner chooses a first-class center. |
| API dependencies | None adequate today for real action center. Could aggregate existing task clarification/blocked/delivery/approval data after contracts. |
| Missing API contracts | Unified action item schema, source type enum, priority/severity, assignment/owner, read/unread, channel delivery status, preferences, acknowledgement/resolve/snooze mutation semantics, audit history. |
| State and error handling | Yes, M4 likely needs a new shared state/data-fetching pattern. One-off `AsyncView` loaders are not enough for multi-source, read/unread, optimistic updates, and cross-route counts. |
| RBAC visibility requirements | Server must filter action items and channel settings; frontend can render capability flags but cannot enforce access. |
| Accessibility requirements | Inbox list semantics, unread indicators with text, keyboard bulk actions, live region for new/changed notifications if polling is added. |
| Test strategy | Contract fixture tests, aggregation tests, role filtering tests, optimistic mutation rollback tests, no external send without explicit authorization. |
| Preview/PO validation strategy | Begin with read-only action inbox preview, then separately validate acknowledged/resolved actions after backend audit contract. |
| Risk of frontend getting ahead of backend | Very high. Notifications/channels are mostly placeholder and must not be faked. |

### M4 shared state answer

Action Center should introduce a shared query/cache layer or a small domain hook pattern before
feature work. It needs cross-page counts, refresh, restricted states, mutation feedback, and
eventual channel status. Reusing `AsyncView` directly would multiply inconsistent loading and error
states.

## M5 - Controlled End-to-End Pilot

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | Task creation/list/detail/workroom, Overview attention tiles, DeliveryPackage, OperatorConsole, AgentExecutions, SafetyCenter, AuditEvidence. |
| New components likely required | `PilotRunChecklist`, `PilotScenarioStatus`, `EndToEndTimeline`, `ValidationChecklist`, `PilotEvidencePackage`. |
| Existing routes | Existing task, workroom, delivery package, operator, evidence, safety, agent execution routes can form a pilot path. |
| New routes requiring authorization | Dedicated `/pilot` or `/pilot/:id` route if Product Owner wants a guided pilot. |
| API dependencies | M1 task/workroom APIs, M2 delivery APIs, M3 execution evidence, M4 action center if included, safety/audit endpoints. |
| Missing API contracts | Pilot scenario definition, run ID, expected checkpoints, evidence bundle, pass/fail criteria, rollback/stop states. |
| State and error handling | Needs orchestration of multiple domain states and a clear "what happened next" timeline. |
| RBAC visibility requirements | Pilot roles must be explicit: requester, reviewer/approver, operator, security/compliance, admin. |
| Accessibility requirements | Guided checklist must be keyboard navigable and announce completion/failure states. |
| Test strategy | End-to-end UI test plan with mocked contracts first, then test-runtime validation; no production/external actions. |
| Preview/PO validation strategy | Product Owner validates a scripted non-production scenario from task intake through clarification, delivery review, audit, and safety evidence. |
| Risk of frontend getting ahead of backend | High if M2-M4 not contracted first; moderate after contracts freeze. |

## M6 - Production Readiness and Platform Hardening

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | Platform Ops pages, SafetyCenter, CalmSafetyPosture, EvidenceTable, KeyValueTable, OperatorActionHistory, read-only guards. |
| New components likely required | `ReadinessGateSummary`, `EvidenceChecklist`, `SecurityFindingList`, `RuntimeHealthPanel`, `AccessReviewPanel`, `AuditExportPanel` if contracts exist. |
| Existing routes | `/production-readiness`, `/controlled-rollout-review`, `/release-governance`, `/backup-dr`, `/runtime`, `/identity`, `/secrets`, `/security`, `/metrics`, `/safety`. |
| New routes requiring authorization | Production operations drill-downs, audit exports, access review detail pages. |
| API dependencies | Existing read-only operations endpoints; operator actions only where explicitly approved. |
| Missing API contracts | Production readiness decision package, audit export/download, access review data, finding severity model, health SLA, rollout authorization model. |
| State and error handling | Current pages are read-only and loose-typed; hardening needs typed contracts, consistent error severity, and stale-data indicators. |
| RBAC visibility requirements | Security/compliance and platform admin views must be server-authoritative; no client-only gates. |
| Accessibility requirements | Tables need captions, sortable/filterable controls with labels, non-color status, keyboard-friendly details. |
| Test strategy | Read-only guard, no secret leakage, role-restricted evidence, typed fixture tests, build/typecheck, stale data and safety posture tests. |
| Preview/PO validation strategy | Validate with security/compliance and platform-admin personas using non-production evidence. |
| Risk of frontend getting ahead of backend | Medium. Many read APIs exist, but production hardening requires precise evidence contracts. |

## M7 - Production Rollout and Adoption

| Required area | Frontend assessment |
| --- | --- |
| Existing reusable components | Layout/nav, Overview, Safety posture, role banners/session controls, read-only Platform Ops pages. |
| New components likely required | `OnboardingGuide`, `RoleHome`, `AdoptionMetrics`, `ReleaseNotesPanel`, `SupportEscalationPanel`, `OperatorRunbookPanel`. |
| Existing routes | Could reuse Overview, Settings placeholders, Platform Ops, and Operator Center. |
| New routes requiring authorization | Role-specific landing pages, onboarding, help/runbook, adoption analytics, support center. |
| API dependencies | Adoption/usage analytics, role settings, support/runbook content, production status feeds if authorized. |
| Missing API contracts | Production auth/session model, durable user preferences, telemetry/adoption metrics, support escalation workflow, channel integrations. |
| State and error handling | Needs persistent user settings and production-grade auth/session handling, not test-role local storage. |
| RBAC visibility requirements | Production roles must use real auth/session, not `TestRoleBanner`; settings pages need server-side policy. |
| Accessibility requirements | Onboarding and support flows must be usable by keyboard/screen reader and avoid modal traps. |
| Test strategy | Production role smoke tests, accessibility checks, telemetry opt-in/visibility tests, no secret/token storage tests. |
| Preview/PO validation strategy | Pilot with target operators and administrators after production readiness gates pass. |
| Risk of frontend getting ahead of backend | High until production auth, settings, telemetry, and rollout contracts are defined. |
