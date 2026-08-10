# Step 66D-DESIGN-M1 — Canonical Merge Record

> **Merge and record only. No frontend, backend, runtime, API, database, migration, identity,
> secret, feature-gate or deployment change. No container, database, Redis, Kubernetes, Vault,
> OIDC provider, agent workflow or external provider started. `production_executed_true_count: 0`.**

## 1. Identity

```text
Stage:                  Step 66D-DESIGN-M1
Executor:               Claude Code
Authorization:          Product Owner (explicit, this stage)
PR:                     #26  design/66d-unified-control-center-ux -> main
Merge authorization:    GRANTED
```

## 2. Commit chain

```text
Pre-merge main:         9c5210d190b82b76575ba8d456b5d2005c2867d2
Original design commit: 47dcbe9feda6633e3d0835d16dcaa0866a26c2cf
RM1 commit:             c9ee13b7389f0b4977cab835337c828675a4a67d
RM2 / PR head:          bb8eab70ee7fb252329fe05c4b7039c2ed0f694b
Merge commit:           e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2
Merge parent 1:         9c5210d190b82b76575ba8d456b5d2005c2867d2
Merge parent 2:         bb8eab70ee7fb252329fe05c4b7039c2ed0f694b
```

```text
Merge method:                       NON-SQUASH MERGE, --match-head-commit bb8eab7
Parent count:                       2  (two-parent merge commit)
PR commit count:                    3
Original PR commits preserved:      YES -- all three are ancestors of main
  47dcbe9 ancestor of main:         exit 0
  c9ee13b ancestor of main:         exit 0
  bb8eab7 ancestor of main:         exit 0
Rebase / Squash / Amend:            NO / NO / NO
Force-push:                         NO
Additional PR commits:              NONE
PR final state:                     MERGED (2026-08-10T02:27:01Z)
```

## 3. Canonical design decision (now binding)

```text
Canonical IA:             UNIFIED_CONTROL_CENTER
Implementation principle: UNIFIED_OVERVIEW_WITH_EXISTING_ROUTE_DRILL_DOWN
Decision authority:       Product Owner
Option comparison:        CLOSED / NOT REOPENED
Non-selected alternative: COORDINATED_EXISTING_ROUTES (historical, superseded)
```

Frozen contract surface carried into main:

```text
Review Gate Actions       6  ACCEPT REJECT REQUEST_CHANGES RERUN_QA ESCALATE ARCHIVE
Product Owner Decisions   3  ACCEPTED ACCEPTED_WITH_FOLLOW_UP REJECTED
Canonical statuses        9  DRAFT SUBMITTED UNDER_REVIEW CHANGES_REQUESTED
                             QA_RERUN_REQUESTED ACCEPTED REJECTED ARCHIVED EXPIRED
Data states               7  loading empty partial stale inaccessible error unknown
Permission states         6  (separate dimension, never multiplied into the data-state matrix)
Open gaps                16  DG-01 .. DG-16, 0 authorized
Mutation surfaces         5  TaskNew TaskDetail TaskWorkroom MultiProjectDelivery OperatorConsole
Wireframes               10  Component candidates 22  Acceptance criteria 18
QA rerun                  1 per DeliverySubmission version, backend-authoritative (ADR-66D-09)
Delivery Review           sole canonical ProductOwnerDecision entry surface
OperatorConsole           legacy operational review; documented coexistence; DG-16; never a PO
                          decision entry point
Inbox status filters      delivery_review_task_status / delivery_submission_status
```

## 4. Design scope, frozen

```text
Design changed paths:     14 exact
  9 design artifacts / 3 handoff-evidence artifacts / 1 verifier / 1 test
Old YAML manifest:        ABSENT
JSON manifest:            PRESENT (step66d-design-contract-manifest.json)
Frontend / backend / runtime / migration / infra paths:  0
Historical verifier or test paths:                       0
ARCH1 contracts / ADR-66D-09 / TASK_ROLES:               UNCHANGED
```

### Post-merge positive scope freeze (bounded adaptation)

While PR #26 was open the design verifier computed its positive scope as
`DESIGN_BASELINE...HEAD`. That was safe only because `HEAD` was the PR head and was bounded by the
exact 14-path registry. Merged, `HEAD` is `main` and advances with every later authorised stage, so
it can no longer be a positive endpoint.

```text
DESIGN_BASELINE:      9c5210d190b82b76575ba8d456b5d2005c2867d2
DESIGN_STAGE_HEAD:    bb8eab70ee7fb252329fe05c4b7039c2ed0f694b
Fixed positive range: 9c5210d...bb8eab7
Registered paths:     14
Actual paths:         14
Exact equality:       YES
Positive HEAD endpoints remaining: 0
```

The rejection guard was deliberately **not** frozen with the positive scope. `RUNTIME_GUARD_ANCHOR`
remains HEAD-relative and feeds the denylist only, so a runtime or frontend path introduced by any
later commit is still caught. A denylist that cannot see current state is not a denylist.

```text
Bounded adaptation files:
  scripts/verify_step66d_design_unified_control_center.py
  tests/test_step66d_design_unified_control_center.py
Product design semantics changed:  NONE
IA / route / OperatorConsole / ARCH1 / ADR-66D-09 / QA rerun / handoff semantics:  UNCHANGED
```

## 5. Review closure

```text
Step 66D-DESIGN-R1:   REMEDIATION_REQUIRED  -> F01..F12 raised
Step 66D-DESIGN-RM1:  F01..F12 remediated
Step 66D-DESIGN-R2:   REMEDIATION_REQUIRED  -> R2-F01, R2-F02, R2-F03 raised
Step 66D-DESIGN-RM2:  R2-F01, R2-F02, R2-F03 remediated
Step 66D-DESIGN-R3:   PASS_WITH_ADVISORY

R2-F01 placeholder-route truthfulness:  CLOSED
        four-representation equality (App.tsx / route_inventory / semantic_routes / route-map
        document), negation-aware classifier, structurally scoped document table parser
R2-F02 regression evidence:             CLOSED
        canonical main has 0 failures on both suite selections; superseded claims retained under
        explicit SUPERSEDED / NOT CURRENT framing
R2-F03 stale metrics:                   CLOSED
        checks_run=135 and 23 passed exist only inside SUPERSEDED blocks; RM1 and RM2 metrics
        recorded as separate rows
```

## 6. Verification (machine-measured)

Pre-merge, at the exact PR head `bb8eab7`:

```text
STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS
  DESIGN_RM1_SCOPE_EXACT:        PASS
  DESIGN_RM1_SOURCE_COUNTS:      PASS
  DESIGN_RM1_ENUM_INTEGRITY:     PASS
  DESIGN_RM1_ROUTE_TRUTHFULNESS: PASS
  DESIGN_RM1_REGRESSION_CLOSURE: PASS
CHECK_DEFINITIONS:      52   (explicit unique named registry)
ASSERTIONS_EXECUTED:    437  (runtime counter)
Design tests:           47 passed, 0 failed, 0 skipped
Suite Set A (9 suites): 716 passed, 0 failed, 0 skipped
Suite Set B (11 suites): 878 passed, 0 failed, 0 skipped
ruff / black / mypy:    PASS / PASS / PASS
git diff --check:       clean
```

Measurement environment (recorded to avoid re-introducing locale measurement contamination):

```text
OS Windows 11 · Python 3.14.4 · pytest 9.0.3
PYTHONUTF8=1 · PYTHONIOENCODING=utf-8 · preferred encoding utf-8 · filesystem encoding utf-8
Dependency environment: pre-existing approved local environment; no package installed, no
requirements or lockfile modified.
```

## 7. Advisories — recorded, deliberately not remediated

```text
ADV-UTF8-01   TRACKED / NON-BLOCKING / NOT REMEDIATED
  Accurate description: a historical locale-portability exposure exists in
  subprocess.run(..., text=True) called WITHOUT an explicit encoding= argument, in several
  historical stage verifiers and tests. Under a non-UTF-8 console codepage the child process
  output is decoded with the locale codec and raises UnicodeDecodeError on the first non-ASCII
  byte. This is NOT "bare read_text() without encoding" -- the historical tests and verifiers all
  pass encoding= to read_text.
  Not introduced by PR #26. No historical verifier or test was modified by this stage.
  Recommended: a separate authorized test-portability hardening stage.

ADV-SUITE-01  TRACKED / NON-BLOCKING / NOT REMEDIATED
  Suite Set A was reconstructed during review but is not a committed regression-selection
  artifact. No new historical suite manifest was created by this stage.
  Recommended: future review stages commit their regression selection.
```

## 8. Authorization state after this stage

```text
STEP66D_DESIGN_M1:               PASS
PR26:                            MERGED
STEP66D_DESIGN:                  PASS / CLOSED / CANONICALIZED
UNIFIED_CONTROL_CENTER_IA:       BINDING / CANONICAL
DESIGN_CONTRACT:                 FROZEN / CANONICALIZED
FRONTEND_IMPLEMENTATION:         NOT STARTED
BACKEND_IMPLEMENTATION:          NOT STARTED
STEP66D_FE1:                     NOT AUTHORIZED
STEP66D_FE2:                     NOT AUTHORIZED
STEP66D_BE1_BE4:                 NOT AUTHORIZED
STEP66D_QA:                      NOT AUTHORIZED
STEP67POC0:                      NOT AUTHORIZED
RA2I0:                           NOT AUTHORIZED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

No Control Center page, Delivery Inbox, Delivery Review surface, API, migration or read model was
created. `DeliverySubmission` remains a frozen contract with no implementation. Nothing was
deployed, no shared database was contacted, no secret was accessed, no external provider was
called, and no resume/replay path was enabled.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
