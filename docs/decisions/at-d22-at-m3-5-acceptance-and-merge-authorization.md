# AT-D22 — AT-M3.5 Plan-driven Delegation and Dynamic Dispatch product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.5 (plan-driven delegation / dynamic dispatch) and
> authorizes merging the exact independently validated candidate into `main`. Authorizes no real
> work execution (AT-M4), no real external LLM call (M3.6B), no production action, no AT-M3.6A
> implementation, no live consumer for the M3.5 dispatch namespace, no authenticated execution
> ingress, no PCP remediation and no P3 backlog work. `production_executed_true_count: 0`.**

```text
AT-D22:                      RESOLVED / BINDING
Recorded_on:                 2026-09-02
Recorded_by:                 Product Owner
Canonical_main_at_decision:  c9f600185bade59a532d64bfe313b1c5c7890387
Validated_candidate:         03ed5748fc5c63860ba76604e92c3682be49dc07
Implementation_end:          03ed5748fc5c63860ba76604e92c3682be49dc07
Branch:                      at-m3.5-plan-driven-delegation-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D21 (docs/decisions/at-d21-at-m3-4-acceptance-and-merge-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes create a later branch tip; `Implementation_end` does not
move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A.
It said nothing about accepting a specific AT-M3.5 implementation or merging one into `main`. This
record is that separate authorization: the Product Owner accepts the AT-M3.5 capability — an
accepted PlanRevision becoming a durable, dependency-ordered, capability-routed work graph whose
ready steps are dispatched over a real broker — as independently validated, and approves
canonicalizing the exact validated candidate.

Same shape as AT-D13 for AT-M2, AT-D15 for AT-M3.1, AT-D19 for AT-M3.2, AT-D20 for AT-M3.3 and
AT-D21 for AT-M3.4: implementation authority and merge authority are separate decisions, and the
second one names the commit. It is the only place the AT-M3.5 acceptance and merge authorization is
recorded.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
one primary autonomous WorkItem per Goal -- goal_execution_lineage, frozen after creation
PlanStep materialized into child project_work_items under that primary WorkItem
a durable execution graph bound to exactly one accepted PlanRevision
exact step_key identity -- uq_peu_revision_step, frozen by trigger
a durable dependency DAG preserved from PlanContent, cycles and empty plans refused
ready/blocked dependency semantics derived from the durable graph, never transitive
capability-CONJUNCTION routing -- an agent must hold every required capability
AT-M2 routing authority reused unchanged, and its decision recorded in agent_routing_decisions
intended_owner_role as a PREFERENCE only, never a filter and never an authority
capability-unavailable fail-closed behaviour with an exact unavailable_reason
production-effect capabilities referred to the unchanged HumanApproval boundary, never routed
one canonical assignment per execution unit
one canonical PostgreSQL dispatch per execution unit -- plan_execution_dispatches, PRIMARY KEY
an isolated transport namespace, stream.plan_delegation.<agent_key>, keyed on a UNIQUE agent_key
Redis at-least-once transport, stated honestly and not disguised as exactly-once
duplicate transport messages carrying the SAME canonical identity -- one correlation id
no real M3.5 execution consumer -- asserted by repository-wide static scan and live broker check
an INTERNAL-only completion seam; no public completion mutation exists at all
canonical identity (principal, correlation id, revision, step) DERIVED from dispatch state
dependency unlock exactly once on completion
stale-plan semantic B -- dispatched work of PlanRevision N may finish
PlanRevision N historical work and its dispatch binding preserved, never rewritten or rebound
no NEW dispatch authorized by a superseded PlanRevision
a successor PlanRevision owning its own graph, its own units and its own work items
cancellation by the existing primary WorkItem -- no second cancellation model
restart / replay idempotency at materialization, assignment, dispatch and completion
migration 042 with a fail-closed DOWN when materialization evidence exists
exactly one canonical dispatch-success audit event per canonical dispatch
no AT-M4 execution capability -- no code, shell, Git, GitHub, deployment or external call path
no live provider and no external network path
no HumanApproval mutation
no production action
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               03ed574 into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded product and source-of-truth checks only
```

## 4. What is NOT authorized

```text
AT-M4 implementation              NOT AUTHORIZED -- real work execution, DebugAttempt and the
                                    debug -> replan back-edge all remain out of scope. AT-M3.5
                                    decides WHAT, WHEN and WHO; HOW is still unbuilt
Live M3.5 dispatch consumer       NOT AUTHORIZED -- the namespace intentionally has no reader
Authenticated execution ingress   NOT AUTHORIZED -- mTLS, JWT, API keys, signed callbacks and
                                    bearer completion tokens all remain out of scope. AT-M4 must
                                    introduce a non-forgeable runtime execution identity before
                                    agent-originated completion can be exposed
M3.6B / real external LLM calls   NOT AUTHORIZED -- unchanged from AT-D14, no path to one is added
External model credentials        NOT AUTHORIZED
Production action                 NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization          NOT GRANTED -- unchanged
AT-M3.6A                          NOT STARTED by this record -- AT-D14 already authorizes the work;
                                    AT-M3.6A (observability / read surface) still needs its own
                                    implementation report and its own validation pass before it can
                                    be accepted the way AT-M3.5 is accepted here
DB hardening / raw-SQL bypass     NOT AUTHORIZED by this record -- see section 6
PCP remediation                   NOT AUTHORIZED by this record
P3 backlog remediation            NOT AUTHORIZED by this record -- see section 6
Artifact/step-count hardening     NOT AUTHORIZED by this record -- see section 6
Unrelated runtime changes         NOT AUTHORIZED -- this record covers AT-M3.5 acceptance and its
                                    merge only
```

## 5. Validation evidence — recorded here, not re-run by this decision

AT-M3.5 went through the bounded remediation policy AT-M1 established and AT-D18 restated:
Validation 1 → at most one remediation → Validation 2, no Validation 3.

```text
AT-M3.5-PLAN-DRIVEN-DELEGATION-1 (implementation, 147707a): READY_FOR_INDEPENDENT_VALIDATION.
  Materialization, dependency DAG, capability routing, canonical dispatch and completion, with all
  five DESIGN_REVIEW_REQUIRED stop conditions resolved from canonical architecture rather than
  escalated: PlanStep maps to a child project_work_items row under one primary Goal WorkItem; a
  superseded PlanRevision authorizes no new dispatch (semantic B); the unlock signal is the
  execution unit's own recorded completion; no Workflow/Run entity is added; and Task remains
  non-authoritative and not required by the lineage.

AT-M3.5-INDEPENDENT-VALIDATION-1: FAIL. Four blockers, none of them a design-premise defect:

  1. Forgeable public completion authority. POST .../result accepted a caller-supplied
     `reported_by` and `correlation_id` and checked them against the canonical dispatch row --
     but this slice's own read routes publish both values, so the check was a lookup, not an
     authorization. Any client able to read a graph could terminalize any dispatched step and
     unlock its dependents.

  2. Legacy agent stream collision. Dispatch published `plan_step.dispatched` onto the selected
     agent's own transport stream -- `stream.development`, `stream.qa`, `stream.design_review`.
     A StreamAgent subclass consumes each of those and calls handle() unconditionally, and the
     orchestrator's workflow-event consumer watches several too. An L3 coordination message
     landing there is AT-M4 execution begun by a stream name.

  3. Migration 042 mapping loss and duplicate rematerialization. DOWN dropped the four AT-M3.5
     tables while deliberately preserving the child project_work_items and their dependency
     edges. Those dropped tables were the ONLY record of which work item is which plan step, so
     DOWN -> UP -> materialize the same accepted PlanRevision was not a replay:
     uq_peu_revision_step had nothing left to collide with, and a second full set of child work
     items and edges was created for the same steps, undetectably.

  4. Duplicate dispatch-success audit claims. Under concurrent schedulers several workers
     legitimately XADD the same canonical dispatch; each then emitted a successful
     plan_step_dispatched event, so the audit chain said the team handed one step over three
     times.

AT-M3.5-IMPLEMENTATION-REMEDIATION-1 (03ed574): the one bounded remediation, closing exactly those
  four and reopening no accepted architecture.

  1. The public completion route was REMOVED rather than hardened. Not hidden identifiers, not
     renamed fields, not a second guessable token -- secrecy standing in for authority fails the
     first time a graph is rendered in an operator console. The write surface is now exactly
     `materialize` and `schedule`. What remains is an internal seam,
     record_internal_result(execution_unit_id, disposition, evidence_ref), which takes no
     principal and no correlation id: the parameters were removed from the service AND from the
     store, so impersonation is unrepresentable rather than detected. Assigned principal,
     correlation id, plan revision and step are read from the unit's own canonical dispatch row.
     This is the same correction AT-M3.4 made when it removed `plan` and `decided_by` from its
     finalize command.

  2. Transport was separated from routing, and only transport moved. AT-M2 still decides WHO from
     capability over the live team and its answer -- including the agent's real transport_stream
     -- is still recorded unchanged in agent_routing_decisions.selected_stream. What changed is
     WHERE the message is staged: stream.plan_delegation.<agent_key>, keyed on agent_key because
     `development-agent` and `development-agent-autofix` share the role `development` and are two
     different workers, and because agent_key is UNIQUE on agent_profiles.

  3. Migration 042's DOWN now counts rows in all four tables and RAISEs before the first DROP when
     any exist, with ERRCODE = restrict_violation; the transaction rolls back and nothing changes.
     There is no force flag, no override and no exemption. Both repairs were rejected on model
     grounds: deleting the work items destroys execution-lineage rows this slice does not own, and
     re-adopting orphans on UP reattaches work whose provenance was deleted. The empty case is
     untouched and UP/DOWN/UP/UP remains clean.

  4. The dispatch-success audit event is gated on the write-once compare-and-swap that
     mark_dispatch_published already performed and whose result was being discarded. A worker
     whose CAS loses publishes its copy and emits nothing. No PostgreSQL row lock is held across
     an XADD to force a single message; AT-M3.4 refused that for the same reason.

AT-M3.5-INDEPENDENT-VALIDATION-2 / 2 FINAL: PASS. All four Validation 1 blockers closed and
  independently reproduced, with no new blocker and no regression against canonical main.
```

Independent Validation 1 was a FAIL and is recorded as a FAIL. This record does not rewrite it, and
does not claim either validation was performed by the acceptance or merge step — both were performed
independently, before this decision, and this record states their results rather than re-deriving
them.

## 6. Retained non-blocking backlog

Recorded here so they are not rediscovered as if new. None blocks AT-M3.5 acceptance or this merge,
and none is authorized for remediation by this record.

```text
1  A privileged raw-SQL DELETE of goal_execution_lineage (or of the other three AT-M3.5 tables) can
   discard the plan-step mapping that migration 042's fail-closed DOWN exists to protect, and so
   re-enable the DOWN -> UP -> materialize duplicate-rematerialization scenario by a different
   route. The product API exposes no such path; reaching it requires direct database privilege.

   Disposition: P3 / DB_HARDENING / OUTSIDE_PRODUCT_API_CONTRACT / NON_BLOCKING

2  `reasoning_invocations.artifact` (JSONB) has no explicit size bound. Harmless under the
   deterministic mock provider in use today; worth a decision before a live provider can write
   into the column.

   Disposition: PRE-M3.6B / PRODUCT_HARDENING / NON_BLOCKING

3  `PlanContent` has no global step-count bound. Inherited from AT-M3.2, unchanged by this slice.

   Disposition: PRE-M3.6B / PRODUCT_HARDENING / NON_BLOCKING
```

Items 2 and 3 are carried forward unchanged from AT-D21 section 6. Under AT-D18-R05 all three are
`NON-BLOCKING` by default: none reaches a production-authorization, human-approval, external-model,
secret-handling, destructive-action, audit-integrity or security-boundary control that is exposed
through the product API. They become blocking only on concrete P0/P1 evidence, which does not exist
today.

The six AT-M3.3 observations recorded in AT-D20 section 7, the four AT-M3.2 observations recorded in
AT-D19 section 6, and the one AT-M3.1 observation recorded in AT-D15 are unchanged and are not
restated here.

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M4 or any real work execution
Does NOT authorize a live consumer for the stream.plan_delegation namespace
Does NOT authorize an authenticated agent execution ingress, an auth framework, a bearer completion
   token or a signed callback
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize AT-M3.6A implementation -- AT-D14 already authorizes that work; this record
   accepts and merges AT-M3.5 only
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT modify, read or bypass the HumanApproval boundary
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14, AT-D20 or AT-D21
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, exemption mechanism, reconciliation daemon, decision-discovery
   or canonical-activation mechanism
Does NOT remediate any observation in section 6
Does NOT rewrite AT-M3.5 Independent Validation 1 as a PASS
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
