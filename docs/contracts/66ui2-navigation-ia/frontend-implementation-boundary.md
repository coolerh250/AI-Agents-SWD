# Frontend Implementation Boundary — DESIGN-66UI.2 Navigation / IA

> **Boundary document only. No runtime code changed. No backend changed. No frontend implementation
> changed. Codex is NOT authorized to implement anything in this document until the Product Owner
> explicitly authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the contract boundary for the round-1 nav
shell defined in `docs/design/66ui2-navigation-ia/design-brief.md`, subordinate to and consistent
with `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md`.

## 1. No new or changed backend contract is required for round-1 nav shell

Every page kept `active` in `docs/design/66ui2-navigation-ia/page-grouping.md` already has a working
route and page component consuming an existing endpoint. The round-1 nav shell is a pure
menu-grouping change: it does not request a new endpoint, a new response field, or a changed
response shape. Existing endpoint set that remains sufficient:

```text
GET  /tasks
GET  /tasks/{id}
GET  /tasks/{id}/workroom
GET  /tasks/{id}/audit-evidence
POST /tasks/{id}/workroom/messages
POST /tasks/{id}/clarifications
POST /tasks/{id}/clarifications/{id}/answer
```

## 2. What may proceed without a new contract (once authorized)

- The 7-group `NavGroup` restructure of `Nav.tsx` (Overview, Team Work, Deliveries, Operator Center,
  Governance, Platform Ops, Settings), regrouping all 28 existing items per
  `docs/design/66ui2-navigation-ia/migration-from-current-nav.md`, with zero route-target changes.
- Default expansion state and role-based default landing route, per
  `docs/design/66ui2-navigation-ia/navigation-map.md` and `role-based-entry-points.md` — both are
  client-side UI conveniences that grant no capability and do not touch RBAC.
- Compliant placeholder routes/panels (Delivery Inbox, Delivery Detail, Approvals, DLQ/Retry,
  Reminder/Expiry, Roles & Permissions, Integrations, Web Research Sources, Approval Policy,
  Identity/Session, in-app Notifications) per
  `docs/design/66ui2-navigation-ia/placeholder-rules.md` — read-only, no actionable control, no
  fabricated data.
- Removing `Diagnostics (Demo Evidence)` from the first-level nav while keeping its route reachable
  by direct URL.
- The persistent top-bar safety posture and test-role-simulation indicator, reusing the existing
  server-computed values — no new computation, no client-side inference.

## 3. What requires a new or updated contract before it may proceed past placeholder

| Frontend piece | Blocked on |
| --- | --- |
| Delivery Inbox / Delivery Detail (real data), Approvals, DLQ/Retry | Claude Code's Step 66D API/data contract |
| Reminder/Expiry / overdue indicators (real data) | Claude Code's Step 66C.4 contract |
| Roles & Permissions, Identity/Session admin UI (real) | Claude Code's Step 66S contract |
| Unified Operator Action Center | Both the 66D and 66C.4 contracts |
| Task Workspace tab-merge (`TaskDetail.tsx` + `TaskWorkroom.tsx`, Option 2) | Its own implementation-plan review, carried over unresolved from the 66UI.1 review §6.3 |
| Lifecycle Pipeline board, even read-only | A `docs/contracts/<stage>/frontend-contract.md` confirming the task-status-to-pipeline-column mapping — same condition carried over from `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md` §3, still unmet |

## 4. RBAC / safety posture unchanged

- Nav visibility remains a convenience layer only; server-side RBAC is the sole access-control
  authority (`docs/design/66ui2-navigation-ia/role-based-entry-points.md`, restated in
  `design-brief.md` §"Constraints").
- `dispatch_enabled`, `resume_dispatch_enabled`, and `production_executed_true_count` remain
  server-computed and displayed exactly as returned; no client-side inference is introduced by the
  nav restructure.
- RBAC denials remain a readable message, never a blank screen or broken section
  (`role-based-entry-points.md` §"Safety visibility is role-independent").

## 5. Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No API contract change requested. No workflow dispatch. No workflow resume. No external
action. No production action. Codex implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
