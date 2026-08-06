# Step 66D-DESIGN — State, Error and Permission Matrix (FROZEN)

> **Design specification only. No implementation. `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
```

## 1. Canonical submission statuses — exactly nine (frozen, 66D-D02)

| Status | Label | Plain-language explanation | Icon role | Color role | Primary CTA | Secondary CTA | Read-only behavior | Empty-state behavior |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DRAFT` | Draft | Being prepared; not yet submitted for review. | pencil/outline | neutral | Continue preparing | — | review panels hidden | "Nothing submitted yet." |
| `SUBMITTED` | Submitted | Submitted; review not started. | inbox-arrow | info | Start Review | View submission | actions disabled until opened | "Review not started." |
| `UNDER_REVIEW` | Under review | Being reviewed now. | eye | info/active | Open Delivery Review | View evidence | full evidence readable | "No actions recorded yet." |
| `CHANGES_REQUESTED` | Changes requested | Content revision requested; a new version is required. | arrow-uturn | warning | Review Requested Changes | Create New Submission Version | actions limited | "No new version yet." |
| `QA_RERUN_REQUESTED` | QA rerun requested | Re-verification requested; awaiting a QA result. | refresh | warning | View QA Rerun | View previous QA | ACCEPT disabled | "QA result not attached yet." |
| `ACCEPTED` | Accepted | Accepted — **projection of the current effective decision**. | check | success | View Effective Decision | View decision history | write actions closed | "No follow-ups." |
| `REJECTED` | Rejected | Rejected — **projection of the current effective decision**. | x-circle | danger | View Effective Decision | View decision history | write actions closed | "No further action." |
| `ARCHIVED` | Archived | Closed administratively — **not** an acceptance and **not** a rejection. | archive-box | neutral (**never success**) | View Archived Submission | View decision history | read-only | "Archived; nothing pending." |
| `EXPIRED` | Expired | The review window closed before a decision; a new version is required. | clock-alert | warning (**not generic error**) | Create New Submission Version | Escalate | accept/reject/rerun disabled | "Expired without a decision." |

Rules:

```text
Status is never conveyed by color alone -- label + icon + text always present.
ACCEPTED / REJECTED are labelled as effective-decision projections (66D-D02-R4, ADR-66D-03).
ARCHIVED is never styled as success (66D-D02-R9).
EXPIRED is never styled as a generic error.
UNKNOWN is not a canonical status and must never be mapped onto one.
```

## 2. Per-section DATA-STATE matrix

This is the **data-state matrix**: 11 sections × 7 data states. Permission is a **separate
dimension** and is specified in §6 (the permission matrix); the two are never conflated or
multiplied into a single figure.

```text
data states (7):        loading · empty · partial · stale · inaccessible · error · unknown
permission states (6):  authorized · not_authorized · identity_not_verified ·
                        capability_unavailable · read_only_observer · future_shared_runtime_required
```

`unknown` is a distinct state with its own behavior and is never carried by the `error` cell:
`error` means a request or projection failed; `unknown` means the value is genuinely not known
(absent source) and must render as UNKNOWN — never as healthy, zero, empty or PASS.

| Section | loading | empty | partial | stale | inaccessible | error | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Project Context Header | skeleton (name/goal) | "Project context unavailable." | header + missing-field notice | `as_of` + stale badge + Refresh | "You do not have access to this project." | canonical copy | health = UNKNOWN (never green) |
| Attention Strip | skeleton rows | "Nothing needs your attention." | listed items + "some sources unavailable" | stale badge + which items may be incomplete | section hidden with reason | canonical copy | item severity UNKNOWN, shown not hidden |
| Lifecycle Progress | skeleton stages | "No lifecycle data yet." | stages shown; missing stages = unknown | stale badge | reason shown | canonical copy | stage = `unknown` (not `completed`) |
| Delivery/Acceptance Summary | skeleton | "No submission for this project yet." | summary + missing-evidence list | stale badge + "re-check before deciding" | reason | canonical copy | readiness UNKNOWN; CTA = Resolve Missing Evidence |
| Execution Summary | skeleton | "No runs recorded." | shown + unavailable sources named | stale badge | reason | canonical copy | activity UNKNOWN |
| Evidence Health | skeleton chips | "No evidence expected yet." | per-category PARTIAL | STALE per category | INACCESSIBLE per category | canonical copy | UNKNOWN per category |
| Cost / External Actions | skeleton | "No cost or external actions recorded." | partial + which counter missing | stale badge | reason | canonical copy | UNKNOWN (never 0) |
| Safety Summary | skeleton | n/a (always renders) | partial + which field missing | stale badge | reason | canonical copy | UNKNOWN (never "safe") |
| Activity Timeline | skeleton rows | "No activity yet." | shown + gap notice ("some entries may be missing") | stale badge + `as_of` | "You do not have access to this activity." | canonical copy — timeline failed to load | entry kind UNKNOWN; ordering gap shown as UNKNOWN, never inferred or silently closed |
| Delivery Inbox | table skeleton | see inbox spec §6 | banner naming sources | `as_of` + Refresh | "No access to this queue." | canonical copy | readiness UNKNOWN |
| Delivery Review (each panel) | panel skeleton | per-panel empty copy | missing-evidence list | stale + re-fetch before write | not-authorized (no write form) | canonical copy | criterion `NOT_TESTED` / UNKNOWN |

**Empty-state must distinguish five different reasons** (never one generic "No data"):

```text
No data expected yet · Data not produced · Data missing · Access denied · Integration unavailable
```

**Partial must always show:** available sources · missing sources · impact on review readiness ·
recommended next action.

## 3. Canonical error → user-facing copy (frozen)

Copy is plain-language and actionable. Never shown: stack trace · raw exception · database detail ·
secret · token · internal credential reference.

| Code | User-facing copy | Next action offered |
| --- | --- | --- |
| `403 DELIVERY_REVIEW_ACCESS_DENIED` | "You do not have permission to review this delivery." | Request access / go back |
| `404 DELIVERY_SUBMISSION_NOT_FOUND` | "This delivery submission is not available." | Back to Delivery Inbox |
| `404 REVIEW_TASK_NOT_FOUND` | "This review task is not available." | Back to Delivery Inbox |
| `409 DELIVERY_VERSION_CONFLICT` | "This submission changed while you were reviewing it. Reload to see the current version before continuing." | Reload and compare |
| `409 DELIVERY_ALREADY_SUBMITTED` | "This submission has already been submitted." | View current status |
| `409 DELIVERY_NOT_REVIEWABLE` | "This submission cannot be reviewed in its current status." | View allowed actions |
| `409 DECISION_ALREADY_SUPERSEDED` | "A newer decision has replaced the one you were acting on." | View effective decision |
| `409 FINAL_DECISION_ALREADY_EXISTS` | "A final decision already exists for this submission. Record a new decision that supersedes it if it needs to change." | View decision history |
| `409 QA_RERUN_LIMIT_REACHED` | "QA rerun limit reached. Use Request Changes, Escalate, or Reject." | those three actions |
| `409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES` | "This follow-up is blocking, so it cannot be accepted with follow-up. Use Request Changes instead." | Switch to Request Changes |
| `409 SUBMISSION_EXPIRED` | "This delivery review has expired. Create or request a new DeliverySubmission version before continuing." | Create/request new version |
| `422 MISSING_REQUIRED_EVIDENCE` | "Required evidence is missing, so this cannot be decided yet." | list + deep links |
| `422 ACCEPTANCE_CRITERIA_INCOMPLETE` | "Some acceptance criteria have not been assessed yet." | list + deep links |
| `422 INVALID_REVIEW_ACTION` | "That review action is not allowed for this submission right now." | show allowed actions |
| `422 INVALID_DECISION_MAPPING` | "That decision does not match the review action being recorded." | show valid pairing |
| `401 / 403 identity not verified` | "A verified identity is required to record a final decision." | explain RA-2 dependency; no write |
| network / unknown | "Could not load this. Retry, or check system status." | Retry |

## 4. Visual-semantics rules

```text
Never color-only for status, severity, blocking, freshness or evidence health.
ARCHIVED  -> neutral, never success.
EXPIRED   -> warning, never generic error.
UNKNOWN   -> neutral/attention, never green, never PASS, never 0.
STALE     -> visible marker plus which decisions may be unsafe.
```

## 5. Read-model freshness (frozen)

The Control Center consumes an **eventually consistent** read model that carries `as_of` and
`is_stale` (ARCH1 read-model §1).

```text
Display:            last refreshed (as_of) · fresh / stale / unknown · per-source freshness where
                    provided · manual Refresh · refresh-in-progress state
Authority:          when a specialized route disagrees with the CC summary, the detailed
                    authoritative route WINS
CC obligations:     show the stale indicator; never imply synchronous consistency; offer
                    "Open current evidence" deep link; re-fetch authoritative detail before any
                    write action
Missing source:     UNKNOWN, never zero/empty/healthy
```

Write-path rule: a write action initiated from stale context must re-fetch the authoritative record
(and its `row_version`) before submitting; if it changed, the conflict flow in the interactions spec
§6 applies.

## 6. Permission and identity states (frozen)

Today's identity reality: a POC sandbox / internal test runtime operator identity exists; a
**verified shared-runtime identity does not** (RA-2, `ARCH1-G08`). The frontend must never treat a
request-provided actor or role as authoritative.

| State | UI behavior |
| --- | --- |
| `authorized` | action available; server still re-checks |
| `not authorized` | action rendered disabled with a plain reason; no write form submitted |
| `identity not verified` | security notice; **final decision (ACCEPT/REJECT) not permitted**; read access unaffected |
| `capability unavailable` | action disabled, explaining the capability is not enabled in this environment |
| `read-only observer` | all authorized data viewable; no write controls rendered |
| `future shared-runtime requirement` | explicit note that a verified identity (RA-2) is required before production-grade acceptance |

Recommended rendering:

```text
Unauthenticated                 -> no write form at all
Authenticated but unauthorized  -> disabled action + reason
Identity not verified           -> security warning + final decision blocked
Read-only observer              -> viewable data, no actions
```

Authorization is decided by the backend; the client only *presents* state. Cross-project/cross-team
access is denied and **masked as 404** so existence is not leaked.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
