# Layout Option 2 — Task Workspace

> Owner: Claude Design. One of three layout proposals for DESIGN-66UI.1. Not selected by default —
> see `recommendation.md` and `product-owner-discussion-guide.md`.

## 1. Layout name

Task Workspace

## 2. Design concept

The single task — and its Workroom — is the primary unit of the entire application, not a
drill-down destination. Opening a task opens a **workspace**, not a detail page: Workroom,
Clarifications, Delivery, and Audit/Safety for that task are all panels within the same workspace
view, always alongside the conversation. This matches the product's own framing (Section C of the
original handoff: "Workroom 是任務協作室，不是一般聊天室") by making the task workspace, not a
dashboard, the thing most screen-time is spent in.

## 3. Best-fit user types

Requester, PM/Engineering Lead, and Engineer roles doing deep single-task collaboration with the
Agent Team. Weaker fit for Platform Admin and Agent Operator, whose work is inherently cross-task.

## 4. Main navigation structure

```text
Left sidebar (minimal, top-level only):

▸ My Tasks / Team Tasks   (role-scoped default list)
▸ Operator Center         (Approvals, DLQ/Retry, Incidents — cross-task, still needed even here)
▸ Safety Center
▸ Audit Evidence (cross-task)
▸ Platform Ops (Category H, collapsed)
▸ Settings

Selecting a task does NOT navigate to a new page in the traditional sense — it opens the Task
Workspace, which takes over the main content area:

┌─ Task Workspace: <task title> ──────────────────────────────┐
│ [Overview tab] [Workroom tab*] [Clarifications tab] [Delivery tab] │
│  *default active tab on open                                 │
└────────────────────────────────────────────────────────────┘
```

## 5. Dashboard behavior

There is no cross-task "dashboard" as the landing page for task-centric roles — `My Tasks` /
`Team Tasks` (a list, not a card dashboard) is the landing page. A lightweight summary strip sits
above the list (open count, clarifications waiting, deliveries pending) but it is a header, not a
separate Overview page. Platform Admin/Agent Operator still get a real dashboard, but it lives
under "Operator Center," not at the app root.

## 6. Task / Workroom placement

Workroom is a **tab within the Task Workspace**, always one click from Task Overview, Clarifications,
and Delivery — all four are panels of the same workspace rather than four separate pages. This is
the layout's central bet: collaboration content and task metadata are co-located, not spread across
navigation.

## 7. Audit / Safety placement

Two placements, deliberately: (a) a compact Safety/Audit panel inside the Task Workspace itself
(task-scoped, always visible while working the task), and (b) a separate cross-task `Safety Center`
/ `Audit Evidence` in the left nav for Security/Compliance Reviewer and Platform Admin, who need
the aggregate view.

## 8. Delivery / Review placement

A tab inside the Task Workspace (`Delivery` tab) for the task that produced it — this directly
ties delivery review to the conversation that produced it, addressing the PM/Reviewer need to see
"what was discussed" next to "what was delivered." A secondary cross-task Delivery Inbox still
exists (reachable from `Team Tasks` header strip: "Deliveries Pending Review: 2") for reviewers who
want to triage across tasks without opening each workspace.

## 9. Operator Center placement

Left nav, top-level, alongside Safety Center — because Agent Operator's work is inherently
cross-task, this role does not benefit from the task-centric workspace model and needs its own
first-class area regardless of this layout's core bet.

## 10. Pros

- Best fit for the product's own stated differentiator (Workroom as collaboration room, not a
  buried detail tab) — directly serves Requester and PM personas doing real task work.
- Reduces navigation depth for the single most-used flow (open task → work in Workroom → check
  Clarifications → review Delivery) to zero extra page loads once the workspace is open.
- Naturally reinforces the "Send Message vs. Clarification" distinction the product requires,
  because both live as adjacent, clearly-separated panels in the same workspace rather than being
  buried in one long feed.

## 11. Cons

- Weaker for Platform Admin/Agent Operator, who need cross-task visibility more than deep
  single-task focus — this layout partially "hides" the operational view behind a secondary nav
  item.
- A tabbed workspace is a bigger frontend rework than Option 1's nav grouping — Task Detail and
  Workroom are two separate pages/routes today (`TaskDetail.tsx`, `TaskWorkroom.tsx`); merging them
  into one tabbed workspace is a real component restructure, not just a nav change.
- Category H (Platform Ops) has no natural home in a task-centric model — it becomes an isolated,
  slightly awkward nav item regardless of placement.

## 12. Recommended use case

Choose this if the Product Owner's near-term priority is **collaboration depth and clarity** for
Requester/PM/Engineer roles working a task end-to-end, and cross-task operator/admin views can
remain secondary for now.

## 13. Risk or tradeoff

Investing frontend effort in a tabbed workspace before Delivery (66D) exists means the "Delivery"
tab ships empty/placeholder first — there is a real sequencing risk if this option is chosen before
66D's contract is ready.

## 14. ASCII wireframe sketch

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [Role: Requester ▾]  Safety: dispatch=OFF resume=OFF prod_exec=0          │
├───────────────┬────────────────────────────────────────────────────────────┤
│ My Tasks       │  TASK WORKSPACE — "Build SaaS User Management Module"     │
│ Operator Ctr   │  [Overview] [Workroom*] [Clarifications] [Delivery]       │
│ Safety Center  │ ┌────────────────────────────┬─────────────────────────┐ │
│ Audit Evidence │ │ Message Timeline            │ Task safety panel:       │ │
│ Platform Ops   │ │ pm.jerry: "Keep v1 API-     │  dispatch_enabled=false  │ │
│ (collapsed)    │  first..."                    │  resume_dispatch=false   │ │
│ Settings       │ │ [clarification_question]    │  production_effect=false │ │
│                │ │ Agent: "Should v1 support..."│                          │ │
│                │ │                              │ Open Clarifications: 1  │ │
│                │ │ [Send Message.......  Send]  │ [Answer] [Create]        │ │
│                │ └────────────────────────────┴─────────────────────────┘ │
└───────────────┴────────────────────────────────────────────────────────────┘
```

## Safety UX (required for every option)

| State | How it is shown in this layout |
| --- | --- |
| `dispatch_enabled=false` | Task Workspace safety panel (always visible while a task is open) + top bar |
| `resume_dispatch_enabled=false` | Same panel; explicit note on the Clarifications tab's Answer form |
| `production_executed_true_count=0` | Cross-task Safety Center (left nav) — since there's no root dashboard in this layout, this is the canonical place, not duplicated on every task |
| `production_effect` warning | Task Workspace Overview tab, shown for the life of the task if `production_effect=true` |
| External action disabled | Settings/Integrations; also a compact note in the Delivery tab if a delivery would otherwise trigger an external action |
| Approval required | Badge on the workspace tab bar ("Delivery ⚠ approval required") + the cross-task Operator Center |
| RBAC denied | Same reusable readable-message component as Option 1 |
| Audit restricted | Task-scoped Audit panel (within workspace) shows the restricted message inline; cross-task Audit Evidence page shows it per-row |

## Current UI migration thinking

- **Reuse as-is:** all shared components (`SafetyBadge`, `StatusBadge`, `EmptyState`, `ErrorState`,
  `LoadingState`, `EvidenceTable`, `JsonPanel`, `KeyValueTable`).
- **Reuse with rework:** `TaskDetail.tsx` and `TaskWorkroom.tsx` are restructured into a single
  `TaskWorkspace` container with tab state, reusing both existing components' internals as tab
  content rather than separate routes.
- **Needs reset:** the routing model for tasks changes (`/tasks/{id}` and `/tasks/{id}/workroom`
  collapse toward one workspace route with a tab query param or nested route) — this is the
  largest structural change of the three options.
- **New components needed:** `TaskWorkspaceTabs`, a task-scoped compact safety panel (distinct from
  the existing full `SafetyCenter.tsx` page).
- **Codex phasing:** (1) build the `TaskWorkspace` shell wrapping existing Task Detail + Workroom
  content as two tabs (no behavior change, pure restructure — can start now), (2) add
  Clarifications as its own tab once visually separated from the general message thread, (3) add
  Delivery tab only after 66D contract exists — this dependency should be sequenced explicitly if
  this option is chosen.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
