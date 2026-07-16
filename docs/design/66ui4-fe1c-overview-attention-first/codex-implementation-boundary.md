# Codex Implementation Boundary — DESIGN-66UI.4-FE.1C

> Owner: Claude Design, for Codex (Frontend Engineer). **Codex is NOT authorized by this document.**
> Authorization requires Claude Code's review to pass AND an explicit Product Owner go-ahead
> (`.agents/skills/design-collaboration/SKILL.md`, `.agents/skills/frontend-implementation/SKILL.md`).
> These notes describe the intended FE.1C build for when that authorization is granted.

## 1. What FE.1C may implement (once authorized)

- Restructure `ExecutiveOverview.tsx` (the `/` route) into the attention-first sections in
  `information-architecture.md` / `layout-wireframe.md`.
- Add sections B–G using **existing data only** per `existing-data-mapping.md`:
  - Needs-your-attention counts from `GET /tasks` (client-side counts of `clarification_needed` /
    `blocked`), plus honest 66D placeholders for Deliveries/Approvals.
  - AI team activity from `GET /operations/agent-executions`.
  - Current work from `GET /tasks` (recent by `updated_at`).
  - System posture by **reusing the FE.1B posture component/summary** (do not re-implement it).
  - Demoted "Platform & delivery metrics" = the existing 12 `getOverview()` cards, moved down.
  - Future-capability placeholders per `placeholder-and-empty-state-strategy.md`.
- Apply Overview microcopy from `microcopy-guide.md`.
- Reuse existing components (`DataCard`, `StatusBadge`, `AsyncView`, `EmptyState`, `ErrorState`,
  `LoadingState`) and FE.1A tokens. New presentational components (attention tile, activity row,
  work row, placeholder tile) are allowed **within `apps/admin-console/src`** and are frontend-only.

## 2. Hard boundary (must not)

```text
- No new backend endpoint, no new API client method beyond calling existing endpoints.
- No new database field, no new workflow computation, no new agent-activity stream,
  no new notification/delivery/reminder backend.
- No change to FE.1A tokens; no redesign/duplication of the FE.1B safety posture.
- No IA/route change (the 66UI.2 nav and the "/" route stay as-is).
- No fabricated numbers; a count renders only from real existing data, else an empty/placeholder.
- No fake buttons/controls; placeholders expose no action.
- No workflow dispatch/resume/state mutation; no production or external action.
- No approval/delivery/retry/reminder action from the Overview.
- No client-side-only RBAC; server governs the underlying endpoints.
```

## 3. Existing-data-only reminder

Every dynamic value must trace to `GET /operations/admin-console/overview`, `GET /tasks`,
`GET /operations/agent-executions`, or the FE.1B posture summary (`GET /operations/safety`). If a
desired element cannot be sourced from these, it is **Future — requires later contract** and ships
as a placeholder, not a real element.

## 4. Open item for Claude Code to confirm before implementation

Whether the Overview should call `GET /tasks` (a new call site of an existing endpoint) for the
attention counts and current-work list. If not approved, those sections degrade to honest empty
states. See `open-questions-and-risks.md`.

## 5. Suggested PR shape (once authorized)

Frontend-only, single cohesive PR touching `apps/admin-console/src` (Overview page + small new
presentational components) + this stage's docs/verifier/test. Frontend tests + `npm run build` /
`npm test` required. Revertible; no backend/infra path touched.

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
