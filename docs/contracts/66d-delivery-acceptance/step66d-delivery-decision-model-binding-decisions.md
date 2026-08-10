# Step 66D — Delivery Decision Model Binding Decisions

> **Product Owner binding decision record. It resolves four canonical conflicts in the delivery
> review and acceptance model. It does NOT freeze the Step 66D-ARCH contract and does NOT authorize
> implementation. No runtime, frontend, backend, API, database, event, migration, deployment,
> identity, secret or feature-gate change was made.
> `production_executed_true_count: 0`.**

```text
DOCUMENT_STATUS:
CANONICAL / BINDING

DECISION_AUTHORITY:
Product Owner

DECISION_DATE:
2026-08-04

RECORDED_BY:
Claude Code (Step 66D-ALIGN1), acting as recorder only

CANONICAL_BASELINE:
main 64467fe

66D-D01:
RESOLVED / BINDING

66D-D02:
RESOLVED / BINDING

66D-D03:
RESOLVED / BINDING

66D-D04:
RESOLVED / BINDING

66D-D05:
RESOLVED / BINDING (added 2026-08-10 by Step 66D-BE1-CR1)

STEP66D_ARCH1:
NOT RESTARTED / NOT AUTHORIZED BY THIS STAGE

IMPLEMENTATION:
NOT STARTED / NOT AUTHORIZED
```

## Conflict background

Step 66D-ARCH1 was attempted on canonical main `64467fe` and correctly stopped with
`RESULT: CANONICAL_STAGE_CONFLICT` before creating any branch or artifact. Main carried two
incompatible delivery vocabularies that had coexisted since Step 66ALIGN.2-M and Step 66SYNC.1-M2
respectively, plus an anchor disagreement and an entity-name collision:

```text
66D-CONFLICT-01  Review Gate Action vocabulary vs Product Owner Final Decision vocabulary
                 Master-plan family: 6-action gate
                   (Accept / Reject / Request-Changes / Re-run-QA / Escalate / Archive)
                 Claude Design specification: "Product Owner decision (only these three)"
                   (ACCEPTED / ACCEPTED_WITH_FOLLOW_UP / REJECTED)

66D-CONFLICT-02  Delivery review lifecycle vs authoritative decision record
                 Milestone manifest listed accepted/rejected/changes-requested/qa-rerun-requested
                 as delivery states; the decision-record model required acceptance to live outside
                 the delivery lifecycle.

66D-CONFLICT-03  Task anchor vs Project/Work Item/Workflow/Run lineage
                 Milestone manifest scoped 66D-ARCH to "delivery packages tied to real tasks" with
                 TASK_ROLES RBAC; binding decision D-1 anchors execution on
                 project -> work item -> workflow/run and holds the Task surface is not the Agent
                 execution source of truth.

66D-CONFLICT-04  Legacy DeliveryPackage vs new human-acceptance aggregate
                 `DeliveryPackage` is an implemented Step 47/49 Platform Ops evidence object
                 (delivery_package_api.py, DeliveryPackage.tsx, agents/delivery-package-agent/),
                 while the milestone manifest required the new acceptance surface to be
                 "not a rename of the existing page".
```

Neither vocabulary was wrong; each described a different layer. The Product Owner resolved all four
on 2026-08-04.

---

## 66D-D01 — Layered review and final-decision model

```text
STATUS:    RESOLVED / BINDING
SELECTION: Layered model. Review Gate Action and Product Owner Final Decision are two separate
           contracts, not two names for one thing.
```

### Review Gate Action (exactly six)

```text
ACCEPT
REJECT
REQUEST_CHANGES
RERUN_QA
ESCALATE
ARCHIVE
```

### Product Owner Final Decision (exactly three)

```text
ACCEPTED
ACCEPTED_WITH_FOLLOW_UP
REJECTED
```

### Binding requirements

```text
D01-R1  Review Gate Action != Product Owner Final Decision.
D01-R2  The two use different enums.
D01-R3  The two use different schemas.
D01-R4  The two use different command / API semantics.
D01-R5  The two emit different durable events.
D01-R6  The two produce different audit actions.
D01-R7  The two have different authorization boundaries.
D01-R8  REQUEST_CHANGES, RERUN_QA, ESCALATE and ARCHIVE must never be added to the Product Owner
        Final Decision enum.
D01-R9  ACCEPTED_WITH_FOLLOW_UP must never be added to the Review Gate Action enum.
```

### Mapping table

| Review Gate Action | Product Owner Final Decision | Result |
| --- | --- | --- |
| `ACCEPT` | `ACCEPTED` | Unconditional acceptance |
| `ACCEPT` | `ACCEPTED_WITH_FOLLOW_UP` | Accepted, with at least one non-blocking follow-up created |
| `REJECT` | `REJECTED` | Final rejection |
| `REQUEST_CHANGES` | none | Content revision requested; resubmission required |
| `RERUN_QA` | none | Verification re-run; no content change requested |
| `ESCALATE` | none | Escalated for governance or permission handling |
| `ARCHIVE` | none | Administrative archival; neither acceptance nor rejection |

Four of the six Review Gate Actions produce **no** Product Owner Final Decision at all. That is the
substance of the layering: a review action is a workflow move, and only `ACCEPT` and `REJECT` carry
a final decision alongside them.

---

## 66D-D02 — Projected review status plus immutable decision history

```text
STATUS:    RESOLVED / BINDING
SELECTION: Delivery review status may project the current effective decision; the authoritative
           decision history lives in a separate immutable ProductOwnerDecision record.
```

### Delivery review status (permitted values)

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

### Binding requirements

```text
D02-R1   ProductOwnerDecision must never be overwritten in place.
D02-R2   A new decision may only replace an older one through `supersedes_decision_id`.
D02-R3   Decision history must never be deleted.
D02-R4   ACCEPTED and REJECTED in the delivery review status are a projection of the current
         effective decision, not the authoritative record.
D02-R5   ACCEPTED_WITH_FOLLOW_UP projects to delivery review status ACCEPTED.
D02-R6   ACCEPTED_WITH_FOLLOW_UP may contain only non-blocking follow-up items.
D02-R7   Whenever a blocking follow-up exists, REQUEST_CHANGES must be used instead.
D02-R8   REQUEST_CHANGES and RERUN_QA are not final decisions.
D02-R9   ARCHIVE means neither Product Owner acceptance nor rejection.
D02-R10  An Agent marking work complete is not equivalent to Product Owner acceptance.
D02-R11  Acceptance is not production approval.
D02-R12  Acceptance does not bypass security, identity, deployment or production gates.
```

### Superseded statement

The earlier formulation that **acceptance must not appear in the delivery lifecycle at all** is
superseded. The binding formulation is:

```text
Delivery review status MAY project the outcome of the current effective final decision,
but the authoritative decision history is a separate immutable record.
```

---

## 66D-D03 — Dual-anchor model

```text
STATUS:    RESOLVED / BINDING
SELECTION: Two distinct anchors. Execution and artifact lineage is project-anchored; human review
           and RBAC is task-anchored.
```

### Execution and artifact lineage

```text
project_id
  -> work_item_id
    -> workflow_id
      -> run_id
```

This lineage is the Agent execution source of truth, the artifact lineage, and the requirement
traceability lineage. It preserves binding decision D-1:

```text
Dedicated POC Development Goal -> Project -> Work Item -> Workflow / Run
```

### Human review anchor

```text
delivery_review_task_id
```

`DeliveryReviewTask` owns the Delivery Inbox queue, reviewer assignment, the human review workflow,
`TASK_ROLES` authorization (`reviewer_approver`, `pm_engineering_lead`), Review Gate Actions, and
the entry point for recording a Product Owner Final Decision.

### Binding boundary

```text
Task is the human-review and RBAC anchor.
Task is not the Agent execution source of truth.
```

```text
D03-R1  Execution, artifacts and requirement traceability anchor on project -> work item ->
        workflow -> run.
D03-R2  Human review, queueing and RBAC anchor on delivery_review_task_id.
D03-R3  The existing non-dispatching Task API must not be re-described as an Agent pipeline entry
        point.
D03-R4  A delivery review task must reference its execution lineage; the reverse is not required.
```

---

## 66D-D04 — Legacy preservation and new aggregate naming

```text
STATUS:    RESOLVED / BINDING
SELECTION: The legacy DeliveryPackage is preserved unchanged. The new human-acceptance aggregate is
           named DeliverySubmission.
```

### Legacy object — preserved

`DeliveryPackage` continues to mean the legacy Platform Ops evidence package (Step 47 / Stage 49).

```text
D04-R1  It must not be renamed into the new aggregate.
D04-R2  It must not be reshaped into the new human-acceptance domain.
D04-R3  Its existing API semantics must not be silently changed.
D04-R4  Step 47/49 historical evidence must not be broken.
```

### New human-acceptance domain

```text
DeliverySubmission        the human-acceptance aggregate
DeliveryReviewTask        the human review anchor and queue entry
DeliveryReviewAction      a recorded Review Gate Action
ProductOwnerDecision      the immutable final-decision record
AcceptanceFollowUpItem    a follow-up raised by a decision
```

Product surface names:

```text
Delivery Inbox
Delivery Review
```

```text
D04-R5  DeliverySubmission may reference the legacy object through `legacy_delivery_package_refs`.
D04-R6  The legacy DeliveryPackage must not be used as the human review aggregate.
```

---

## 66D-D05 — DeliveryReviewTask structural active state

```text
STATUS:    RESOLVED / BINDING
ADDED:     2026-08-10, recorded by Step 66D-BE1-CR1
SELECTION: Active state is structural, derived from closed_at. No DeliveryReviewTask lifecycle
           enum is defined, and DeliverySubmission.status is never mirrored as task lifecycle
           authority.
FULL TEXT: docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md
```

### Predicates

```text
DeliveryReviewTask.active  :=  closed_at IS NULL
DeliveryReviewTask.closed  :=  closed_at IS NOT NULL
```

### Binding requirements

```text
D05-R1   Active state is structural: closed_at IS NULL. Closed state is closed_at IS NOT NULL.
D05-R2   Step 66D-BE1 must not persist an independent DeliveryReviewTask status or review_status
         lifecycle enum.
D05-R3   Step 66D-BE1 must not mirror DeliverySubmission.status into DeliveryReviewTask as
         lifecycle authority.
D05-R4   The persistence invariant is AT MOST ONE structurally active DeliveryReviewTask per
         delivery_submission_id, enforced by a partial unique index where closed_at IS NULL.
D05-R5   delivery_submission_id is the submission-version boundary, because each submission
         version is a distinct row linked by supersedes_submission_id.
D05-R6   When an active review task MUST exist is deferred to a future lifecycle stage. BE1 must
         not force every submission to always have one.
D05-R7   closed_at never implies ACCEPTED, REJECTED, EXPIRED, ARCHIVED, a recorded
         ProductOwnerDecision, completed QA, or a terminal submission status.
D05-R8   The DeliveryReviewTask lifecycle enum is NOT DEFINED. OPEN, IN_PROGRESS, CLOSED,
         CANCELLED, PENDING and ACTIVE must not be introduced as review-task lifecycle values.
         OPEN / IN_PROGRESS / CLOSED / CANCELLED belongs to AcceptanceFollowUpItem.
D05-R9   The Delivery Inbox filter delivery_review_task_status stays a reserved product concept:
         PLANNED / NOT IMPLEMENTED, lifecycle enum not yet defined, BE1 persistence source none.
         It must not be derived from DeliverySubmission.status.
D05-R10  Reopen, close-action, reopen-after-close, automatic closure, closure caused by a Product
         Owner decision and closure caused by expiry are all deferred and unimplemented.
```

### Supersession

```text
SUPERSEDED  ARCH1 domain-and-state-model section 2, "review_status mirrors submission review
            state for the assignee's view" -- withdrawn as lifecycle and storage authority for
            BE1 persistence. The original sentence is annotated in place, never deleted.
PRESERVED   DESIGN delivery-inbox-spec section 3 -- review-task status and submission status stay
            NOT interchangeable, and a closed review task against an EXPIRED submission stays
            expressible.
UNCHANGED   66D-D01, 66D-D02, 66D-D03, 66D-D04 and ADR-66D-09 keep their existing semantics.
```

## Deferred implementation

```text
Bounded QA rerun count, cooldown, timeout and escalation threshold
  -> deferred to Step 66D-ARCH contract freeze. NOT decided in this stage.

DeliverySubmission schema, Review Action API, PO Decision API, immutable supersession persistence,
DeliveryReviewTask linkage, TASK_ROLES authorization mapping, Delivery Inbox read model,
legacy reference contract, follow-up lifecycle
  -> all remain NOT IMPLEMENTED and NOT AUTHORIZED.

Final POC information architecture (Unified POC Control Center vs Coordinated Existing Routes)
  -> still an open POC.0 design option; not selected by this record.
```

## Prohibited implications

None of the following is true, and none may be inferred from this record:

```text
Contracts are already frozen                      -- FALSE
Step 66D-ARCH is complete                         -- FALSE
Step 66D-ARCH1 is authorized to restart           -- FALSE
DeliverySubmission is implemented                 -- FALSE
Delivery Inbox is implemented                     -- FALSE
The PO decision API is implemented                -- FALSE
TASK_ROLES has been updated                       -- FALSE
The POC is ready                                  -- FALSE
Acceptance implies production approval            -- FALSE
```

## Authorization status

```text
66D_D01_D04:                     RESOLVED / BINDING
CANONICAL_CONFLICTS:             RESOLVED IN THIS RECORD
STEP66D_ARCH1:                   NOT STARTED / NOT AUTHORIZED
STEP66D_DESIGN:                  NOT STARTED / NOT AUTHORIZED
STEP66D_IMPLEMENTATION:          NOT STARTED / NOT AUTHORIZED
STEP67POC0:                      NOT STARTED / NOT AUTHORIZED
RA2I0:                           NOT STARTED / NOT AUTHORIZED
BE3_RESUME_REPLAY:               DISABLED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

Resolving a vocabulary conflict is not a contract freeze. Step 66D-ARCH still has to define the
schemas, state machines, APIs, events, audit records, read model and bounded QA-rerun limits, and it
requires its own separate Product Owner authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
