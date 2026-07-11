# Layout Option 1 — Operations Command Center

> Owner: Claude Design. One of three layout proposals for DESIGN-66UI.1. Not selected by default —
> see `recommendation.md` and `product-owner-discussion-guide.md`.

## 1. Layout name

Operations Command Center

## 2. Design concept

The Admin Console's home is a **cross-task, cross-project operational dashboard**. Individual
tasks and their Workrooms are one drill-down destination among several (alongside DLQ, Approvals,
Incidents, Safety posture). This mirrors how a NOC/SRE console is organized: the top-level view is
"what needs attention across the whole fleet," not "one item in depth."

## 3. Best-fit user types

Platform Admin, Agent Operator, PM/Engineering Lead (in team-oversight mode, not single-task mode).
Weaker fit for Requester, whose entire concern is usually one task.

## 4. Main navigation structure

```text
Left sidebar (persistent, grouped, collapsible groups):

▸ Overview            (dashboard — default landing page)
▸ Team Work
    Tasks
    Workroom (opens from a task, not a standalone nav item)
    Clarifications (queue view across all tasks)
    Deliveries          [66D]
▸ Operator Center
    Action Center (unified: DLQ + overdue + incidents + approvals) [66D/66C.4]
    Approvals            [66D]
    DLQ / Retry          [66D]
    Incidents
    Agent Executions
▸ Governance
    Safety Center
    Audit Evidence
▸ Platform Ops (Category H, collapsed by default)
    Runtime / Identity / Secret / Security / Release Governance / Backup-DR /
    Production Readiness / Controlled Rollout / Sandbox GitHub / Cost-LLM / Regression
▸ Settings
    Roles & Permissions [66S]
    Integrations
    Web Research Sources
    Approval Policy
```

Top bar: persistent Safety Banner (see Section 9) + role-simulation indicator, always visible
regardless of which left-nav group is open.

## 5. Dashboard behavior

The `Overview` landing page is card-based, aggregating across all tasks/projects:
`Open Tasks`, `Clarifications Waiting for Human`, `Deliveries Pending Review`,
`Approvals Required`, `Agent Failures`, `production_executed_true_count`,
`External Actions Status`. Every card is a queue — clicking it goes to a filtered list, not to a
single item. This is a superset/refinement of the existing `ExecutiveOverview.tsx` +
`OperationalMetrics.tsx` pattern already in the app.

## 6. Task / Workroom placement

Task List and Workroom are one drill-down path under "Team Work," reached via `Tasks → Task Detail
→ Workroom`. Workroom is not a top-level nav item — it is only reachable in the context of a
specific task. This is a deliberate tradeoff (see Cons).

## 7. Audit / Safety placement

Own top-level group ("Governance"), separate from both Team Work and Platform Ops. Audit Evidence
here is the cross-task audit view; a task-scoped Audit Evidence section still exists inside
Workroom (Category C item), this group is the aggregate/searchable one.

## 8. Delivery / Review placement

Under "Team Work" as `Deliveries`, a cross-task inbox (66D). The pre-existing
`DeliveryPackage.tsx` / multi-project delivery concept moves under "Platform Ops" unless the
Product Owner decides to merge them (open question, see `feature-categorization.md`).

## 9. Operator Center placement

Its own top-level group, second from the top — reflecting that Agent Operator and
Reviewer/Approver both need a fast path to it. This is the group most likely to be the actual
default landing page for Agent Operator and Reviewer/Approver personas (role-based default route,
not a layout change per se).

## 10. Pros

- Best fit for the roles managing volume across many tasks at once (Operator, Admin).
- Aggregated queues (Action Center) directly address the cross-role finding in
  `user-role-journey-map.md`.
- Clear separation of "Team Work" vs. "Platform Ops," resolving the Category H ambiguity by simply
  collapsing it rather than deleting or merging it.
- Closest to the existing app's actual structure (dashboard + flat groups), so migration cost is
  lower than Option 3.

## 11. Cons

- Task/Workroom is one level deeper than in Option 2 — a Requester with exactly one task to check
  takes more clicks than necessary for their narrow use case.
- Risks becoming "yet another ops dashboard" if card design does not stay disciplined — the stage
  prompt explicitly warns against "consumer chatbot" and "plain issue tracker," but the opposite
  failure mode (overwhelming NOC-style dashboard) is also a real risk here.
- "Governance" vs. "Platform Ops" split is a judgment call that may not hold up once Security/
  Compliance Reviewer's actual usage pattern is observed.

## 12. Recommended use case

Choose this if the Product Owner's near-term priority is **operational scale** (many concurrent
tasks, Agent Operator workload, incident response) over **single-task collaboration depth**.

## 13. Risk or tradeoff

Optimizing for the operator/admin's cross-task view can make the single-task collaboration
experience (Requester, PM on one task) feel like a detour through a dashboard they don't need.

## 14. ASCII wireframe sketch

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [Role: PM ▾]  Safety: dispatch=OFF resume=OFF prod_exec=0  ⚠ test-mode    │
├───────────────┬────────────────────────────────────────────────────────────┤
│ ▸ Overview     │  OVERVIEW                                                 │
│ ▸ Team Work    │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │
│    Tasks       │  │Open Tasks │ │Clarifica- │ │Deliveries │ │Approvals  │  │
│    Deliveries  │  │   14      │ │tions: 3   │ │Pending: 2 │ │Required:1 │  │
│ ▸ Operator     │  └───────────┘ └───────────┘ └───────────┘ └───────────┘  │
│   Center       │  ┌───────────┐ ┌────────────────────────────────────┐    │
│    Action Ctr  │  │Agent      │ │ production_executed_true_count = 0 │    │
│    Approvals   │  │Failures:0 │ │ external_actions_enabled = false   │    │
│    DLQ/Retry   │  └───────────┘ └────────────────────────────────────┘    │
│    Incidents   │                                                          │
│ ▸ Governance   │  [Open Tasks list...]                                    │
│    Safety Ctr  │                                                          │
│    Audit Evid. │                                                          │
│ ▸ Platform Ops │                                                          │
│   (collapsed)  │                                                          │
│ ▸ Settings     │                                                          │
└───────────────┴────────────────────────────────────────────────────────────┘
```

## Safety UX (required for every option)

| State | How it is shown in this layout |
| --- | --- |
| `dispatch_enabled=false` | Persistent top bar, all pages; also repeated in Task Detail/Workroom safety panel |
| `resume_dispatch_enabled=false` | Same top bar; repeated on Clarification answer form |
| `production_executed_true_count=0` | Overview dashboard card + Safety Center; numeric, always visible, not buried |
| `production_effect` warning | Inline banner on Create Task when `production_effect=true`; carried into Task Detail safety panel |
| External action disabled | Top bar badge + Settings/Integrations page marks each integration `not connected` / `disabled` |
| Approval required | Overview card count + item-level badge in Approvals queue |
| RBAC denied | Standard readable message component, reused across all pages: "Your current role cannot perform this action." |
| Audit restricted | Audit Evidence page shows a readable restricted message per denied field/row, never a blank or broken section |

## Current UI migration thinking

- **Reuse as-is:** `SafetyBadge`, `StatusBadge`, `EmptyState`, `ErrorState`, `LoadingState`,
  `EvidenceTable`, `JsonPanel`, `KeyValueTable` — all layout-agnostic, no change needed.
- **Reuse with rework:** `Nav.tsx` — same underlying routes, but grouped/collapsible instead of
  flat; `ExecutiveOverview.tsx` becomes the basis for the new `Overview` dashboard (extend, don't
  replace).
- **Needs reset:** none of the existing pages need a rebuild under this option — it is primarily a
  navigation/IA change, which is why this option has the lowest migration cost of the three.
- **New components needed:** an `ActionCenter` aggregation component (queries DLQ + overdue +
  incidents + approvals into one list), a collapsible `NavGroup` component.
- **Codex phasing:** (1) ship the grouped `NavGroup` nav shell with existing routes unchanged, (2)
  extend Overview dashboard cards, (3) build Action Center once 66D/66C.4 backends exist — nav
  shell work can start immediately and does not block on 66D.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
