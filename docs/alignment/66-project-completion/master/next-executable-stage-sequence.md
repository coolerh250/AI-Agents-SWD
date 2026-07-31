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
Step 66C.4-BE3-A (durable authorization model, repository and policy enforcement — the first
  implementation slice) is IMPLEMENTED on branch feature/66c4-be3-resume-replay-authorization (Draft
  PR, NOT FOR MERGE): migration 032 (resume_replay_authorizations, additive), the authorization
  model/repository/policy/service, with single-use/time-bound/state-version-bound/revocable
  semantics, two-person replay control, service-identity consume-only, team/project isolation, and
  the production-approval gate (STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS; 14 real-PG
  tests). NO resume/replay execution, NO public endpoint, NO dead-outbox replay call, NO shared
  activation/deployment; migration 032 NOT applied to any shared DB.
Step 66C.4-BE3-B (operator-controlled resume request/authorize/gated execution command) is
  IMPLEMENTED on the same branch (Draft PR #20, NOT FOR MERGE): migration 033 (resume_requests,
  additive), the resume request model/repository/service, and the /operations/resume-requests API
  (DISABLED-BY-DEFAULT via BE3_RESUME_API_ENABLED). DB-authoritative eligibility under row locks;
  resume authorized ONLY by the policy/safety authority (a server-side capability, never client
  input; an operator cannot self-authorize); Service-Identity-only, BE3_RESUME_COMMAND_ENABLED-gated
  execution preparation that consumes the single-use authorization and writes a single durable
  resume.execution_requested outbox command (command_id = the outbox row id); outbox failure rolls
  back the consume; production gate intact; exact null-safe NOT NULL scope
  (STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY: PASS; 22 real-PG tests, 208 regression). NO orchestrator
  call, NO resume execution, NO replay_dead, NO shared migration/deployment/activation.
Step 66C.4-BE3-C (two-person-controlled dead-event replay) is IMPLEMENTED on the same branch (Draft
  PR #20, NOT FOR MERGE): migration 034 (replay_requests, additive), the replay request
  model/repository/service, and the /operations/replay-requests API (DISABLED-BY-DEFAULT via
  BE3_REPLAY_API_ENABLED). Reuses the BE3-A durable authorization UNCHANGED with action_type='replay'
  (requester != approver two-person control via the existing policy + DB constraint); a NEW
  transaction-aware replay_dead_row adapter (the existing ClarificationOutboxRelay.replay_dead always
  owns its own transaction and cannot compose with an authorization consume); a dead-episode
  resource_state_version composite (dead_at:attempts, no new column); mandatory destination readiness
  (default provider never reports ready -- no consumer exists for either destination);
  server-derived production-effect (never client-trusted); bounded server-side rate limiting
  (STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS; 27 real-PG + 5 DB-less tests, 253 regression). A
  request_authorization savepoint composability fix was required (replay has no pre-authorization
  claim gate like resume's clarification CAS). NO real replay_dead call in any shared runtime, NO
  event publish, NO shared migration/deployment/activation, NO public execute endpoint.
BE3-A + BE3-B + BE3-C + the combined independent BE3-R review (BE3_TECHNICAL_VERDICT: PASS, two
  Medium findings M-1/L-1 recorded as activation preconditions) + BE3-R1/R2 remediation (M-1, L-1,
  R2-1) + the focused closure by the ORIGINAL independent reviewer (STEP66C4_BE3_R1_R2_FOCUSED_
  CLOSURE_VERIFY: PASS, final BE3_TECHNICAL_VERDICT: PASS) are now MERGED to main at Step
  66C.4-BE3-M (merge commit 284d706, PR #20, reviewed head 5a413bf; see
  be3-merge-and-source-of-truth-record.md and step66c4-be3-merge-verification-record.md). BE3
  status is MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED / NO SHARED MIGRATION:
  migrations 032-035 are present in the repository but NOT applied to any shared database, all four
  BE3 feature gates (BE3_RESUME_API_ENABLED, BE3_RESUME_COMMAND_ENABLED, BE3_REPLAY_API_ENABLED,
  BE3_REPLAY_EXECUTION_ENABLED) remain default-false, replay_dead remains internal-only, and the
  Runtime Compatibility Gate plus the 11-item activation gate (be3-runtime-activation-gate.md)
  remain in force before any activation. Runtime activation READINESS PLANNING is now complete at
  Step 66C.4-BE3-RA-P (planning/inventory only; see be3-runtime-activation-readiness-plan.md,
  be3-runtime-activation-stage-sequence.md): all 11 gate items are classified, the single most
  consequential finding is that no runtime-callable caller or consumer exists yet for either
  resume-command or replay-execution (both are internal-service-only functions with zero production
  call sites), and a proposed 12-stage sequence (RA-1..RA-12) is handed off but NOT authorized or
  started. Step 66C.4-BE3-RA-1A (Isolated Migration Rehearsal and Rollback Proof) is now REHEARSED /
  SELF-VERIFIED (see be3-ra1-migration-rehearsal-and-rollback-plan.md,
  step66c4-be3-ra1-migration-rehearsal-evidence.md): migrations 031-035 rehearsed stepwise on
  isolated PostgreSQL 16 with existing-data preservation, failure injection, duplicate/out-of-order/
  concurrent-migrator coverage, pre-activation down rehearsal, reapply/fingerprint equality, and a
  non-destructive post-write rollback simulation; a genuine, previously-open concurrent-migrator gap
  was found and closed with a new additive advisory-lock safeguard
  (shared/sdk/backup_dr/migration_runner.py); migrations 031-035 themselves were NOT modified. Gates
  1/2/6 are IMPLEMENTED / REHEARSED, PENDING RA-1R independent review — NOT marked CLOSED by this
  self-verified stage. No shared migration was applied; all four feature gates remain default-false.
  Step 66C.4-BE3-RA-1R (independent migration/rollback/locking review) is now COMPLETE (review
  branch review/66c4-be3-ra1-migration-rollback, commit 352d546, pushed to origin, unmerged):
  STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY: PASS, final verdict RA1_TECHNICAL_VERDICT:
  REMEDIATION_REQUIRED (one High finding -- H-1, aborted-transaction cleanup/lock-release failure --
  and three Medium findings -- M-1 fingerprint blind spots, M-2 no migration ledger, M-3 unbounded
  waits/no operational controls; migrations 031-035 themselves had no blocking defect). Step
  66C.4-BE3-RA-1B (targeted remediation of H-1/M-1/M-2/M-3) is now REMEDIATED / SELF-VERIFIED (see
  be3-ra1b-migration-runner-remediation-record.md,
  step66c4-be3-ra1b-migration-runner-remediation-evidence.md): apply_chain_locked now rolls back
  before unlocking and never masks the original error; the schema fingerprint captures FK actions
  and CHECK expressions; a new additive migration ledger (platform_schema_migrations) provides
  version/checksum provenance with fail-closed checksum-mismatch and untracked-schema handling and
  strict ambiguous-commit reconciliation; lock-wait/statement timeouts are bounded and a read-only
  plan mode plus operator CLI (scripts/run_platform_migrations.py) were added. Migrations 031-035
  remain unmodified; all four feature gates remain default-false; no shared migration was applied.
  Gates 1/2/6 remain PENDING -- this self-verified remediation does not close them. The next
  candidate is a **focused closure** by the **original RA-1R independent reviewer** over
  H-1/M-1/M-2/M-3; each remaining RA-stage requires its own separate, explicit Product Owner
  authorization, and none has been given beyond RA-1A/RA-1R/RA-1B themselves.
  Step 66C.4-BE3-RA-1FC (focused closure by the original RA-1R reviewer over H-1/M-1/M-2/M-3) is
  now COMPLETE (same review branch, reviewer-only integration commit 19cff82, focused-closure
  commit 9cd841f, pushed to origin, unmerged, unmodified by any implementation change --
  independently confirmed via zero-diff on every reviewed file): STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_
  VERIFY: PASS, RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED. H-1 and M-1 CLOSED. Four remaining
  gaps found (M-2A: an applied ledger row was never re-checked against the actual schema, so a raw
  isolated down left plan/apply silently claiming health; M-2B: ambiguous-commit reconciliation
  accepted a null expected fingerprint and a wrong-shaped table; M-3A: redact_for_operator missed
  the canonical postgresql:// scheme; M-3B: the CLI's connect() call sat outside its redacting
  try). Step 66C.4-BE3-RA-1C (targeted remediation of M-2A/M-2B/M-3A/M-3B) is now REMEDIATED /
  SELF-VERIFIED (see be3-ra1c-ledger-schema-cli-remediation-record.md,
  step66c4-be3-ra1c-ledger-schema-cli-evidence.md): plan_chain and apply_chain_with_ledger now
  re-verify an applied/reconciled ledger row's actual schema against a committed canonical manifest
  every time (shared/sdk/backup_dr/migration_manifests/{031..035}.json, generated once from a clean
  isolated rehearsal); the expected fingerprint is set from that manifest BEFORE any DDL runs and
  reconciliation now requires a non-null, manifest-validated match; redact_for_operator recognizes
  every connection-string scheme this project uses (not a fixed substring list) and collapses the
  whole message on detection; the CLI's connect attempt is wrapped in a protected path returning
  exactly one redacted JSON object on failure. A destructive-down policy was explicitly recorded:
  ledger-managed destructive down is NOT supported for shared environments (future shared rollback
  is disable-gates/stop-consumers/roll-back-application-version/retain-tables-and-data/forward-fix;
  RA-1A's isolated down rehearsal remains valid only as an ephemeral, no-business-data exercise).
  Migrations 031-035 remain unmodified; all four feature gates remain default-false; no shared
  migration was applied. Gates 1/2/6 remain PENDING -- this self-verified remediation does not
  close them. The next candidate is a **second focused closure** by the **original RA-1R
  independent reviewer** over M-2A/M-2B/M-3A/M-3B; each remaining RA-stage requires its own
  separate, explicit Product Owner authorization, and none has been given beyond RA-1A/RA-1R/
  RA-1B/RA-1FC/RA-1C themselves.
  Step 66C.4-BE3-RA-1FC2 (second focused closure by the original RA-1R/RA-1FC reviewer over
  M-2A/M-2B/M-3A/M-3B) is now COMPLETE (same review branch, reviewer-only integration commit
  07f839f, second-focused-closure commit 800035b, pushed to origin, unmerged, unmodified by any
  implementation change -- independently confirmed via zero-diff on every reviewed file):
  STEP66C4_BE3_RA1C_SECOND_FOCUSED_CLOSURE_VERIFY: PASS, RA1_TECHNICAL_VERDICT:
  REMEDIATION_REQUIRED. M-2A, M-2B, and M-3A CLOSED. One narrow, Low-severity M-3B residual found:
  the missing-configuration path printed a plain-text stderr line instead of the required single
  JSON object (no secret/traceback exposure; exit code itself correct). Step 66C.4-BE3-RA-1D
  (targeted remediation of the M-3B residual) is now REMEDIATED / SELF-VERIFIED (see
  be3-ra1d-missing-config-json-remediation-record.md,
  step66c4-be3-ra1d-missing-config-json-evidence.md): scripts/run_platform_migrations.py's
  _dsn_from_env() no longer prints or exits directly -- a single new _print_missing_configuration()
  function, called once from main() where the plan/apply mode is already known, is now the only
  place a missing/empty/whitespace-only configuration is reported (one JSON object, exit 2, no
  plain text, no env-var-value leak); a malformed-but-present DSN remains correctly routed to the
  existing connect-failure path. H-1/M-1/M-2A/M-2B/M-3A unmodified. Migrations 031-035 remain
  unmodified; all four feature gates remain default-false; no shared migration was applied. Gates
  1/2/6 remain PENDING -- this self-verified remediation does not close them. The next candidate is
  a **final, M-3B-only re-check** by the **original RA-1R independent reviewer**; each remaining
  RA-stage requires its own separate, explicit Product Owner authorization, and none has been given
  beyond RA-1A/RA-1R/RA-1B/RA-1FC/RA-1C/RA-1FC2/RA-1D themselves.
  Step 66C.4-BE3-RA-1FC3 (final, M-3B-only closure by the original RA-1R/RA-1FC/RA-1FC2 reviewer) is
  now COMPLETE (same review branch, reviewer-only integration commit 7c6b830, final closure commit
  1f3a66f, pushed to origin, unmerged, unmodified by any implementation change -- independently
  re-verified by a fresh, separately-provisioned ephemeral PostgreSQL 16 re-run of the reviewer's own
  21-test closure suite and 158 directly-affected RA-1/BE1 regression tests, 0 failed, 0 skipped):
  STEP66C4_BE3_RA1D_FINAL_M3B_CLOSURE_VERIFY: PASS, RA1_TECHNICAL_VERDICT: PASS. M-3B CLOSED. With
  this, H-1, M-1, M-2A, M-2B, M-3A, and M-3B are all independently verified CLOSED. Step
  66C.4-BE3-RA-1M (controlled merge of Draft PR #21 into canonical main) is now COMPLETE: merge
  commit 48004e3, two parents in order (18f11fe pre-merge main, 97e56d4 approved feature head),
  confirmed via git show; review branch 1f3a66f confirmed preserved and NOT a main ancestor both
  before and after. RA-1 Migration Readiness Foundation status: MERGED / NOT APPLIED TO SHARED DB /
  NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED. All four feature gates remain default-false;
  production_executed_true_count remains 0. Gates 1/2/6 remain PENDING RUNTIME/SHARED EXECUTION --
  this merge does not close them. RA-2 remains NOT AUTHORIZED; each remaining stage (shared migration
  application, deployment, runtime validation, activation, or RA-2) requires its own separate,
  explicit Product Owner authorization, and none has been given beyond RA-1A/RA-1R/RA-1B/RA-1FC/
  RA-1C/RA-1FC2/RA-1D/RA-1FC3/RA-1M themselves.
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
