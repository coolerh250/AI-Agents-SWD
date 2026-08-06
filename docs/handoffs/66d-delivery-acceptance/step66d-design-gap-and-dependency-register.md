# Step 66D-DESIGN — Gap and Dependency Register

> **Read-only register. Every implementation-related item is NOT IMPLEMENTED and NOT AUTHORIZED.
> `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
GAP COUNT:          15  (measured: manifest open_gaps length / this document's gap headings)
CRITICAL:           4   (DG-01, DG-02, DG-05, DG-09)
```

Legend — `Blocking design implementation` = whether FE work on that surface can begin at all once
authorized.

### DG-01 — Unified Control Center route absent
```text
Observed current state:  grep 'control-center' apps/admin-console/src/App.tsx -> 0 matches
Required UX behavior:    /projects/:projectId/control-center renders the frozen IA
Dependency:              FE1 route creation + project_delivery_control_center read model
Recommended slice:       Step 66D-FE1 (route/shell) after Step 66D-BE4 (read model)
Risk:                    CRITICAL - the canonical IA has no host surface
Blocking design impl:    YES
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-02 — Delivery Inbox route is a placeholder
```text
Observed current state:  /delivery-inbox exists, renders PlaceholderPage ("Requires Step 66D")
Required UX behavior:    cross-project DeliveryReviewTask queue per the inbox spec
Dependency:              review-task queue read model + GET /delivery-submissions (list)
Recommended slice:       Step 66D-BE2 then Step 66D-FE1
Risk:                    CRITICAL - the PO entry point to review work does not function
Blocking design impl:    YES
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-03 — Delivery Review route absent (submission-scoped)
```text
Observed current state:  grep 'delivery-submissions' App.tsx -> 0 matches; /delivery-detail exists
                         but is id-less and cannot address a DeliverySubmission
Required UX behavior:    /delivery-submissions/:deliverySubmissionId/review review workspace
Dependency:              FE1/FE2 route creation + submission/action/decision APIs
Recommended slice:       Step 66D-FE1 (observation), Step 66D-FE2 (actions)
Risk:                    HIGH
Blocking design impl:    YES
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-04 — Unified read model unavailable
```text
Observed current state:  project_delivery_control_center specified in ARCH1, not implemented; no
                         projector, cache or endpoint exists
Required UX behavior:    one document per project with as_of + is_stale and UNKNOWN-on-absence
Dependency:              Step 66D-BE4 (events, outbox, projection)
Risk:                    CRITICAL-adjacent (drives DG-01)
Blocking design impl:    YES for the Control Center
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-05 — DeliverySubmission API unavailable
```text
Observed current state:  no submission persistence, no endpoints (ARCH1 marks every endpoint
                         NOT IMPLEMENTED); no 66D client in apps/admin-console/src/api
Required UX behavior:    list/read/traceability/evidence/audit reads for Inbox + Review
Dependency:              Step 66D-BE1 (domain/migrations) + Step 66D-BE2 (APIs)
Risk:                    CRITICAL - nothing to review without it
Blocking design impl:    YES
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-06 — Review action API unavailable
```text
Observed current state:  POST /review-actions not implemented
Required UX behavior:    the exact six Review Gate Actions, idempotent, If-Match guarded
Dependency:              Step 66D-BE3
Risk:                    HIGH
Blocking design impl:    YES for FE2
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-07 — Product Owner decision API unavailable
```text
Observed current state:  POST /po-decisions not implemented; no immutable decision store
Required UX behavior:    exactly three decisions; append-only; supersession; effective-decision read
Dependency:              Step 66D-BE3 (+ BE1 persistence), ADR-66D-02/10
Risk:                    HIGH
Blocking design impl:    YES for FE2
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-08 — Follow-up API unavailable
```text
Observed current state:  follow-up endpoints not implemented
Required UX behavior:    non-blocking follow-ups; blocking guard returning
                         409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES
Dependency:              Step 66D-BE3
Risk:                    MEDIUM
Blocking design impl:    YES for the follow-up panel
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-09 — Verified human identity unavailable
```text
Observed current state:  POC sandbox/test operator identity only; verified shared-runtime identity
                         decided by RA-2 (RA2-D01..D12) and NOT IMPLEMENTED (ARCH1-G08)
Required UX behavior:    ACCEPT/REJECT require a verified human actor; UI must block final decisions
                         and show a security notice while identity is unverified
Dependency:              RA-2 (RA-2I0 onward) - NOT AUTHORIZED
Risk:                    CRITICAL - a production-grade acceptance flow cannot be claimed, only a
                         sandbox one
Blocking design impl:    Blocks production-grade FE2 acceptance; sandbox observation unaffected
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-10 — TASK_ROLES capability mapping unavailable
```text
Observed current state:  TASK_ROLES exist in shared/sdk/tasks/rbac.py; the 66D capability mapping is
                         specified in ARCH1 section 8 but NOT implemented, and this stage must not
                         modify TASK_ROLES
Required UX behavior:    render available / disabled / not-authorized per capability
Dependency:              Step 66D-BE2/BE3 authorization implementation
Risk:                    HIGH
Blocking design impl:    Partially - UI can render states, but real authorization must come from
                         the server
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-11 — Freshness metadata unavailable
```text
Observed current state:  no as_of / is_stale surface exists for a 66D read model
Required UX behavior:    FreshnessIndicator on every Control Center section; stale-before-write
                         re-fetch rule
Dependency:              Step 66D-BE4
Risk:                    MEDIUM-HIGH (stale-decision risk if omitted)
Blocking design impl:    YES for the freshness contract
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-12 — Deep-link context gaps
```text
Observed current state:  existing specialized routes accept no 66D context parameters
                         (project/work-item/workflow/run/submission/review-task/artifact/return_to)
Required UX behavior:    context-preserving drill-down and return without re-selecting a project
Dependency:              Step 66D-FE1 (+ per-route query handling); return_to allow-list validation
Risk:                    MEDIUM
Blocking design impl:    NO (degrades gracefully to default views)
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-13 — Responsive component gaps
```text
Observed current state:  no responsive table->card pattern and no small-mobile write-unsupported
                         notice component exist
Required UX behavior:    1440/1280/1024/768 behavior + explicit unsupported-write message < 768
Dependency:              Step 66D-FE1/FE2
Risk:                    MEDIUM
Blocking design impl:    NO
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-14 — Accessibility component gaps
```text
Observed current state:  no accessible modal/confirmation pattern, no error-summary pattern, and no
                         polite/assertive live-region utility exist in components/
Required UX behavior:    focus-trapped cancellable dialogs, first-error focus, status announcements,
                         aria-sort tables
Dependency:              Step 66D-FE1/FE2 (shared a11y primitives)
Risk:                    MEDIUM-HIGH (AC-15 cannot pass without it)
Blocking design impl:    NO, but required before FE2 acceptance
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-15 — Existing-route inconsistency (`/delivery-detail`)
```text
Observed current state:  an id-less /delivery-detail placeholder overlaps the submission-scoped
                         review route conceptually while being unable to address a submission
Required UX behavior:    single canonical review route; /delivery-detail retired or redirected
Dependency:              Step 66D-FE1 route decision (Codex), design disposition recorded in
                         step66d-design-route-and-drilldown-map.md section 2.1
Risk:                    LOW-MEDIUM (navigation ambiguity)
Blocking design impl:    NO
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

### DG-16 — OperatorConsole legacy review controls overlap the new Delivery Review
```text
Observed current state:  /operator (OperatorConsole.tsx) already renders OperatorReviewPanel
                         ({ packageId }) with accept / reject / requestChanges / addNote /
                         rerunVerification via actionClient's private POST helper, gated to
                         role operator|platform_admin, using a two-step confirmation nonce.
                         It is addressed by the LEGACY DeliveryPackage id, records a single
                         mutable human_acceptance_status, has no decision history, no
                         supersession, no ACCEPTED_WITH_FOLLOW_UP, and no per-submission-version
                         QA rerun bound. It was not analysed in the original design package.
Required UX behavior:    Delivery Review must be the SINGLE canonical Product Owner Decision entry
                         point. /operator must never present or record a ProductOwnerDecision;
                         its accept/reject stay legacy package-level operational controls and must
                         be labelled as such. Reuse only the confirmation/idempotency/session
                         patterns; never the legacy acceptance semantics or the `note` action.
Dependency:              FE2 coexistence gate + the deferred legacy DeliveryPackage migration
                         question (66D-D04 defers migration to a separate authorization)
Recommended slice:       Step 66D-FE2 (coexistence gate), with retire-vs-keep deferred to its own
                         authorized stage
Risk:                    MEDIUM_HIGH - two surfaces could otherwise both look like the acceptance
                         entry point, and an operator "accept" could be mistaken for a PO decision
Blocking design impl:    NO for FE1; YES as a gate before any FE2 acceptance control
Authorization status:    NOT IMPLEMENTED / NOT AUTHORIZED
```

## Summary

```text
Total gaps:                 16
Critical:                   4    (DG-01, DG-02, DG-05, DG-09)
Backend-dependent:          9    (DG-01, DG-02, DG-03, DG-04, DG-05, DG-06, DG-07, DG-08, DG-11)
Identity-dependent:         2    (DG-09, DG-10)
Existing-route-dependent:   4    (DG-02, DG-12, DG-15, DG-16)
Frontend-only once authorized: 3 (DG-12, DG-13, DG-14)
Authorized for implementation: 0
```

Gap count is machine-measured (`DG-` headings in this file / `open_gaps` length in the JSON
manifest); it was **not** held at 15 to preserve the earlier figure.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
