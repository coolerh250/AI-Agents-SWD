# Frontend Implementation Boundary — DESIGN-66UI.4-FE.1C Overview Attention-first Cleanup

> **Boundary document only. No runtime code changed. No backend changed. No frontend implementation
> changed. Codex is NOT authorized to implement anything in this document until the Product Owner
> explicitly authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the contract boundary for the FE.1C Overview
attention-first work defined in `docs/design/66ui4-fe1c-overview-attention-first/design-brief.md`,
subordinate to and consistent with the merged
`docs/design/66ui4-phase1-product-visual-language/overview-dashboard-spec.md` and
`docs/contracts/66ui4-phase1-product-visual-language/frontend-implementation-boundary.md`.

## 1. No new or changed backend contract is required for FE.1C

Every surface FE.1C touches already reads from an existing, deployed endpoint:

```text
GET /operations/admin-console/overview   (getOverview -- already used by ExecutiveOverview.tsx)
GET /tasks                                (taskApi.list -- already used by TaskList.tsx)
GET /operations/safety                    (getSafety -- already used by FE.1B's CalmSafetyPosture)
GET /operations/agent-executions          (getAgentExecutions -- already used by Agent Executions page)
```

No new endpoint, response field, or response shape is requested.

## 2. Precondition — merge order

**FE.1C implementation must not begin until PR #7 (`frontend/66ui4-fe1b-calm-safety`) is merged to
`main`.** The System Posture section reuses `CalmSafetyPosture.tsx`, which does not exist on `main`
until that merge. This is a hard precondition, not a preference — see the Codex readiness boundary's
authorization gate.

## 3. What may proceed, once authorized and once the precondition above is met

- **Overview restructure** — reorganize `apps/admin-console/src/pages/ExecutiveOverview.tsx` into the
  attention-first sections in `information-architecture.md` / `layout-wireframe.md`, over existing
  data only. No new route; the existing `/` route's content is restructured in place.
- **Needs-your-attention section** — real counts from `GET /tasks` filtered by the existing `status`
  query parameter (`taskApi.list({status: "clarification_needed"})`,
  `taskApi.list({status: "blocked"})` — **prefer these filtered calls over an unfiltered fetch plus
  client-side counting**, since `/tasks` has no server-side pagination today), plus honest 66D
  placeholders for Deliveries-to-review/Approvals. Any `/tasks` failure (missing test-role identity,
  `role_cannot_view_tasks`, or any other error) must render through the existing readable-error
  mapping (`taskClient.ts`'s `READABLE_ERRORS`) or the brief's own "This information isn't available
  for your role right now." copy — never a raw error or a blank section.
- **AI team activity section** — from `GET /operations/agent-executions`, using the conservative
  status mapping in §4 below, verified against live test-runtime data before finalizing (do not ship
  a mapping value that was only assumed from this review's static code reading).
- **Current work snapshot** — recent tasks from `GET /tasks` sorted by `updated_at` (suggested count:
  5, pending Product Owner confirmation per `open-questions-and-risks.md` open question #4).
- **System posture integration** — reuse `CalmSafetyPosture` (compact mode) directly, exactly as
  `SafetyStatusBar.tsx` already does, passing the same `getSafety()` result. Do not re-implement or
  duplicate its logic.
- **Metrics demotion** — move the existing 12 `getOverview()` cards (`DataCard`/`StatusBadge`,
  unchanged data) into a secondary "Platform & delivery metrics" section, below the fold or
  collapsible.
- **Future-capability placeholders** — Delivery Review (66D), Reminder/Expiry (66C.4),
  Notifications/Action Center, Pipeline view — exact copy per
  `placeholder-and-empty-state-strategy.md`; no controls of any kind.
- **Microcopy** — apply `docs/design/66ui4-fe1c-overview-attention-first/microcopy-guide.md`
  verbatim where specified.
- New small presentational components (attention tile, activity row, work row, placeholder tile)
  within `apps/admin-console/src`, reusing `DataCard`/`StatusBadge`/`AsyncView`/existing empty/error
  state components and FE.1A visual tokens — no new tokens, no new palette.

## 4. Conservative agent-execution status mapping (binding until re-verified live)

```text
"completed"          -> "Completed"
"failed"             -> "Needs review"
any other value/null -> "Not reported"  (do NOT invent "Running"/"Working"/"Queued" — no evidence
                                          any such value exists in the current data model; confirm
                                          against live /operations/agent-executions data during
                                          implementation before adding any such mapping)
```

## 5. What requires a new or updated contract before it may proceed past FE.1C scope

| Frontend piece | Blocked on |
| --- | --- |
| Delivery Inbox/Detail (real data), Approvals real counts | Claude Code's Step 66D API/data contract |
| Reminder/Expiry (real data) | Claude Code's Step 66C.4 contract |
| Notifications / Action Center | Its own future design brief + contract |
| Pipeline board (even read-only) | A `docs/contracts/<stage>/frontend-contract.md` confirming the task-status-to-pipeline-column mapping (condition carried over from `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md` §3, still unmet) |

## 6. RBAC / safety posture unchanged

- Overview introduces no client-side gating; server-side RBAC on `/tasks` and every other endpoint
  remains the sole access-control authority. A `requester` identity naturally sees only its own tasks
  (`task_api.py`'s `scope_created_by` logic) — this personalizes "Needs your attention" correctly and
  is not a gap.
- No safety-relevant field may be hidden; System Posture only summarizes/links to Safety Center, it
  never removes access to FE.1B's detailed evidence.

## 7. Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No API contract change requested. No workflow dispatch. No workflow resume. No external
action. No production action. Codex implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
