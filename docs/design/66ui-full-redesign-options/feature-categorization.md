# Feature Categorization — DESIGN-66UI.1

> Owner: Claude Design. Reclassifies current + planned capability against the stage prompt's
> Category A–G, cross-checked against the actual implemented routes in
> `apps/admin-console/src/pages/*` and `apps/admin-console/src/components/Nav.tsx` (27 nav items
> today).

## Category A — Task & Intake

| Item | Status | Current implementation |
| --- | --- | --- |
| Task List | Implemented | `TaskList.tsx` |
| Create Task | Implemented | `TaskNew.tsx` |
| Task Detail | Implemented | `TaskDetail.tsx` |
| Submit Draft | Implemented | action within Task Detail |
| Task Status / Task Type / Priority / Acceptance Criteria | Implemented | fields within Task List / Detail |

## Category B — Workroom & Human-Agent Collaboration

| Item | Status | Current implementation |
| --- | --- | --- |
| Workroom (message thread + composer) | Implemented | `TaskWorkroom.tsx` (494 lines) |
| Send Message | Implemented | Workroom composer |
| Create Clarification | Implemented | Workroom clarification form |
| Answer Clarification | Implemented | Workroom clarification form |
| Clarification Status (open/answered) | Implemented | Clarification card |
| Message Visibility Filtering | Implemented (66C.3) | server-side filtering, visibility note in UI |
| Answered-twice Guard | Implemented (66C.3) | readable `clarification_already_answered` error |
| Reminder / Expiry | Planned (66C.4) | not yet implemented — this is the next stage pending PO authorization |
| Agent Updates / System Events | Partial | message types defined in spec; UI differentiation not fully verified in this pass |

## Category C — Audit / Safety / Governance

| Item | Status | Current implementation |
| --- | --- | --- |
| Audit Evidence (Workroom-scoped) | Implemented (66C.3) | Audit Evidence section, `AuditEvidence.tsx` also exists as a broader page |
| Visibility Filtering | Implemented (66C.3) | see Category B |
| RBAC Restriction / RBAC Error State | Implemented | readable restricted-role message |
| Safety Flags / Safety Panel | Implemented | `SafetyBadge.tsx`, `SafetyCenter.tsx` |
| Role Simulation Banner | Implemented | test-only `X-Task-Actor`/`X-Task-Role` header simulation |
| `production_executed_true_count` | Implemented | shown in Safety Center |
| `dispatch_enabled` / `resume_dispatch_enabled` | Implemented | shown in Workroom + Safety Center |
| Approval Boundaries / Policy Warnings | Partial | Safety Center shows posture; a dedicated Approval Queue does not exist yet (see Category E) |

## Category D — Delivery & Review

| Item | Status | Current implementation |
| --- | --- | --- |
| Delivery Inbox | Planned (66D) | not yet implemented |
| Delivery Detail | Planned (66D) | not yet implemented |
| Delivery Evidence / QA Evidence | Partial | `QaCode.tsx` and `DeliveryPackage.tsx` exist but predate the Step 66 Task→Delivery model; relationship to the new Delivery Inbox is an open question |
| Accept / Reject / Request Changes / Re-run QA | Planned (66D) | not yet implemented |

## Category E — Operator Center

| Item | Status | Current implementation |
| --- | --- | --- |
| Operator Console (general) | Implemented | `OperatorConsole.tsx` — pre-existing, scope vs. new Approval/DLQ pages needs reconciling |
| Approval Queue | Planned (66D) | not yet implemented |
| DLQ / Retry | Planned (66D) | not yet implemented |
| Incidents | Implemented | `Incidents.tsx` |
| Blocked Tasks / Clarification Overdue | Planned (66C.4 dependent) | depends on reminder/expiry scheduler |
| Action Items | Partial | scattered across Operator Console / Incidents, not unified |

## Category F — Platform Settings

| Item | Status | Current implementation |
| --- | --- | --- |
| Roles / Permissions | Planned (66S) | not yet implemented as a settings UI (RBAC model exists in `docs/product/operator-rbac-model.md`, no admin UI) |
| Integrations | Not started | no UI |
| Web Research Sources | Not started | no UI |
| Approval Policy | Not started | no UI (policy concepts exist in `docs/product/operator-action-policy-model.md`) |
| Identity / Session | Implemented (read-only posture) | `IdentityPosture.tsx` — reports posture, does not manage real login; 66S will add real identity |
| Project / Team Scope | Planned (66S) | not yet implemented |

## Category G — Metrics / Dashboard

| Item | Status | Current implementation |
| --- | --- | --- |
| Task throughput | Partial | `ExecutiveOverview.tsx`, `OperationalMetrics.tsx` cover platform-level metrics; task-specific throughput not isolated |
| Clarification wait time | Not started | depends on 66C.4 reminder/expiry data |
| Delivery review status | Planned (66D) | not yet implemented |
| Agent execution health | Implemented | `AgentExecutions.tsx` |
| Audit coverage | Partial | Safety Center shows posture, not a coverage metric |
| Safety posture | Implemented | `SafetyCenter.tsx` |
| Pending operator actions | Partial | scattered, see Category E |

## Category H — Platform Operations & DevOps Governance (pre-existing, not in the stage prompt's taxonomy)

This category is **not** one of the seven the stage prompt asked for — it is added here because
it accounts for roughly half of the current nav (12 of 27 items) and any redesigned IA has to put
it somewhere.

| Item | Status | Current implementation |
| --- | --- | --- |
| Executive Overview | Implemented | `ExecutiveOverview.tsx` (current `/` route) |
| Projects / Project Detail | Implemented | `Projects.tsx`, `ProjectDetail.tsx` |
| Multi-project Delivery | Implemented | delivery work-item model, pre-dates Step 66 Task model |
| Task Graph / Design Review / Workspace Execution / Mini Delivery Pilot | Implemented | `TaskGraph.tsx`, `DesignReview.tsx`, `WorkspaceExecution.tsx`, `MiniDeliveryPilot.tsx` |
| Regression Status | Implemented | `RegressionStatus.tsx` |
| Cost / LLM Governance | Implemented | `CostLlmGovernance.tsx` |
| Runtime Baseline | Implemented | `RuntimeBaseline.tsx` |
| Identity / Secret / Security Posture | Implemented (read-only) | `IdentityPosture.tsx`, `SecretPosture.tsx`, `SecurityPosture.tsx` |
| Release Governance | Implemented (read-only) | `ReleaseGovernance.tsx` |
| Backup / Restore / DR | Implemented (read-only) | `BackupDr.tsx` |
| Production Readiness Gate | Implemented (read-only) | `ProductionReadiness.tsx` |
| Controlled Rollout Review | Implemented (read-only) | `ControlledRolloutReview.tsx` |
| Sandbox GitHub Draft PR | Implemented (sandbox-only) | `SandboxGithub.tsx` |

## Key changes from the current UI

1. **From flat to hierarchical navigation.** 27 flat nav items become ~6–8 top-level groups
   (A through H, with some merged — see each layout option for how grouping differs).
2. **Task/Workroom moves from "one item in a long list" to a primary entry point** in every option
   — it is currently indistinguishable in the nav from `Regression` or `Sandbox GitHub Draft PR`,
   which does not match its actual product importance (Section C of the original handoff:
   "Workroom 是最重要的頁面").
3. **A previously implicit split becomes explicit:** "the new Team Work product" (A–G) vs. "the
   platform's own operations/governance instrumentation" (H). Today both live in one nav with no
   visual distinction.
4. **Delivery has two candidate homes** that must be reconciled: the new Task-linked Delivery
   Inbox/Detail (66D, Category D) and the pre-existing `DeliveryPackage.tsx` /
   `MultiProjectDelivery` delivery model (Category H). This is called out as an open question.

## Areas needing clarification

1. Is Category H in scope for this redesign at all, or does it remain on its current flat/legacy
   nav indefinitely? (See `design-objective.md` "Scope boundary".)
2. Should `DeliveryPackage.tsx` / multi-project delivery be merged into the new Delivery Inbox
   (Category D) when 66D ships, superseded by it, or kept as a separate "release-level delivery"
   concept distinct from "task-level delivery"? This is a product decision, not a layout decision,
   but it affects nav structure.
3. `OperatorConsole.tsx` (Category E, pre-existing) vs. the new Approval Queue / DLQ-Retry pages
   (66D) — same-page tabs, or separate pages under one "Operator Center" group?
4. Category G (Metrics/Dashboard) content overlaps `ExecutiveOverview.tsx` and
   `OperationalMetrics.tsx` (Category H) — is one dashboard or two dashboards the intended end
   state?

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
