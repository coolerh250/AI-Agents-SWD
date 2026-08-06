# Step 66D-DESIGN — Delivery Inbox Specification (FROZEN)

> **Design specification only. No frontend implementation. No merge.
> `production_executed_true_count: 0`.** Route `/delivery-inbox` exists today as a
> `PlaceholderPage`; the queue behind it is **NOT IMPLEMENTED**.

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
SCOPE:              cross-project queue of pending DeliveryReviewTask
ANCHOR:             delivery_review_task_id (human review anchor, 66D-D03)
```

## 1. Responsibility boundary (frozen)

```text
IS:      the cross-project work queue that answers "which submission needs me next?"
IS NOT:  a project dashboard; an artifact browser; a decision-history archive; a specialist
         operational evidence surface
```

The Inbox never renders a Review Gate Action or a Product Owner Final Decision control. Its only
action is navigation into Delivery Review (or into the Control Center for project context).

## 2. Queue model

One row per `DeliveryReviewTask`. Row identity is the review task; the row *displays* submission
facts (version, status) because that is what the reviewer decides about.

```text
grouping (default)   by due state:  Overdue -> Due soon -> Open -> Waiting on others -> Terminal
scope                only review tasks the actor is authorized to see; cross-project and
                     cross-team rows are not returned (denied and masked as 404 server-side)
empty behavior       see section 6
```

## 3. Filters (minimum, frozen — each with an explicit field definition)

The previously ambiguous pair `review_status` / `submission status` is **replaced** by two
explicitly-named, separately-defined filters. There is no filter without a field definition.

| Filter name | Source field | Enum / source contract | Display label | Missing-data behavior | Backend dependency |
| --- | --- | --- | --- | --- | --- |
| `delivery_review_task_status` | `DeliveryReviewTask.status` | review-task lifecycle (**NOT IMPLEMENTED**) | "Review task status" | `UNKNOWN` (never treated as open/clear) | review-task queue read model |
| `delivery_submission_status` | `DeliverySubmission.status` | the nine canonical submission statuses | "Submission status" | `UNKNOWN` | `GET /delivery-submissions` |
| `assigned_role` | `DeliveryReviewTask.assigned_role` | `TASK_ROLES` (`reviewer_approver`, `pm_engineering_lead`, …) | "Assigned role" | `UNKNOWN` | review-task read model |
| `assigned_actor` | `DeliveryReviewTask.assigned_actor` | `actor_ref` | "Assignee" | `UNKNOWN` | review-task read model |
| `project` | `project_id` | project list | "Project" | `UNKNOWN` | project read model |
| `due_state` | `DeliverySubmission.review_due_at` | derived: `overdue` / `due_soon` / `open` / `no_due_date` | "Due state" | `no_due_date` (never "open") | `review_due_at` (DB-authoritative) |
| `blocking_state` | derived blocking indicator | `blocked` / `not_blocked` | "Blocking" | `UNKNOWN` (never "not blocked") | unified read model |
| `evidence_readiness` | evidence-health rollup | `COMPLETE`/`PARTIAL`/`MISSING`/`STALE`/`INACCESSIBLE`/`UNKNOWN` | "Evidence readiness" | `UNKNOWN` | evidence read model |

The two status filters are **not interchangeable**: the review task is the human-review anchor
(66D-D03) and can be open while its submission is already terminal; the submission status is the
nine-value canonical lifecycle. A row may therefore legitimately show a closed review task against
an `EXPIRED` submission, and the Inbox must be able to express that.

No filter introduces a backend capability that is not already named in the ARCH1 contracts; every
one is marked **NOT IMPLEMENTED** in the gap register.

Filter behavior: filters are additive; the active filter set is URL-encoded (no identity, no
secrets) so a filtered queue is shareable and restorable; a filter that returns nothing shows the
"no match" empty state (§6) rather than an error.

## 4. Sorting (minimum, frozen)

```text
overdue first
due soon
blocking severity
oldest submitted
recently updated
```

Default sort = `overdue first`, then `due soon`, then `blocking severity`. Sort is explicit and
visible; it is never silently re-ordered by a background refresh (a refresh that changes ordering
surfaces a "queue updated" affordance rather than reflowing under the pointer).

## 5. Row content (minimum, frozen)

```text
Project                (name + project_id ref)
Submission version     (submission_version, e.g. v3)
Review status          (canonical status label + plain-language explanation on hover/expand)
Due time               (absolute + relative; overdue state explicit, not color-only)
Assignee / role        (actor ref + TASK_ROLES role)
Evidence health        (COMPLETE / PARTIAL / MISSING / STALE / INACCESSIBLE / UNKNOWN)
Blocking indicator     (icon + word, never color alone)
Latest action          (latest DeliveryReviewAction type + when)
Primary CTA            (see below)
```

Primary CTA per row state (frozen):

```text
UNDER_REVIEW, evidence complete       -> Open Delivery Review
SUBMITTED (not yet opened)            -> Start Review
missing / inaccessible evidence       -> Resolve Missing Evidence
QA_RERUN_REQUESTED                    -> View QA Rerun
CHANGES_REQUESTED                     -> View Requested Changes
EXPIRED                               -> View Expired Submission
ACCEPTED / REJECTED                   -> View Effective Decision
ARCHIVED                              -> View Archived Submission
```

`ARCHIVED` rows are never styled as success; `EXPIRED` rows are never styled as a generic error
(see `step66d-design-state-error-permission-matrix.md` §4).

## 6. States

```text
loading        table-level skeleton rows (header + filter bar remain interactive)
empty (none)   "No delivery reviews are waiting for you." + explain that new submissions appear
               here when they are submitted for review
empty (filter) "No delivery reviews match these filters." + Clear filters
partial        queue rendered + banner naming which sources were unavailable and the impact on
               review readiness
stale          as_of timestamp + stale warning + Refresh; rows keep their own freshness where the
               read model provides it
inaccessible   "You do not have access to this queue." (no existence leak; cross-project rows are
               simply absent, never listed as denied)
error          canonical-error copy per step66d-design-state-error-permission-matrix.md §3
unknown        evidence readiness renders UNKNOWN (never green, never PASS)
```

## 7. Accessibility and responsive (summary; full spec in the a11y/responsive doc)

```text
semantic table with a caption; sortable headers expose sort state to assistive tech
row primary CTA is a real link/button reachable in tab order
overdue/blocking conveyed by word + icon + text, not color alone
1440/1280 full table; 1024 reduced columns (Project, Version, Status, Due, CTA);
768 stacked cards; small mobile read-only summary
```

## 8. Dependencies (all NOT IMPLEMENTED / NOT AUTHORIZED)

```text
DeliveryReviewTask persistence + queue read model
GET /delivery-submissions (list, filtered, paginated, cursor-based)
review task assignment + TASK_ROLES capability mapping
freshness metadata (as_of, is_stale)
route element replacement for /delivery-inbox (currently PlaceholderPage)
```

See `docs/handoffs/66d-delivery-acceptance/step66d-design-gap-and-dependency-register.md`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
