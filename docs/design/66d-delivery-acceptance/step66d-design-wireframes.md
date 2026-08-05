# Step 66D-DESIGN — Low-fidelity Wireframes (FROZEN)

> **Low-fidelity structural wireframes only. Not a high-fidelity brand redesign. No implementation.
> `production_executed_true_count: 0`.** Reuses the existing Admin Console design tokens,
> navigation conventions, spacing, typography, component patterns and status language
> (`apps/admin-console/src/styles.css`, `components/NavGroup.tsx`, `components/CalmSafetyPosture.tsx`).

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
WIREFRAME COUNT:    10 (measured: see step66d-design-contract-manifest.yaml wireframe_inventory)
```

Annotation legend used on every wireframe:

```text
[P1]/[P2]/[P3] information priority   (P1 = highest)
{CTA}      primary CTA               (cta)  secondary CTA
->route    deep-link target          [RO] read-only region   [W] write region
[PERM:x]   permission state
```

---

## WF-01 — Delivery Inbox (desktop 1440)

```text
+----------------------------------------------------------------------------------+
| Admin Console      [existing side nav: Deliveries > Delivery Inbox]              |
+----------------------------------------------------------------------------------+
| [P1] Delivery Inbox                          as_of 12:04  (fresh) {Refresh}      |
| Reviews waiting for you across projects.                                  [RO]   |
+----------------------------------------------------------------------------------+
| [P2] Filters: review_status | assigned_role | assigned_actor | project |          |
|              due state | blocking | evidence readiness | submission status       |
|      Sort: (Overdue first) v                                              [RO]   |
+----------------------------------------------------------------------------------+
| [P1] OVERDUE (2)                                                                 |
|  Project        Ver  Status         Due          Assignee     Evidence  Blocking |
|  Atlas Portal   v3   Under review   -2d (overdue) PM/you      PARTIAL   ! Blocked|
|      Latest action: RERUN_QA - 3d ago      {Open Delivery Review}                |
|                                             ->/delivery-submissions/:id/review   |
|  Beacon API     v1   QA rerun req.  -1d (overdue) Reviewer    COMPLETE   - none  |
|      Latest action: RERUN_QA - 1d ago      {View QA Rerun}                       |
| [P2] DUE SOON (1)   ...                                                          |
| [P3] OPEN (4)       ...                                                          |
| [P3] TERMINAL (3)   Archived / Expired rows - neutral styling, never success      |
+----------------------------------------------------------------------------------+
```

`[RO]` entire surface. No Review Gate Action and no PO Decision control appears here.
Empty variants per inbox spec §6.

---

## WF-02 — Unified Control Center (desktop 1440)

```text
+----------------------------------------------------------------------------------+
| [P1] PROJECT CONTEXT                                                             |
|  Goal: "Deliver the X module"      Project: Atlas Portal (proj_123)               |
|  Primary Work Item: wi_88          Stage: Review      Health: ATTENTION           |
|  as_of 12:04  (STALE - 6m behind) {Refresh}        Env: internal test runtime     |
|  Sections: Overview | Delivery | Execution | Evidence | Safety | Activity  (#anchors)|
+----------------------------------------------------------------------------------+
| [P1] NEEDS ATTENTION                                                             |
|  ! CRITICAL  Expired review - submission v3 review window closed                 |
|              -> Create new version      ->/delivery-submissions/:id/review  2h   |
|  ! HIGH      Missing evidence - source-control refs absent for wi_88             |
|              -> Resolve missing evidence   ->/sandbox-github               10m   |
|  ! MEDIUM    Stale read model - summary may lag detail                           |
|              -> Open current evidence                                       now  |
|  (severity = word + icon + text; never color alone)                       [RO]   |
+----------------------------------------------------------------------------------+
| [P2] LIFECYCLE                                                                   |
|  Goal(done) > Requirements(done) > Work Items(done) > Execution(done) >           |
|  QA(failed) > Delivery Submission(done) > Review(in progress) >                   |
|  PO Decision(NOT STARTED) > Follow-up(n/a)                                       |
|  NOTE: Execution complete does NOT mark PO Decision complete.             [RO]   |
+----------------------------------------------------------------------------------+
| [P1] DELIVERY & ACCEPTANCE                       | [P2] EXECUTION                |
|  Submission: v3   Status: EXPIRED                |  Workflow wf_9 / run r_41      |
|  Review due: passed 2h ago                       |  runtime_agent: qa-agent FAILED|
|  Assignee: PM/Eng Lead (you)                     |  ai_partner: Codex - PR draft  |
|  Criteria: 6 assessed / 1 FAIL / 2 NOT_TESTED    |  (partners are NOT runtime     |
|  Artifacts: PARTIAL   QA: FAILED                 |   agents)                      |
|  Latest action: RERUN_QA (1 of 1 used)           |  Failures/retries: 2 / DLQ 0   |
|  Effective decision: none (projection: n/a)      |  ->/agent-executions           |
|  Readiness: BLOCKED                              |  ->/task-graph ->/workspace    |
|  {Create New Submission Version}  (cta View v3)  |                          [RO]  |
|  ->/delivery-submissions/:id/review        [RO]   |                               |
+--------------------------------------------------+-------------------------------+
| [P2] EVIDENCE HEALTH                                                             |
|  requirements COMPLETE | artifact PARTIAL | QA FAILED-evidence COMPLETE |         |
|  source-control MISSING | audit COMPLETE | safety COMPLETE | cost UNKNOWN        |
|  (UNKNOWN is neutral - never green, never PASS)   ->/qa-code ->/audit-evidence    |
+----------------------------------------------------------------------------------+
| [P3] COST & EXTERNAL ACTIONS          | [P2] SAFETY                              |
|  planned 4 / attempted 3 / ok 2 / fail 1 |  production execution: none            |
|  actual cost: UNKNOWN                 |  feature gates: all false                 |
|  limit: set   breach: no               |  identity: NOT VERIFIED (RA-2)           |
|  sandbox actions: 3                    |  resume/replay: DISABLED                 |
|  production actions: 0                 |  ->/safety                        [RO]   |
|  production_executed_true_count = 0 [RO, server-derived, not client-editable]     |
+----------------------------------------------------------------------------------+
| [P3] ACTIVITY TIMELINE (kinds distinguished)                                     |
|  [Review Gate Action] RERUN_QA by reviewer - 3d                                   |
|  [Agent/partner] qa-agent run failed - 3d                                        |
|  [System projection] status -> QA_RERUN_REQUESTED - 3d                            |
|  [PO Final Decision] (none yet)                                           [RO]   |
+----------------------------------------------------------------------------------+
```

---

## WF-03 — Unified Control Center (compact / tablet 1024)

```text
+--------------------------------------------------+
| [P1] Atlas Portal  Stage: Review  Health: ATTN   |
| as_of 12:04 (STALE) {Refresh}   env: test        |
| [Overview][Delivery][Execution][Evidence][Safety]|
+--------------------------------------------------+
| [P1] NEEDS ATTENTION (3)  - full list, not hidden|
|  ! CRITICAL Expired review -> new version        |
|  ! HIGH Missing source-control evidence          |
|  ! MEDIUM Stale read model                       |
+--------------------------------------------------+
| [P2] LIFECYCLE (horizontal scroll, labels kept)  |
+--------------------------------------------------+
| [P1] DELIVERY & ACCEPTANCE (stacked, full)       |
|  ... {Create New Submission Version}             |
+--------------------------------------------------+
| [P2] EXECUTION (stacked)                         |
| [P2] EVIDENCE HEALTH (chips wrap)                |
| [P3] COST | SAFETY (stacked)                     |
| [P3] ACTIVITY (stacked)                          |
+--------------------------------------------------+
Rule: status, blocking reason and decision history are NEVER hidden at any breakpoint.
```

---

## WF-04 — Delivery Review (desktop 1440)

```text
+----------------------------------------------------------------------------------+
| [P1] REVIEW CONTEXT  Atlas Portal / wi_88 / wf_9-r_41 / submission v3             |
|      review task rt_12   Status: UNDER_REVIEW   Due: in 6h                        |
|      as_of 12:04 (fresh) {Refresh}     [PERM: pm_engineering_lead]                |
+----------------------------------------------------------------------------------+
| [P2] SUBMISSION SUMMARY                          | [P2] REQUIREMENT TRACEABILITY  |
|  Delivering: X module API + docs                  |  Req > Criterion > WorkItem >  |
|  Requirements baseline: rb_7                      |  Execution > Artifact > QA >   |
|  Acceptance criteria version: ac_3                |  Item > Action > Decision      |
|  Known limitations: 2                             |  filter: [all|PASS|FAIL|       |
|  Run instructions: present                        |          PARTIAL|NOT_TESTED]   |
|  legacy_delivery_package_refs: pkg_19 (LEGACY     |  C-1 PASS  (assessor, at)      |
|   Step 47/49 evidence reference only)      [RO]   |  C-2 FAIL  -> QA evidence      |
|                                                   |  C-3 NOT_TESTED (no assessor)  |
|                                                   |  NOTE: agent completion != PASS|
+---------------------------------------------------+--------------------------------+
| [P2] ARTIFACT & EVIDENCE WORKSPACE                                        [RO]   |
|  delivery items | artifacts | QA | source control | security boundary |          |
|  demo evidence | cost | external actions | audit                                 |
|  art_5  generation_mode: deterministic-template  partner: - (runtime_agent)       |
|         review: pending  test: PASS  safety: sandbox    ->/workspace              |
|  art_6  generation_mode: external-partner-generated  partner: Codex (ai_partner)  |
|         review: approved test: PASS  safety: sandbox    ->/sandbox-github         |
|  (never shown: chain of thought, raw tokens, secrets, credentials, DSNs)          |
+----------------------------------------------------------------------------------+
| [P1] REVIEW GATE ACTION  (six, exactly)     [W] | [P1] PRODUCT OWNER DECISION [W] |
|  ( ) ACCEPT              available              |  --- SEPARATE PANEL ---          |
|  ( ) REJECT              available              |  Effective decision: none        |
|  ( ) REQUEST_CHANGES     available              |  (status projection only when set)|
|  ( ) RERUN_QA            disabled: 1 of 1 used  |  Decisions: exactly three        |
|  ( ) ESCALATE            available              |   ACCEPTED                       |
|  ( ) ARCHIVE             not applicable         |   ACCEPTED_WITH_FOLLOW_UP        |
|  {Continue}                                     |   REJECTED                       |
|  A review action is a workflow move.            |  History (incl. superseded): 0   |
+-------------------------------------------------+---------------------------------+
| [P3] FOLLOW-UPS (only for ACCEPTED_WITH_FOLLOW_UP) - none                         |
| [P3] DECISION HISTORY - immutable; superseded entries remain visible       [RO]   |
+----------------------------------------------------------------------------------+
```

---

## WF-05 — ACCEPT decision flow (confirmation dialog)

```text
+---------------------------- Record Acceptance Decision ---------------------------+
| [P1] Two records will be written together (one transaction, two records):          |
|                                                                                   |
|   Step 1  Review Gate Action .... ACCEPT                                           |
|   Step 2  Final Decision ........ ( ) ACCEPTED                                     |
|                                   (o) ACCEPTED_WITH_FOLLOW_UP                      |
|                                                                                   |
| Reason (required) [__________________________________________]              [W]   |
| Evidence reviewed  [x] QA report  [x] artifacts  [ ] audit trail                   |
| Follow-up items (non-blocking only):                                              |
|   1. "Add rate-limit doc"  owner: PM  severity: low  blocking: NO                 |
|   [+ Add follow-up]                                                               |
|                                                                                   |
| ! Blocking follow-ups are not allowed here. If a follow-up is blocking, use        |
|   Request Changes instead. (submit stays disabled while any item is blocking)      |
| ! Decision history is append-only. A later correction supersedes this record;      |
|   it never overwrites or deletes it.                                              |
|                                                                                   |
|                        (cta Cancel)      {Record Acceptance Decision}             |
+-----------------------------------------------------------------------------------+
[PERM] requires verified human actor with PO decision capability; if identity is not
verified -> submit blocked with a security notice (RA-2 dependency).
```

---

## WF-06 — REQUEST_CHANGES flow

```text
+-------------------------- Request Changes (no final decision) --------------------+
| This records a Review Gate Action only. No Product Owner Decision is created.      |
|                                                                                   |
| Reason (required)          [_______________________________________]        [W]   |
| Requested scope            [_______________________________________]              |
| Affected criteria / items  [x] C-2 FAIL   [ ] C-3 NOT_TESTED                      |
| Required evidence          [x] updated QA report                                  |
|                                                                                   |
| ! A new DeliverySubmission version will be required.                              |
|                          (cta Cancel)          {Request Changes}                  |
+-----------------------------------------------------------------------------------+
```

---

## WF-07 — RERUN_QA available (0 of 1)

```text
+------------------------------- Re-run QA (bounded) -------------------------------+
| QA reruns used: 0 of 1        (source: authoritative persisted actions)            |
| This asks for re-verification only. No content change is requested and no          |
| Product Owner Decision is created.                                                |
|                                                                                   |
| Reason (required)      [__________________________________]                 [W]   |
| QA scope               [ full | targeted: C-2 ]                                   |
| Previous QA reference  qa_run_77                                                  |
|                          (cta Cancel)             {Re-run QA}                     |
+-----------------------------------------------------------------------------------+
```

## WF-08 — RERUN_QA exhausted (1 of 1)

```text
+------------------------------- Re-run QA (bounded) -------------------------------+
| QA reruns used: 1 of 1        (source: authoritative persisted actions)            |
|                                                                                   |
| [!] QA rerun limit reached. Use Request Changes, Escalate, or Reject.              |
|     (no submit control is rendered - not merely visually disabled)                 |
|                                                                                   |
|  {Request Changes}   {Escalate}   {Reject}          (cta Close)                    |
+-----------------------------------------------------------------------------------+
Client counters never determine this state; the backend value governs.
```

---

## WF-09 — Expired submission

```text
+----------------------------------------------------------------------------------+
| [P1] REVIEW CONTEXT  submission v3   Status: EXPIRED (warning, not error)          |
|      Review window closed 2h ago (server-provided due time)                       |
+----------------------------------------------------------------------------------+
| [!] This delivery review has expired.                                             |
|     Create or request a new DeliverySubmission version before continuing.         |
+----------------------------------------------------------------------------------+
| REVIEW GATE ACTION                                                                |
|  ACCEPT           disabled - expired                                              |
|  REJECT           disabled - expired                                              |
|  RERUN_QA         disabled - expired                                              |
|  REQUEST_CHANGES  disabled - a new version is required                             |
|  ESCALATE         available                                                       |
|  ARCHIVE          available (archiving is neither acceptance nor rejection)        |
+----------------------------------------------------------------------------------+
| PRODUCT OWNER DECISION - no new final decision can be recorded while expired      |
| Evidence and decision history remain fully readable                        [RO]   |
+----------------------------------------------------------------------------------+
| Countdown elsewhere in the UI is labelled "Estimated from server-provided due      |
| time" and can never re-enable a disabled control.                                 |
+----------------------------------------------------------------------------------+
```

---

## WF-10 — Stale / conflict recovery

```text
+------------------------- This submission changed -------------------------+
| [!] 409 DELIVERY_VERSION_CONFLICT                                         |
|                                                                           |
| What changed:                                                             |
|   submission version   v3  ->  v4                                         |
|   review status        UNDER_REVIEW -> CHANGES_REQUESTED                   |
|   your action          ACCEPT (not submitted)                              |
|                                                                           |
| Your reason text has been kept:                                           |
|   "Looks good apart from the rate-limit note..."                          |
|                                                                           |
| We stopped before writing anything. Nothing was submitted and nothing was  |
| retried automatically.                                                    |
|                                                                           |
|   {Reload current version}      (cta Discard my draft text)                |
+---------------------------------------------------------------------------+
Same pattern for FINAL_DECISION_ALREADY_EXISTS / DECISION_ALREADY_SUPERSEDED /
QA_RERUN_LIMIT_REACHED - each names the specific changed record, never a generic error,
and never auto-resends a final decision.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
