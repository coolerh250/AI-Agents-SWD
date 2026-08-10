# Step 66D-ARCH1 — Domain and State Model

> **Specification only. No persistence, no migration, no code. `production_executed_true_count: 0`.**

## 1. DeliverySubmission

```text
Authoritative source:  DeliverySubmission row (NOT IMPLEMENTED)
Immutability:          content frozen at SUBMITTED; a change requires a new version
Versioning:            submission_version, supersedes_submission_id
Concurrency:           row_version, optimistic CAS on every mutation
Retention:             retained with the project; decisions outlive the submission
Redaction:             no raw tokens, secrets, credentials or private chain of thought
```

### Identity and lineage (required)

```text
delivery_submission_id      uuid, immutable
project_id                  required -- execution lineage anchor
primary_work_item_id        required
workflow_id                 required
run_id                      required
delivery_review_task_id     required -- human review anchor (66D-D03)
submission_version          integer, starts at 1, monotonic per logical submission
status                      one of the nine canonical statuses (section 6)
```

### Lifecycle (required)

```text
created_at                  timestamp, DB authoritative
created_by_actor            actor_ref
submitted_at                timestamp, null until SUBMITTED
submitted_by_actor          actor_ref, null until SUBMITTED
review_due_at               timestamp, drives EXPIRED
row_version                 integer, CAS precondition
```

### Baseline and linkage (required)

```text
requirements_baseline_id    required -- what this submission claims to satisfy
acceptance_criteria_version required -- which criteria version was assessed
legacy_delivery_package_refs  list, may be empty -- reference only (66D-D04)
supersedes_submission_id    nullable -- set when replacing a CHANGES_REQUESTED version
```

### Content and evidence

```text
delivery_items              list of DeliveryItem
requirement_results         list of AcceptanceCriterionResult
artifact_refs               list of ArtifactRef
qa_results                  list of QaEvidenceRef
source_control_evidence     branch / commit_sha / pull_request, may be empty for plan-only work
security_boundary           declared limits of what the work touched
known_limitations           explicit, required -- an empty list is a claim, not a default
run_instructions            how a reviewer reproduces the result
demo_evidence_refs          screenshots, recordings, transcripts (redacted)
cost_summary                CostSummary (see api-event-audit-contracts.md section 6)
external_action_summary     ExternalActionSummary
audit_refs                  list of audit event ids
```

`known_limitations` is required and must be explicitly populated. A submission that claims no
limitations has made an assertion a reviewer can challenge, which is the point.

## 2. DeliveryReviewTask

```text
delivery_review_task_id     uuid, immutable
delivery_submission_id      required
task_id                     required -- the existing Task this review hangs off
assigned_roles              subset of TASK_ROLES
assigned_actor_refs         list, may be empty until assignment
review_status               mirrors submission review state for the assignee's view
                            ** SUPERSEDED BY 66D-D05 -- NOT AUTHORITATIVE FOR BE1 PERSISTENCE **
review_due_at               timestamp
created_at                  timestamp
closed_at                   nullable -- ACTIVE-STATE AUTHORITY (66D-D05)
row_version                 integer
```

```text
Authoritative source:  DeliveryReviewTask row (NOT IMPLEMENTED)
Relationship:          exactly one active review task per submission version
Immutability:          assignment history is audited; the row itself is mutable under CAS
```

> **Amended by 66D-D05 (BINDING).** The `review_status` line above is retained as the original
> ARCH1 text and is **superseded as lifecycle and storage authority**. Step 66D-BE1 must not persist
> an independent `DeliveryReviewTask` status enum and must not mirror `DeliverySubmission.status`
> into the review task. Active state is structural:

```text
DeliveryReviewTask.active  :=  closed_at IS NULL
DeliveryReviewTask.closed  :=  closed_at IS NOT NULL

Persistence invariant:  AT MOST ONE structurally active DeliveryReviewTask per
                        delivery_submission_id (partial unique index WHERE closed_at IS NULL).
                        delivery_submission_id is the submission-version boundary, because each
                        version is a distinct row linked by supersedes_submission_id.
Required existence:     WHEN an active task must exist is DEFERRED, not enforced by BE1.
Lifecycle enum:         NOT DEFINED. OPEN / IN_PROGRESS / CLOSED / CANCELLED belongs to
                        AcceptanceFollowUpItem (section 5) and must not be reused here.
closed_at meaning:      structural only -- never ACCEPTED, REJECTED, EXPIRED, ARCHIVED, a recorded
                        ProductOwnerDecision, completed QA, or a terminal submission status.
Transitions:            reopen, close-action, automatic closure, closure by decision and closure
                        by expiry are all DEFERRED.
```

> Full text: `docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md`

## 3. DeliveryReviewAction

Append-only. One row per recorded Review Gate Action.

```text
review_action_id            uuid, immutable
delivery_submission_id      required
delivery_review_task_id     required
action_type                 one of the six Review Gate Actions -- no other value
actor_ref                   verified actor (section 5)
reason                      required for REQUEST_CHANGES, RERUN_QA, ESCALATE, REJECT
requested_scope             required for RERUN_QA -- what to re-verify
previous_qa_ref             required for RERUN_QA -- what is being re-verified
created_at                  timestamp, DB authoritative
idempotency_key             required, unique per (submission, actor, logical intent)
audit_event_id              required
```

```text
Authoritative source:  DeliveryReviewAction row (NOT IMPLEMENTED)
Immutability:          append-only; never updated, never deleted
Versioning:            none -- a correction is a new action, or a superseding decision
```

## 4. ProductOwnerDecision

Append-only, supersedable. This is the authoritative acceptance record (66D-D02).

```text
decision_id                 uuid, immutable
delivery_submission_id      required
decision_type               ACCEPTED | ACCEPTED_WITH_FOLLOW_UP | REJECTED -- no other value
decision_reason             required
decided_by_actor            verified human actor with PO decision capability
decided_at                  timestamp, DB authoritative
evidence_reviewed           list of refs the decider actually saw
supersedes_decision_id      nullable -- the only way to replace a decision
decision_version            integer, monotonic per submission
audit_event_id              required
```

```text
Authoritative source:  ProductOwnerDecision row (NOT IMPLEMENTED)
Immutability:          never updated in place, never deleted
Effective decision:    the row with the highest decision_version not itself superseded
Projection:            submission.status ACCEPTED/REJECTED is DERIVED from this
```

### Superseded statement

A superseded decision remains visible and queryable. It is not deleted, not hidden, and not
rewritten. History shows what was decided, when, by whom, and what replaced it.

## 5. AcceptanceFollowUpItem

```text
follow_up_item_id           uuid, immutable
decision_id                 required -- belongs to a decision, not to a submission
description                 required
owner_actor_ref             required
severity                    required
blocking                    boolean -- MUST be false under ACCEPTED_WITH_FOLLOW_UP
due_at                      nullable
status                      OPEN | IN_PROGRESS | CLOSED | CANCELLED
created_at                  timestamp
closed_at                   nullable
evidence_refs               list
```

```text
Rule:  ACCEPTED_WITH_FOLLOW_UP accepts only blocking = false.
       Any blocking follow-up -> 409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES; use REQUEST_CHANGES.
```

## 6. Delivery review state machine

### Canonical statuses (exactly nine)

```text
DRAFT
SUBMITTED
UNDER_REVIEW
CHANGES_REQUESTED
QA_RERUN_REQUESTED
ACCEPTED
REJECTED
ARCHIVED
EXPIRED
```

### Frozen transitions

| From | To | Trigger | Creates decision |
| ---- | -- | ------- | ---------------- |
| DRAFT | SUBMITTED | submit | no |
| SUBMITTED | UNDER_REVIEW | review assignment / first open | no |
| UNDER_REVIEW | CHANGES_REQUESTED | REQUEST_CHANGES | no |
| UNDER_REVIEW | QA_RERUN_REQUESTED | RERUN_QA (bounded) | no |
| QA_RERUN_REQUESTED | UNDER_REVIEW | new QA result attached | no |
| UNDER_REVIEW | ACCEPTED | ACCEPT | yes |
| UNDER_REVIEW | REJECTED | REJECT | yes |
| terminal / expired / superseded | ARCHIVED | ARCHIVE | no |
| SUBMITTED or UNDER_REVIEW | EXPIRED | review_due_at passed | no |

`ESCALATE` deliberately appears in no row: it records an escalation and leaves the status at
`UNDER_REVIEW`.

### Rules

```text
1.  ACCEPTED and REJECTED are projections of the current effective ProductOwnerDecision.
2.  REQUEST_CHANGES creates no final decision.
3.  RERUN_QA creates no final decision.
4.  ESCALATE creates an escalation record; status stays UNDER_REVIEW; never a final decision.
5.  ARCHIVE applies only to terminal, expired or superseded submissions.
6.  Re-submission after CHANGES_REQUESTED MUST create a new DeliverySubmission version.
7.  An existing submission is never rewritten in place with new content.
8.  After EXPIRED, no direct accept or reject; create a new version or an explicit reopen.
9.  Expiry is judged by DB authoritative time, never client time.
10. Every transition is idempotent and uses optimistic concurrency (row_version CAS).
```

### Per-transition contract

Every transition specifies:

```text
authorized actor      which TASK_ROLES capability is required
preconditions         current status, row_version, evidence completeness
required evidence     what must be present for the transition to be legal
state mutation        exact fields written
event                 durable event emitted via transactional outbox
audit record          audit action name, before state, after state
error behavior        which error code on each precondition failure
retry behavior        idempotency key semantics; replay returns the original result
```

Concrete example, the one with the sharpest failure mode:

```text
UNDER_REVIEW -> ACCEPTED
  authorized actor   verified human with PO decision capability (pm_engineering_lead / PO)
  preconditions      status == UNDER_REVIEW; row_version matches; all acceptance criteria
                     assessed; no blocking follow-up in the request
  required evidence  evidence_reviewed non-empty; decision_reason present
  state mutation     status := ACCEPTED (projection); DeliveryReviewAction(ACCEPT) inserted;
                     ProductOwnerDecision(ACCEPTED | ACCEPTED_WITH_FOLLOW_UP) inserted;
                     follow-ups inserted -- all in ONE transaction
  event              delivery.review_action.recorded, delivery.review.accepted,
                     delivery.po_decision.recorded, delivery.po_accepted[_with_follow_up]
  audit              review_action.accept AND po_decision.accepted -- different action names
  error              409 FINAL_DECISION_ALREADY_EXISTS, 409 DELIVERY_VERSION_CONFLICT,
                     409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES, 422 ACCEPTANCE_CRITERIA_INCOMPLETE
  retry              same idempotency_key returns the original decision, creates nothing new
```

There must never be a persisted state where an `ACCEPT` action exists without its corresponding
final decision.

## 7. Actor contract

```text
actor_id                    stable identifier
actor_type                  runtime_agent | ai_partner | human | system
display_name                human-readable
role                        TASK_ROLES value where applicable
identity_source             where the identity was established
authenticated_identity_ref  verified human identity, null until RA-2 identity is implemented
service_identity_ref        workload identity, null until RA-2 identity is implemented
partner_execution_ref       external partner session/run reference
environment                 sandbox / internal test runtime -- never production in this stage
```

External AI partners — **Claude Code, Codex, Claude Design** — are `actor_type: ai_partner`. They
must never be described or recorded as `runtime_agent` services. They are not deployed workloads.

## 8. Artifact provenance

```text
artifact_id                 uuid
artifact_type               document | code | test | design | evidence | report
producer_actor_ref          required
generation_mode             see below
repository                  nullable
branch                      nullable
commit_sha                  nullable
pull_request                nullable
content_hash                required -- integrity anchor
created_at                  timestamp
review_status               required
test_status                 required
supersedes_artifact_id      nullable
```

### generation_mode

```text
plan_only
deterministic_template
external_partner_generated
human_authored
future_autonomous_runtime_generated      NOT PERMITTED IN THE FIRST POC
```

The first POC forbids:

```text
future_autonomous_runtime_generated
runtime direct patch generation
runtime direct test generation
automatic patch application
autonomous merge
```

No artifact record may store private chain of thought, raw tokens, secrets or credentials.

## 9. Requirement traceability identifiers

```text
requirement_id  ->  acceptance_criterion_id  ->  work_item_id  ->  execution_id
                ->  artifact_id  ->  qa_evidence_id  ->  delivery_item_id
                ->  review_action_id  ->  decision_id
```

Acceptance criterion result values:

```text
PASS  FAIL  PARTIAL  NOT_TESTED  NOT_APPLICABLE
```

Each result carries `assessor_actor_ref`, `assessed_at`, `reason`, `evidence_refs`.

**Agent completion does not imply PASS.** There is no transition, default or inference that turns a
finished run into a passing criterion.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
