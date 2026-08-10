# Step 66D — 66D-D05 DeliveryReviewTask Active-State Amendment

> **Product Owner binding decision record. Documentation only. It resolves one canonical conflict
> about `DeliveryReviewTask` state storage so that Step 66D-BE1 can build a deterministic partial
> unique constraint. No runtime, frontend, backend, API, database, migration, event, deployment,
> identity, secret or feature-gate change was made. No table, repository, ORM model or migration was
> created. `production_executed_true_count: 0`.**

```text
Decision ID:          66D-D05
Status:               BINDING
Decision authority:   Product Owner
Recorded by:          Claude Code (Step 66D-BE1-CR1), acting as recorder only
Canonical baseline:   main af40b3bf9792fe8182e9620fb9d134af67cf4a12
Scope:                DeliveryReviewTask structural active state, and the persistence invariant
                      Step 66D-BE1 must implement
Implementation:       NOT STARTED / BE1 PAUSED until this amendment is canonicalized
```

## 1. The conflict this resolves

Step 66D-BE1 stopped at its canonical contract gate. Two canonical, merged, binding artifacts
disagreed about how `DeliveryReviewTask` state is stored, which made the ARCH1 relationship
"exactly one active review task per submission version" impossible to implement without inventing
product contract.

```text
ARCH1  docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md, section 2
       merged ab19dad
       "review_status    mirrors submission review state for the assignee's view"
       -> implies the nine canonical DeliverySubmission statuses
       -> QUOTED HERE AS THE SUPERSEDED PRIOR STATEMENT. It is SUPERSEDED by 66D-D05 and is NOT
          AUTHORITATIVE for BE1 persistence. It must not be re-asserted as current authority.

DESIGN docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md, section 3
       and the design contract manifest, merged bb8eab7 (later)
       "delivery_review_task_status | DeliveryReviewTask.status | review-task lifecycle
        (NOT IMPLEMENTED)"
       "The two status filters are not interchangeable ... the review task can be open while its
        submission is already terminal ... A row may therefore legitimately show a closed review
        task against an EXPIRED submission, and the Inbox must be able to express that."
```

Both cannot hold. If review-task state mirrors the submission's nine statuses, a closed review task
against an `EXPIRED` submission is inexpressible, which DESIGN explicitly requires. If it is an
independent lifecycle, its values are declared **NOT IMPLEMENTED** and are enumerated nowhere in the
repository. The precedence record resolves the D01–D04 vocabulary conflicts and does not rank ARCH1
against DESIGN on this point.

## 2. The decision

```text
DeliveryReviewTask.active  :=  closed_at IS NULL
DeliveryReviewTask.closed  :=  closed_at IS NOT NULL
```

Active state is **structural**. It is derived from one canonical ARCH1 field that already exists on
the entity, and it requires no lifecycle enum at all.

```text
BE1 SHALL NOT persist an independent DeliveryReviewTask status or review_status lifecycle enum.
BE1 SHALL NOT mirror DeliverySubmission.status into DeliveryReviewTask as lifecycle authority.
```

## 3. What `closed_at` does NOT mean

`closed_at` is a structural marker only. It must never be read, projected, rendered or documented as
any of the following:

```text
ACCEPTED                     REJECTED
EXPIRED                      ARCHIVED
a ProductOwnerDecision was recorded
QA completed
the submission reached a terminal status
```

A closed review task says the human-review anchor is no longer structurally open. It says nothing
about the outcome, and it is not an acceptance signal. The authoritative acceptance record remains
the immutable, supersedable `ProductOwnerDecision` (66D-D02).

## 4. Persistence invariant

```text
AT MOST ONE structurally active DeliveryReviewTask per delivery_submission_id.
```

Because ARCH1 rules 6 and 7 make every submission version a distinct row — a re-submission after
`CHANGES_REQUESTED` creates a **new** `DeliverySubmission` linked by `supersedes_submission_id`, and
an existing submission is never rewritten in place — `delivery_submission_id` **is** the
submission-version boundary. No separate version column is required on the review task to scope the
constraint.

Canonical implementation requirement for Step 66D-BE1:

```sql
CREATE UNIQUE INDEX ...
    ON delivery_review_tasks (delivery_submission_id)
    WHERE closed_at IS NULL;
```

### At-most-one is not required-existence

```text
AT MOST ONE active task per submission     BINDING, enforced by BE1 persistence
WHEN an active task MUST exist             DEFERRED to a future lifecycle / orchestration stage
```

BE1 must not add a database trigger, constraint or backfill that forces every submission to always
have an active review task. A submission with zero active review tasks is a legal persistence state
in BE1.

## 5. Review-task lifecycle enum — deferred

```text
DeliveryReviewTask lifecycle enum:  NOT DEFINED
```

BE1 must not introduce any of the following as a `DeliveryReviewTask` canonical lifecycle:

```text
OPEN            IN_PROGRESS
CLOSED          CANCELLED
PENDING         ACTIVE
```

`OPEN / IN_PROGRESS / CLOSED / CANCELLED` currently belongs to `AcceptanceFollowUpItem`
(ARCH1 section 5) and must not be reused for the review task.

## 6. `delivery_review_task_status` — reserved product concept

The DESIGN Delivery Inbox filter keeps its identity and its separation from the submission status,
and remains unimplemented:

```text
delivery_review_task_status:  RESERVED PRODUCT / READ-MODEL CONCEPT
                              PLANNED / NOT IMPLEMENTED
                              LIFECYCLE ENUM NOT YET DEFINED
                              BE1 persistence source: none
```

It must not be derived from `DeliverySubmission.status`, must not be derived as an `OPEN`/`CLOSED`
value straight from `closed_at`, and must not be described as an existing backend field. Implementing
that filter for real requires a separate authorized lifecycle-contract stage.

## 7. Transition semantics — deferred

66D-D05 defines the active predicate and the persistence invariant. It deliberately does **not**
define:

```text
reopen                          a close action
reopen-after-close              automatic closure
closure caused by a Product Owner decision
closure caused by expiry
```

All of the above are deferred. BE1 must not implement any of them.

## 8. Supersession and preservation

```text
SUPERSEDES
  ARCH1 step66d-arch1-domain-and-state-model.md section 2:
  "review_status mirrors submission review state for the assignee's view"
  -- superseded as lifecycle and storage authority for BE1 persistence.
  The original sentence is retained in place, annotated, not deleted.

PRESERVES
  DESIGN step66d-design-delivery-inbox-spec.md section 3:
  the review-task status and the submission status are NOT interchangeable, and a closed review
  task against an EXPIRED submission must remain expressible.
  66D-D05 satisfies this: structural closure is independent of submission status.

UNCHANGED
  66D-D01  six Review Gate Actions / three Product Owner Final Decisions
  66D-D02  projected review status plus immutable decision history
  66D-D03  dual-anchor model
  66D-D04  legacy DeliveryPackage preserved; DeliverySubmission is the new aggregate
  ADR-66D-09  one bounded QA rerun per DeliverySubmission version
```

Neither prior literal representation wins. ARCH1's mirroring statement is withdrawn as authority,
DESIGN's independence requirement is kept, and the canonical replacement is a structural predicate
that needs no enum.

## 9. What this amendment does not authorize

```text
Step 66D-BE1 implementation start   -- BE1 resumes only after this amendment is canonicalized
migration creation                  -- none in this stage
delivery_review_tasks table         -- not created
repository / ORM model              -- not created
API / router / frontend             -- not created
event, outbox, read model           -- not created
TASK_ROLES or identity change       -- none
shared, staging or production DB    -- not applied
```

```text
STEP66D_BE1_CR1:                 documentation only
66D_D05:                         DOCUMENTED / PROPOSED FOR CANONICAL MERGE
BE1_IMPLEMENTATION:              PAUSED
MIGRATION:                       NOT STARTED
SHARED_DB:                       NOT APPLIED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
