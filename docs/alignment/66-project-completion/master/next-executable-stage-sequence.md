# Next Executable Stage Sequence — Project Completion Master Plan

> **Planning/recommendation document only. This document authorizes nothing itself. No stage
> listed below is started by this document. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

## Stage 1 — Step 66C.4-P: Reminder / Expiry / Controlled Resume Planning

```text
Owner: Claude Code.
Prerequisite: M0 CLOSED (satisfied).
Expected artifact: scheduler-mechanism decision (poller vs. Redis-Streams delayed message),
  confirmation that no new task-status value is needed (clarification_expired already exists),
  and a Codex frontend-implementation boundary for the real /clarification-reminders page,
  mirroring the established FE.1x contract pattern.
Stage gate: Architecture Direction Gate (Claude Code self-certifies, no merge/deploy this stage).
PO decision required: none to plan; Product Owner authorization required before Stage 2 begins.
Runtime impact: none (planning/documentation only).
```

## Stage 2 — Step 66C.4: Reminder / Expiry Implementation Lifecycle

Corrected per Step 66ALIGN.2-R1 (see `ownership-remediation-record.md`): Step 66C.4 is a
Claude-Code-primary-owned backend/workflow stage, not a Codex-owned implementation stage. Its own
future sub-stage names may be refined during 66C.4-P, but the ownership boundary below is binding.

```text
Owner: Claude Code (primary implementation owner — scheduler, reminder/expiry state transitions,
  controlled resume, backend/API/DB/workflow, audit/safety enforcement, notification event
  production, integration review, preview deployment/runtime validation); Codex (only the
  explicitly authorized frontend slice); Claude Design (only if new UX states require
  clarification).
Prerequisite: Stage 1 complete; explicit Product Owner authorization to implement.
Expected artifact (canonical sub-stage sequence):
  66C.4-BE (Claude Code backend/workflow implementation) -> 66C.4-BE-R (Claude Code technical
  review/gate) -> 66C.4-FE (Codex frontend slice, only if explicitly authorized) -> 66C.4-VP
  (test-runtime preview) -> 66C.4-POV (Product Owner validation) -> 66C.4-MD (merge/deploy merged
  main).
Stage gate: Architecture Direction Gate, Implementation Efficiency Gate, Security/Governance Gate,
  Product Owner Validation Gate, Merge Gate, Deployment Gate, Post-deployment Review Gate — all as
  previously exercised for backend-owned stages in this project.
PO decision required: backend implementation authorization (start), frontend-slice implementation
  authorization (if/when Codex work is needed), merge authorization, deployment authorization —
  separate, scoped authorizations, per this project's established pattern.
Runtime impact: test-runtime backend (scheduler mechanism) + test-runtime frontend (only the
  authorized slice); completes M1.
```

## Step 66C.4 status update (added at Step 66C.4-P-M)

```text
Step 66C.4 contract is now canonical: the Reminder / Expiry / Controlled Resume planning/contract
  set and the six approved Product Owner decisions were merged to main at Step 66C.4-P-M (merge
  commit e109189), per docs/decisions/66c4-reminder-expiry-controlled-resume-product-decisions.md
  and docs/contracts/66c4-reminder-expiry-controlled-resume/contract-source-of-truth-record.md.
Step 66C.4-BE1 (data model / migration / disabled outbox foundation) is now MERGED at Step
  66C.4-BE1-M (merge commit 8080141, PR #17, reviewed head 0bb9944), after an independent review
  (REMEDIATION_REQUIRED), a scoped remediation, and an independent closure review that recorded the
  final BE1_TECHNICAL_VERDICT: PASS. BE1 status is MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED:
  migration 031 is present in the repository but NOT applied to any shared runtime, the outbox
  foundation is disabled (no live producer, no relay, no scheduler), and the "BE1 Runtime
  Compatibility Gate" remains in force. See be1-merge-record.md, be1-technical-closure-record.md and
  be1-source-of-truth-record.md.
Step 66C.4-BE2 (reminder/expiry lifecycle poller + transactional outbox relay) is now MERGED at Step
  66C.4-BE2-M (merge commit 161f4f3, PR #18, reviewed head c2677f7), after an independent review
  (BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED for B-1 expiry parent-task consistency and B-2
  unbounded Redis publish), a scoped remediation at Step 66C.4-BE2-R1 (c2677f7), and an independent
  closure review at Step 66C.4-BE2-R1-R (b22e4c7) that recorded the final BE2_TECHNICAL_VERDICT:
  PASS. BE2 status is MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED / NO PRODUCER
  CUTOVER: the poller and relay exist in the repository but are wired into no shared runtime,
  migration 031 is NOT applied to any shared database, and the Runtime Compatibility Gate remains in
  force. See be2-merge-and-source-of-truth-record.md.
Step 66C.4-BE3 planning is now MERGED at Step 66C.4-BE3-P-M (merge commit 90fc765, PR #19, reviewed
  head 81f38d2): the operator-controlled resume + replay authorization contract, RBAC permission
  matrix (reusing the six canonical TASK_ROLES), resume/replay state machines, durable authorization
  model, API/event contract, security/threat model, runtime activation gate, and BE3-A/B/C/R/M
  implementation slicing are canonical source of truth on main
  (docs/contracts/66c4-reminder-expiry-controlled-resume/be3-*.md;
  STEP66C4_BE3_PLANNING_MERGE_VERIFY: PASS). Step 66C.4-BE3-P = MERGED / PRODUCT CONTRACT READY. No
  backend/API/migration/frontend/deployment code entered main.
Step 66C.4-BE3-A (authorization model, repository and policy enforcement — the first implementation
  slice) is the NEXT CANDIDATE but is NOT AUTHORIZED and NOT STARTED; it requires a separate,
  explicit Product Owner authorization and, before any runtime producer cutover, the
  relay/retry/DLQ/observability/rollback paths to be simultaneously available per the Runtime
  Compatibility Gate. The BE3 replay-authorization prerequisite (operator RBAC + two-person human
  authorization + replay audit evidence + authorization-outcome persistence) is bound before any
  operator-facing replay exposure; replay_dead remains internal-only.
```

This status update only records the two facts above. It does NOT change the M0-M7 milestone order
or any milestone scope, and Stage 2's ownership boundary (Claude Code primary, Codex frontend-slice-
only) is unchanged.

## Stage 3 — Step 66D-ARCH: Delivery and Acceptance Data Model / API Contract Freeze

```text
Owner: Claude Code (architecture-only, no implementation).
Prerequisite: Stage 2 complete (M1 closed).
Expected artifact: the frozen data model for delivery packages tied to real tasks, the 6-action
  acceptance-gate endpoint contract, and RBAC scoping for who may Accept/Reject/Escalate — produced
  BEFORE any UI is designed against it (the single highest-priority sequencing rule in this Master
  Plan).
Stage gate: Architecture Direction Gate.
PO decision required: acceptance of the frozen contract before 66D-DESIGN begins.
Runtime impact: none (architecture/contract documentation only).
```

## Stage 4 — Step 66D-DESIGN: Delivery Inbox / Detail / Acceptance UX

```text
Owner: Claude Design (design), Claude Code (review).
Prerequisite: Stage 3 complete and Product-Owner-accepted.
Expected artifact: Delivery Inbox, Delivery Detail, and the four-action decision-gate UX design,
  built strictly against the frozen 66D-ARCH contract — following the design-collaboration/
  SKILL.md chain (design -> Claude Code review -> Product Owner decision -> Codex authorization)
  exactly as it was applied for FE.1C/FE.1D, now to the value-adding M2 milestone.
Stage gate: Design Review Gate.
PO decision required: direction acceptance before Codex implementation authorization.
Runtime impact: none (design documentation only).
```

## Stage 5 — Step 66D implementation slices

```text
Owner: Codex (implementation), Claude Code (review/deploy).
Prerequisite: Stage 4 complete and Product-Owner-authorized for implementation.
Expected artifact: the first bounded, reviewable Codex implementation slice — Delivery Inbox,
  Approvals P0, or DLQ/Retry P0, whichever the Product Owner judges highest value first — scoped
  no more broadly than the FE.1D-S1 precedent (one slice at a time, small-PR discipline).
Stage gate: Implementation Efficiency Gate, Security/Governance Gate (server-side RBAC
  non-negotiable), Product Owner Validation Gate, Merge Gate, Deployment Gate.
PO decision required: implementation authorization, merge authorization, deployment authorization —
  per slice.
Runtime impact: test-runtime frontend + new backend endpoints/data model per the frozen contract;
  produces the first real M2 deliverable.
```

## FE.1D-S2 disposition (explicit, per this sequence)

FE.1D-S2 is not listed as a standalone stage in this sequence. Its content is absorbed into Stages
1-5 and later M3/M4/M6 work wherever it naturally touches the same surface (see
deferred-work-register.md #1 and cross-partner-resolution-record.md §1). It remains available for
a standalone authorization if the Product Owner explicitly wants it for its own sake (e.g. an
imminent stakeholder demo), but it is not on this critical-path sequence.

## Explicitly NOT started by this stage (66ALIGN.2-CONSOLIDATE)

```text
None of Stages 1-5 above is started, planned in detail beyond this summary, or implemented by this
Master-Plan-consolidation stage. Step 66C.4-P specifically is not started (per this stage's own
hard constraint).
```

## Statement

Planning/recommendation document only. This document authorizes nothing itself. No stage listed
above is started by this document. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
