# Step 66D-DESIGN — Unified Control Center Information Architecture (FROZEN)

> **Design specification only. No frontend implementation. No backend implementation. No merge. No
> deployment. No runtime, API, database, migration, identity, secret or feature-gate change.
> `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE:        main 9c5210d190b82b76575ba8d456b5d2005c2867d2
BINDING_IA_DECISION:       Unified Control Center
IMPLEMENTATION_PRINCIPLE:  Unified Overview + Existing Route Drill-down
DECISION_AUTHORITY:        Product Owner (binding; recorded in this stage)
66D_D01..D04:              BINDING (restated, not reopened)
ADR66D09:                  BINDING (1 QA rerun per DeliverySubmission version)
STEP66D_DESIGN:            IA FROZEN IN DESIGN PR
IMPLEMENTATION:            NOT STARTED / NOT AUTHORIZED
```

## 0. Decision provenance — why this is now closed

`docs/architecture/66d-delivery-acceptance/step66d-arch1-contract-freeze.md` §12 and
`step66d-arch1-read-model-and-security-boundary.md` §1 both recorded:

```text
Information architecture: Unified Control Center vs Coordinated Existing Routes
Status: STILL OPEN
Owner:  Step 67POC.0 / Step 66D-DESIGN
```

This stage is that owner. The Product Owner has selected **Unified Control Center** with the
implementation principle **Unified Overview + Existing Route Drill-down**. Option comparison is
therefore **closed** and is not reopened anywhere in this design package.

Binding semantics of the selection:

```text
Unified Control Center      = the project-level primary product entry point. It unifies status,
                              progress, blockers, delivery, acceptance, cost, safety and an
                              evidence index.
Existing specialized routes = retained as drill-down surfaces for detailed data, specialist
                              evidence and controlled operations.
"Unified" does NOT mean duplicating every existing page.
"Drill-down" does NOT mean the Product Owner must rebuild the whole picture across pages.
```

## 0.1 Dual-anchor model carried into the IA (66D-D03, ADR-66D-04)

The IA renders **two distinct anchors** and never substitutes one for the other:

```text
Execution / artifact / traceability anchor:
    project_id -> work_item_id -> workflow_id -> run_id
Human review and RBAC anchor:
    delivery_review_task_id -> task_id -> TASK_ROLES
```

Surface consequences of the dual-anchor model:

```text
Unified Control Center is anchored on project_id           (execution lineage)
Delivery Inbox is anchored on delivery_review_task_id      (human review anchor)
Delivery Review is anchored on delivery_submission_id, and displays BOTH anchors
Task is the human-review/RBAC anchor -- never the Agent execution source of truth (66D-D03-R3);
  the existing non-dispatching Task API is never re-described as a pipeline entry point.
```

## 1. Three-surface product model (frozen)

| Surface | Scope | Primary responsibility | Explicitly NOT responsible for |
| --- | --- | --- | --- |
| **Delivery Inbox** | cross-project | queue of pending `DeliveryReviewTask`; priority, due time, blocking state, review readiness; help the reviewer/PO find the submission that needs work | full project execution overview; full artifact inspection; full PO decision history; specialist operational evidence |
| **Unified Control Center** | one project | primary product entry point; Goal → PO Decision context; overall status, blockers, delivery, acceptance, cost, safety, evidence health; next-step recommendation + deep-link index | duplicating specialized route content; a second Agent execution viewer; a second Task Graph; a second Audit explorer; a second Safety Center; a second DLQ console |
| **Delivery Review** | one `DeliverySubmission` | detailed review workspace; submission content, requirements, artifacts, QA and audit evidence; **Review Gate Action**; **Product Owner Final Decision**; non-blocking follow-ups; decision supersession history | cross-project queueing; project-wide execution overview |

**Duplication-prevention rule (binding for FE1/FE2):** a Control Center section may render a
*summary + status + blocking reason + primary CTA + deep link*. It must not re-implement the
specialized route's full dataset, filters, or write controls. The single exception is the
Delivery/Acceptance summary, which may surface review status, decision readiness, latest action and
effective decision — but the review **form** and evidence inspection remain in Delivery Review.

## 2. Unified Control Center — frozen desktop information hierarchy

Order is the frozen information priority (top = highest).

```text
1. Project Context Header
2. Attention and Decision Strip
3. Lifecycle Progress
4. Delivery and Acceptance Summary
5. Execution Summary
6. Evidence Health
7. Cost and External Actions
8. Safety Summary
9. Activity Timeline
```

### 2.1 Project Context Header

Displays: Development Goal · Project name / `project_id` · Primary Work Item (`work_item_id`) ·
current lifecycle stage · overall health · last refreshed (`as_of`) · data freshness
(`is_stale`) · environment (internal test runtime).

Section navigation (in-page anchors, not new routes):

```text
Overview · Delivery · Execution · Evidence · Safety · Activity
```

Anchor + history behavior: each section anchor updates the URL fragment (e.g.
`#delivery`) via `replaceState`, so browser Back does not walk through anchors; a deep link
carrying a fragment scrolls to and focus-targets that section heading. The selected section is
restored on return from a drill-down (see `step66d-design-route-and-drilldown-map.md` §5).

### 2.2 Attention and Decision Strip

Highest-priority surface. Items, in the frozen severity order used for sorting:

```text
Pending review · Blocking issue · Expired review · Missing evidence ·
Failed acceptance criterion · QA rerun requested · Follow-up overdue ·
Stale read model · Identity not verified · Safety restriction
```

Every item carries: severity · plain-language summary · affected entity (typed ref) · recommended
next step · deep link · last updated. **Severity is never conveyed by color alone** — each item
carries a severity word and an icon (see `step66d-design-accessibility-responsive-spec.md`).

Acceptance requirement: all blocking items are reachable within the first screen or one scroll
(see `step66d-design-frontend-handoff.md` acceptance criteria AC-02).

### 2.3 Lifecycle Progress

Stages (frozen, mirroring the ARCH1 nine-link traceability chain):

```text
Goal · Requirements · Work Items · Execution · QA · Delivery Submission · Review ·
PO Decision · Follow-up
```

Per-stage state vocabulary (frozen — distinct from the nine canonical submission statuses):

```text
not started · in progress · blocked · completed · failed · unknown · not applicable
```

**Binding rule (66D-D02-R10):** Agent execution completing must never render the `PO Decision`
stage as completed. `Execution: completed` and `PO Decision: not started` is a legal, expected
combination and must be displayable.

### 2.4 Delivery and Acceptance Summary

Displays: current `DeliverySubmission` version · submission status (one of the nine canonical
statuses) · review status · `review_due_at` · review task assignee/role · acceptance criteria
summary · artifact completeness · QA result summary · latest `DeliveryReviewAction` · current
**effective** `ProductOwnerDecision` · follow-up summary · decision readiness.

Primary CTA is state-derived (frozen mapping):

```text
UNDER_REVIEW + evidence complete        -> Open Delivery Review
missing evidence                        -> Resolve Missing Evidence
CHANGES_REQUESTED                       -> Review Requested Changes
QA_RERUN_REQUESTED                      -> View QA Rerun
CHANGES_REQUESTED / EXPIRED             -> Create New Submission Version
ACCEPTED / REJECTED                     -> View Effective Decision
```

**The full PO decision form is never duplicated here.** Recording a decision always happens in
Delivery Review.

### 2.5 Execution Summary

Displays: workflow / run status (`workflow_id`, `run_id`) · runtime agent activity summary ·
external AI partner activity summary · latest artifact · latest source-control evidence ·
failure/retry summary. Each block deep-links to its specialized route.

**Actor typing is mandatory and visible:**

```text
runtime_agent · ai_partner · human · system
```

Claude Code, Codex and Claude Design are `ai_partner` and **must never be rendered as runtime
agents** (66D-D03 / prior binding decision D-2).

### 2.6 Evidence Health

Categories: requirements · artifact · QA · source-control · audit · safety · cost.

State vocabulary (frozen):

```text
COMPLETE · PARTIAL · MISSING · STALE · INACCESSIBLE · UNKNOWN
```

**`UNKNOWN` must never render green and must never be treated as PASS** (read-model contract §1:
"an absent source renders as UNKNOWN, never as zero, empty or healthy").

### 2.7 Cost and External Actions

Displays: planned · attempted · successful · failed · actual cost · authorized limit · limit breach ·
sandbox actions · production actions, and always renders:

```text
production_executed_true_count = 0
```

This value is **server-derived and read-only in the UI**; no client control may modify, override or
locally compute it.

### 2.8 Safety Summary

Displays: production execution status · feature-gate status · identity verification status ·
secret/backend readiness · resume/replay activation status · policy restrictions. Detail deep-links
to the existing Safety Center route. BE3 resume/replay are shown as **disabled** (all four gates
default false) and must not be presented as available.

### 2.9 Activity Timeline

Unified, time-ordered: workflow milestones · artifact creation · QA result · submission · review
actions · PO decisions · follow-up changes · audit-relevant failures.

Entries are visually and semantically distinguished by kind:

```text
Review Gate Action · Product Owner Final Decision · System projection · Agent/partner activity
```

A `Review Gate Action` entry and a `Product Owner Final Decision` entry are never merged into one
timeline row, even when created in the same transaction (ADR-66D-10) — they are two records.

## 3. Read model dependency

The Control Center consumes the ARCH1 `project_delivery_control_center` read model
(`read_model_id: project_delivery_control_center`, one document per `project_id`, DERIVED,
EVENTUALLY CONSISTENT, carries `as_of` and `is_stale`). It is **NOT IMPLEMENTED**; see
`docs/handoffs/66d-delivery-acceptance/step66d-design-gap-and-dependency-register.md`.

Freshness rules are frozen in `step66d-design-state-error-permission-matrix.md` §5.

## 4. What this IA freeze does not do

```text
Does not implement any surface            Does not modify any route source
Does not authorize FE1/FE2/BE1..BE4/QA    Does not modify TASK_ROLES
Does not change ADR-66D-09                Does not reopen the IA option comparison
Does not redefine Review Action or PO Decision enums
Does not repurpose the legacy DeliveryPackage
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
