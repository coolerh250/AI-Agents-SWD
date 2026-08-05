# Step 66D-ARCH1 — Delivery and Product Owner Acceptance Contract Freeze

> **Architecture contract only. Nothing in this document is implemented. No runtime, frontend,
> backend, API, database, event, migration, deployment, identity, secret or feature-gate change.
> No container, database, Redis, Kubernetes, Vault, OIDC provider, agent workflow or external
> provider started. `production_executed_true_count: 0`.**

```text
Canonical baseline:  main ccfee8ef47f72d5d67ea6bb58845018f306cfa0c
Binding decisions:   66D-D01, 66D-D02, 66D-D03, 66D-D04 (RESOLVED / BINDING / CANONICALIZED)
Marker:              STEP66D_ARCH1_CONTRACT_FREEZE_VERIFY: PASS
```

## 1. What this freeze is for

Step 66D-ALIGN1 resolved *what the vocabulary means*. This stage fixes *what gets built*, so that
Claude Design, Codex and Claude Code can work from one set of contracts instead of three readings.

It answers, and freezes answers to, these questions:

```text
What is the delivery aggregate?                     DeliverySubmission (section 3)
How does it join Project/Work Item/Workflow/Run?    Dual anchor (section 4)
How does human review attach?                       DeliveryReviewTask + TASK_ROLES (section 4, 8)
How does a Review Gate Action work?                 Six actions, no final decision except 2 (5)
How is a Product Owner Final Decision kept?         Immutable ProductOwnerDecision (section 6)
How are requirement/artifact/QA/decision traced?    Nine-link chain (section 7)
Which APIs, events and audit records are required?  api-event-audit-contracts.md
How are duplicate decisions and infinite QA rerun   Idempotency, CAS, one rerun per version (9)
prevented?
How is legacy DeliveryPackage preserved?            Reference-only, unchanged (section 10)
What read model does the Control Center need?       read-model-and-security-boundary.md
How is implementation decomposed?                   Eight slices, none authorized (section 11)
```

## 2. Binding baseline, restated not re-decided

The four decisions below were canonicalized into `main` by Step 66D-ALIGN1-M1 (merge `ad2d218`).
This stage **implements them as contracts**; it does not reopen them.

```text
66D-D01  Review Gate Action (6) and Product Owner Final Decision (3) are separate contracts,
         with different schema, record, event, audit action and authorization check.
66D-D02  Delivery review status may PROJECT a decision. The authoritative record is an
         immutable ProductOwnerDecision, replaceable only by supersession.
66D-D03  Execution lineage is project -> work item -> workflow/run. Human review anchors on
         DeliveryReviewTask. Task is NOT the Agent execution source of truth.
66D-D04  Legacy DeliveryPackage is preserved as the Step 47/49 Platform Ops evidence object.
         The new human-acceptance aggregate is DeliverySubmission.
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

### Mapping

| Review Gate Action | Product Owner Final Decision | Creates decision record |
| ------------------ | ---------------------------- | ----------------------- |
| ACCEPT | ACCEPTED or ACCEPTED_WITH_FOLLOW_UP | yes |
| REJECT | REJECTED | yes |
| REQUEST_CHANGES | none | no |
| RERUN_QA | none | no |
| ESCALATE | none | no |
| ARCHIVE | none | no |

Exactly four actions carry no final decision. The two enums share no value.

## 3. The aggregate

`DeliverySubmission` is the unit a Product Owner accepts or rejects. It is versioned, never edited
in place after submission, and carries its own evidence rather than pointing at mutable state.

Full field contract: `step66d-arch1-domain-and-state-model.md` section 1.

```text
Authoritative source:  DeliverySubmission row (future persistence, NOT implemented)
Identity:              delivery_submission_id
Versioning:            submission_version + supersedes_submission_id
Concurrency:           row_version, optimistic CAS
Immutability:          content frozen at SUBMITTED; changes require a new version
Retention:             retained with the project; decisions outlive submissions
```

## 4. Dual anchor

```text
Execution lineage (artifacts, traceability, agent work):
    project_id -> work_item_id -> workflow_id -> run_id

Human review and RBAC anchor:
    delivery_review_task_id  ->  task_id  ->  TASK_ROLES
```

A `DeliverySubmission` carries **both**. The execution lineage says what produced the work; the
review task says who is accountable for judging it. Neither substitutes for the other, and per
66D-D03 the Task is not the Agent execution source of truth — binding decision D-1 from
Step 66SYNC.1 is preserved intact.

## 5. Review Gate Action semantics

Every action is recorded as a `DeliveryReviewAction`. Four of the six never produce a decision.

```text
ACCEPT           terminal for this version; MUST atomically create a ProductOwnerDecision
REJECT           terminal for this version; MUST atomically create a ProductOwnerDecision
REQUEST_CHANGES  no decision; requires a new submission version to proceed
RERUN_QA         no decision; no content change requested; bounded to once per version
ESCALATE         no decision; creates an escalation record; status stays UNDER_REVIEW
ARCHIVE          no decision; only for terminal, expired or superseded submissions
```

`ESCALATE` must not be presented, stored or audited as a final decision. It is explicitly not an
outcome; it is a request for a different decider.

## 6. Decision record

```text
ProductOwnerDecision is append-only.
It is never updated in place and never deleted.
A correction is a NEW decision row with supersedes_decision_id set.
Delivery review status ACCEPTED / REJECTED is a PROJECTION of the current effective decision.
The projection is derived, never the source of truth.
```

`ACCEPTED_WITH_FOLLOW_UP` carries only **non-blocking** follow-ups. If any follow-up is blocking,
the command is rejected with `409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES` and the correct action is
`REQUEST_CHANGES`. This is what stops "accepted, but actually not done" from becoming a state.

## 7. Requirement traceability

```text
Requirement
  -> Acceptance Criterion
    -> Work Item
      -> Execution (workflow/run)
        -> Artifact
          -> QA Evidence
            -> DeliverySubmission Item
              -> Review Action
                -> Product Owner Decision
```

Acceptance criterion results are `PASS`, `FAIL`, `PARTIAL`, `NOT_TESTED`, `NOT_APPLICABLE`, each
with `assessor_actor_ref`, `assessed_at`, `reason` and `evidence_refs`.

**Agent completion never implies PASS.** A run finishing is evidence that work happened, not
evidence that a criterion is met. An assessment requires an assessor.

## 8. Authorization boundary

Existing `TASK_ROLES` on `main` (`shared/sdk/tasks/rbac.py`) are:

```text
requester  pm_engineering_lead  reviewer_approver  platform_admin
agent_operator  security_compliance_reviewer
```

Contract for this stage — **specification only, no RBAC code is modified here**:

```text
reviewer_approver              REQUEST_CHANGES, RERUN_QA, ESCALATE, read evidence
pm_engineering_lead            ACCEPT, REJECT, ARCHIVE, record ProductOwnerDecision,
(designated Product Owner)     manage non-blocking follow-ups
```

`ACCEPT` and `REJECT` require a **verified human actor** holding Product Owner decision capability.
Request-supplied actor or role fields are never authoritative identity.

```text
POC sandbox/test operator identity     available today, NOT a verified shared-runtime identity
Verified shared-runtime identity       decided by RA-2 (RA2-D01..D12), NOT implemented
```

Acceptance is **not** production approval, security approval, identity activation approval, secret
provisioning approval, or deployment approval. Those remain separate gates (ADR-66D-07).

## 9. Bounded QA rerun

```text
ADR-66D-09: One bounded QA rerun per DeliverySubmission version.

Limit:          1 RERUN_QA action per submission version
Counter source: authoritative persisted DeliveryReviewAction rows, never a UI or client counter
Second attempt: 409 QA_RERUN_LIMIT_REACHED
Then allowed:   REQUEST_CHANGES, ESCALATE, REJECT
Reset:          a new DeliverySubmission version gets a fresh allowance
Bypass:         replaying the same request must not create a second action (idempotency key)
```

This is the numeric bound Step 66D-ALIGN1 deliberately refused to invent. It is decided here, by
this authorized stage, and recorded as an ADR.

## 10. Legacy compatibility

```text
DeliveryPackage     legacy Platform Ops evidence object (Step 47/49) -- UNCHANGED
DeliverySubmission  new human-acceptance aggregate -- NEW CONTRACT
```

A `DeliverySubmission` may reference legacy packages through `legacy_delivery_package_refs`. A
legacy `DeliveryPackage` may **not** act as the human review aggregate: its
`human_acceptance_status` is a single mutable string with no decision history, which cannot satisfy
66D-D02. Legacy API and UI semantics do not change in this stage. Any migration is a separate,
separately authorized design.

## 11. Implementation decomposition

```text
Step 66D-DESIGN   UX/IA and interaction specification            NOT AUTHORIZED
Step 66D-BE1      Persistence/domain models and migrations       NOT AUTHORIZED
Step 66D-BE2      DeliverySubmission and ReviewTask APIs         NOT AUTHORIZED
Step 66D-BE3      ReviewAction, PO Decision, follow-up APIs      NOT AUTHORIZED
Step 66D-BE4      Events, outbox, audit, unified read model      NOT AUTHORIZED
Step 66D-FE1      Delivery Inbox / Delivery Review observation   NOT AUTHORIZED
Step 66D-FE2      Review actions, PO decisions, follow-ups       NOT AUTHORIZED
Step 66D-QA       Combined contract/runtime/UI/security check    NOT AUTHORIZED
```

Detail in `docs/handoffs/66d-delivery-acceptance/step66d-arch1-gap-and-implementation-slice-plan.md`.
No slice is authorized by this stage. Authorizing one is a separate Product Owner decision.

## 12. What this stage does not decide

```text
POC Control Center IA        Unified Control Center vs Coordinated Existing Routes -- STILL OPEN,
                             owned by Step 67POC.0 / Step 66D-DESIGN
Legacy migration plan        deferred, needs its own authorization
Verified identity activation owned by RA-2 (RA-2I0 onward), NOT AUTHORIZED
Notification/escalation      routing and channels not specified here
Retention/archival windows   named as a requirement, values not fixed
```

## 13. Status

```text
STEP66D_ARCH1:                   PASS
CONTRACT_FREEZE:                 PREPARED IN PR
MERGED_TO_MAIN:                  NO
STEP66D_DESIGN:                  NOT STARTED / NOT AUTHORIZED
BACKEND_IMPLEMENTATION:          NOT STARTED / NOT AUTHORIZED
FRONTEND_IMPLEMENTATION:         NOT STARTED / NOT AUTHORIZED
STEP67POC0:                      NOT STARTED / NOT AUTHORIZED
RA2I0:                           NOT STARTED / NOT AUTHORIZED
BE3 resume/replay:               DISABLED, all four gates default false
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

`DeliverySubmission` is not implemented. The Delivery Inbox is not implemented. No PO decision API
exists. No migration was written. `TASK_ROLES` was not modified. The POC is not ready.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
