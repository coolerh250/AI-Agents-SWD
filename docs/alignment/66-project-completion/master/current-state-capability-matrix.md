# Current-State Capability Matrix — Project Completion Master Plan

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

Consolidated from Claude Code's `current-state-assessment.md`, Claude Design's
`product-experience-roadmap.md`, and Codex's `frontend-current-state-map.md`/
`milestone-frontend-backlog.md` — cross-checked for consistency (all three agree; see
cross-partner-resolution-record.md).

## Completed capabilities (real, shipped, deployed, PO-validated)

```text
- Task assignment (Create Task, 66B) — real.
- Task workspace: Detail + Workroom, message thread (66C) — real, log-style presentation.
- Clarification: create/answer, task-scoped, safe wait state — real.
- Grouped IA shell (7 nav groups), product-language labels, Soon/Read-only/Evidence badges,
  Platform Ops compact density (FE.1D-S1) — real, merged, deployed, PO-validated PASS.
- Attention-first Overview: "Needs your attention" + AI team activity + current work (FE.1C) —
  real.
- Calm safety posture (FE.1B/FE.1B.1): dispatch_enabled/resume_dispatch_enabled surfaced as
  reassurance, not a raw field dump — real.
- TaskList query-param filter support (FE.1C.1) — real.
- FE.1D source-of-truth gap: design + technical-readiness + boundary all merged to main (Step
  66M0-SOT-RECONCILE-M) — real, documentation/contract only, not a runtime change.
```

## Test-validated-only capabilities (proven in test runtime, not production)

```text
- Every capability above: validated on the internal test runtime only. No production environment
  exists. production_executed_true_count = 0 across the project's entire history to date.
- Audit evidence pipeline (audit-service/audit-worker containers) — healthy in test; the one prior
  audit-chain-mismatch incident (Stage 42, seq 265288) was root-caused as a test-tamper artifact,
  not a real integrity failure, and is CLOSED.
- DLQ/retry-scheduler backend service — running and healthy in test; no product UI yet (M2).
- Approval-engine backend service — running in test; no product UI yet (M2).
```

## Staging evidence (historical, environment no longer exists)

```text
- The historical staging host (Step 64-65) was a more production-like environment while it
  existed (22 containers, real migrations applied) but used SECRET_PROVIDER=mock-vault,
  ALLOW_VAULT_DEV_MODE_FOR_STAGING=true, Postgres trust auth, and disabled/mocked live
  integrations. It was torn down as of Step 66A.0. Nothing about its prior existence is cited as
  current evidence of anything — it no longer exists to verify.
```

## Seeded-only evidence (not real production data, not counted toward any milestone)

```text
- The existing Platform Ops "Delivery Package" page is a read-only evidence view of demo/seeded
  mini-delivery-pilot data — explicitly NOT the real 66D delivery lifecycle (all three partners
  agree this must not be conflated or renamed into the real Delivery Inbox).
- Any seeded task/agent-execution record used in a Product Owner UI-validation walkthrough is
  real-shaped test data, not production evidence.
```

## Not-started capabilities

```text
- Step 66C.4 (Reminder / Expiry scheduler) — READY_TO_START, not started. /clarification-reminders
  is still a PlaceholderPage requiring "66C.4".
- Step 66D (Delivery Inbox, Delivery Detail, 6-action acceptance gate, Approvals P0, DLQ/Retry P0)
  — NOT STARTED. /delivery-inbox, /delivery-detail, /approvals, /dlq-retry are all PlaceholderPage
  requiring "66D".
- Step 66E (fixed AI team integration) — NOT STARTED.
- Team RBAC UI (Step 66S / Settings/Roles & Permissions) — locked on paper (66A.3 blueprint 6-role
  matrix), not implemented as product UI. /settings/roles-permissions is a placeholder requiring
  "66S".
- Step 66F (multi-channel intake: Slack/Telegram gateways) — NOT STARTED. Only Discord notify-first
  and Console+API intake exist today.
- Step 66G (Notifications + Action Center) — NOT STARTED. /notifications is a PlaceholderPage.
- Step 66H (controlled E2E pilot) — NOT STARTED.
- Real Kubernetes/Helm/ArgoCD production substrate — NOT ESTABLISHED (see security gaps below).
- Production auth/session/settings/adoption contracts — NOT DEFINED.
```

## Accepted gaps (explicitly non-blocking for current milestone, tracked for a later one)

```text
- FE.1D-S2 (microcopy/field-label cleanup, shared status-label module) — UNAUTHORIZED / NON-
  CRITICAL, absorbed into functional milestones per cross-partner-resolution-record.md §1.
- Admin Console SPA deep-link/hard-refresh fallback — accepted as a known backend/platform gap
  through every UI stage to date (docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md);
  must be remediated before M7 (a real production operator hitting a raw 404 on a bookmarked/
  refreshed deep link is a real support-burden risk).
- Two-way URL sync — excluded, no milestone currently requires it.
- TaskWorkroom.tsx body_hash relabel; broad evidence/raw-field relabel across Audit/Demo-Evidence
  pages — deferred (see deferred-work-register.md).
```

## Security gaps (real, open, must close before the milestone that depends on them)

```text
- Vault runs in ephemeral dev mode in every environment used so far — root token/unseal key
  regenerate on every restart, nothing persisted. No real production-grade secret store exists.
  Must close before M6 completion.
- PostgreSQL auth uses POSTGRES_HOST_AUTH_METHOD=trust in every environment used so far. Must close
  before M6 completion.
- Backup/DR: encryption_no_key, storage_not_off_host, schedule_dry_run_only, migration_down_gaps —
  open since at least Stage 38, never remediated, never on any stage's execution list since. Must
  close before M6 completion (all four, not a subset).
- Team RBAC is enforced today only via a test-harness mechanism (X-Task-Actor/X-Task-Role headers,
  gated by TASK_API_TEST_AUTH_ENABLED) — not the product's real identity/session/RBAC system. Real
  identity/session/CSRF (Step 66S) is M6/M7 scope per docs/decisions/66-team-rbac-milestone-
  ownership.md.
- Loose Record<string, unknown> typing on many Platform Ops operations responses masks backend
  changes silently — should be typed before M6 production hardening relies on them.
```

## Runtime/deployment gaps

```text
- No formal frontend route/API contract inventory exists yet (recommended as an M0/early-M1
  documentation slice, see next-executable-stage-sequence.md).
- No shared frontend data-fetching/mutation state pattern exists for multi-source, optimistic-
  update surfaces (needed before M4 Action Center; AsyncView alone is insufficient per Codex's
  analysis).
- No automated accessibility test suite exists.
- Real Kubernetes/ArgoCD production substrate: only a non-production "kind" cluster + non-
  production ArgoCD instance exist (Stage 60-63A dry-run rehearsal). No real cluster, no real sync,
  ever performed. This dry-run work is valuable REHEARSAL evidence for M6, explicitly NOT M6 itself
  — conflating the two is the single most likely misreading of this project's state (see
  cross-partner-resolution-record.md principle #10).
```

## What must NOT be written as production-complete (explicit, per all three partners)

```text
1. The Stage 60-63A "kind" dry-run cluster / non-production ArgoCD rehearsal.
2. Seeded/demo delivery-package evidence on the existing Platform Ops "Delivery Package" page.
3. Mock or seeded agent-execution records used for UI validation walkthroughs.
4. Any placeholder Admin Console page, regardless of how polished its badge/subtitle text is.
5. Any test-runtime deployment/validation record, regardless of how many checks it passed — these
   are test-environment evidence only, never production evidence.
```

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
