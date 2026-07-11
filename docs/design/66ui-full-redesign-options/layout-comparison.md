# Layout Comparison — DESIGN-66UI.1

> Owner: Claude Design. Side-by-side comparison of the three options in
> `layout-option-1-operations-command-center.md`, `layout-option-2-task-workspace.md`,
> `layout-option-3-lifecycle-pipeline.md`.

## Comparison table

| Dimension | Option 1 — Operations Command Center | Option 2 — Task Workspace | Option 3 — Lifecycle Pipeline |
| --- | --- | --- | --- |
| Primary organizing unit | Cross-task dashboard | Single task workspace | Pipeline stage |
| Best-fit roles | Platform Admin, Agent Operator, PM (oversight) | Requester, PM (single task), Engineer | PM (portfolio view), Platform Admin |
| Weakest-fit role | Requester (extra depth to reach Workroom) | Platform Admin/Operator (cross-task hidden) | Requester, Agent Operator |
| Landing page | Card dashboard (Overview) | Task list, role-scoped | Pipeline board |
| Workroom depth from landing page | 2 clicks (Tasks → Task → Workroom) | 1 click, opens as workspace tab | 1 click, opens as drawer |
| Delivery placement | Cross-task Deliveries under Team Work | Tab inside Task Workspace + secondary cross-task inbox | Last pipeline column ("Review") |
| Operator Center prominence | High — 2nd top-level group | Medium — top-level but secondary to task list | Medium — top-level, separate from board |
| Category H (Platform Ops) handling | Collapsed top-level group | Collapsed top-level group, feels more isolated | Collapsed top-level group, feels more isolated |
| Frontend migration cost | Lowest — mostly nav regrouping | Medium-high — Task Detail + Workroom merge into tabs | Highest — new board/card/drawer components |
| Dependency risk | Low — works with today's feature set | Medium — Delivery tab is empty until 66D | Medium-high — needs 66D + 66C.4 to feel complete, and needs a product decision on drag/transition |
| Risk of reading as "just a dashboard/tracker" | Medium (NOC-dashboard risk) | Low | Highest (Kanban/issue-tracker risk) |
| Best answers "what needs my attention across everything?" | Yes, directly | Partially (header strip only) | Yes, via blocked-swimlane/badges |
| Best answers "let me work this one task deeply" | Partially (2 clicks away) | Yes, directly | Partially (drawer, not full page) |

## Recommended option

**Option 1 — Operations Command Center**, as the default recommendation *if* the Product Owner
wants the lowest-risk, lowest-migration-cost path that still fixes the immediate problem (27-item
flat nav) without a large frontend rebuild. See `recommendation.md` for the full "why" and its
caveats.

## Hybrid possibility

The three options are not mutually exclusive at the component level:

- Option 1's **grouped/collapsible nav shell** is close to a prerequisite for either of the other
  two — even Option 2 and Option 3 need *some* top-level nav for Operator Center/Safety/Settings
  alongside their respective primary surface.
- Option 2's **tabbed Task Workspace** could sit *underneath* Option 1's nav shell as "what Tasks →
  Task Detail opens into," rather than a separate full layout philosophy — i.e., Option 1's IA +
  Option 2's task-opening pattern.
- Option 3's **pipeline board** could be offered as a `Pipeline` view *within* Option 1's "Team
  Work" group, alongside `Tasks` (list) as an alternate view of the same data, rather than as the
  entire app's landing page.

A realistic hybrid: **Option 1's nav/IA + Option 2's tabbed task workspace when a task is opened +
Option 3's pipeline board as an optional view toggle on the Task list**, deferred until 66D exists.
This is flagged as "Hybrid" in the discussion guide rather than pre-selected, because it is a
larger scope decision than picking one option outright.

## Key tradeoffs

1. **Migration cost vs. product-fit ambition.** Option 1 is cheapest to ship but is the most
   "incremental" — it does not change the fundamental interaction model, only the navigation.
   Options 2 and 3 cost more but more directly express the product's stated differentiators
   (collaboration depth, lifecycle visibility respectively).
2. **Sequencing risk.** Options 2 and 3 both have components that are only fully justified once
   66D (Delivery) and 66C.4 (Reminder/Expiry) ship — choosing either now means accepting a
   partially-empty experience in the interim, or explicitly sequencing Codex's phases so the new
   layout ships incrementally alongside those backend stages (see each option's "Codex phasing").
3. **Category H never gets a clean answer from layout alone.** All three options collapse it the
   same way; resolving whether it belongs in this IA at all is a product decision independent of
   which layout wins (see `product-owner-discussion-guide.md`).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
