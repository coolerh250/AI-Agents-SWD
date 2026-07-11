# Layout Option 3 — Lifecycle Pipeline

> Owner: Claude Design. One of three layout proposals for DESIGN-66UI.1. Not selected by default —
> see `recommendation.md` and `product-owner-discussion-guide.md`.

## 1. Layout name

Lifecycle Pipeline

## 2. Design concept

The Admin Console's home is a **stage-based pipeline view** (Kanban-like columns) mirroring the
Software Delivery Team's actual lifecycle: `Intake → Requirement → Development → QA → Delivery →
Review`. Each task appears as a card in exactly one column at a time, and every card surfaces its
Workroom/Clarification/Delivery status inline without opening it. This is the option most oriented
around the fixed Software Delivery Team's flow described in the product context.

## 3. Best-fit user types

PM/Engineering Lead managing a portfolio of tasks moving through stages; Platform Admin wanting an
at-a-glance view of where the whole team's work sits. Weaker fit for a Requester who only cares
about their own single task, and for Agent Operator/Reviewer whose work (DLQ, approvals) is not
stage-shaped.

## 4. Main navigation structure

```text
Left sidebar (minimal — pipeline is the primary surface, not a nav tree):

▸ Pipeline            (default landing page — the Kanban board)
▸ Operator Center
▸ Safety Center
▸ Audit Evidence
▸ Platform Ops (collapsed)
▸ Settings

Top bar: view toggle [Pipeline | List] so Requester/single-task users can switch to a flat list
instead of the board, without leaving the same page.
```

## 5. Dashboard behavior

The pipeline board itself *is* the dashboard — there is no separate metrics-card Overview page in
this option's default state. Column headers show per-stage counts and per-stage safety rollups
(e.g., "QA (4) — 1 blocked"). A "Blocked" swimlane or filter surfaces anything with an open
Clarification or a Retry/DLQ condition, cutting across the stage columns when needed.

## 6. Task / Workroom placement

Each pipeline card shows a compact status strip (Clarification open/none, Delivery status, Safety
flag) and clicking the card opens the task's Workroom as an **overlay/drawer** on top of the board
— not a full page navigation — so the user's place in the pipeline is preserved when they close it.

## 7. Audit / Safety placement

Per-card safety indicator inline on the board (small icon/badge: "safe" / "blocked" /
"approval required"); the full Safety Center and cross-task Audit Evidence remain separate
top-level nav items for deep inspection, same as Options 1 and 2.

## 8. Delivery / Review placement

Delivery is modeled as the last pipeline column ("Review"), so a delivered-but-unreviewed task
visibly sits in a column until a reviewer acts — this makes delivery backlog viscerally visible
(a full "Review" column) rather than a separate inbox count. `Accept` moves the card out of the
board (to `completed`); `Request Changes` moves it back to `Development`; `Re-run QA` moves it back
to `QA`. This directly visualizes the state-machine in `docs/product/project-delivery-state-model.md`
-style transitions the product already models server-side.

## 9. Operator Center placement

Separate top-level nav item, not part of the pipeline board, because DLQ/Retry/Approvals/Incidents
are not stage-shaped — they are cross-cutting operational concerns that would otherwise clutter the
board with non-lifecycle information.

## 10. Pros

- Uniquely good at answering "where is everything, end-to-end, right now" for a PM managing many
  tasks — the single most literal visualization of the product's own core-flow diagram
  (`建立任務 → 任務審查 → Agent Team 執行 → Workroom → Clarification → Delivery → 人工驗收`).
- Makes "blocked" states (the product's most safety-relevant states) visually unmissable — a card
  stuck in a column with a Clarification-open badge is harder to miss than a count on a dashboard
  card.
- Naturally extensible to "more AI teams / more workflow types" (a stated future requirement) since
  each team/workflow type could define its own column set later.

## 11. Cons

- Kanban/pipeline visual language is the closest of the three options to "just an issue tracker" —
  the stage prompt explicitly warns against this; this option requires the most deliberate visual
  restraint (safety badges, audit-ready framing) to avoid reading as a generic ticket board.
- A drawer/overlay Workroom is more awkward for long collaboration sessions (many messages,
  clarifications) than a full-page workspace — Option 2 is structurally better suited to deep
  single-task work.
- Largest frontend rebuild of the three: the board itself, drag/transition semantics (or read-only
  stage indicators if drag is out of scope), and the drawer pattern are all new, on top of the
  existing page components.
- Requires stage-per-task data to be reliable and current; if intermediate states are noisy or
  ambiguous in the backend today, the board will visibly show it.

## 12. Recommended use case

Choose this if the Product Owner's near-term priority is **visualizing the fixed Software Delivery
Team's end-to-end flow** for a PM managing many tasks concurrently, and is comfortable with a
larger frontend investment before the payoff (this option benefits most once 66D and 66C.4 exist,
weakest of the three if built with today's feature set alone).

## 13. Risk or tradeoff

This is the option most likely to need real product decisions before Codex can start (e.g., can a
task be manually dragged between stages, or is stage strictly server-derived and read-only in the
UI?) — several of the "Open questions" in `product-owner-discussion-guide.md` are specific to this
option for exactly that reason.

## 14. ASCII wireframe sketch

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [Role: PM ▾]  Safety: dispatch=OFF resume=OFF prod_exec=0   [Pipeline|List]│
├───────────────┬────────────────────────────────────────────────────────────┤
│ Pipeline       │  INTAKE(2)  REQUIREMENT(3) DEV(5)   QA(4)⚠1   REVIEW(2)   │
│ Operator Ctr   │  ┌───────┐  ┌───────┐      ┌──────┐ ┌──────┐  ┌───────┐  │
│ Safety Center  │  │Task A │  │Task C │      │Task E│ │Task G│  │Task I │  │
│ Audit Evidence │  │       │  │⚠ Clar.│      │      │ │blocked│  │ready  │  │
│ Platform Ops   │  └───────┘  │ open  │      └──────┘ │for QA │  │for    │  │
│ (collapsed)    │  ┌───────┐  └───────┘      ┌──────┐ │rerun  │  │review │  │
│ Settings       │  │Task B │  ┌───────┐      │Task F│ └──────┘  └───────┘  │
│                │  └───────┘  │Task D │      └──────┘                     │
│                │             └───────┘                                    │
└───────────────┴────────────────────────────────────────────────────────────┘
      (clicking a card opens Workroom as a drawer, board stays visible behind it)
```

## Safety UX (required for every option)

| State | How it is shown in this layout |
| --- | --- |
| `dispatch_enabled=false` | Top bar (all pages) + a small note in the Workroom drawer header |
| `resume_dispatch_enabled=false` | Same top bar; note repeated in the drawer's Clarification answer form |
| `production_executed_true_count=0` | Safety Center (deep nav item) — not on the board itself, to avoid diluting the board with non-task-level metrics |
| `production_effect` warning | Persistent badge on the card itself for any task with `production_effect=true`, visible without opening the drawer |
| External action disabled | Settings/Integrations, same as other options |
| Approval required | Card badge in the "Review" column ("⚠ approval required") + Operator Center |
| RBAC denied | Same reusable readable-message component |
| Audit restricted | Drawer's Audit section shows the restricted message inline; cross-task Audit Evidence page unaffected |

## Current UI migration thinking

- **Reuse as-is:** all shared components (`SafetyBadge`, `StatusBadge`, `EmptyState`, `ErrorState`,
  `LoadingState`, `EvidenceTable`, `JsonPanel`, `KeyValueTable`).
- **Reuse with rework:** `TaskWorkroom.tsx`'s internals become the content of the drawer/overlay
  rather than a full page — the component's message-thread and clarification-form logic can be
  reused, only its container changes.
- **Needs reset:** `TaskList.tsx` needs a genuinely new companion view (the board itself is new
  code, not a rework of the list — the list remains as the "List" toggle state).
- **New components needed:** `PipelineBoard`, `PipelineColumn`, `TaskCard` (compact, safety-badge-
  aware), `WorkroomDrawer`.
- **Codex phasing:** (1) ship the board as read-only (server-derived stage, no drag) alongside the
  existing Task List as a view toggle — lowest-risk first step, (2) add the drawer overlay reusing
  existing Workroom internals, (3) only consider drag-to-transition after the Product Owner
  explicitly decides whether manual stage transition is a real product requirement (see open
  questions) — this should not be assumed as in-scope by Codex.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
