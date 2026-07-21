# Component Reuse Plan

Step: 66ALIGN.1-CODEX

## Reuse Principles

- Reuse existing safety-tested components before creating new ones.
- Extract from existing TaskWorkroom only when a new slice touches that behavior.
- Keep placeholders honest: no fake queues, counts, dispatch, resume, external send, or production action.
- Keep product polish coupled to core work where it reduces confusion; pause cosmetic-only work.

## Component Reuse By Milestone

| Milestone | Reuse first | Extract or create later |
| --- | --- | --- |
| M0 | `NAV_GROUPS`, `NAV_ITEMS`, route tests, API guards. | Route/API inventory generator if authorized. |
| M1 | `TaskList`, `TaskNew`, `TaskDetail`, `TaskWorkroom`, `TestRoleBanner`, `StatusBadge`, `AsyncView`, `EmptyState`, `ErrorState`. | `TaskSafetyPanel`, `TechnicalDetails`, `WorkroomMessages`, `ClarificationQueue`, `ClarificationComposer`, shared mutation state helper. |
| M2 | `DeliveryPackage`, `OperatorReviewPanel`, `ConfirmDialog`, `SessionBanner`, `OperatorActionHistory`, `StatusBadge`, `KeyValueTable`, `EvidenceTable`. | `DeliveryInbox`, `DeliveryDetail`, `AcceptanceDecisionPanel`, `DeliveryEvidenceSummary`, `RequestChangesComposer`, `AcceptanceTimeline`. |
| M3 | `AgentExecutions`, `TaskGraph`, `WorkspaceExecution`, `ExecutiveOverview` activity strip, `EvidenceTable`. | `AgentActivityTimeline`, `ExecutionDetailDrawer`, `AgentIdentityChip`, `RoleScopedActivityFilter`, `OrchestrationEvidencePanel`. |
| M4 | `PlaceholderPanel`, Overview attention tile pattern, `OperatorActionHistory`, `DisabledFutureActions`, `EmptyState`. | `ActionCenter`, `ActionItemCard`, `NotificationFeed`, `ChannelPreferences`, shared query/cache hooks. |
| M5 | All M1-M4 components after contract freeze. | `PilotRunChecklist`, `PilotTimeline`, `PilotEvidencePackage`, `ValidationChecklist`. |
| M6 | `CalmSafetyPosture`, `SafetyCenter`, Platform Ops pages, `EvidenceTable`, `KeyValueTable`. | `ReadinessGateSummary`, `EvidenceChecklist`, `SecurityFindingList`, `AuditExportPanel`, `AccessReviewPanel`. |
| M7 | Shell/nav/Overview/session patterns. | `RoleHome`, `OnboardingGuide`, `AdoptionMetrics`, `SupportEscalationPanel`, `OperatorRunbookPanel`. |

## M1 Workroom/Clarification Reuse

The current Workroom already has the important safety-bearing pieces:

- Plain-text message rendering.
- Separate normal message and clarification actions.
- Client-side length validation.
- Readable RBAC and already-answered errors.
- Server-filtered message visibility note.
- Safe audit metadata rendering.
- Dispatch/resume flags read from API and shown as false.

Recommended M1 approach:

1. Extract presentational subcomponents only when modifying that area.
2. Keep `workroomClient` named methods. Do not introduce a generic mutation helper.
3. Add a small mutation-state helper after two or more forms need the same pending/error handling.
4. Keep raw technical metadata available but move it behind details only when the slice is authorized.

## M2 Delivery Reuse

`DeliveryPackage` is an evidence/package record, not the future Delivery Inbox. `OperatorReviewPanel`
has useful controlled-action mechanics, but M2 should not blindly reuse its package-ID manual input.
Step 66D needs a real delivery list/detail contract first.

Reusable pieces:

- `ConfirmDialog` for reason-required decisions.
- `SessionBanner` for controlled operator auth pattern.
- `OperatorActionHistory` for audit trail shape.
- `StatusBadge`, `DataCard`, `EvidenceTable` for read-only detail.

Not reusable as-is:

- Manual package ID entry as primary delivery UX.
- `KeyValueTable` as user-facing acceptance detail.
- Loose `Record<string, unknown>` delivery state as decision contract.

## M3 Agent Activity Reuse

The existing Overview and `AgentExecutions` page can display recent agent executions. They should
not be stretched into orchestration controls until backend exposes:

- canonical agent identity;
- execution detail;
- task assignment relationship;
- allowed controls and capability flags;
- audit result of each control.

## M4 Shared State Need

Action Center should not be implemented as a collection of independent `AsyncView` islands. It will
need a shared pattern for:

- multiple sources;
- periodic refresh or manual refresh;
- read/unread or acknowledged state;
- optimistic mutation and rollback;
- restricted action visibility;
- route-level badge counts.

This can be a lightweight project-local hook pattern first; a larger data-fetching library should be
considered only if backend contracts require caching, invalidation, and polling across many pages.

## FE.1D-S2 Timing

Can merge naturally with core work:

- TaskList status labels and relative time when M1 TaskList is touched.
- TaskDetail technical details disclosure when M1/M2 task/delivery context needs it.
- Placeholder wording when M4 notification/action placeholders are replaced.
- Safety wording cosmetic consistency when touching safety posture for M6.

Pause as cosmetic-only:

- Broad audit/evidence raw column rename without explicit maps.
- Platform Ops visual sub-headers.
- TaskWorkroom `body_hash` relabel if no surrounding Workroom slice exists.
- Any microcopy that would touch a decision-critical delivery field before Step 66D.
