# AT-D23 — AT-M3.6A Observability / Read Surface product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.6A (observability / read surface) and authorizes
> merging the exact independently validated candidate into `main`. Authorizes no real external LLM
> call (M3.6B), no real work execution (AT-M4), no production action, no live consumer for the
> M3.5 dispatch namespace, no authenticated execution ingress, no HumanApproval mutation, no PCP
> remediation and no P3 backlog work. `production_executed_true_count: 0`.**

```text
AT-D23:                      RESOLVED / BINDING
Recorded_on:                 2026-09-03
Recorded_by:                 Product Owner
Canonical_main_at_decision:  f3a85afb465791457444b93b850014e1faf5d4f3
Validated_candidate:         7a7baaee4f45c2b48579701221d5cd58e063ded8
Implementation_end:          7a7baaee4f45c2b48579701221d5cd58e063ded8
Branch:                      at-m3.6a-observability-read-surface-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D22 (docs/decisions/at-d22-at-m3-5-acceptance-and-merge-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes create a later branch tip; `Implementation_end` does not
move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A.
It said nothing about accepting a specific AT-M3.6A implementation or merging one into `main`, and
AT-D22 section 4 was explicit that AT-M3.6A "still needs its own implementation report and its own
validation pass before it can be accepted the way AT-M3.5 is accepted here". This record is that
separate authorization: the Product Owner accepts the AT-M3.6A capability — the autonomous runtime
exposed as a coherent, entity-level, strictly read-only product model — as independently validated,
and approves canonicalizing the exact validated candidate.

Same shape as AT-D13 for AT-M2, AT-D15 for AT-M3.1, AT-D19 for AT-M3.2, AT-D20 for AT-M3.3, AT-D21
for AT-M3.4 and AT-D22 for AT-M3.5: implementation authority and merge authority are separate
decisions, and the second one names the commit. It is the only place the AT-M3.6A acceptance and
merge authorization is recorded.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
an ADDITIVE read surface at /operations/autonomy/*, inside the existing operational read domain
one primary read domain -- no competing /observability authority is created
six public endpoints, every one of them GET; no POST, PUT, PATCH or DELETE exists at all
PostgreSQL as the only source of read truth; Redis is not consulted and is not required
zero read-induced canonical database mutation -- measured, not asserted
zero read-induced Redis publish
zero read-induced business audit event; viewing a page is not a decision
Goal -> Project -> primary WorkItem lineage, resolved through canonical FK identity
team roster observability, including members who have left, with membership state
discussion observability -- seats in speaking order, matched capabilities, the router's own
    selection reason, bounded turn summaries, convergence state and stop reason
TeamDecision visibility, including unresolved dissent
the current accepted PlanRevision with its own structured PlanContent
historical / superseded PlanRevision navigation, with what each revision actually dispatched
current vs historical execution-graph separation, never conflated
an entity-level execution graph -- unit, work item, revision, step, state, assignment, dispatch
dependency topology as stable identifiers, both depends_on and unlocks, never as prose
routing / assignment explanation from recorded AT-M2 evidence, without model reasoning
a closed, derivable blocker vocabulary carrying the canonical stored value alongside each code
a DERIVED, NON-AUTHORITATIVE autonomy phase with documented deterministic precedence
current-plan progress derivation, with the completion formula stated in the payload
next-work visibility as read-only data; the scheduler is never called from a GET
control-stream dispatch truth -- DISPATCHED_TO_CONTROL_STREAM, never EXECUTING
terminal AT-M3.5 state labelled execution_mode = internal_control_plane_simulation
safe reasoning metadata only -- verb, provider, mode, status, attempt, timing, sanitized failure
no reasoning artifact body, no attempt_token, no raw prompt, completion, CoT or scratchpad
a bounded, Goal-scoped audit timeline whose scope is built from that Goal's OWN identifiers
the timeline stated as EVIDENCE, not authority, with nothing synthesised from current state
deterministic ordering with a stable secondary key on every collection
bounded pagination on every collection, capped; no unbounded "every event ever" endpoint
migration 043 -- one index, index-only, evidence-backed query optimization, reversible
additive compatibility with every existing /operations contract; nothing renamed or removed
explicit response models; no raw database row dictionary is the public contract
truthful partial state -- no discussion, no plan, no graph, no assignment, unpublished dispatch,
    cancelled lineage and superseded graph are all answers, never 500s
no new runtime authority -- no observability table, no phase column, no percent-complete column
no live provider and no external network path
no AT-M4 execution capability
HumanApproval surfaced read-only and never mutated
no production action
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               7a7baae into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded product and source-of-truth checks only
```

## 4. What is NOT authorized

```text
AT-M3.6B / real external LLM   NOT AUTHORIZED -- unchanged from AT-D14 and AT-D22; no path to one
                                  is added, and AT-M3.6A reads local canonical data only
External model credentials     NOT AUTHORIZED
AT-M4 implementation           NOT AUTHORIZED -- real work execution, DebugAttempt and the
                                  debug -> replan back-edge all remain out of scope. AT-M3.6A
                                  observes the M3.5 control plane; it executes nothing and it
                                  makes nothing executable
Live M3.5 dispatch consumer    NOT AUTHORIZED -- the namespace intentionally still has no reader,
                                  and this record does not create one
Authenticated execution ingress NOT AUTHORIZED -- mTLS, JWT, API keys, signed callbacks and bearer
                                  completion tokens all remain out of scope. The identifiers this
                                  read surface publishes -- correlation ids, principal ids, routing
                                  decision ids -- are IDENTIFIERS, not credentials, and nothing in
                                  the system grants authority on the strength of holding one
Production action              NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization       NOT GRANTED -- unchanged
Frontend / Admin Console work  NOT AUTHORIZED by this record -- AT-M3.6A deliberately shipped no
                                  UI. The read model is sufficient for a later Codex/Admin Console
                                  slice, and that slice needs its own authorization
P3 backlog remediation         NOT AUTHORIZED by this record -- see section 6
PCP remediation                NOT AUTHORIZED by this record
Step 66 stage-freeze guards    NOT AUTHORIZED for repair by this record -- see section 7
Unrelated runtime changes      NOT AUTHORIZED -- this record covers AT-M3.6A acceptance and its
                                  merge only
```

## 5. Validation evidence — recorded here, not re-run by this decision

AT-M3.6A went through the bounded remediation policy AT-M1 established and AT-D18 restated. It did
not need it:

```text
AT-M3.6A-OBSERVABILITY-READ-SURFACE-1 (implementation, 7a7baae): READY_FOR_INDEPENDENT_VALIDATION.

  A read-only projection over the canonical AT-M2 / AT-M3.1-3.5 tables, mounted inside the existing
  /operations domain rather than beside it, deriving what it derives on every read and persisting
  none of it.

  Three load-bearing product truths were resolved from the accepted architecture rather than
  escalated. Currency, phase, progress and blockers are DERIVED at read time, exactly as
  planning-and-plan-revision-model.md 11b keeps plan currency a function of lineage -- a stored
  phase or percent-complete column would have been this project's first second answer to a question
  the runtime tables already answer. A dispatch is reported as DISPATCHED_TO_CONTROL_STREAM and can
  never be reported as EXECUTING, because the AT-M3.5 namespace has no consumer. A terminal unit
  carries execution_mode = internal_control_plane_simulation, because AT-M4 does not exist and
  record_internal_result is an internal seam with no public route.

  A fourth was found and corrected during implementation: the MATERIALIZED phase first meant "every
  unit is blocked", which AT-M3.5 cannot produce -- a validated plan is a DAG, so it always has a
  root and materialization leaves that root ready. It now means "no unit has been routed yet".

AT-M3.6A-INDEPENDENT-VALIDATION-1: PASS. No blocker. No remediation required, and no Validation 2.

  Read-only was verified by measurement rather than by inspection: row counts for twenty canonical
  tables PLUS content digests for the seven carrying mutable columns, snapshotted around repeated
  reads of every endpoint, with zero delta -- including updated_at, published_at and audit_ref,
  which a COUNT alone would not have caught. The absence of Redis from the read path was verified by
  breaking it: the event bus was replaced with a class that raises on construction for the duration
  of a read. The store's SELECT-only contract was verified by parsing rather than grepping, because
  these modules discuss at length the writes they do not perform and a text scan would have flagged
  their own explanation.

  Migration 043's need was verified against a real PostgreSQL at 200,243 audit_logs rows: one
  bounded timeline page went from Parallel Seq Scan / cost 6781.81 / 5,516 shared buffers /
  27.062 ms to Bitmap Index Scan / cost 428.72 / 23 shared buffers / 0.033 ms. Every other
  high-value query already resolved through an existing index, and none was added for it.

  One P3 observation was raised and is carried as backlog rather than remediated -- see section 6
  item 1.
```

Independent Validation 1 was a PASS and is recorded as a PASS. This record does not claim the
validation was performed by the acceptance or merge step — it was performed independently, before
this decision, and this record states its result rather than re-deriving it.

## 6. Retained non-blocking backlog

Recorded here so they are not rediscovered as if new. None blocks AT-M3.6A acceptance or this merge,
and none is authorized for remediation by this record.

```text
1  AutonomyReadStore._session() recurses into itself instead of opening a private connection when
   no shared connection is open. The intended fallback -- connect, yield, close -- was overwritten
   during the session refactor, so the `self._shared is None` branch reads
   `async with self._session() as conn: yield conn`.

   It is unreachable on every shipped product path: all six service entry points
   (goal_overview, plan_revision_history, execution_graph, execution_unit, goal_timeline,
   discussion_reasoning) open `async with self.store.session():` before issuing any query, which
   sets `_shared` first, so the recursive branch is never taken. The 77 AT-M3.6A tests exercise all
   six endpoints against a real database and pass. What the defect costs today is that a future
   caller using AutonomyReadStore directly, without a session, would recurse rather than connect.

   Disposition: P3 / PRODUCT_HARDENING / CURRENT_PRODUCT_PATH_UNREACHABLE / NON_BLOCKING

2  A privileged raw-SQL DELETE of goal_execution_lineage (or of the other three AT-M3.5 tables) can
   discard the plan-step mapping that migration 042's fail-closed DOWN exists to protect, and so
   re-enable the DOWN -> UP -> materialize duplicate-rematerialization scenario by a different
   route. The product API exposes no such path; reaching it requires direct database privilege.

   Disposition: P3 / DB_HARDENING / OUTSIDE_PRODUCT_API_CONTRACT / NON_BLOCKING

3  `reasoning_invocations.artifact` (JSONB) has no explicit size bound. Harmless under the
   deterministic mock provider in use today; worth a decision before a live provider can write
   into the column. AT-M3.6A does not read that column at all, which narrows the exposure but does
   not close it.

   Disposition: PRE-M3.6B / PRODUCT_HARDENING / NON_BLOCKING

4  `PlanContent` has no global step-count bound. Inherited from AT-M3.2, unchanged by this slice.
   AT-M3.6A bounds its own reads of the resulting units at 500 per page, which limits what a large
   plan can do to a single response but does not bound the plan itself.

   Disposition: PRE-M3.6B / PRODUCT_HARDENING / NON_BLOCKING
```

Items 2, 3 and 4 are carried forward unchanged from AT-D22 section 6. Under AT-D18-R05 all four are
`NON-BLOCKING` by default: none reaches a production-authorization, human-approval, external-model,
secret-handling, destructive-action, audit-integrity or security-boundary control that is exposed
through the product API. They become blocking only on concrete P0/P1 evidence, which does not exist
today.

The six AT-M3.3 observations recorded in AT-D20 section 7, the four AT-M3.2 observations recorded in
AT-D19 section 6, and the one AT-M3.1 observation recorded in AT-D15 are unchanged and are not
restated here.

## 7. One GOVERNANCE_DRIFT_ALERT, and one class of failure deliberately left alone

AT-M3.6A raised a single `GOVERNANCE_DRIFT_ALERT`, at P3 / CONTINUE, recorded in full in
`source/progress.md`. `tests/test_at_m3_5_migration_lifecycle.py::
test_no_canonical_migration_001_through_041_was_changed_by_this_slice` asserted that the
`migrations/` diff against AT-M3.5's canonical main equalled *exactly* the two 042 files — a
stronger claim than the test's own name makes, since it also said "and no later migration exists
anywhere in the repository". Every future slice's first migration therefore failed an AT-M3.5 test.

This is the same defect AT-M3.4's numbering assertion had, amended in `72b7a28` for the same stated
reason: a repository-wide claim living inside a slice-scoped file. The assertion was amended in
place to assert what its name says — no migration at or below 041 appears in the diff, and
AT-M3.5's own 042 pair is present and unrenamed. Changing a canonical migration still fails it, and
no AT-M3.5 contract, schema, constraint, trigger or behaviour was touched.

Separately, three tests fail on the candidate that do not fail on canonical main:
`test_design_66ui4_fe1c_overview_brief::test_no_runtime_paths_changed`,
`test_design66ui4_fe1d_navigation_microcopy::test_no_runtime_paths_changed` and
`test_stage_gate_compliance::test_verifier_marker_pass`. Each runs
`git diff --name-only origin/main...HEAD` and fails if any path under `apps/`, `shared/`,
`migrations/`, `infra/`, `services/` or `database/` appears, so on canonical main they pass
vacuously and on any implementation branch they fail. This was demonstrated rather than argued: a
branch cut from `f3a85af` whose only change is one empty `shared/sdk/probe_only/__init__.py` fails
precisely those three and nothing else.

They are Step 66UI.4 / Step 66GOV.1 stage-scoped freeze guards, they carry no P0/P1 risk, and they
are **not** repaired by this record. Amending another stage's governance artifact from an AT-M3
product slice would be reaching into that stage's authority to make this slice's number look
better, which is the drift AT-D18 exists to prevent.

## 8. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize external model credentials
Does NOT authorize AT-M4 or any real work execution
Does NOT authorize a live consumer for the stream.plan_delegation namespace
Does NOT authorize an authenticated agent execution ingress, an auth framework, a bearer completion
   token or a signed callback
Does NOT authorize any frontend or Admin Console implementation against this read model
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14, AT-D20, AT-D21 or AT-D22
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, exemption mechanism, reconciliation daemon, decision-discovery
   or canonical-activation mechanism
Does NOT remediate any observation in section 6
Does NOT repair the Step 66 stage-freeze guards described in section 7
Does NOT decide whether AT-M3.6B or AT-M4 is the next product stage -- that is a separate Product
   Owner decision and no record in this repository makes it
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
