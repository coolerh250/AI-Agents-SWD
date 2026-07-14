# Codex Implementation Plan Boundary — DESIGN-66UI.2 Navigation / IA

> **Boundary document only. No runtime code changed. No frontend implementation changed. Codex is
> NOT authorized to implement anything in this document until the Product Owner explicitly
> authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the boundary Codex must observe for the
round-1 nav shell defined in `docs/design/66ui2-navigation-ia/`, subordinate to and consistent with
`docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md` and this stage's
`docs/contracts/66ui2-navigation-ia/frontend-implementation-boundary.md`.

## 1. What Codex may later start with (once authorized)

- Navigation grouping / IA shell — the grouped, collapsible `NavGroup` restructure of `Nav.tsx` per
  `docs/design/66ui2-navigation-ia/navigation-map.md`.
- Left navigation grouping — Overview, Team Work, Deliveries, Operator Center, Governance,
  Platform Ops, Settings, with the documented default-expansion state (Team Work expanded; Platform
  Ops collapsed; active-route group auto-expands).
- Route grouping using existing routes — regrouping all 28 current items per
  `docs/design/66ui2-navigation-ia/migration-from-current-nav.md`, with **no route target or page
  component change**.
- Page section organization — e.g. wrapping existing pages into their new group headers; no existing
  page's internal content changes.
- Placeholder pages/panels for unfinished features, following
  `docs/design/66ui2-navigation-ia/placeholder-rules.md` exactly: state label, "Not yet available,"
  the specific required stage, "No workflow action available," no actionable control, no fabricated
  data.
- Role-based default landing route, per `docs/design/66ui2-navigation-ia/role-based-entry-points.md`,
  including the documented interim fallbacks (e.g. Reviewer/Approver → Overview until 66D) — client-
  side only, grants no capability.
- Top safety status bar, reusing the existing safety endpoint/data and `SafetyBadge` component — no
  new computation, values displayed exactly as server-returned.

## 2. What Codex must NOT implement

```text
- Backend changes.
- API contract changes.
- Workflow state mutation.
- Workflow dispatch.
- Workflow resume.
- Production action.
- External integration behavior (all connectors stay not-connected/disabled).
- Delivery (66D) real UI — Delivery Inbox/Detail beyond a compliant placeholder.
- Reminder / Expiry (66C.4) real UI beyond a compliant placeholder.
- Lifecycle Pipeline board (not part of round 1; needs its own future contract).
- Drag-and-drop behavior of any kind.
- Client-side-only RBAC as access control (server remains the sole authority).
```

## 3. Dependency map

| Frontend piece | Blocked on |
| --- | --- |
| Nav shell / IA regrouping (round 1) | Nothing — ready once Product Owner authorizes |
| Placeholder routes/panels (round 1) | Nothing — ready once authorized |
| Role-based default landing (round 1) | Nothing — ready once authorized |
| Delivery Inbox/Detail, Approvals, DLQ/Retry (real) | Claude Code's 66D contract |
| Reminder/overdue/expiry (real) | Claude Code's 66C.4 contract |
| Roles & Permissions, Identity/Session (real) | Claude Code's 66S contract |
| Unified Operator Action Center | Both 66D and 66C.4 contracts |
| Task Workspace tab shell (Option 2) | Its own implementation-plan review (carried over from 66UI.1 review §6.3, still open) |
| Lifecycle Pipeline read-only view | A status-to-column mapping frontend-contract from Claude Code (still unmet) |

## 4. Authorization gate

**Codex must not implement until the Product Owner explicitly authorizes implementation after this
review.** This document, the architecture review, and the implementation-boundary contract together
establish that the design is *safe* to authorize — they do not themselves constitute that
authorization.

## 5. Recommended first implementation candidate

If this review passes, the recommended first safe frontend task is:

```text
Step 66UI.2-FE.1 — Navigation Grouping / IA Shell
```

Scope limited to: nav grouping, existing route reorganization, collapsed Platform Ops group, safe
placeholder pages. No business logic change. No backend change. No workflow behavior change. This
matches the single self-contained PR `docs/design/66ui2-navigation-ia/codex-implementation-notes.md`
§7 describes: `NavGroup` regrouping + `PlaceholderPanel` + placeholder routes + role-based default
landing + removal of Demo Evidence from first-level nav — no existing page modified, fully
revertible.

## 6. Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No workflow dispatch. No workflow resume. No external action. No production action. Codex
implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
