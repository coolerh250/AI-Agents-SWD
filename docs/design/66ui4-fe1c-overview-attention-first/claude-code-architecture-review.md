# Claude Code Architecture Review — DESIGN-66UI.4-FE.1C Overview Attention-first Brief

Marker: `STEP66UI4_FE1C_DESIGN_REVIEW_VERIFY: PASS`

Reviewed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`). Review scope: Draft PR #8,
`design/66ui4-fe1c-overview-attention-first`, commit `0c7762e`.

## Verdict

**PASS.** The FE.1C design brief is existing-data-only, introduces no backend/API/database/workflow
requirement, proposes no fake counts or fake controls, correctly treats 66D/66C.4/Notifications/
Pipeline as honest placeholders, and explicitly avoids duplicating FE.1B. All three open questions
have safe, concrete recommendations below. Ready for Product Owner decision on brief acceptance and,
separately, for a future explicit Codex FE.1C implementation authorization. Codex is **not**
authorized by this review. PR #8 not merged.

## 1. Shared Context Preflight

- Latest main reviewed: `7ad50d7` (Step 66UI.4-FE.1B-V — Product Owner UI validation for Calm Safety
  Posture, VISIBLE with one accepted gap).
- Skill files reviewed: `shared-context`, `stage-gate`, `security-governance`,
  `design-collaboration`, `frontend-implementation`.
- Shared docs reviewed: `source/progress.md`, `docs/process/source-of-truth-policy.md`,
  `docs/process/context-guard-protocol.md`, `docs/process/stop-conditions.md`,
  `docs/design/66ui-source-of-truth-record.md`,
  `docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md` (confirms the
  Hybrid A+B+C direction and that Overview falls under Direction A framing), Phase 1 design brief,
  **`overview-dashboard-spec.md`** (the merged Phase 1 spec this brief narrows), visual-language-spec,
  product-microcopy-guide, frontend-implementation-boundary, codex-readiness-boundary,
  fe1a-merge-record, step66ui4-fe1a-merged-main-test-deployment-record.
- Design PR/branch reviewed: PR #8, `design/66ui4-fe1c-overview-attention-first`, commit `0c7762e`
  (`gh pr view 8`: OPEN, base `main`, 17 files, mergeable unknown, +1478/-0).
- Current frontend source reviewed: `apps/admin-console/src/pages/ExecutiveOverview.tsx` (confirms
  the "flat 12-card grid" description in `current-overview-analysis.md` is accurate),
  `apps/admin-console/src/api/operations.ts` (`getOverview`, `getAgentExecutions`),
  `apps/admin-console/src/tasks/taskClient.ts` and `testRole.ts` (test-role auth headers, default
  identity), `apps/admin-console/src/tasks/taskTypes.ts` (confirms `clarification_needed`/`blocked`
  are real `TaskStatus` values), `apps/orchestrator/src/task_api.py` (confirms RBAC scoping
  behavior), `apps/orchestrator/src/operations.py` (confirms `/operations/agent-executions` response
  shape and the actual SQL-level status values in use).
- New information found: FE.1B (PR #7) has since been reviewed **PASS** and Product-Owner-validated
  **VISIBLE with one accepted, non-blocking gap** (missing live safety fields causing an honest
  "Unavailable" state) — not yet merged to `main`. This is directly relevant to Q2 below.
- Conflicts found: none. The brief correctly narrows the merged `overview-dashboard-spec.md` without
  contradicting it.
- How the new information affected this review: confirmed the FE.1B merge-order dependency this
  brief's own open questions already flagged, and let this review answer Q2 with the current, real
  FE.1B status rather than an assumption.

## 2. 20 required review checks

| # | Check | Result |
| --- | --- | --- |
| 1 | Existing-data-only constraint respected | PASS — every dynamic element traces to `getOverview()`, `GET /tasks`, `GET /operations/agent-executions`, or FE.1B's posture summary |
| 2 | No new backend metrics endpoint required | PASS |
| 3 | No new database field required | PASS |
| 4 | No workflow computation or dispatch/resume required | PASS |
| 5 | No external action required | PASS |
| 6 | No production action required | PASS |
| 7 | No fake counts proposed | PASS — every count either derives from real existing data or is an honest placeholder; the brief explicitly separates the legacy `ready_for_review_packages_count` from the not-yet-built 66D "Deliveries to review" item |
| 8 | No fake controls proposed | PASS — placeholders explicitly state "no buttons, no fake counts, no fake rows, no controls of any kind" |
| 9 | 66D-gated Delivery Review items are placeholders only | PASS |
| 10 | 66C.4-gated Reminder/Expiry items are placeholders only | PASS |
| 11 | Notifications/Action Center are future placeholders only | PASS |
| 12 | Pipeline view remains future/read-only-only/no drag-drop | PASS — explicitly stated in three separate docs |
| 13 | FE.1B calm safety posture referenced but not duplicated | PASS — IA §E and the Codex boundary both state "reuse FE.1B's component/output rather than defining its own" |
| 14 | Metrics demoted but still accessible | PASS — the existing 12 `getOverview()` cards move to a secondary "Platform & delivery metrics" section, unchanged data, not deleted |
| 15 | Overview remains useful for PM/Platform Admin/Agent Operator | PASS — see role-scoping analysis below; each role sees server-RBAC-appropriate content, no client-side gate |
| 16 | Requester view not over-complicated by operator-only material | PASS — the attention/activity/current-work bands are inherently scoped by the requester's own visible tasks (see Q1 analysis); no operator-only controls appear anywhere on Overview |
| 17 | No client-side-only RBAC introduced | PASS — the brief explicitly states server governs the underlying endpoints; Overview shows honest empty/role-restricted states, never a client-side gate |
| 18 | No hiding of audit/safety evidence | PASS — System posture only summarizes/links; it does not remove or relocate any evidence that exists today, since the detail remains on Safety Center under FE.1B |
| 19 | No runtime route changes unless explicitly frontend-only and safe | PASS — the brief restructures the content of the existing `/` route only; no new route, no nav change |
| 20 | Codex implementation boundary narrow enough for a small PR | PASS — `codex-implementation-boundary.md` scopes to one file restructure (`ExecutiveOverview.tsx`) plus small new presentational components, all within `apps/admin-console/src`; comparable in shape to FE.1A/FE.1B |

## 3. Open-question decisions

### Q1 — May Overview call `GET /tasks`?

**Recommendation: Option C** — Overview may call `GET /tasks`, but conservatively, with two concrete
refinements found during this review:

1. **Use the existing `status` query parameter for each attention count rather than one unfiltered
   fetch + client-side counting.** `task_api.py`'s `list_tasks` already accepts an optional `status`
   filter (confirmed at `apps/orchestrator/src/task_api.py:148-164`), and `taskApi.list(filters)`
   already supports it (`apps/admin-console/src/tasks/taskClient.ts`). Calling
   `taskApi.list({status: "clarification_needed"})` and `taskApi.list({status: "blocked"})`
   separately returns only the matching rows, rather than fetching the full task list and counting
   client-side as `existing-data-mapping.md` describes. This reduces payload size and avoids a future
   performance risk if the task volume grows — `GET /tasks` currently has no server-side pagination
   (confirmed: no `limit`/`page_size` parameter exists in `taskTypes.ts` or `task_api.py`), so an
   unfiltered fetch is the more expensive option available today.
2. **Role-scoping is correct-by-design, not a risk.** `task_api.py:161` confirms
   `scope_created_by = ctx.actor if ctx.role == "requester" else created_by` — a `requester`
   identity sees only their own tasks; every other role sees the unscoped set (subject to its own
   RBAC checks). This means "Needs your attention" naturally personalizes to "waiting on your
   answer" for a Requester and reflects team-wide state for PM/Platform Admin/Agent Operator — this
   is the *correct* behavior, not a gap, and matches the brief's own copy ("agents waiting on **your**
   answer").
3. **Auth-failure handling must use the existing readable-error path.** `taskClient.ts`'s
   `READABLE_ERRORS` already maps `missing_actor`/`missing_role`/`role_cannot_view_tasks` to
   readable text. FE.1C's implementation must route any `/tasks` failure on Overview through this
   same mapping (or the brief's own "This information isn't available for your role right now."
   copy) — never a raw error or a blank section.

Performance/RBAC risk is low and already anticipated by the brief's own degrade-to-empty-state
design; this recommendation only sharpens *how* to call `/tasks`, not whether to.

### Q2 — How should Overview reuse FE.1B safety posture?

**Recommendation: Option A, gated by an explicit merge-order precondition.** Reuse
`CalmSafetyPosture` (compact mode) directly — it is already a clean, reusable, presentational
component (`props: { data, compact }`) with no logic to duplicate; the Overview would call it exactly
as `SafetyStatusBar.tsx` already does, passing the same `getSafety()` result.

**Precondition, confirmed current as of this review:** FE.1B (PR #7,
`frontend/66ui4-fe1b-calm-safety`) has passed Claude Code review (Step 66UI.4-FE.1B-R, PASS) and
Product Owner UI validation (Step 66UI.4-FE.1B-V, `VISIBLE` with one accepted, non-blocking gap
around missing live safety fields — not a blocker to reuse) but **is not yet merged to `main`**.
`CalmSafetyPosture.tsx` does not exist on `main` until that merge happens. Therefore: **Codex FE.1C
implementation must not begin the System Posture section (and, practically, should not begin at all)
until PR #7 is merged.** This is not Option C ("defer until merged, then implement") as a separate
choice — it is the same technical reuse approach (Option A) with the merge-order dependency stated as
an explicit, checkable precondition in the Codex readiness boundary below, rather than left implicit.

Option B (a hand-rolled lightweight card avoiding the FE.1B import) is not recommended: it would
duplicate presentation logic FE.1B already owns, directly contradicting both this brief's own
"must not duplicate or re-specify the FE.1B component" rule and the merged
`calm-safety-posture-spec.md`'s ownership boundary.

### Q3 — How should `/operations/agent-executions` status map to product language?

Reviewed the actual response shape (`apps/orchestrator/src/operations.py:1499-1520`): each execution
row is `{id, task_id, agent, status, started_at, completed_at, created_at}`. Reviewed every SQL-level
reference to `agent_executions.status` in the codebase (`operations.py`, `progress.py`) — the **only**
literal status values ever queried or referenced are `'completed'` and `'failed'`. No `'running'`,
`'in_progress'`, `'queued'`, or `'pending'` value is written or read anywhere for this table today.

**Conservative mapping (recommended):**

| Raw `status` value | Product label | Confidence |
| --- | --- | --- |
| `"completed"` | "Completed" | Confirmed present in live queries |
| `"failed"` | "Needs review" | Confirmed present in live queries; "Needs review" chosen over a bare "Failed" since a failed agent execution is exactly the kind of thing this page's own design goal ("what needs my attention") should surface as actionable, not just informational |
| any other value, or missing/null | "Not reported" | **Do not invent** a "Running"/"Working"/"Queued" mapping — no evidence any such value is ever produced by the current data model |

This directly applies the lesson from Step 66UI.4-FE.1B-V (a live-data mismatch caused FE.1B's safety
indicator to show "Unavailable" more often than intended because assumed fields didn't exist):
Codex's FE.1C implementation must verify the actual live `/operations/agent-executions` payload
during implementation (not just this review's static code reading) before finalizing the mapping, and
must not hardcode a "running" state without confirming it is genuinely producible — an execution row
with `started_at` set and `completed_at` null might informally represent "in progress," but this
review found no explicit `status` value confirming that; Codex should check test-runtime live data
before deciding how (or whether) to represent that case, and default to "Not reported" if uncertain.

## 4. Design review (narrative)

- **Existing-data-only:** confirmed at every level — brief, IA, wireframe, data mapping, and Codex
  boundary all independently restate and enforce this constraint consistently; no drift found between
  documents.
- **Overview information hierarchy:** attention-first ordering (Needs-you → AI-team-activity →
  Current-work → System-posture → demoted-metrics → Future) is a clear, well-reasoned improvement
  over the current flat 12-card grid, and directly answers the "what needs me" question the current
  page cannot.
- **Needs-your-attention:** correctly sources from real task statuses (`clarification_needed`,
  `blocked`) with honest 66D placeholders for Deliveries/Approvals; explicitly separates the legacy
  `ready_for_review_packages_count` from the future 66D queue — this is the single most important
  honesty guarantee in the brief and it is handled correctly.
- **AI team activity:** existing-data-only via `/operations/agent-executions`; see Q3 above for the
  one refinement needed (conservative status mapping, verified against live data before shipping).
- **Current work snapshot:** sources from existing `/tasks`, sorted by `updated_at` — reasonable and
  low-risk; recommend Codex confirm the suggested count (5) and sort with the Product Owner per open
  question #4 (a preference, not a safety question).
- **System posture integration:** correctly designed to reuse FE.1B rather than duplicate it; see Q2.
- **Metrics demotion:** preserves all 12 existing cards, unchanged data, simply reordered — no loss of
  information, matches the Phase 1 `overview-dashboard-spec.md` intent exactly.
- **Placeholder strategy:** rigorous — explicit distinction between "placeholder" (feature doesn't
  exist) and "empty state" (feature exists, no data right now), exact required copy for each, and an
  explicit rule against ever showing a control on a placeholder.
- **Empty states/microcopy:** calm, product-warm, reassurance-first, consistent with the merged Phase
  1 `product-microcopy-guide.md` tone rules; zero/clear states are explicitly treated as good news,
  not an alarm — consistent with the FE.1B precedent.
- **Codex implementation boundary:** narrow and concrete — one file restructure
  (`ExecutiveOverview.tsx`) plus small new presentational components, all frontend-only, comparable
  in shape and risk to the already-shipped FE.1A/FE.1B stages.

## 5. Known gaps (non-blocking)

```text
- Q3's conservative status mapping should be re-verified against live /operations/agent-executions
  data during FE.1C implementation, not shipped from this review's static code reading alone (same
  category of gap that surfaced in FE.1B; flagging proactively here rather than after the fact).
- Recent-task count/sort (open question #4) is a Product Owner preference item, not a safety/
  architecture blocker; suggest 5 items sorted by updated_at desc as the brief proposes, pending
  Product Owner confirmation.
- FE.1C Codex implementation is sequenced behind FE.1B's merge (Q2) -- this is a real, checkable
  precondition, not merely a note; the Codex readiness boundary below states it as a gate.
```

No blocking gap. The brief is safe and implementable pending the FE.1B merge-order precondition.

## Statement

Review only. No runtime code changed by this document. No backend/API/database/workflow change. No
production/external action. Codex FE.1C implementation not authorized by this document. PR #8 not
merged.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
