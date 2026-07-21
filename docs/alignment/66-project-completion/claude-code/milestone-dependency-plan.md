# Milestone Dependency Plan — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

## Canonical milestone order (unchanged, per stage prompt)

```text
M0 — Source of Truth and Runtime Reconciliation
M1 — Core Human–Agent Interaction Loop
M2 — Delivery and Acceptance Loop
M3 — AI Team Orchestration and Multi-role Control
M4 — Notifications, Action Center and Channels
M5 — Controlled End-to-End Pilot
M6 — Production Readiness and Platform Hardening
M7 — Production Rollout and Adoption

Critical path: M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7
FE.1D-S2 is NOT on the critical path.
```

No objection to this order from an architecture/backend perspective — it matches the dependency
reality found in the codebase (see §2). Recorded here per the instruction to state any disagreement
explicitly rather than silently rewrite: **none found.**

## 1. Mapping canonical milestones to this project's own step numbering

| Canonical | Project steps it corresponds to | Status |
| --- | --- | --- |
| M0 | Ongoing housekeeping: main/test-runtime reconciliation (already consistent, see current-state-assessment.md), stale host-checkout hygiene, decision on the 3 unmerged FE.1D branches | Mostly satisfied; one small hygiene action recommended |
| M1 | 66B (Task Assignment UI + Task API), 66C (Agent Workroom), 66C.4 (Reminder/Expiry) | 66B, 66C complete; **66C.4 not started** |
| M2 | 66D (Delivery Inbox, 6-action acceptance gate, Approvals P0, DLQ/Retry P0) | **Not started** |
| M3 | 66E (fixed AI team integration), Team RBAC UI (Step 66S) | **Not started** |
| M4 | 66F (multi-channel intake: Slack/Telegram), 66G (Notifications + Action Center) | **Not started** |
| M5 | 66H (controlled E2E pilot) | **Not started** |
| M6 | Real Kubernetes/Helm/ArgoCD production substrate, real secret store, real backup/DR remediation, production-readiness gate execution (building on the Stage 60–63A dry-run rehearsals) | **Not started** (dry-run rehearsal only) |
| M7 | Production rollout, adoption, operator training/handoff | **Not started** |
| (parallel, not on critical path) | FE.1D-S2 (Slice 2 microcopy/field-label cleanup), any further Admin Console cosmetic polish | Boundary/slicing plan exist; not authorized |

## 2. Dependency graph (why the order is correct)

```text
M0 (source-of-truth reconciliation)
  -> required before any milestone, because every later milestone's "what exists today" claim
     depends on main/test-runtime state being trustworthy. Already effectively satisfied; the one
     residual item (stale host reference checkout) is non-blocking but should be closed before M2
     starts touching backend delivery-lifecycle code on that same host.

M1 (Core Human-Agent Interaction Loop: task assignment, workroom, clarification, reminder/expiry)
  -> depends on M0.
  -> is the foundation for M2: Delivery cannot be "accepted" until a task has completed its
     interaction loop (intake -> assignment -> execution -> clarification -> completion). The
     Task API's existing status enum already encodes this (delivery_ready, changes_requested,
     qa_rerun_requested are downstream of the interaction loop, not independent of it).
  -> 66C.4 (Reminder/Expiry) is the one remaining piece of M1. It is backend-light (a scheduler +
     existing clarification_expired status transition, already modeled in TASK_STATUSES) and
     frontend-light (a real Reminder/Expiry page replacing today's placeholder). It has no
     dependency on 66D and should not wait for it.

M2 (Delivery and Acceptance Loop: 66D)
  -> depends on M1 being real (an acceptance gate is meaningless without real task completion
     signal to accept).
  -> requires a genuine data-model extension: delivery packages, acceptance-gate decisions, and
     the Approvals/DLQ product UI need backend models and endpoints that do not exist yet
     (the existing Platform Ops "Delivery Package" page is a read-only evidence view of the
     mini-delivery-pilot demo data, not the real 66D delivery lifecycle).
  -> should NOT begin its UI design as pixel-final before the data model/API contract is decided
     -- see the explicit question in alignment-statement.md.

M3 (AI Team Orchestration and Multi-role Control: 66E, Team RBAC)
  -> depends on M2's delivery lifecycle existing, because "multi-role control" is largely about who
     may accept/reject/escalate a delivery, and the fixed-team integration (66E) assumes tasks flow
     all the way to delivery.
  -> Team RBAC UI (Settings/Roles & Permissions) could technically be built earlier since the
     6-role matrix is already locked (Q1, 66A.3), but doing so before M2 would produce a
     permissions UI for actions (accept/reject/escalate) that do not exist yet -- low value,
     recommend sequencing it inside M3 alongside 66E rather than pulling it forward.

M4 (Notifications, Action Center and Channels: 66F, 66G)
  -> depends on M2/M3 existing, because a unified Action Center's primary queues (Approvals,
     DLQ/Retry, Delivery review) are M2/M3 artifacts; building the Action Center shell before those
     queues have real data would produce another placeholder-in-disguise.
  -> multi-channel intake (66F, Slack/Telegram) has no hard dependency on M2/M3 beyond needing a
     stable Task API to submit into -- it is deferrable within M4 without reordering, since
     Discord notify-first already proves the pattern.

M5 (Controlled E2E Pilot: 66H)
  -> depends on M1-M4 all being real, since a pilot's entire value is exercising the full loop
     (assign -> execute -> clarify -> deliver -> accept -> notify) with a real operator.

M6 (Production Readiness and Platform Hardening)
  -> intentionally placed AFTER the pilot, not before: hardening a substrate before you know the
     pilot didn't reveal a design flaw in the product loop wastes the hardening effort. This
     matches this project's own established caution (the Stage 60-63A dry-run rehearsals were
     explicitly kept non-production and reversible for exactly this reason).
  -> requires: real Kubernetes/Helm/ArgoCD production cluster (not the "kind" sandbox), real
     secret store (Vault HA/auto-unseal or a cloud KMS), backup/DR remediation
     (encryption_no_key, storage_not_off_host, schedule_dry_run_only, migration_down_gaps all
     closed), Postgres auth hardened away from `trust`.

M7 (Production Rollout and Adoption)
  -> depends on M6. Standard last step: cutover, operator training, monitoring handoff.
```

## 3. Backend / API / data-model requirements per milestone

```text
M0: none beyond documentation/hygiene -- no schema change.

M1 (66C.4 remainder): a scheduler process (or an existing retry-scheduler-style service extended)
  to transition clarification_needed tasks to clarification_expired after the locked 24h/72h
  timeout; a notification hook (can reuse the existing notification-worker) to fire the reminder
  at 24h. No new task-status values needed -- clarification_expired already exists in
  TASK_STATUSES. Requires: confirming whether the timeout is enforced by a poller or a Redis-
  Streams delayed-message pattern (the existing agent pipeline already uses Streams + consumer
  groups, so a delayed-message pattern would be consistent with existing architecture rather than
  introducing a new mechanism).

M2 (66D): requires a genuine new data model for delivery packages tied to real tasks (the current
  DeliveryPackage/mini-delivery-pilot models are demo/evidence-only, per the delivery-inbox-
  blueprint.md's own scope), plus:
  - New API endpoints for the 6-action acceptance gate (Accept/Reject/Request-Changes/Re-run-QA/
    Escalate/Archive) -- each is a state transition on a task/delivery record, ideally implemented
    as narrowly-scoped POST endpoints on the existing Task API surface rather than a new service.
  - Approvals P0 and DLQ/Retry P0 UI need to read from the EXISTING approval-engine and
    retry-scheduler services' real state (both already run and already have real backend logic;
    this is a UI-and-thin-API gap, not a backend build-from-scratch gap).
  - RBAC scoping for who may Accept/Reject/Escalate must reuse the existing TASK_ROLES model
    (reviewer_approver, pm_engineering_lead) rather than inventing new roles.

M3 (66E, Team RBAC): fixed-team integration is largely a data-model/assignment-logic change (task
  routing to the fixed Software Delivery Team's agent roster) rather than a new service. Team RBAC
  UI needs no new backend beyond exposing the already-defined TASK_ROLES + the 66A.3 blueprint's
  6-role matrix through a real endpoint (today there is none -- Settings/Roles & Permissions has
  nothing to call).

M4 (66F, 66G): Slack/Telegram gateways are new services, structurally identical to the existing
  discord-gateway (same integration pattern, same governance posture -- external_send disabled by
  default, explicit authorization required before any real external send). Action Center needs a
  read aggregation API across Approvals/DLQ/Delivery-review queues (a composition endpoint, not a
  new domain model).

M5 (66H): no new backend surface expected -- a pilot exercises what M1-M4 already built. Any gap
  found during the pilot becomes new backend scope, discovered rather than pre-planned here.

M6: no product-feature backend change -- this milestone is entirely platform/infrastructure
  (Kubernetes manifests/Helm charts, ArgoCD application definitions targeting a REAL cluster,
  secret-store migration, backup/DR remediation, Postgres auth hardening). Zero product API
  surface change is required for M6 itself.

M7: no backend change -- rollout/operational milestone.
```

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
