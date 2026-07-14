# Frontend Implementation Boundary — DESIGN-66UI.4 Phase 1 Product Visual Language

> **Boundary document only. No runtime code changed. No backend changed. No frontend implementation
> changed. Codex is NOT authorized to implement anything in this document until the Product Owner
> explicitly authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the contract boundary for the Phase 1 visual
language work defined in `docs/design/66ui4-phase1-product-visual-language/design-brief.md`,
subordinate to and consistent with
`docs/contracts/66ui2-navigation-ia/frontend-implementation-boundary.md` and
`docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md`.

## 1. No new or changed backend contract is required for Phase 1

Every surface Phase 1 touches already reads from an existing, deployed endpoint. Existing endpoint
set that remains sufficient (confirmed present in `apps/orchestrator/src/operations.py`):

```text
GET /operations/admin-console/overview
GET /operations/safety
GET /tasks
GET /tasks/{id}
GET /tasks/{id}/workroom
GET /tasks/{id}/audit-evidence
```

Phase 1 is a presentation/composition change over data these endpoints already return, plus honest
placeholders for the two Overview tiles gated on the Step 66D contract. No new endpoint, response
field, or response shape is requested.

## 2. What may proceed without a new contract (once authorized)

- **Visual-language tokens** (`docs/design/66ui4-phase1-product-visual-language/visual-language-spec.md`):
  add `--surface-raised` / `--surface-base` / `--surface-quiet`, a spacing scale, a typography scale,
  and lifecycle-vs-safety color separation to `apps/admin-console/src/styles.css`, refining the
  existing dark tokens (`--bg`, `--card`, `--fg`, `--muted`, `--line`, `.b-ok`/`.b-warn`/`.b-bad`/
  `.b-neutral`) — no new palette, no theme system.
- **Calm safety posture component** (`calm-safety-posture-spec.md`): replace the raw-field render in
  `SafetyStatusBar.tsx` with a calm summary + expandable human-labeled detail, reading the exact same
  server fields it reads today (`production_executed_true_count`, `dispatch_enabled`,
  `resume_dispatch_enabled`, `task_api_workflow_dispatch_enabled`,
  `task_workroom_resume_dispatch_enabled`, `github_external_write_enabled`,
  `discord_external_send_enabled`, `llm_external_call_enabled`, `approval_required`,
  `requires_approval`, `workflow_production_executed_true_count`) — presentation-only change.
- **Overview restructure** (`overview-dashboard-spec.md`): reorganize `ExecutiveOverview.tsx` into
  attention-first bands over the existing `/operations/admin-console/overview` data, with honest
  "Requires Step 66D" placeholders (not fabricated numbers) for Deliveries-to-review and Approvals
  tiles.
- **Navigation visual polish** (`navigation-visual-polish-spec.md`): restyle `Nav.tsx` /
  `NavGroup.tsx` / `.side-nav` (group rhythm, active-state weight, quiet Platform Ops density) with
  **zero IA/route change** — the deployed 66UI.2 group membership, order, and every route stay exactly
  as merged/deployed in Step 66UI.2-FE.1-M/D.
- **Engineering-field relabel/demote + microcopy** (`engineering-field-reduction-map.md`,
  `product-microcopy-guide.md`), applied only to the surfaces Phase 1 touches (safety posture,
  Overview, nav, and the safety fields already shown on `TaskDetail.tsx`) — presentation only; no
  value or its server provenance changes.

## 3. What requires a new or updated contract before it may proceed past this Phase 1 scope

| Frontend piece | Blocked on |
| --- | --- |
| Delivery Inbox / Delivery Detail (real data), Approvals real counts | Claude Code's Step 66D API/data contract |
| Reminder/Expiry (real data) | Claude Code's Step 66C.4 contract |
| Full Task List / Task Detail / Workroom / Audit Evidence redesigns | Their own future design brief + Claude Code review (Phase 1 only defines the shared field-reduction/microcopy mapping they will use) |
| Task Workspace tab convergence (Direction B) | Its own implementation-plan review, carried over unresolved from the 66UI.1 review |
| Lifecycle Pipeline board, even read-only | A `docs/contracts/<stage>/frontend-contract.md` confirming the task-status-to-pipeline-column mapping — condition carried over from `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md` §3, still unmet |

## 4. RBAC / safety posture unchanged

- Nav visibility and visual treatment remain a convenience/presentation layer only; server-side RBAC
  is the sole access-control authority. Phase 1 introduces no client-side gating.
- `dispatch_enabled`, `resume_dispatch_enabled`, `production_executed_true_count`, and every other
  safety field remain server-computed and displayed exactly as returned; the calm posture summary is
  a presentation mapping over those same values, never a hardcoded or inferred one. A missing value
  must render "not reported," never a guessed default.
- No safety-relevant field may be hidden entirely — relocation to expand/hover is the only permitted
  disposition for a safety-relevant field.

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
