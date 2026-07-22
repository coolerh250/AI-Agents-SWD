# Step 66C.4 — Contract Source-of-Truth Record

Marker: `STEP66C4_CONTRACT_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS`

This record establishes the Step 66C.4 Reminder / Expiry / Controlled Resume contract set as the
canonical source of truth on `main`, and pins the binding constraints that govern the future
Step 66C.4-BE1 implementation stage.

## Provenance chain

```text
Step 66C.4-P   (planning)     -> commit 4d9cc2a, marker
                                 STEP66C4_REMINDER_EXPIRY_CONTROLLED_RESUME_PLANNING_VERIFY: PASS
Step 66C.4-P-R1 (remediation) -> commit f50dd05, marker
                                 STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY: PASS
Step 66C.4-P-M (merge)        -> pre-merge main 83af345, merge commit e109189
                                 (git merge --no-ff, zero conflicts)
Product decisions             -> APPROVED_BY_PRODUCT_OWNER
                                 (docs/decisions/66c4-reminder-expiry-controlled-resume-product-
                                 decisions.md)
```

## Canonical contract index (on main)

```text
docs/contracts/66c4-reminder-expiry-controlled-resume/
  current-state-assessment.md
  lifecycle-and-time-contract.md          (§7.1 clock, §7.2A reminder, §7.3A authoritative expiry)
  data-model-contract.md                  (six lifecycle columns + clarification_lifecycle_outbox)
  api-and-event-contract.md               (§11.3 transactional-outbox atomicity, binding)
  scheduler-architecture-decision.md      (Option 2, dedicated DB poller)
  controlled-resume-contract.md           (binding six-transition resume state model)
  rbac-and-safety-contract.md
  race-condition-and-failure-analysis.md  (17 scenarios + recovery-semantics split)
  observability-and-audit-plan.md
  frontend-ux-boundary.md
  implementation-stage-slicing-plan.md    (BE1/BE2/BE3 corrected)
  test-and-validation-plan.md
  product-owner-decision-checklist.md
  contract-remediation-record.md
  contract-merge-record.md
  contract-source-of-truth-record.md      (this file)
```

## Canonical semantics (binding)

```text
Lifecycle fields: exactly six new columns on operator_clarification_requests --
  reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at, resume_requested_by,
  resume_authorized_at. resume_dispatched_at is NOT a column (dispatch/resumed evidence lives in
  durable outbox/audit + the task's own status). Internally consistent -- no "six vs seven" conflict.
Deadline semantics: due_at = authoritative exclusive expiry deadline; reminder_at = authoritative
  reminder-due time; PostgreSQL DB time = authoritative lifecycle clock; DB time >= due_at -> answer
  rejected with 409; scheduler lag does not extend answer eligibility.
Reminder semantics: one reminder per clarification at created_at + 24h; at-least-once delivery +
  idempotent processing; exactly-once NOT claimed.
Outbox model: canonical -- lifecycle state update + outbox insert in the same DB transaction; a
  relay publishes / acknowledges / bounded-retries / terminal-DLQs / emits metrics / supports
  operator replay.
Resume transitions: ANSWERED -> RESUME_ELIGIBLE -> RESUME_REQUESTED -> RESUME_AUTHORIZED ->
  RESUME_DISPATCHED -> WORKFLOW_RESUMED; operator request != workflow resumed; policy authorization
  is separate from request; dispatch is separate from workflow confirmation; cancelled/aborted/
  terminal workflows cannot resume; production-effect tasks cannot bypass existing approval.
Recovery model: automatic recovery (transient retry, process restart, outbox backlog replay,
  duplicate suppression) vs operator recovery (terminal DLQ, poison event, policy failure,
  inconsistent legacy record, manual replay, audit reconciliation exception) -- explicitly split.
```

## BE1 Runtime Compatibility Gate (binding — must be cited by the 66C.4-BE1 prompt)

```text
If no active outbox relay exists:

- Existing runtime producers remain on their current path.
- Existing answer/audit/event runtime behavior remains unchanged.
- The outbox schema/repository may be introduced ONLY as disabled foundation.
- No lifecycle event may be written into an unconsumed outbox.
- Producer cutover requires relay, retries, DLQ, metrics, rollback path, and runtime validation to
  be ready TOGETHER.

This is a binding stage gate for Step 66C.4-BE1, not a suggestion. BE1 may create only schema,
repository, CAS, and disabled foundation; it may not switch existing producers to the outbox, and
it may not change existing answer/audit/event runtime behavior.
```

## Authorization posture

```text
Step 66C.4-BE1: NOT STARTED / NOT AUTHORIZED (next candidate stage, pending separate PO
  authorization).
Codex: NOT AUTHORIZED.
Claude Design: NOT AUTHORIZED.
```

## Runtime / safety

```text
Runtime frontend code commit: 513f190 (unaffected).
git diff 83af345 e109189 -- apps services infra migrations database helm k8s .github/workflows
  -> empty.
No migration created. No scheduler/relay activated. No dispatch/resume. No deployment. No external
  notification. production_executed_true_count: 0.
```

## Statement

Source-of-truth record only. No backend/frontend runtime change. No API implementation change. No
database schema change. No migration created. No workflow change. No scheduler activated. No outbox
relay activated. No existing producer switched. No dispatch/resume executed. No deployment. No
external notification. No production/external action. Step 66C.4-BE1 not started. Codex and Claude
Design not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->

<!-- STEP66C4_CONTRACT_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS -->
