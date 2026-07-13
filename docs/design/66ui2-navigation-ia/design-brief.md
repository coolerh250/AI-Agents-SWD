# Design Brief — DESIGN-66UI.2 Navigation / Information Architecture

> Owner: Claude Design. This is the fuller implementation-stage design brief that
> `docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md` §4 names as the required
> next step after the 66UI.1 review. **Design specification only — no runtime code, no Codex
> implementation authorized, no backend/API change requested.**

## Stage

`66ui2-navigation-ia` (DESIGN-66UI.2)

## Design goal

Replace the current flat, ungrouped Admin Console navigation with a grouped, hierarchical
Information Architecture that (a) raises Task/Workroom to a first-class position, (b) separates the
AI Agents Team Work product surface from the pre-existing Platform Operations/DevOps governance
surface, and (c) gives every not-yet-built area an honest, non-misleading placeholder — all without
changing a single route target, page behavior, or backend contract in this round.

Concretely, the current navigation (`apps/admin-console/src/components/Nav.tsx`) is **28 flat
`NavLink` items** at one level, where `Task Workroom`'s entry point sits at the same visual weight
as `Sandbox GitHub Draft PR`, `Regression`, and `Controlled Rollout Review`. This brief reorganizes
those 28 items — plus the near-term planned items — into **7 top-level nav groups**.

## Hybrid baseline

This brief implements the Product Owner's Hybrid decision recorded in
`docs/design/66ui-full-redesign-options/product-owner-decision-summary.md`:

```text
Option 1 (Operations Command Center) → IA / Navigation        ← this brief is Option 1's realization
Option 2 (Task Workspace)            → task-level interaction model (later stage, not this brief)
Option 3 (Lifecycle Pipeline)        → deferred, future read-only Task List view toggle
```

DESIGN-66UI.2 delivers **only the Option 1 IA/navigation layer**. The Option 2 Task Workspace
tab-shell and the Option 3 read-only pipeline are explicitly *out of scope for the round-1 nav
shell* and are documented here only as forward-looking placement, per the boundary docs.

## What this stage changes

- Introduces 7 grouped, collapsible top-level nav groups: **Overview, Team Work, Deliveries,
  Operator Center, Governance, Platform Ops, Settings**.
- Moves every existing page under exactly one group (see `page-grouping.md`), collapsing the 28-item
  flat list into a legible hierarchy.
- Raises Task List / Task Detail / Task Workroom / Clarification into a dedicated, prominent
  **Team Work** group instead of being buried among DevOps pages.
- Collects the ~20 pre-existing Platform Operations/DevOps pages under one collapsed **Platform Ops**
  group so they no longer compete with the core product surface (grouping only — no page redesign).
- Defines role-based default entry points (see `role-based-entry-points.md`).
- Defines placeholder presentation rules for 66D / 66C.4 / 66S / future items (see
  `placeholder-rules.md`).
- Removes the developer-only `Diagnostics (Demo Evidence)` item from the first-level nav (direct
  route access only), per its existing "NOT a staging acceptance path" annotation in `Nav.tsx`.

## What this stage does NOT change

- **No route targets change.** Every existing route (`/`, `/tasks`, `/tasks/:id`,
  `/tasks/:id/workroom`, `/operator`, `/incidents`, `/agent-executions`, `/safety`,
  `/audit-evidence`, and all ~20 Platform Ops routes) keeps its current path and its current page
  component. This round regroups the menu; it does not re-route or re-point anything.
- **No page content or behavior changes.** Platform Ops pages are grouped as-is; none is redesigned
  (Product Owner decision, restated in Claude Code's review §3).
- **No Task Workspace tab-merge** of `TaskDetail.tsx` + `TaskWorkroom.tsx` in this round — that is
  Option 2 and needs its own implementation-plan review before Codex starts it (Claude Code review
  §6.3).
- **No Delivery (66D) functionality** beyond a compliant placeholder — no contract exists yet
  (`frontend-implementation-boundary.md` §3).
- **No Reminder/Expiry (66C.4) functionality** beyond a compliant placeholder — no contract exists
  yet.
- **No Lifecycle Pipeline** — not even read-only — in the round-1 nav shell; if ever built it needs a
  status-to-column mapping contract first (`frontend-implementation-boundary.md` §3).
- **No backend, API, RBAC, or safety-behavior change.** All safety values remain server-computed
  and displayed as returned; no client-side inference (`frontend-implementation-boundary.md` §4).
- **No Codex authorization.** This brief makes the design *ready* to authorize; it does not
  authorize implementation. The Product Owner authorizes, per
  `docs/process/frontend-design-engineering-collaboration-protocol.md`.

## Decisions folded in from Claude Code's 66UI.1 review

Claude Code's `claude-code-architecture-review.md` §6 raised three items to resolve here:

1. **Dashboard overlap (`ExecutiveOverview.tsx` vs `OperationalMetrics.tsx`).** Resolved in this
   brief by placing the Overview *dashboard* (Team-Work-oriented summary, reusing/extending
   `ExecutiveOverview.tsx`) under **Overview**, and the platform-level `OperationalMetrics.tsx`
   under **Platform Ops**. The residual question of whether these should eventually merge into one
   dashboard is left as an open question for the Product Owner (see
   `product-owner-review-checklist.md`) — it does not block the nav shell.
2. **`OperatorConsole.tsx` vs new Approval Queue / DLQ-Retry pages.** Resolved here (Claude Code
   asked for this to be settled in this brief, not deferred): **separate pages under one Operator
   Center group**, not same-page tabs. `OperatorConsole.tsx`, `Incidents.tsx`, and
   `AgentExecutions.tsx` stay as their own existing pages; `Approvals` and `DLQ / Retry` are new
   placeholder routes under the same group. A unified aggregated "Action Center" remains a future
   item blocked on both 66D and 66C.4 (`codex-readiness-boundary.md` §3).
3. **Option 2 routing collapse.** Acknowledged as out of scope for this brief and flagged to require
   its own implementation-plan review before Codex begins it.

## Target roles / personas

All six product RBAC roles (`docs/product/operator-rbac-model.md`): Requester, PM / Engineering
Lead, Reviewer / Approver, Platform Admin, Agent Operator, Security / Compliance Reviewer. Per-role
default entry points are defined in `role-based-entry-points.md`.

## Constraints

- Plain-text rendering only for user/agent content (no `dangerouslySetInnerHTML`, no
  markdown-to-HTML, no URL auto-linking) — unchanged.
- Server-side RBAC only; nav visibility is a convenience layer, never the access control itself.
- No nav item, badge, or placeholder may imply that workflow dispatch, workflow resume, or any
  external/production action is enabled.
- Existing endpoints only (`frontend-implementation-boundary.md` §1): `GET /tasks`,
  `GET /tasks/{id}`, `GET /tasks/{id}/workroom`, `GET /tasks/{id}/audit-evidence`,
  `POST /tasks/{id}/workroom/messages`, `POST /tasks/{id}/clarifications`,
  `POST /tasks/{id}/clarifications/{id}/answer`. No new endpoint is requested by this brief.
- No internal IP, SSH alias, private hostname, token, secret, or environment identifier anywhere.

## Companion documents in this stage

- `navigation-map.md` — the proposed left-nav structure, collapse behavior, default landing.
- `page-grouping.md` — every page → group, visibility, status, dependencies.
- `role-based-entry-points.md` — per-role default entry point and primary items.
- `placeholder-rules.md` — how not-yet-available features are shown.
- `migration-from-current-nav.md` — item-by-item migration from today's flat nav.
- `codex-implementation-notes.md` — what Codex may/must-not build (once authorized).
- `product-owner-review-checklist.md` — the Product Owner's acceptance checklist.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
