# Frontend Implementation Boundary — DESIGN-66UI.1 Full UI/UX Redesign Options

> **Contract-boundary document only. No runtime code changed. No backend changed. No API/contract
> requested or created by this document. No Codex implementation authorized.**

Owner: Claude Code (Lead Engineer / Architecture Owner). This document does not introduce a new API
contract — per `docs/design/66ui-full-redesign-options/recommendation.md` and
`product-owner-decision-summary.md`, the Hybrid decision requires no new or changed backend data
shape. Its purpose is to state, precisely, what Codex may and may not build once the Product Owner
authorizes implementation, and which pieces still require a contract that does not exist yet.

## 1. No contract change required by this stage

Confirmed independently in `docs/design/66ui-full-redesign-options/claude-code-architecture-review.md`
§6.4: none of the three layout options, nor the Hybrid selection, request a new or modified backend
endpoint or data shape. The existing endpoints (`GET /tasks`, `GET /tasks/{id}`,
`GET /tasks/{id}/workroom`, `GET /tasks/{id}/audit-evidence`, `POST /tasks/{id}/workroom/messages`,
`POST /tasks/{id}/clarifications`, `POST /tasks/{id}/clarifications/{id}/answer`) are sufficient for
every piece of the Hybrid IA/Navigation and Task Workspace work.

## 2. What may proceed without a new contract (IA/navigation restructuring only)

- Grouped/collapsible left-navigation shell (Option 1's `NavGroup` pattern) — a pure `Nav.tsx`
  restructure using existing routes; no new data requirement.
- Reorganizing existing pages under nav groups ("Team Work," "Operator Center," "Governance,"
  "Platform Ops," "Settings") — routing/menu-structure change only, no page content change.
- Task Workspace tab shell (Option 2) wrapping the *existing* `TaskDetail.tsx` and
  `TaskWorkroom.tsx` content as tabs — this is a container/routing restructure; the data each tab
  displays is already returned by the existing endpoints above.
- Placeholder routes/sections for not-yet-available areas (Delivery Inbox, Approval Queue,
  DLQ/Retry, Reminder/Expiry indicators), provided each placeholder follows the placeholder policy
  in `product-owner-decision-summary.md` §5 (states "Not yet available," the specific required
  stage, and "No workflow action available").

## 3. What requires a new or updated contract before Codex may build it

- **Lifecycle Pipeline / Kanban board (Option 3), if and when it proceeds beyond a placeholder.**
  Even though the first version must be read-only, Claude Code must still publish a
  `docs/contracts/<pipeline-stage>/frontend-contract.md` confirming: which existing field(s) supply
  each task's pipeline-column placement (task status is already returned by `GET /tasks`, but the
  mapping from status values to the six named stages — Intake/Requirement/Development/QA/
  Delivery/Review — needs to be written down as a contract, not inferred by Codex), and restating
  explicitly that stage is server-derived and read-only in the UI (no drag-and-drop endpoint exists
  or is implied).
- **Delivery Inbox / Delivery Detail / Accept / Reject / Request Changes / Re-run QA (66D).** No
  contract exists yet. Codex must not build the Delivery tab (Option 2) or Deliveries queue
  (Option 1) beyond a placeholder until Claude Code publishes the 66D contract under
  `docs/contracts/<66d-stage>/`.
- **Clarification reminder / overdue / expiry indicators (66C.4).** No contract exists yet. Codex
  must not build a real "overdue" badge, blocked-swimlane trigger, or Action Center count for this
  until Claude Code publishes the 66C.4 contract.
- **Unified Operator Action Center** (aggregating DLQ + overdue + incidents + approvals). Depends on
  both the 66D and 66C.4 contracts existing first — cannot be meaningfully built before either does.

## 4. RBAC and safety posture — unchanged

No layout option changes any RBAC rule or safety behavior. `dispatch_enabled`,
`resume_dispatch_enabled`, and `production_executed_true_count` remain server-computed and must
continue to be displayed exactly as the existing endpoints return them — no layout may hardcode or
infer these values client-side. This is restated, not newly introduced, per every layout option's
"Safety UX" table.

## 5. Statement

Contract-boundary specification only, describing what is and is not authorized without further
contract work. No runtime code changed. No API/contract created or requested by this document. No
Codex implementation authorized. No workflow dispatch. No workflow resume. No external action. No
production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
