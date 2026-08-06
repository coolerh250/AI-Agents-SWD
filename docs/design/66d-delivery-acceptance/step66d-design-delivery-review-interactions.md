# Step 66D-DESIGN — Delivery Review Interactions (FROZEN)

> **Design specification only. No frontend implementation. No backend implementation. No merge. No
> API exists. `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
ROUTE:              /delivery-submissions/:deliverySubmissionId/review  (PLANNED / NOT IMPLEMENTED)
BINDING:            66D-D01, 66D-D02, 66D-D03, 66D-D04, ADR-66D-01..10 (ADR-66D-09 unchanged)
```

## 1. Page structure (frozen)

```text
1. Review Context Header
2. Submission Summary
3. Requirement Traceability
4. Artifact and Evidence Workspace
5. Review Gate Action Panel
6. Product Owner Decision Panel
7. Acceptance Follow-up Panel
8. Decision History (incl. superseded)
```

### 1.1 Review Context Header
Project · Work Item (`work_item_id`) · Workflow / Run (`workflow_id`, `run_id`) · submission version ·
review task (`delivery_review_task_id`) · status · `review_due_at` · data freshness (`as_of`,
`is_stale`).

### 1.2 Submission Summary
What is being delivered · requirements baseline · acceptance criteria version · known limitations ·
run instructions · `legacy_delivery_package_refs` (clearly labelled **legacy Step 47/49 evidence
reference**, never presented as the acceptance aggregate — 66D-D04).

### 1.3 Requirement Traceability
Renders the frozen ARCH1 nine-link chain, in order:

```text
Requirement -> Acceptance Criterion -> Work Item -> Execution -> Artifact -> QA Evidence ->
DeliverySubmission Item -> Review Action -> Product Owner Decision
```

Criterion results (frozen ARCH1 vocabulary): `PASS` · `FAIL` · `PARTIAL` · `NOT_TESTED` ·
`NOT_APPLICABLE`, each with `assessor_actor_ref`, `assessed_at`, `reason`, `evidence_refs`.

**Binding rule:** *Agent completion never implies PASS.* A finished run renders as execution
evidence; the criterion stays `NOT_TESTED` until an assessor records a result.

Required capabilities: filter by criterion result · expand the evidence chain · open the specialized
evidence route · show a missing link · show stale evidence.

### 1.4 Artifact and Evidence Workspace
Categories: delivery items · artifacts · QA · source control · security boundary · demo evidence ·
cost · external actions · audit.

**Never displayed** (hard boundary, ARCH1 read-model §2): private chain of thought · raw model
tokens · secrets · credentials · client secrets · private keys · actual DSNs · internal credential
identifiers · real account identifiers · unredacted sensitive evidence. Secret **names** may appear
as references only; values never appear.

Every artifact row shows provenance and generation mode (ADR-66D-06): implementation partner ·
actor type (`runtime_agent`/`ai_partner`/`human`/`system`) · generation mode · review status · test
status · safety mode.

## 2. Review Gate Action Panel — exactly six (frozen)

```text
ACCEPT · REJECT · REQUEST_CHANGES · RERUN_QA · ESCALATE · ARCHIVE
```

No action may be added, merged, renamed or softened. Per-action display state vocabulary:

```text
available · disabled · not authorized · not applicable · blocked by missing evidence
```

Frozen availability matrix (status × action). `n/a` = not applicable for that status.

| Status | ACCEPT | REJECT | REQUEST_CHANGES | RERUN_QA | ESCALATE | ARCHIVE |
| --- | --- | --- | --- | --- | --- | --- |
| `DRAFT` | n/a | n/a | n/a | n/a | n/a | n/a |
| `SUBMITTED` | disabled (open review first) | disabled | disabled | disabled | available | n/a |
| `UNDER_REVIEW` | available¹ | available | available | available² | available | n/a |
| `CHANGES_REQUESTED` | n/a | available | n/a (already requested) | n/a | available | n/a |
| `QA_RERUN_REQUESTED` | disabled (awaiting QA result) | available | available | disabled (limit) | available | n/a |
| `ACCEPTED` | n/a | n/a | n/a | n/a | n/a | available |
| `REJECTED` | n/a | n/a | n/a | n/a | n/a | available |
| `EXPIRED` | **disabled** | **disabled** | disabled — new version required | **disabled** | available | available |
| `ARCHIVED` | n/a | n/a | n/a | n/a | n/a | n/a |

¹ `ACCEPT` additionally requires: all acceptance criteria assessed, required evidence present,
verified human actor with PO decision capability. Otherwise `blocked by missing evidence` or
`not authorized`.
² `RERUN_QA` available only if the authoritative rerun count for this submission version is 0
(ADR-66D-09).

Authorization display (specification only; server decides — ARCH1 §8):

```text
reviewer_approver     REQUEST_CHANGES, RERUN_QA, ESCALATE, read evidence
pm_engineering_lead   ACCEPT, REJECT, ARCHIVE, record ProductOwnerDecision, manage non-blocking
(designated PO)       follow-ups
```

## 3. Product Owner Decision Panel — exactly three (frozen)

```text
ACCEPTED · ACCEPTED_WITH_FOLLOW_UP · REJECTED
```

**Visually and semantically separated from the Review Gate Action Panel** (66D-D01, ADR-66D-01):
distinct panel, distinct heading, distinct visual treatment, distinct copy, and never rendered as a
sub-control of an action button.

Displays: current **effective** decision · decision history · superseded decisions · decision reason ·
decided by · decided at · evidence reviewed.

Binding rules surfaced in the UI:

```text
The projected status (ACCEPTED / REJECTED) is labelled as a projection of the current effective
  decision, NOT the authoritative record (66D-D02-R4, ADR-66D-03).
The authoritative record is the immutable ProductOwnerDecision history; a correction is a NEW
  decision with supersedes_decision_id (66D-D02-R1..R3, ADR-66D-02).
History is never deleted and superseded entries remain visible.
ACCEPTED_WITH_FOLLOW_UP projects to review status ACCEPTED (66D-D02-R5).
```

## 4. Acceptance Follow-up Panel

Applies only to `ACCEPTED_WITH_FOLLOW_UP`. Per item: description · owner · severity · blocking ·
due date · status · evidence.

**Blocking rule (66D-D02-R6/R7, server error `409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES`):** if any
follow-up item has `blocking = true`, the UI must

```text
block submission of ACCEPTED_WITH_FOLLOW_UP (submit control disabled with reason)
NOT auto-convert the decision to anything else
state plainly: "This follow-up is blocking. Use Request Changes instead."
keep the entered reason/description text so nothing the reviewer wrote is lost
```

## 5. Interaction flows (frozen)

### 5.1 ACCEPT — guided two-concept flow
The UI must present two clearly distinct concepts even though the backend persists them in one
transaction (ADR-66D-10):

```text
Step 1  Review Gate Action = ACCEPT
Step 2  Product Owner Final Decision = ACCEPTED  or  ACCEPTED_WITH_FOLLOW_UP
```

Confirmation dialog must contain: review action · final decision · reason · evidence reviewed ·
follow-up items (if any) · irreversible-history notice · supersession explanation.

Primary button copy: **`Record Acceptance Decision`** — never a bare `Accept`.

The dialog must state that the action and the decision are two records written together, so the user
does not read them as one record (they appear as two Activity Timeline entries).

### 5.2 REJECT — guided flow

```text
Review Gate Action = REJECT      Final Decision = REJECTED
```

Requires an explicit reason and the evidence reviewed. Primary button copy:
**`Record Rejection Decision`**.

### 5.3 REQUEST_CHANGES — creates no final decision
Collects: reason · requested scope · affected criteria/items · required evidence. Must state plainly:

```text
A new DeliverySubmission version will be required.
```

No `ProductOwnerDecision` is created (66D-D01 mapping; 66D-D02-R8).

### 5.4 RERUN_QA — bounded to one per submission version (ADR-66D-09)
Displays the **backend-authoritative** quota, never a client counter:

```text
QA reruns used: 0 of 1     -> submit control available
QA reruns used: 1 of 1     -> submit control absent/disabled
```

Collects: reason · QA scope · previous QA reference. Disabled-state copy:

```text
QA rerun limit reached. Use Request Changes, Escalate, or Reject.
```

The UI must not compute, cache-as-truth, or decrement the allowance locally; the count comes from
persisted `DeliveryReviewAction` rows. A replayed request (same `Idempotency-Key`) must not appear
as a second use.

### 5.5 ESCALATE — creates no final decision
Collects: reason · target role/team · required resolution. Status remains `UNDER_REVIEW`. Must never
be displayed, labelled, or recorded as an outcome or a decision (ARCH1 §5).

### 5.6 ARCHIVE
Offered only for `terminal`, `expired` or `superseded` submissions. Requires explicit consequence
copy, e.g.:

```text
Archiving closes this submission for administrative purposes. It is not an acceptance and not a
rejection, and it does not change the effective decision.
```

`ARCHIVED` is never presented as success (66D-D02-R9).

## 6. Concurrency and idempotency UX (frozen)

Every write action implements:

```text
single-submit protection      (control disabled on submit; no double-fire)
in-progress state             (explicit, cancel-safe where the server permits)
idempotent retry message      (a retry with the same Idempotency-Key is not a second action)
stale version handling        (If-Match / row_version precondition)
conflict recovery             (see below)
refresh and compare
```

Canonical conflict handling — never a generic error:

| Server response | UI behavior |
| --- | --- |
| `409 DELIVERY_VERSION_CONFLICT` | stop local submitting state; refetch authoritative submission; name what changed (version/row_version); preserve typed reason; require explicit re-confirm |
| `409 FINAL_DECISION_ALREADY_EXISTS` | stop; refetch decision history; explain a decision already exists; offer supersession path; **never auto-resend** |
| `409 DECISION_ALREADY_SUPERSEDED` | stop; refetch; show which decision now supersedes; require re-confirm against the current effective decision |
| `409 QA_RERUN_LIMIT_REACHED` | stop; refetch action history; show `1 of 1`; disable RERUN_QA; offer REQUEST_CHANGES / ESCALATE / REJECT |
| `409 SUBMISSION_EXPIRED` | stop; switch the page to the expired state (§7) |
| `409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES` | stop; mark the blocking item; direct to REQUEST_CHANGES; keep entered text |
| `409 DELIVERY_NOT_REVIEWABLE` / `DELIVERY_ALREADY_SUBMITTED` | stop; refetch; explain the current status and the allowed next actions |
| `422 MISSING_REQUIRED_EVIDENCE` | stop; list the missing evidence with deep links; keep text |
| `422 ACCEPTANCE_CRITERIA_INCOMPLETE` | stop; list unassessed/failed criteria with deep links |
| `422 INVALID_REVIEW_ACTION` / `INVALID_DECISION_MAPPING` | stop; explain the illegal action/mapping in product language (never echo an enum error) |
| `403 DELIVERY_REVIEW_ACCESS_DENIED` | render not-authorized state; no write form |
| `404 DELIVERY_SUBMISSION_NOT_FOUND` / `REVIEW_TASK_NOT_FOUND` | render not-found (cross-project access is masked as 404 — the UI must not imply the record exists elsewhere) |

Preserved text rule: unsent reason/description text is retained across a conflict **unless** it
would carry sensitive content, in which case it is dropped with an explicit notice.

## 7. Expiry UX (frozen)

The **database-authoritative** `review_due_at` is the only source of expiry. When status is
`EXPIRED`:

```text
ACCEPT           disabled
REJECT           disabled
RERUN_QA         disabled
REQUEST_CHANGES  disabled - a new version is required (per contract)
ESCALATE         available
ARCHIVE          available
```

Message:

```text
This delivery review has expired.
Create or request a new DeliverySubmission version before continuing.
```

A client countdown is a **hint only**, must be labelled `Estimated from server-provided due time`,
and must never change the authoritative status or re-enable a disabled control.

## 8. Not implemented / not authorized

Every endpoint, record, event, audit action and capability referenced here is **NOT IMPLEMENTED**.
FE2 (review actions, PO decisions, follow-ups) is **NOT AUTHORIZED**. `ACCEPT` and `REJECT`
additionally require a verified human identity that does not exist until RA-2 (`ARCH1-G08`), so a
production-grade acceptance flow cannot be claimed — only a sandbox one.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
