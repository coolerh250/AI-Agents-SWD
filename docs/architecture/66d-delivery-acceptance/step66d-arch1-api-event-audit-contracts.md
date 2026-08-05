# Step 66D-ARCH1 — API, Event and Audit Contracts

> **Specification only. None of these endpoints, events or audit actions exist. Nothing here is
> implemented. `production_executed_true_count: 0`.**

## 1. API contract

Every endpoint below is **NOT IMPLEMENTED**. None may be described as existing.

Common to all endpoints:

```text
authentication      verified actor required; request-supplied actor/role is never authoritative
authorization       capability check against TASK_ROLES (see contract-freeze.md section 8)
idempotency         Idempotency-Key header required on every POST and PATCH
precondition        If-Match / row_version required on every state-changing call
transaction         one transaction per command; durable events via transactional outbox
redaction           no secrets, raw tokens, credentials or private chain of thought in any payload
pagination          cursor-based; filters on project_id, status, review task, decision type
```

### Submission lifecycle

| Method | Path | Capability | Notes |
| ------ | ---- | ---------- | ----- |
| POST | `/delivery-submissions` | create | creates DRAFT |
| GET | `/delivery-submissions` | read | list, filtered, paginated |
| GET | `/delivery-submissions/{submission_id}` | read | single |
| POST | `/delivery-submissions/{submission_id}/items` | create | DRAFT only |
| POST | `/delivery-submissions/{submission_id}/submit` | submit | DRAFT -> SUBMITTED |
| POST | `/delivery-submissions/{submission_id}/withdraw` | submit | pre-decision only |
| GET | `/delivery-submissions/{submission_id}/traceability` | read | the nine-link chain |
| GET | `/delivery-submissions/{submission_id}/evidence` | read | artifacts, QA, source control |
| GET | `/delivery-submissions/{submission_id}/audit` | read | audit trail |

### Review actions

| Method | Path | Capability | Notes |
| ------ | ---- | ---------- | ----- |
| POST | `/delivery-submissions/{submission_id}/review-actions` | review | one of the six actions |
| GET | `/delivery-submissions/{submission_id}/review-actions` | read | append-only history |

`POST /review-actions` with `action_type` `ACCEPT` or `REJECT` **must** create the corresponding
`ProductOwnerDecision` in the same transaction. It is not a two-call flow, and a client must not be
able to leave the system in a state where the action exists without the decision.

### Product Owner decisions

| Method | Path | Capability | Notes |
| ------ | ---- | ---------- | ----- |
| POST | `/delivery-submissions/{submission_id}/po-decisions` | po_decision | verified human only |
| GET | `/delivery-submissions/{submission_id}/po-decisions` | read | full history incl. superseded |
| GET | `/product-owner-decisions/{decision_id}` | read | single, immutable |

### Follow-ups

| Method | Path | Capability | Notes |
| ------ | ---- | ---------- | ----- |
| POST | `/product-owner-decisions/{decision_id}/follow-ups` | po_decision | non-blocking only |
| GET | `/product-owner-decisions/{decision_id}/follow-ups` | read | list |
| PATCH | `/acceptance-follow-ups/{follow_up_id}` | po_decision | status/owner/due only |

## 2. Error semantics

```text
400 INVALID_DELIVERY_SUBMISSION
401 AUTHENTICATION_REQUIRED
403 DELIVERY_REVIEW_ACCESS_DENIED
404 DELIVERY_SUBMISSION_NOT_FOUND
404 REVIEW_TASK_NOT_FOUND

409 DELIVERY_VERSION_CONFLICT
409 DELIVERY_ALREADY_SUBMITTED
409 DELIVERY_NOT_REVIEWABLE
409 DECISION_ALREADY_SUPERSEDED
409 FINAL_DECISION_ALREADY_EXISTS
409 QA_RERUN_LIMIT_REACHED
409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES
409 SUBMISSION_EXPIRED

422 MISSING_REQUIRED_EVIDENCE
422 ACCEPTANCE_CRITERIA_INCOMPLETE
422 INVALID_REVIEW_ACTION
422 INVALID_DECISION_MAPPING

423 DELIVERY_REVIEW_BLOCKED
```

Cross-project and cross-team access is denied and **masked as `404`**, matching the existing BE3
RBAC posture, so that existence is not leaked through a `403`.

No error body may disclose a secret, raw token, private prompt, private chain of thought,
credential identifier or unredacted sensitive evidence.

## 3. Durable event contracts

All events are **NOT IMPLEMENTED**. No producer and no consumer is built in this stage.

```text
delivery.submission.created
delivery.submission.submitted
delivery.submission.expired
delivery.submission.archived
delivery.submission.version_created

delivery.review_action.recorded
delivery.review.accepted
delivery.review.rejected
delivery.review.changes_requested
delivery.review.qa_rerun_requested
delivery.review.escalated
delivery.review.archived

delivery.po_decision.recorded
delivery.po_accepted
delivery.po_accepted_with_follow_up
delivery.po_rejected
delivery.po_decision.superseded

delivery.follow_up.created
delivery.follow_up.updated
delivery.follow_up.closed
```

### Envelope (required on every event)

```text
event_id                 uuid, unique
event_type               from the list above
schema_version           integer
occurred_at              DB authoritative timestamp
project_id               execution lineage
work_item_id             execution lineage
workflow_id              execution lineage
run_id                   execution lineage
delivery_submission_id   aggregate
delivery_review_task_id  human review anchor
review_action_id         nullable
decision_id              nullable
actor_ref                redacted actor reference
correlation_id           end-to-end trace
causation_id             the event or command that caused this one
payload                  event-specific, redacted
audit_ref                audit event id
```

### Delivery semantics

```text
producer candidate    the delivery API service (NOT BUILT)
consumer candidates   audit-service, notification-worker, read-model projector (NONE BUILT)
ordering              per delivery_submission_id; no global ordering assumed
idempotency           consumers key on event_id; duplicate delivery must be safe
retry                 at-least-once; consumers must be idempotent
DLQ                   required; a poisoned delivery event must not block the partition
redaction             applied at production time, not at consumption time
```

## 4. Audit contract

An audit record is required for:

```text
submission creation          artifact attachment           requirements assessment
QA result attachment         submission                    review assignment
every Review Gate Action     every PO final decision       decision supersession
follow-up create/update/close   expiry                     archive
```

Each audit record carries:

```text
verified actor ref     action        target
before state           after state   reason
evidence refs          timestamp     correlation
environment            production_executed
```

```text
production_executed MUST remain false for every record produced by this contract.
```

### Distinct action names

Review actions and PO decisions use **different** audit action names, so the two layers can never
be conflated in the trail:

```text
review_action.accept              po_decision.accepted
review_action.reject              po_decision.accepted_with_follow_up
review_action.request_changes     po_decision.rejected
review_action.rerun_qa            po_decision.superseded
review_action.escalate
review_action.archive
```

## 5. Transactional consistency

```text
1.  ACCEPT + ProductOwnerDecision + status projection + events + audit  -> ONE transaction
2.  REJECT + ProductOwnerDecision + status projection + events + audit  -> ONE transaction
3.  RERUN_QA action + rerun count + status update                       -> ONE transaction
4.  ACCEPTED_WITH_FOLLOW_UP + its follow-up rows                        -> ONE transaction
5.  Durable events are written through a transactional outbox, never published inline
6.  An API response must not report success before the outbox row is persisted
7.  Replaying an idempotency key creates no second action and no second decision
8.  Concurrent decisions are resolved by row_version / CAS; the loser gets
    409 DELIVERY_VERSION_CONFLICT
9.  Outbox relay, consumers and runtime activation are OUT OF SCOPE for this stage
```

A transactional outbox already exists in this repository for the clarification path. This contract
**specifies** that delivery events use the same pattern; it does not implement or wire it.

## 6. Cost and external action contract

```text
provider              operation_type        planned_count
attempted_count       successful_count      failed_count
estimated_cost        actual_cost           currency
environment           authorized_limit      limit_breach
evidence_ref
```

Recorded separately, never aggregated into a single opaque number:

```text
LLM call        GitHub branch      commit
draft PR        notification       other sandbox action
production action
```

```text
production_executed_true_count MUST remain 0.
Acceptance NEVER auto-authorizes any external action.
```

An `ACCEPTED` decision is a statement about the delivered work. It grants no permission to call a
provider, write to GitHub, notify anyone, deploy, or touch production.

## 7. Failure and recovery contract

| Condition | Error | Recovery | PO action |
| --------- | ----- | -------- | --------- |
| artifact missing | 422 MISSING_REQUIRED_EVIDENCE | resubmit with artifact | REQUEST_CHANGES |
| source-control evidence inaccessible | 422 MISSING_REQUIRED_EVIDENCE | re-attach ref | REQUEST_CHANGES |
| QA incomplete | 422 ACCEPTANCE_CRITERIA_INCOMPLETE | complete QA | RERUN_QA or REQUEST_CHANGES |
| QA rerun failed | 422 ACCEPTANCE_CRITERIA_INCOMPLETE | new version | REQUEST_CHANGES |
| QA rerun limit reached | 409 QA_RERUN_LIMIT_REACHED | none | REQUEST_CHANGES / ESCALATE / REJECT |
| acceptance criterion failed | 422 ACCEPTANCE_CRITERIA_INCOMPLETE | new version | REQUEST_CHANGES or REJECT |
| audit evidence missing | 423 DELIVERY_REVIEW_BLOCKED | restore audit | ESCALATE |
| duplicate review action | idempotent replay | return original | none |
| duplicate final decision | 409 FINAL_DECISION_ALREADY_EXISTS | supersede instead | new decision |
| stale submission version | 409 DELIVERY_VERSION_CONFLICT | refetch, retry | none |
| expired submission | 409 SUBMISSION_EXPIRED | new version or reopen | new version |
| partial external partner evidence | 422 MISSING_REQUIRED_EVIDENCE | complete evidence | REQUEST_CHANGES |
| retry/DLQ evidence unavailable | 423 DELIVERY_REVIEW_BLOCKED | restore evidence | ESCALATE |
| identity not verified | 401 / 403 | verified identity required | none until RA-2 |

Each row also defines a user-visible summary (safe, redacted) and an operator-visible detail
(diagnostic, still redacted of secrets).

```text
REJECTED and REQUEST_CHANGES MUST NOT automatically restart an Agent workflow.
Re-execution is a separate, explicitly requested action.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
