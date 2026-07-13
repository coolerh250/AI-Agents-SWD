# Codex Readiness Boundary — DESIGN-66UI.1 Full UI/UX Redesign Options

> **Boundary document only. No runtime code changed. No frontend implementation changed. Codex is
> NOT authorized to implement anything in this document until the Product Owner explicitly
> authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the boundary Codex must observe for any
future work on the Hybrid direction selected in
`docs/design/66ui-full-redesign-options/product-owner-decision-summary.md`. It does not itself
authorize starting work — see §4.

## 1. What Codex may later start with (once authorized)

- Navigation grouping / IA shell — the grouped, collapsible `NavGroup` restructure of `Nav.tsx`
  (Option 1's IA), using existing routes unchanged.
- Left navigation grouping — "Team Work," "Operator Center," "Governance," "Platform Ops,"
  "Settings" groups as specified in `layout-option-1-operations-command-center.md` §4.
- Route grouping — reorganizing which existing pages sit under which nav group; no new routes to
  pages that don't exist yet.
- Page section organization — e.g. the Task Workspace tab shell (Option 2) wrapping the existing
  `TaskDetail.tsx`/`TaskWorkroom.tsx` content as tabs, a pure container/restructure with no new data
  requirement.
- Placeholder routing for future features (Delivery Inbox, Approval Queue, DLQ/Retry, Reminder/
  Expiry indicators) — provided every placeholder states, in plain text: "Not yet available,"
  the specific required stage ("Requires Step 66D" or "Requires Step 66C.4" as applicable), and "No
  workflow action available."

## 2. What is explicitly forbidden, always

- No business logic change.
- No backend behavior change.
- No workflow state mutation.
- No workflow dispatch.
- No workflow resume.
- No production behavior.
- No lifecycle drag-and-drop (Option 3's pipeline board, if ever built, ships read-only first — see
  `docs/design/66ui-full-redesign-options/product-owner-decision-summary.md` §4 and
  `claude-code-architecture-review.md` §5).
- No Delivery (66D) UI beyond a compliant placeholder until Claude Code publishes the 66D contract.
- No Reminder/Expiry (66C.4) UI beyond a compliant placeholder until Claude Code publishes the
  66C.4 contract.

## 3. Dependency map (what must exist before which piece can move past placeholder)

| Frontend piece | Blocked on |
| --- | --- |
| Nav shell / IA restructure | Nothing — can start immediately once authorized |
| Task Workspace tab shell (existing content only) | Nothing — can start immediately once authorized |
| Delivery tab / Deliveries queue (real data) | Claude Code's 66D contract |
| Reminder/overdue badge, blocked-swimlane trigger | Claude Code's 66C.4 contract |
| Unified Operator Action Center | Both 66D and 66C.4 contracts |
| Lifecycle Pipeline board (even read-only) | A `docs/contracts/<stage>/frontend-contract.md` confirming the task-status-to-pipeline-column mapping (see `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md` §3) |

## 4. Authorization gate

**Codex must not implement until the Product Owner explicitly authorizes implementation after this
review.** This document, the architecture review, and the implementation-boundary contract
together establish that the design is *safe* to authorize — they do not themselves constitute that
authorization. The next required step, per
`docs/process/frontend-design-engineering-collaboration-protocol.md`, is Claude Design producing a
fuller design brief for the specific implementation stage (e.g. `66ui.2-navigation-ia`), followed
by Product Owner sign-off to begin.

## 5. Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No
backend change. No workflow dispatch. No workflow resume. No external action. No production
action. Codex implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
