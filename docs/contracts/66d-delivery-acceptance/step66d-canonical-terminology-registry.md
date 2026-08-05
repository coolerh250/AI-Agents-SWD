# Step 66D — Canonical Terminology Registry

> **Terminology alignment only. No contract frozen, no schema defined, no implementation authorized.
> `production_executed_true_count: 0`.**

Authoritative for Step 66D vocabulary as of 2026-08-04, per
`docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md`.

---

## Review Gate Action

```text
Canonical definition:
  One of exactly six workflow moves a reviewer may take on a delivery submission:
  ACCEPT, REJECT, REQUEST_CHANGES, RERUN_QA, ESCALATE, ARCHIVE.

Not to be confused with:
  Product Owner Final Decision. Four of the six actions carry no final decision at all.

Authoritative source:
  66D-D01

Future implementation owner:
  Step 66D-ARCH (contract), Step 66D backend slices (implementation) -- NOT AUTHORIZED
```

## Product Owner Final Decision

```text
Canonical definition:
  One of exactly three authoritative outcomes recorded by the Product Owner:
  ACCEPTED, ACCEPTED_WITH_FOLLOW_UP, REJECTED.

Not to be confused with:
  Review Gate Action; delivery review status; approval of production, security, identity,
  deployment or secret provisioning.

Authoritative source:
  66D-D01, 66D-D02

Future implementation owner:
  Step 66D-ARCH (contract) -- NOT AUTHORIZED
```

## Delivery Review Status

```text
Canonical definition:
  The workflow state of a delivery submission: DRAFT, SUBMITTED, UNDER_REVIEW, CHANGES_REQUESTED,
  QA_RERUN_REQUESTED, ACCEPTED, REJECTED, ARCHIVED, EXPIRED. Its ACCEPTED and REJECTED values are a
  projection of the current effective Product Owner Final Decision.

Not to be confused with:
  The authoritative decision record. The status is a projection; ProductOwnerDecision is the record.

Authoritative source:
  66D-D02

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## DeliverySubmission

```text
Canonical definition:
  The new human-acceptance aggregate: what was submitted for human review, with its evidence
  references and its execution lineage.

Not to be confused with:
  The legacy DeliveryPackage (Platform Ops evidence object). DeliverySubmission may reference it via
  `legacy_delivery_package_refs`, but is not it.

Authoritative source:
  66D-D04

Future implementation owner:
  Step 66D-ARCH (contract), Step 66D backend slices -- NOT AUTHORIZED
```

## DeliveryReviewTask

```text
Canonical definition:
  The human-review anchor. Owns the Delivery Inbox queue entry, reviewer assignment, the human
  review workflow, and TASK_ROLES authorization.

Not to be confused with:
  The Agent execution source of truth. Execution is anchored on project -> work item ->
  workflow -> run, never on a task.

Authoritative source:
  66D-D03

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## DeliveryReviewAction

```text
Canonical definition:
  A recorded instance of a Review Gate Action, with actor, reason, timestamp and audit reference.

Not to be confused with:
  ProductOwnerDecision. An ACCEPT action and the ACCEPTED decision it carries are two records.

Authoritative source:
  66D-D01

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## ProductOwnerDecision

```text
Canonical definition:
  The immutable authoritative record of a Product Owner Final Decision, replaceable only through
  `supersedes_decision_id`, never deleted, never overwritten in place.

Not to be confused with:
  Delivery review status; an approval of any other kind; an Agent completion marker.

Authoritative source:
  66D-D02

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## AcceptanceFollowUpItem

```text
Canonical definition:
  A follow-up raised by a Product Owner Final Decision, each classified blocking or non-blocking.

Not to be confused with:
  A rejection. ACCEPTED_WITH_FOLLOW_UP may carry only non-blocking items.

Authoritative source:
  66D-D02

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## DeliveryPackage

```text
Canonical definition:
  The legacy Platform Ops evidence package from Step 47 / Stage 49. Fourteen sections, an
  eighteen-check acceptance gate, `human_acceptance_status`, `status = ready_for_review`.
  IMPLEMENTED and operational.

Not to be confused with:
  DeliverySubmission. The legacy object is preserved unchanged and is not the human review
  aggregate.

Authoritative source:
  66D-D04; docs/product/delivery-package-acceptance-gate.md

Future implementation owner:
  unchanged -- no Step 66D slice may modify it
```

## Execution Lineage

```text
Canonical definition:
  project_id -> work_item_id -> workflow_id -> run_id. The Agent execution source of truth, the
  artifact lineage and the requirement traceability lineage.

Not to be confused with:
  The human review anchor.

Authoritative source:
  66D-D03, and binding decision D-1

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## Human Review Anchor

```text
Canonical definition:
  delivery_review_task_id. The anchor for queueing, assignment and TASK_ROLES authorization.

Not to be confused with:
  Execution lineage.

Authoritative source:
  66D-D03

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## Blocking Follow-up

```text
Canonical definition:
  A follow-up item that prevents the delivery from being treated as accepted. Its presence requires
  REQUEST_CHANGES rather than ACCEPTED_WITH_FOLLOW_UP.

Not to be confused with:
  A non-blocking follow-up.

Authoritative source:
  66D-D02 (D02-R7)

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

## Non-blocking Follow-up

```text
Canonical definition:
  A follow-up item that does not prevent acceptance. The only kind permitted under
  ACCEPTED_WITH_FOLLOW_UP.

Not to be confused with:
  A waiver. ACCEPTED_WITH_FOLLOW_UP is not unconditional completion.

Authoritative source:
  66D-D02 (D02-R6)

Future implementation owner:
  Step 66D-ARCH -- NOT AUTHORIZED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
