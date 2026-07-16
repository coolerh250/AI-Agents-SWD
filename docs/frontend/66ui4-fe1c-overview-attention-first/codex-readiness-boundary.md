# Codex Readiness Boundary — DESIGN-66UI.4-FE.1C Overview Attention-first Cleanup

> **Boundary document only. No runtime code changed. No frontend implementation changed. Codex is
> NOT authorized to implement anything in this document until the Product Owner explicitly
> authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the boundary Codex must observe for the FE.1C
Overview attention-first work, subordinate to and consistent with
`docs/design/66ui4-fe1c-overview-attention-first/codex-implementation-boundary.md` (Claude Design's
own notes) and this stage's
`docs/contracts/66ui4-fe1c-overview-attention-first/frontend-implementation-boundary.md`.

## 1. Authorization gate — two preconditions, both required

```text
1. Claude Code architecture review must pass (this document/review — PASS, confirmed).
2. PR #7 (frontend/66ui4-fe1b-calm-safety) must be merged to main before FE.1C implementation
   begins. CalmSafetyPosture.tsx, which FE.1C's System Posture section reuses, does not exist on
   main until that merge.
3. An explicit Product Owner authorization naming FE.1C implementation specifically.
```

**Codex must not start FE.1C implementation on its own initiative, and must not start it even after
Product Owner authorization if PR #7 is still unmerged at that time.**

## 2. Can implement after both preconditions are met and Product Owner authorizes

- **Overview restructure** — `apps/admin-console/src/pages/ExecutiveOverview.tsx` into the
  attention-first sections (Needs your attention → AI team activity → Current work → System posture
  → Platform & delivery metrics (demoted) → Future capabilities), per
  `information-architecture.md` / `layout-wireframe.md`.
- **Needs-your-attention** — filtered `GET /tasks` calls (`status=clarification_needed`,
  `status=blocked`) for real counts, honest 66D placeholders for Deliveries/Approvals.
- **AI team activity** — from `GET /operations/agent-executions`, conservative status mapping (see
  §3), verified against live test-runtime data before finalizing.
- **Current work snapshot** — recent tasks from `GET /tasks`, sorted by `updated_at`.
- **System posture** — reuse `CalmSafetyPosture` (compact mode) directly; do not duplicate its logic.
- **Metrics demotion** — the existing 12 `getOverview()` cards, unchanged data, moved to a secondary
  section.
- **Future-capability placeholders** and **microcopy** per the FE.1C design docs.

## 3. Conservative agent-execution status mapping (binding until re-verified live)

```text
"completed"          -> "Completed"
"failed"             -> "Needs review"
any other value/null -> "Not reported"
```

Do not invent a "Running"/"Working"/"Queued" mapping without first confirming, against live
`/operations/agent-executions` data on the test runtime, that such a value actually occurs.

## 4. What Codex must NOT implement

```text
- Backend changes.
- API changes.
- Database changes.
- New metrics endpoints.
- Workflow dispatch / resume.
- Production / external controls of any kind.
- Delivery (66D) real UI beyond a compliant placeholder.
- Reminder/Expiry (66C.4) real UI beyond a compliant placeholder.
- Notifications / Action Center real UI (future; placeholder only).
- Pipeline board (future; read-only only when eventually authorized; no drag-and-drop ever).
- New agent activity model.
- Client-side-only RBAC (server remains the sole access-control authority).
- Hiding required audit/safety evidence.
- Duplicating or re-implementing FE.1B's CalmSafetyPosture logic.
- Any IA/route/navigation change (the existing "/" route and 66UI.2 nav stay exactly as deployed).
- Fabricated counts of any kind; a count renders only from real existing data, else an empty/
  placeholder state.
```

## 5. Dependency map

| Frontend piece | Blocked on |
| --- | --- |
| Overview restructure (FE.1C) | PR #7 merged to `main` + Product Owner authorization |
| Delivery Inbox/Detail, Approvals (real data) | Claude Code's Step 66D contract |
| Reminder/overdue/expiry (real data) | Claude Code's Step 66C.4 contract |
| Notifications / Action Center | Its own future design brief + contract |
| Lifecycle Pipeline read-only view | A status-to-column mapping frontend-contract from Claude Code (still unmet) |

## 6. Recommended PR shape (if/when authorized)

Frontend-only, single cohesive PR touching `apps/admin-console/src/pages/ExecutiveOverview.tsx`, a
small number of new presentational components, and this stage's own docs/verifier/test —
comparable in shape and risk to the already-shipped FE.1A/FE.1B stages. `npm test` / `npm run build`
/ `npm run typecheck` required; no backend/infra path touched.

## Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No workflow dispatch. No workflow resume. No external action. No production action. Codex
implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
