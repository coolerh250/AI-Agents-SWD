# Implementation Stage Slicing Plan — Step 66C.4-P

> **Planning document only. This document proposes a stage sequence for future, separately
> authorized execution — no stage listed below is started by this document.**

This slicing follows exactly the canonical Step 66C.4 sequence already recorded in the Master
Plan's `role-ownership-matrix.md` (corrected in Step 66ALIGN.2-R1):
`66C.4-P -> 66C.4-BE -> 66C.4-BE-R -> 66C.4-FE -> 66C.4-VP -> 66C.4-POV -> 66C.4-MD`, expanded here
into the finer-grained slices this stage's own prompt requests (`66C.4-BE1/BE2/BE3` as sub-slices
of `66C.4-BE`), plus two additional gate stages (`66C.4-DESIGN` conditional, `66C.4-E2E`) this
planning stage recommends adding for safety/clarity. **No deviation from the ownership boundary
established in Step 66ALIGN.2-R1 is proposed** — Claude Code remains the primary owner of every
backend slice.

## 66C.4-BE1 — Data model / migration / lifecycle + atomicity foundation

```text
Owner: Claude Code.
Scope (corrected in Step 66C.4-P-R1 to include the authoritative-deadline predicates and the
  durable-outbox atomicity foundation):
  - the migration proposed in data-model-contract.md: 6 new lifecycle columns, 2 partial indexes,
    1 CHECK constraint on operator_clarification_requests, AND the new clarification_lifecycle_outbox
    table (durable outbox / pending-event foundation).
  - the authoritative-deadline CAS predicates: the answer-claim gains `AND due_at > now()` and the
    lifecycle-claim guards are defined so the DEADLINE (not the scheduler) closes the answer window
    (lifecycle-and-time-contract.md §7.3A).
  - lifecycle CAS operations (reminder-claim, expiry-claim, resume-claims) as store helpers, each
    writing its state column(s) AND an outbox row in the SAME transaction (api-and-event-contract.md
    §11.3) -- the audit/event consistency foundation.
  - NO scheduler activation yet, NO resume dispatch yet, no new endpoint yet.
Prerequisite: this stage (66C.4-P / 66C.4-P-R1) reviewed and accepted by the Product Owner; the
  "no new task-status value" default confirmed (i.e. no conflicting PO decision from
  product-owner-decision-checklist.md).
Allowed paths: migrations/**, shared/sdk/tasks/workroom_store.py (claim helpers + outbox insert, no
  API route change yet).
Forbidden paths/actions: apps/orchestrator/src/workroom_api.py (no new route yet), apps/admin-
  console/** (no frontend change), no scheduler process, no resume dispatch, no deployment.
Artifacts: the migration file (columns + indexes + CHECK + outbox table), the CAS/outbox store
  helpers, an updated data-model-contract implementation record.
Tests: migration up/down test, column/table-existence test, CHECK-constraint test, answer-claim
  deadline-predicate test (answer at/after due_at rejected), state+outbox same-transaction
  atomicity test (both commit or neither).
Stage gate: Architecture Direction Gate + Security/Governance Gate (Claude Code self-certifies;
  migration reviewed for rollback safety per data-model-contract.md).
PO authorization required: YES — explicit authorization to create the migration (this stage,
  66C.4-P/-P-R1, only proposes it).
Deployment impact: test-runtime only, once authorized in a later deploy step; this slice itself
  does not deploy.
Rollback condition: any CHECK-constraint violation on existing data (not expected — all new
  columns are nullable with no default) halts and reverts.
```

## 66C.4-BE2 — Reminder and expiry scheduler

```text
Owner: Claude Code.
Scope (corrected in Step 66C.4-P-R1):
  - the dedicated clarification-timeout worker (new service, per scheduler-architecture-decision.md
    Option 2) and its poll/claim logic for both reminder and expiry transitions (each claim writes
    its outbox row in the same transaction, per BE1's foundation).
  - the outbox RELAY: idempotent publication of 'pending' outbox rows to audit + internal event bus
    (at-least-once + idempotent via deterministic idempotency keys; never exactly-once), marking
    rows 'published'.
  - retry + DLQ: bounded relay retries, then mark 'dead' and route to the existing
    stream.deadletter / retry-scheduler DLQ.
  - metrics + health: poll_cycle_*, reminder/expiry claim counts, outbox_pending_depth,
    outbox_dead_total, and the "last successful poll cycle" liveness gauge
    (observability-and-audit-plan.md).
  - the new audit event types (clarification_reminder_sent, clarification_expired).
Prerequisite: 66C.4-BE1 merged and deployed to test runtime.
Allowed paths: a new apps/clarification-scheduler/** service directory, shared/sdk/tasks/
  workroom_store.py (new claim methods), shared/sdk/tasks/audit_events.py (new event types),
  shared/sdk/event_bus/** (event publishing only, no new bus infrastructure).
Forbidden paths/actions: no resume-related code yet (that's 66C.4-BE3), no frontend, no external
  notification channel, no workflow dispatch.
Artifacts: the new service source, its own README/health-check, updated audit-events allowlist.
Tests: unit tests for claim queries (reminder/expiry) including the idempotency/duplicate-
  prevention cases from race-condition-and-failure-analysis.md scenarios 1-5, 12-15; integration
  test exercising the full poll-cycle against a real (test) Postgres.
Stage gate: Architecture Direction Gate, Implementation Efficiency Gate, Security/Governance Gate.
PO authorization required: YES — explicit authorization to build and deploy this service.
Deployment impact: a new container in the test-runtime compose stack; production_executed_true_
  count unaffected (still 0).
Rollback condition: any observed duplicate reminder/expiry (should be impossible by CAS design,
  but if observed) halts and reverts to the previous state.
```

## 66C.4-BE3 — Controlled resume, audit and recovery

```text
Owner: Claude Code.
Scope (corrected in Step 66C.4-P-R1 to reflect the full binding resume state model):
  - resume ELIGIBILITY derivation (set in the answer transaction when the task is non-terminal).
  - explicit resume REQUEST (Option A) — resume-request endpoint + RBAC functions from
    rbac-and-safety-contract.md; resume_requested_at/_by via CAS.
  - policy AUTHORIZATION — the automated policy/safety check (re-evaluates §2 conditions at
    authorization time); resume_authorized_at via CAS.
  - durable resume EVENT (dispatch) — the Dispatcher publishes a durable outbox resume event.
    Built here but GATED/DISABLED-BY-DEFAULT: dispatch_enabled remains false (as it is today), so no
    real production workflow is affected until a SEPARATE authorization enables it.
  - orchestrator resume CONFIRMATION — the confirmation handler that establishes WORKFLOW_RESUMED
    (distinct from dispatched); the task's own status is the source of truth for "resumed."
  - RECOVERY and AUDIT — outbox relay + DLQ for resume events (scenarios 11, 17), and the resume
    audit events (clarification_resume_eligible/requested/authorized/dispatched, workflow_resumed).
  Request, authorized, dispatched, and workflow-resumed are FOUR separate transitions; an operator
  request never equals any later state (controlled-resume-contract.md binding state model).
Prerequisite: 66C.4-BE2 merged and deployed; explicit PO decision on Option A vs. B received.
Allowed paths: apps/orchestrator/src/workroom_api.py (new GET/POST routes per api-and-event-
  contract.md), shared/sdk/tasks/workroom_rbac.py (new capability functions), shared/sdk/tasks/
  workroom_store.py (resume-claim methods + resume outbox events), the orchestrator resume-
  confirmation handler.
Forbidden paths/actions: no ENABLING of real production-effecting dispatch (dispatch_enabled stays
  false; enabling is a separate explicit authorization); no dispatch against a production-effect
  task under any circumstance; no frontend; no external notification.
Artifacts: the new endpoints, RBAC functions, resume state helpers, gated dispatch + confirmation
  handlers, and their own contract-compliance test suite.
Tests: unit tests for eligibility/authorization logic including race-condition-and-failure-
  analysis.md scenarios 6-11, 16, 17; tests that request != authorized != dispatched != resumed
  (no transition is collapsed); dispatch-disabled-by-default test (no real workflow effect); API
  tests for the new endpoints' RBAC/error-code behavior.
Stage gate: Architecture Direction Gate, Implementation Efficiency Gate, Security/Governance Gate
  (server-side RBAC non-negotiable, per rbac-and-safety-contract.md).
PO authorization required: YES.
Deployment impact: test-runtime only.
Rollback condition: any client-side-only RBAC gate found in review halts and reverts (matches the
  Master Plan's own standing rollback condition for M2/M3 gates).
```

## 66C.4-BE-R — Independent technical/security review

```text
Owner: Claude Code (self-review per this project's established pattern — Claude Code both
  implements and reviews backend work, per role-responsibility-matrix.md).
Scope: independent re-verification of 66C.4-BE1/BE2/BE3's own claims (re-run tests in a fresh
  worktree, confirm no forbidden path touched, confirm the race-condition scenarios are actually
  covered by real tests, not just documented).
Prerequisite: 66C.4-BE1/BE2/BE3 complete.
Stage gate: Security/Governance Gate.
PO authorization required: NO (review is Claude Code's own standing responsibility, not a
  separately-authorized action — matches every prior FE.1x review stage's pattern).
Deployment impact: none (review only).
```

## 66C.4-DESIGN — Only if new UX-state design is required

```text
Owner: Claude Design.
Scope: ONLY the new UX states identified in frontend-ux-boundary.md that genuinely need design
  beyond what core-loop-experience-definition.md already covers (per this stage's own conditional
  framing — this slice may be skipped entirely if the Product Owner/Claude Code determine the
  existing design language already suffices).
Prerequisite: 66C.4-BE3 complete (so the design work is against a real, frozen contract, not a
  moving target); explicit Product Owner authorization for Claude Design to begin.
PO authorization required: YES, and explicit — this document does not authorize it.
Deployment impact: none (design documentation only).
```

## 66C.4-FE — Explicitly authorized frontend slice

```text
Owner: Codex.
Scope: exactly the frontend items in frontend-ux-boundary.md's "Codex potential future scope"
  section, built against the frozen 66C.4-BE1/BE2/BE3 contracts (and 66C.4-DESIGN's output, if
  that slice ran).
Prerequisite: 66C.4-BE-R passed; explicit, separate Product Owner authorization for Codex to begin
  (per frontend-implementation/SKILL.md's authorization gate — a design brief/contract existing is
  not itself an authorization).
Allowed paths: apps/admin-console/src/** (Workroom-area components and the /clarification-
  reminders route only).
Forbidden paths/actions: no backend/API/DB/workflow change, no new endpoint invention beyond what
  66C.4-BE1/BE2/BE3 already built.
Artifacts: updated components, frontend tests.
Tests: extended WorkroomUI/WorkroomAuditVisibility-style tests plus new lifecycle/resume-state
  tests.
Stage gate: Implementation Efficiency Gate (Claude Code reviews Codex's PR).
PO authorization required: YES, explicit, separate from the backend authorizations.
Deployment impact: test-runtime frontend only.
```

## 66C.4-E2E — Backend/frontend integration validation

```text
Owner: Claude Code.
Scope: full-loop test of a real clarification through create -> reminder -> (or) answer -> expiry
  -> resume-eligibility -> (if Option A) resume-request, on the test runtime, confirming no
  backend/frontend contract drift occurred across the separately-executed slices above.
Prerequisite: 66C.4-FE complete.
Stage gate: Security/Governance Gate.
PO authorization required: NO (technical validation, matches this project's established pattern of
  Claude-Code-owned integration checks before PO validation).
Deployment impact: test-runtime only, read/write against test data.
```

## 66C.4-VP — Test-runtime preview

```text
Owner: Claude Code.
Scope: deploy the full, merged 66C.4 change set to the test runtime for Product Owner UI
  validation, exactly matching the established FE.1C/FE.1D-S1 preview-deployment pattern.
Prerequisite: 66C.4-E2E passed.
PO authorization required: YES (deployment authorization, scoped to test runtime only, per the
  standing Deployment Gate rule).
Deployment impact: test-runtime deployment.
```

## 66C.4-POV — Product Owner validation

```text
Owner: Product Owner.
Scope: the observable checklist from test-and-validation-plan.md's Product Owner Validation
  section.
Prerequisite: 66C.4-VP complete.
PO authorization required: this IS the Product Owner's own gate (VISIBLE/NOT_VISIBLE/
  PARTIAL_WITH_GAPS, per the established pattern).
Deployment impact: none (validation only).
```

## 66C.4-MD — Merge and deploy merged main

```text
Owner: Claude Code.
Scope: merge all 66C.4-BE*/FE/DESIGN branches to main in chronological order (matching the
  established multi-branch merge pattern from Step 66UI.4-FE.1D-S1-MD), deploy merged main to the
  test runtime, close out Step 66C.4 as COMPLETE/SHIPPED.
Prerequisite: 66C.4-POV = PASS or PASS_WITH_ACCEPTED_GAPS.
PO authorization required: YES (merge authorization + deployment authorization, two separate
  scoped authorizations per this project's standing pattern).
Deployment impact: test-runtime deployment of merged main.
Rollback condition: standard git revert, per this project's established zero-risk rollback pattern
  for documentation/contract merges; for the runtime deployment itself, the established backup-
  before-swap pattern (per every prior FE.1x/deployment stage) applies unchanged.
```

## If a different slicing were proposed instead

No different slicing is proposed. This exact 10-stage sequence (7 canonical + 3 stage-prompt-
requested sub-slices) is adopted directly because it is the smallest set of independently
reviewable, independently rollback-able units that respects the ownership boundary from Step
66ALIGN.2-R1 (Claude Code primary for all backend work, Codex limited to one clearly-scoped
frontend slice) and the established FE.1x precedent (one bounded PR at a time, never a "big bang"
merge).

## Statement

Planning document only. This document proposes a stage sequence for future, separately authorized
execution — no stage listed above is started by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
