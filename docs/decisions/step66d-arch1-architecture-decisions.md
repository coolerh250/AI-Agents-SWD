# Step 66D-ARCH1 — Architecture Decisions

> **Decision records only. Nothing implemented. `production_executed_true_count: 0`.**

Baseline: canonical main `ccfee8ef47f72d5d67ea6bb58845018f306cfa0c`. None of these ADRs conflicts
with the binding decisions 66D-D01 through 66D-D04; each either implements one or resolves a
question those decisions deliberately left open.

---

## ADR-66D-01 — Review Gate Action and Product Owner Final Decision are separate

**Status:** ACCEPTED · implements 66D-D01

**Context.** Two vocabularies were live on `main`: a six-action review gate and a three-value
Product Owner decision. Collapsing them loses either the four actions that are not outcomes, or the
distinction between "reviewed" and "decided".

**Decision.** They are separate contracts: different enum, schema, record, durable event, audit
action name and authorization check. Only `ACCEPT` and `REJECT` map to a final decision; the other
four map to none.

**Consequences.** Two tables and two event families instead of one. In exchange, `ESCALATE` can
never be mistaken for a decision, and the audit trail distinguishes who reviewed from who decided.

---

## ADR-66D-02 — The decision record is immutable and supersedable

**Status:** ACCEPTED · implements 66D-D02

**Context.** A Product Owner sometimes changes their mind. Overwriting the decision destroys the
record of what was originally decided and on what evidence.

**Decision.** `ProductOwnerDecision` is append-only. Never updated in place, never deleted. A
change is a new row with `supersedes_decision_id`. Superseded decisions stay visible and queryable.

**Consequences.** Reading "the decision" requires resolving the effective row. That cost is
accepted; it is the price of an auditable history.

---

## ADR-66D-03 — Delivery review status is a projection

**Status:** ACCEPTED · implements 66D-D02

**Context.** `ACCEPTED` and `REJECTED` appear as delivery review statuses. If status were the
source of truth, it would contradict ADR-66D-02.

**Decision.** Status may carry `ACCEPTED` / `REJECTED`, but only as a **projection** of the current
effective decision. It is derived and may be rebuilt; it is never authoritative.

**Consequences.** Status and decision can be compared, and a divergence is a detectable bug rather
than an ambiguity.

---

## ADR-66D-04 — Dual-anchor execution and review model

**Status:** ACCEPTED · implements 66D-D03

**Context.** Execution traceability wants `project -> work item -> workflow/run`. Human review and
RBAC want a Task. Forcing one to serve both breaks either lineage or accountability.

**Decision.** Both. Execution lineage stays on project/work-item/workflow/run.
`delivery_review_task_id` anchors human review and TASK_ROLES. Task is **not** the Agent execution
source of truth; Step 66SYNC.1 binding decision D-1 is preserved intact.

**Consequences.** A `DeliverySubmission` carries both anchors. Slightly more linkage, no
ambiguity about which system owns which fact.

---

## ADR-66D-05 — Legacy DeliveryPackage is preserved, not repurposed

**Status:** ACCEPTED · implements 66D-D04

**Context.** `DeliveryPackage` is an implemented Step 47/49 object with an API, a UI page, an
agent, a migration and an acceptance gate. Its `human_acceptance_status` is a single mutable
string.

**Decision.** It stays exactly as it is, as the Platform Ops evidence object. The new
human-acceptance aggregate is `DeliverySubmission`, which may reference legacy packages via
`legacy_delivery_package_refs`. A legacy package may never act as the review aggregate.

**Consequences.** Two objects coexist. That is deliberate: a single mutable status string cannot
satisfy ADR-66D-02, so reusing it would silently break the immutability guarantee. Migration is a
separate, separately authorized design.

---

## ADR-66D-06 — Artifact provenance is mandatory

**Status:** ACCEPTED

**Context.** A reviewer accepting work needs to know who or what produced each artifact, and
whether it was generated, templated or hand-written.

**Decision.** Every artifact records `producer_actor_ref`, `generation_mode` and `content_hash`.
External AI partners are `actor_type: ai_partner`, never `runtime_agent`. The first POC forbids
`future_autonomous_runtime_generated`, runtime patch/test generation, automatic patch application
and autonomous merge.

**Consequences.** Provenance must be captured at creation time. Artifacts without it are not
acceptable evidence.

---

## ADR-66D-07 — Acceptance does not imply production approval

**Status:** ACCEPTED

**Context.** "Accepted" reads like "ship it". The platform has separate production, security,
identity and deployment gates that acceptance must not short-circuit.

**Decision.** An `ACCEPTED` decision authorizes nothing. It does not grant production approval,
security approval, identity activation, secret provisioning, deployment, external provider calls,
GitHub writes, notifications, resume/replay or feature-gate activation.

**Consequences.** Every audit record from this contract carries `production_executed = false`, and
`production_executed_true_count` stays 0.

---

## ADR-66D-08 — Durable events use a transactional outbox

**Status:** ACCEPTED

**Context.** Publishing an event inline with a decision risks either a lost event or an event for a
transaction that rolled back.

**Decision.** Delivery events are written to a transactional outbox inside the same transaction as
the state change. An API response must not report success before the outbox row is persisted. The
repository already uses this pattern for the clarification path; this reuses it.

**Consequences.** A relay is required before events are observable. Relay, consumers and runtime
activation are explicitly out of scope for this stage.

---

## ADR-66D-09 — One bounded QA rerun per DeliverySubmission version

**Status:** ACCEPTED · resolves the bound Step 66D-ALIGN1 deliberately left open

**Context.** `RERUN_QA` asks for re-verification without content changes. Unbounded, it lets a
review loop forever without ever producing a decision. Step 66D-ALIGN1 recorded that the numeric
bound was not its to choose; this stage is authorized to choose it.

**Decision.**

```text
Limit            1 RERUN_QA action per DeliverySubmission version
Requires         reason, QA scope, previous QA reference
Flow             first legal call -> QA_RERUN_REQUESTED; new QA result -> UNDER_REVIEW
Second attempt   409 QA_RERUN_LIMIT_REACHED
Then allowed     REQUEST_CHANGES, ESCALATE, REJECT
Reset            a new submission version restores the allowance
Counter source   authoritative persisted actions, never a UI or client counter
Bypass           replaying the same request must not create a second action
```

**Consequences.** A reviewer who needs more than one rerun must escalate, request changes, or
reject — each of which is visible. The loop is bounded by construction rather than by convention.

---

## ADR-66D-10 — ACCEPT/REJECT action and final decision are atomically persisted

**Status:** ACCEPTED · implements 66D-D01 and 66D-D02 jointly

**Context.** If the review action and the decision are written separately, a partial failure leaves
a recorded `ACCEPT` with no decision — visibly reviewed, invisibly undecided.

**Decision.** `ACCEPT` and `REJECT` write the `DeliveryReviewAction`, the `ProductOwnerDecision`,
the status projection, any non-blocking follow-ups, the durable events and the audit records in
**one transaction**. Replaying an idempotency key returns the original result and creates nothing.
Concurrent decisions are resolved by row version CAS.

**Consequences.** No persisted state can exist where an `ACCEPT` action has no corresponding final
decision. This is the strongest structural guarantee in the contract, and the verifier checks it.

---

## Conflicts

```text
Conflicts with 66D-D01..D04 found:   0
New material canonical conflicts:    0
Remaining Product Owner decisions:   POC Control Center IA (Unified vs Coordinated) -- STILL OPEN,
                                     owned by Step 67POC.0 / Step 66D-DESIGN
                                     Legacy DeliveryPackage migration -- deferred
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
