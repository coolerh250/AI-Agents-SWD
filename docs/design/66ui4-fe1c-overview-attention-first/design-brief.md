# Design Brief — DESIGN-66UI.4-FE.1C Overview Attention-first Cleanup

> Owner: Claude Design. Detailed design brief for the FE.1C frontend sub-stage: turn the Overview
> from an engineering metrics console into an AI Team Command Center product home. **Design /
> documentation / handoff only — no runtime code, no frontend implementation, no backend/API/DB/
> workflow change, no Codex authorization.** Existing data only.

## Stage

`66ui4-fe1c-overview-attention-first` (DESIGN-66UI.4-FE.1C)

## Source of truth

`main` (commit `77ab4e0`) is authoritative. This brief **narrows and details** the already-merged
`docs/design/66ui4-phase1-product-visual-language/overview-dashboard-spec.md` (Phase 1, on main) into
an implementable FE.1C spec. It does not contradict it — where the merged spec described the
attention-first Overview at a high level, this brief specifies it against the *actual* existing data
and the FE.1A visual language already deployed.

## Relationship to sibling sub-stages

- **FE.1A** (visual tokens / typography / cards): merged + deployed. This brief consumes that visual
  language; it does not change tokens.
- **FE.1B** (calm safety posture): in progress by Codex. This brief **does not redesign FE.1B** — the
  Overview's "System posture" section only *links to / briefly summarizes* posture and must not
  duplicate or re-specify the FE.1B component. Where the Overview needs a posture summary it reuses
  FE.1B's component/output rather than defining its own.
- **FE.1C** (this brief): Overview attention-first cleanup.

## Design goal

Make the Overview answer, at a glance:

```text
1. What needs my attention now?
2. What is the AI team working on?
3. What is blocked or waiting for human input?
4. What changed recently?
5. Is the system safe?
6. Where should I go next?
```

…and stop reading as a raw metrics dump / backend-health debug page / log viewer / table-first admin
page / generic DevOps dashboard.

## Scope (FE.1C)

1. Overview information hierarchy (attention-first) — `information-architecture.md`.
2. Attention-first layout model + wireframe — `layout-wireframe.md`.
3. "Needs your attention" section — existing task data + honest placeholders.
4. AI team activity summary — existing agent-execution data only.
5. Calm system posture *integration* (link/summary, not a duplicate of FE.1B).
6. Recent work / recent task movement — existing task data.
7. Metrics demotion strategy — existing overview cards moved to a secondary section.
8. Placeholder strategy for 66D / 66C.4 gated content — `placeholder-and-empty-state-strategy.md`.
9. Empty-state strategy.
10. Overview microcopy — `microcopy-guide.md`.
11. Codex implementation boundary — `codex-implementation-boundary.md`.
12. Product Owner validation checklist — `product-owner-validation-checklist.md`.

## Existing-data-only constraint (binding)

FE.1C must be implementable with data the frontend can already obtain:

- `GET /operations/admin-console/overview` (already used by `ExecutiveOverview.tsx`).
- `GET /tasks` (already used by `TaskList.tsx` via `taskApi.list`).
- `GET /operations/safety` (already used by the FE.1B safety posture; Overview reuses FE.1B's
  summary, does not re-fetch/re-render detail).
- `GET /operations/agent-executions` (already used by the Agent Executions page).

See `existing-data-mapping.md` for the field-by-field mapping. **No new backend endpoint, no new DB
field, no new workflow computation, no new agent-activity stream, no new notification/delivery/
reminder backend is requested.** Anything requiring future backend is labelled
**"Future — requires later contract"** and excluded from FE.1C implementation scope.

## What this stage does NOT do

- No runtime code, no frontend implementation (design/handoff only).
- No change to FE.1A tokens or FE.1B safety posture.
- No new endpoint / DB / workflow / API.
- No fake numbers, no fake buttons, no fake controls.
- No Delivery (66D) / Reminder-Expiry (66C.4) / Notifications / Pipeline real UI — honest
  placeholders only.
- No Codex authorization — this brief goes to Claude Code review, then Product Owner authorization,
  before any implementation.

## Companion documents

`current-overview-analysis.md`, `information-architecture.md`, `layout-wireframe.md`,
`existing-data-mapping.md`, `placeholder-and-empty-state-strategy.md`, `microcopy-guide.md`,
`codex-implementation-boundary.md`, `product-owner-validation-checklist.md`,
`open-questions-and-risks.md`; handoff at
`docs/handoffs/66ui4-fe1c/claude-design-to-claude-code-handoff.md`; stage artifacts under
`docs/stages/66ui4-fe1c/`.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
